# -*- coding: utf-8 -*-
import logging
import os
import sys

def setup_logger(name: str = "ggbf6_bot") -> logging.Logger:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        h.setFormatter(fmt)
        logger.addHandler(h)

    logger.propagate = False
    return logger

log = setup_logger()