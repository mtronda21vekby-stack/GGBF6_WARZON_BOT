# fps_coach_bot_v4.py
# Telegram FPS Coach Bot (Render + long polling)
# Games: Warzone / BO7 / BF6
# Features: stable polling, conflict backoff, safe animation, UI hide/show, persona/talk, optional persistence.

import os
import time
import json
import threading
import logging
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests

# OpenAI SDK (optional)
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError


# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_bot")


# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# Optional persistence (use Render persistent disk and point DATA_DIR to it)
DATA_DIR = os.getenv("DATA_DIR", "/tmp").strip()
STATE_PATH = os.path.join(DATA_DIR, "fps_coach_state.json")

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
TG_LONGPOLL_TIMEOUT = int(os.getenv("TG_LONGPOLL_TIMEOUT", "50"))
TG_RETRIES = int(os.getenv("TG_RETRIES", "5"))

# Animation safety (Telegram edit limits)
PULSE_MIN_SECONDS = float(os.getenv("PULSE_MIN_SECONDS", "1.25"))

# Anti-flood per chat
MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.25"))

# Conflict getUpdates backoff (409)
CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

# Default UI mode for new users
UI_DEFAULT = os.getenv("UI_DEFAULT", "show").strip().lower()
if UI_DEFAULT not in ("show", "hide"):
    UI_DEFAULT = "show"

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN")


# =========================
# OpenAI client (optional)
# =========================
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=30,
            max_retries=0,  # we retry ourselves
        )
    except TypeError:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


# =========================
# Requests session
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-bot/4.0"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))


# =========================
# Persistence (optional)
# =========================
def _safe_mkdir(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

_safe_mkdir(DATA_DIR)

USER_PROFILE = {}  # chat_id -> dict
USER_MEMORY = {}   # chat_id -> list[{role, content}]
LAST_MSG_TS = {}   # chat_id -> float

MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))

_state_lock = threading.Lock()

def load_state():
    global USER_PROFILE, USER_MEMORY
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            USER_PROFILE = {int(k): v for k, v in (data.get("profiles") or {}).items()}
            USER_MEMORY = {int(k): v for k, v in (data.get("memory") or {}).items()}
            log.info("State loaded: profiles=%d memory=%d (%s)", len(USER_PROFILE), len(USER_MEMORY), STATE_PATH)
    except Exception as e:
        log.warning("State load failed: %r", e)

def save_state():
    try:
        with _state_lock:
            data = {
                "profiles": {str(k): v for k, v in USER_PROFILE.items()},
                "memory": {str(k): v for k, v in USER_MEMORY.items()},
                "saved_at": int(time.time()),
            }
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        log.warning("State save failed: %r", e)

def autosave_loop(stop: threading.Event, interval_s: int = 60):
    while not stop.is_set():
        stop.wait(interval_s)
        if stop.is_set():
            break
        save_state()

load_state()


# =========================
# Knowledge base (expandable)
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "pillars": (
            "ð§  Warzone â ÑÑÐ½Ð´Ð°Ð¼ÐµÐ½Ñ\n"
            "â¢ ÐÐ¾Ð·Ð¸ÑÐ¸Ñ/ÑÐ°Ð¹Ð¼Ð¸Ð½Ð³ > ÐºÐ¸Ð»Ð»Ñ\n"
            "â¢ ÐÐ½ÑÐ¾: ÑÐ°Ð´Ð°Ñ/Ð·Ð²ÑÐº/Ð¿Ð¸Ð½Ð³Ð¸\n"
            "â¢ ÐÑÐµ-ÑÐ¹Ð¼ + Ð¸Ð³ÑÐ° Ð¾Ñ ÑÐºÑÑÑÐ¸Ð¹\n"
            "â¢ Ð Ð¾ÑÐ°ÑÐ¸Ð¸ Ð·Ð°ÑÐ°Ð½ÐµÐµ, Ð½Ðµ Ð¿Ð¾Ð·Ð´Ð½Ð¾\n"
            "â¢ ÐÐ¾Ð½ÑÐ°ÐºÑ â ÑÐµÐ¿Ð¾Ð·Ð¸ÑÐ¸Ñ\n"
        ),
        "settings": (
            "ð Warzone â Ð±Ð°Ð·Ð¾Ð²ÑÐ¹ ÑÐµÑÐ°Ð¿ (ÐºÐ¾Ð½ÑÑÐ¾Ð»Ð»ÐµÑ)\n"
            "â¢ Sens: 6â8 (ÑÑÐ°ÑÑ 7/7)\n"
            "â¢ ADS: 0.90 low / 0.85 high\n"
            "â¢ Aim Assist: Dynamic (ÐµÑÐ»Ð¸ Ð¼Ð¸Ð¼Ð¾ â Standard)\n"
            "â¢ Deadzone min: 0.05 (Ð´ÑÐ¸ÑÑ â 0.07â0.10)\n"
            "â¢ FOV: 105â110 | ADS FOV Affected: ON | Weapon FOV: Wide\n"
            "â¢ Camera Movement: Least\n"
        ),
        "drills": {
            "aim": "ð¯ Aim (20Ð¼)\n10Ð¼ warm-up\n5Ð¼ ÑÑÐµÐºÐ¸Ð½Ð³\n5Ð¼ Ð¼Ð¸ÐºÑÐ¾",
            "recoil": "ð« Recoil (20Ð¼)\n5Ð¼ 15â25Ð¼\n10Ð¼ 25â40Ð¼\n5Ð¼ Ð´Ð¸ÑÑÐ¸Ð¿Ð»Ð¸Ð½Ð°",
            "movement": "ð¹ Movement (15Ð¼)\nÑÐ³Ð¾Ð»âÑÐ»Ð°Ð¹Ð´âÐ¿Ð¸Ðº\nÐ´Ð¶Ð°Ð¼Ð¿-Ð¿Ð¸ÐºÐ¸\nÑÐµÐ¿Ð¾Ð·Ð¸ÑÐ¸Ñ",
        },
        "plan": (
            "ð ÐÐ»Ð°Ð½ 7 Ð´Ð½ÐµÐ¹ â Warzone\n"
            "Ð1â2: warm-up 10Ð¼ + aim 15Ð¼ + movement 10Ð¼ + Ð¼Ð¸Ð½Ð¸-ÑÐ°Ð·Ð±Ð¾Ñ 5Ð¼\n"
            "Ð3â4: warm-up 10Ð¼ + Ð´ÑÑÐ»Ð¸/ÑÐ³Ð»Ñ 15Ð¼ + Ð´Ð¸ÑÑÐ¸Ð¿Ð»Ð¸Ð½Ð° 10Ð¼ + Ð²ÑÐ²Ð¾Ð´ 5Ð¼\n"
            "Ð5â6: warm-up 10Ð¼ + Ð¸Ð³ÑÐ° Ð¾Ñ Ð¸Ð½ÑÐ¾ 20Ð¼ + ÑÐ¸ÐºÑÐ°ÑÐ¸Ñ Ð¾ÑÐ¸Ð±Ð¾Ðº 5Ð¼\n"
            "Ð7: 30â60Ð¼ Ð¸Ð³ÑÑ + ÑÐ°Ð·Ð±Ð¾Ñ 2 ÑÐ¼ÐµÑÑÐµÐ¹ 10Ð¼\n"
        ),
        "vod": (
            "ð¼ VOD-ÑÐ°Ð±Ð»Ð¾Ð½ (Warzone)\n"
            "1) Ð ÐµÐ¶Ð¸Ð¼/ÑÐºÐ²Ð°Ð´\n2) ÐÐ´Ðµ Ð±Ð¾Ð¹\n3) ÐÐ°Ðº ÑÐ¼ÐµÑ\n"
            "4) Ð ÐµÑÑÑÑÑ (Ð¿Ð»Ð¸ÑÑ/ÑÐ¼Ð¾Ðº/ÑÐ°Ð¼Ð¾ÑÐµÐ·)\n5) ÐÐ»Ð°Ð½ (Ð¿ÑÑ/Ð¾ÑÑÐ¾Ð´/ÑÐ¾ÑÐ°ÑÐ¸Ñ)\n"
        ),
    },
    "bo7": {
        "name": "Call of Duty: BO7",
        "pillars": (
            "ð§  BO7 â ÑÑÐ½Ð´Ð°Ð¼ÐµÐ½Ñ\n"
            "â¢ Ð¦ÐµÐ½ÑÑ ÑÐºÑÐ°Ð½Ð° + Ð¿ÑÐµÑÐ°Ð¹Ñ\n"
            "â¢ Ð¢Ð°Ð¹Ð¼Ð¸Ð½Ð³Ð¸: Ð¿Ð¸Ðº Ð¿Ð¾ Ð¸Ð½ÑÐµ\n"
            "â¢ 2 ÑÐµÐº Ð½Ð° Ð¿Ð¾Ð·Ð¸ÑÐ¸Ð¸ â ÑÐ¼ÐµÐ½Ð°\n"
            "â¢ Ð ÐµÐ¿Ð¸Ðº ÑÐ¾Ð»ÑÐºÐ¾ Ñ Ð´ÑÑÐ³Ð¾Ð³Ð¾ ÑÐ³Ð»Ð°\n"
        ),
        "settings": (
            "ð BO7 â Ð±Ð°Ð·Ð¾Ð²ÑÐ¹ ÑÐµÑÐ°Ð¿ (ÐºÐ¾Ð½ÑÑÐ¾Ð»Ð»ÐµÑ)\n"
            "â¢ Sens: 6â8 (Ð¿ÐµÑÐµÐ»ÐµÑÐ°ÐµÑÑ â -1)\n"
            "â¢ ADS: 0.80â0.95\n"
            "â¢ Deadzone min: 0.03â0.07\n"
            "â¢ Curve: Dynamic/Standard\n"
            "â¢ FOV: 100â115\n"
        ),
        "drills": {
            "aim": "ð¯ Aim (20Ð¼)\nÐ¿ÑÐµÑÐ°Ð¹Ñ\nÑÑÐµÐºÐ¸Ð½Ð³\nÐ¼Ð¸ÐºÑÐ¾",
            "recoil": "ð« Recoil (15Ð¼)\nÐºÐ¾ÑÐ¾ÑÐºÐ¸Ðµ Ð¾ÑÐµÑÐµÐ´Ð¸\nÐ¿ÐµÑÐ²Ð°Ñ Ð¿ÑÐ»Ñ",
            "movement": "ð¹ Movement (15â20Ð¼)\nÑÐµÐ¿Ð¸ÐºÐ¸\nÑÐ°Ð¹Ð¼Ð¸Ð½Ð³\nÑÑÑÐµÐ¹Ñ",
        },
        "plan": (
            "ð ÐÐ»Ð°Ð½ 7 Ð´Ð½ÐµÐ¹ â BO7\n"
            "Ð1â2: aim 20Ð¼ + movement 10Ð¼\n"
            "Ð3â4: ÑÐ³Ð»Ñ/ÑÐ°Ð¹Ð¼Ð¸Ð½Ð³Ð¸ 25Ð¼ + Ð¼Ð¸Ð½Ð¸-ÑÐ°Ð·Ð±Ð¾Ñ 5Ð¼\n"
            "Ð5â6: Ð´ÑÑÐ»Ð¸ 30Ð¼\n"
            "Ð7: 45â60Ð¼ + ÑÐ°Ð·Ð±Ð¾Ñ 2â3 ÑÐ¼ÐµÑÑÐµÐ¹\n"
        ),
        "vod": "ð¼ BO7: ÑÐµÐ¶Ð¸Ð¼/ÐºÐ°ÑÑÐ°, ÑÐ¼ÐµÑÑÑ, Ð¸Ð½ÑÐ¾ (ÑÐ°Ð´Ð°Ñ/Ð·Ð²ÑÐº), ÑÑÐ¾ ÑÐ¾ÑÐµÐ» ÑÐ´ÐµÐ»Ð°ÑÑ.",
    },
    "bf6": {
        "name": "BF6",
        "pillars": (
            "ð§  BF6 â ÑÑÐ½Ð´Ð°Ð¼ÐµÐ½Ñ\n"
            "â¢ ÐÐ¸Ð½Ð¸Ð¸ ÑÑÐ¾Ð½ÑÐ°/ÑÐ¿Ð°Ð²Ð½Ñ\n"
            "â¢ ÐÐ¸ÐºâÐ¸Ð½ÑÐ¾âÐ¾ÑÐºÐ°Ñ\n"
            "â¢ Ð¡ÐµÑÐ¸Ñ â ÑÐµÐ¿Ð¾Ð·Ð¸ÑÐ¸Ñ\n"
        ),
        "settings": (
            "ð BF6 â Ð±Ð°Ð·Ð°\n"
            "â¢ Sens: ÑÑÐµÐ´Ð½ÑÑ, ADS Ð½Ð¸Ð¶Ðµ\n"
            "â¢ Deadzone: Ð¼Ð¸Ð½Ð¸Ð¼ÑÐ¼ Ð±ÐµÐ· Ð´ÑÐ¸ÑÑÐ°\n"
            "â¢ FOV: Ð²ÑÑÐ¾ÐºÐ¸Ð¹ (ÐºÐ¾Ð¼ÑÐ¾ÑÑ)\n"
            "â¢ ÐÐ¾Ð½ÑÐ°ÐºÑ â ÑÐ¼ÐµÐ½Ð° Ð¿Ð¾Ð·Ð¸ÑÐ¸Ð¸\n"
        ),
        "drills": {
            "aim": "ð¯ Aim (15â20Ð¼)\nÐ¿ÑÐµÑÐ°Ð¹Ñ\nÑÑÐµÐºÐ¸Ð½Ð³\nÑÐµÐ¿Ð¾Ð·Ð¸ÑÐ¸Ñ",
            "recoil": "ð« Recoil (15Ð¼)\nÐºÐ¾ÑÐ¾ÑÐºÐ¸Ðµ Ð¾ÑÐµÑÐµÐ´Ð¸\nÐºÐ¾Ð½ÑÑÐ¾Ð»Ñ",
            "movement": "ð¹ Movement (15Ð¼)\nÐ²ÑÐ³Ð»ÑÐ½ÑÐ»âÐ¸Ð½ÑÐ¾âÐ¾ÑÐºÐ°Ñ\nÑÐµÐ¿Ð¸Ðº Ñ Ð´ÑÑÐ³Ð¾Ð³Ð¾ ÑÐ³Ð»Ð°",
        },
        "plan": (
            "ð ÐÐ»Ð°Ð½ 7 Ð´Ð½ÐµÐ¹ â BF6\n"
            "Ð1â2: aim 15Ð¼ + Ð¿Ð¾Ð·Ð¸ÑÐ¸Ð¸ 15Ð¼\n"
            "Ð3â4: ÑÑÐ¾Ð½Ñ/ÑÐ¿Ð°Ð²Ð½Ñ 20Ð¼ + Ð´ÑÑÐ»Ð¸ 10Ð¼\n"
            "Ð5â6: Ð¸Ð³ÑÐ° Ð¾Ñ Ð¸Ð½ÑÐ¾ 25Ð¼ + ÑÐ°Ð·Ð±Ð¾Ñ 5Ð¼\n"
            "Ð7: 45â60Ð¼ + ÑÐ°Ð·Ð±Ð¾Ñ 2 ÑÐ¼ÐµÑÑÐµÐ¹\n"
        ),
        "vod": "ð¼ BF6: ÐºÐ°ÑÑÐ°/ÑÐµÐ¶Ð¸Ð¼, ÐºÐ»Ð°ÑÑ, Ð³Ð´Ðµ ÑÐ¼ÐµÑ/Ð¿Ð¾ÑÐµÐ¼Ñ, ÑÑÐ¾ ÑÐ¾ÑÐµÐ» ÑÐ´ÐµÐ»Ð°ÑÑ.",
    },
}


# =========================
# Persona + format
# =========================
SYSTEM_PROMPT = (
    "Ð¢Ñ ÑÐ°ÑÐ¸Ð·Ð¼Ð°ÑÐ¸ÑÐ½ÑÐ¹ FPS-ÐºÐ¾ÑÑ Ð¿Ð¾ Warzone/BO7/BF6. ÐÐ¸ÑÐµÑÑ Ð¿Ð¾-ÑÑÑÑÐºÐ¸.\n"
    "Ð¢Ð¾Ð½: ÑÐ²ÐµÑÐµÐ½Ð½ÑÐ¹, Ð±ÑÑÑÑÑÐ¹, Ñ ÑÐ¼Ð¾ÑÐ¾Ð¼ Ð¸ Ð»ÑÐ³ÐºÐ¸Ð¼Ð¸ Ð¿Ð¾Ð´ÐºÐ¾Ð»Ð°Ð¼Ð¸ (Ð±ÐµÐ· ÑÐ¾ÐºÑÐ¸ÑÐ½Ð¾ÑÑÐ¸).\n"
    "ÐÐ°Ð¿ÑÐµÑÐµÐ½Ð¾: ÑÐ¸ÑÑ/ÑÐ°ÐºÐ¸/Ð¾Ð±ÑÐ¾Ð´ Ð°Ð½ÑÐ¸ÑÐ¸ÑÐ°/ÑÐºÑÐ¿Ð»Ð¾Ð¹ÑÑ.\n\n"
    "Ð¤Ð¾ÑÐ¼Ð°Ñ Ð¾ÑÐ²ÐµÑÐ° ÐÐ¡ÐÐÐÐ:\n"
    "1) ð¯ ÐÐ¸Ð°Ð³Ð½Ð¾Ð· (1 Ð³Ð»Ð°Ð²Ð½Ð°Ñ Ð¾ÑÐ¸Ð±ÐºÐ°)\n"
    "2) â Ð§ÑÐ¾ Ð´ÐµÐ»Ð°ÑÑ (2 Ð´ÐµÐ¹ÑÑÐ²Ð¸Ñ Ð¿ÑÑÐ¼Ð¾ ÑÐµÐ¹ÑÐ°Ñ)\n"
    "3) ð§ª ÐÑÐ¸Ð»Ð» (5â10 Ð¼Ð¸Ð½ÑÑ)\n"
    "4) ð ÐÐ°Ð½ÑÐ¸Ðº/Ð¼Ð¾ÑÐ¸Ð²Ð°ÑÐ¸Ñ (1 ÑÑÑÐ¾ÐºÐ°)\n"
    "ÐÑÐ»Ð¸ Ð´Ð°Ð½Ð½ÑÑ Ð¼Ð°Ð»Ð¾ â Ð·Ð°Ð´Ð°Ð¹ 1 Ð²Ð¾Ð¿ÑÐ¾Ñ Ð² ÐºÐ¾Ð½ÑÐµ.\n"
)
PERSONA_HINT = {
    "spicy": "Ð¡ÑÐ¸Ð»Ñ: Ð´ÐµÑÐ·ÐºÐ¾ Ð¸ ÑÐ¼ÐµÑÐ½Ð¾, Ð½Ð¾ Ð±ÐµÐ· Ð¾ÑÐºÐ¾ÑÐ±Ð»ÐµÐ½Ð¸Ð¹.",
    "chill": "Ð¡ÑÐ¸Ð»Ñ: ÑÐ¿Ð¾ÐºÐ¾Ð¹Ð½Ð¾ Ð¸ Ð´ÑÑÐ¶ÐµÐ»ÑÐ±Ð½Ð¾, Ð¼ÑÐ³ÐºÐ¸Ð¹ ÑÐ¼Ð¾Ñ.",
    "pro": "Ð¡ÑÐ¸Ð»Ñ: ÑÑÑÐ¾Ð³Ð¾ Ð¿Ð¾ Ð´ÐµÐ»Ñ, Ð¼Ð¸Ð½Ð¸Ð¼ÑÐ¼ ÑÑÑÐ¾Ðº.",
}
VERBOSITY_HINT = {
    "short": "ÐÐ»Ð¸Ð½Ð°: ÐºÐ¾ÑÐ¾ÑÐºÐ¾ (Ð´Ð¾ ~10 ÑÑÑÐ¾Ðº).",
    "normal": "ÐÐ»Ð¸Ð½Ð°: Ð¾Ð±ÑÑÐ½Ð¾ (10â18 ÑÑÑÐ¾Ðº).",
    "talkative": "ÐÐ»Ð¸Ð½Ð°: Ð¿Ð¾Ð´ÑÐ¾Ð±Ð½ÐµÐµ (Ð´Ð¾ ~30 ÑÑÑÐ¾Ðº), +1â2 Ð´Ð¾Ð¿. ÑÐ¾Ð²ÐµÑÐ°.",
}
THINKING_LINES = [
    "ð§  ÐÑÐ¼Ð°Ñâ¦ ÑÐµÐ¹ÑÐ°Ñ Ð±ÑÐ´ÐµÑ Ð¶Ð°ÑÐ° ð",
    "â Ð¡ÐµÐºÑÐ½Ð´Ñâ¦ ÑÐ°ÑÐºÐ»Ð°Ð´ÑÐ²Ð°Ñ Ð¿Ð¾ Ð¿Ð¾Ð»Ð¾ÑÐºÐ°Ð¼ ð§©",
    "ð® ÐÐºÐµÐ¹, ÐºÐ¾ÑÑ Ð½Ð° ÑÐ²ÑÐ·Ð¸. Ð¡ÐµÐ¹ÑÐ°Ñ ÑÐ°Ð·Ð½ÐµÑÑÐ¼ ð",
    "ð ÐÐ½Ð°Ð»Ð¸Ð·Ð¸ÑÑÑâ¦ Ð½Ðµ Ð¼Ð¾ÑÐ³Ð°Ð¹ ð",
]


# =========================
# Telegram API helpers
# =========================
def _sleep_backoff(i: int):
    time.sleep((0.6 * (i + 1)) + random.random() * 0.25)

def tg_request(method: str, *, params=None, payload=None, is_post=False, retries=TG_RETRIES):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last = None
    for i in range(retries):
        try:
            if is_post:
                r = SESSION.post(url, json=payload, timeout=HTTP_TIMEOUT)
            else:
                r = SESSION.get(url, params=params, timeout=HTTP_TIMEOUT)

            try:
                data = r.json()
            except Exception:
                raise RuntimeError(f"Telegram non-JSON (HTTP {r.status_code}): {r.text[:200]}")

            if r.status_code == 200 and data.get("ok"):
                return data

            last = RuntimeError(data.get("description", f"Telegram HTTP {r.status_code}"))

        except Exception as e:
            last = e
        _sleep_backoff(i)

    raise last

def send_message(chat_id: int, text: str, reply_markup=None):
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
    last_msg_id = None
    for ch in chunks:
        res = tg_request("sendMessage", payload={"chat_id": chat_id, "text": ch, "reply_markup": reply_markup}, is_post=True)
        last_msg_id = res.get("result", {}).get("message_id")
    return last_msg_id

def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None):
    tg_request("editMessageText", payload={"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup}, is_post=True)

def answer_callback(callback_id: str):
    try:
        tg_request("answerCallbackQuery", payload={"callback_query_id": callback_id}, is_post=True, retries=2)
    except Exception:
        pass

def send_chat_action(chat_id: int, action: str = "typing"):
    try:
        tg_request("sendChatAction", payload={"chat_id": chat_id, "action": action}, is_post=True, retries=2)
    except Exception:
        pass

def delete_webhook_on_start():
    try:
        tg_request("deleteWebhook", payload={"drop_pending_updates": True}, is_post=True, retries=3)
        log.info("Webhook deleted (drop_pending_updates=true)")
    except Exception as e:
        log.warning("Could not delete webhook: %r", e)


# =========================
# Animation helpers (safe)
# =========================
def typing_loop(chat_id: int, stop_event: threading.Event, interval: float = 4.0):
    while not stop_event.is_set():
        send_chat_action(chat_id, "typing")
        stop_event.wait(interval)

def pulse_edit_loop(chat_id: int, message_id: int, stop_event: threading.Event, base: str = "â ÐÑÐ¼Ð°Ñ"):
    dots = 0
    last_edit = 0.0
    while not stop_event.is_set():
        now = time.time()
        if now - last_edit >= PULSE_MIN_SECONDS:
            dots = (dots + 1) % 4
            try:
                edit_message(chat_id, message_id, base + ("." * dots), reply_markup=None)
            except Exception:
                pass
            last_edit = now
        stop_event.wait(0.2)


# =========================
# Profile / UI
# =========================
def ensure_profile(chat_id: int) -> dict:
    default_coach = bool(OPENAI_API_KEY)
    p = USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "platform": "",
        "style": "",
        "goal": "",
        "coach": default_coach,
        "persona": "spicy",
        "verbosity": "normal",
        "ui": UI_DEFAULT,
    })
    if "coach" not in p:
        p["coach"] = default_coach
    return p

def maybe_kb(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    return kb_main(chat_id)

def update_memory(chat_id: int, role: str, content: str):
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS * 2:]

def parse_profile_line(text: str):
    t = text.lower()
    platform = ""
    if "xbox" in t:
        platform = "Xbox"
    elif "ps" in t or "playstation" in t:
        platform = "PlayStation"
    elif "kbm" in t or "Ð¼ÑÑ" in t or "ÐºÐ»Ð°Ð²" in t:
        platform = "KBM"

    style = ""
    if "Ð°Ð³ÑÐ¾" in t or "aggressive" in t:
        style = "Aggressive"
    elif "ÑÐ¿Ð¾ÐºÐ¾Ð¹" in t or "calm" in t or "Ð´ÐµÑ" in t:
        style = "Calm"

    goal = ""
    if "aim" in t or "Ð°Ð¸Ð¼" in t:
        goal = "Aim"
    elif "recoil" in t or "Ð¾ÑÐ´Ð°Ñ" in t:
        goal = "Recoil"
    elif "rank" in t or "ÑÐ°Ð½Ð³" in t:
        goal = "Rank"

    return platform, style, goal


# =========================
# Keyboards (Telegram colors cannot be set)
# =========================
def kb_main(chat_id: int):
    p = ensure_profile(chat_id)
    coach_on = "ð§  ON" if p.get("coach", True) else "ð§  OFF"
    ui = p.get("ui", "show")
    ui_btn = "ð¶ Hide UI" if ui == "show" else "ð¶ Show UI"
    return {
        "inline_keyboard": [
            [{"text": "ð Warzone", "callback_data": "game:warzone"},
             {"text": "ð BF6", "callback_data": "game:bf6"},
             {"text": "ð BO7", "callback_data": "game:bo7"}],
            [{"text": "âï¸ Settings", "callback_data": "action:settings"},
             {"text": "ðª Drills", "callback_data": "action:drills"}],
            [{"text": "ð Plan", "callback_data": "action:plan"},
             {"text": "ð¼ VOD", "callback_data": "action:vod"}],
            [{"text": "ð¤ Profile", "callback_data": "action:profile"},
             {"text": coach_on, "callback_data": "action:coach"}],
            [{"text": "ð Persona", "callback_data": "action:persona"},
             {"text": "ð£ Talk", "callback_data": "action:talk"}],
            [{"text": ui_btn, "callback_data": "action:ui"}],
            [{"text": "ð§¹ Reset", "callback_data": "action:reset"}],
        ]
    }

def kb_drills(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    return {
        "inline_keyboard": [
            [{"text": "ð¯ Aim", "callback_data": "drill:aim"},
             {"text": "ð« Recoil", "callback_data": "drill:recoil"},
             {"text": "ð¹ Movement", "callback_data": "drill:movement"}],
            [{"text": "â¬ï¸ Menu", "callback_data": "action:menu"}],
        ]
    }


# =========================
# Text blocks
# =========================
def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "ð FPS Coach Bot\n"
        f"ÐÐ³ÑÐ°: {GAME_KB[p['game']]['name']}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'} | Persona: {p.get('persona')} | Talk: {p.get('verbosity')} | UI: {p.get('ui')}\n\n"
        "ÐÐ¼Ð¸ ÐºÐ½Ð¾Ð¿ÐºÐ¸ ð"
    )

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "ð¤ ÐÑÐ¾ÑÐ¸Ð»Ñ\n"
        f"ÐÐ³ÑÐ°: {GAME_KB[p['game']]['name']}\n"
        f"ÐÐ»Ð°ÑÑÐ¾ÑÐ¼Ð°: {p.get('platform') or 'â'}\n"
        f"Ð¡ÑÐ¸Ð»Ñ: {p.get('style') or 'â'}\n"
        f"Ð¦ÐµÐ»Ñ: {p.get('goal') or 'â'}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n"
        f"Persona: {p.get('persona')}\n"
        f"Talk: {p.get('verbosity')}\n"
        f"UI: {p.get('ui')}\n\n"
        "ÐÐ¾Ð¼Ð°Ð½Ð´Ñ:\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/ui show|hide\n"
        "/ai_test\n"
    )

def status_text() -> str:
    ok_key = "â" if bool(OPENAI_API_KEY) else "â"
    ok_tg = "â" if bool(TELEGRAM_BOT_TOKEN) else "â"
    return (
        "ð§¾ Status\n"
        f"TELEGRAM_BOT_TOKEN: {ok_tg}\n"
        f"OPENAI_API_KEY: {ok_key}\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"STATE_PATH: {STATE_PATH}\n\n"
        "ÐÑÐ»Ð¸ Ð»Ð¾Ð²Ð¸ÑÑ Conflict 409 â Ð·Ð½Ð°ÑÐ¸Ñ Instances>1 Ð¸Ð»Ð¸ Ð²ÐºÐ»ÑÑÐµÐ½ webhook.\n"
    )

def set_game(chat_id: int, game_key: str) -> str:
    p = ensure_profile(chat_id)
    if game_key not in GAME_KB:
        return "ÐÐµ Ð·Ð½Ð°Ñ ÑÐ°ÐºÑÑ Ð¸Ð³ÑÑ."
    p["game"] = game_key
    return f"â ÐÐ³ÑÐ°: {GAME_KB[game_key]['name']}"


# =========================
# OpenAI (compat)
# =========================
def _openai_create(messages, max_tokens: int):
    try:
        return openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
    except TypeError:
        return openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=max_tokens,
        )

def openai_reply_safe(chat_id: int, user_text: str) -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "â ï¸ AI Ð²ÑÐºÐ»ÑÑÐµÐ½: Ð½ÐµÑ OPENAI_API_KEY. ÐÐ¾Ð±Ð°Ð²Ñ Ð² Render â Environment Variables â Redeploy."

    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    coach_frame = (
        "ÐÐ¸ÑÐ¸ ÐºÐ¾Ð½ÐºÑÐµÑÐ½Ð¾ Ð¸ Ð¿Ð¾Ð»ÐµÐ·Ð½Ð¾. ÐÑÐ»Ð¸ Ð¸Ð½ÑÐ¾ÑÐ¼Ð°ÑÐ¸Ð¸ Ð¼Ð°Ð»Ð¾ â ÑÐ¿ÑÐ¾ÑÐ¸ 1 ÑÑÐ¾ÑÐ½ÐµÐ½Ð¸Ðµ.\n"
        "ÐÐµ Ð¿ÑÐ¸Ð´ÑÐ¼ÑÐ²Ð°Ð¹ Ð¿Ð°ÑÑÐ¸/Ð¼ÐµÑÑ. ÐÑÐ»Ð¸ Ð½Ðµ ÑÐ²ÐµÑÐµÐ½ â Ð¾Ð±ÑÐ¸Ðµ Ð¿ÑÐ¸Ð½ÑÐ¸Ð¿Ñ.\n"
        "Ð¤Ð¾ÐºÑÑ: Ð¿Ð¾Ð·Ð¸ÑÐ¸Ñ, ÑÐ°Ð¹Ð¼Ð¸Ð½Ð³, Ð¸Ð½ÑÐ¾, Ð´Ð¸ÑÑÐ¸Ð¿Ð»Ð¸Ð½Ð°, Ð¼Ð¸ÐºÑÐ¾Ð¼ÑÐ², Ð¾ÑÐ´Ð°ÑÐ°.\n"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": coach_frame},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
        {"role": "system", "content": f"Ð¢ÐµÐºÑÑÐ°Ñ Ð¸Ð³ÑÐ°: {kb['name']}. {kb.get('pillars','')}"},
        {"role": "system", "content": f"ÐÑÐ¾ÑÐ¸Ð»Ñ: {json.dumps(p, ensure_ascii=False)}"},
    ]
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    max_out = 650 if verbosity == "talkative" else 520

    for attempt in range(2):
        try:
            resp = _openai_create(messages, max_out)
            out = (resp.choices[0].message.content or "").strip()
            return out or "ÐÐµ Ð¿Ð¾Ð»ÑÑÐ¸Ð» Ð¾ÑÐ²ÐµÑ. ÐÐ°Ð¿Ð¸ÑÐ¸ ÐµÑÑ ÑÐ°Ð· ð"

        except APIConnectionError:
            if attempt == 0:
                time.sleep(0.9)
                continue
            return "â ï¸ AI: Ð¿ÑÐ¾Ð±Ð»ÐµÐ¼Ð° ÑÐ¾ÐµÐ´Ð¸Ð½ÐµÐ½Ð¸Ñ. ÐÐ¾Ð¿ÑÐ¾Ð±ÑÐ¹ ÐµÑÑ ÑÐ°Ð· ÑÐµÑÐµÐ· Ð¼Ð¸Ð½ÑÑÑ."
        except AuthenticationError:
            return "â AI: Ð½ÐµÐ²ÐµÑÐ½ÑÐ¹ OPENAI_API_KEY. ÐÑÐ¾Ð²ÐµÑÑ Render â Env â Redeploy."
        except RateLimitError:
            return "â³ AI: Ð»Ð¸Ð¼Ð¸Ñ/Ð¿ÐµÑÐµÐ³ÑÑÐ·. ÐÐ¾Ð´Ð¾Ð¶Ð´Ð¸ 20â60 ÑÐµÐº Ð¸ Ð¿Ð¾Ð¿ÑÐ¾Ð±ÑÐ¹ ÑÐ½Ð¾Ð²Ð°."
        except BadRequestError:
            return f"â AI: bad request. ÐÐ¾Ð´ÐµÐ»Ñ: {OPENAI_MODEL}."
        except APIError:
            return "â ï¸ AI: Ð²ÑÐµÐ¼ÐµÐ½Ð½Ð°Ñ Ð¾ÑÐ¸Ð±ÐºÐ° ÑÐµÑÐ²Ð¸ÑÐ°. ÐÐ¾Ð¿ÑÐ¾Ð±ÑÐ¹ ÐµÑÑ ÑÐ°Ð· ÑÐµÑÐµÐ· Ð¼Ð¸Ð½ÑÑÑ."
        except Exception:
            log.exception("OpenAI unknown error")
            return "â ï¸ AI: Ð½ÐµÐ¸Ð·Ð²ÐµÑÑÐ½Ð°Ñ Ð¾ÑÐ¸Ð±ÐºÐ°. ÐÐ°Ð¿Ð¸ÑÐ¸ /status."

def ai_test() -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "â /ai_test: Ð½ÐµÑ OPENAI_API_KEY."
    try:
        r = _openai_create([{"role": "user", "content": "ÐÑÐ²ÐµÑÑ Ð¾Ð´Ð½Ð¸Ð¼ ÑÐ»Ð¾Ð²Ð¾Ð¼: OK"}], 10)
        out = (r.choices[0].message.content or "").strip()
        return f"â /ai_test: {out or 'OK'} (model={OPENAI_MODEL})"
    except AuthenticationError:
        return "â /ai_test: Ð½ÐµÐ²ÐµÑÐ½ÑÐ¹ ÐºÐ»ÑÑ."
    except APIConnectionError:
        return "â ï¸ /ai_test: Ð¿ÑÐ¾Ð±Ð»ÐµÐ¼Ð° ÑÐµÑÐ¸/Render."
    except Exception as e:
        return f"â ï¸ /ai_test: {type(e).__name__}"


# =========================
# Throttle
# =========================
def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False


# =========================
# Handlers
# =========================
def handle_message(chat_id: int, text: str):
    if throttle(chat_id):
        return

    p = ensure_profile(chat_id)
    low = text.lower().strip()

    if text.startswith("/start") or text.startswith("/menu"):
        send_message(chat_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))
        save_state()
        return

    if text.startswith("/status"):
        send_message(chat_id, status_text(), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/profile"):
        send_message(chat_id, profile_text(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/ai_test"):
        send_message(chat_id, ai_test(), reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/reset"):
        USER_PROFILE.pop(chat_id, None)
        USER_MEMORY.pop(chat_id, None)
        ensure_profile(chat_id)
        save_state()
        send_message(chat_id, "ð§¹ Ð¡Ð±ÑÐ¾ÑÐ¸Ð» Ð¿ÑÐ¾ÑÐ¸Ð»Ñ Ð¸ Ð¿Ð°Ð¼ÑÑÑ.", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/persona"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("spicy", "chill", "pro"):
            p["persona"] = parts[1].lower()
            save_state()
            send_message(chat_id, f"â Persona = {p['persona']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "ÐÑÐ¿Ð¾Ð»ÑÐ·ÑÐ¹: /persona spicy | chill | pro", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/talk"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("short", "normal", "talkative"):
            p["verbosity"] = parts[1].lower()
            save_state()
            send_message(chat_id, f"â Talk = {p['verbosity']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "ÐÑÐ¿Ð¾Ð»ÑÐ·ÑÐ¹: /talk short | normal | talkative", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/ui"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("show", "hide"):
            p["ui"] = parts[1].lower()
            save_state()
            send_message(chat_id, f"â UI = {p['ui']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "ÐÑÐ¿Ð¾Ð»ÑÐ·ÑÐ¹: /ui show | /ui hide", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/game"):
        parts = text.split()
        if len(parts) >= 2:
            msg = set_game(chat_id, parts[1].lower())
            save_state()
            send_message(chat_id, msg, reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "ÐÑÐ¿Ð¾Ð»ÑÐ·ÑÐ¹: /game warzone | bf6 | bo7", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/settings"):
        send_message(chat_id, GAME_KB[p["game"]]["settings"], reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/plan"):
        send_message(chat_id, GAME_KB[p["game"]]["plan"], reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/vod"):
        send_message(chat_id, GAME_KB[p["game"]]["vod"], reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/drills"):
        send_message(chat_id, "ÐÑÐ±ÐµÑÐ¸ Ð´ÑÐ¸Ð»Ð»:", reply_markup=kb_drills(chat_id))
        return

    if low in ("Ð¿ÑÐ¸Ð²ÐµÑ", "ÑÐ°Ð¹", "yo", "Ð·Ð´Ð°ÑÐ¾Ð²Ð°", "hello", "ÐºÑ"):
        send_message(chat_id, "ÐÐ¾ ð ÐÑÐ±Ð¸ÑÐ°Ð¹ Ð¸Ð³ÑÑ Ð¸ Ð¿Ð¾Ð³Ð½Ð°Ð»Ð¸. Ð¯ ÑÑÑ Ð½Ðµ Ð´Ð»Ñ Ð»Ð°ÑÐºÐ¸ â Ñ Ð´Ð»Ñ Ð¿Ð¾Ð±ÐµÐ´.", reply_markup=maybe_kb(chat_id))
        return

    platform, style, goal = parse_profile_line(text)
    if platform or style or goal:
        if platform:
            p["platform"] = platform
        if style:
            p["style"] = style
        if goal:
            p["goal"] = goal
        save_state()
        send_message(chat_id, "â ÐÑÐ¾ÑÐ¸Ð»Ñ Ð¾Ð±Ð½Ð¾Ð²Ð»ÑÐ½.\n\n" + profile_text(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if not p.get("coach", True):
        send_message(chat_id, "ð§  Coach OFF. ÐÐºÐ»ÑÑÐ¸ Ð² Ð¼ÐµÐ½Ñ (ÐºÐ½Ð¾Ð¿ÐºÐ° ð§  ON/OFF).", reply_markup=maybe_kb(chat_id))
        return

    update_memory(chat_id, "user", text)
    tmp_id = send_message(chat_id, random.choice(THINKING_LINES), reply_markup=None)

    stop = threading.Event()
    threading.Thread(target=typing_loop, args=(chat_id, stop), daemon=True).start()
    if tmp_id:
        threading.Thread(target=pulse_edit_loop, args=(chat_id, tmp_id, stop, "â ÐÑÐ¼Ð°Ñ"), daemon=True).start()

    try:
        reply = openai_reply_safe(chat_id, text)
    finally:
        stop.set()

    update_memory(chat_id, "assistant", reply)
    save_state()

    if tmp_id:
        try:
            edit_message(chat_id, tmp_id, reply, reply_markup=maybe_kb(chat_id))
        except Exception:
            send_message(chat_id, reply, reply_markup=maybe_kb(chat_id))
    else:
        send_message(chat_id, reply, reply_markup=maybe_kb(chat_id))


def handle_callback(cb: dict):
    cb_id = cb["id"]
    msg = cb.get("message", {})
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data", "")

    if not chat_id or not message_id:
        answer_callback(cb_id)
        return

    try:
        p = ensure_profile(chat_id)

        if data == "action:menu":
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data.startswith("game:"):
            game = data.split(":", 1)[1]
            set_game(chat_id, game)
            save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:settings":
            edit_message(chat_id, message_id, GAME_KB[p["game"]]["settings"], reply_markup=maybe_kb(chat_id))

        elif data == "action:plan":
            edit_message(chat_id, message_id, GAME_KB[p["game"]]["plan"], reply_markup=maybe_kb(chat_id))

        elif data == "action:vod":
            edit_message(chat_id, message_id, GAME_KB[p["game"]]["vod"], reply_markup=maybe_kb(chat_id))

        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:coach":
            p["coach"] = not p.get("coach", True)
            save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:persona":
            cur = p.get("persona", "spicy")
            p["persona"] = {"spicy": "chill", "chill": "pro", "pro": "spicy"}.get(cur, "spicy")
            save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:talk":
            cur = p.get("verbosity", "normal")
            p["verbosity"] = {"short": "normal", "normal": "talkative", "talkative": "short"}.get(cur, "normal")
            save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:ui":
            p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
            save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

        elif data == "action:reset":
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            ensure_profile(chat_id)
            save_state()
            edit_message(chat_id, message_id, "ð§¹ Ð¡Ð±ÑÐ¾ÑÐ¸Ð» Ð¿ÑÐ¾ÑÐ¸Ð»Ñ Ð¸ Ð¿Ð°Ð¼ÑÑÑ.", reply_markup=maybe_kb(chat_id))

        elif data == "action:drills":
            edit_message(chat_id, message_id, "ÐÑÐ±ÐµÑÐ¸ Ð´ÑÐ¸Ð»Ð»:", reply_markup=kb_drills(chat_id))

        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            drills = GAME_KB[p["game"]]["drills"]
            edit_message(chat_id, message_id, drills.get(kind, "ÐÐ¾ÑÑÑÐ¿Ð½Ð¾: aim/recoil/movement"), reply_markup=kb_drills(chat_id))

        else:
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))

    finally:
        answer_callback(cb_id)


# =========================
# Polling loop (hardened)
# =========================
POLLING_STARTED = False

def run_telegram_bot():
    global POLLING_STARTED
    if POLLING_STARTED:
        log.warning("Polling already started. Skip.")
        return
    POLLING_STARTED = True

    delete_webhook_on_start()

    log.info("Telegram bot started (long polling)")
    offset = 0

    while True:
        try:
            data = tg_request("getUpdates", params={"offset": offset, "timeout": TG_LONGPOLL_TIMEOUT})

            for upd in data.get("result", []):
                offset = upd.get("update_id", offset) + 1

                if "callback_query" in upd:
                    handle_callback(upd["callback_query"])
                    continue

                msg = upd.get("message") or upd.get("edited_message") or {}
                text = (msg.get("text") or "").strip()
                chat_id = (msg.get("chat") or {}).get("id")
                if not chat_id or not text:
                    continue

                try:
                    handle_message(chat_id, text)
                except Exception:
                    log.exception("Message handling error")
                    send_message(chat_id, "ÐÑÐ¸Ð±ÐºÐ° ð ÐÐ¾Ð¿ÑÐ¾Ð±ÑÐ¹ ÐµÑÑ ÑÐ°Ð·.", reply_markup=maybe_kb(chat_id))

        except RuntimeError as e:
            s = str(e)
            if "Conflict:" in s and "getUpdates" in s:
                sleep_s = random.randint(CONFLICT_BACKOFF_MIN, CONFLICT_BACKOFF_MAX)
                log.warning("Telegram conflict (Instances>1 or webhook). Backoff %ss: %s", sleep_s, s)
                time.sleep(sleep_s)
                continue
            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2)

        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)


# =========================
# Health endpoint (Render)
# =========================
class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _ok(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

    def do_HEAD(self):
        if self.path in ("/", "/healthz"):
            self._ok()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/healthz"):
            self._ok()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()


def run_http_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    log.info("HTTP server listening on :%s", port)
    server.serve_forever()


if __name__ == "__main__":
    stop_autosave = threading.Event()
    threading.Thread(target=autosave_loop, args=(stop_autosave, 60), daemon=True).start()

    threading.Thread(target=run_telegram_bot, daemon=True).start()
    run_http_server()
