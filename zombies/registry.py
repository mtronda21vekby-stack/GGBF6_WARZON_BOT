# -*- coding: utf-8 -*-
import importlib
import pkgutil
from typing import List, Any


def load_maps() -> List[Any]:
    import zombies
    maps: List[Any] = []

    for m in pkgutil.iter_modules(zombies.__path__):
        name = m.name
        if name.startswith("_") or name in ("registry", "router"):
            continue
        try:
            mod = importlib.import_module(f"zombies.{name}")
        except Exception:
            continue

        if hasattr(mod, "MAP_ID") and hasattr(mod, "MAP_NAME") and hasattr(mod, "SECTIONS"):
            maps.append(mod)

    maps.sort(key=lambda x: getattr(x, "MAP_NAME", ""))
    return maps


def get_map(map_id: str):
    for m in load_maps():
        if getattr(m, "MAP_ID", "") == map_id:
            return m
    return None
