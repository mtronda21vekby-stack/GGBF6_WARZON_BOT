from __future__ import annotations

from app.core.outgoing import Outgoing
from app.domain.enums import Game, Mode, InputDevice, SkillTier
from app.content.catalog import ContentCatalog
from app.ui.keyboards import KB


catalog = ContentCatalog()


def format_settings(pack) -> str:
    lines = []
    lines.append(f"✅ *{pack.title}*")
    lines.append(f"🗓 last_updated: {pack.last_updated}")
    lines.append(f"🔎 source: {pack.source}")
    lines.append("")
    # flatten a bit
    for section, data in pack.settings.items():
        lines.append(f"*{section.upper()}*")
        if isinstance(data, dict):
            for k, v in data.items():
                lines.append(f"• {k}: {v}")
        elif isinstance(data, list):
            for x in data:
                lines.append(f"• {x}")
        else:
            lines.append(f"• {data}")
        lines.append("")
    return "\n".join(lines).strip()


def format_training(plan: dict) -> str:
    lines = [f"🎯 *{plan.get('title','Training')}*"]
    for b in plan.get("blocks", []):
        lines.append(f"\n*{b.get('name','Block')}*")
        for s in b.get("steps", []):
            lines.append(f"• {s}")
    return "\n".join(lines).strip()


def format_classes(data: dict) -> str:
    lines = [f"📚 *{data.get('title','Classes')}*"]
    for c in data.get("classes", []):
        lines.append(f"\n*{c['name']}* — {c.get('role','')}")
        for f in c.get("focus", []):
            lines.append(f"• {f}")
    # BO7 file uses "modes"
    for m in data.get("modes", []):
        lines.append(f"\n*{m['name']}*")
        for n in m.get("notes", []):
            lines.append(f"• {n}")
    return "\n".join(lines).strip()


async def handle_content_request(data: str) -> Outgoing:
    # data examples:
    # "pick_game:warzone" / "pick_mode:wz_br" / "pick_device:ps" / "pick_tier:pro"
    # "show:settings" / "show:training" / "show:classes_bf6"
    return Outgoing(
        text="⚙️ Неверная команда. Открой меню.",
        keyboard=KB.main_menu(),
    )
