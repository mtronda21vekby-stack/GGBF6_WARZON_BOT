# -*- coding: utf-8 -*-
import logging
import os
import sys


def _level() -> int:
    s = (os.getenv("LOG_LEVEL") or "INFO").upper().strip()
    return getattr(logging, s, logging.INFO)


def build_logger(name: str = "ggbf6_bot") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # уже настроен

    logger.setLevel(_level())

    h = logging.StreamHandler(sys.stdout)
    h.setLevel(_level())

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    h.setFormatter(fmt)

    logger.addHandler(h)
    logger.propagate = False
    return logger


# ✅ То, что ждёт runner.py: "from app.log import log"
log = build_logger()