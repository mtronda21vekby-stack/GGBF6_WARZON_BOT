from __future__ import annotations


class BrainEngine:
    def __init__(self, store, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    async def handle_text(self, user_id: int, text: str):
        p = self.profiles.get(user_id)

        # ---------- ZOMBIES ----------
        if text == "ZOMBIE_BEGINNER":
            return self._zombie_plan("beginner")

        if text == "ZOMBIE_PRO":
            return self._zombie_plan("pro")

        if text == "ZOMBIE_DEMON":
            return self._zombie_plan("demon")

        # ---------- TRAINING ----------
        if text.startswith("TRAIN_"):
            return self._training(user_id, text)

        # ---------- DEFAULT ----------
        return type(
            "R",
            (),
            {
                "text": (
                    f"🎮 {p.game.upper()} | 😈 {p.mode.upper()}\n\n"
                    "Опиши ситуацию:\n"
                    "• где умер\n"
                    "• чем убили\n"
                    "• что делал\n\n"
                    "Я скажу, где ошибка."
                )
            },
        )

    # ---------------- ZOMBIES ----------------
    def _zombie_plan(self, level: str):
        if level == "beginner":
            text = (
                "🧟 ZOMBIES — НОВИЧОК\n\n"
                "ЦЕЛЬ:\n"
                "• Дожить до 20+ раунда\n\n"
                "ОСНОВЫ:\n"
                "• Не бегай по карте хаотично\n"
                "• Используй один маршрут\n"
                "• Ремонт баррикад в начале\n\n"
                "ОШИБКИ:\n"
                "• Ранний Pack-a-Punch\n"
                "• Паника в углах"
            )
        elif level == "pro":
            text = (
                "🔥 ZOMBIES — PRO\n\n"
                "ЦЕЛЬ:\n"
                "• Контроль орд\n"
                "• Экономика очков\n\n"
                "ТАКТИКА:\n"
                "• Train zombies\n"
                "• Убивай только когда орда собрана\n"
                "• Минимум перков — максимум контроля\n\n"
                "ОШИБКИ:\n"
                "• Стрельба по одиночкам\n"
                "• Потеря маршрута"
            )
        else:  # demon
            text = (
                "😈 ZOMBIES — DEMON\n\n"
                "ТЫ НЕ ВЫЖИВАЕШЬ — ТЫ КОНТРОЛИРУЕШЬ.\n\n"
                "ПРИНЦИПЫ:\n"
                "• Орда = инструмент\n"
                "• Карта — твоя арена\n"
                "• Убивай только когда выгодно\n\n"
                "ФОКУС:\n"
                "• Тайминги спавна\n"
                "• Escape routes\n"
                "• Хладнокровие\n\n"
                "ОШИБКА = СМЕРТЬ."
            )

        return type("R", (), {"text": text})

    # ---------------- TRAINING ----------------
    def _training(self, user_id: int, text: str):
        p = self.profiles.get(user_id)

        minutes = text.replace("TRAIN_", "")
        return type(
            "R",
            (),
            {
                "text": (
                    f"🎯 ТРЕНИРОВКА {minutes} МИН\n"
                    f"😈 РЕЖИМ: {p.mode.upper()}\n\n"
                    "• AIM — контроль\n"
                    "• MOVEMENT — выживание\n"
                    "• MINDSET — холод\n\n"
                    "Дисциплина важнее таланта."
                )
            },
        )
