from __future__ import annotations

from app.content.presets import PRESETS


def _fmt_dict(d: dict, indent: str = "") -> str:
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{indent}{k}:")
            lines.append(_fmt_dict(v, indent + "  "))
        else:
            lines.append(f"{indent}- {k}: {v}")
    return "\n".join(lines)


def render_settings(game: str, difficulty: str, device: str) -> str:
    game = (game or "warzone").lower()
    difficulty = (difficulty or "normal").lower()
    device = (device or "ps").lower()
    if device == "pad":
        device = "ps"  # если пользователь выбрал controller без уточнения — дефолт PS

    pack = PRESETS.get(game, {}).get(difficulty, {}).get(device)
    if not pack:
        return "⚙️ Настройки: пресет не найден (проверь игру/устройство/сложность)."

    title = pack["title"]
    settings = pack["settings"]

    # Ключевое правило языка: BF6 settings EN only; others RU
    # Мы ничего не переводим автоматически — берём как есть из PRESETS.
    return f"⚙️ SETTINGS\n{title}\n\n{_fmt_dict(settings)}"
