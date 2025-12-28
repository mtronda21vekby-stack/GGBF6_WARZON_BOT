from __future__ import annotations
from enum import Enum


class Game(str, Enum):
    WARZONE = "warzone"
    BF6 = "bf6"
    BO7 = "bo7"


class InputDevice(str, Enum):
    KBM = "kbm"
    PS = "ps"
    XBOX = "xbox"


class SkillTier(str, Enum):
    NORMAL = "normal"
    PRO = "pro"
    DEMON = "demon"


class Mode(str, Enum):
    # Warzone
    WZ_BR = "wz_br"
    WZ_RESURGENCE = "wz_resurgence"
    WZ_RANKED = "wz_ranked"

    # BF6
    BF6_PVP = "bf6_pvp"

    # BO7
    BO7_MP = "bo7_mp"
    BO7_ZOMBIES = "bo7_zombies"
    BO7_ZOMBIES_ZOMBIE = "bo7_zombies_zombie"  # “зомби режим расширенный”
