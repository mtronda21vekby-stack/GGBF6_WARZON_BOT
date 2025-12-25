# -*- coding: utf-8 -*-
"""fps_coach_bot_public_v5.py

Исправлено:
- битые символы (все строки в UTF-8)
- усилена стабильность: per-chat lock, антифлуд, безопасная анимация
- webhook удаляется при старте (частая причина Conflict 409)
- готово для публичного запуска на Render (Instances=1)
"""

from __future__ import annotations

import os
import time
import json
import threading
import logging
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from openai import OpenAI
    from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore
    APIConnectionError = AuthenticationError = RateLimitError = BadRequestError = APIError = Exception  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_bot")

# ===== ENV =====
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

UI_DEFAULT = os.getenv("UI_DEFAULT", "show").strip().lower()
if UI_DEFAULT not in ("show", "hide"):
    UI_DEFAULT = "show"

MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "2000"))

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN")

# ===== OpenAI =====
openai_client = None
OPENAI_ENABLED = bool(OPENAI_API_KEY) and (OpenAI is not None)
if OPENAI_ENABLED:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=30, max_retries=0)
    except TypeError:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# ===== HTTP session =====
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-bot/5.0"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50))

# ===== State =====
def _safe_mkdir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

_safe_mkdir(DATA_DIR)

USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
LAST_MSG_TS: Dict[int, float] = {}
CHAT_LOCKS: Dict[int, threading.Lock] = {}

MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))
_state_lock = threading.Lock()

def _get_chat_lock(chat_id: int) -> threading.Lock:
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

# ===== Knowledge base =====
GAME_KB: Dict[str, Dict[str, Any]] = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "pillars": (
            "🧠 Warzone — фундамент\n"
            "• Позиция/тайминг > киллы\n"
            "• Инфо: радар/звук/пинги\n"
            "• Пре-эйм + игра от укрытий\n"
            "• Ротации заранее\n"
            "• Контакт → репозиция\n"
        ),
        "settings": (
            "🌑 Warzone — базовый сетап (контроллер)\n"
            "• Sens: 6–8 (старт 7/7)\n"
            "• ADS: 0.90 low / 0.85 high\n"
            "• Aim Assist: Dynamic (если мимо → Standard)\n"
            "• Deadzone min: 0.05 (дрифт → 0.07–0.10)\n"
            "• FOV: 105–110 | ADS FOV Affected: ON | Weapon FOV: Wide\n"
            "• Camera Movement: Least\n"
        ),
        "drills": {
            "aim": "🎯 Aim (20м)\n10м warm-up\n5м трекинг\n5м микро",
            "recoil": "🔫 Recoil (20м)\n5м 15–25м\n10м 25–40м\n5м дисциплина",
            "movement": "🕹 Movement (15м)\nугол→слайд→пик\nджамп-пики\nрепозиция",
        },
        "plan": (
            "📅 План 7 дней — Warzone\n"
            "Д1–2: warm-up 10м + aim 15м + movement 10м + мини-разбор 5м\n"
            "Д3–4: warm-up 10м + дуэли/углы 15м + дисциплина 10м + вывод 5м\n"
            "Д5–6: warm-up 10м + игра от инфо 20м + фиксация ошибок 5м\n"
            "Д7: 30–60м игры + разбор 2 смертей 10м\n"
        ),
        "vod": (
            "📼 VOD-шаблон (Warzone)\n"
            "1) Режим/сквад\n2) Где бой\n3) Как умер\n"
            "4) Ресурсы (плиты/смок/саморез)\n5) План (пуш/отход/ротация)\n"
        ),
    },
    "bo7": {
        "name": "Call of Duty: BO7",
        "pillars": (
            "🧠 BO7 — фундамент\n"
            "• Центр экрана + префайр\n"
            "• Тайминги: пик по инфе\n"
            "• 2 сек на позиции → смена\n"
            "• Репик только с другого угла\n"
        ),
        "settings": (
            "🌑 BO7 — базовый сетап (контроллер)\n"
            "• Sens: 6–8 (перелетаешь → -1)\n"
            "• ADS: 0.80–0.95\n"
            "• Deadzone min: 0.03–0.07\n"
            "• Curve: Dynamic/Standard\n"
            "• FOV: 100–115\n"
        ),
        "drills": {
            "aim": "🎯 Aim (20м)\nпрефайр\nтрекинг\nмикро",
            "recoil": "🔫 Recoil (15м)\nкороткие очереди\nпервая пуля",
            "movement": "🕹 Movement (15–20м)\nрепики\nтайминг\nстрейф",
        },
        "plan": (
            "📅 План 7 дней — BO7\n"
            "Д1–2: aim 20м + movement 10м\n"
            "Д3–4: углы/тайминги 25м + мини-разбор 5м\n"
            "Д5–6: дуэли 30м\n"
            "Д7: 45–60м + разбор 2–3 смертей\n"
        ),
        "vod": "📼 BO7: режим/карта, смерть, инфо (радар/звук), что хотел сделать.",
    },
    "bf6": {
        "name": "BF6",
        "pillars": (
            "🧠 BF6 — фундамент\n"
            "• Линии фронта/спавны\n"
            "• Пик→инфо→откат\n"
            "• Серия → репозиция\n"
        ),
        "settings": (
            "🌑 BF6 — база\n"
            "• Sens: средняя, ADS ниже\n"
            "• Deadzone: минимум без дрифта\n"
            "• FOV: высокий (комфорт)\n"
            "• Контакт → смена позиции\n"
        ),
        "drills": {
            "aim": "🎯 Aim (15–20м)\nпрефайр\nтрекинг\nрепозиция",
            "recoil": "🔫 Recoil (15м)\nкороткие очереди\nконтроль",
            "movement": "🕹 Movement (15м)\nвыглянул→инфо→откат\nрепик с другого угла",
        },
        "plan": (
            "📅 План 7 дней — BF6\n"
            "Д1–2: aim 15м + позиции 15м\n"
            "Д3–4: фронт/спавны 20м + дуэли 10м\n"
            "Д5–6: игра от инфо 25м + разбор 5м\n"
            "Д7: 45–60м + разбор 2 смертей\n"
        ),
        "vod": "📼 BF6: карта/режим, класс, где умер/почему, что хотел сделать.",
    },
}

# ===== Prompts =====
SYSTEM_PROMPT = (
    "Ты харизматичный FPS-коуч по Warzone/BO7/BF6. Пишешь по-русски.\n"
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
    "chill": "Стиль: спокойно и дружелюбно, мягкий юмор.",
    "pro": "Стиль: строго по делу, минимум шуток.",
}
VERBOSITY_HINT = {
    "short": "Длина: коротко (до ~10 строк).",
    "normal": "Длина: обычно (10–18 строк).",
    "talkative": "Длина: подробнее (до ~30 строк), +1–2 доп. совета.",
}
THINKING_LINES = [
    "🧠 Думаю… сейчас будет жара 😈",
    "⌛ Секунду… раскладываю по полочкам 🧩",
    "🎮 Окей, коуч на связи. Сейчас разнесём 👊",
    "🌑 Анализирую… не моргай 😈",
]

# ===== Telegram helpers =====
def _sleep_backoff(i: int) -> None:
    time.sleep((0.6 * (i + 1)) + random.random() * 0.25)

def tg_request(method: str, *, params=None, payload=None, is_post: bool = False, retries: int = TG_RETRIES) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last: Optional[Exception] = None
    for i in range(retries):
        try:
            r = SESSION.post(url, json=payload, timeout=HTTP_TIMEOUT) if is_post else SESSION.get(url, params=params, timeout=HTTP_TIMEOUT)
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
    raise last if last else RuntimeError("Telegram request failed")

def send_message(chat_id: int, text: str, reply_markup=None) -> Optional[int]:
    chunks = [text[i:i+3900] for i in range(0, len(text), 3900)] or [""]
    last_id: Optional[int] = None
    for ch in chunks:
        res = tg_request("sendMessage", payload={"chat_id": chat_id, "text": ch, "reply_markup": reply_markup}, is_post=True)
        last_id = res.get("result", {}).get("message_id")
    return last_id

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

# ===== Animation =====
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
                edit_message(chat_id, message_id, base + ("." * dots), reply_markup=None)
            except Exception:
                pass
            last_edit = now
        stop_event.wait(0.2)

# ===== Profile / UI =====
def ensure_profile(chat_id: int) -> Dict[str, Any]:
    default_coach = OPENAI_ENABLED
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

def update_memory(chat_id: int, role: str, content: str) -> None:
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS * 2:]

def maybe_kb(chat_id: int):
    p = ensure_profile(chat_id)
    return None if p.get("ui", "show") == "hide" else kb_main(chat_id)

def parse_profile_line(text: str) -> Tuple[str, str, str]:
    t = text.lower()
    platform = ""
    if "xbox" in t:
        platform = "Xbox"
    elif "ps" in t or "playstation" in t:
        platform = "PlayStation"
    elif "kbm" in t or "мыш" in t or "клав" in t:
        platform = "KBM"

    style = ""
    if "агро" in t or "aggressive" in t:
        style = "Aggressive"
    elif "спокой" in t or "calm" in t or "деф" in t:
        style = "Calm"

    goal = ""
    if "aim" in t or "аим" in t:
        goal = "Aim"
    elif "recoil" in t or "отдач" in t:
        goal = "Recoil"
    elif "rank" in t or "ранг" in t:
        goal = "Rank"
    return platform, style, goal

# ===== Keyboards =====
def kb_main(chat_id: int) -> Dict[str, Any]:
    p = ensure_profile(chat_id)
    coach_on = "🧠 ON" if p.get("coach", True) else "🧠 OFF"
    ui = p.get("ui", "show")
    ui_btn = "🕶 Hide UI" if ui == "show" else "🕶 Show UI"
    return {
        "inline_keyboard": [
            [{"text": "🌑 Warzone", "callback_data": "game:warzone"},
             {"text": "🌑 BF6", "callback_data": "game:bf6"},
             {"text": "🌑 BO7", "callback_data": "game:bo7"}],
            [{"text": "⚙️ Settings", "callback_data": "action:settings"},
             {"text": "💪 Drills", "callback_data": "action:drills"}],
            [{"text": "📅 Plan", "callback_data": "action:plan"},
             {"text": "📼 VOD", "callback_data": "action:vod"}],
            [{"text": "👤 Profile", "callback_data": "action:profile"},
             {"text": coach_on, "callback_data": "action:coach"}],
            [{"text": "😈 Persona", "callback_data": "action:persona"},
             {"text": "🗣 Talk", "callback_data": "action:talk"}],
            [{"text": ui_btn, "callback_data": "action:ui"}],
            [{"text": "🧹 Reset", "callback_data": "action:reset"}],
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
            [{"text": "⬅️ Menu", "callback_data": "action:menu"}],
        ]
    }

# ===== Text blocks =====
def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "🌑 FPS Coach Bot\n"
        f"Игра: {GAME_KB[p['game']]['name']}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'} | Persona: {p.get('persona')} | Talk: {p.get('verbosity')} | UI: {p.get('ui')}\n\n"
        "Команды: /help\n"
        "Жми кнопки 👇"
    )

def help_text() -> str:
    return (
        "🆘 Команды\n"
        "/start или /menu — меню\n"
        "/settings /plan /vod /drills\n"
        "/game warzone|bf6|bo7\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/ui show|hide\n"
        "/ai_test — проверка AI\n"
        "/status — диагностика\n"
    )

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "👤 Профиль\n"
        f"Игра: {GAME_KB[p['game']]['name']}\n"
        f"Платформа: {p.get('platform') or '—'}\n"
        f"Стиль: {p.get('style') or '—'}\n"
        f"Цель: {p.get('goal') or '—'}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n"
        f"Persona: {p.get('persona')}\n"
        f"Talk: {p.get('verbosity')}\n"
        f"UI: {p.get('ui')}\n"
    )

def status_text() -> str:
    ok_key = "✅" if OPENAI_ENABLED else "❌"
    ok_tg = "✅" if bool(TELEGRAM_BOT_TOKEN) else "❌"
    return (
        "🧾 Status\n"
        f"TELEGRAM_BOT_TOKEN: {ok_tg}\n"
        f"OPENAI_API_KEY: {ok_key}\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"STATE_PATH: {STATE_PATH}\n\n"
        "Если ловишь Conflict 409 — значит запущено >1 инстанса или включён webhook. На Render: Instances = 1."
    )

def set_game(chat_id: int, game_key: str) -> str:
    p = ensure_profile(chat_id)
    if game_key not in GAME_KB:
        return "Не знаю такую игру."
    p["game"] = game_key
    return f"✅ Игра: {GAME_KB[game_key]['name']}"

# ===== OpenAI =====
def _openai_create(messages: List[Dict[str, str]], max_tokens: int):
    try:
        return openai_client.chat.completions.create(model=OPENAI_MODEL, messages=messages, max_completion_tokens=max_tokens)
    except TypeError:
        return openai_client.chat.completions.create(model=OPENAI_MODEL, messages=messages, max_tokens=max_tokens)

def openai_reply_safe(chat_id: int, user_text: str) -> str:
    if not OPENAI_ENABLED or openai_client is None:
        return "⚠️ AI выключен: нет OPENAI_API_KEY (Render → Environment Variables → Redeploy)."

    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    coach_frame = (
        "Пиши конкретно и полезно. Если инфы мало — спроси 1 уточнение.\n"
        "Не выдумывай патчи/мету. Если не уверен — общие принципы.\n"
        "Фокус: позиция, тайминг, инфо, дисциплина, микромув, отдача.\n"
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": coach_frame},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
        {"role": "system", "content": f"Текущая игра: {kb['name']}. {kb.get('pillars','')}"},
        {"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"},
    ]
    messages.extend(USER_MEMORY.get(chat_id, []))
    messages.append({"role": "user", "content": user_text})

    max_out = 650 if verbosity == "talkative" else 520

    for attempt in range(2):
        try:
            resp = _openai_create(messages, max_out)
            out = (resp.choices[0].message.content or "").strip()
            return out or "Не получил ответ. Напиши ещё раз 🙌"
        except APIConnectionError:
            if attempt == 0:
                time.sleep(0.9)
                continue
            return "⚠️ AI: проблема соединения. Попробуй ещё раз через минуту."
        except AuthenticationError:
            return "❌ AI: неверный OPENAI_API_KEY. Проверь Render → Env → Redeploy."
        except RateLimitError:
            return "⏳ AI: лимит/перегруз. Подожди 20–60 сек и попробуй снова."
        except BadRequestError:
            return f"❌ AI: bad request. Модель: {OPENAI_MODEL}."
        except APIError:
            return "⚠️ AI: временная ошибка сервиса. Попробуй ещё раз через минуту."
        except Exception:
            log.exception("OpenAI unknown error")
            return "⚠️ AI: неизвестная ошибка. Напиши /status."

def ai_test() -> str:
    if not OPENAI_ENABLED or openai_client is None:
        return "❌ /ai_test: нет OPENAI_API_KEY."
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

# ===== Throttle =====
def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False

# ===== Handlers =====
def handle_message(chat_id: int, text: str) -> None:
    if not text:
        return
    if len(text) > MAX_INPUT_CHARS:
        send_message(chat_id, f"✋ Слишком длинно ({len(text)} символов). Сократи до {MAX_INPUT_CHARS} и отправь снова.", reply_markup=maybe_kb(chat_id))
        return
    if throttle(chat_id):
        return

    p = ensure_profile(chat_id)
    low = text.lower().strip()

    if low in ("/help", "help"):
        send_message(chat_id, help_text(), reply_markup=maybe_kb(chat_id))
        return

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
        send_message(chat_id, "🧹 Сбросил профиль и память.", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/persona"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("spicy", "chill", "pro"):
            p["persona"] = parts[1].lower()
            save_state()
            send_message(chat_id, f"✅ Persona = {p['persona']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /persona spicy | chill | pro", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/talk"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("short", "normal", "talkative"):
            p["verbosity"] = parts[1].lower()
            save_state()
            send_message(chat_id, f"✅ Talk = {p['verbosity']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /talk short | normal | talkative", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/ui"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].lower() in ("show", "hide"):
            p["ui"] = parts[1].lower()
            save_state()
            send_message(chat_id, f"✅ UI = {p['ui']}", reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /ui show | /ui hide", reply_markup=maybe_kb(chat_id))
        return

    if text.startswith("/game"):
        parts = text.split()
        if len(parts) >= 2:
            msg = set_game(chat_id, parts[1].lower())
            save_state()
            send_message(chat_id, msg, reply_markup=maybe_kb(chat_id))
        else:
            send_message(chat_id, "Используй: /game warzone | bf6 | bo7", reply_markup=maybe_kb(chat_id))
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
        send_message(chat_id, "Выбери дрилл:", reply_markup=kb_drills(chat_id))
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
        send_message(chat_id, "✅ Профиль обновлён.

" + profile_text(chat_id), reply_markup=maybe_kb(chat_id))
        return

    if not p.get("coach", True):
        send_message(chat_id, "🧠 Coach OFF. Включи в меню (кнопка 🧠 ON/OFF).", reply_markup=maybe_kb(chat_id))
        return

    lock = _get_chat_lock(chat_id)
    if not lock.acquire(blocking=False):
        send_message(chat_id, "⌛ Я уже отвечаю на прошлое сообщение. Подожди секунду и напиши снова 🙌", reply_markup=maybe_kb(chat_id))
        return

    try:
        update_memory(chat_id, "user", text)
        tmp_id = send_message(chat_id, random.choice(THINKING_LINES), reply_markup=None)

        stop = threading.Event()
        threading.Thread(target=typing_loop, args=(chat_id, stop), daemon=True).start()
        if tmp_id:
            threading.Thread(target=pulse_edit_loop, args=(chat_id, tmp_id, stop, "⌛ Думаю"), daemon=True).start()

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
    finally:
        try:
            lock.release()
        except Exception:
            pass

def handle_callback(cb: Dict[str, Any]) -> None:
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data", "")

    if not cb_id or not chat_id or not message_id:
        if cb_id:
            answer_callback(cb_id)
        return

    chat_id = int(chat_id)
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
            edit_message(chat_id, message_id, "🧹 Сбросил профиль и память.", reply_markup=maybe_kb(chat_id))
        elif data == "action:drills":
            edit_message(chat_id, message_id, "Выбери дрилл:", reply_markup=kb_drills(chat_id))
        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            drills = GAME_KB[p["game"]]["drills"]
            edit_message(chat_id, message_id, drills.get(kind, "Доступно: aim/recoil/movement"), reply_markup=kb_drills(chat_id))
        else:
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=maybe_kb(chat_id))
    finally:
        answer_callback(cb_id)

# ===== Polling loop =====
POLLING_STARTED = False

def run_telegram_bot() -> None:
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
                    handle_message(int(chat_id), text)
                except Exception:
                    log.exception("Message handling error")
                    send_message(int(chat_id), "Ошибка 😅 Попробуй ещё раз.", reply_markup=maybe_kb(int(chat_id)))
        except RuntimeError as e:
            s = str(e)
            if "Conflict:" in s and "getUpdates" in s:
                sleep_s = random.randint(CONFLICT_BACKOFF_MIN, CONFLICT_BACKOFF_MAX)
                log.warning("Telegram conflict. Backoff %ss: %s", sleep_s, s)
                time.sleep(sleep_s)
                continue
            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2)
        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)

# ===== Health endpoint =====
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
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    run_http_server()
