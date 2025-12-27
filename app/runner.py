# -*- coding: utf-8 -*-
import os
import time

from app.log import log


def main():
    log.info("BOOT: runner.main() start")

    # тут дальше твоя загрузка конфига / ai / handlers
    # оставляю безопасный каркас, чтобы Render точно не падал

    # ✅ ПИНГ-ЛУП, чтобы процесс жил (пока подключаем Brain/AI дальше)
    while True:
        log.info("alive")
        time.sleep(60)