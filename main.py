# -*- coding: utf-8 -*-
"""
FPS Coach Bot — PUBLIC AI (Render + long polling)

Goals:
- Works reliably on Render (health endpoint + stable long polling)
- No inline keyboards (buttons removed)
- AI replies in a fixed 4-block coaching format
- Auto-detects game (Warzone / BF6 / BO7) from user text + allows /game override
- Reduces repetitive answers (anti-repeat prompt + penalties + focus rotation + similarity retry)
- Conflict 409 backoff + deleteWebhook on start
- Optional state persistence (profiles + short memory) via DATA_DIR

ENV (Render -> Environment -> Add):
- TELEGRAM_BOT_TOKEN   (required)
- OPENAI_API_KEY       (required)
- OPENAI_MODEL         (optional, default: gpt-4o-mini)
- OPENAI_BASE_URL      (optional, default: https://api.openai.com/v1)

Optional tuning:
- DATA_DIR=/tmp                    (or mount a Render Disk and set DATA_DIR=/var/data)
- MEMORY_MAX_TURNS=10
- MIN_SECONDS_BETWEEN_MSG=0.35
- TG_LONGPOLL_TIMEOUT=50
- TG_RETRIES=5
- HTTP_TIMEOUT=25
- PULSE_MIN_SECONDS=1.25
- CONFLICT_BACKOFF_MIN=12
- CONFLICT_BACKOFF_MAX=30
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

import requests
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError


# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_public_v7")


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
MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.35"))

CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))

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
SESSION.headers.update({"User-Agent": "render-fps-coach-public/7.0"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))


# =========================
# State (profiles + short memory)
# =========================
USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
LAST_MSG_TS: Dict[int, float] = {}

# per-chat lock to avoid overlapping concurrent AI calls for same chat
CHAT_LOCKS: Dict[int, threading.Lock] = {}

_state_lock = threading.Lock()


def _get_lock(chat_id: int) -> threading.Lock:
    if chat_id not in CHAT_LOCKS:
        CHAT_LOCKS[chat_id] = threading.Lock()
    return CHAT_LOCKS[chat_id]


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
# Profile / memory
# =========================
def ensure_profile(chat_id: int) -> Dict[str, Any]:
    # Default game: warzone; user can override by /game or auto-detect
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "persona": "spicy",
        "verbosity": "normal",
    })


def update_memory(chat_id: int, role: str, content: str) -> None:
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    # keep only last N turns (user+assistant messages)
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
    "warzone": re.compile(r"\b(warzone|wz|варзон|варзоне|код|cod|бр|battle\s*royale)\b", re.I),
    "bf6": re.compile(r"\b(bf6|battlefield|батлфилд|battle field)\b", re.I),
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
    # priority if multiple (rare): explicit bf6/bo7 > warzone
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

            # Telegram returns 200 ok:false sometimes
            last = RuntimeError(data.get("description", f"Telegram HTTP {r.status_code}"))

        except Exception as e:
            last = e

        _sleep_backoff(i)

    raise last or RuntimeError("Telegram request failed")


def send_message(chat_id: int, text: str) -> Optional[int]:
    # Telegram limit ~4096; stay safe
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
    # Critical for long polling if a webhook was ever set
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
    """
    Uses penalties + temperature to reduce repetition and improve variety.
    Compatible with SDKs that use max_tokens vs max_completion_tokens.
    """
    kwargs = dict(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.9,
        presence_penalty=0.6,
        frequency_penalty=0.35,
    )
    try:
        return openai_client.chat.completions.create(
            **kwargs,
            max_completion_tokens=max_tokens,
        )
    except TypeError:
        return openai_client.chat.completions.create(
            **kwargs,
            max_tokens=max_tokens,
        )


def _tokenize(s: str) -> List[str]:
    s = s.lower()
    s = re.sub(r"[^a-zа-я0-9ё\s]+", " ", s)
    parts = [p for p in s.split() if len(p) >= 3]
    return parts


def too_similar(a: str, b: str, threshold: float = 0.62) -> bool:
    """
    Simple Jaccard similarity over tokens.
    If reply is too similar to previous assistant reply, we regenerate once with stronger instruction.
    """
    if not a or not b:
        return False
    ta = set(_tokenize(a))
    tb = set(_tokenize(b))
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    uni = len(ta | tb)
    sim = inter / max(1, uni)
    return sim >= threshold


def build_messages(chat_id: int, user_text: str, regen: bool = False) -> Tuple[List[Dict[str, str]], str]:
    p = ensure_profile(chat_id)

    # auto-detect game (unless user explicitly set via /game recently)
    detected = detect_game(user_text)
    if detected and detected in GAMES:
        p["game"] = detected

    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")
    game = p.get("game", "warzone")

    focus = random.choice(FOCUSES)
    focus_line = f"СЕГОДНЯШНИЙ ФОКУС: {focus[0]} — {focus[1]}. Держись этого фокуса."

    last_a = last_assistant_text(chat_id)
    anti_repeat = (
        "ВАЖНО: НЕ повторяй формулировки и советы из прошлого ответа ассистента.\n"
        "Если тема похожа — дай ДРУГОЙ угол: (1) другие 2 действия, (2) другой дрилл, (3) другой панч.\n"
        "Обязательно упомяни слова пользователя (перефразируй) и сделай советы конкретными.\n"
    )
    if last_a:
        anti_repeat += f"\nПРОШЛЫЙ ОТВЕТ (избегай повторов):\n{last_a}\n"

    if regen:
        anti_repeat += (
            "\nРЕЖИМ АНТИ-ПОВТОР x2: полностью измени дрилл и 2 действия; "
            "не используй слова 'позиция/тайминг/инфо' вместе — выбери одну тему.\n"
        )

    coach_frame = (
        "Не придумывай патчи/мету. Если не уверен — общие принципы.\n"
        "Запрещено: читы/хаки/обход античита.\n"
    )

    max_len_hint = VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])

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
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    max_out = 720 if verbosity == "talkative" else (520 if verbosity == "normal" else 380)
    return messages, game


def openai_reply(chat_id: int, user_text: str) -> str:
    # 1) first try
    messages, game = build_messages(chat_id, user_text, regen=False)
    prev = last_assistant_text(chat_id, limit=1800)

    for attempt in range(2):
        try:
            resp = _openai_create(messages, 720)
            out = (resp.choices[0].message.content or "").strip()
            if not out:
                out = "Не получил ответ. Напиши ещё раз 🙌"

            # If too similar to previous assistant reply -> regenerate once with stronger anti-repeat
            if attempt == 0 and prev and too_similar(out, prev):
                messages, _ = build_messages(chat_id, user_text, regen=True)
                continue

            # small header to show detected game (optional but helpful)
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
        "Пиши ситуацию / вопрос — отвечу как коуч.\n\n"
        "Команды:\n"
        "/start — помощь\n"
        "/status — конфиг\n"
        "/ai_test — тест AI\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/game warzone|bf6|bo7 (или просто упоминай игру в тексте)\n"
        "/reset — очистить память\n"
    )


def status_text() -> str:
    return (
        "🧾 Status\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"STATE_PATH: {STATE_PATH}\n\n"
        "Если ловишь Conflict 409 — значит запущены 2 инстанса или второй сервис с тем же ботом.\n"
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


# =========================
# Message handler
# =========================
def handle_message(chat_id: int, text: str) -> None:
    # per-chat serial execution
    with _get_lock(chat_id):
        if throttle(chat_id):
            return

        p = ensure_profile(chat_id)
        t = text.strip()

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

        # Auto-detect game from regular messages too (no command needed)
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

    # Start polling in a background thread so the HTTP server can respond to Render health checks.
    threading.Thread(target=run_telegram_bot_forever, daemon=True).start()

    # Main thread keeps process alive.
    run_http_server()
