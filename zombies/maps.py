# zombies/maps.py
# Central registry for Zombies maps

from zombies.ashes_of_damned import ASHES_OF_DAMNED
from zombies.astra_malorum import ASTRA_MALORUM

MAPS = {
    "ashes_of_damned": {
        "title": "Ashes of the Damned",
        "data": ASHES_OF_DAMNED,
    },
    "astra_malorum": {
        "title": "Astra Malorum",
        "data": ASTRA_MALORUM,
    },
}

def get_maps_keyboard():
    """
    Inline keyboard for Zombies maps
    """
    keyboard = []
    for key, value in MAPS.items():
        keyboard.append([
            {
                "text": value["title"],
                "callback_data": f"zombies:map:{key}"
            }
        ])

    keyboard.append([
        {"text": "⬅️ Back", "callback_data": "nav:main"}
    ])

    return {"inline_keyboard": keyboard}


def get_map_text(map_key: str) -> str:
    """
    Returns full formatted guide for selected map
    """
    if map_key not in MAPS:
        return "❌ Map not found."

    return MAPS[map_key]["data"]
