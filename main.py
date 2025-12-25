# -*- coding: utf-8 -*-
"""FPS Coach Bot — PUBLIC AI v10 (Render + long polling)

Основное:
- Работает на Render как long-polling бот (deleteWebhook + стабильный getUpdates).
- Health endpoint для Render (/, /healthz).
- Состояние (профили + память) сохраняется в DATA_DIR/fps_coach_state.json.
- Авто-определение игры (Warzone / BF6 / BO7) + режимов:
  * PvP тактика (стиль как на твоих первых скринах: "Действуем чётко", "Профилактика")
  * Коуч-формат 4 блока (Диагноз/Что делать/Дрилл/Панч)
  * Гайды по BO7 Zombies (из локальной базы статей kb_articles.json)

Важно про 24/7:
- На бесплатном Render сервис может "засыпать" (spin down). Код НЕ может это отменить.
  Решение: платный план/Always On или внешний пинг (UptimeRobot) на /healthz.

ENV (Render -> Environment):
- TELEGRAM_BOT_TOKEN (required)
- OPENAI_API_KEY (required)
- OPENAI_MODEL (optional, default: gpt-4o-mini)
- OPENAI_BASE_URL (optional, default: https://api.openai.com/v1)

Optional:
- DATA_DIR=/tmp  (или Render Disk: /var/data)
- ADMIN_CHAT_IDS=123,456  (кто может /kb_add, /kb_reload)

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
log = logging.getLogger("fps_coach_public_v10")

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

ADMIN_CHAT_IDS = set()
_raw_admin = os.getenv("ADMIN_CHAT_IDS", "").strip()
if _raw_admin:
    for part in _raw_admin.split(","):
        part = part.strip()
        if part.isdigit():
            ADMIN_CHAT_IDS.add(int(part))

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
    max_retries=0,
)

# =========================
# Requests session
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-public/10.0"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))

# =========================
# State
# =========================
USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
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


load_state()

# =========================
# KB (Articles)
# =========================
KB: Dict[str, Any] = {"articles": []}


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("ё", "е")
    s = re.sub(r"[^a-zа-я0-9\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> List[str]:
    parts = _norm(s).split()
    return [p for p in parts if len(p) >= 3]


def kb_load() -> None:
    global KB
    try:
        if os.path.exists(KB_PATH):
            with open(KB_PATH, "r", encoding="utf-8") as f:
                KB = json.load(f)
            if not isinstance(KB, dict) or "articles" not in KB:
                KB = {"articles": []}
            log.info("KB loaded: %d articles (%s)", len(KB.get("articles", [])), KB_PATH)
        else:
            KB = {"articles": []}
            log.info("KB not found (%s) - continuing without articles", KB_PATH)
    except Exception as e:
        KB = {"articles": []}
        log.warning("KB load failed: %r", e)


def kb_reload() -> str:
    kb_load()
    return f"✅ KB reload: {len(KB.get('articles', []))} articles"


def kb_search(query: str, *, game: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """Fuzzy-ish scorer over tokens in title/keywords/tags/content."""
    q = _norm(query)
    q_tokens = set(_tokens(q))
    if not q_tokens:
        return []

    results = []
    for art in KB.get("articles", []):
        if not isinstance(art, dict):
            continue
        if game and art.get("game") and art.get("game") != game:
            continue

        title = _norm(art.get("title", ""))
        kw = art.get("keywords") or []
        tags = art.get("tags") or []
        content = _norm(art.get("content", ""))

        bag = set(_tokens(title))
        bag |= set(_tokens(" ".join([str(x) for x in kw])))
        bag |= set(_tokens(" ".join([str(x) for x in tags])))

        # lightweight content signal: only take first ~2500 chars
        bag |= set(_tokens(content[:2500]))

        inter = len(q_tokens & bag)
        if inter == 0:
            continue

        # boost: exact phrase match in title
        score = inter
        if q in title and len(q) >= 6:
            score += 6
        # boost: zombies intent
        if "zombie" in q or "зомби" in q:
            if "zombie" in title or "зомби" in title:
                score += 3
        # boost: astra malorum
        if "astra" in q or "астра" in q:
            if "astra" in title or "астра" in title:
                score += 5

        results.append((score, art))

    results.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in results[:top_k]]


def kb_render_article(art: Dict[str, Any], *, max_chars: int = 3300) -> str:
    title = art.get("title") or "Статья"
    url = art.get("url") or ""
    content = (art.get("content") or "").strip()
    if not content:
        return f"🧾 {title}\n\n(контент пуст)\n{url}".strip()

    if len(content) > max_chars:
        content = content[:max_chars].rsplit("\n", 1)[0] + "\n…"

    header = f"📚 {title}" + (f"\n{url}" if url else "")
    return header + "\n\n" + content


kb_load()

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
    "warzone": re.compile(r"\b(warzone|wz|варзон|варзоне|варзона|код|cod|бр|battle\s*royale)\b", re.I),
    "bf6": re.compile(r"\b(bf6|battlefield|батлфилд|battle\s*field)\b", re.I),
    "bo7": re.compile(r"\b(bo7|black\s*ops|блэк\s*опс|blackops)\b", re.I),
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
# Mode detection
# =========================
MODE_COACH = "coach"       # 4-block coaching
MODE_TACTIC = "tactic"     # first-bot style (tactical)
MODE_GUIDE = "guide"       # KB-based (BO7 zombies guides)


def detect_mode(game: str, text: str) -> str:
    t = _norm(text)

    # explicit
    if t.startswith("гайд") or "пасхал" in t or "easter" in t or "яйц" in t:
        return MODE_GUIDE
    if "зомби" in t or "zombies" in t:
        return MODE_GUIDE

    # warzone typical tactical questions
    tactical_triggers = (
        "сквад", "зона", "ротац", "гейт", "gatekeep", "хайграунд", "низ", "сверху", "сзади",
        "пуш", "фланг", "смок", "дым", "кластер", "пресижн", "страйк", "мортир", "uav", "пин",
    )

    if game == "warzone" and any(x in t for x in tactical_triggers):
        return MODE_TACTIC

    # BF6/BO7 PvP default coach
    return MODE_COACH


# =========================
# Persona / formatting
# =========================
SYSTEM_PROMPT_BASE = (
    "Ты харизматичный FPS-коуч по Warzone/BF6/BO7. Пишешь по-русски.\n"
    "Тон: уверенный, быстрый, с юмором и лёгкими подколами (без токсичности).\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
)

COACH_FORMAT_RULE = (
    "Формат ответа ВСЕГДА (если режим COACH):\n"
    "1) 🎯 Диагноз (1 главная ошибка)\n"
    "2) ✅ Что делать (2 действия прямо сейчас)\n"
    "3) 🧪 Дрилл (5–10 минут)\n"
    "4) 😈 Панчик/мотивация (1 строка)\n"
    "Если данных мало — задай 1 вопрос в конце."
)

TACTIC_FORMAT_RULE = (
    "Если режим TACTIC (Warzone): отвечай как тактик, короткими буллетами, как в примере ниже.\n"
    "Структура:\n"
    "- 1 строка: назвать ситуацию (например: 'Классическая gatekeep-ситуация. Действуем чётко:')\n"
    "- Затем 5–8 буллетов с конкретными шагами (утилы, маршрут, тайминг, роли).\n"
    "- Затем блок 'Профилактика на будущее:' 2–4 буллета.\n"
    "- В конце 1 уточняющий вопрос, если нужно.\n"
    "Не нумеруй обязательно. Не расписывай теорию."
)

GUIDE_FORMAT_RULE = (
    "Если режим GUIDE (BO7 Zombies):\n"
    "- Дай пошаговое прохождение (шаги 1..N) по конкретному запросу, без лишней воды.\n"
    "- Если статья/гайд найден в базе — опирайся на него, цитируй термины/названия, но не пиши огромные полотна.\n"
    "- Если в базе нет — попроси уточнение или скажи, что нужно добавить статью в базу."
)

PERSONA_HINT = {
    "spicy": "Стиль: дерзко и смешно, но без оскорблений.",
    "chill": "Стиль: спокойно и дружелюбно, мягкий юмор.",
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
    ("инфо", "радар, звук, пинги, чтение ситуации"),
    ("дуэли", "пик, префайр, first-shot, микрокоррекции"),
    ("дисциплина", "ресурсы, отступления, ресеты, не жадничать"),
]

# =========================
# Profile / memory
# =========================

def ensure_profile(chat_id: int) -> Dict[str, Any]:
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "persona": "spicy",
        "verbosity": "normal",
        "mode": "auto",  # auto/coach/tactic/guide
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
# OpenAI helpers
# =========================

def _openai_create(messages: List[Dict[str, str]], max_tokens: int):
    kwargs = dict(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.95,
        presence_penalty=0.7,
        frequency_penalty=0.4,
    )
    try:
        return openai_client.chat.completions.create(**kwargs, max_completion_tokens=max_tokens)
    except TypeError:
        return openai_client.chat.completions.create(**kwargs, max_tokens=max_tokens)


def _jaccard_sim(a: str, b: str) -> float:
    ta = set(_tokens(a))
    tb = set(_tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def build_messages(chat_id: int, user_text: str, *, mode: str, regen: bool) -> Tuple[List[Dict[str, str]], str, str]:
    p = ensure_profile(chat_id)

    # auto-detect game
    detected = detect_game(user_text)
    if detected and detected in GAMES:
        p["game"] = detected

    game = p.get("game", "warzone")

    # resolve mode
    user_mode = p.get("mode", "auto")
    if user_mode in (MODE_COACH, MODE_TACTIC, MODE_GUIDE):
        mode_final = user_mode
    else:
        mode_final = mode

    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    focus = random.choice(FOCUSES)
    focus_line = f"СЕГОДНЯШНИЙ ФОКУС: {focus[0]} — {focus[1]}." if mode_final != MODE_GUIDE else ""

    last_a = last_assistant_text(chat_id)
    anti_repeat = (
        "ВАЖНО: не повторяй формулировки и советы из прошлого ответа. "
        "Если тема похожа — дай другой угол (другие действия/дрилл/панч).\n"
    )
    if last_a:
        anti_repeat += f"ПРОШЛЫЙ ОТВЕТ (избегай повторов):\n{last_a}\n"
    if regen:
        anti_repeat += "АНТИ-ПОВТОР x2: полностью измени 2 действия и дрилл, новые формулировки.\n"

    # attach KB snippet if guide
    kb_block = ""
    if mode_final == MODE_GUIDE:
        hits = kb_search(user_text, game="bo7", top_k=1)
        if hits:
            art = hits[0]
            # short, because the model should use it as reference
            kb_block = (
                "КОНТЕКСТ ИЗ БАЗЫ (используй для ответа):\n"
                f"TITLE: {art.get('title','')}\n"
                f"URL: {art.get('url','')}\n"
                f"CONTENT:\n{(art.get('content') or '')[:5000]}\n"
            )
        else:
            kb_block = "В БАЗЕ НЕТ ПОДХОДЯЩЕЙ СТАТЬИ. Скажи честно, что нужно добавить гайд в KB."\

    # format rules
    rules = [SYSTEM_PROMPT_BASE]
    if mode_final == MODE_COACH:
        rules.append(COACH_FORMAT_RULE)
    elif mode_final == MODE_TACTIC:
        rules.append(TACTIC_FORMAT_RULE)
    else:
        rules.append(GUIDE_FORMAT_RULE)

    rules.append(PERSONA_HINT.get(persona, PERSONA_HINT["spicy"]))
    rules.append(VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"]))
    if focus_line:
        rules.append(focus_line)
    rules.append(anti_repeat)
    rules.append(f"Текущая игра: {GAME_NAMES.get(game, game)}")
    if kb_block:
        rules.append(kb_block)

    messages: List[Dict[str, str]] = [{"role": "system", "content": "\n\n".join(rules)}]
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    max_out = 900 if mode_final == MODE_GUIDE else (720 if verbosity == "talkative" else (520 if verbosity == "normal" else 380))
    return messages, game, mode_final


def openai_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    game = p.get("game", "warzone")
    mode_guess = detect_mode(game, user_text)

    prev = last_assistant_text(chat_id, limit=2000)

    for attempt in range(2):
        try:
            messages, game_final, mode_final = build_messages(chat_id, user_text, mode=mode_guess, regen=(attempt == 1))
            resp = _openai_create(messages, 900)
            out = (resp.choices[0].message.content or "").strip() or "Не получил ответ. Напиши ещё раз 🙌"

            # similarity regen (only for non-guide)
            if attempt == 0 and prev and mode_final != MODE_GUIDE:
                if _jaccard_sim(out, prev) >= 0.62:
                    continue

            # show header if you want (minimal)
            if mode_final == MODE_GUIDE:
                return out

            prefix = f"🎮 {GAME_NAMES.get(game_final, game_final)}\n" if game_final in GAME_NAMES else ""
            return (prefix + "\n" + out).strip()

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
        "🌑 FPS Coach Bot\n"
        "Пиши вопрос/ситуацию — отвечу.\n\n"
        "Команды:\n"
        "/start — помощь\n"
        "/status — конфиг\n"
        "/ai_test — тест AI\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/game warzone|bf6|bo7\n"
        "/mode auto|coach|tactic|guide\n"
        "/kb_search <запрос>  (по базе статей)\n"
        "/kb_show <номер>     (последние результаты поиска)\n"
        "/reset — очистить память\n"
    )


def status_text() -> str:
    return (
        "🧾 Status\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"STATE_PATH: {STATE_PATH}\n"
        f"KB_PATH: {KB_PATH} (articles={len(KB.get('articles', []))})\n\n"
        "Если ловишь Conflict 409 — значит запущены 2 инстанса или где-то включен webhook.\n"
        "Если бот на free Render выключается — это spin down, включи Always On или пингуй /healthz."
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


# store last KB search results per chat
KB_LAST: Dict[int, List[Dict[str, Any]]] = {}


def handle_kb_search(chat_id: int, query: str) -> str:
    hits = kb_search(query, game="bo7", top_k=5)
    KB_LAST[chat_id] = hits
    if not hits:
        return "🔎 Ничего не нашёл в базе. Добавь статью в kb_articles.json и сделай /kb_reload (админ)."

    lines = ["🔎 Нашёл:"]
    for i, art in enumerate(hits, 1):
        lines.append(f"{i}) {art.get('title','(без названия)')}")
    lines.append("\nОткрой: /kb_show 1")
    return "\n".join(lines)


def handle_kb_show(chat_id: int, idx: int) -> str:
    hits = KB_LAST.get(chat_id) or []
    if not hits:
        return "Сначала сделай /kb_search <запрос>"
    if idx < 1 or idx > len(hits):
        return f"Номер должен быть 1..{len(hits)}"
    return kb_render_article(hits[idx - 1])


# =========================
# Message handler
# =========================

def handle_message(chat_id: int, text: str) -> None:
    with _get_lock(chat_id):
        if throttle(chat_id):
            return

        p = ensure_profile(chat_id)
        t = (text or "").strip()
        low = t.lower().strip()

        if low.startswith("/start"):
            send_message(chat_id, help_text())
            return

        if low.startswith("/status"):
            send_message(chat_id, status_text())
            return

        if low.startswith("/ai_test"):
            send_message(chat_id, ai_test())
            return

        if low.startswith("/reset"):
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            ensure_profile(chat_id)
            save_state()
            send_message(chat_id, "🧹 Сбросил профиль и память.")
            return

        if low.startswith("/persona"):
            parts = low.split()
            if len(parts) >= 2 and parts[1] in ("spicy", "chill", "pro"):
                p["persona"] = parts[1]
                save_state()
                send_message(chat_id, f"✅ Persona = {p['persona']}")
            else:
                send_message(chat_id, "Используй: /persona spicy | chill | pro")
            return

        if low.startswith("/talk"):
            parts = low.split()
            if len(parts) >= 2 and parts[1] in ("short", "normal", "talkative"):
                p["verbosity"] = parts[1]
                save_state()
                send_message(chat_id, f"✅ Talk = {p['verbosity']}")
            else:
                send_message(chat_id, "Используй: /talk short | normal | talkative")
            return

        if low.startswith("/game"):
            parts = low.split()
            if len(parts) >= 2 and parts[1] in GAMES:
                p["game"] = parts[1]
                save_state()
                send_message(chat_id, f"✅ Игра = {GAME_NAMES[p['game']]}")
            else:
                send_message(chat_id, "Используй: /game warzone | bf6 | bo7")
            return

        if low.startswith("/mode"):
            parts = low.split()
            if len(parts) >= 2 and parts[1] in ("auto", MODE_COACH, MODE_TACTIC, MODE_GUIDE):
                p["mode"] = parts[1]
                save_state()
                send_message(chat_id, f"✅ Mode = {p['mode']}")
            else:
                send_message(chat_id, "Используй: /mode auto|coach|tactic|guide")
            return

        if low.startswith("/kb_reload"):
            if ADMIN_CHAT_IDS and chat_id not in ADMIN_CHAT_IDS:
                send_message(chat_id, "⛔️ /kb_reload только для админов")
                return
            send_message(chat_id, kb_reload())
            return

        if low.startswith("/kb_search"):
            q = t[len("/kb_search"):].strip()
            if not q:
                send_message(chat_id, "Используй: /kb_search astra malorum")
                return
            send_message(chat_id, handle_kb_search(chat_id, q))
            return

        if low.startswith("/kb_show"):
            arg = t[len("/kb_show"):].strip()
            if not arg.isdigit():
                send_message(chat_id, "Используй: /kb_show 1")
                return
            send_message(chat_id, handle_kb_show(chat_id, int(arg)))
            return

        # Auto-detect game for regular text
        detected = detect_game(t)
        if detected:
            p["game"] = detected

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
            log.exception("Polling crashed - restarting in 3 seconds")
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
