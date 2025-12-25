# -*- coding: utf-8 -*-
"""
FPS Coach Bot — PUBLIC (Render + long polling) — v13

Что улучшено:
- Простое /start меню (коротко и понятно)
- "Умная память": профиль + краткое резюме (summary) + последние диалоги
- Меньше ответов "под копирку": сценарии + ротация фокусов + анти-повтор + similarity retry
- KB (статьи) для BO7/зомби и т.п.: /kb_search, /kb_show, режим /mode guide
- Надёжность на Render: health endpoint, deleteWebhook, 409 conflict backoff, авто-restart polling
- Опциональная персистентность на диске: DATA_DIR (Render Disk) или /tmp

ENV (Render):
- TELEGRAM_BOT_TOKEN  (required)
- OPENAI_API_KEY      (required)
- OPENAI_MODEL        (default: gpt-4o-mini)
- OPENAI_BASE_URL     (default: https://api.openai.com/v1)

Optional:
- DATA_DIR=/var/data  (если подключён Render Disk) иначе /tmp
- MEMORY_MAX_TURNS=10
- SUMMARY_MAX_CHARS=900
"""

import os
import re
import time
import json
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
log = logging.getLogger("fps_coach_public_v13")


# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

DATA_DIR = os.getenv("DATA_DIR", "/tmp").strip()
STATE_PATH = os.path.join(DATA_DIR, "fps_coach_state.json")
KB_PATH = os.getenv("KB_PATH", "kb_articles.json").strip()

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
TG_LONGPOLL_TIMEOUT = int(os.getenv("TG_LONGPOLL_TIMEOUT", "50"))
TG_RETRIES = int(os.getenv("TG_RETRIES", "5"))

PULSE_MIN_SECONDS = float(os.getenv("PULSE_MIN_SECONDS", "1.25"))
MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.35"))

CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", "900"))

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
SESSION.headers.update({"User-Agent": "render-fps-coach-public/13.0"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=30, pool_maxsize=30))


# =========================
# State (profiles + memory + summary + kb cache)
# =========================
USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
USER_SUMMARY: Dict[int, str] = {}
LAST_MSG_TS: Dict[int, float] = {}
CHAT_LOCKS: Dict[int, threading.Lock] = {}
LAST_TEMPLATE: Dict[int, str] = {}
LAST_KB_RESULTS: Dict[int, List[Dict[str, Any]]] = {}

_state_lock = threading.Lock()


def _get_lock(chat_id: int) -> threading.Lock:
    if chat_id not in CHAT_LOCKS:
        CHAT_LOCKS[chat_id] = threading.Lock()
    return CHAT_LOCKS[chat_id]


def load_state() -> None:
    global USER_PROFILE, USER_MEMORY, USER_SUMMARY
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            USER_PROFILE = {int(k): v for k, v in (data.get("profiles") or {}).items()}
            USER_MEMORY = {int(k): v for k, v in (data.get("memory") or {}).items()}
            USER_SUMMARY = {int(k): v for k, v in (data.get("summary") or {}).items()}
            log.info("State loaded: profiles=%d memory=%d summary=%d (%s)",
                     len(USER_PROFILE), len(USER_MEMORY), len(USER_SUMMARY), STATE_PATH)
    except Exception as e:
        log.warning("State load failed: %r", e)


def save_state() -> None:
    try:
        with _state_lock:
            data = {
                "profiles": {str(k): v for k, v in USER_PROFILE.items()},
                "memory": {str(k): v for k, v in USER_MEMORY.items()},
                "summary": {str(k): v for k, v in USER_SUMMARY.items()},
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


# =========================
# Knowledge base (kb_articles.json)
# =========================
KB: List[Dict[str, Any]] = []


def load_kb() -> None:
    global KB
    try:
        if os.path.exists(KB_PATH):
            with open(KB_PATH, "r", encoding="utf-8") as f:
                KB = json.load(f)
            if not isinstance(KB, list):
                KB = []
            log.info("KB loaded: %d articles (%s)", len(KB), KB_PATH)
        else:
            KB = []
            log.warning("KB not found: %s", KB_PATH)
    except Exception as e:
        KB = []
        log.warning("KB load failed: %r", e)


load_kb()


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-zа-я0-9ё\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def kb_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    q = _norm(query)
    if not q or not KB:
        return []
    q_terms = [t for t in q.split() if len(t) >= 3]
    if not q_terms:
        return []

    scored = []
    for art in KB:
        title = _norm(art.get("title", ""))
        text = _norm(art.get("text", ""))
        tags = " ".join(art.get("tags") or [])
        tags = _norm(tags)
        hay = f"{title} {tags} {text}"
        score = 0
        for t in q_terms:
            if t in title:
                score += 6
            if t in tags:
                score += 4
            if t in hay:
                score += 1
        if score > 0:
            scored.append((score, art))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:limit]]


def kb_get_by_index(results: List[Dict[str, Any]], idx: int) -> Optional[Dict[str, Any]]:
    if not results:
        return None
    if idx < 1 or idx > len(results):
        return None
    return results[idx - 1]


# =========================
# Games / detection
# =========================
GAMES = ("warzone", "bf6", "bo7")
GAME_NAMES = {
    "warzone": "Call of Duty: Warzone",
    "bf6": "Battlefield 6 (BF6)",
    "bo7": "Call of Duty: Black Ops (BO7)",
}

_GAME_PATTERNS = {
    "warzone": re.compile(r"\b(warzone|wz|варзон|варзоне|cod|код|бр|battle\s*royale|ранк|рейтин)\b", re.I),
    "bf6": re.compile(r"\b(bf6|battlefield|батлфилд|battle\s*field)\b", re.I),
    "bo7": re.compile(r"\b(bo7|black\s*ops|блэк\s*опс|zombie|зомби|зомби-режим)\b", re.I),
}


def detect_game(text: str) -> Optional[str]:
    t = text.strip()
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
# "Умная память" (профиль + summary)
# =========================
def ensure_profile(chat_id: int) -> Dict[str, Any]:
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "persona": "spicy",     # spicy/chill/pro
        "verbosity": "normal",  # short/normal/talkative
        "mode": "auto",         # auto/coach/tactic/guide
        "squad": "unknown",     # solo/duo/trio/squad/unknown
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


def _extract_profile_hints(p: Dict[str, Any], text: str) -> None:
    t = _norm(text)

    # squad size
    if re.search(r"\b(соло|solo)\b", t):
        p["squad"] = "solo"
    elif re.search(r"\b(дуо|duo|2x2|2х2)\b", t):
        p["squad"] = "duo"
    elif re.search(r"\b(трио|trio|3x3|3х3)\b", t):
        p["squad"] = "trio"
    elif re.search(r"\b(сквад|squad|4x4|4х4)\b", t):
        p["squad"] = "squad"

    # game auto-detect
    g = detect_game(text)
    if g in GAMES:
        p["game"] = g


def summarize_memory(chat_id: int) -> None:
    """
    Сжимает длинный контекст в короткую "память-заметку".
    Делается редко (когда диалог длинный), и хранится отдельно от последних сообщений.
    """
    mem = USER_MEMORY.get(chat_id, [])
    if len(mem) < MEMORY_MAX_TURNS * 2:
        return

    # берём последние ~12 сообщений и делаем короткое резюме
    recent = mem[-12:]
    prev_summary = USER_SUMMARY.get(chat_id, "")

    prompt = (
        "Сделай КОРОТКОЕ резюме (до 6 строк) о пользователе и его стиле игры.\n"
        "Запомни только полезное для будущих советов: игра, режим, тип ошибок, предпочтения, цели.\n"
        "Без воды. Без персональных данных.\n"
        "Пиши по-русски.\n"
    )
    if prev_summary:
        prompt += f"\nТекущее резюме:\n{prev_summary}\n"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Диалог:\n" + "\n".join([f"{m['role']}: {m['content']}" for m in recent])}
    ]

    try:
        r = _openai_create(messages, max_tokens=220, temperature=0.3, presence=0.0, frequency=0.0)
        s = (r.choices[0].message.content or "").strip()
        s = s[:SUMMARY_MAX_CHARS]
        if s:
            USER_SUMMARY[chat_id] = s
            # после резюме можно чистить старые сообщения сильнее
            USER_MEMORY[chat_id] = mem[-(MEMORY_MAX_TURNS * 2):]
    except Exception:
        # резюме — не критично
        pass


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


def send_message(chat_id: int, text: str) -> Optional[int]:
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
    last_msg_id = None
    for ch in chunks:
        res = tg_request("sendMessage", payload={"chat_id": chat_id, "text": ch}, is_post=True)
        last_msg_id = res.get("result", {}).get("message_id")
    return last_msg_id


def edit_message(chat_id: int, message_id: int, text: str) -> None:
    tg_request("editMessageText", payload={"chat_id": chat_id, "message_id": message_id, "text": text}, is_post=True)


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
# UX: typing animation
# =========================
THINKING_LINES = [
    "🧠 Думаю… сейчас будет жарко 😈",
    "⌛ Секунду… раскладываю по полочкам 🧩",
    "🎮 Коуч на связи. Сейчас настроим 💪",
    "🌑 Анализирую… не моргай 😈",
]


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
# Answer engine: scenarios + variety
# =========================
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

SYSTEM_PROMPT_COACH = (
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

SYSTEM_PROMPT_TACTIC = (
    "Ты тактический FPS-коуч. Пиши по-русски.\n"
    "Дай конкретный план действий, как в боевой памятке: шаги, утилы, роль в скваде.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
    "Стиль: короткие буллеты, без воды, но умно.\n"
)

SYSTEM_PROMPT_GUIDE = (
    "Ты эксперт по гайдам. Пиши по-русски.\n"
    "Если вопрос про BO7/зомби/пасхалки — используй базу статей (KB) как источник.\n"
    "Если KB не хватает — честно скажи и дай общий план.\n"
    "Не придумывай факты.\n"
)

FOCUSES: List[Tuple[str, str]] = [
    ("позиционка", "высота, укрытия, линии обзора, угол"),
    ("тайминг", "вход/выход из файта, репик, пауза"),
    ("инфо", "звук, пинги, радар, чтение зоны"),
    ("дуэль", "пик, префайр, first-shot, микрокоррекция"),
    ("дисциплина", "ресурсы, ресет, не жадничать"),
    ("плеймейкинг", "фланг, изоляция, давление"),
]

SCENARIOS = {
    "gatekeep": re.compile(r"\b(gatekeep|гейткип|выхожу из зоны|выход из зоны|меня видит сквад|держат край|держат зону)\b", re.I),
    "backstab": re.compile(r"\b(выйду сзади|заход с тыла|зайти сзади|фланг сзади|обход с тыла)\b", re.I),
    "low_to_high": re.compile(r"\b(снизу наверх|пушить снизу|хайграунд|high\s*ground|высоту держат)\b", re.I),
    "ranked": re.compile(r"\b(рейтинг|ранк|ranked|соревноват)\b", re.I),
    "zombies": re.compile(r"\b(зомби|zombies|пасхалк|easter egg|яйцо|astra)\b", re.I),
}


TEMPLATE_BANK = {
    # "как первый бот": больше тактики, утил, ролей — но без ломания формата в coach
    "gatekeep": [
        "Делай 2 дыма: один под себя, второй — на разрыв линии видимости. Ротация ступеньками от укрытия к укрытию.",
        "Сначала сбей им фокус: страйк/кластер/мортира по их углам, и только потом двигайся. Если нет — фейки + смена угла.",
        "Роли: один даёт дым/подавление, второй режет угол и ищет изоляцию 1v1. Не ломись всей пачкой в один прострел."
    ],
    "backstab": [
        "Тайминг: заходи, когда они заняты стрельбой/перезарядом. Не открывай файт первым — забери 'последнего'.",
        "Маршрут: избегай длинных прострелов, иди через укрытия/лестницы/окна. Шаг рядом с ними, спринт — только в тени.",
        "После нока: смена позиции или добив + отход. Не лутай в шуме."
    ],
    "low_to_high": [
        "Не лезь по прямой. Сделай 'ступеньки': камни/коробки/крыши. 2 дыма и заход под разный угол (45°).",
        "Сбей их хедглич: флеш/стан в точку, затем пуш на окно после 'плати' по ним.",
        "Асэндер/лестница — только после нока или когда их выдавили утилой."
    ],
    "ranked": [
        "Твой ранк не растёт не из-за аима, а из-за решений: когда не файтиться и когда отступить.",
        "Вводи правило: 1 файт = 1 цель. Нок → закреп → ресет. Никаких 'дожмём' без брони.",
        "Сделай микро-рутинку: скан инфы каждые 5–7 сек (карта/зона/углы)."
    ],
    "zombies": [
        "Сначала уточним карту/пасхалку (название) и где ты застрял (шаг/предмет). Потом дам точный маршрут.",
        "Если ты про Astra Malorum — ищи в KB и дам пошагово, без выдумок.",
        "Фокус: выживаемость → сбор предметов → выполнение шагов. Не прыгай между задачами."
    ]
}


def detect_scenario(text: str) -> Optional[str]:
    for name, rx in SCENARIOS.items():
        if rx.search(text or ""):
            return name
    return None


def _tokenize(s: str) -> List[str]:
    s = _norm(s)
    return [p for p in s.split() if len(p) >= 3]


def too_similar(a: str, b: str, threshold: float = 0.62) -> bool:
    if not a or not b:
        return False
    ta, tb = set(_tokenize(a)), set(_tokenize(b))
    if not ta or not tb:
        return False
    return (len(ta & tb) / max(1, len(ta | tb))) >= threshold


def _openai_create(messages: List[Dict[str, str]], max_tokens: int,
                   temperature: float = 0.9, presence: float = 0.6, frequency: float = 0.35):
    kwargs = dict(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
        presence_penalty=presence,
        frequency_penalty=frequency,
    )
    try:
        return openai_client.chat.completions.create(**kwargs, max_completion_tokens=max_tokens)
    except TypeError:
        return openai_client.chat.completions.create(**kwargs, max_tokens=max_tokens)


def build_messages(chat_id: int, user_text: str, regen: bool = False) -> Tuple[List[Dict[str, str]], str]:
    p = ensure_profile(chat_id)
    _extract_profile_hints(p, user_text)

    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")
    mode = p.get("mode", "auto")
    game = p.get("game", "warzone")

    scenario = detect_scenario(user_text)
    focus = random.choice(FOCUSES)

    # template rotation (avoid same template twice)
    tmpl_list = TEMPLATE_BANK.get(scenario or "", [])
    template = ""
    if tmpl_list:
        prev = LAST_TEMPLATE.get(chat_id, "")
        candidates = [t for t in tmpl_list if t != prev] or tmpl_list
        template = random.choice(candidates)
        LAST_TEMPLATE[chat_id] = template

    last_a = last_assistant_text(chat_id, limit=1400)
    anti_repeat = (
        "ВАЖНО: НЕ повторяй формулировки и советы из прошлого ответа.\n"
        "Если тема похожа — дай ДРУГОЙ угол (другие 2 действия и другой дрилл).\n"
        "Обязательно используй конкретику из сообщения пользователя.\n"
    )
    if last_a:
        anti_repeat += f"\nПРОШЛЫЙ ОТВЕТ (избегай повторов):\n{last_a}\n"
    if regen:
        anti_repeat += "\nАНТИ-ПОВТОР x2: полностью поменяй дрилл и формулировки. Не копируй структуру предложений.\n"

    summary = USER_SUMMARY.get(chat_id, "").strip()
    summary_block = f"Память (кратко):\n{summary}\n" if summary else ""

    focus_line = f"ФОКУС СЕГОДНЯ: {focus[0]} — {focus[1]}."
    game_line = f"Текущая игра: {GAME_NAMES.get(game, game)}."

    # Choose system prompt by mode
    if mode == "guide":
        sys0 = SYSTEM_PROMPT_GUIDE
    elif mode == "tactic":
        sys0 = SYSTEM_PROMPT_TACTIC
    else:
        # auto/coach -> coach format
        sys0 = SYSTEM_PROMPT_COACH

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": sys0},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
        {"role": "system", "content": game_line},
        {"role": "system", "content": focus_line},
        {"role": "system", "content": anti_repeat},
    ]
    if template:
        messages.append({"role": "system", "content": f"Подсказка под сценарий ({scenario}): {template}"})
    if summary_block:
        messages.append({"role": "system", "content": summary_block})
    messages.append({"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"})

    # For guide mode: attach relevant KB excerpts (short, to avoid huge prompts)
    if mode == "guide":
        # Try auto KB search by user_text
        res = kb_search(user_text, limit=3)
        if res:
            # store for /kb_show convenience
            LAST_KB_RESULTS[chat_id] = res
            kb_snips = []
            for i, a in enumerate(res, 1):
                snip = (a.get("text") or "")[:1200]
                kb_snips.append(f"[{i}] {a.get('title','')}\nSOURCE: {a.get('source','')}\n{snip}")
            messages.append({"role": "system", "content": "KB материалы (используй как источник, без выдумок):\n\n" + "\n\n".join(kb_snips)})

    # Recent dialog memory
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    return messages, game


def openai_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    verbosity = p.get("verbosity", "normal")
    mode = p.get("mode", "auto")

    max_out = 760 if verbosity == "talkative" else (560 if verbosity == "normal" else 400)
    prev = last_assistant_text(chat_id, limit=1800)

    for attempt in range(2):
        try:
            messages, game = build_messages(chat_id, user_text, regen=(attempt == 1))

            # parameters tuned by mode
            if mode == "guide":
                temp, pres, freq = 0.4, 0.2, 0.1
            elif mode == "tactic":
                temp, pres, freq = 0.7, 0.5, 0.2
            else:
                temp, pres, freq = 0.9, 0.6, 0.35

            resp = _openai_create(messages, max_tokens=max_out, temperature=temp, presence=pres, frequency=freq)
            out = (resp.choices[0].message.content or "").strip()
            if not out:
                out = "Не получил ответ. Напиши ещё раз 🙌"

            if attempt == 0 and prev and too_similar(out, prev):
                continue  # regenerate once

            # nice header (single line)
            if game in GAME_NAMES:
                out = f"🎮 {GAME_NAMES[game]}\n\n" + out

            return out

        except APIConnectionError:
            if attempt == 0:
                time.sleep(0.8)
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
# Commands / Menu (simple)
# =========================
def help_text() -> str:
    return (
        "🌑 FPS Coach Bot\n"
        "Пиши вопрос/ситуацию — отвечу.\n\n"
        "⚡ Быстро:\n"
        "• /mode auto|coach|tactic|guide\n"
        "• /persona spicy|chill|pro\n"
        "• /talk short|normal|talkative\n"
        "• /game warzone|bf6|bo7\n\n"
        "📚 Статьи (KB):\n"
        "• /kb_search <запрос>\n"
        "• /kb_show <номер>\n\n"
        "🧠 Память:\n"
        "• /profile — что я о тебе помню\n"
        "• /reset — очистить память\n"
    )


def status_text() -> str:
    return (
        "🧾 Status\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"STATE_PATH: {STATE_PATH}\n"
        f"KB_PATH: {KB_PATH} (articles={len(KB)})\n\n"
        "⚠️ Если в логах 'Conflict: getUpdates' — запущено 2 инстанса/сервиса или включён webhook.\n"
        "Решение: Render -> Service -> Settings -> Instances = 1, и убедись что webhook не используется.\n"
        "⚠️ Render Free может 'spin down' без пинга/трафика. Внешний пинг помогает, но 24/7 гарантирует платный план.\n"
    )


def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    s = USER_SUMMARY.get(chat_id, "").strip()
    if not s:
        s = "— пока пусто (я запомню стиль по мере диалога)"
    return (
        "🧠 Профиль\n"
        f"Игра: {GAME_NAMES.get(p.get('game','warzone'), p.get('game'))}\n"
        f"Режим: {p.get('mode','auto')}\n"
        f"Сквад: {p.get('squad','unknown')}\n"
        f"Persona: {p.get('persona','spicy')}\n"
        f"Talk: {p.get('verbosity','normal')}\n\n"
        "Память (кратко):\n"
        f"{s}"
    )


def ai_test() -> str:
    try:
        r = _openai_create([{"role": "user", "content": "Ответь одним словом: OK"}], max_tokens=10,
                           temperature=0.2, presence=0.0, frequency=0.0)
        out = (r.choices[0].message.content or "").strip()
        return f"✅ /ai_test: {out or 'OK'} (model={OPENAI_MODEL})"
    except AuthenticationError:
        return "❌ /ai_test: неверный ключ."
    except APIConnectionError:
        return "⚠️ /ai_test: проблема сети/Render."
    except Exception as e:
        return f"⚠️ /ai_test: {type(e).__name__}"


# =========================
# KB commands
# =========================
def kb_list_text(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "📚 Ничего не нашёл в статьях. Попробуй другой запрос."
    lines = ["📚 Нашёл в статьях:"]
    for i, a in enumerate(results, 1):
        title = a.get("title", "Без названия")
        src = a.get("source", "")
        lines.append(f"{i}) {title}")
        if src:
            lines.append(f"   🔗 {src}")
    lines.append("\nОткрой: /kb_show <номер>")
    return "\n".join(lines)


def kb_show_text(article: Dict[str, Any]) -> str:
    title = article.get("title", "Без названия")
    src = article.get("source", "")
    text = (article.get("text", "") or "").strip()
    if len(text) > 3500:
        text = text[:3500] + "\n\n…(обрезано)"
    out = f"📄 {title}\n"
    if src:
        out += f"Источник: {src}\n\n"
    out += text
    return out


# =========================
# Message handler
# =========================
def handle_message(chat_id: int, text: str) -> None:
    with _get_lock(chat_id):
        if throttle(chat_id):
            return

        p = ensure_profile(chat_id)
        t = (text or "").strip()

        if not t:
            return

        # commands
        if t.startswith("/start"):
            send_message(chat_id, help_text())
            return

        if t.startswith("/status"):
            send_message(chat_id, status_text())
            return

        if t.startswith("/profile"):
            send_message(chat_id, profile_text(chat_id))
            return

        if t.startswith("/ai_test"):
            send_message(chat_id, ai_test())
            return

        if t.startswith("/reset"):
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            USER_SUMMARY.pop(chat_id, None)
            LAST_KB_RESULTS.pop(chat_id, None)
            ensure_profile(chat_id)
            save_state()
            send_message(chat_id, "🧹 Ок, память и профиль очищены.")
            return

        if t.startswith("/persona"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].lower() in ("spicy", "chill", "pro"):
                p["persona"] = parts[1].lower()
                save_state()
                send_message(chat_id, f"✅ Persona = {p['persona']}")
            else:
                send_message(chat_id, "Используй: /persona spicy | chill | pro")
            return

        if t.startswith("/talk"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].lower() in ("short", "normal", "talkative"):
                p["verbosity"] = parts[1].lower()
                save_state()
                send_message(chat_id, f"✅ Talk = {p['verbosity']}")
            else:
                send_message(chat_id, "Используй: /talk short | normal | talkative")
            return

        if t.startswith("/game"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].lower() in GAMES:
                p["game"] = parts[1].lower()
                save_state()
                send_message(chat_id, f"✅ Игра = {GAME_NAMES[p['game']]}")
            else:
                send_message(chat_id, "Используй: /game warzone | bf6 | bo7")
            return

        if t.startswith("/mode"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].lower() in ("auto", "coach", "tactic", "guide"):
                p["mode"] = parts[1].lower()
                save_state()
                send_message(chat_id, f"✅ Mode = {p['mode']}")
            else:
                send_message(chat_id, "Используй: /mode auto | coach | tactic | guide")
            return

        if t.startswith("/kb_search"):
            q = t[len("/kb_search"):].strip()
            if not q:
                send_message(chat_id, "Напиши так: /kb_search astra malorum")
                return
            res = kb_search(q, limit=6)
            LAST_KB_RESULTS[chat_id] = res
            send_message(chat_id, kb_list_text(res))
            return

        if t.startswith("/kb_show"):
            arg = t[len("/kb_show"):].strip()
            try:
                idx = int(arg)
            except Exception:
                send_message(chat_id, "Напиши так: /kb_show 1")
                return
            art = kb_get_by_index(LAST_KB_RESULTS.get(chat_id, []), idx)
            if not art:
                send_message(chat_id, "Нет такого номера. Сначала сделай /kb_search <запрос>.")
                return
            send_message(chat_id, kb_show_text(art))
            return

        # non-command: update hints + memory
        _extract_profile_hints(p, t)
        update_memory(chat_id, "user", t)

        # background typing
        tmp_id = send_message(chat_id, random.choice(THINKING_LINES))
        stop = threading.Event()
        threading.Thread(target=typing_loop, args=(chat_id, stop), daemon=True).start()
        if tmp_id:
            threading.Thread(target=pulse_edit_loop, args=(chat_id, tmp_id, stop, "⌛ Думаю"), daemon=True).start()

        try:
            reply = openai_reply(chat_id, t)
        finally:
            stop.set()

        update_memory(chat_id, "assistant", reply)

        # compress memory occasionally
        summarize_memory(chat_id)
        save_state()

        if tmp_id:
            try:
                edit_message(chat_id, tmp_id, reply)
            except Exception:
                send_message(chat_id, reply)
        else:
            send_message(chat_id, reply)


# =========================
# Polling loop (with restart)
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

                msg = upd.get("message") or upd.get("edited_message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue

                try:
                    handle_message(chat_id, text)
                except Exception:
                    log.exception("Message handling error")
                    send_message(chat_id, "Ошибка 😅 Попробуй ещё раз.")

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
        if self.path in ("/", "/healthz"):
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
