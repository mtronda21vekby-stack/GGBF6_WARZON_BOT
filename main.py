# -*- coding: utf-8 -*-
"""
FPS Coach Bot — PUBLIC AI v8 (Render + long polling)

Что улучшено по сравнению с v7:
- Стабильнее 24/7 на Render: бесконечный watchdog перезапуска polling + health endpoint
- Жёстче обработка ошибок Telegram: 429 retry_after, JSON/non-JSON, backoff, таймауты
- Пер-чат "очередь": один запрос к AI за раз на чат (lock), чтобы не ломалось при спаме
- Авто-определение игры (Warzone/BF6/BO7 + Zombies)
- Меньше одинаковых ответов: смена фокуса, анти-повтор + similarity retry, перефразируй слова юзера
- База статей (KB): можно хранить краткие конспекты (без кнопок)
  * /kb_list, /kb_clear, /kb_reload
  * /kb_add <url> (по умолчанию разрешён только rutab.net; можно расширить через ALLOWED_KB_DOMAINS)
  * /kb_on, /kb_off (включить/выключить подсказки из KB в промпт)
  * /kb_show <id> (покажет конспект)
- Опциональная персистентность: DATA_DIR (лучше подключить Render Disk)

ВАЖНО ПРО 24/7:
- На бесплатных/спящих тарифах Render сервис может "усыпляться". Для 24/7 обычно нужен платный инстанс
  или тип сервиса "Background Worker". Код максимально устойчивый, но хостинг тоже важен.

ENV (Render -> Environment):
- TELEGRAM_BOT_TOKEN   (обязательно)
- OPENAI_API_KEY       (обязательно)
- OPENAI_MODEL         (опц., default: gpt-4o-mini)
- OPENAI_BASE_URL      (опц., default: https://api.openai.com/v1)
- DATA_DIR             (опц., default: /tmp; для Render Disk например /var/data)

Tuning:
- MEMORY_MAX_TURNS=10
- MIN_SECONDS_BETWEEN_MSG=0.35
- TG_LONGPOLL_TIMEOUT=50
- TG_RETRIES=6
- HTTP_TIMEOUT=25
- PULSE_MIN_SECONDS=1.25
- CONFLICT_BACKOFF_MIN=12
- CONFLICT_BACKOFF_MAX=30
- ALLOWED_KB_DOMAINS=rutab.net   (CSV)
- KB_MAX_ARTICLES=50
"""

import os
import re
import time
import json
import random
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Tuple, Optional
from urllib.parse import urlparse

import requests
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError


# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_public_v8")


# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

DATA_DIR = os.getenv("DATA_DIR", "/tmp").strip()
STATE_PATH = os.path.join(DATA_DIR, "fps_coach_state.json")
KB_PATH = os.path.join(DATA_DIR, "fps_coach_kb.json")

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
TG_LONGPOLL_TIMEOUT = int(os.getenv("TG_LONGPOLL_TIMEOUT", "50"))
TG_RETRIES = int(os.getenv("TG_RETRIES", "6"))

PULSE_MIN_SECONDS = float(os.getenv("PULSE_MIN_SECONDS", "1.25"))
MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.35"))

CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))
KB_MAX_ARTICLES = int(os.getenv("KB_MAX_ARTICLES", "50"))

ALLOWED_KB_DOMAINS = [d.strip().lower() for d in os.getenv("ALLOWED_KB_DOMAINS", "rutab.net").split(",") if d.strip()]

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
    max_retries=0,  # retry ourselves
)


# =========================
# Requests session
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-public/8.0"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))


# =========================
# State
# =========================
USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
LAST_MSG_TS: Dict[int, float] = {}

CHAT_LOCKS: Dict[int, threading.Lock] = {}
_state_lock = threading.Lock()


# =========================
# KB state (article summaries)
# =========================
KB: Dict[str, Any] = {
    "version": 1,
    "articles": []  # list[{id, title, url, tags[], game, summary}]
}


# =========================
# Knowledge / defaults
# =========================
GAMES = ("warzone", "bf6", "bo7")
GAME_NAMES = {
    "warzone": "Call of Duty: Warzone",
    "bf6": "Battlefield 6 (BF6)",
    "bo7": "Call of Duty: Black Ops (BO7)",
}

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
# Locks
# =========================
def _get_lock(chat_id: int) -> threading.Lock:
    if chat_id not in CHAT_LOCKS:
        CHAT_LOCKS[chat_id] = threading.Lock()
    return CHAT_LOCKS[chat_id]


# =========================
# Persistence
# =========================
def load_state() -> None:
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


def save_state() -> None:
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


def autosave_loop(stop: threading.Event, interval_s: int = 60) -> None:
    while not stop.is_set():
        stop.wait(interval_s)
        if stop.is_set():
            break
        save_state()
        save_kb()


def load_kb() -> None:
    global KB
    try:
        if os.path.exists(KB_PATH):
            with open(KB_PATH, "r", encoding="utf-8") as f:
                KB = json.load(f)
            if "articles" not in KB:
                KB["articles"] = []
            log.info("KB loaded: %d articles (%s)", len(KB["articles"]), KB_PATH)
    except Exception as e:
        log.warning("KB load failed: %r", e)


def save_kb() -> None:
    try:
        with _state_lock:
            data = KB
        with open(KB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        log.warning("KB save failed: %r", e)


load_state()
load_kb()


# =========================
# Profile / memory
# =========================
def ensure_profile(chat_id: int) -> Dict[str, Any]:
    # kb_enabled: включать ли KB подсказки в промпт
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "persona": "spicy",
        "verbosity": "normal",
        "kb_enabled": True,
        "focus_i": 0,  # для ротации фокуса
    })


def update_memory(chat_id: int, role: str, content: str) -> None:
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS * 2:]


def last_assistant_text(chat_id: int, limit: int = 1400) -> str:
    mem = USER_MEMORY.get(chat_id, [])
    for m in reversed(mem):
        if m.get("role") == "assistant":
            return (m.get("content") or "")[:limit]
    return ""


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
# Game auto-detect
# =========================
_GAME_PATTERNS = {
    "warzone": re.compile(r"\b(warzone|wz|варзон|варзоне|бр|battle\s*royale|uav)\b", re.I),
    "bf6": re.compile(r"\b(bf6|battlefield|батлфилд)\b", re.I),
    "bo7": re.compile(r"\b(bo7|black\s*ops|блэк\s*опс|zombies|зомби)\b", re.I),
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
# Telegram API
# =========================
def _sleep_backoff(i: int) -> None:
    time.sleep((0.6 * (i + 1)) + random.random() * 0.35)

def tg_request(method: str, *, params=None, payload=None, is_post: bool = False, retries: int = TG_RETRIES) -> Dict[str, Any]:
    """
    Укреплено:
    - ловим Telegram 429 и ждём retry_after
    - ловим non-JSON ответы
    - backoff
    """
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

            # Handle rate limit
            desc = data.get("description", f"Telegram HTTP {r.status_code}")
            params_err = (data.get("parameters") or {})
            if r.status_code == 429 or ("Too Many Requests" in desc):
                wait_s = int(params_err.get("retry_after") or (2 + i))
                log.warning("Telegram 429 rate limit. Sleep %ss. %s", wait_s, desc)
                time.sleep(wait_s)
                continue

            last = RuntimeError(desc)

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
        stop_event.wait(0.25)


# =========================
# KB helpers
# =========================
def _domain_allowed(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    return any(host == d or host.endswith("." + d) for d in ALLOWED_KB_DOMAINS)

def _html_to_text(html: str) -> str:
    # очень простой извлекатель: вырезаем script/style, теги, лишние пробелы
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</p\s*>", "\n", html)
    html = re.sub(r"(?is)<.*?>", " ", html)
    html = re.sub(r"[ \t\r\f\v]+", " ", html)
    html = re.sub(r"\n\s+\n", "\n\n", html)
    return html.strip()

def kb_seed_if_empty() -> None:
    # seed кратким конспектом (без копипасты) — можно расширять своими статьями
    if KB.get("articles"):
        return
    KB["articles"] = [{
        "id": 1,
        "title": "BO7 Zombies — Astra Malorum (пасхалка): быстрый конспект шагов",
        "url": "https://rutab.net/b/games/2025/12/05/polnoe-rukovodstvo-po-pashalnomu-yaycu-astra-malorum-v-black-ops-7-zombies.html",
        "game": "bo7",
        "tags": ["bo7", "zombies", "astra", "easter-egg", "гайд"],
        "summary": (
            "Короткий конспект (по гайду):\n"
            "1) Включи питание + активируй Pack-a-Punch через зону Обсерватории/локдаун.\n"
            "2) Получи чудо-оружие LGM‑1 (цепочка с О.С.К.А.Р. + ловушки).\n"
            "3) Планетный код: запомни 3 планеты из реплик, переведи в номера (по расстоянию к Солнцу) и введи код у колонны.\n"
            "4) Ключ от криокамеры → добыть мозг доктора (пила в Музеуме) → локдаун 60 сек в Люминарии.\n"
            "5) Пазл Архива: найти 5 книг и нажать бюсты по количеству нужных книг на стене → получить планету.\n"
            "6) Планетарий: по 3 запискам выставить направления планет (стрельбой) → локдаун ~2 мин → телепорт на Марс.\n"
            "7) Марс: по звуку мозга активировать пилоны в порядке от дальнего к ближнему; затем поймать «Возвышенное око».\n"
            "8) Дальше: символы/колонны → гармонизация → призыв босса → финальный бой.\n"
        ),
    }]
    save_kb()

def kb_add_from_url(url: str) -> Tuple[bool, str]:
    if not _domain_allowed(url):
        return False, f"❌ Домен запрещён. Разрешено: {', '.join(ALLOWED_KB_DOMAINS)}"
    if len(KB.get("articles", [])) >= KB_MAX_ARTICLES:
        return False, f"❌ KB переполнена (лимит {KB_MAX_ARTICLES}). Используй /kb_clear или увеличь KB_MAX_ARTICLES."

    try:
        r = SESSION.get(url, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        text = _html_to_text(r.text)
        # делаем наш конспект, а не копию (чтобы не тащить огромные тексты)
        # выжимка: берём самые "инструктивные" строки
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        head = " ".join(lines[:8])[:280]
        body = "\n".join(lines[:60])
        summary = (
            "Конспект (авто-сжатие):\n"
            f"- Заголовок/вступление: {head}\n"
            "- Ключевые пункты (обрезано):\n"
            f"{body[:2200]}\n"
            "\n⚠️ Совет: лучше заменить авто-конспект на ручной (короче и точнее)."
        )
    except Exception as e:
        return False, f"❌ Не смог скачать/обработать: {type(e).__name__}"

    new_id = (max([a.get("id", 0) for a in KB.get("articles", [])] or [0]) + 1)
    KB["articles"].append({
        "id": new_id,
        "title": f"Статья #{new_id}",
        "url": url,
        "game": "bo7",
        "tags": ["imported"],
        "summary": summary,
    })
    save_kb()
    return True, f"✅ Добавил в KB как id={new_id}. Можешь посмотреть: /kb_show {new_id}"

def kb_match(game: str, user_text: str, limit: int = 2) -> List[Dict[str, Any]]:
    """
    Примитивный ранжировщик по пересечению токенов.
    """
    if not KB.get("articles"):
        return []
    tokens = set(_tokenize(user_text))
    if not tokens:
        return []
    scored = []
    for a in KB["articles"]:
        if game and a.get("game") and a["game"] != game:
            continue
        hay = " ".join([
            a.get("title",""),
            " ".join(a.get("tags") or []),
            a.get("summary","")[:1200],
        ])
        ht = set(_tokenize(hay))
        score = len(tokens & ht)
        if score > 0:
            scored.append((score, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:limit]]


# =========================
# OpenAI helpers
# =========================
def _openai_create(messages: List[Dict[str, str]], max_tokens: int):
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

def next_focus(p: Dict[str, Any]) -> Tuple[str, str]:
    i = int(p.get("focus_i") or 0) % len(FOCUSES)
    p["focus_i"] = (i + 1) % len(FOCUSES)
    return FOCUSES[i]

def build_messages(chat_id: int, user_text: str, regen: bool = False) -> Tuple[List[Dict[str, str]], str]:
    p = ensure_profile(chat_id)

    detected = detect_game(user_text)
    if detected and detected in GAMES:
        p["game"] = detected

    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")
    game = p.get("game", "warzone")

    focus = next_focus(p)
    focus_line = f"СЕГОДНЯШНИЙ ФОКУС: {focus[0]} — {focus[1]}. Держись этого фокуса."

    last_a = last_assistant_text(chat_id)
    anti_repeat = (
        "ВАЖНО: НЕ повторяй формулировки и те же 2 действия из прошлого ответа ассистента.\n"
        "Если тема похожа — дай ДРУГОЙ угол: (1) другие 2 действия, (2) другой дрилл, (3) другой панч.\n"
        "ОБЯЗАТЕЛЬНО: перефразируй 1–2 ключевые фразы пользователя (чтобы ответ был 'про него').\n"
        "Сделай советы конкретными под ситуацию (дистанция, оружие, роль, режим).\n"
    )
    if last_a:
        anti_repeat += f"\nПРОШЛЫЙ ОТВЕТ (избегай повторов):\n{last_a}\n"
    if regen:
        anti_repeat += (
            "\nАНТИ-ПОВТОР x2: полностью измени диагноз, дрилл и 2 действия. "
            "Не используй одинаковые примеры. Не копируй структуру фраз.\n"
        )

    coach_frame = (
        "Не выдумывай патчи/мету. Если не уверен — общие принципы.\n"
        "Запрещено: читы/хаки/обход античита.\n"
    )

    max_len_hint = VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])

    kb_block = ""
    if p.get("kb_enabled", True):
        hits = kb_match(game, user_text, limit=2)
        if hits:
            pieces = []
            for a in hits:
                pieces.append(f"- [{a.get('title','')}] ({a.get('url','')})\n{a.get('summary','')[:900]}")
            kb_block = "KB-подсказки (используй как справку, не цитируй дословно):\n" + "\n\n".join(pieces)

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": coach_frame},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": max_len_hint},
        {"role": "system", "content": focus_line},
        {"role": "system", "content": anti_repeat},
        {"role": "system", "content": f"Текущая игра: {GAME_NAMES.get(game, game)}."},
        {"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"},
    ]
    if kb_block:
        messages.append({"role": "system", "content": kb_block})

    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    max_out = 760 if verbosity == "talkative" else (560 if verbosity == "normal" else 420)
    return messages, game, max_out

def openai_reply(chat_id: int, user_text: str) -> str:
    messages, game, max_out = build_messages(chat_id, user_text, regen=False)
    prev = last_assistant_text(chat_id, limit=1800)

    for attempt in range(2):
        try:
            resp = _openai_create(messages, max_out)
            out = (resp.choices[0].message.content or "").strip()
            if not out:
                out = "Не получил ответ. Напиши ещё раз 🙌"

            if attempt == 0 and prev and too_similar(out, prev):
                messages, _, max_out = build_messages(chat_id, user_text, regen=True)
                continue

            if game in GAME_NAMES:
                out = f"🎮 {GAME_NAMES[game]}\n\n" + out
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
# Commands
# =========================
def help_text() -> str:
    return (
        "🌑 FPS Coach Bot (public)\n"
        "Пиши ситуацию/вопрос — отвечу как коуч.\n\n"
        "Команды:\n"
        "/start — помощь\n"
        "/status — конфиг\n"
        "/ai_test — тест AI\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/game warzone|bf6|bo7 (или просто упоминай игру в тексте)\n"
        "/kb_list | /kb_show <id> | /kb_add <url> | /kb_clear | /kb_reload\n"
        "/kb_on | /kb_off\n"
        "/reset — очистить память\n"
    )

def status_text() -> str:
    return (
        "🧾 Status\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"STATE_PATH: {STATE_PATH}\n"
        f"KB_PATH: {KB_PATH}\n"
        f"KB articles: {len(KB.get('articles', []))}\n\n"
        "Если ловишь Conflict 409 — запущены 2 инстанса (Render Instances > 1) или второй сервис с тем же ботом.\n"
    )

def ai_test() -> str:
    try:
        r = _openai_create([{"role": "user", "content": "Ответь одним словом: OK"}], 10)
        out = (r.choices[0].message.content or "").strip()
        return f"✅ /ai_test: {out or 'OK'} (model={OPENAI_MODEL})"
    except AuthenticationError:
        return "❌ /ai_test: неверный ключ."
    except APIConnectionError:
        return "⚠️ /ai_test: проблема сети/Render."
    except Exception as e:
        return f"⚠️ /ai_test: {type(e).__name__}"

def kb_list_text() -> str:
    items = KB.get("articles", []) or []
    if not items:
        return "KB пустая. Добавь: /kb_add <url>"
    lines = ["📚 KB articles:"]
    for a in items[:30]:
        lines.append(f"- id={a.get('id')} | {a.get('game','')} | {a.get('title','')}")
    if len(items) > 30:
        lines.append(f"… и ещё {len(items)-30}")
    return "\n".join(lines)

def kb_show_text(article_id: int) -> str:
    for a in (KB.get("articles") or []):
        if int(a.get("id", 0)) == int(article_id):
            return f"📄 id={a.get('id')}\n{a.get('title')}\n{a.get('url')}\n\n{a.get('summary','')}"
    return "Не нашёл такой id. Посмотри /kb_list"

def kb_clear() -> str:
    KB["articles"] = []
    save_kb()
    kb_seed_if_empty()
    return "🧹 KB очищена (и пересидирована базовым конспектом)."


# =========================
# Message handler
# =========================
def handle_message(chat_id: int, text: str) -> None:
    with _get_lock(chat_id):
        if throttle(chat_id):
            return

        p = ensure_profile(chat_id)
        t = (text or "").strip()

        # commands
        if t.startswith("/start"):
            send_message(chat_id, help_text())
            return

        if t.startswith("/status"):
            send_message(chat_id, status_text())
            return

        if t.startswith("/ai_test"):
            send_message(chat_id, ai_test())
            return

        if t.startswith("/reset"):
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            ensure_profile(chat_id)
            save_state()
            send_message(chat_id, "🧹 Сбросил профиль и память.")
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

        if t.startswith("/kb_on"):
            p["kb_enabled"] = True
            save_state()
            send_message(chat_id, "✅ KB подсказки: ON")
            return

        if t.startswith("/kb_off"):
            p["kb_enabled"] = False
            save_state()
            send_message(chat_id, "✅ KB подсказки: OFF")
            return

        if t.startswith("/kb_list"):
            send_message(chat_id, kb_list_text())
            return

        if t.startswith("/kb_reload"):
            load_kb()
            send_message(chat_id, f"✅ KB перезагружена. Articles: {len(KB.get('articles', []))}")
            return

        if t.startswith("/kb_clear"):
            send_message(chat_id, kb_clear())
            return

        if t.startswith("/kb_show"):
            parts = t.split()
            if len(parts) >= 2 and parts[1].isdigit():
                send_message(chat_id, kb_show_text(int(parts[1])))
            else:
                send_message(chat_id, "Используй: /kb_show <id>")
            return

        if t.startswith("/kb_add"):
            parts = t.split(maxsplit=1)
            if len(parts) < 2:
                send_message(chat_id, "Используй: /kb_add <url>")
                return
            ok, msg = kb_add_from_url(parts[1].strip())
            send_message(chat_id, msg)
            return

        # auto detect game from message
        detected = detect_game(t)
        if detected and detected in GAMES:
            p["game"] = detected

        # AI reply + safe animation
        update_memory(chat_id, "user", t)

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
        save_state()

        if tmp_id:
            try:
                edit_message(chat_id, tmp_id, reply)
            except Exception:
                send_message(chat_id, reply)
        else:
            send_message(chat_id, reply)


# =========================
# Polling loop (watchdog)
# =========================
def run_telegram_bot_once() -> None:
    delete_webhook_on_start()
    log.info("Telegram bot started (long polling)")
    offset = 0
    last_ok = time.time()

    while True:
        try:
            data = tg_request("getUpdates", params={"offset": offset, "timeout": TG_LONGPOLL_TIMEOUT})
            last_ok = time.time()

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

        # Heartbeat: если слишком долго нет успешного getUpdates — перезапускаем цикл
        if time.time() - last_ok > max(180, TG_LONGPOLL_TIMEOUT * 4):
            raise RuntimeError("Polling heartbeat timeout")


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
    kb_seed_if_empty()

    stop_autosave = threading.Event()
    threading.Thread(target=autosave_loop, args=(stop_autosave, 60), daemon=True).start()

    # Polling in background thread so HTTP server can answer health checks.
    threading.Thread(target=run_telegram_bot_forever, daemon=True).start()

    # Main thread keeps process alive.
    run_http_server()

