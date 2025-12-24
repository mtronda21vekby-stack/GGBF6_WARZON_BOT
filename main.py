import os
import json
import time
import logging
from typing import Dict, List, Any, Tuple

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from openai import OpenAI

# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-5-mini").strip()

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing ENV: TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise SystemExit("Missing ENV: OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# LOG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# =========================
# In-memory state
# =========================
USER_PROFILE: Dict[int, Dict[str, str]] = {}   # user_id -> profile
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}  # user_id -> [{"role","content"}]
MEMORY_MAX_TURNS = 10  # (user+assistant) pairs -> 20 msgs max

# =========================
# Knowledge base
# =========================
GAME_KB = {
    "warzone": {
        "name": "Call of Duty: Warzone",
        "quick_settings": (
            "🎮 *Warzone — базовые настройки (контроллер)*\n"
            "• Sens: 7/7 (если мажешь → 6/6)\n"
            "• ADS: 0.90 low / 0.85 high\n"
            "• Aim Assist: Dynamic (fallback Standard)\n"
            "• Response Curve: Dynamic\n"
            "• Deadzone min: 0.05 (дрифт → 0.07–0.10)\n"
            "• FOV: 105–110\n"
            "• ADS FOV Affected: ON\n"
            "• Weapon FOV: Wide\n"
            "• Camera Movement: Least\n"
        ),
        "pillars": (
            "🧠 *Warzone — фундамент про-уровня*\n"
            "1) Позиция/тайминги (высота, укрытия, ротации)\n"
            "2) Инфо (пинги, короткие коллы)\n"
            "3) Выживание > киллы (ресурсы, перезанятие позиции)\n"
            "4) Первые 0.7 сек решают (pre-aim, headglitch, центр экрана)\n"
            "5) Микро-движение без паники (slide/strafe/jump)\n"
        ),
        "vod_template": (
            "📼 *Разбор ситуации (шаблон)*\n"
            "1) Режим/сквад\n"
            "2) Где был бой (дом/крыша/поле)\n"
            "3) Как умер (угол/ошибка/чем наказали)\n"
            "4) Ресурсы (плиты/смок/стим/саморез)\n"
            "5) Что хотел сделать (пуш/отход/ротация)\n\n"
            "Я верну: *Ошибка №1* + *1–2 действия* + *мини-дрилл* 💪\n"
        ),
        "drills": {
            "aim": "🎯 *Warzone Aim 20 мин*\n10м warm-up\n5м трекинг\n5м микро-коррекции",
            "recoil": "🔫 *Warzone Recoil 20 мин*\n5м 15–25м\n10м 25–40м\n5м дисциплина очередей",
            "movement": "🕹 *Warzone Movement 15 мин*\nугол→slide→пик\njump-пики\nreposition после контакта",
        },
    },
    "bf6": {
        "name": "BF6",
        "quick_settings": (
            "🎮 *BF6 — базовые настройки*\n"
            "• Sens: средняя\n"
            "• ADS: чуть ниже base\n"
            "• Deadzone: минимум без дрифта\n"
            "• FOV: высокий (комфорт)\n"
        ),
        "pillars": (
            "🧠 *BF6 — фундамент*\n"
            "• Линии фронта + спавн-логика\n"
            "• Не стой на одном угле: дал инфо → сменил позицию\n"
            "• Мини-пики, префайр, дисциплина перезарядки\n"
        ),
        "vod_template": "📼 *BF6 разбор:* карта/режим, класс, где умер/почему, что хотел сделать.",
        "drills": {
            "aim": "🎯 *BF6 Aim*\nпрефайр углов\nтрекинг\nсмена позиции после серии",
            "movement": "🕹 *BF6 Movement*\nвыглянул→дал инфо→откатился\nрепик с другого угла",
        },
    },
    "bo7": {
        "name": "BO7",
        "quick_settings": (
            "🎮 *BO7 — настройки (быстро и по делу)*\n"
            "• Sens: 6–8 (агро → ближе к 8)\n"
            "• ADS: −10–15% от base (чтобы трекинг не «дрожал»)\n"
            "• Deadzone min: 0.03–0.06 (без дрифта)\n"
            "• FOV: 105–115 (если теряешь цели → 105)\n"
            "• Sprint Assist / Auto Tac Sprint: ON (если удобно)\n"
            "• Aim response curve: Dynamic/Linear (выбирай по контролю)\n"
        ),
        "pillars": (
            "🧠 *BO7 — что реально делает разницу*\n"
            "1) *Центр экрана*: держи прицел там, где появится враг\n"
            "2) *Тайминги*: после контакта не стой — репозиция за 1–2 сек\n"
            "3) *Дуэль*: первая точная очередь + контроль отдачи\n"
            "4) *Репики*: второй пик — с другого угла, не повторяйся\n"
            "5) *Инфо*: мини-карты/звук/пинги → решение за 0.5 сек\n"
        ),
        "vod_template": (
            "📼 *BO7 разбор (шаблон)*\n"
            "1) Режим/карта\n"
            "2) Оружие/роль (entry/anchor/support)\n"
            "3) Момент смерти (что видел/что не видел)\n"
            "4) Позиция (почему именно там)\n"
            "5) План (что хотел сделать)\n\n"
            "Я верну: *Ошибка №1* + *2 правки* + *два мини-дрилла* 🔥\n"
        ),
        "drills": {
            "aim": (
                "🎯 *BO7 Aim 15–20 мин*\n"
                "• 5м: pre-aim по углам (медленно, чисто)\n"
                "• 5м: трекинг ближний (микро-движение стиком)\n"
                "• 5–10м: «первый выстрел» — выход/1 очередь/укрытие\n"
            ),
            "recoil": (
                "🔫 *BO7 Recoil 10–15 мин*\n"
                "• 5м: короткие очереди 8–12 патронов\n"
                "• 5–10м: контроль на средней дистанции\n"
                "Фокус: *не зажимай*, держи темп и точность.\n"
            ),
            "movement": (
                "🕹 *BO7 Movement 10–15 мин*\n"
                "• угол → короткий пик → назад\n"
                "• slide/jump только с целью (не «ради красоты»)\n"
                "• после килла: *сразу* смена позиции\n"
            ),
        },
        "meta_help": (
            "⚠️ По «мете» BO7: она меняется патчами.\n"
            "Скажи:\n"
            "• режим (MP/Ranked/Warzone-стиль)\n"
            "• платформа (controller/KBM)\n"
            "• дистанция (close/mid/long)\n"
            "— и я дам 2–3 связки + как их играть.\n"
        )
    }
}

SYSTEM_PROMPT = (
    "Ты профессиональный киберспортивный коуч по FPS (Warzone/BF6/BO7).\n"
    "Язык: русский. Тон: уверенный, дружелюбный.\n"
    "Формат: коротко и структурно. Иногда эмодзи 🎮🔥💪\n\n"
    "Запрещено: читы/хаки/обход античита.\n"
    "Если просят — вежливо откажи и дай честные альтернативы.\n\n"
    "Правило ответа: всегда дай:\n"
    "• 1 ключевая ошибка/узкое место\n"
    "• 1–2 конкретных действия\n"
    "• 1 мини-дрилл на 5–10 минут\n"
)

# =========================
# Helpers
# =========================
def ensure_profile(user_id: int) -> Dict[str, str]:
    return USER_PROFILE.setdefault(user_id, {
        "game": "warzone",
        "platform": "",
        "style": "",
        "goal": "",
    })

def update_memory(user_id: int, role: str, content: str):
    mem = USER_MEMORY.setdefault(user_id, [])
    mem.append({"role": role, "content": content})
    # keep last N turns
    if len(mem) > MEMORY_MAX_TURNS * 2:
        USER_MEMORY[user_id] = mem[-MEMORY_MAX_TURNS*2:]

def parse_tune_text(text: str) -> Tuple[str, str, str]:
    t = text.lower()
    platform = ""
    if "xbox" in t: platform = "Xbox"
    elif "ps" in t or "playstation" in t: platform = "PlayStation"
    elif "kbm" in t or "мыш" in t or "клав" in t: platform = "KBM"

    style = ""
    if "агро" in t or "aggressive" in t: style = "Aggressive"
    elif "спокой" in t or "calm" in t or "деф" in t: style = "Calm"

    goal = ""
    if "aim" in t or "аим" in t or "прицел" in t: goal = "Aim"
    elif "recoil" in t or "отдач" in t: goal = "Recoil"
    elif "movement" in t or "мув" in t or "движ" in t: goal = "Movement"
    elif "rank" in t or "ранг" in t: goal = "Rank"

    return platform, style, goal

def profile_hint(user_id: int) -> str:
    p = ensure_profile(user_id)
    kb = GAME_KB.get(p["game"], {})
    parts = [f"game={p['game']}"]
    for k in ("platform", "style", "goal"):
        if p.get(k):
            parts.append(f"{k}={p[k]}")
    return f"Профиль игрока: {', '.join(parts)}. Игра: {kb.get('name', p['game'])}"

def tune_prompt() -> str:
    return (
        "🎯 *Настройка профиля (1 сообщением)*\n"
        'Напиши: "Xbox, Aggressive, Aim"\n\n'
        "*Команды:*\n"
        "• /game warzone | bf6 | bo7\n"
        "• /settings\n"
        "• /drills aim | recoil | movement\n"
        "• /vod\n"
        "• /plan\n"
        "• /profile\n"
        "• /reset\n"
    )

def settings_text(user_id: int) -> str:
    p = ensure_profile(user_id)
    kb = GAME_KB[p["game"]]
    extra = []
    if p.get("platform"): extra.append(f"Платформа: {p['platform']}")
    if p.get("style"): extra.append(f"Стиль: {p['style']}")
    if p.get("goal"): extra.append(f"Цель: {p['goal']}")
    return kb.get("quick_settings", "") + ("\n\n" + "\n".join(extra) if extra else "")

def drills_text(user_id: int, kind: str) -> str:
    p = ensure_profile(user_id)
    drills = GAME_KB[p["game"]].get("drills", {})
    if kind not in drills:
        return "Доступно: aim | recoil | movement"
    return drills[kind]

def plan_text(user_id: int) -> str:
    p = ensure_profile(user_id)
    game = GAME_KB[p["game"]]["name"]
    goal = p.get("goal") or "стабильность"
    return (
        f"📅 *План на 7 дней — {game}*\nЦель: *{goal}*\n\n"
        "День 1–2: warm-up 10м + aim 15м + movement 10м + мини-разбор 5м\n"
        "День 3–4: warm-up 10м + дуэли/углы 15м + дисциплина 10м + вывод 5м\n"
        "День 5–6: warm-up 10м + игра от инфо 20м + фиксация ошибок 5м\n"
        "День 7: 30–60м игры + разбор 2 смертей 10м\n"
    )

def set_game(user_id: int, game_key: str) -> str:
    p = ensure_profile(user_id)
    if game_key not in GAME_KB:
        return "Не знаю такую игру. Доступно: warzone, bf6, bo7"
    p["game"] = game_key
    return f"Ок ✅ Текущая игра: *{GAME_KB[game_key]['name']}*\nНапиши /settings или /drills"

# =========================
# OpenAI
# =========================
def openai_reply(user_id: int, user_text: str) -> str:
    p = ensure_profile(user_id)
    kb = GAME_KB[p["game"]]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": profile_hint(user_id)},
        {"role": "system", "content": kb.get("pillars", "")},
    ]

    # BO7 extra helper about meta volatility
    if p["game"] == "bo7":
        messages.append({"role": "system", "content": kb.get("meta_help", "")})

    messages.extend(USER_MEMORY.get(user_id, []))
    messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        # экономим: без огромных простыней
        max_tokens=450,
    )
    return (resp.choices[0].message.content or "").strip() or "Не получил ответ. Напиши ещё раз 🙌"

# =========================
# Telegram handlers
# =========================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Я бот: @{BOT_NAME} 🎮\n\n" + tune_prompt(),
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    USER_PROFILE.pop(uid, None)
    USER_MEMORY.pop(uid, None)
    await update.message.reply_text("Сбросил профиль и память ✅\n\n" + tune_prompt(), parse_mode=ParseMode.MARKDOWN)

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = ensure_profile(uid)
    await update.message.reply_text(
        "Профиль:\n" + json.dumps(p, ensure_ascii=False, indent=2)
    )

async def cmd_tune(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tune_prompt(), parse_mode=ParseMode.MARKDOWN)

async def cmd_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Используй: /game warzone  или  /game bf6  или  /game bo7")
        return
    await update.message.reply_text(set_game(uid, context.args[0].lower()), parse_mode=ParseMode.MARKDOWN)

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(settings_text(uid), parse_mode=ParseMode.MARKDOWN)

async def cmd_drills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    kind = (context.args[0].lower() if context.args else "aim")
    await update.message.reply_text(drills_text(uid, kind), parse_mode=ParseMode.MARKDOWN)

async def cmd_vod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = ensure_profile(uid)
    await update.message.reply_text(GAME_KB[p["game"]].get("vod_template", "Опиши ситуацию."), parse_mode=ParseMode.MARKDOWN)

async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(plan_text(uid), parse_mode=ParseMode.MARKDOWN)

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        return

    # quick tune message (Xbox, Aggressive, Aim)
    p = ensure_profile(uid)
    platform, style, goal = parse_tune_text(text)
    if platform or style or goal:
        if platform: p["platform"] = platform
        if style: p["style"] = style
        if goal: p["goal"] = goal
        await update.message.reply_text("Принял ✅\n\n" + settings_text(uid), parse_mode=ParseMode.MARKDOWN)
        return

    # AI
    try:
        update_memory(uid, "user", text)
        reply = openai_reply(uid, text)
        update_memory(uid, "assistant", reply)

        # Telegram message limit safety
        if len(reply) > 3900:
            for i in range(0, len(reply), 3900):
                await update.message.reply_text(reply[i:i+3900], parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logging.exception("AI/Message error: %s", e)
        await update.message.reply_text("Ошибка 😅 Попробуй ещё раз через минуту.")

# =========================
# MAIN
# =========================
def main():
    logging.info("Starting bot polling...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("tune", cmd_tune))
    app.add_handler(CommandHandler("game", cmd_game))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("drills", cmd_drills))
    app.add_handler(CommandHandler("vod", cmd_vod))
    app.add_handler(CommandHandler("plan", cmd_plan))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
