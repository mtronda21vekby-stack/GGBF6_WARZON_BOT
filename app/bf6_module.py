# -*- coding: utf-8 -*-
"""
BF6 MODULE (ReplyKeyboard)
- хаб BF6 + вход в Roles/Deaths из твоего legacy BF6
- legacy НЕ трогаем, просто подключаем
"""

from typing import Dict, Any, Optional

from app.state import ensure_profile
from app.pro_settings import get_text as pro_get_text

# ✅ ТВОЙ СТАРЫЙ BF6 КОД (roles/deaths) должен лежать тут:
from app import bf6_legacy


def _kb(rows):
    return {"keyboard": rows, "resize_keyboard": True}


def home_keyboard() -> Dict[str, Any]:
    return _kb([
        [{"text": "🟣 Роли (BF6)"}, {"text": "💀 Почему я умираю"}],
        [{"text": "⚙️ Настройки (Device)"}],
        [{"text": "⬅️ Назад в главное"}],
    ])


def device_keyboard() -> Dict[str, Any]:
    return _kb([
        [{"text": "🎮 PS5/Xbox (Controller)"}, {"text": "🖥 PC (MnK)"}],
        [{"text": "⬅️ Назад (BF6)"}],
    ])


def handle_text(chat_id: int, text: str) -> Optional[Dict[str, Any]]:
    p = ensure_profile(chat_id)
    page = p.get("page", "main")
    t = (text or "").strip()

    if page not in ("bf6_home", "bf6_roles", "bf6_deaths", "bf6_device"):
        return None

    style = p.get("persona", "spicy")
    mode = p.get("speed", "normal")
    # у тебя режимы chat/coach/lightning лежат в p["mode"] и p["speed"] отдельно,
    # legacy BF6 ожидает mode: chat/coach/lightning.
    # Смапим:
    bf_mode = p.get("mode", "chat")
    if p.get("speed", "normal") == "lightning":
        bf_mode = "lightning"

    # -------- BF6 HOME --------
    if page == "bf6_home":
        if t == "🟣 Роли (BF6)":
            p["page"] = "bf6_roles"
            return {
                "text": "🟣 BF6 — роли: выбери снизу 👇",
                "reply_markup": bf6_legacy.roles_keyboard(),
                "set_profile": {"page": "bf6_roles"},
            }

        if t == "💀 Почему я умираю":
            p["page"] = "bf6_deaths"
            return {
                "text": "💀 BF6 — причины: выбери снизу 👇",
                "reply_markup": bf6_legacy.deaths_keyboard(),
                "set_profile": {"page": "bf6_deaths"},
            }

        if t == "⚙️ Настройки (Device)":
            p["page"] = "bf6_device"
            return {
                "text": "⚙️ BF6 — choose device:",
                "reply_markup": device_keyboard(),
                "set_profile": {"page": "bf6_device"},
            }

        if t == "⬅️ Назад в главное":
            p["page"] = "main"
            return {
                "text": "⬅️ Ок, вернул в главное меню.",
                "reply_markup": {"remove_keyboard": True},
                "set_profile": {"page": "main"},
            }

        return {"text": "BF6 модуль: жми кнопки снизу 👇", "reply_markup": home_keyboard()}

    # -------- BF6 DEVICE --------
    if page == "bf6_device":
        if t == "🎮 PS5/Xbox (Controller)":
            return {"text": pro_get_text("bf6:pad"), "reply_markup": device_keyboard()}
        if t == "🖥 PC (MnK)":
            return {"text": pro_get_text("bf6:mnk"), "reply_markup": device_keyboard()}
        if t == "⬅️ Назад (BF6)":
            p["page"] = "bf6_home"
            return {
                "text": "🎮 BF6 — раздел:",
                "reply_markup": home_keyboard(),
                "set_profile": {"page": "bf6_home"},
            }
        return {"text": "Choose device кнопкой 👇", "reply_markup": device_keyboard()}

    # -------- BF6 ROLES (legacy) --------
    if page == "bf6_roles":
        if t == "⬅️ Назад":
            p["page"] = "bf6_home"
            return {"text": "🎮 BF6 — раздел:", "reply_markup": home_keyboard(), "set_profile": {"page": "bf6_home"}}

        # маппинг кнопок -> role_id
        role_map = {
            "🟠 Assault": "assault",
            "🟢 Support": "support",
            "🔵 Engineer": "engineer",
            "🟣 Recon": "recon",
        }
        rid = role_map.get(t)
        if rid:
            return {"text": bf6_legacy.get_role_text(rid, style, bf_mode), "reply_markup": bf6_legacy.roles_keyboard()}

        return {"text": "Выбери роль кнопкой снизу 👇", "reply_markup": bf6_legacy.roles_keyboard()}

    # -------- BF6 DEATHS (legacy) --------
    if page == "bf6_deaths":
        if t == "⬅️ Назад":
            p["page"] = "bf6_home"
            return {"text": "🎮 BF6 — раздел:", "reply_markup": home_keyboard(), "set_profile": {"page": "bf6_home"}}

        reason_map = {
            "👁 Меня не вижу": "no_vision",
            "🔙 Со спины": "backstab",
            "🔁 Сразу": "instadeath",
            "⚔️ Дуэли": "duel",
        }
        rid = reason_map.get(t)
        if rid:
            return {"text": bf6_legacy.get_death_text(rid, style, bf_mode), "reply_markup": bf6_legacy.deaths_keyboard()}

        return {"text": "Выбери причину кнопкой снизу 👇", "reply_markup": bf6_legacy.deaths_keyboard()}

    return None
