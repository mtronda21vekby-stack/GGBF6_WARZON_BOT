# -*- coding: utf-8 -*-
from typing import Callable, Dict

REGISTRY: Dict[str, Callable[[str], str]] = {}

def register(name: str):
    def _wrap(fn):
        REGISTRY[name] = fn
        return fn
    return _wrap