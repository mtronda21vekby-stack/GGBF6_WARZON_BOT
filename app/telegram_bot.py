from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from app.config import get_settings
from app.log import setup_logger
from app.ui.keyboards import main_menu
from app.ui import texts
from app.brain.memory import MemoryStore
from app.brain.brain_v3 import BrainV3

logger = setup_logger()

settings = get_settings()
mem = MemoryStore()
brain = BrainV3(mem)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(texts.WELCOME, reply_markup=main_menu())

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Меню:", reply_markup=main_menu())

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    if not text:
        return

    reply = await brain.handle_text(user_id, text)
    await update.message.reply_text(reply.text, reply_markup=main_menu())

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    data = q.data

    if data == "help":
        await q.message.reply_text(texts.HELP)
    elif data == "mem_clear":
        mem.clear(user_id)
        await q.message.reply_text("🧹 Память очищена.")
    elif data == "style":
        brain.set_style(user_id, "aggressive")
        await q.message.reply_text("🎭 Стиль: aggressive (пока заглушка).")
    else:
        await q.message.reply_text(f"⚙️ {data} (в разработке)")

def build_application() -> Application:
    app = Application.builder().token(settings.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app
