# -*- coding: utf-8 -*-
from __future__ import annotations


ROLE_LOADOUTS = {
    "warzone": {
        "entry": {
            "role": "Entry fragger",
            "weapons": ["SMG", "Fast AR"],
            "focus": "агрессия, быстрые киллы",
        },
        "anchor": {
            "role": "Anchor",
            "weapons": ["AR", "LMG"],
            "focus": "контроль зоны и тыла",
        },
        "sniper": {
            "role": "Sniper",
            "weapons": ["Sniper", "DMR"],
            "focus": "пики и инфа",
        },
    },
    "bf6": {
        "assault": {
            "role": "Assault",
            "weapons": ["AR"],
            "focus": "давление на objective",
        },
        "engineer": {
            "role": "Engineer",
            "weapons": ["SMG", "AT"],
            "focus": "техника и фланги",
        },
        "support": {
            "role": "Support",
            "weapons": ["LMG"],
            "focus": "саппорт и удержание",
        },
        "recon": {
            "role": "Recon",
            "weapons": ["Sniper", "DMR"],
            "focus": "разведка",
        },
    },
    "bo7": {
        "slayer": {
            "role": "Slayer",
            "weapons": ["SMG", "AR"],
            "focus": "duels и трейды",
        },
        "anchor": {
            "role": "Anchor",
            "weapons": ["AR"],
            "focus": "контроль спавнов",
        },
        "objective": {
            "role": "Objective",
            "weapons": ["AR", "Utility"],
            "focus": "захват точек",
        },
    },
}
