# zombies/maps.py
# -*- coding: utf-8 -*-

from zombies.blood_spire import MAP_ID as B_ID, MAP_NAME as B_NAME, list_buttons as B_LIST, get_section as B_GET
from zombies.astra_malorum import MAP_ID as A_ID, MAP_NAME as A_NAME, list_buttons as A_LIST, get_section as A_GET

MAPS = {
    B_ID: {"name": B_NAME, "list": B_LIST, "get": B_GET},
    A_ID: {"name": A_NAME, "list": A_LIST, "get": A_GET},
}

def map_list():
    return [(mid, MAPS[mid]["name"]) for mid in MAPS.keys()]

def map_exists(map_id: str) -> bool:
    return map_id in MAPS

def list_sections(map_id: str):
    return MAPS[map_id]["list"]()

def get_section(map_id: str, section_id: str):
    return MAPS[map_id]["get"](section_id)
