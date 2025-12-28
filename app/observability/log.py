from __future__ import annotations

import logging


def setup_logging(level: str = "INFO"):
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str):
    return logging.getLogger(name)
