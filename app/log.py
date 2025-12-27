# -*- coding: utf-8 -*-
import logging
import sys

def get_logger(name: str = "bot"):
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    h.setFormatter(fmt)
    log.addHandler(h)
    return log
