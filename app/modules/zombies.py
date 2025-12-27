# -*- coding: utf-8 -*-
from app.modules.registry import register

@register("zombies")
def zombies_tip(text: str) -> str:
    return "Zombies-модуль подключен. Напиши карту/раунд/перки — дам маршрут."
