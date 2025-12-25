# -*- coding: utf-8 -*-
"""
FPS Coach Bot — PUBLIC AI (no buttons) for Render (Web Service) + long polling

What this version fixes/strengthens:
- Proper UTF-8 strings (no broken symbols)
- Much tougher Telegram request layer (timeouts, JSON errors, 429/5xx retries)
- Safer long polling loop with conflict backoff + jitter
- Optional typing animation (default OFF to avoid edit limits)
- Per-chat rate limit + global concurrency limit for OpenAI calls
- Small in-memory chat memory (bounded)
- Health endpoint for Render: /healthz

IMPORTANT ABOUT 24/7:
- Render Free Web Services can "spin down" on inactivity. To stay always-on you need either:
  1) Paid plan (recommended), or
  2) External ping (e.g., UptimeRobot) hitting /healthz every ~5 minutes.
"""

import os
import time
import json
import random
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional

import requests
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_public_v6")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
TG_LONGPOLL_TIMEOUT = int(os.getenv("TG_LONGPOLL_TIMEOUT", "50"))
TG_RETRIES = int(os.getenv("TG_RETRIES", "6"))

MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.35"))

CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "8"))

ANIMATION = os.getenv("ANIMATION", "0").strip() == "1"
PULSE_MIN_SECONDS = float(os.getenv("PULSE_MIN_SECONDS", "1.35"))

MAX_CONCURRENT_AI = int(os.getenv("MAX_CONCURRENT_AI", "2"))

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise SystemExit("Missing ENV: OPENAI_API_KEY")

openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    timeout=30,
    max_retries=0,
)
_ai_sem = threading.Semaphore(max(1, MAX_CONCURRENT_AI))

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-public/6.0"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))

USER_PROFILE: Dict[int, Dict[str, str]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
LAST_MSG_TS: Dict[int, float] = {}

GAME_PILLARS = {
    "warzone": "Фокус Warzone: позиция/тайминг, инфо (радар/звук/пинги), пре-эйм, ротации заранее, после контакта — репозиция.",
    "bf6": "Фокус BF6: линии фронта/спавны, пик→инфо→откат, серия→репозиция, игра от укрытий.",
    "bo7": "Фокус BO7: центр экрана+префайр, тайминги, 2 секунды на позиции→смена, репик с другого угла.",
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
    "short": "Длина: коротко.",
    "normal": "Длина: обычно.",
    "talkative": "Длина: подробнее + 1–2 доп. совета.",
}
THINKING_LINES = [
    "🧠 Думаю… сейчас будет жара 😈",
    "⌛ Секунду… раскладываю по полочкам 🧩",
    "🎮 Окей, коуч на связи. Сейчас разнесём 👊",
    "🌑 Анализирую… не моргай 😈",
]

def ensure_profile(chat_id: int) -> Dict[str, str]:
    return USER_PROFILE.setdefault(chat_id, {
        "game": "warzone",
        "persona": "spicy",
        "verbosity": "normal",
    })

def update_memory(chat_id: int, role: str, content: str):
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    cap = max(2, MEMORY_MAX_TURNS * 2)
    if len(mem) > cap:
        USER_MEMORY[chat_id] = mem[-cap:]

def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False

def _sleep_backoff(i: int):
    time.sleep(min(8.0, 0.7 * (i + 1)) + random.random() * 0.35)

def tg_request(method: str, *, params=None, payload=None, is_post=False, retries=TG_RETRIES):
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

            desc = data.get("description", f"Telegram HTTP {r.status_code}")

            if r.status_code == 429:
                retry_after = 2
                try:
                    retry_after = int((data.get("parameters") or {}).get("retry_after") or 2)
                except Exception:
                    retry_after = 2
                time.sleep(min(30, retry_after))
                last = RuntimeError(desc)
                continue

            last = RuntimeError(desc)

        except Exception as e:
            last = e

        _sleep_backoff(i)

    raise last if last else RuntimeError("Telegram request failed")

def send_message(chat_id: int, text: str):
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
    last_msg_id = None
    for ch in chunks:
        res = tg_request("sendMessage", payload={"chat_id": chat_id, "text": ch}, is_post=True)
        last_msg_id = res.get("result", {}).get("message_id")
    return last_msg_id

def edit_message(chat_id: int, message_id: int, text: str):
    tg_request("editMessageText", payload={"chat_id": chat_id, "message_id": message_id, "text": text}, is_post=True)

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

def typing_loop(chat_id: int, stop_event: threading.Event, interval: float = 4.0):
    while not stop_event.is_set():
        send_chat_action(chat_id, "typing")
        stop_event.wait(interval)

def pulse_edit_loop(chat_id: int, message_id: int, stop_event: threading.Event, base: str = "⌛ Думаю"):
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

def openai_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")
    game = p.get("game", "warzone")

    coach_frame = (
        "Пиши конкретно. Если данных мало — 1 уточняющий вопрос.\n"
        "Не выдумывай патчи/мету. Если не уверен — общие принципы.\n"
        "Фокус: позиция, тайминг, инфо, дисциплина, микромув, отдача.\n"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": coach_frame},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
        {"role": "system", "content": f"Текущая игра: {game}. {GAME_PILLARS.get(game, '')}"},
        {"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"},
    ]
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    max_out = 700 if verbosity == "talkative" else 520

    with _ai_sem:
        for attempt in range(3):
            try:
                resp = _openai_create(messages, max_out)
                out = (resp.choices[0].message.content or "").strip()
                return out or "Не получил ответ. Напиши ещё раз 🙌"

            except RateLimitError:
                time.sleep(2.0 + attempt * 2.0)
                if attempt == 2:
                    return "⏳ AI: лимит/перегруз. Подожди 20–60 сек и попробуй снова."
            except APIConnectionError:
                time.sleep(1.0 + attempt * 1.5)
                if attempt == 2:
                    return "⚠️ AI: проблема соединения. Попробуй ещё раз через минуту."
            except AuthenticationError:
                return "❌ AI: неверный ключ OPENAI_API_KEY."
            except BadRequestError:
                return f"❌ AI: bad request. Модель: {OPENAI_MODEL}."
            except APIError:
                time.sleep(1.0 + attempt)
                if attempt == 2:
                    return "⚠️ AI: временная ошибка сервиса. Попробуй ещё раз."
            except Exception:
                log.exception("OpenAI unknown error")
                return "⚠️ AI: неизвестная ошибка. Напиши /status."

def ai_test() -> str:
    try:
        r = _openai_create([{"role": "user", "content": "Ответь одним словом: OK"}], 10)
        out = (r.choices[0].message.content or "").strip()
        return f"✅ /ai_test: {out or 'OK'} (model={OPENAI_MODEL})"
    except Exception as e:
        return f"⚠️ /ai_test: {type(e).__name__}"

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
        "/game warzone|bf6|bo7\n"
        "/reset — очистить память\n"
    )

def status_text() -> str:
    return (
        "🧾 Status\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"ANIMATION: {'ON' if ANIMATION else 'OFF'}\n"
        f"MAX_CONCURRENT_AI: {MAX_CONCURRENT_AI}\n\n"
        "Если ловишь Conflict 409 — значит запущены 2 инстанса (Instance count > 1) или есть webhook.\n"
    )

def handle_message(chat_id: int, text: str):
    if throttle(chat_id):
        return

    p = ensure_profile(chat_id)
    t = text.strip()

    if t.startswith("/start") or t.startswith("/help"):
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
        send_message(chat_id, "🧹 Сбросил профиль и память.")
        return

    if t.startswith("/persona"):
        parts = t.split()
        if len(parts) >= 2 and parts[1].lower() in ("spicy", "chill", "pro"):
            p["persona"] = parts[1].lower()
            send_message(chat_id, f"✅ Persona = {p['persona']}")
        else:
            send_message(chat_id, "Используй: /persona spicy | chill | pro")
        return

    if t.startswith("/talk"):
        parts = t.split()
        if len(parts) >= 2 and parts[1].lower() in ("short", "normal", "talkative"):
            p["verbosity"] = parts[1].lower()
            send_message(chat_id, f"✅ Talk = {p['verbosity']}")
        else:
            send_message(chat_id, "Используй: /talk short | normal | talkative")
        return

    if t.startswith("/game"):
        parts = t.split()
        if len(parts) >= 2 and parts[1].lower() in ("warzone", "bf6", "bo7"):
            p["game"] = parts[1].lower()
            send_message(chat_id, f"✅ Игра = {p['game']}")
        else:
            send_message(chat_id, "Используй: /game warzone | bf6 | bo7")
        return

    update_memory(chat_id, "user", t)

    tmp_id = None
    stop = threading.Event()
    if ANIMATION:
        tmp_id = send_message(chat_id, random.choice(THINKING_LINES))
        threading.Thread(target=typing_loop, args=(chat_id, stop), daemon=True).start()
        if tmp_id:
            threading.Thread(target=pulse_edit_loop, args=(chat_id, tmp_id, stop, "⌛ Думаю"), daemon=True).start()

    try:
        reply = openai_reply(chat_id, t)
    finally:
        stop.set()

    update_memory(chat_id, "assistant", reply)

    if tmp_id:
        try:
            edit_message(chat_id, tmp_id, reply)
        except Exception:
            send_message(chat_id, reply)
    else:
        send_message(chat_id, reply)

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
                log.warning("Telegram conflict. Backoff %ss: %s", sleep_s, s)
                time.sleep(sleep_s)
                continue
            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2.0)

        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2.0)

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _ok(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
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
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    run_http_server()
