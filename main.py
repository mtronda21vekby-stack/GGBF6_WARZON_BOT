# -*- coding: utf-8 -*-
"""
FPS Coach Bot — clean+smart v2 (Render + long polling + memory + dialog)

+ Zombies: 2 карты (выбор карты -> выбор раздела) 🧟
+ Zombies: поиск по тексту (если ты в меню Zombies — любое сообщение ищет по разделам)
+ Всё меню на русском (кроме коротких названий игр WZ/BF6/BO7 — это ок)

ENV:
TELEGRAM_BOT_TOKEN=...
OPENAI_API_KEY=... (опционально)
OPENAI_MODEL=gpt-4o-mini (или другой)
PORT=10000 (Render сам задаёт)
"""

import os
import re
import time
import json
import random
import threading
import logging
import traceback
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Optional

import requests

# ✅ Zombies router (2 карты + поиск)
from zombies import router as zombies_router

# OpenAI optional
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_clean_smart_v2")


# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

DATA_DIR = os.getenv("DATA_DIR", "/tmp").strip()
STATE_PATH = os.path.join(DATA_DIR, "fps_coach_state.json")
OFFSET_PATH = os.path.join(DATA_DIR, "tg_offset.txt")

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
TG_LONGPOLL_TIMEOUT = int(os.getenv("TG_LONGPOLL_TIMEOUT", "50"))
TG_RETRIES = int(os.getenv("TG_RETRIES", "6"))

CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.25"))
MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))

MAX_TEXT_LEN = 3900
os.makedirs(DATA_DIR, exist_ok=True)


def startup_diagnostics():
    try:
        log.info("=== STARTUP DIAGNOSTICS ===")
        log.info("python: %s", sys.version.replace("\n", " "))
        log.info("cwd: %s", os.getcwd())
        log.info("DATA_DIR=%s", DATA_DIR)
        log.info("STATE_PATH=%s", STATE_PATH)
        log.info("OFFSET_PATH=%s", OFFSET_PATH)
        log.info("OPENAI_BASE_URL=%s", OPENAI_BASE_URL)
        log.info("OPENAI_MODEL=%s", OPENAI_MODEL)
        log.info("TELEGRAM_BOT_TOKEN present: %s", bool(TELEGRAM_BOT_TOKEN))
        log.info("OPENAI_API_KEY present: %s", bool(OPENAI_API_KEY))
        log.info("openai pkg available: %s", bool(OpenAI))
        log.info("===========================")
    except Exception:
        pass


# =========================
# OpenAI client (optional)
# =========================
openai_client = None
if OpenAI and OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=30, max_retries=0)
        log.info("OpenAI client: ON")
    except Exception as e:
        log.warning("OpenAI init failed: %r", e)
        openai_client = None
else:
    log.warning("OpenAI: OFF (missing key or package). Bot still works.")


# =========================
# Requests session (Telegram)
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-bot/clean-smart-v2"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=40, pool_maxsize=40))


# =========================
# Knowledge (simple built-in)
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "settings": (
            "🌑 Warzone — быстрый сетап (контроллер)\n"
            "• Sens: 7/7 (перелетаешь → 6/6)\n"
            "• ADS: 0.90 low / 0.85 high\n"
            "• Aim Assist: Dynamic (если не заходит → Standard)\n"
            "• Deadzone min: 0.05 (дрифт → 0.07–0.10)\n"
            "• FOV: 105–110 | ADS FOV Affected: ON | Weapon FOV: Wide\n"
            "• Camera Movement: Least\n"
        ),
        "drills": {
            "aim": "🎯 Aim (7 минут)\n• 2м warm-up\n• 3м трекинг\n• 2м микро-фиксы (центрирование на голову/плечи)",
            "recoil": "🔫 Recoil (7 минут)\n• 3м 20–30м короткие очереди\n• 2м first-shot\n• 2м контроль на средней",
            "movement": "🕹 Move (7 минут)\n• угол→пик→откат\n• слайд/джамп пики\n• после хита — смена угла",
        },
        "vod": "📼 VOD: режим/карта → что видел → что решил → где ошибся → что сделаешь иначе.",
    },
    "bf6": {
        "name": "Battlefield 6 (BF6)",
        "settings": (
            "🌑 BF6 — база\n"
            "• Sens средняя, ADS ниже\n"
            "• Deadzone минимум без дрифта\n"
            "• FOV высокий (комфорт)\n"
            "• После контакта — смена позиции\n"
        ),
        "drills": {
            "aim": "🎯 Aim (7 минут)\n• префайр углов\n• трекинг\n• файт→репозиция",
            "recoil": "🔫 Recoil (7 минут)\n• короткие очереди\n• первая пуля\n• контроль на дистанции",
            "movement": "🕹 Move (7 минут)\n• выглянул→инфо→откат\n• репик с другого угла",
        },
        "vod": "📼 BF6: точка/спавны → где стоял → кто первый увидел → почему не вышел/вышел.",
    },
    "bo7": {
        "name": "Call of Duty: Black Ops 7 (BO7)",
        "settings": (
            "🌑 BO7 — базовый сетап (контроллер)\n"
            "• Sens: 6–8\n"
            "• ADS: 0.80–0.95\n"
            "• Deadzone min: 0.03–0.07\n"
            "• FOV: 100–115\n"
        ),
        "drills": {
            "aim": "🎯 Aim (7 минут)\n• префайр\n• трекинг\n• микро-подводки",
            "recoil": "🔫 Recoil (7 минут)\n• короткие очереди\n• first-shot\n• контроль на средней",
            "movement": "🕹 Move (7 минут)\n• репики\n• стрейф-шоты\n• смена угла",
        },
        "vod": "📼 BO7: режим/карта → смерть → инфо (радар/звук) → решение → ошибка.",
    },
}
GAMES = tuple(GAME_KB.keys())


# =========================
# Style / prompts
# =========================
PERSONA_HINT = {
    "spicy": "Стиль: дерзко и смешно, но без унижений. Сленг уместен.",
    "chill": "Стиль: спокойный, дружелюбный, мягко и по делу.",
    "pro": "Стиль: строго по делу, минимум шуток, чёткая структура.",
}
VERBOSITY_HINT = {
    "short": "Длина: коротко, без воды.",
    "normal": "Длина: нормально, плотная польза.",
    "talkative": "Длина: подробнее, но без занудства.",
}

SYSTEM_COACH = (
    "Ты FPS-коуч. Пишешь по-русски. Без токсичности.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
    "Отвечай живо, но практично.\n"
    "Если данных мало — задай 1 короткий уточняющий вопрос.\n\n"
    "Если режим COACH: дай 4 блока:\n"
    "🎯 Диагноз\n"
    "✅ Что делать (ровно 2 строки: 'Сейчас — ...' и 'Дальше — ...')\n"
    "🧪 Дрилл\n"
    "😈 Панчик/мотивация\n"
)

SYSTEM_CHAT = (
    "Ты тиммейт/коуч в чате. Пишешь по-русски.\n"
    "Твоя задача — общаться как живой: задавай вопросы, уточняй, подстраивайся.\n"
    "Не выдавай шаблон. Можно коротко. Можно пошутить.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
)

THINKING_LINES = ["🧠 Думаю…", "⌛ Секунду…", "🎮 Окей, ща разложу…", "🌑 Анализирую…"]


# =========================
# Detectors
# =========================
_SMALLTALK_RX = re.compile(r"^\s*(привет|здаров|здравствуйте|йо|ку|qq|hello|hi|хай)\s*[!.\-–—]*\s*$", re.I)
_TILT_RX = re.compile(r"(я\s+говно|я\s+дно|не\s+прёт|не\s+идёт|вечно\s+не\s+везёт|тильт|бесит|ненавижу|заеб|сука|бля)", re.I)

def is_smalltalk(text: str) -> bool:
    return bool(_SMALLTALK_RX.match(text or ""))

def is_tilt(text: str) -> bool:
    return bool(_TILT_RX.search(text or ""))

def is_cheat_request(text: str) -> bool:
    t = (text or "").lower()
    banned = ["чит", "cheat", "hack", "обход", "античит", "exploit", "эксплойт", "аимбот", "wallhack", "вх", "спуфер"]
    return any(w in t for w in banned)

def detect_game(text: str) -> Optional[str]:
    t = (text or "").lower()
    if any(x in t for x in ["bf6", "battlefield", "батлфилд", "конквест", "захват"]):
        return "bf6"
    if any(x in t for x in ["bo7", "black ops", "блэк опс", "hardpoint", "хардпоинт", "zombies", "зомби"]):
        return "bo7"
    if any(x in t for x in ["warzone", "wz", "варзон", "verdansk", "rebirth", "gulag", "бр"]):
        return "warzone"
    return None


# =========================
# Root-cause classifier
# =========================
CAUSES = ("info", "timing", "position", "discipline", "mechanics")
CAUSE_LABEL = {
    "info": "Инфо (звук/радар/пинги)",
    "timing": "Тайминг (когда пикнул/вышел)",
    "position": "Позиция (угол/высота/линия обзора)",
    "discipline": "Дисциплина (жадность/ресурсы/ресет)",
    "mechanics": "Механика (аим/отдача/сенса)",
}

def classify_cause(text: str) -> str:
    t = (text or "").lower()
    score = {c: 0 for c in CAUSES}
    for k in ["не слыш", "звук", "шаг", "радар", "пинг", "инфо", "увидел поздно"]:
        if k in t: score["info"] += 2
    for k in ["тайм", "поздно", "рано", "репик", "пикнул", "вышел", "задержал"]:
        if k in t: score["timing"] += 2
    for k in ["пози", "угол", "высот", "открыт", "прострел", "линия", "укрыт"]:
        if k in t: score["position"] += 2
    for k in ["жадн", "ресурс", "плейт", "пласти", "хил", "перезар", "вдвоём", "в соло", "погнал"]:
        if k in t: score["discipline"] += 2
    for k in ["аим", "отдач", "сенс", "фов", "перел", "дрейф", "не попал", "мимо"]:
        if k in t: score["mechanics"] += 2

    best = max(score.items(), key=lambda kv: kv[1])[0]
    if score[best] == 0:
        return "position"
    return best


# =========================
# State
# =========================
USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
USER_STATS: Dict[int, Dict[str, int]] = {}
USER_DAILY: Dict[int, Dict[str, Any]] = {}
LAST_MSG_TS: Dict[int, float] = {}

STATE_GUARD = threading.Lock()
CHAT_LOCKS: Dict[int, threading.Lock] = {}
LOCKS_GUARD = threading.Lock()

def _get_lock(chat_id: int) -> threading.Lock:
    with LOCKS_GUARD:
        if chat_id not in CHAT_LOCKS:
            CHAT_LOCKS[chat_id] = threading.Lock()
        return CHAT_LOCKS[chat_id]

def ensure_profile(chat_id: int) -> Dict[str, Any]:
    return USER_PROFILE.setdefault(chat_id, {
        "game": "auto",
        "persona": "spicy",
        "verbosity": "normal",
        "memory": "on",
        "ui": "show",
        "mode": "chat",
        "last_question": "",
        "last_answer": "",
        "page": "main",        # main | zombies
        "zmb_map": "ashes",     # выбранная карта зомби
    })

def load_state() -> None:
    global USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            USER_PROFILE = {int(k): v for k, v in (data.get("profiles") or {}).items()}
            USER_MEMORY = {int(k): v for k, v in (data.get("memory") or {}).items()}
            USER_STATS = {int(k): v for k, v in (data.get("stats") or {}).items()}
            USER_DAILY = {int(k): v for k, v in (data.get("daily") or {}).items()}
            log.info("State loaded: profiles=%d memory=%d stats=%d daily=%d",
                     len(USER_PROFILE), len(USER_MEMORY), len(USER_STATS), len(USER_DAILY))
    except Exception as e:
        log.warning("State load failed: %r (starting clean)", e)

def save_state() -> None:
    try:
        with STATE_GUARD:
            data = {
                "profiles": {str(k): v for k, v in USER_PROFILE.items()},
                "memory": {str(k): v for k, v in USER_MEMORY.items()},
                "stats": {str(k): v for k, v in USER_STATS.items()},
                "daily": {str(k): v for k, v in USER_DAILY.items()},
                "saved_at": int(time.time()),
            }
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, STATE_PATH)
    except Exception as e:
        log.warning("State save failed: %r", e)

def autosave_loop(stop: threading.Event, interval_s: int = 60) -> None:
    while not stop.is_set():
        stop.wait(interval_s)
        if stop.is_set():
            break
        save_state()

def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False

def update_memory(chat_id: int, role: str, content: str) -> None:
    p = ensure_profile(chat_id)
    if p.get("memory", "on") != "on":
        return
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    max_len = max(2, MEMORY_MAX_TURNS * 2)
    if len(mem) > max_len:
        USER_MEMORY[chat_id] = mem[-max_len:]

def clear_memory(chat_id: int) -> None:
    USER_MEMORY.pop(chat_id, None)
    p = ensure_profile(chat_id)
    p["last_answer"] = ""
    p["last_question"] = ""

def stat_inc(chat_id: int, cause: str) -> None:
    st = USER_STATS.setdefault(chat_id, {})
    st[cause] = int(st.get(cause, 0)) + 1


# =========================
# Daily challenge
# =========================
DAILY_POOL = [
    ("angles", "5 файтов подряд — не репикай тот же угол. После первого хита меняй позицию."),
    ("info", "3 файта подряд — сначала инфо (звук/радар), потом выход. Без ‘на авось’."),
    ("center", "10 минут — держи прицел на уровне головы/плеч. Без ‘в пол’."),
    ("reset", "Каждый файт — после контакта 1 раз: ‘плейты/перезар/ресет’ перед репиком."),
]

def _today_key() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

def ensure_daily(chat_id: int) -> Dict[str, Any]:
    d = USER_DAILY.setdefault(chat_id, {})
    if d.get("day") != _today_key() or not d.get("id"):
        cid, text = random.choice(DAILY_POOL)
        USER_DAILY[chat_id] = {"day": _today_key(), "id": cid, "text": text, "done": 0, "fail": 0}
    return USER_DAILY[chat_id]


# =========================
# Telegram API
# =========================
def _sleep_backoff(i: int) -> None:
    time.sleep((0.6 * (i + 1)) + random.random() * 0.3)

def tg_request(method: str, *, params=None, payload=None, is_post: bool = False, retries: int = TG_RETRIES) -> Dict[str, Any]:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing ENV: TELEGRAM_BOT_TOKEN")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last: Optional[Exception] = None

    for i in range(max(1, retries)):
        try:
            if is_post:
                r = SESSION.post(url, json=payload, timeout=HTTP_TIMEOUT)
            else:
                r = SESSION.get(url, params=params, timeout=HTTP_TIMEOUT)

            data = r.json()
            if r.status_code == 200 and data.get("ok"):
                return data

            desc = data.get("description", f"Telegram HTTP {r.status_code}")
            last = RuntimeError(desc)

            params_ = data.get("parameters") or {}
            retry_after = params_.get("retry_after")
            if isinstance(retry_after, int) and retry_after > 0:
                time.sleep(min(30, retry_after))
                continue

        except Exception as e:
            last = e

        _sleep_backoff(i)

    raise last or RuntimeError("Telegram request failed")

def tg_getme_check_forever():
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is missing (set it in Render Environment).")
        return
    while True:
        try:
            data = tg_request("getMe", retries=3)
            me = data.get("result") or {}
            log.info("Telegram getMe OK: @%s (id=%s)", me.get("username"), me.get("id"))
            return
        except Exception as e:
            log.error("Telegram getMe failed (will retry): %r", e)
            time.sleep(5)

def send_message(chat_id: int, text: str, reply_markup=None) -> Optional[int]:
    text = text or ""
    chunks = [text[i:i + MAX_TEXT_LEN] for i in range(0, len(text), MAX_TEXT_LEN)] or [""]
    last_msg_id = None
    for ch in chunks:
        payload = {"chat_id": chat_id, "text": ch}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        res = tg_request("sendMessage", payload=payload, is_post=True)
        last_msg_id = res.get("result", {}).get("message_id")
    return last_msg_id

def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    tg_request("editMessageText", payload=payload, is_post=True)

def answer_callback(callback_id: str) -> None:
    try:
        tg_request("answerCallbackQuery", payload={"callback_query_id": callback_id}, is_post=True, retries=2)
    except Exception:
        pass


# =========================
# UI / Menu (РУССКИЙ)
# =========================
def _badge(ok: bool) -> str:
    return "✅" if ok else "🚫"

def menu_main(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui") == "hide":
        return None

    game = p.get("game", "auto").upper()
    persona = p.get("persona", "spicy")
    talk = p.get("verbosity", "normal")
    mem_on = (p.get("memory", "on") == "on")
    mode = p.get("mode", "chat").upper()
    ai = "ON" if openai_client else "OFF"

    return {
        "inline_keyboard": [
            [
                {"text": f"🎮 Игра: {game}", "callback_data": "nav:game"},
                {"text": f"🎭 Стиль: {persona}", "callback_data": "nav:persona"},
            ],
            [
                {"text": f"🗣 Ответ: {talk}", "callback_data": "nav:talk"},
                {"text": f"{_badge(mem_on)} Память", "callback_data": "toggle:memory"},
            ],
            [
                {"text": f"🔁 Режим: {mode}", "callback_data": "toggle:mode"},
                {"text": f"🤖 ИИ: {ai}", "callback_data": "action:ai_status"},
            ],
            [
                {"text": "💪 Тренировка", "callback_data": "nav:training"},
                {"text": "📊 Профиль", "callback_data": "action:profile"},
                {"text": "⚙️ Настройки", "callback_data": "nav:settings"},
            ],
            [
                {"text": "🎯 Задание дня", "callback_data": "action:daily"},
                {"text": "📼 VOD-разбор", "callback_data": "action:vod"},
                {"text": "🧟 Zombies", "callback_data": "zmb:home"},
            ],
            [
                {"text": "🧽 Очистить память", "callback_data": "action:clear_memory"},
                {"text": "🧨 Сбросить всё", "callback_data": "action:reset_all"},
            ],
        ]
    }

def menu_game(chat_id: int):
    p = ensure_profile(chat_id)
    cur = p.get("game", "auto")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:game:{key}"}

    return {"inline_keyboard": [
        [b("auto", "АВТО"), b("warzone", "WZ"), b("bf6", "BF6"), b("bo7", "BO7")],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}]
    ]}

def menu_persona(chat_id: int):
    p = ensure_profile(chat_id)
    cur = p.get("persona", "spicy")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:persona:{key}"}

    return {"inline_keyboard": [
        [b("spicy", "Дерзко 😈"), b("chill", "Спокойно 🙂"), b("pro", "Профи 🧠")],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}]
    ]}

def menu_talk(chat_id: int):
    p = ensure_profile(chat_id)
    cur = p.get("verbosity", "normal")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:talk:{key}"}

    return {"inline_keyboard": [
        [b("short", "Коротко"), b("normal", "Норм"), b("talkative", "Подробно")],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}]
    ]}

def menu_training(chat_id: int):
    return {"inline_keyboard": [
        [{"text": "🎯 Аим", "callback_data": "action:drill:aim"},
         {"text": "🔫 Отдача", "callback_data": "action:drill:recoil"},
         {"text": "🕹 Мувмент", "callback_data": "action:drill:movement"}],
        [{"text": "🎯 Задание дня", "callback_data": "action:daily"},
         {"text": "📼 VOD-разбор", "callback_data": "action:vod"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def menu_settings(chat_id: int):
    p = ensure_profile(chat_id)
    ui = p.get("ui", "show")
    return {"inline_keyboard": [
        [{"text": f"{_badge(ui=='show')} Показ меню", "callback_data": "toggle:ui"},
         {"text": "🧾 Статус", "callback_data": "action:status"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def menu_daily(chat_id: int):
    return {"inline_keyboard": [
        [{"text": "✅ Сделал", "callback_data": "daily:done"},
         {"text": "❌ Не вышло", "callback_data": "daily:fail"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def header(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    ai = "ON" if openai_client else "OFF"
    return f"🌑 FPS Coach Bot v2 | 🎮 {p.get('game','auto').upper()} | 🔁 {p.get('mode','chat').upper()} | 🤖 AI {ai}"

def main_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    mode = p.get("mode", "chat")
    if mode == "chat":
        return (
            f"{header(chat_id)}\n\n"
            "Напиши как другу/тиммейту: что бесит, где умираешь, что хочешь улучшить.\n"
            "Я буду задавать вопросы и вести тебя к решению.\n\n"
            "Или жми меню 👇"
        )
    return (
        f"{header(chat_id)}\n\n"
        "COACH режим: опиши 1 сцену:\n"
        "• где был • кто первый увидел • на чём умер • что хотел сделать\n\n"
        "Или жми меню 👇"
    )

def help_text() -> str:
    return (
        "❓ Помощь\n"
        "Режимы:\n"
        "• CHAT — живой разговор/вопросы/разбор по шагам\n"
        "• COACH — структурный разбор (4 блока)\n\n"
        "Команды:\n"
        "/start /menu\n"
        "/profile\n"
        "/daily\n"
        "/zombies\n"
        "/reset\n"
    )

def status_text() -> str:
    return (
        "🧾 Статус\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"DATA_DIR: {DATA_DIR}\n"
        f"ИИ: {'ON' if openai_client else 'OFF'}\n"
        "Если Conflict 409 — у тебя два инстанса или где-то ещё включён getUpdates.\n"
    )

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    st = USER_STATS.get(chat_id, {})
    mem_len = len(USER_MEMORY.get(chat_id, []))
    daily = ensure_daily(chat_id)
    top = sorted(st.items(), key=lambda kv: kv[1], reverse=True)[:3]

    lines = [
        "📊 Профиль",
        f"Режим: {p.get('mode','chat').upper()}",
        f"Игра: {p.get('game','auto').upper()}",
        f"Стиль: {p.get('persona')}",
        f"Длина: {p.get('verbosity')}",
        f"Память: {p.get('memory','on').upper()} (сообщений: {mem_len})",
        "",
        "🧩 Карта проблем (топ):"
    ]
    if not top:
        lines.append("— пока пусто (нужны ситуации/смерти).")
    else:
        for c, n in top:
            lines.append(f"• {CAUSE_LABEL.get(c,c)}: {n}")

    lines += [
        "",
        "🎯 Задание дня:",
        f"• {daily.get('text')}",
        f"• сделано={daily.get('done',0)} / не вышло={daily.get('fail',0)}",
    ]
    return "\n".join(lines)


# =========================
# AI helpers
# =========================
def _openai_chat(messages: List[Dict[str, str]], max_tokens: int) -> str:
    if not openai_client:
        return ""
    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.9,
            presence_penalty=0.7,
            frequency_penalty=0.4,
            max_completion_tokens=max_tokens,
        )
    except TypeError:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.9,
            presence_penalty=0.7,
            frequency_penalty=0.4,
            max_tokens=max_tokens,
        )
    return (resp.choices[0].message.content or "").strip()

def enforce_4_blocks(text: str, fallback_cause: str) -> str:
    t = (text or "").replace("\r", "").strip()
    needed = ["🎯", "✅", "🧪", "😈"]
    if all(x in t for x in needed):
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        t = re.sub(r"(?im)^\s*🎯.*$", "🎯 Диагноз", t)
        t = re.sub(r"(?im)^\s*✅.*$", "✅ Что делать", t)
        t = re.sub(r"(?im)^\s*🧪.*$", "🧪 Дрилл", t)
        t = re.sub(r"(?im)^\s*😈.*$", "😈 Панчик/мотивация", t)
        return t

    return (
        "🎯 Диагноз\n"
        f"Похоже, главная причина — {CAUSE_LABEL.get(fallback_cause)}.\n\n"
        "✅ Что делать\n"
        "Сейчас — сыграй от инфо: звук/радар/пинг перед выходом.\n"
        "Дальше — после первого хита меняй угол (не репикай лоб в лоб).\n\n"
        "🧪 Дрилл\n"
        "7 минут: 3 файта → после каждого 1 фраза: «почему умер».\n\n"
        "😈 Панчик/мотивация\n"
        "Не ищем магию. Ищем привычку. 😈"
    )

def resolve_game(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    forced = p.get("game", "auto")
    if forced in GAMES:
        return forced
    d = detect_game(user_text)
    return d if d in GAMES else "warzone"

def build_messages(chat_id: int, user_text: str, mode: str, cause: str) -> List[Dict[str, str]]:
    p = ensure_profile(chat_id)
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")
    game = resolve_game(chat_id, user_text)

    sys_prompt = SYSTEM_CHAT if mode == "chat" else SYSTEM_COACH
    sys_prompt += f"\nТекущая игра: {GAME_KB[game]['name']}. Предполагаемая причина: {CAUSE_LABEL.get(cause)}."

    msgs: List[Dict[str, str]] = [
        {"role": "system", "content": sys_prompt},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
    ]

    if p.get("memory") == "on":
        msgs.extend(USER_MEMORY.get(chat_id, []))

    last_ans = (p.get("last_answer") or "")[:800]
    if last_ans:
        msgs.append({"role": "system", "content": "Не повторяй прошлый ответ, меняй формулировки.\nПрошлый ответ:\n" + last_ans})

    msgs.append({"role": "user", "content": user_text})
    return msgs

def ai_off_chat(chat_id: int, user_text: str) -> str:
    cause = classify_cause(user_text)
    st = CAUSE_LABEL.get(cause, cause)
    if is_tilt(user_text):
        return (
            "Слышу тильт 😈\n"
            "Давай без самоуничтожения. Быстро: что именно чаще всего ломает — звук/тайминг/аим/позиция?\n"
            f"По тексту похоже на: {st}."
        )
    if is_smalltalk(user_text):
        return "Йо 😄 Скажи: ты сейчас в WZ/BF6/BO7 и где чаще умираешь — ближка или средняя?"
    return (
        f"Ок, понял. Похоже, причина: {st}.\n"
        "Скажи одну сцену: где был, кто первый увидел, на чём умер — и я дам точнее."
    )

def coach_reply(chat_id: int, user_text: str) -> str:
    cause = classify_cause(user_text)
    stat_inc(chat_id, cause)

    if is_cheat_request(user_text):
        return (
            "🎯 Диагноз\n"
            "Читы = бан + ноль прогресса.\n\n"
            "✅ Что делать\n"
            "Сейчас — скажи, где сыпешься: инфо/тайминг/позиция/аим.\n"
            "Дальше — соберём план без магии.\n\n"
            "🧪 Дрилл\n"
            "7 минут: 3×2 минуты микро-скилл + 1 минута разбор.\n\n"
            "😈 Панчик/мотивация\n"
            "Мы качаем руки, не софт. 😈"
        )

    if not openai_client:
        return enforce_4_blocks("", fallback_cause=cause)

    msgs = build_messages(chat_id, user_text, mode="coach", cause=cause)
    max_out = 750 if ensure_profile(chat_id).get("verbosity") == "talkative" else 550
    out = _openai_chat(msgs, max_out)
    return enforce_4_blocks(out, fallback_cause=cause)

def chat_reply(chat_id: int, user_text: str) -> str:
    cause = classify_cause(user_text)
    stat_inc(chat_id, cause)

    if is_tilt(user_text) and not openai_client:
        return ai_off_chat(chat_id, user_text)

    if not openai_client:
        return ai_off_chat(chat_id, user_text)

    msgs = build_messages(chat_id, user_text, mode="chat", cause=cause)
    max_out = 420 if ensure_profile(chat_id).get("verbosity") == "short" else 650
    out = _openai_chat(msgs, max_out)
    return (out or "").strip()[:3500] or ai_off_chat(chat_id, user_text)


# =========================
# Offset persistence
# =========================
def load_offset() -> int:
    try:
        if os.path.exists(OFFSET_PATH):
            with open(OFFSET_PATH, "r", encoding="utf-8") as f:
                return int((f.read() or "0").strip())
    except Exception:
        pass
    return 0

def save_offset(offset: int) -> None:
    try:
        tmp = OFFSET_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(int(offset)))
        os.replace(tmp, OFFSET_PATH)
    except Exception:
        pass


# =========================
# Handlers
# =========================
def handle_message(chat_id: int, text: str) -> None:
    lock = _get_lock(chat_id)
    if not lock.acquire(blocking=False):
        return
    try:
        if throttle(chat_id):
            return

        p = ensure_profile(chat_id)
        t = (text or "").strip()
        if not t:
            return

        # ✅ Если мы в Zombies-режиме — любой НЕ-командный текст = поиск по текущей карте
        if not t.startswith("/") and p.get("page") == "zombies":
            z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
            if z is not None:
                # возвращаемся в зомби-меню, не трогаем память/ИИ
                send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
                return

        if t.startswith("/start") or t.startswith("/menu"):
            p["page"] = "main"
            ensure_daily(chat_id)
            send_message(chat_id, main_text(chat_id), reply_markup=menu_main(chat_id))
            save_state()
            return

        if t.startswith("/help"):
            send_message(chat_id, help_text(), reply_markup=menu_main(chat_id))
            return

        if t.startswith("/status"):
            send_message(chat_id, status_text(), reply_markup=menu_main(chat_id))
            return

        if t.startswith("/profile"):
            send_message(chat_id, profile_text(chat_id), reply_markup=menu_main(chat_id))
            return

        if t.startswith("/daily"):
            d = ensure_daily(chat_id)
            send_message(chat_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))
            return

        # ✅ Zombies: открываем выбор карты + ставим page=zombies
        if t.startswith("/zombies"):
            p["page"] = "zombies"
            save_state()
            z = zombies_router.handle_callback("zmb:home")
            send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
            return

        if t.startswith("/reset"):
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            USER_STATS.pop(chat_id, None)
            USER_DAILY.pop(chat_id, None)
            ensure_profile(chat_id)
            ensure_daily(chat_id)
            save_state()
            send_message(chat_id, "🧨 Сброс: профиль/память/статы/задание дня очищены.", reply_markup=menu_main(chat_id))
            return

        update_memory(chat_id, "user", t)

        tmp_id = send_message(chat_id, random.choice(THINKING_LINES), reply_markup=None)

        mode = p.get("mode", "chat")
        try:
            reply = coach_reply(chat_id, t) if mode == "coach" else chat_reply(chat_id, t)
        except Exception:
            log.exception("Reply generation failed")
            reply = "Упс 😅 Что-то сломалось. Напиши ещё раз коротко: где умер и почему думаешь?"

        update_memory(chat_id, "assistant", reply)
        p["last_answer"] = reply[:2000]
        save_state()

        if tmp_id:
            try:
                edit_message(chat_id, tmp_id, reply, reply_markup=menu_main(chat_id))
            except Exception:
                send_message(chat_id, reply, reply_markup=menu_main(chat_id))
        else:
            send_message(chat_id, reply, reply_markup=menu_main(chat_id))

    finally:
        lock.release()


def handle_callback(cb: Dict[str, Any]) -> None:
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not cb_id or not chat_id or not message_id:
        return

    try:
        p = ensure_profile(chat_id)

        # ✅ Zombies router перехватывает ВСЕ zmb:* кнопки
        z = zombies_router.handle_callback(data)
        if z is not None:
            # применяем изменения профиля, если router их вернул
            sp = z.get("set_profile") or {}
            if isinstance(sp, dict) and sp:
                for k, v in sp.items():
                    p[k] = v
                save_state()
            edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
            return

        if data == "nav:main":
            p["page"] = "main"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "nav:game":
            edit_message(chat_id, message_id, "🎮 Выбери игру:", reply_markup=menu_game(chat_id))

        elif data == "nav:persona":
            edit_message(chat_id, message_id, "🎭 Выбери стиль:", reply_markup=menu_persona(chat_id))

        elif data == "nav:talk":
            edit_message(chat_id, message_id, "🗣 Длина ответа:", reply_markup=menu_talk(chat_id))

        elif data == "nav:training":
            edit_message(chat_id, message_id, "💪 Тренировка:", reply_markup=menu_training(chat_id))

        elif data == "nav:settings":
            edit_message(chat_id, message_id, "⚙️ Настройки:", reply_markup=menu_settings(chat_id))

        elif data == "toggle:memory":
            p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
            if p["memory"] == "off":
                clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "toggle:mode":
            p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "toggle:ui":
            p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data.startswith("set:game:"):
            g = data.split(":", 2)[2]
            if g in ("auto",) + GAMES:
                p["game"] = g
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data.startswith("set:persona:"):
            v = data.split(":", 2)[2]
            if v in PERSONA_HINT:
                p["persona"] = v
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data.startswith("set:talk:"):
            v = data.split(":", 2)[2]
            if v in VERBOSITY_HINT:
                p["verbosity"] = v
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "action:status":
            edit_message(chat_id, message_id, status_text(), reply_markup=menu_main(chat_id))

        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "action:ai_status":
            ai = "ON" if openai_client else "OFF"
            edit_message(chat_id, message_id, f"🤖 ИИ: {ai}\nМодель: {OPENAI_MODEL}", reply_markup=menu_main(chat_id))

        elif data == "action:clear_memory":
            clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧽 Память очищена.", reply_markup=menu_main(chat_id))

        elif data == "action:reset_all":
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            USER_STATS.pop(chat_id, None)
            USER_DAILY.pop(chat_id, None)
            ensure_profile(chat_id)
            ensure_daily(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧨 Сброс выполнен.", reply_markup=menu_main(chat_id))

        elif data.startswith("action:drill:"):
            kind = data.split(":", 2)[2]
            g = resolve_game(chat_id, "")
            txt = GAME_KB[g]["drills"].get(kind, "Доступно: aim/recoil/movement")
            edit_message(chat_id, message_id, txt, reply_markup=menu_training(chat_id))

        elif data == "action:vod":
            g = resolve_game(chat_id, "")
            edit_message(chat_id, message_id, GAME_KB[g]["vod"], reply_markup=menu_training(chat_id))

        elif data == "action:daily":
            d = ensure_daily(chat_id)
            edit_message(chat_id, message_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))

        elif data == "daily:done":
            d = ensure_daily(chat_id)
            d["done"] = int(d.get("done", 0)) + 1
            save_state()
            edit_message(chat_id, message_id,
                        f"✅ Засчитал.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                        reply_markup=menu_daily(chat_id))

        elif data == "daily:fail":
            d = ensure_daily(chat_id)
            d["fail"] = int(d.get("fail", 0)) + 1
            save_state()
            edit_message(chat_id, message_id,
                        f"❌ Ок, честно.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                        reply_markup=menu_daily(chat_id))

        else:
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

    finally:
        answer_callback(cb_id)


# =========================
# Polling loop
# =========================
def delete_webhook_on_start() -> None:
    try:
        tg_request("deleteWebhook", payload={"drop_pending_updates": True}, is_post=True, retries=3)
        log.info("Webhook deleted (drop_pending_updates=true)")
    except Exception as e:
        log.warning("Could not delete webhook: %r", e)

def run_telegram_bot_once() -> None:
    tg_getme_check_forever()
    if not TELEGRAM_BOT_TOKEN:
        return

    delete_webhook_on_start()
    log.info("Telegram bot started (long polling)")

    offset = load_offset()
    last_offset_save = time.time()

    while True:
        try:
            data = tg_request(
                "getUpdates",
                params={"offset": offset, "timeout": TG_LONGPOLL_TIMEOUT},
                is_post=False,
                retries=TG_RETRIES,
            )

            for upd in data.get("result", []):
                upd_id = upd.get("update_id")
                if isinstance(upd_id, int):
                    offset = max(offset, upd_id + 1)

                if "callback_query" in upd:
                    try:
                        handle_callback(upd["callback_query"])
                    except Exception:
                        log.exception("Callback handling error")
                    continue

                msg = upd.get("message") or upd.get("edited_message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue

                try:
                    handle_message(chat_id, text)
                except Exception:
                    log.exception("Message handling error")
                    try:
                        send_message(chat_id, "Ошибка 😅 Напиши ещё раз коротко.", reply_markup=menu_main(chat_id))
                    except Exception:
                        pass

            if time.time() - last_offset_save >= 5:
                save_offset(offset)
                last_offset_save = time.time()

        except RuntimeError as e:
            s = str(e)
            if "Conflict" in s and ("getUpdates" in s or "terminated by other getUpdates" in s):
                sleep_s = random.randint(CONFLICT_BACKOFF_MIN, CONFLICT_BACKOFF_MAX)
                log.warning("Telegram conflict 409. Backoff %ss: %s", sleep_s, s)
                time.sleep(sleep_s)
                continue
            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2)
        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)

def run_telegram_bot_forever() -> None:
    while True:
        try:
            run_telegram_bot_once()
            if not TELEGRAM_BOT_TOKEN:
                time.sleep(30)
        except Exception:
            log.exception("Polling crashed — restarting in 3 seconds")
            time.sleep(3)


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
        if self.path in ("/", "/healthz", "/"):
            self._ok()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_http_server() -> None:
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    log.info("HTTP server listening on :%s", port)
    server.serve_forever()


# =========================
# Main
# =========================
if __name__ == "__main__":
    try:
        startup_diagnostics()
        load_state()

        stop_autosave = threading.Event()
        threading.Thread(target=autosave_loop, args=(stop_autosave, 60), daemon=True).start()

        threading.Thread(target=run_telegram_bot_forever, daemon=True).start()
        run_http_server()

    except Exception:
        log.error("FATAL STARTUP ERROR:\n%s", traceback.format_exc())
        while True:
            time.sleep(60)
