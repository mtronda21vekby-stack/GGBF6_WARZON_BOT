# -*- coding: utf-8 -*-
"""
FPS Coach Bot — clean_hardened (Render + long polling + memory)

Фишки:
- /healthz всегда живой (HTTP в main thread), Telegram polling в daemon thread.
- Не падает “молча”: лог + traceback.
- Если TELEGRAM_BOT_TOKEN отсутствует — процесс жив (healthz OK), Telegram не стартуем.
- getMe self-check + deleteWebhook(drop_pending_updates=True)
- OpenAI опционален: нет ключа/пакета -> AI OFF, бот живёт.
- Память/профиль/факты/заметки сохраняются в DATA_DIR.
- UI-кнопки (inline keyboard) + команды.

ENV (Render):
- TELEGRAM_BOT_TOKEN=...
- OPENAI_API_KEY=... (опционально)
- OPENAI_MODEL=gpt-4o-mini (или gpt-4o если доступно)
- DATA_DIR=/tmp (по умолчанию)
- PORT=10000 (Render выставит сам)
"""

import os
import re
import sys
import time
import json
import random
import threading
import logging
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Optional, Tuple

import requests

# OpenAI optional
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_clean")


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
TG_RETRIES = int(os.getenv("TG_RETRIES", "5"))

CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

PULSE_MIN_SECONDS = float(os.getenv("PULSE_MIN_SECONDS", "1.25"))
MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.25"))

MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))
KB_ARTICLES_PATH = os.getenv("KB_ARTICLES_PATH", "kb_articles.json").strip()

MAX_TEXT_LEN = 3900

os.makedirs(DATA_DIR, exist_ok=True)


def startup_diagnostics() -> None:
    try:
        log.info("=== STARTUP DIAGNOSTICS ===")
        log.info("python: %s", sys.version.replace("\n", " "))
        log.info("cwd: %s", os.getcwd())
        try:
            log.info("files: %s", ", ".join(sorted(os.listdir("."))[:40]))
        except Exception:
            pass
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
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=30,
            max_retries=0,
        )
    except Exception as e:
        log.warning("OpenAI init failed: %r", e)
        openai_client = None
else:
    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY missing => AI OFF (bot still runs).")
    if not OpenAI:
        log.warning("openai package not installed => AI OFF.")


# =========================
# Requests session (Telegram)
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-bot/clean_hardened"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=40, pool_maxsize=40))


# =========================
# Game KB
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
            "aim": "🎯 Aim (5–10м)\n• warm-up 2м\n• трекинг 3м\n• микро 2м\n• дуэли/префайр 1–3м",
            "recoil": "🔫 Recoil (5–10м)\n• 15–25м 2м\n• 25–40м 3м\n• первая пуля 2м\n• очереди 1–3м",
            "movement": "🕹 Movement (5–10м)\n• угол→пик→откат\n• джамп/слайд пики\n• репозиция после контакта",
        },
        "plan": (
            "📅 План на 7 дней — Warzone\n"
            "Д1–2: aim 10м + movement 10м + разбор 2 смертей\n"
            "Д3–4: углы/тайминги 15м + дисциплина 10м\n"
            "Д5–6: игра от инфо 20м + фиксация ошибок 5м\n"
            "Д7: 45–60м + разбор 3 моментов\n"
        ),
        "vod": "📼 VOD (коротко): режим/сквад → где бой → как умер → ресурсы → что хотел сделать.",
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
        "drills": {
            "aim": "🎯 Aim (5–10м)\n• префайр\n• трекинг\n• файт→репозиция",
            "recoil": "🔫 Recoil (5–10м)\n• короткие очереди\n• первая пуля\n• контроль на дистанции",
            "movement": "🕹 Movement (5–10м)\n• выглянул→инфо→откат\n• репик с другого угла",
        },
        "plan": (
            "📅 План на 7 дней — BF6\n"
            "Д1–2: aim 15м + позиции 15м\n"
            "Д3–4: фронт/спавны 20м + дуэли 10м\n"
            "Д5–6: игра от инфо 25м + разбор 5м\n"
            "Д7: 45–60м + разбор 2 смертей\n"
        ),
        "vod": "📼 BF6: карта/режим → класс → где умер/почему → что хотел сделать → что помешало.",
    },
    "bo7": {
        "name": "Call of Duty: Black Ops 7 (BO7)",
        "settings": (
            "🌑 BO7 — базовый сетап (контроллер)\n"
            "• Sens: 6–8 (перелетаешь → -1)\n"
            "• ADS: 0.80–0.95\n"
            "• Deadzone min: 0.03–0.07\n"
            "• FOV: 100–115\n"
        ),
        "drills": {
            "aim": "🎯 Aim (5–10м)\n• префайр\n• трекинг\n• микро-подводки",
            "recoil": "🔫 Recoil (5–10м)\n• короткие очереди\n• первая пуля\n• контроль на средней",
            "movement": "🕹 Movement (5–10м)\n• репики\n• стрейф-шоты\n• смена угла",
        },
        "plan": (
            "📅 План на 7 дней — BO7\n"
            "Д1–2: aim 20м + movement 10м\n"
            "Д3–4: углы/тайминги 25м + мини-разбор 5м\n"
            "Д5–6: дуэли 30м\n"
            "Д7: 45–60м + разбор 2–3 смертей\n"
        ),
        "vod": "📼 BO7: режим/карта → смерть → инфо (радар/звук) → что хотел сделать → что не учёл.",
    },
}
GAMES = tuple(GAME_KB.keys())


# =========================
# Articles KB (optional)
# =========================
def load_articles() -> List[Dict[str, Any]]:
    try:
        if KB_ARTICLES_PATH and os.path.exists(KB_ARTICLES_PATH):
            with open(KB_ARTICLES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("articles"), list):
                return data["articles"]
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
    tokens = re.findall(r"[a-zа-я0-9ё]{3,}", q)
    scored = []
    for a in ARTICLES:
        if game and a.get("game") and a.get("game") != game:
            continue
        hay = " ".join(
            [
                str(a.get("id", "")),
                str(a.get("title", "")),
                " ".join(a.get("tags") or []),
                str(a.get("summary_ru", "")),
                " ".join(a.get("steps_ru") or []),
            ]
        ).lower()
        score = sum(1 for t in tokens if t in hay)
        if score > 0:
            score += 2 * sum(1 for t in tokens if t in str(a.get("title", "")).lower())
            scored.append((score, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:limit]]


def kb_get(article_id: str) -> Optional[Dict[str, Any]]:
    aid = (article_id or "").strip()
    for a in ARTICLES:
        if str(a.get("id", "")).strip() == aid:
            return a
    return None


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
        for s in steps[:12]:
            if isinstance(s, str) and s.strip():
                out.append(f"• {s.strip()}")
    return "\n".join(out).strip()


def kb_relevant_steps(user_text: str, game: str, limit_steps: int = 3) -> List[str]:
    t = (user_text or "").lower()
    tokens = set(re.findall(r"[a-zа-я0-9ё]{3,}", t))
    best = None
    best_score = 0
    for a in ARTICLES:
        if a.get("lang") and a.get("lang") != "ru":
            continue
        if a.get("game") and a.get("game") != game:
            continue
        hay = " ".join(
            [
                str(a.get("title", "")),
                " ".join(a.get("tags") or []),
                str(a.get("summary_ru", "")),
            ]
        ).lower()
        score = sum(1 for tok in tokens if tok in hay)
        if score > best_score:
            best_score = score
            best = a
    if not best or best_score <= 0:
        return []
    steps = best.get("steps_ru") or []
    out = []
    for s in steps:
        if isinstance(s, str) and s.strip():
            out.append(s.strip())
        if len(out) >= limit_steps:
            break
    return out


# =========================
# Style
# =========================
SYSTEM_PROMPT = (
    "Ты харизматичный FPS-коуч по Warzone/BF6/BO7. Пишешь по-русски.\n"
    "Тон: уверенный, быстрый, живой, с юмором, без токсичности.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n\n"
    "Формат ответа СТРОГО 4 блока и только так:\n"
    "🎯 Диагноз\n"
    "✅ Что делать\n"
    "🧪 Дрилл\n"
    "😈 Панчик/мотивация\n\n"
    "В '✅ Что делать' дай РОВНО 2 строки:\n"
    "Сейчас — ...\n"
    "Дальше — ...\n"
    "Не нумеруй, не делай подпункты.\n"
    "Если мало данных — один короткий вопрос в самом конце."
)

PERSONA_HINT = {
    "spicy": "Стиль: дерзко и смешно, но без унижений.",
    "chill": "Стиль: спокойный, дружелюбный, мягкий юмор.",
    "pro": "Стиль: строго по делу, минимум шуток.",
}
VERBOSITY_HINT = {
    "short": "Длина: коротко, без воды.",
    "normal": "Длина: обычно, плотная польза.",
    "talkative": "Длина: подробнее, но не занудно.",
}

FOCUSES: List[Tuple[str, str]] = [
    ("позиционка", "углы, укрытия, высота, линии обзора"),
    ("тайминг", "когда входить/выходить, репики, паузы"),
    ("инфо", "радар, звук, пинги, чтение ситуации"),
    ("дуэли", "пик, first-shot, центрирование, микро-коррекции"),
    ("дисциплина", "ресурсы, ресеты, не жадничать, контроль"),
    ("плеймейкинг", "инициатива, фланг, давление, открытие файта"),
]

MICRO_CHALLENGES = [
    "🎲 Micro-Challenge: 3 файта подряд — после первого хита сразу смени угол.",
    "🎲 Micro-Challenge: 5 минут — держи центр экрана на уровне головы/плеч.",
    "🎲 Micro-Challenge: 3 входа в бой — сначала инфо (радар/звук), потом стрельба.",
    "🎲 Micro-Challenge: каждый файт — один фейк-пик перед реальным выходом.",
]

THINKING_LINES = [
    "🧠 Ща разложу…",
    "⌛ Секунду, включаю коуча…",
    "🎮 Окей. Сейчас будет практично.",
    "🌑 Анализирую. Не моргай 😈",
]

_SMALLTALK_RX = re.compile(
    r"^\s*(привет|здаров|здравствуйте|йо|ку|qq|hello|hi|хай|добрый\s*(день|вечер|утро)|что\s+умеешь\??)\s*[!.\-–—]*\s*$",
    re.I,
)


def is_smalltalk(text: str) -> bool:
    return bool(_SMALLTALK_RX.match(text or ""))


def is_low_info(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12:
        return True
    tl = t.lower()
    keywords = [
        "умираю",
        "сливаю",
        "проигрываю",
        "не получается",
        "ошибка",
        "пуш",
        "эндгейм",
        "пози",
        "дуэ",
        "тайм",
        "инфо",
        "аим",
        "отдач",
        "сенс",
        "fov",
        "пинг",
    ]
    return not any(k in tl for k in keywords)


# =========================
# State
# =========================
USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
USER_FACTS: Dict[int, Dict[str, Any]] = {}
COACH_NOTES: Dict[int, str] = {}
LAST_MSG_TS: Dict[int, float] = {}

CHAT_LOCKS: Dict[int, threading.Lock] = {}
LOCKS_GUARD = threading.Lock()
STATE_GUARD = threading.Lock()


def _get_lock(chat_id: int) -> threading.Lock:
    with LOCKS_GUARD:
        lock = CHAT_LOCKS.get(chat_id)
        if lock is None:
            lock = threading.Lock()
            CHAT_LOCKS[chat_id] = lock
        return lock


def load_state() -> None:
    global USER_PROFILE, USER_MEMORY, USER_FACTS, COACH_NOTES
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            USER_PROFILE = {int(k): v for k, v in (data.get("profiles") or {}).items()}
            USER_MEMORY = {int(k): v for k, v in (data.get("memory") or {}).items()}
            USER_FACTS = {int(k): v for k, v in (data.get("facts") or {}).items()}
            COACH_NOTES = {int(k): str(v) for k, v in (data.get("coach_notes") or {}).items()}
            log.info(
                "State loaded: profiles=%d memory=%d facts=%d notes=%d",
                len(USER_PROFILE),
                len(USER_MEMORY),
                len(USER_FACTS),
                len(COACH_NOTES),
            )
    except Exception as e:
        log.warning("State load failed (reset state): %r", e)


def save_state() -> None:
    try:
        with STATE_GUARD:
            data = {
                "profiles": {str(k): v for k, v in USER_PROFILE.items()},
                "memory": {str(k): v for k, v in USER_MEMORY.items()},
                "facts": {str(k): v for k, v in USER_FACTS.items()},
                "coach_notes": {str(k): v for k, v in COACH_NOTES.items()},
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


load_state()


def ensure_profile(chat_id: int) -> Dict[str, Any]:
    return USER_PROFILE.setdefault(
        chat_id,
        {
            "game": "auto",
            "persona": "spicy",
            "verbosity": "normal",
            "ui": "show",
            "memory": "on",
            "last_focus": "",
            "last_answer": "",
        },
    )


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
    p["last_focus"] = ""


def update_coach_notes(chat_id: int, user_text: str) -> None:
    tl = (user_text or "").lower()
    notes = COACH_NOTES.get(chat_id, "").strip()

    tags = []
    if any(x in tl for x in ["не слыш", "звук", "шаги"]):
        tags.append("часто теряет инфо по звуку")
    if any(x in tl for x in ["тайминг", "когда пуш", "момент"]):
        tags.append("проблема тайминга (вход/выход)")
    if any(x in tl for x in ["пози", "угол", "высот"]):
        tags.append("позиционка/углы")
    if any(x in tl for x in ["дуэль", "1v1", "вблизи", "ближ"]):
        tags.append("дуэли (особенно ближние)")

    if not tags:
        return

    existing = set([x.strip() for x in notes.split(" • ") if x.strip()]) if notes else set()
    for t in tags:
        existing.add(t)
    COACH_NOTES[chat_id] = " • ".join(sorted(existing))[:600]


# =========================
# Facts
# =========================
_RX_SENS = re.compile(r"(sens|сенс)\s*[:=]?\s*([0-9]{1,2})(?:\s*/\s*([0-9]{1,2}))?", re.I)
_RX_FOV = re.compile(r"\b(fov)\s*[:=]?\s*([0-9]{2,3})\b", re.I)
_RX_PLATFORM = re.compile(r"\b(xbox|ps5|ps4|ps|playstation|pc|kbm|клава|мыш|комп)\b", re.I)


def extract_facts(chat_id: int, text: str) -> None:
    t = (text or "").lower()
    facts = USER_FACTS.setdefault(chat_id, {})

    m = _RX_PLATFORM.search(t)
    if m:
        raw = m.group(1).lower()
        if raw in ("ps", "ps4", "ps5", "playstation"):
            facts["platform"] = "PlayStation"
        elif raw == "xbox":
            facts["platform"] = "Xbox"
        else:
            facts["platform"] = "PC/KBM"

    m = _RX_SENS.search(t)
    if m:
        a = m.group(2)
        b = m.group(3)
        facts["sens"] = f"{a}/{b}" if b else a

    m = _RX_FOV.search(t)
    if m:
        facts["fov"] = m.group(2)


def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False


# =========================
# Game detect
# =========================
_GAME_PATTERNS = {
    "warzone": re.compile(r"\b(warzone|wz|варзон|verdansk|rebirth|gulag|бр|battle\s*royale)\b", re.I),
    "bf6": re.compile(r"\b(bf6|battlefield|батлфилд|конквест|захват)\b", re.I),
    "bo7": re.compile(r"\b(bo7|black\s*ops|блэк\s*опс|zombies|зомби|hardpoint|хардпоинт)\b", re.I),
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


def resolve_game(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    forced = p.get("game", "auto")
    if forced in GAMES:
        return forced
    detected = detect_game(user_text)
    return detected if detected in GAMES else "warzone"


def _tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    s = re.sub(r"[^a-zа-я0-9ё\s]+", " ", s)
    return [p for p in s.split() if len(p) >= 4]


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta = set(_tokenize(a))
    tb = set(_tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def is_cheat_request(text: str) -> bool:
    t = (text or "").lower()
    banned = ["чит", "cheat", "hack", "обход", "античит", "exploit", "эксплойт", "аимбот", "wallhack", "вх", "спуфер"]
    return any(w in t for w in banned)


# =========================
# Telegram API
# =========================
def _sleep_backoff(i: int) -> None:
    time.sleep((0.6 * (i + 1)) + random.random() * 0.25)


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

            try:
                data = r.json()
            except Exception:
                raise RuntimeError(f"Telegram non-JSON (HTTP {r.status_code}): {r.text[:200]}")

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


def tg_getme_check_forever() -> None:
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is missing (set it in Render Environment).")
        return
    while True:
        try:
            data = tg_request("getMe", is_post=False, params=None, retries=3)
            me = data.get("result") or {}
            log.info("Telegram getMe OK: @%s (id=%s)", me.get("username"), me.get("id"))
            return
        except Exception as e:
            log.error("Telegram getMe failed (will retry): %r", e)
            time.sleep(5)


def send_message(chat_id: int, text: str, reply_markup=None) -> Optional[int]:
    if text is None:
        text = ""
    chunks = [text[i : i + MAX_TEXT_LEN] for i in range(0, len(text), MAX_TEXT_LEN)] or [""]
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
# UI
# =========================
def _badge(ok: bool) -> str:
    return "✅" if ok else "🚫"


def kb_main(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    game = p.get("game", "auto")
    persona = p.get("persona", "spicy")
    talk = p.get("verbosity", "normal")
    mem_on = (p.get("memory", "on") == "on")
    return {
        "inline_keyboard": [
            [
                {"text": f"🎮 {game.upper()}", "callback_data": "menu:game"},
                {"text": f"😈 {persona}", "callback_data": "menu:persona"},
                {"text": f"🗣 {talk}", "callback_data": "menu:talk"},
            ],
            [
                {"text": f"{_badge(mem_on)} Память", "callback_data": "toggle:memory"},
                {"text": "👤 Профиль", "callback_data": "action:profile"},
                {"text": "🕶 UI", "callback_data": "action:ui"},
            ],
            [
                {"text": "💪 Drills", "callback_data": "action:drills"},
                {"text": "📅 Plan", "callback_data": "action:plan"},
                {"text": "⚙️ Settings", "callback_data": "action:settings"},
            ],
            [
                {"text": "📼 VOD", "callback_data": "action:vod"},
                {"text": "📚 Статьи", "callback_data": "action:kb"},
                {"text": "❓ Help", "callback_data": "action:help"},
            ],
            [{"text": "🧽 Clear memory", "callback_data": "action:reset_mem"}],
        ]
    }


def kb_game(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    cur = p.get("game", "auto")

    def b(key, label):
        mark = "✅ " if cur == key else ""
        return {"text": f"{mark}{label}", "callback_data": f"set:game:{key}"}

    return {
        "inline_keyboard": [
            [b("auto", "AUTO"), b("warzone", "Warzone"), b("bf6", "BF6"), b("bo7", "BO7")],
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
            [
                {"text": "🎯 Aim", "callback_data": "drill:aim"},
                {"text": "🔫 Recoil", "callback_data": "drill:recoil"},
                {"text": "🕹 Move", "callback_data": "drill:movement"},
            ],
            [{"text": "⬅️ Назад", "callback_data": "action:menu"}],
        ]
    }


def kb_kb(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui", "show") == "hide":
        return None
    return {
        "inline_keyboard": [
            [{"text": "🔎 Как искать", "callback_data": "kb:help"}, {"text": "⭐ Топ по игре", "callback_data": "kb:top"}],
            [{"text": "⬅️ Назад", "callback_data": "action:menu"}],
        ]
    }


def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    g = p.get("game", "auto")
    mem = p.get("memory", "on")
    ai = "ON" if openai_client else "OFF"
    return (
        "🌑 FPS Coach Bot (clean)\n"
        f"🎮 {g.upper()}  |  😈 {p.get('persona')}  |  🗣 {p.get('verbosity')}  |  🧠 {mem.upper()}  |  🤖 AI {ai}\n\n"
        "Напиши ситуацию одной сценой:\n"
        "• где был • кто первый увидел • на чём умер • что хотел сделать\n\n"
        "Или жми кнопки 👇"
    )


def help_text() -> str:
    return (
        "❓ Как пользоваться\n"
        "Пиши одну ситуацию — я дам диагноз, 2 действия и дрилл.\n\n"
        "Команды:\n"
        "/start /status /profile\n"
        "/kb_search <слово>\n"
        "/kb_show <id>\n"
        "/reset (полный сброс)\n"
    )


def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    facts = USER_FACTS.get(chat_id, {})
    notes = COACH_NOTES.get(chat_id, "").strip()
    lines = [
        "👤 Профиль",
        f"Игра: {p.get('game','auto').upper()}",
        f"Persona: {p.get('persona')}",
        f"Talk: {p.get('verbosity')}",
        f"Память: {p.get('memory','on').upper()}",
        f"История: {len(USER_MEMORY.get(chat_id, []))} сообщений",
        f"AI: {'ON' if openai_client else 'OFF'}",
    ]
    if facts:
        extras = []
        if facts.get("platform"):
            extras.append(f"platform={facts['platform']}")
        if facts.get("sens"):
            extras.append(f"sens={facts['sens']}")
        if facts.get("fov"):
            extras.append(f"fov={facts['fov']}")
        if extras:
            lines.append("Факты: " + ", ".join(extras))
    if notes:
        lines.append("Заметки коуча: " + notes)
    return "\n".join(lines)


def status_text() -> str:
    return (
        "🧾 Status\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"DATA_DIR: {DATA_DIR}\n"
        f"STATE_PATH: {STATE_PATH}\n"
        f"OFFSET_PATH: {OFFSET_PATH}\n"
        f"ARTICLES: {len(ARTICLES)}\n"
        f"AI: {'ON' if openai_client else 'OFF'}\n\n"
        "Если Conflict 409 — у тебя 2 инстанса или второй сервис делает getUpdates.\n"
    )


# =========================
# Animation
# =========================
def typing_loop(chat_id: int, stop_event: threading.Event, interval: float = 4.0) -> None:
    while not stop_event.is_set():
        try:
            send_chat_action(chat_id, "typing")
        except Exception:
            pass
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
# OpenAI helpers
# =========================
def _openai_create(messages: List[Dict[str, str]], max_tokens: int, regen: bool = False):
    # Чуть больше разнообразия, чтобы не было “под копирку”
    temp = 0.95 if not regen else 0.99
    pres = 0.80 if not regen else 0.95
    freq = 0.55 if not regen else 0.70

    kwargs = dict(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=temp,
        presence_penalty=pres,
        frequency_penalty=freq,
    )

    # Совместимость со старыми/новыми версиями SDK
    try:
        return openai_client.chat.completions.create(**kwargs, max_completion_tokens=max_tokens)
    except TypeError:
        return openai_client.chat.completions.create(**kwargs, max_tokens=max_tokens)


def enforce_4_blocks(text: str) -> str:
    t = (text or "").replace("\r", "").strip()
    t = re.sub(r"(?m)^\s*\d+\)\s*", "", t)
    t = re.sub(r"(?m)^\s*\d+\.\s*", "", t)

    needed = ["🎯", "✅", "🧪", "😈"]
    if all(x in t for x in needed):
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        t = re.sub(r"(?im)^\s*🎯.*$", "🎯 Диагноз", t)
        t = re.sub(r"(?im)^\s*✅.*$", "✅ Что делать", t)
        t = re.sub(r"(?im)^\s*🧪.*$", "🧪 Дрилл", t)
        t = re.sub(r"(?im)^\s*😈.*$", "😈 Панчик/мотивация", t)
        return t

    sents = [x.strip() for x in re.split(r"[.!?\n]+", t) if x.strip()]
    diag = sents[0] if sents else "Ты действуешь без плана и отдаёшь инициативу."
    do1 = sents[1] if len(sents) > 1 else "Сначала инфо, потом движение."
    do2 = sents[2] if len(sents) > 2 else "После контакта — смена угла."
    drill = "5–10 минут: 3×2 минуты один микро-скилл + 1 минута честного разбора."
    punch = "Скилл — это привычка. 😈"
    return (
        "🎯 Диагноз\n"
        f"{diag}\n\n"
        "✅ Что делать\n"
        f"Сейчас — {do1}\n"
        f"Дальше — {do2}\n\n"
        "🧪 Дрилл\n"
        f"{drill}\n\n"
        "😈 Панчик/мотивация\n"
        f"{punch}"
    )


def build_messages(chat_id: int, user_text: str, regen: bool = False) -> List[Dict[str, str]]:
    p = ensure_profile(chat_id)
    game = resolve_game(chat_id, user_text)
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    last_focus = p.get("last_focus") or ""
    focus = random.choice(FOCUSES)
    if last_focus and len(FOCUSES) > 1:
        for _ in range(6):
            if focus[0] != last_focus:
                break
            focus = random.choice(FOCUSES)
    p["last_focus"] = focus[0]

    micro = random.choice(MICRO_CHALLENGES)

    facts = USER_FACTS.get(chat_id, {})
    facts_line = ""
    if facts:
        parts = []
        if facts.get("platform"):
            parts.append(f"platform={facts['platform']}")
        if facts.get("sens"):
            parts.append(f"sens={facts['sens']}")
        if facts.get("fov"):
            parts.append(f"fov={facts['fov']}")
        if parts:
            facts_line = "ФАКТЫ ИГРОКА: " + ", ".join(parts)

    notes = COACH_NOTES.get(chat_id, "").strip()
    notes_line = f"ЗАМЕТКИ КОУЧА: {notes}" if notes else ""

    kb_steps = kb_relevant_steps(user_text, game, limit_steps=3)
    kb_hint = ""
    if kb_steps:
        kb_hint = (
            "Если уместно, аккуратно встрои 1–3 пункта ниже в '✅ Что делать' или '🧪 Дрилл' (не упоминай источник):\n"
            + "\n".join([f"- {x}" for x in kb_steps])
        )

    prev_answer = (p.get("last_answer") or "")[:1200]

    anti_repeat_lines = [
        "Анти-повтор:",
        "- Не используй канцелярит.",
        "- Меняй ритм, глаголы и формулировки.",
        "- Не повторяй прошлый ответ.",
    ]
    if prev_answer:
        anti_repeat_lines += ["", "Прошлый ответ (не повторять):", prev_answer]
    if regen:
        anti_repeat_lines += ["", "Усиление: полностью поменяй 2 действия и дрилл."]

    coach_frame_lines = [
        "Не выдумывай патчи/мету.",
        "Запрещено: читы/хаки/обход античита.",
        f"Игра: {GAME_KB[game]['name']}.",
        f"ФОКУС ДНЯ: {focus[0]} — {focus[1]}.",
        micro,
    ]
    if facts_line:
        coach_frame_lines.append(facts_line)
    if notes_line:
        coach_frame_lines.append(notes_line)
    if kb_hint:
        coach_frame_lines.append(kb_hint)

    coach_frame_lines.append("Важно: в '✅ Что делать' ровно 2 строки: 'Сейчас — ...' и 'Дальше — ...'.")

    coach_frame = "\n".join([x for x in coach_frame_lines if x]).strip()
    anti_repeat = "\n".join([x for x in anti_repeat_lines if x is not None]).strip()

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
        {"role": "system", "content": coach_frame},
        {"role": "system", "content": anti_repeat},
    ]

    if p.get("memory", "on") == "on":
        messages.extend(USER_MEMORY.get(chat_id, []))

    messages.append({"role": "user", "content": f"[GAME={game}] {user_text}"})
    return messages


def ai_off_reply(chat_id: int, user_text: str) -> str:
    game = resolve_game(chat_id, user_text)
    micro = random.choice(MICRO_CHALLENGES)
    return enforce_4_blocks(
        "🎯 Диагноз\n"
        "AI сейчас выключен, но база коучинга всё равно работает.\n\n"
        "✅ Что делать\n"
        "Сейчас — опиши одну смерть (где был / кто первый увидел / чем умер).\n"
        f"Дальше — скажи дистанцию и игру: {GAME_KB[game]['name']}.\n\n"
        "🧪 Дрилл\n"
        f"5–7 минут: 3 контакта → после каждого: «почему умер». {micro}\n\n"
        "😈 Панчик/мотивация\n"
        "Ключ — это ускорение. Но привычка — это сила. 😈"
    )


def openai_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)

    if is_cheat_request(user_text):
        return enforce_4_blocks(
            "🎯 Диагноз\n"
            "Читы = бан + ноль прогресса.\n\n"
            "✅ Что делать\n"
            "Сейчас — скажи, где сыпешься: дуэли / инфо / пози.\n"
            "Дальше — сделаем план без магии.\n\n"
            "🧪 Дрилл\n"
            "7 минут: 3×2 минуты микро-скилл + 1 минута разбор.\n\n"
            "😈 Панчик/мотивация\n"
            "Мы качаем руки, не софт. 😈"
        )

    if is_smalltalk(user_text) or is_low_info(user_text):
        return enforce_4_blocks(
            "🎯 Диагноз\n"
            "Пока мало деталей — если начну умничать, будет коуч-гороскоп.\n\n"
            "✅ Что делать\n"
            "Сейчас — опиши одну смерть: где был, кто первый увидел, чем закончилось.\n"
            "Дальше — дистанция (близко/средне/далеко) и игра (WZ/BF6/BO7).\n\n"
            "🧪 Дрилл\n"
            "5 минут: 3 контакта → после каждого: «что сделал лишнего».\n\n"
            "😈 Панчик/мотивация\n"
            "Дай факты — и будет план. 😈"
        )

    if not openai_client:
        return ai_off_reply(chat_id, user_text)

    messages = build_messages(chat_id, user_text, regen=False)
    max_out = 900 if p.get("verbosity") == "talkative" else 650

    last = p.get("last_answer", "")
    for attempt in range(2):
        try:
            resp = _openai_create(messages, max_out, regen=(attempt == 1))
            out = (resp.choices[0].message.content or "").strip()
            out = enforce_4_blocks(out)

            sim = similarity(out, last)
            if attempt == 0 and sim >= 0.35:
                messages = build_messages(chat_id, user_text, regen=True)
                continue
            return out
        except Exception:
            log.exception("OpenAI failed -> fallback to AI OFF reply")
            return ai_off_reply(chat_id, user_text)


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

        extract_facts(chat_id, t)
        update_coach_notes(chat_id, t)

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
            COACH_NOTES.pop(chat_id, None)
            ensure_profile(chat_id)
            save_state()
            send_message(chat_id, "🧹 Полный сброс (профиль/память/факты/заметки).", reply_markup=kb_main(chat_id))
            return

        if t.startswith("/kb_search"):
            q = t[len("/kb_search") :].strip()
            game = resolve_game(chat_id, t)
            res = kb_search(q, game=game, limit=7)
            if not res:
                send_message(chat_id, "Не нашёл. Пример: /kb_search тайминг", reply_markup=kb_main(chat_id))
                return
            lines = ["🔎 Нашёл статьи:"]
            for a in res:
                lines.append(f"• {a.get('id')} — {a.get('title')}")
            lines.append("\nОткрыть: /kb_show <id>")
            send_message(chat_id, "\n".join(lines), reply_markup=kb_main(chat_id))
            return

        if t.startswith("/kb_show"):
            art_id = t[len("/kb_show") :].strip()
            a = kb_get(art_id)
            if not a:
                send_message(chat_id, "Не нашёл такой id. Сначала: /kb_search <слово>", reply_markup=kb_main(chat_id))
                return
            send_message(chat_id, kb_format_article(a), reply_markup=kb_main(chat_id))
            return

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

        reply = enforce_4_blocks(reply)
        update_memory(chat_id, "assistant", reply)

        p["last_answer"] = reply[:2000]
        save_state()

        if tmp_id:
            try:
                edit_message(chat_id, tmp_id, reply, reply_markup=kb_main(chat_id))
            except Exception:
                send_message(chat_id, reply, reply_markup=kb_main(chat_id))
        else:
            send_message(chat_id, reply, reply_markup=kb_main(chat_id))

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

        if data == "action:menu":
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))
        elif data == "menu:game":
            edit_message(chat_id, message_id, "🎮 Выбери игру:", reply_markup=kb_game(chat_id))
        elif data == "menu:persona":
            edit_message(chat_id, message_id, "😈 Выбери Persona:", reply_markup=kb_persona(chat_id))
        elif data == "menu:talk":
            edit_message(chat_id, message_id, "🗣 Выбери Talk:", reply_markup=kb_talk(chat_id))
        elif data == "toggle:memory":
            p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
            if p["memory"] == "off":
                clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))
        elif data.startswith("set:game:"):
            g = data.split(":", 2)[2]
            if g in ("auto",) + GAMES:
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
            g = resolve_game(chat_id, "")
            edit_message(chat_id, message_id, GAME_KB[g]["settings"], reply_markup=kb_main(chat_id))
        elif data == "action:plan":
            g = resolve_game(chat_id, "")
            edit_message(chat_id, message_id, GAME_KB[g]["plan"], reply_markup=kb_main(chat_id))
        elif data == "action:vod":
            g = resolve_game(chat_id, "")
            edit_message(chat_id, message_id, GAME_KB[g]["vod"], reply_markup=kb_main(chat_id))
        elif data == "action:drills":
            edit_message(chat_id, message_id, "💪 Выбери дрилл:", reply_markup=kb_drills(chat_id))
        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            g = resolve_game(chat_id, "")
            txt = GAME_KB[g]["drills"].get(kind, "Доступно: aim/recoil/movement")
            edit_message(chat_id, message_id, txt, reply_markup=kb_drills(chat_id))
        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=kb_main(chat_id))
        elif data == "action:reset_mem":
            clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧽 Память очищена (профиль оставил).", reply_markup=kb_main(chat_id))
        elif data == "action:kb":
            edit_message(chat_id, message_id, "📚 Статьи: что делаем?", reply_markup=kb_kb(chat_id))
        elif data == "kb:help":
            edit_message(
                chat_id,
                message_id,
                "🔎 Поиск статей:\n/kb_search <слово>\nОткрыть:\n/kb_show <id>",
                reply_markup=kb_kb(chat_id),
            )
        elif data == "kb:top":
            g = resolve_game(chat_id, "")
            lst = [a for a in ARTICLES if (a.get("game") == g and (a.get("lang", "ru") == "ru"))][:7]
            if not lst:
                txt = "Пока нет статей под эту игру. Добавь в kb_articles.json."
            else:
                lines = [f"⭐ Топ по {GAME_KB[g]['name']}:"]
                for a in lst:
                    lines.append(f"• {a.get('id')} — {a.get('title')}")
                lines.append("\nОткрыть: /kb_show <id>")
                txt = "\n".join(lines)
            edit_message(chat_id, message_id, txt, reply_markup=kb_kb(chat_id))
        elif data == "action:help":
            edit_message(chat_id, message_id, help_text(), reply_markup=kb_main(chat_id))
        elif data == "action:ui":
            p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
            save_state()
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))
        else:
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))
    finally:
        answer_callback(cb_id)


# =========================
# Polling loop
# =========================
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
                        send_message(chat_id, "Ошибка 😅 Попробуй ещё раз.", reply_markup=kb_main(chat_id))
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

        stop_autosave = threading.Event()
        threading.Thread(target=autosave_loop, args=(stop_autosave, 60), daemon=True).start()

        threading.Thread(target=run_telegram_bot_forever, daemon=True).start()

        run_http_server()

    except Exception:
        log.error("FATAL STARTUP ERROR:\n%s", traceback.format_exc())
        while True:
            time.sleep(60)
