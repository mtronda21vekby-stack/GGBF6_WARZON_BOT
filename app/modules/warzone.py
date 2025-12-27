# -*- coding: utf-8 -*-
from app.modules.registry import register

@register("warzone")
def warzone_tip(text: str) -> str:
    return "Warzone-модуль подключен. Напиши: loadout/rotate/gulag/позиция — и разберу."