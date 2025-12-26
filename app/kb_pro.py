# -*- coding: utf-8 -*-

PRO_SETTINGS = {
    "warzone": """
🎮 **WARZONE — НАСТРОЙКИ ТОП-ИГРОКОВ**

🎯 Aim Assist:
• Aim Assist Type: Dynamic
• Response Curve: Dynamic

🕹 Sensitivity:
• Horizontal / Vertical: 6–7
• ADS Low Zoom: 0.85–0.95
• ADS High Zoom: 0.80–0.90

📐 Deadzone:
• Left Stick Min: 0.03–0.06
• Right Stick Min: 0.04–0.07

👁 FOV:
• FOV: 105–110
• ADS FOV: Affected
• Weapon FOV: Wide

🎥 Camera:
• Camera Movement: Least (50%)

⚠️ Главное правило про-игроков:
стабильность > скорость
""",

    "bo7": """
🎮 **BLACK OPS 7 — ПРО СЕТАП**

• Sensitivity: 6–8
• ADS Multiplier: 0.80–0.95
• Deadzone: минимальный без дрифта
• FOV: 100–115

💡 BO7 выигрывается:
пефайром + таймингом + углами
""",

    "bf6": """
🎮 **BATTLEFIELD 6 — PRO SETTINGS**

Controller:
• Aim Assist: ON
• Response Curve: Linear / Dynamic

Sensitivity:
• Medium overall
• Lower ADS than hipfire

FOV:
• High but comfortable (90–100)

Gameplay Rules:
• Reposition after every engagement
• Never repeek same angle
• Information > aim

Battlefield is positioning first.
"""
}

def get_pro_settings(game: str) -> str:
    return PRO_SETTINGS.get(game, "Нет настроек для этой игры.")
