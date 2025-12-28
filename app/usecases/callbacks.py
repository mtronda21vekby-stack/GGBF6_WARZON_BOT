from __future__ import annotations

from app.core.outgoing import Outgoing
from app.ui.keyboards import KB
from app.domain.enums import Game, Mode, InputDevice, SkillTier
from app.content.catalog import ContentCatalog

catalog = ContentCatalog()


def _safe_enum(enum_cls, value, default):
    try:
        return enum_cls(value)
    except Exception:
        return default


async def handle_callback(brain, profiles, user_id: int, data: str) -> Outgoing:
    data = (data or "").strip()
    p = profiles.get(user_id)

    # global buttons
    if data == "menu:modes":
        return Outgoing("🎮 Выбери игру:", KB.modes_menu())

    if data == "back:main":
        return Outgoing("Главное меню:", KB.main_menu())

    if data == "mem_clear":
        brain.clear_memory(user_id)
        return Outgoing("🧹 Память очищена.", KB.main_menu())

    if data == "ai_mode":
        enabled = brain.toggle_ai(user_id)
        return Outgoing(f"🧠 ИИ-режим: {'ON' if enabled else 'OFF'}", KB.main_menu())

    # quick info blocks
    if data == "show:classes_bf6":
        d = catalog.load_classes(Game.BF6)
        text = _format_classes(d)
        return Outgoing(text, KB.main_menu())

    if data == "show:bo7_zombies":
        d = catalog.load_classes(Game.BO7)
        text = _format_classes(d)
        return Outgoing(text, KB.main_menu())

    # picking flow
    if data.startswith("pick_game:"):
        g = data.split(":", 1)[1]
        p.game = _safe_enum(Game, g, Game.WARZONE)
        if p.game == Game.WARZONE:
            return Outgoing("Warzone: выбери режим:", KB.warzone_modes())
        if p.game == Game.BF6:
            p.mode = Mode.BF6_PVP
            return Outgoing("BF6: выбери устройство:", KB.device_menu())
        if p.game == Game.BO7:
            # по умолчанию зомби, можно расширить позже
            p.mode = Mode.BO7_ZOMBIES
            return Outgoing("BO7: выбери устройство:", KB.device_menu())
        return Outgoing("Выбери устройство:", KB.device_menu())

    if data.startswith("pick_mode:"):
        m = data.split(":", 1)[1]
        p.mode = _safe_enum(Mode, m, Mode.WZ_BR)
        return Outgoing("Выбери устройство:", KB.device_menu())

    if data.startswith("pick_device:"):
        d = data.split(":", 1)[1]
        p.device = _safe_enum(InputDevice, d, InputDevice.PS)
        return Outgoing("Выбери уровень:", KB.tier_menu())

    if data.startswith("pick_tier:"):
        t = data.split(":", 1)[1]
        p.tier = _safe_enum(SkillTier, t, SkillTier.NORMAL)
        return Outgoing(
            f"Готово ✅\nИгра: {p.game.value}\nРежим: {p.mode.value}\nУстройство: {p.device.value}\nУровень: {p.tier.value}\n\nЧто показать?",
            KB.show_menu(),
        )

    if data == "show:settings":
        pack = catalog.load_settings_pack(p.game, p.mode, p.device, p.tier)
        return Outgoing(_format_settings(pack), KB.main_menu())

    if data == "show:training":
        plan = catalog.load_training_plan(p.game, p.mode, p.tier)
        return Outgoing(_format_training(plan), KB.main_menu())

    return Outgoing(f"⚙️ {data} (в разработке)", KB.main_menu())


def _format_settings(pack) -> str:
    lines = []
    lines.append(f"✅ {pack.title}")
    lines.append(f"🗓 last_updated: {pack.last_updated}")
    lines.append(f"🔎 source: {pack.source}")
    lines.append("")
    for section, data in pack.settings.items():
        lines.append(f"[{section}]")
        if isinstance(data, dict):
            for k, v in data.items():
                lines.append(f"- {k}: {v}")
        elif isinstance(data, list):
            for x in data:
                lines.append(f"- {x}")
        else:
            lines.append(f"- {data}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_training(plan: dict) -> str:
    lines = [f"🎯 {plan.get('title','Training')}"]
    for b in plan.get("blocks", []):
        lines.append(f"\n{b.get('name','Block')}:")
        for s in b.get("steps", []):
            lines.append(f"- {s}")
    return "\n".join(lines).strip()


def _format_classes(data: dict) -> str:
    lines = [f"📚 {data.get('title','Info')}"]
    for c in data.get("classes", []):
        lines.append(f"\n{c['name']} — {c.get('role','')}")
        for f in c.get("focus", []):
            lines.append(f"- {f}")
    for m in data.get("modes", []):
        lines.append(f"\n{m['name']}:")
        for n in m.get("notes", []):
            lines.append(f"- {n}")
    return "\n".join(lines).strip()
