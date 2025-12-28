# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services.brain.ai_hook import AIHook


class BrainEngine:
    def __init__(self, store, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings
        self.ai = AIHook()

    async def handle_text(self, user_id: int, text: str):
        profile = self.profiles.get(user_id)

        game = getattr(profile, "game", "warzone")
        mode = getattr(profile, "mode", "normal")
        role = getattr(profile, "role", None)

        platform = getattr(profile, "platform", None)
        input_ = getattr(profile, "input", None)
        world_settings = getattr(profile, "world_settings", None)

        # ----- OFFLINE PREMIUM BASE (всегда работает) -----
        base = self._offline_premium(text, game, mode, role)

        # memory hint (если есть store/memory) — безопасно, не ломаем
        memory_hint = None
        try:
            # если у тебя store умеет читать “последнюю частую ошибку” — подставишь тут
            memory_hint = None
        except Exception:
            memory_hint = None

        # ----- AI ADDON (если включен) -----
        ai_text = await self.ai.analyze(
            game=game,
            mode=mode,
            role=role,
            platform=platform,
            input_=input_,
            world_settings=world_settings if isinstance(world_settings, dict) else {},
            user_text=text,
            memory_hint=memory_hint,
        )

        final = base
        if ai_text:
            final = f"{base}\n\n🤖 AI COACH:\n{ai_text}"

        return type("Reply", (), {"text": final})

    def _offline_premium(self, text: str, game: str, mode: str, role: str | None) -> str:
        g = (game or "warzone").upper()
        m = (mode or "normal").upper()
        r = (role.upper() if role else "—")

        if (game or "").lower() == "bf6":
            # BF6 settings labels EN
            header = f"🪖 BF6 | MODE: {m} | ROLE: {r}"
        else:
            header = f"🎮 {g} | РЕЖИМ: {m} | РОЛЬ: {r}"

        if (mode or "").lower() == "demon":
            body = (
                "❌ Это не аим. Это решение.\n"
                "1) Причина: тайминг/позиция/угол.\n"
                "2) Сейчас: выход + укрытие + темп.\n"
                "3) Дальше: играй от трейда/инфы.\n"
                "4) 10 мин: контроль углов + микро-флики."
            )
        elif (mode or "").lower() == "pro":
            body = (
                "1) Причина: позиция/тайминг.\n"
                "2) Сейчас: стабилизируй выход.\n"
                "3) Дальше: планируй трейд/маршрут.\n"
                "4) 10 мин: pre-aim + tracking."
            )
        else:
            body = (
                "1) Причина: невыгодная ситуация.\n"
                "2) Сейчас: играй от укрытия.\n"
                "3) Дальше: меньше риска без инфы.\n"
                "4) 10 мин: базовый контроль прицела."
            )

        return f"{header}\n\n{body}"
