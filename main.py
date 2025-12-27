import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот жив и отвечает")

def main():
    if not TOKEN:
        raise RuntimeError("❌ TELEGRAM_BOT_TOKEN not found")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    logging.info("BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
