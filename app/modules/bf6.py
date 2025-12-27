# -*- coding: utf-8 -*-
from app.modules.registry import register

@register("bf6")
def bf6_tip(text: str) -> str:
    return "BF6-модуль подключен. Напиши: recoil/movement/objective — и разберу."