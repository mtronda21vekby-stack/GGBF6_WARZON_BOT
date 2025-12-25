# -*- coding: utf-8 -*-
"""
FPS Coach Bot — PUBLIC v14 (Render + long polling + working buttons)

Что умеет:
- Работает 24/7 на Render: health endpoint + устойчивый long polling + авто‑рестарт лупа
- Рабочие кнопки (InlineKeyboard): выбор игры, настройки, дриллы, план, VOD, профиль
- AI‑коуч (OpenAI) с фиксированным форматом 1‑2‑3‑4 и более “живыми” ответами (anti‑repeat)
- Авто‑определение игры из текста (Warzone / BF6 / BO7) + ручной выбор кнопкой/командой
- “Умная память”:
  - хранит профиль (игра/платформа/стиль/цель/персона/болтливость)
  - хранит последние N сообщений (короткий контекст)
  - хранит «факты игрока» (что пользователь сам сказал: платформа/сенса/фокус и т.п.)
  - сохранение на диск (Render Disk) через DATA_DIR (иначе /tmp)
- База статей (kb_articles.json) + кнопка/команды: поиск и выдача конспекта по статье
- Безопасность: запрет читов/хака/обходов. Ответы только “честной” практикой.

ENV (Render → Environment):
- TELEGRAM_BOT_TOKEN   (обязательно)
- OPENAI_API_KEY       (обязательно)
- OPENAI_MODEL         (опционально, default: gpt-4o-mini)
- OPENAI_BASE_URL      (опционально, default: https://api.openai.com/v1)

Рекомендуемые ENV:
- DATA_DIR=/var/data   (если подключил Render Disk; иначе оставь /tmp)
- MEMORY_MAX_TURNS=12
- PULSE_MIN_SECONDS=1.25
- MIN_SECONDS_BETWEEN_MSG=0.25
- TG_LONGPOLL_TIMEOUT=50

Start command (Render → Start Command):
python main.py

Файлы:
- main.py (этот файл)
- kb_articles.json (рядом с main.py)
"""

import os
import re
import time
import json
import math
import random
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Optional, Tuple

import requests
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError


# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_v14")


# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

DATA_DIR = os.getenv("DATA_DIR", "/tmp").strip()
STATE_PATH = os.path.join(DATA_DIR, "fps_coach_state.json")

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
TG_LONGPOLL_TIMEOUT = int(os.getenv("TG_LONGPOLL_TIMEOUT", "50"))
TG_RETRIES = int(os.getenv("TG_RETRIES", "5"))

PULSE_MIN_SECONDS = float(os.getenv("PULSE_MIN_SECONDS", "1.25"))
MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.25"))

CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "12"))

# KB file (articles)
KB_ARTICLES_PATH = os.getenv("KB_ARTICLES_PATH", "kb_articles.json").strip()

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise SystemExit("Missing ENV: OPENAI_API_KEY")

os.makedirs(DATA_DIR, exist_ok=True)


# =========================
# OpenAI client
# =========================
openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    timeout=30,
    max_retries=0,  # we retry ourselves
)


# =========================
# Requests session
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-bot/14.0"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=30, pool_maxsize=30))


# =========================
# Game KB (you can expand freely)
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
        "pillars": (
            "🧠 Warzone — фундамент\n"
            "• Позиция/тайминг важнее киллов\n"
            "• Инфо: радар/звук/пинги\n"
            "• Пре-эйм и игра от укрытий\n"
            "• Ротации: заранее\n"
            "• После контакта — репозиция\n"
        ),
        "drills": {
            "aim": "🎯 Aim (7–10м)\n2м warm-up\n3м трекинг\n2м микро\n1–3м дуэли/префайр",
            "recoil": "🔫 Recoil (7–10м)\n2м 15–25м\n3м 25–40м\n2м контроль первой пули\n1–3м дисциплина очередей",
            "movement": "🕹 Movement (7–10м)\nугол→слайд→пик\nджамп-пики\nрепозиция после шота",
        },
        "plan": (
            "📅 План на 7 дней — Warzone\n"
            "Д1–2: aim 10м + movement 10м + 2 смерти разбор\n"
            "Д3–4: углы/тайминги 15м + дисциплина 10м\n"
            "Д5–6: игра от инфо 20м + фиксация ошибок 5м\n"
            "Д7: 45–60м + разбор 3 моментов\n"
        ),
        "vod": (
            "📼 VOD-шаблон (Warzone)\n"
            "1) режим/сквад\n2) где бой\n3) как умер\n"
            "4) ресурсы (плиты/смок/саморез)\n"
            "5) план (пуш/отход/ротация)\n"
        ),
    },
    "bf6": {
        "name": "Battlefield 6 (BF6)",
        "settings": (
            "🌑 BF6 — база\n"
            "• Sens: средняя, ADS ниже\n"
            "• Deadzone: минимум без дрифта\n"
            "• FOV: высокий (комфорт)\n"
            "• После контакта — смена позиции\n"
        ),
        "pillars": (
            "🧠 BF6 — фундамент\n"
            "• линии фронта/спавны\n"
            "• пик→инфо→откат\n"
            "• серия → репозиция\n"
        ),
        "drills": {
            "aim": "🎯 Aim (7–10м)\nпрефайр\nтрекинг\nперестрелка+репозиция",
            "recoil": "🔫 Recoil (7–10м)\nкороткие очереди\nпервая пуля\nконтроль на дистанции",
            "movement": "🕹 Movement (7–10м)\nвыглянул→инфо→откат\nрепик с другого угла",
        },
        "plan": (
            "📅 План на 7 дней — BF6\n"
            "Д1–2: aim 15м + позиции 15м\n"
            "Д3–4: фронт/спавны 20м + дуэли 10м\n"
            "Д5–6: игра от инфо 25м + разбор 5м\n"
            "Д7: 45–60м + разбор 2 смертей\n"
        ),
        "vod": "📼 BF6: карта/режим, класс, где умер/почему, что хотел сделать.",
    },
    "bo7": {
        "name": "Call of Duty: Black Ops 7 (BO7)",
        "settings": (
            "🌑 BO7 — базовый сетап (контроллер)\n"
            "• Sens: 6–8 (перелетаешь → -1)\n"
            "• ADS: 0.80–0.95\n"
            "• Deadzone min: 0.03–0.07\n"
            "• Curve: Dynamic/Standard\n"
            "• FOV: 100–115\n"
        ),
        "pillars": (
            "🧠 BO7 — фундамент\n"
            "• центр экрана + префайр\n"
            "• тайминги\n"
            "• 2 сек на позиции → смена\n"
        ),
        "drills": {
            "aim": "🎯 Aim (7–10м)\nпрефайр\nтрекинг\nмикро‑подводки",
            "recoil": "🔫 Recoil (7–10м)\nкороткие очереди\nпервая пуля\nконтроль на средней",
            "movement": "🕹 Movement (7–10м)\nрепики\nстрейф‑шоты\nсмена угла",
        },
        "plan": (
            "📅 План на 7 дней — BO7\n"
            "Д1–2: aim 20м + movement 10м\n"
            "Д3–4: углы/тайминги 25м + мини‑разбор 5м\n"
            "Д5–6: дуэли 30м\n"
            "Д7: 45–60м + разбор 2–3 смертей\n"
        ),
        "vod": "📼 BO7: режим/карта, смерть, инфо (радар/звук), что хотел сделать.",
    },
}
GAMES = tuple(GAME_KB.keys())


# =========================
# Articles KB (simple local json)
# =========================
def load_articles() -> List[Dict[str, Any]]:
    """
    kb_articles.json format:
    [
      {
        "id": "astra_malorum",
        "title": "Полное руководство ...",
        "url": "https://....",
        "game": "bo7",
        "tags": ["zombies", "пасхалка", "astra malorum"],
        "lang": "ru",
        "summary_ru": "Короткий конспект на русском...",
        "steps_ru": ["Шаг 1 ...", "Шаг 2 ..."]
      }
    ]
    """
    try:
        if os.path.exists(KB_ARTICLES_PATH):
            with open(KB_ARTICLES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception as e:
        log.warning("KB load failed: %r", e)
    return []

ARTICLES = load_articles()


def kb_search(query: str, game: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return []
    scored = []
    for a in ARTICLES:
        if game and a.get("game") and a.get("game") != game:
            continue
        hay = " ".join([
            str(a.get("id", "")),
            str(a.get("title", "")),
            str(a.get("url", "")),
            " ".join(a.get("tags") or []),
            str(a.get("summary_ru", "")),
        ]).lower()
        score = 0
        for token in re.findall(r"[a-zа-я0-9ё]{3,}", q):
            if token in hay:
                score += 1
        if score > 0:
            scored.append((score, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:limit]]


def kb_format_article(a: Dict[str, Any]) -> str:
    title = a.get("title") or a.get("id") or "Статья"
    url = a.get("url", "")
    summary = (a.get("summary_ru") or "").strip()
    steps = a.get("steps_ru") or []
    out = [f"📚 {title}"]
    if url:
        out.append(url)
    if summary:
        out.append("\n🧠 Коротко:")
        out.append(summary)
    if steps:
        out.append("\n🧩 Шаги:")
        for i, s in enumerate(steps[:20], 1):
            out.append(f"{i}) {s}")
    return "\n".join(out).strip()


# =========================
# Persona / answer format
# =========================
SYSTEM_PROMPT = (
    "Ты харизматичный FPS-коуч по Warzone/BF6/BO7. Пишешь по-русски.\n"
    "Тон: уверенный, быстрый, с юмором и лёгкими подколами (без токсичности).\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n\n"
    "Формат ответа ВСЕГДА:\n"
    "1) 🎯 Диагноз (1 главная ошибка)\n"
    "2) ✅ Что делать (2 действия прямо сейчас)\n"
    "3) 🧪 Дрилл (5–10 минут)\n"
    "4) 😈 Панчик/мотивация (1 строка)\n"
    "Если данных мало — задай 1 вопрос в конце."
)

PERSONA_HINT = {
    "spicy": "Стиль: дерзко и смешно, но без оскорблений.",
    "chill": "Стиль: спокойный, дружелюбный, мягкий юмор.",
    "pro": "Стиль: строго по делу, минимум шуток.",
}
VERBOSITY_HINT = {
    "short": "Длина: коротко (до ~10 строк).",
    "normal": "Длина: обычно (10–18 строк).",
    "talkative": "Длина: подробнее (до ~30 строк) + 1–2 доп. совета.",
}
THINKING_LINES = [
    "🧠 Думаю… сейчас будет жара 😈",
    "⌛ Секунду… раскладываю по полочкам 🧩",
    "🎮 Окей, коуч на связи. Сейчас разнесём 👊",
    "🌑 Анализирую… не моргай 😈",
]
FOCUSES: List[Tuple[str, str]] = [
    ("позиционирование", "высота, линии обзора, укрытия, углы"),
    ("тайминг", "репики, паузы, момент входа/выхода из файта"),
    ("инфо", "радар, звук, пинги, UAV/скан, чтение ситуации"),
    ("дуэли", "пик, префайр, first-shot, микрокоррекции"),
    ("дисциплина", "ресурсы, отступления, ресеты, не жадничать"),
    ("плеймейкинг", "инициатива, открытие файта, фланг, давление"),
]


# =========================
# State: profiles + memory + facts
# =========================
USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
USER_FACTS: Dict[int, Dict[str, Any]] = {}  # extracted stable facts
LAST_MSG_TS: Dict[int, float] = {}
CHAT_LOCKS: Dict[int, threading.Lock] = {}
_state_lock = threading.Lock()


def _get_lock(chat_id: int) -> threading.Lock:
    lock = CHAT_LOCKS.get(chat_id)
    if lock is None:
        lock = threading.Lock()
        CHAT_LOCKS[chat_id] = lock
    return lock


def load_state() -> None:
    global USER_PROFILE, USER_MEMORY, USER_FACTS
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            USER_PROFILE = {int(k): v for k, v in (data.get("profiles") or {}).items()}
            USER_MEMORY = {int(k): v for k, v in (data.get("memory") or {}).items()}
            USER_FACTS = {int(k): v for k, v in (data.get("facts") or {}).items()}
            log.info("State loaded: profiles=%d memory=%d facts=%d", len(USER_PROFILE), len(USER_MEMORY), len(USER_FACTS))
    except Exception as e:
        log.warning("State load failed: %r", e)


def save_state() -> None:
    try:
        with _state_lock:
            data = {
                "profiles": {str(k): v for k, v in USER_PROFILE.items()},
                "memory": {str(k): v for k, v in USER_MEMORY.items()},
                "facts": {str(k): v for k, v in USER_FACTS.items()},
                "saved_at": int(time.time()),
            }
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        log.warning("State save failed: %r", e)


def autosave_loop(stop: threading.Event, interval_s: int = 60) -> None:
    while not stop.is_set():
        stop.wait(interval_s)
        if stop.is_set():
            break
        save_state()


load_state()


def ensure_profile(chat_id: int) -> Dict[str, Any]:
    # defaults
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "platform": "",
        "style": "",
        "goal": "",
        "persona": "spicy",
        "verbosity": "normal",
        "ui": "show",
        "last_focus": "",
    })


def update_memory(chat_id: int, role: str, content: str) -> None:
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS * 2:]


def last_assistant_text(chat_id: int, limit: int = 1600) -> str:
    mem = USER_MEMORY.get(chat_id, [])
    for m in reversed(mem):
        if m.get("role") == "assistant":
            return (m.get("content") or "")[:limit]
    return ""


# =========================
# Smart facts extraction (very lightweight)
# =========================
_RX_SENS = re.compile(r"(sens|сенс)\s*[:=]?\s*([0-9]{1,2})(?:\s*/\s*([0-9]{1,2}))?", re.I)
_RX_FOV = re.compile(r"\b(fov)\s*[:=]?\s*([0-9]{2,3})\b", re.I)
_RX_PLATFORM = re.compile(r"\b(xbox|ps5|ps4|ps|playstation|pc|kbm|клава|мыш|комп)\b", re.I)

def extract_facts(chat_id: int, text: str) -> None:
    t = text.lower()

    facts = USER_FACTS.setdefault(chat_id, {})

    m = _RX_PLATFORM.search(t)
    if m:
        raw = m.group(1)
        if raw in ("ps", "ps4", "ps5", "playstation"):
            facts["platform"] = "PlayStation"
        elif raw == "xbox":
            facts["platform"] = "Xbox"
        elif raw in ("pc", "kbm", "клава", "мыш", "комп"):
            facts["platform"] = "PC/KBM"

    m = _RX_SENS.search(t)
    if m:
        a = m.group(2)
        b = m.group(3)
        facts["sens"] = f"{a}/{b}" if b else a

    m = _RX_FOV.search(t)
    if m:
        facts["fov"] = m.group(2)

    # if user explicitly says goal
    if "аим" in t or "aim" in t:
        facts["goal"] = "Aim"
    if "отдач" in t or "recoil" in t:
        facts["goal"] = "Recoil"
    if "ранг" in t or "rank" in t:
        facts["goal"] = "Rank"


# =========================
# Anti-flood
# =========================
def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False


# =========================
# Auto game detect
# =========================
_GAME_PATTERNS = {
    "warzone": re.compile(r"\b(warzone|wz|варзон|варзоне|cod|код|бр|battle\s*royale)\b", re.I),
    "bf6": re.compile(r"\b(bf6|battlefield|батлфилд|battle\s*field)\b", re.I),
    "bo7": re.compile(r"\b(bo7|black\s*ops|блэк\s*опс|blackops|zombies|зомби)\b", re.I),
}

def detect_game(text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None
    hits = []
    for g, rx in _GAME_PATTERNS.items():
        if rx.search(t):
            hits.append(g)
    if "bf6" in hits:
        return "bf6"
    if "bo7" in hits:
        return "bo7"
    if "warzone" in hits:
        return "warzone"
    return None


# =========================
# Similarity check (reduce “под копирку”)
# =========================
def _tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    s = re.sub(r"[^a-zа-я0-9ё\s]+", " ", s)
    return [p for p in s.split() if len(p) >= 3]

def too_similar(a: str, b: str, threshold: float = 0.60) -> bool:
    if not a or not b:
        return False
    ta = set(_tokenize(a))
    tb = set(_tokenize(b))
    if not ta or not tb:
        return False
    sim = len(ta & tb) / max(1, len(ta | tb))
    return sim >= threshold


# =========================
# Telegram API
# =========================
def _sleep_backoff(i: int) -> None:
    time.sleep((0.6 * (i + 1)) + random.random() * 0.25)

def tg_request(method: str, *, params=None, payload=None, is_post: bool = False, retries: int = TG_RETRIES) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last: Optional[Exception] = None
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
    raise last or RuntimeError("Telegram request failed")

def send_message(chat_id: int, text: str, reply_markup=None) -> Optional[int]:
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
    last_msg_id = None
    for ch in chunks:
        res = tg_request("sendMessage", payload={"chat_id": chat_id, "text": ch, "reply_markup": reply_markup}, is_post=True)
        last_msg_id = res.get("result", {}).get("message_id")
    return last_msg_id

def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
    tg_request("editMessageText", payload={"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup}, is_post=True)

def answer_callback(callback_id: str) -> None:
    try:
        tg_request("answerCallbackQuery", payload={"callback_query_id": callback_id}, is_post=True, retries=2)
    except Exception:
        pass

def send_chat_action(chat_id: int, action: str = "typing") -> None:
    try:
        tg_request("sendChatAction", payload={"chat_id": chat_id, "action": action}, is_post=True, retries=2)
    except Exception:
        pass

def delete_webhook_on_start() -> None:
    try:
        tg_request("deleteWebhook", payload={"drop_pending_updates": True}, is_post=True, retries=3)
        log.info("Webhook deleted (drop_pending_updates=true)")
    except Exception as e:
        log.warning("Could not delete webhook: %r", e)


# =========================
# UI (Buttons)
# =========================
def kb_main(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    g = p.get("game", "warzone")
    persona = p.get("persona", "spicy")
    talk = p.get("verbosity", "normal")
    return {
        "inline_keyboard": [
            [{"text": f"🎮 Игра: {g.upper()}", "callback_data": "menu:game"},
             {"text": f"😈 Persona: {persona}", "callback_data": "menu:persona"}],
            [{"text": f"🗣 Talk: {talk}", "callback_data": "menu:talk"},
             {"text": "⚙️ Settings", "callback_data": "action:settings"}],
            [{"text": "💪 Drills", "callback_data": "action:drills"},
             {"text": "📅 Plan", "callback_data": "action:plan"}],
            [{"text": "📼 VOD", "callback_data": "action:vod"},
             {"text": "📚 Статьи", "callback_data": "action:kb"}],
            [{"text": "👤 Profile", "callback_data": "action:profile"},
             {"text": "🧹 Reset", "callback_data": "action:reset"}],
            [{"text": "🕶 Hide UI", "callback_data": "action:ui"}],
        ]
    }

def kb_game(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    cur = p.get("game", "warzone")
    def b(key, label):
        mark = "✅ " if cur == key else ""
        return {"text": f"{mark}{label}", "callback_data": f"set:game:{key}"}
    return {
        "inline_keyboard": [
            [b("warzone", "Warzone"), b("bf6", "BF6"), b("bo7", "BO7")],
            [{"text": "⬅️ Назад", "callback_data": "action:menu"}],
        ]
    }

def kb_persona(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    cur = p.get("persona", "spicy")
    def b(key):
        mark = "✅ " if cur == key else ""
        return {"text": f"{mark}{key}", "callback_data": f"set:persona:{key}"}
    return {
        "inline_keyboard": [
            [b("spicy"), b("chill"), b("pro")],
            [{"text": "⬅️ Назад", "callback_data": "action:menu"}],
        ]
    }

def kb_talk(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    cur = p.get("verbosity", "normal")
    def b(key):
        mark = "✅ " if cur == key else ""
        return {"text": f"{mark}{key}", "callback_data": f"set:talk:{key}"}
    return {
        "inline_keyboard": [
            [b("short"), b("normal"), b("talkative")],
            [{"text": "⬅️ Назад", "callback_data": "action:menu"}],
        ]
    }

def kb_drills(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    return {
        "inline_keyboard": [
            [{"text": "🎯 Aim", "callback_data": "drill:aim"},
             {"text": "🔫 Recoil", "callback_data": "drill:recoil"},
             {"text": "🕹 Movement", "callback_data": "drill:movement"}],
            [{"text": "⬅️ Назад", "callback_data": "action:menu"}],
        ]
    }

def kb_kb(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    return {
        "inline_keyboard": [
            [{"text": "🔎 Найти статью", "callback_data": "kb:help"},
             {"text": "⭐ Топ по игре", "callback_data": "kb:top"}],
            [{"text": "⬅️ Назад", "callback_data": "action:menu"}],
        ]
    }

def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    g = p.get("game", "warzone")
    return (
        "🌑 FPS Coach Bot\n"
        f"Игра: {GAME_KB[g]['name']}\n"
        f"Persona: {p.get('persona')} | Talk: {p.get('verbosity')}\n\n"
        "Пиши ситуацию (как умер/что не получается) — отвечу как коуч.\n"
        "Или жми кнопки 👇"
    )

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    facts = USER_FACTS.get(chat_id, {})
    lines = [
        "👤 Профиль",
        f"Игра: {GAME_KB[p['game']]['name']}",
        f"Платформа: {p.get('platform') or facts.get('platform') or '—'}",
        f"Стиль: {p.get('style') or '—'}",
        f"Цель: {p.get('goal') or facts.get('goal') or '—'}",
        f"Persona: {p.get('persona')}",
        f"Talk: {p.get('verbosity')}",
    ]
    if facts:
        extras = []
        if facts.get("sens"):
            extras.append(f"sens={facts['sens']}")
        if facts.get("fov"):
            extras.append(f"fov={facts['fov']}")
        if extras:
            lines.append("Факты: " + ", ".join(extras))
    lines += [
        "",
        "Команды (если не хочешь кнопки):",
        "/start  /status  /profile  /reset",
        "/game warzone|bf6|bo7",
        "/persona spicy|chill|pro",
        "/talk short|normal|talkative",
        "/kb_search <слово>  (например: /kb_search astra)",
    ]
    return "\n".join(lines)


def status_text() -> str:
    return (
        "🧾 Status\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"DATA_DIR: {DATA_DIR}\n"
        f"STATE_PATH: {STATE_PATH}\n"
        f"ARTICLES: {len(ARTICLES)}\n\n"
        "Если ловишь Conflict 409 — значит запущены 2 инстанса (Render Instances > 1)\n"
        "или два сервиса с этим ботом.\n"
    )


# =========================
# Animation (safe)
# =========================
def typing_loop(chat_id: int, stop_event: threading.Event, interval: float = 4.0) -> None:
    while not stop_event.is_set():
        send_chat_action(chat_id, "typing")
        stop_event.wait(interval)

def pulse_edit_loop(chat_id: int, message_id: int, stop_event: threading.Event, base: str = "⌛ Думаю") -> None:
    dots = 0
    last_edit = 0.0
    while not stop_event.is_set():
        now = time.time()
        if now - last_edit >= PULSE_MIN_SECONDS:
            dots = (dots + 1) % 4
            try:
                edit_message(chat_id, message_id, base + ("." * dots))
            except Exception:
                pass
            last_edit = now
        stop_event.wait(0.2)


# =========================
# OpenAI
# =========================
def _openai_create(messages: List[Dict[str, str]], max_tokens: int):
    """
    Penalties + temperature to reduce “под копирку”.
    """
    kwargs = dict(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.95,
        presence_penalty=0.75,
        frequency_penalty=0.45,
    )
    try:
        return openai_client.chat.completions.create(**kwargs, max_completion_tokens=max_tokens)
    except TypeError:
        return openai_client.chat.completions.create(**kwargs, max_tokens=max_tokens)


def build_messages(chat_id: int, user_text: str, regen: bool = False) -> List[Dict[str, str]]:
    p = ensure_profile(chat_id)

    detected = detect_game(user_text)
    if detected in GAMES:
        p["game"] = detected

    # rotate focus (avoid repeating last focus)
    last_focus = p.get("last_focus") or ""
    focus = random.choice(FOCUSES)
    if last_focus and len(FOCUSES) > 1:
        for _ in range(4):
            if focus[0] != last_focus:
                break
            focus = random.choice(FOCUSES)
    p["last_focus"] = focus[0]

    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")
    game = p.get("game", "warzone")

    facts = USER_FACTS.get(chat_id, {})
    facts_line = ""
    if facts:
        # keep short
        parts = []
        if facts.get("platform"):
            parts.append(f"platform={facts['platform']}")
        if facts.get("sens"):
            parts.append(f"sens={facts['sens']}")
        if facts.get("fov"):
            parts.append(f"fov={facts['fov']}")
        if parts:
            facts_line = "ФАКТЫ ПРО ИГРОКА: " + ", ".join(parts)

    anti_repeat = (
        "ВАЖНО: Не отвечай шаблоном.\n"
        "1) Упомяни детали из сообщения пользователя (перефразируй).\n"
        "2) Дай 2 действия и дрилл, которые подходят ИМЕННО под ситуацию.\n"
        "3) Не повторяй текст прошлого ответа ассистента.\n"
        "4) Избегай одинаковых связок фраз, меняй формулировки.\n"
    )
    prev = last_assistant_text(chat_id, limit=1200)
    if prev:
        anti_repeat += "\nПРОШЛЫЙ ОТВЕТ (избегай повторов):\n" + prev

    if regen:
        anti_repeat += (
            "\nРЕЖИМ АНТИ‑ПОВТОР x2: полностью поменяй 2 действия и дрилл; "
            "выбери другой угол (например: дуэли вместо позиционирования).\n"
        )

    coach_frame = (
        "Не выдумывай патчи/мету. Если не уверен — общие принципы.\n"
        "Запрещено: читы/хаки/обход античита.\n"
        f"СЕГОДНЯШНИЙ ФОКУС: {focus[0]} — {focus[1]}.\n"
        + (facts_line + "\n" if facts_line else "")
        f"Текущая игра: {GAME_KB[game]['name']}.\n"
    )

    max_hint = VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": max_hint},
        {"role": "system", "content": coach_frame},
        {"role": "system", "content": anti_repeat},
        {"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"},
    ]
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})
    return messages


def openai_reply(chat_id: int, user_text: str) -> str:
    prev = last_assistant_text(chat_id, limit=1800)
    messages = build_messages(chat_id, user_text, regen=False)

    max_out = 780 if ensure_profile(chat_id).get("verbosity") == "talkative" else 560

    for attempt in range(2):
        try:
            resp = _openai_create(messages, max_out)
            out = (resp.choices[0].message.content or "").strip()
            if not out:
                out = "Не получил ответ. Напиши ещё раз 🙌"

            if attempt == 0 and prev and too_similar(out, prev):
                messages = build_messages(chat_id, user_text, regen=True)
                continue

            return out

        except APIConnectionError:
            if attempt == 0:
                time.sleep(0.9)
                continue
            return "⚠️ AI: проблема соединения. Попробуй ещё раз через минуту."
        except AuthenticationError:
            return "❌ AI: неверный ключ OPENAI_API_KEY."
        except RateLimitError:
            return "⏳ AI: лимит/перегруз. Подожди 20–60 сек и попробуй снова."
        except BadRequestError:
            return f"❌ AI: bad request. Модель: {OPENAI_MODEL}."
        except APIError:
            return "⚠️ AI: временная ошибка сервиса. Попробуй ещё раз."
        except Exception:
            log.exception("OpenAI unknown error")
            return "⚠️ AI: неизвестная ошибка. Напиши /status."


# =========================
# Commands (simple for users)
# =========================
def help_text() -> str:
    return (
        "🌑 FPS Coach Bot\n"
        "Пиши ситуацию — отвечу как коуч.\n\n"
        "Самое простое управление:\n"
        "• Нажми /start и пользуйся кнопками\n"
        "• Или напиши: «Warzone / BF6 / BO7» в сообщении — игру определю сам\n\n"
        "Команды:\n"
        "/start /status /profile /reset\n"
        "/game warzone|bf6|bo7\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/kb_search <слово>\n"
    )


# =========================
# Handlers
# =========================
def handle_message(chat_id: int, text: str) -> None:
    with _get_lock(chat_id):
        if throttle(chat_id):
            return

        p = ensure_profile(chat_id)
        t = (text or "").strip()

        # update facts from ANY text (including commands), cheap and useful
        extract_facts(chat_id, t)

        if t.startswith("/start") or t.startswith("/menu"):
            send_message(chat_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))
            save_state()
            return

        if t.startswith("/help"):
            send_message(chat_id, help_text(), reply_markup=kb_main(chat_id))
            return

        if t.startswith("/status"):
            send_message(chat_id, status_text(), reply_markup=kb_main(chat_id))
            return

        if t.startswith("/profile"):
            send_message(chat_id, profile_text(chat_id), reply_markup=kb_main(chat_id))
            return

        if t.startswith("/reset"):
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            USER_FACTS.pop(chat_id, None)
            ensure_profile(chat_id)
            save_state()
            send_message(chat_id, "🧹 Сбросил профиль/память/факты.", reply_markup=kb_main(chat_id))
            return

        if t.startswith("/ui"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].lower() in ("show", "hide"):
                p["ui"] = parts[1].lower()
                save_state()
                send_message(chat_id, f"✅ UI = {p['ui']}", reply_markup=kb_main(chat_id))
            else:
                send_message(chat_id, "Используй: /ui show | /ui hide", reply_markup=kb_main(chat_id))
            return

        if t.startswith("/persona"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].lower() in ("spicy", "chill", "pro"):
                p["persona"] = parts[1].lower()
                save_state()
                send_message(chat_id, f"✅ Persona = {p['persona']}", reply_markup=kb_main(chat_id))
            else:
                send_message(chat_id, "Используй: /persona spicy|chill|pro", reply_markup=kb_main(chat_id))
            return

        if t.startswith("/talk"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].lower() in ("short", "normal", "talkative"):
                p["verbosity"] = parts[1].lower()
                save_state()
                send_message(chat_id, f"✅ Talk = {p['verbosity']}", reply_markup=kb_main(chat_id))
            else:
                send_message(chat_id, "Используй: /talk short|normal|talkative", reply_markup=kb_main(chat_id))
            return

        if t.startswith("/game"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].lower() in GAMES:
                p["game"] = parts[1].lower()
                save_state()
                send_message(chat_id, f"✅ Игра = {GAME_KB[p['game']]['name']}", reply_markup=kb_main(chat_id))
            else:
                send_message(chat_id, "Используй: /game warzone | bf6 | bo7", reply_markup=kb_main(chat_id))
            return

        if t.startswith("/kb_search"):
            q = t[len("/kb_search"):].strip()
            res = kb_search(q, game=p.get("game"))
            if not res:
                send_message(chat_id, "Не нашёл. Попробуй другое слово (например: /kb_search zombies)", reply_markup=kb_main(chat_id))
                return
            lines = ["🔎 Нашёл:"]
            for a in res:
                lines.append(f"• {a.get('id')} — {a.get('title')}")
            lines.append("\nЧтобы открыть: /kb_show <id>")
            send_message(chat_id, "\n".join(lines), reply_markup=kb_main(chat_id))
            return

        if t.startswith("/kb_show"):
            art_id = t[len("/kb_show"):].strip()
            a = next((x for x in ARTICLES if str(x.get("id")) == art_id), None)
            if not a:
                send_message(chat_id, "Не нашёл такой id. Сначала: /kb_search <слово>", reply_markup=kb_main(chat_id))
                return
            send_message(chat_id, kb_format_article(a), reply_markup=kb_main(chat_id))
            return

        # auto-detect game from normal text too
        detected = detect_game(t)
        if detected in GAMES:
            p["game"] = detected

        # AI reply + safe animation
        update_memory(chat_id, "user", t)
        tmp_id = send_message(chat_id, random.choice(THINKING_LINES), reply_markup=None)

        stop = threading.Event()
        threading.Thread(target=typing_loop, args=(chat_id, stop), daemon=True).start()
        if tmp_id:
            threading.Thread(target=pulse_edit_loop, args=(chat_id, tmp_id, stop, "⌛ Думаю"), daemon=True).start()

        try:
            reply = openai_reply(chat_id, t)
        finally:
            stop.set()

        update_memory(chat_id, "assistant", reply)
        save_state()

        if tmp_id:
            try:
                edit_message(chat_id, tmp_id, reply, reply_markup=kb_main(chat_id))
            except Exception:
                send_message(chat_id, reply, reply_markup=kb_main(chat_id))
        else:
            send_message(chat_id, reply, reply_markup=kb_main(chat_id))


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

        if data == "action:menu":
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "menu:game":
            edit_message(chat_id, message_id, "Выбери игру:", reply_markup=kb_game(chat_id))

        elif data == "menu:persona":
            edit_message(chat_id, message_id, "Выбери Persona:", reply_markup=kb_persona(chat_id))

        elif data == "menu:talk":
            edit_message(chat_id, message_id, "Выбери Talk:", reply_markup=kb_talk(chat_id))

        elif data.startswith("set:game:"):
            g = data.split(":", 2)[2]
            if g in GAMES:
                p["game"] = g
                save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data.startswith("set:persona:"):
            v = data.split(":", 2)[2]
            if v in PERSONA_HINT:
                p["persona"] = v
                save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data.startswith("set:talk:"):
            v = data.split(":", 2)[2]
            if v in VERBOSITY_HINT:
                p["verbosity"] = v
                save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:settings":
            g = p.get("game", "warzone")
            edit_message(chat_id, message_id, GAME_KB[g]["settings"], reply_markup=kb_main(chat_id))

        elif data == "action:plan":
            g = p.get("game", "warzone")
            edit_message(chat_id, message_id, GAME_KB[g]["plan"], reply_markup=kb_main(chat_id))

        elif data == "action:vod":
            g = p.get("game", "warzone")
            edit_message(chat_id, message_id, GAME_KB[g]["vod"], reply_markup=kb_main(chat_id))

        elif data == "action:drills":
            edit_message(chat_id, message_id, "Выбери дрилл:", reply_markup=kb_drills(chat_id))

        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            g = p.get("game", "warzone")
            txt = GAME_KB[g]["drills"].get(kind, "Доступно: aim/recoil/movement")
            edit_message(chat_id, message_id, txt, reply_markup=kb_drills(chat_id))

        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:reset":
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            USER_FACTS.pop(chat_id, None)
            ensure_profile(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧹 Сбросил профиль/память/факты.", reply_markup=kb_main(chat_id))

        elif data == "action:ui":
            p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
            save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:kb":
            edit_message(chat_id, message_id, "📚 Статьи: что делаем?", reply_markup=kb_kb(chat_id))

        elif data == "kb:help":
            txt = (
                "🔎 Поиск статей:\n"
                "Напиши команду:\n"
                "/kb_search <слово>\n\n"
                "Например:\n"
                "/kb_search astra\n"
                "/kb_search zombies\n\n"
                "Потом открой:\n"
                "/kb_show <id>\n"
            )
            edit_message(chat_id, message_id, txt, reply_markup=kb_kb(chat_id))

        elif data == "kb:top":
            g = p.get("game", "warzone")
            # naive top: first 5 by game
            lst = [a for a in ARTICLES if a.get("game") == g][:5]
            if not lst:
                txt = "Пока нет статей под эту игру. Добавь в kb_articles.json."
            else:
                lines = [f"⭐ Топ по {GAME_KB[g]['name']}:"]
                for a in lst:
                    lines.append(f"• {a.get('id')} — {a.get('title')}")
                lines.append("\nОткрыть: /kb_show <id>")
                txt = "\n".join(lines)
            edit_message(chat_id, message_id, txt, reply_markup=kb_kb(chat_id))

        else:
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

    finally:
        answer_callback(cb_id)


# =========================
# Polling loop (hardened + restart)
# =========================
def run_telegram_bot_once() -> None:
    delete_webhook_on_start()
    log.info("Telegram bot started (long polling)")
    offset = 0

    while True:
        try:
            data = tg_request("getUpdates", params={"offset": offset, "timeout": TG_LONGPOLL_TIMEOUT})

            for upd in data.get("result", []):
                offset = upd.get("update_id", offset) + 1

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
                    send_message(chat_id, "Ошибка 😅 Попробуй ещё раз.", reply_markup=kb_main(chat_id))

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


def run_telegram_bot_forever() -> None:
    while True:
        try:
            run_telegram_bot_once()
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


if __name__ == "__main__":
    stop_autosave = threading.Event()
    threading.Thread(target=autosave_loop, args=(stop_autosave, 60), daemon=True).start()

    threading.Thread(target=run_telegram_bot_forever, daemon=True).start()
    run_http_server()
