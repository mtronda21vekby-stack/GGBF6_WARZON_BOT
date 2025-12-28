from __future__ import annotations

from dataclasses import dataclass

from app.services.brain.formatter import render_settings


@dataclass
class BrainReply:
    text: str


def _style_prefix(diff: str) -> str:
    diff = (diff or "normal").lower()
    if diff == "demon":
        return "😈 DEMON TEAMMATE"
    if diff == "pro":
        return "🔥 PRO TEAMMATE"
    return "🧠 COACH"


def _teammate_plan_ru(diff: str, text: str) -> str:
    diff = (diff or "normal").lower()

    # более “жёсткий” демон, но без токсичности
    tone = {
        "normal": "Спокойно. Сейчас разберём и исправим.",
        "pro": "Ок. Будем играть дисциплинированно и без бесплатных смертей.",
        "demon": "Соберись. Мы забираем лобби. Ноль хаоса — только контроль.",
    }[diff]

    # 1 уточняющий вопрос максимум (как тиммейт)
    question = "Один вопрос: где именно умер (в здании/открыто/высота) и чем тебя сняли (AR/SMG/sniper)?"

    # универсальный тиммейт-чеклист
    checklist = [
        "Колл: где враг, сколько их, на какой высоте.",
        "Правило: сначала укрытие/угол → потом стрельба.",
        "Следующий шаг: либо ресет (откат+хил), либо добив с преимуществом.",
    ]

    drills = [
        "10 мин: tracking (плавно вести цель)",
        "10 мин: recoil control (одна пушка, 2 дистанции)",
        "10 мин: angle-peek (wide/tight + возврат в укрытие)",
    ]

    if diff == "demon":
        drills.append("Матч: играешь 1 цель — НЕ умирать бесплатно на ротации. Если сомневаешься — не пушишь.")

    out = (
        f"{tone}\n\n"
        f"🧩 Диагноз (по твоему сообщению): я вижу, что тебе не хватает структуры в моменте.\n"
        f"🎯 Цель: повысить выживаемость + качество энгажментов.\n\n"
        f"📞 Тиммейт-режим:\n- {checklist[0]}\n- {checklist[1]}\n- {checklist[2]}\n\n"
        f"🧠 Один вопрос:\n{question}\n\n"
        f"🔥 Тренировка на сегодня:\n" + "\n".join(f"• {d}" for d in drills) +
        f"\n\n📝 Ты написал:\n{text}"
    )
    return out


class BrainEngine:
    def __init__(self, store, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    async def handle_text(self, user_id: int, text: str) -> BrainReply:
        p = self.profiles.get(user_id) if self.profiles else None

        game = (getattr(p, "game", None) or "warzone").lower()
        device = (getattr(p, "device", None) or "ps").lower()   # ps/xbox/pc or kbm/pad
        diff = (getattr(p, "difficulty", None) or "normal").lower()

        # “PC” можно задавать как kbm
        if device == "kbm":
            device = "pc"
        if device == "pad":
            device = "ps"

        prefix = _style_prefix(diff)
        teammate = _teammate_plan_ru(diff, text)

        settings_block = render_settings(game=game, difficulty=diff, device=device)

        # ВАЖНО: настройки будут на EN только если game == bf6,
        # потому что в PRESETS bf6 settings уже EN, остальные RU.
        final = f"{prefix}\n\n{teammate}\n\n{settings_block}"

        return BrainReply(text=final)

    def clear_memory(self, user_id: int) -> None:
        if self.store:
            self.store.clear(user_id)

    def toggle_ai(self, user_id: int) -> bool:
        # если позже подключим OpenAI — тут будет переключатель
        p = self.profiles.get(user_id)
        p.ai_enabled = not getattr(p, "ai_enabled", True)
        return p.ai_enabled
