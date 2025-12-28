# app/services/brain/engine.py  (ЗАМЕНИ ЦЕЛИКОМ)
from __future__ import annotations

from dataclasses import dataclass

from app.content.presets import PRESETS  # если файла нет — скажи, я дам целиком
from app.services.brain.memory import InMemoryStore


@dataclass
class BrainReply:
    text: str


def _mode_prefix(mode: str) -> str:
    if mode == "demon":
        return "😈 DEMON TEAMMATE"
    if mode == "pro":
        return "🔥 PRO TEAMMATE"
    return "🧠 COACH"


def _pick_focus_ru(msg: str) -> str:
    m = msg.lower()
    if any(k in m for k in ["аим", "aim", "метк", "трек", "отдач", "реакц"]):
        return "AIM"
    if any(k in m for k in ["мув", "movement", "слайд", "стрейф", "прыж", "уклон"]):
        return "MOVEMENT"
    if any(k in m for k in ["пози", "position", "ротац", "угол", "зона", "пуш", "пик"]):
        return "POSITIONING"
    return "HYBRID"


def _render_settings(game: str, mode: str, device: str) -> str:
    game = (game or "warzone").lower()
    mode = (mode or "normal").lower()
    device = (device or "ps").lower()

    pack = PRESETS.get(game, {}).get(mode, {}).get(device)
    if not pack:
        return "⚙️ Настройки: пресет не найден (проверь игру/устройство/режим)."

    title = pack.get("title", "")
    settings = pack.get("settings", {})

    # ЯЗЫК: BF6 settings EN, остальные RU — это задано содержимым PRESETS
    lines = [f"⚙️ НАСТРОЙКИ\n{title}"]
    for group, items in settings.items():
        lines.append(f"\n{group}:")
        for k, v in items.items():
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def _teammate_response_ru(game: str, mode: str, device: str, msg: str) -> str:
    focus = _pick_focus_ru(msg)

    tone = {
        "normal": "Спокойно. Сейчас разберём и исправим.",
        "pro": "Ок. Дисциплина. Ноль бесплатных смертей.",
        "demon": "Соберись. Мы забираем лобби. Контроль, тайминг, доминация.",
    }.get(mode, "Спокойно. Сейчас разберём и исправим.")

    checklist = [
        "Колл: где враг, сколько их, высота/угол.",
        "Правило: укрытие → угол → первый урон → добив.",
        "Решение: если нет преимущества — ресет и переигровка.",
    ]

    drills = [
        "10 мин: tracking (вести цель, не дёргать).",
        "10 мин: recoil (одна пушка, 2 дистанции).",
        "10 мин: peeks (wide/tight + откат в укрытие).",
    ]
    if focus == "POSITIONING":
        drills.append("5 мин: ротации — всегда знай 2 выхода и 1 safe-угол.")
    if mode == "demon":
        drills.append("Матч-цель: не пушишь без инфо. Сначала контроль, потом убийство.")

    q = "Один вопрос: где умер (внутри/открыто/высота) и чем сняли (AR/SMG/sniper)?"

    return (
        f"{tone}\n\n"
        f"🧩 Фокус: {focus}\n"
        f"🎮 {game.upper()} | 🕹 {device.upper()} | 🎭 {mode.upper()}\n\n"
        f"📞 Тиммейт-чеклист:\n- {checklist[0]}\n- {checklist[1]}\n- {checklist[2]}\n\n"
        f"🧠 Вопрос:\n{q}\n\n"
        f"🔥 Упражнения:\n" + "\n".join(f"• {d}" for d in drills)
    )


class BrainEngine:
    def __init__(self, store: InMemoryStore, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    async def handle_text(self, user_id: int, text: str) -> BrainReply:
        p = self.profiles.get(user_id)
        game = p.game
        device = p.device
        mode = p.mode

        if p.memory_enabled:
            self.store.add(user_id, "user", text)

        prefix = _mode_prefix(mode)
        teammate = _teammate_response_ru(game, mode, device, text)
        settings_block = _render_settings(game, mode, device)

        out = f"{prefix}\n\n{teammate}\n\n{settings_block}"

        if p.memory_enabled:
            self.store.add(user_id, "assistant", out)

        return BrainReply(text=out)
