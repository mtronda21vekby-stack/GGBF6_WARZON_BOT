import os
import time
import json
import threading
import logging
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError, APIError


# =========================
# Logging
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("bot")


# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

HTTP_TIMEOUT = 25
TG_LONGPOLL_TIMEOUT = 50
TG_RETRIES = 5

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN (BotFather token)")

# OpenAI client (таймаут + меньше шанс зависнуть)
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=30,
            max_retries=1,  # ретраи делаем сами ниже
        )
    except TypeError:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


# =========================
# Requests session (faster + stabler)
# =========================
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-telegram-bot/2.2"})
SESSION.adapters["https://"] = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)


# =========================
# Thread-safety locks (усилили)
# =========================
PROFILE_LOCK = threading.Lock()
MEMORY_LOCK = threading.Lock()
THROTTLE_LOCK = threading.Lock()
KB_LOCK = threading.Lock()


# =========================
# Data (in-memory)
# =========================
USER_PROFILE = {}  # chat_id -> dict
USER_MEMORY = {}   # chat_id -> list[{role, content}]
MEMORY_MAX_TURNS = 8

LAST_MSG_TS = {}   # chat_id -> float
MIN_SECONDS_BETWEEN_MSG = 0.35


# =========================
# Knowledge base (static)
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "settings": (
            "🎮 Warzone — настройки (контроллер)\n"
            "• Sens: 7/7 (мимо → 6/6)\n"
            "• ADS: 0.90 low / 0.85 high\n"
            "• Aim Assist: Dynamic (если не заходит → Standard)\n"
            "• Deadzone min: 0.05 (дрифт → 0.07–0.10)\n"
            "• FOV: 105–110 | ADS FOV Affected: ON | Weapon FOV: Wide\n"
            "• Camera Movement: Least\n"
        ),
        "drills": {
            "aim": "🎯 Warzone Aim (20м)\n10м warm-up\n5м трекинг\n5м микро-коррекции",
            "recoil": "🔫 Warzone Recoil (20м)\n5м 15–25м\n10м 25–40м\n5м дисциплина",
            "movement": "🕹 Warzone Movement (15м)\nугол→слайд→пик\nджамп-пики\nreposition",
        },
        "plan": (
            "📅 План на 7 дней — Warzone\n"
            "Д1–2: warm-up 10м + aim 15м + movement 10м + мини-разбор 5м\n"
            "Д3–4: warm-up 10м + дуэли/углы 15м + дисциплина 10м + вывод 5м\n"
            "Д5–6: warm-up 10м + игра от инфо 20м + фиксация ошибок 5м\n"
            "Д7: 30–60м игры + разбор 2 смертей 10м\n"
        ),
        "vod": (
            "📼 VOD/ситуация (шаблон)\n"
            "1) Режим (solo/duo/trio/quad)\n"
            "2) Где бой (дом/крыша/поле)\n"
            "3) Как умер (угол, чем наказали)\n"
            "4) Ресурсы (плиты/смок/стим/саморес)\n"
            "5) Что хотел сделать (пуш/отход/ротация)\n\n"
            "Я верну: ошибка №1 + 1–2 действия + мини-дрилл 💪"
        ),
        "pillars": (
            "🧠 Warzone — база\n"
            "1) Позиция и тайминг\n2) Инфо\n3) Выживание > киллы\n"
            "4) Пре-эйм решает\n5) Микро без паники\n"
        ),
    },
    "bf6": {
        "name": "BF6",
        "settings": (
            "🎮 BF6 — настройки (база)\n"
            "• Sens: средняя, ADS чуть ниже\n"
            "• Deadzone: минимум без дрифта\n"
            "• FOV: высокий (комфорт)\n"
            "• После контакта — смена позиции\n"
        ),
        "drills": {
            "aim": "🎯 BF6 Aim (15–20м)\nпрефайр углов\nтрекинг\nсмена позиции после серии",
            "movement": "🕹 BF6 Movement (15м)\nвыглянул→дал инфо→откатился\nрепик с другого угла",
            "recoil": "🔫 BF6 Recoil (15м)\nкороткие очереди\nконтроль на средней",
        },
        "plan": (
            "📅 План на 7 дней — BF6\n"
            "Д1–2: aim 15м + позиции 15м\n"
            "Д3–4: линии фронта/спавны 20м + дуэли 10м\n"
            "Д5–6: игра от инфо 25м + разбор 5м\n"
            "Д7: 45–60м + разбор 2 смертей\n"
        ),
        "vod": "📼 BF6 разбор: карта/режим, класс, где умер/почему, что хотел сделать.",
        "pillars": "🧠 BF6: линии фронта, спавны, минимальный пик, ротации.",
    },
    "bo7": {
        "name": "BO7",
        "settings": (
            "🎮 BO7 — настройки (контроллер)\n"
            "• Sens: 6–8 (если перелетаешь → -1)\n"
            "• ADS: 0.80–0.95 (стабильность > скорость)\n"
            "• Deadzone min: 0.03–0.07 (дрифт → 0.08+)\n"
            "• Curve: Dynamic/Standard\n"
            "• FOV: 100–115\n\n"
            "🔥 Быстрые правила\n"
            "• После килла: репозиция 1–2 сек\n"
            "• Проиграл дуэль → упрощай углы\n"
            "• Короткий пик → инфо → откат → другой пик\n"
        ),
        "drills": {
            "aim": "🎯 BO7 Aim (20м)\n5м префайр\n7м трекинг\n5м микро\n3м дисциплина",
            "movement": "🕹 BO7 Movement (15–20м)\nрепики с другого угла\nтайминг\nстрейф + центр",
            "recoil": "🔫 BO7 Recoil (15м)\nкороткие очереди\nпервая пуля\nне жадничай",
        },
        "plan": (
            "📅 План на 7 дней — BO7\n"
            "Д1–2: aim 20м + movement 10м\n"
            "Д3–4: углы/тайминги 25м + мини-разбор 5м\n"
            "Д5–6: дуэли 30м\n"
            "Д7: 45–60м + разбор 2–3 смертей\n"
        ),
        "vod": "📼 BO7 разбор: режим/карта, момент смерти, инфо (радар/звук), что хотел сделать.",
        "pillars": "🧠 BO7: центр+префайр, тайминги, 2 сек на позиции→смена, репик только с другого угла.",
    },
}


# =========================
# Persistent KB (обучаемая база, сохраняется в файл)
# =========================
# На Render лучше сделать Persistent Disk и выставить:
# KB_PATH=/var/data/kb_store.json
KB_PATH = os.getenv("KB_PATH", "kb_store.json").strip()

MAX_KB_ITEMS_PER_TOPIC = 80
MAX_KB_CHARS_PER_INJECT = 8000  # чтобы не убить контекст модельке
DEFAULT_TOPICS = [
    "aim", "movement", "recoil", "positioning", "rotations", "endgame",
    "teamplay", "gunfight", "mindset", "settings", "vod_review"
]

EXTRA_KB = {"warzone": {}, "bo7": {}, "bf6": {}}


def kb_load():
    global EXTRA_KB
    with KB_LOCK:
        try:
            if os.path.exists(KB_PATH):
                with open(KB_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for g in ("warzone", "bo7", "bf6"):
                    data.setdefault(g, {})
                    if not isinstance(data[g], dict):
                        data[g] = {}
                EXTRA_KB = data
                log.info("KB loaded: %s", KB_PATH)
        except Exception:
            log.exception("KB load failed, using empty KB")
            EXTRA_KB = {"warzone": {}, "bo7": {}, "bf6": {}}


def kb_save():
    with KB_LOCK:
        try:
            with open(KB_PATH, "w", encoding="utf-8") as f:
                json.dump(EXTRA_KB, f, ensure_ascii=False, indent=2)
        except Exception:
            log.exception("KB save failed")


def kb_add(game: str, topic: str, text: str) -> str:
    game = (game or "").strip().lower()
    topic = (topic or "").strip().lower()
    text = (text or "").strip()

    if game not in ("warzone", "bo7", "bf6"):
        return "❌ game должен быть: warzone | bo7 | bf6"
    if not topic:
        return "❌ topic пустой. Пример: /teach warzone rotations <текст>"
    if len(text) < 20:
        return "❌ текст слишком короткий. Напиши выжимку (20+ символов)."

    with KB_LOCK:
        EXTRA_KB.setdefault(game, {})
        EXTRA_KB[game].setdefault(topic, [])
        if len(EXTRA_KB[game][topic]) >= MAX_KB_ITEMS_PER_TOPIC:
            EXTRA_KB[game][topic] = EXTRA_KB[game][topic][-MAX_KB_ITEMS_PER_TOPIC + 1:]
        EXTRA_KB[game][topic].append(text)

    kb_save()
    return f"✅ Запомнил ({game}/{topic}). +1"


def kb_get(game: str, topic: str, limit_items: int = 6) -> str:
    game = (game or "").strip().lower()
    topic = (topic or "").strip().lower()
    with KB_LOCK:
        items = EXTRA_KB.get(game, {}).get(topic, [])
        if not items:
            return ""
        picked = items[-limit_items:]
    blob = "\n\n".join([f"• {x}" for x in picked]).strip()
    if len(blob) > MAX_KB_CHARS_PER_INJECT:
        blob = blob[-MAX_KB_CHARS_PER_INJECT:]
    return blob


def kb_summary(game: str) -> str:
    game = (game or "").strip().lower()
    with KB_LOCK:
        g = EXTRA_KB.get(game, {})
        topics = sorted(g.keys()) if isinstance(g, dict) else []
        total = sum(len(g[t]) for t in topics) if topics else 0
    if not topics:
        return f"📚 KB({game}): пусто.\nДобавь: /teach {game} aim <текст>"
    return (
        f"📚 KB({game}): тем={len(topics)}, заметок={total}\n"
        f"Темы: {', '.join(topics[:25])}{'...' if len(topics) > 25 else ''}"
    )


def lesson_pack(game: str, topic: str) -> str:
    topic = (topic or "").strip().lower()
    base = kb_get(game, topic, limit_items=8)
    if not base:
        return (
            f"📘 Урок: {topic}\n"
            "Пока нет твоих материалов по этой теме.\n"
            f"Добавь: /teach {game} {topic} <выжимка/совет>\n"
        )
    return (
        f"📘 Урок: {topic}\n"
        "🔑 Суть (из твоей базы):\n"
        f"{base}\n\n"
        "✅ Домашка (10–20 минут):\n"
        "1) 2 матча — держи фокус только на этой теме\n"
        "2) Запиши 2 ошибки и 1 удачный момент\n"
        "3) Скинь сюда: что было → что сделал → что вышло\n"
    )


# =========================
# Persona + style (живость)
# =========================
SYSTEM_PROMPT = (
    "Ты харизматичный FPS-коуч по Warzone/BF6/BO7. Пишешь по-русски.\n"
    "Тон: уверенный, быстрый, с юмором и лёгкими подколами (без токсичности и унижений).\n"
    "Структура ответа ВСЕГДА:\n"
    "1) 🎯 Диагноз (1 главная ошибка)\n"
    "2) ✅ Что делать (2 конкретных действия прямо сейчас)\n"
    "3) 🧪 Дрилл (1 мини-упражнение на 5–10 минут)\n"
    "4) 😈 Панчик/мотивация (1 короткая фраза)\n\n"
    "Запрещено: читы/хаки/обход античита. Если просят — откажи и предложи честные тренировки."
)

PERSONA_HINT = {
    "spicy": "Стиль: дерзкий, смешной, короткие панчи. Никакой грубости.",
    "chill": "Стиль: спокойный, дружелюбный, мягкий юмор.",
    "pro": "Стиль: максимально профессионально, строго по делу, минимум шуток.",
}

VERBOSITY_HINT = {
    "short": "Длина: очень коротко (до 6–10 строк).",
    "normal": "Длина: обычно (10–18 строк).",
    "talkative": "Длина: чуть подробнее (15–30 строк), добавь 1–2 доп. совета.",
}

THINKING_LINES = [
    "🧠 Думаю… сейчас будет жара 😈",
    "⌛ Секунду… раскладываю по полочкам 🧩",
    "🎮 Окей, коуч на связи. Сейчас разнесём 👊",
]


# =========================
# Telegram helpers
# =========================
def _sleep_backoff(i: int, retry_after: float | None = None):
    if retry_after is not None:
        time.sleep(min(6.0, max(0.5, retry_after)))
        return
    time.sleep((0.7 * (i + 1)) + random.random() * 0.25)


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

            # если телега попросила подождать — уважаем
            # format: {"ok": false, "error_code": 429, "description": "Too Many Requests: retry after X"}
            if not data.get("ok") and data.get("error_code") == 429:
                retry_after = None
                try:
                    retry_after = float(data.get("parameters", {}).get("retry_after", 1))
                except Exception:
                    retry_after = 1.2
                last = RuntimeError(data.get("description", "Telegram 429"))
                _sleep_backoff(i, retry_after=retry_after)
                continue

            if r.status_code == 200 and data.get("ok"):
                return data

            desc = data.get("description", f"Telegram HTTP {r.status_code}")
            last = RuntimeError(desc)

        except Exception as e:
            last = e

        _sleep_backoff(i)

    raise last


def send_message(chat_id: int, text: str, reply_markup=None):
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
    last_msg_id = None
    for ch in chunks:
        res = tg_request(
            "sendMessage",
            payload={"chat_id": chat_id, "text": ch, "reply_markup": reply_markup},
            is_post=True
        )
        last_msg_id = res.get("result", {}).get("message_id")
    return last_msg_id


def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None):
    tg_request(
        "editMessageText",
        payload={"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup},
        is_post=True
    )


def answer_callback(callback_id: str):
    tg_request("answerCallbackQuery", payload={"callback_query_id": callback_id}, is_post=True)


def send_chat_action(chat_id: int, action: str = "typing"):
    try:
        tg_request("sendChatAction", payload={"chat_id": chat_id, "action": action}, is_post=True, retries=2)
    except Exception:
        pass


# =========================
# "Animation" helpers (усилили: не спамим слишком часто)
# =========================
def typing_loop(chat_id: int, stop_event: threading.Event, interval: float = 4.0):
    while not stop_event.is_set():
        send_chat_action(chat_id, "typing")
        stop_event.wait(interval)


def pulse_edit_loop(chat_id: int, message_id: int, stop_event: threading.Event, base: str = "⌛ Думаю"):
    # edit раз в ~1 сек, чтобы не ловить 429
    dots = 0
    last_edit = 0.0
    while not stop_event.is_set():
        now = time.time()
        if now - last_edit >= 1.05:
            dots = (dots + 1) % 4
            txt = base + ("." * dots)
            try:
                edit_message(chat_id, message_id, txt, reply_markup=None)
            except Exception:
                pass
            last_edit = now
        stop_event.wait(0.2)


def quick_loading_edit(chat_id: int, message_id: int, text: str = "⌛ Загружаю…"):
    try:
        edit_message(chat_id, message_id, text, reply_markup=None)
    except Exception:
        pass


# =========================
# UI / profile
# =========================
def ensure_profile(chat_id: int) -> dict:
    default_coach = bool(OPENAI_API_KEY)
    with PROFILE_LOCK:
        return USER_PROFILE.setdefault(chat_id, {
            "game": "warzone",
            "platform": "",
            "style": "",
            "goal": "",
            "coach": default_coach,
            "persona": "spicy",      # spicy | chill | pro
            "verbosity": "normal",   # short | normal | talkative
        })


def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    persona = p.get("persona", "spicy")
    verb = p.get("verbosity", "normal")
    return (
        "👤 Профиль\n"
        f"Игра: {GAME_KB[p['game']]['name']}\n"
        f"Платформа: {p.get('platform') or '—'}\n"
        f"Стиль: {p.get('style') or '—'}\n"
        f"Цель: {p.get('goal') or '—'}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n"
        f"Persona: {persona}\n"
        f"Verbosity: {verb}\n\n"
        "Команды:\n"
        "/persona spicy|chill|pro\n"
        "/talk short|normal|talkative\n"
        "/kb, /topics, /lesson <topic>\n"
        "/teach warzone|bo7|bf6 <topic> <текст>\n"
    )


def parse_profile_line(text: str):
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


def update_memory(chat_id: int, role: str, content: str):
    with MEMORY_LOCK:
        mem = USER_MEMORY.setdefault(chat_id, [])
        mem.append({"role": role, "content": content})
        if len(mem) > MEMORY_MAX_TURNS * 2:
            USER_MEMORY[chat_id] = mem[-MEMORY_MAX_TURNS * 2:]


# =========================
# Keyboards
# =========================
def kb_main(chat_id: int):
    p = ensure_profile(chat_id)
    coach_on = "🧠 Coach: ON" if p.get("coach", True) else "🧠 Coach: OFF"
    persona = p.get("persona", "spicy")
    verb = p.get("verbosity", "normal")
    return {
        "inline_keyboard": [
            [{"text": "🎮 Warzone", "callback_data": "game:warzone"},
             {"text": "🎮 BF6", "callback_data": "game:bf6"},
             {"text": "🎮 BO7", "callback_data": "game:bo7"}],
            [{"text": "⚙️ Settings", "callback_data": "action:settings"},
             {"text": "💪 Drills", "callback_data": "action:drills"}],
            [{"text": "📅 Plan", "callback_data": "action:plan"},
             {"text": "📼 VOD", "callback_data": "action:vod"}],
            [{"text": "👤 Profile", "callback_data": "action:profile"},
             {"text": coach_on, "callback_data": "action:coach"}],
            [{"text": f"😈 Persona: {persona}", "callback_data": "action:persona"},
             {"text": f"🗣 Talk: {verb}", "callback_data": "action:talk"}],
            [{"text": "📚 KB", "callback_data": "action:kb"},
             {"text": "📘 Lesson", "callback_data": "action:lesson"}],
            [{"text": "🧹 Reset", "callback_data": "action:reset"}],
        ]
    }


def kb_drills():
    return {
        "inline_keyboard": [
            [{"text": "🎯 Aim", "callback_data": "drill:aim"},
             {"text": "🔫 Recoil", "callback_data": "drill:recoil"},
             {"text": "🕹 Movement", "callback_data": "drill:movement"}],
            [{"text": "⬅️ Меню", "callback_data": "action:menu"}],
        ]
    }


# =========================
# OpenAI (safe + retry + personality + KB inject)
# =========================
def _guess_topics(user_text: str):
    t = (user_text or "").lower()
    guessed = []
    if any(k in t for k in ["ротац", "rotate", "энд", "зона", "круг", "шторм"]):
        guessed.append("rotations")
        guessed.append("endgame")
    if any(k in t for k in ["пози", "угол", "холд", "cover", "пик", "хедглич", "хедглитч"]):
        guessed.append("positioning")
    if any(k in t for k in ["аим", "aim", "трек", "микро", "флик", "точность"]):
        guessed.append("aim")
    if any(k in t for k in ["мув", "movement", "слайд", "джамп", "бхоп", "strafe", "стрейф"]):
        guessed.append("movement")
    if any(k in t for k in ["отдач", "recoil", "контроль", "спрей"]):
        guessed.append("recoil")
    if any(k in t for k in ["тим", "комм", "пинг", "callout", "втроём", "дуо", "сквад"]):
        guessed.append("teamplay")
    # база всегда
    base = ["aim", "positioning", "rotations"]
    out = []
    for x in guessed + base:
        if x not in out:
            out.append(x)
    return out[:3]


def openai_reply_safe(chat_id: int, user_text: str) -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "⚠️ AI выключен: нет OPENAI_API_KEY. Render → Environment Variables → add → Redeploy."

    p = ensure_profile(chat_id)
    kb = GAME_KB[p["game"]]

    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    # KB inject (самое важное + по теме запроса)
    topics = _guess_topics(user_text)
    injected = []
    for topic in topics:
        blob = kb_get(p["game"], topic, limit_items=6)
        if blob:
            injected.append(f"[KB:{p['game']}/{topic}]\n{blob}")
    injected_text = "\n\n".join(injected).strip()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
        {"role": "system", "content": f"Текущая игра: {kb['name']}. {kb.get('pillars', '')}"},
        {"role": "system", "content": f"Профиль: {json.dumps(p, ensure_ascii=False)}"},
    ]

    if injected_text:
        messages.append({
            "role": "system",
            "content": "Доп. знания пользователя (используй как учебник; НЕ выдумывай факты, если не уверен):\n" + injected_text
        })

    with MEMORY_LOCK:
        messages.extend(USER_MEMORY.get(chat_id, []))

    messages.append({"role": "user", "content": user_text})

    # ретрай от сетевых глюков
    for attempt in range(2):
        try:
            resp = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_completion_tokens=560 if verbosity == "talkative" else 440,
            )
            out = (resp.choices[0].message.content or "").strip()
            return out or "Не получил ответ. Напиши ещё раз 🙌"

        except APIConnectionError:
            if attempt == 0:
                time.sleep(0.9)
                continue
            return "⚠️ AI: проблема соединения. Попробуй ещё раз через минуту."
        except AuthenticationError:
            return "❌ AI: неверный ключ. Проверь OPENAI_API_KEY в Render и сделай Redeploy."
        except RateLimitError:
            return "⏳ AI: лимит/перегруз. Подожди 20–60 сек и попробуй снова."
        except BadRequestError:
            return f"❌ AI: bad request. Модель сейчас: {OPENAI_MODEL}."
        except APIError:
            return "⚠️ AI: временная ошибка. Попробуй ещё раз через минуту."
        except Exception:
            log.exception("OpenAI unknown error")
            return "⚠️ AI: неизвестная ошибка. Напиши /status — посмотрим конфиг."


# =========================
# Actions
# =========================
def render_menu_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "🧠 FPS Coach Bot\n"
        f"Текущая игра: {GAME_KB[p['game']]['name']}\n"
        f"Coach: {'ON' if p.get('coach') else 'OFF'}\n"
        f"Persona: {p.get('persona','spicy')} | Talk: {p.get('verbosity','normal')}\n\n"
        "Жми кнопки ниже 👇\n"
        "📌 /teach — обучить меня твоими конспектами (я сохраню в KB)."
    )


def set_game(chat_id: int, game_key: str) -> str:
    if game_key not in GAME_KB:
        return "Не знаю такую игру."
    with PROFILE_LOCK:
        p = ensure_profile(chat_id)
        p["game"] = game_key
    return f"✅ Игра: {GAME_KB[game_key]['name']}"


def get_settings(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return GAME_KB[p["game"]]["settings"]


def get_plan(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return GAME_KB[p["game"]]["plan"]


def get_vod(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return GAME_KB[p["game"]]["vod"]


def get_drill(chat_id: int, kind: str) -> str:
    p = ensure_profile(chat_id)
    drills = GAME_KB[p["game"]]["drills"]
    return drills.get(kind, "Доступно: aim / recoil / movement")


def status_text() -> str:
    ok_key = "✅" if bool(OPENAI_API_KEY) else "❌"
    ok_tg = "✅" if bool(TELEGRAM_BOT_TOKEN) else "❌"
    return (
        "🧾 Status\n"
        f"TELEGRAM_BOT_TOKEN: {ok_tg}\n"
        f"OPENAI_API_KEY: {ok_key}\n"
        f"OPENAI_BASE_URL: {OPENAI_BASE_URL}\n"
        f"OPENAI_MODEL: {OPENAI_MODEL}\n"
        f"KB_PATH: {KB_PATH}\n"
    )


def ai_test() -> str:
    if not OPENAI_API_KEY or openai_client is None:
        return "❌ /ai_test: нет OPENAI_API_KEY."
    try:
        r = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": "Ответь одним словом: OK"}],
            max_completion_tokens=10,
        )
        out = (r.choices[0].message.content or "").strip()
        return f"✅ /ai_test: {out or 'OK'} (model={OPENAI_MODEL})"
    except AuthenticationError:
        return "❌ /ai_test: неверный ключ."
    except APIConnectionError:
        return "⚠️ /ai_test: проблема сети/Render."
    except Exception as e:
        return f"⚠️ /ai_test: ошибка: {type(e).__name__}"


def throttle(chat_id: int) -> bool:
    now = time.time()
    with THROTTLE_LOCK:
        last = LAST_MSG_TS.get(chat_id, 0.0)
        if now - last < MIN_SECONDS_BETWEEN_MSG:
            return True
        LAST_MSG_TS[chat_id] = now
    return False


# =========================
# Telegram handlers
# =========================
def handle_message(chat_id: int, text: str):
    if throttle(chat_id):
        return

    p = ensure_profile(chat_id)
    low = text.lower().strip()

    if low in ("привет", "хай", "yo", "здарова", "hello", "ку"):
        send_message(chat_id, "Йо 😈 Ты сюда за победами или за оправданиями? Выбирай игру кнопкой и погнали.", reply_markup=kb_main(chat_id))
        return

    if text.startswith("/start") or text.startswith("/menu"):
        send_message(chat_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/reset"):
        with PROFILE_LOCK:
            USER_PROFILE.pop(chat_id, None)
        with MEMORY_LOCK:
            USER_MEMORY.pop(chat_id, None)
        ensure_profile(chat_id)
        send_message(chat_id, "🧹 Сбросил профиль и память.", reply_markup=kb_main(chat_id))
        return

    if text.startswith("/profile"):
        send_message(chat_id, profile_text(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/status"):
        send_message(chat_id, status_text(), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/ai_test"):
        send_message(chat_id, ai_test(), reply_markup=kb_main(chat_id))
        return

    # ===== KB команды =====
    if text.startswith("/kb_reset"):
        with KB_LOCK:
            EXTRA_KB[p["game"]] = {}
        kb_save()
        send_message(chat_id, f"🧹 Сбросил KB для {p['game']}.", reply_markup=kb_main(chat_id))
        return

    if text.startswith("/kb"):
        send_message(chat_id, kb_summary(p["game"]), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/topics"):
        send_message(chat_id, "🧠 Темы обучения:\n" + "\n".join([f"• {t}" for t in DEFAULT_TOPICS]), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/lesson"):
        parts = text.split(maxsplit=1)
        topic = parts[1].strip() if len(parts) > 1 else "aim"
        send_message(chat_id, lesson_pack(p["game"], topic), reply_markup=kb_main(chat_id))
        return

    # /teach <game> <topic> <text...>
    if text.startswith("/teach"):
        parts = text.split(maxsplit=3)
        if len(parts) < 4:
            send_message(
                chat_id,
                "Используй:\n"
                "/teach warzone|bo7|bf6 <topic> <текст>\n\n"
                "Пример:\n"
                "/teach warzone rotations Не режь центр без UAV. Ротируй по краю, заранее занимай хедглич и держи инфо.\n",
                reply_markup=kb_main(chat_id)
            )
            return
        g = parts[1].strip().lower()
        topic = parts[2].strip().lower()
        payload = parts[3].strip()
        msg = kb_add(g, topic, payload)
        send_message(chat_id, msg, reply_markup=kb_main(chat_id))
        return

    # ===== persona / talk =====
    if text.startswith("/persona"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].strip().lower() in ("spicy", "chill", "pro"):
            with PROFILE_LOCK:
                p["persona"] = parts[1].strip().lower()
            send_message(chat_id, f"✅ Persona = {p['persona']}", reply_markup=kb_main(chat_id))
        else:
            send_message(chat_id, "Используй: /persona spicy | chill | pro", reply_markup=kb_main(chat_id))
        return

    if text.startswith("/talk"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].strip().lower() in ("short", "normal", "talkative"):
            with PROFILE_LOCK:
                p["verbosity"] = parts[1].strip().lower()
            send_message(chat_id, f"✅ Talk = {p['verbosity']}", reply_markup=kb_main(chat_id))
        else:
            send_message(chat_id, "Используй: /talk short | normal | talkative", reply_markup=kb_main(chat_id))
        return

    # ===== game/settings/plan/vod/drills =====
    if text.startswith("/game"):
        parts = text.split()
        if len(parts) >= 2:
            msg = set_game(chat_id, parts[1].lower())
            send_message(chat_id, msg, reply_markup=kb_main(chat_id))
        else:
            send_message(chat_id, "Используй: /game warzone | bf6 | bo7", reply_markup=kb_main(chat_id))
        return

    if text.startswith("/settings"):
        send_message(chat_id, get_settings(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/plan"):
        send_message(chat_id, get_plan(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/vod"):
        send_message(chat_id, get_vod(chat_id), reply_markup=kb_main(chat_id))
        return

    if text.startswith("/drills"):
        send_message(chat_id, "Выбери дрилл:", reply_markup=kb_drills())
        return

    # ===== профиль одной строкой =====
    platform, style, goal = parse_profile_line(text)
    if platform or style or goal:
        with PROFILE_LOCK:
            if platform:
                p["platform"] = platform
            if style:
                p["style"] = style
            if goal:
                p["goal"] = goal
        send_message(chat_id, "✅ Профиль обновлён.\n\n" + profile_text(chat_id), reply_markup=kb_main(chat_id))
        return

    # ===== Coach OFF =====
    if not p.get("coach", True):
        send_message(
            chat_id,
            "🧠 Coach сейчас OFF. Нажми кнопку Coach в меню чтобы включить.\n"
            "А пока используй кнопки Settings/Drills/Plan/VOD.",
            reply_markup=kb_main(chat_id),
        )
        return

    # ===== AI “анимация”: typing + пульс + потом заменяем текст =====
    update_memory(chat_id, "user", text)

    tmp_id = send_message(chat_id, random.choice(THINKING_LINES), reply_markup=None)

    stop = threading.Event()
    t1 = threading.Thread(target=typing_loop, args=(chat_id, stop), daemon=True)
    t1.start()

    t2 = None
    if tmp_id:
        t2 = threading.Thread(target=pulse_edit_loop, args=(chat_id, tmp_id, stop, "⌛ Думаю"), daemon=True)
        t2.start()

    try:
        reply = openai_reply_safe(chat_id, text)
    finally:
        stop.set()

    update_memory(chat_id, "assistant", reply)

    if tmp_id:
        try:
            edit_message(chat_id, tmp_id, reply, reply_markup=kb_main(chat_id))
        except Exception:
            send_message(chat_id, reply, reply_markup=kb_main(chat_id))
    else:
        send_message(chat_id, reply, reply_markup=kb_main(chat_id))


def handle_callback(cb: dict):
    cb_id = cb["id"]
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data", "")

    if not chat_id or not message_id:
        answer_callback(cb_id)
        return

    try:
        p = ensure_profile(chat_id)

        # мгновенная реакция на клик
        quick_loading_edit(chat_id, message_id, "⌛ Загружаю…")

        if data == "action:menu":
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data.startswith("game:"):
            game = data.split(":", 1)[1]
            set_game(chat_id, game)
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:settings":
            edit_message(chat_id, message_id, get_settings(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:plan":
            edit_message(chat_id, message_id, get_plan(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:vod":
            edit_message(chat_id, message_id, get_vod(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:coach":
            with PROFILE_LOCK:
                p["coach"] = not p.get("coach", True)
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:persona":
            cur = p.get("persona", "spicy")
            nxt = {"spicy": "chill", "chill": "pro", "pro": "spicy"}.get(cur, "spicy")
            with PROFILE_LOCK:
                p["persona"] = nxt
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:talk":
            cur = p.get("verbosity", "normal")
            nxt = {"short": "normal", "normal": "talkative", "talkative": "short"}.get(cur, "normal")
            with PROFILE_LOCK:
                p["verbosity"] = nxt
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

        elif data == "action:kb":
            edit_message(chat_id, message_id, kb_summary(p["game"]), reply_markup=kb_main(chat_id))

        elif data == "action:lesson":
            edit_message(chat_id, message_id, lesson_pack(p["game"], "aim"), reply_markup=kb_main(chat_id))

        elif data == "action:reset":
            with PROFILE_LOCK:
                USER_PROFILE.pop(chat_id, None)
            with MEMORY_LOCK:
                USER_MEMORY.pop(chat_id, None)
            ensure_profile(chat_id)
            edit_message(chat_id, message_id, "🧹 Сбросил профиль и память.", reply_markup=kb_main(chat_id))

        elif data == "action:drills":
            edit_message(chat_id, message_id, "Выбери дрилл:", reply_markup=kb_drills())

        elif data.startswith("drill:"):
            kind = data.split(":", 1)[1]
            edit_message(chat_id, message_id, get_drill(chat_id, kind), reply_markup=kb_drills())

        else:
            edit_message(chat_id, message_id, render_menu_text(chat_id), reply_markup=kb_main(chat_id))

    finally:
        answer_callback(cb_id)


def run_telegram_bot():
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
                    send_message(chat_id, "Ошибка 😅 Попробуй ещё раз.", reply_markup=kb_main(chat_id))

        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)


# =========================
# Render health endpoint
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


# ===== старт =====
kb_load()

if __name__ == "__main__":
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    run_http_server()
