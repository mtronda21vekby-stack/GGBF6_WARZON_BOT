# app/observability/log.py
from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        stream=sys.stdout,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
