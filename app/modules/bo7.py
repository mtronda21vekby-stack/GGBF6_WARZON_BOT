# -*- coding: utf-8 -*-
from app.modules.registry import register

@register("bo7")
def bo7_tip(text: str) -> str:
    return "BO7-модуль подключен. Напиши: spawns/lanes/map control — и разберу."