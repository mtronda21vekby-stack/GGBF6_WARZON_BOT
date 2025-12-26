# -*- coding: utf-8 -*-
import sys
import os
import time
import logging

# гарантируем корректный путь
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.health import start_health

log = logging.getLogger("runner")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def main():
    log.info("========== BOOT ==========")

    # ✅ ВАЖНО: старт health-сервера (Render PORT)
    start_health(log)

    # ⏳ небольшая пауза чтобы порт точно поднялся
    time.sleep(0.5)

    # 🔁 дальше запускаем ТВОЮ текущую логику бота
    try:
        from app.tg import start_bot
        log.info("Starting Telegram bot via app.tg.start_bot()")
        start_bot()
        return
    except ImportError:
        log.warning("app.tg.start_bot not found")

    try:
        from app.telegram_api import run
        log.info("Starting Telegram bot via app.telegram_api.run()")
        run()
        return
    except ImportError:
        log.warning("app.telegram_api.run not found")

    # ❌ если ни один запуск не найден — не падаем
    log.error("No Telegram entrypoint found. Bot is idle.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()