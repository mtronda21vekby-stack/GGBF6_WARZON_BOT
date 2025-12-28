from __future__ import annotations


class BrainEngine:
    def __init__(self, store, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    async def handle_text(self, user_id: int, text: str):
        p = self.profiles.get(user_id)

        mode = p.mode
        game = p.game
        device = p.device

        prefix = {
            "normal": "🧠 Normal режим — учимся стабильно.",
            "pro": "🔥 Pro режим — играем на результат.",
            "demon": "😈 Demon режим — доминируем.",
        }.get(mode, "")

        base = f"{prefix}\n🎮 {game.upper()} | 🕹 {device.upper()}\n\n"

        if text == "TRAIN_15":
            return self._training_plan(base, 15, mode)

        if text == "TRAIN_30":
            return self._training_plan(base, 30, mode)

        if text == "TRAIN_60":
            return self._training_plan(base, 60, mode)

        return type(
            "R",
            (),
            {
                "text": base
                + "Опиши ситуацию:\n"
                + "• где умер\n"
                + "• режим\n"
                + "• что не получилось\n\n"
                + "Я дам точный разбор.",
            },
        )

    def _training_plan(self, base: str, minutes: int, mode: str):
        if mode == "normal":
            plan = (
                "AIM:\n• Трекинг — 5 мин\n• Флики — 5 мин\n\n"
                "MOVEMENT:\n• Стрейф — 3 мин\n• Слайды — 2 мин\n\n"
                "FOCUS:\n• Не спеши, контроль."
            )
        elif mode == "pro":
            plan = (
                "AIM:\n• Head tracking — 10 мин\n• Micro flicks — 5 мин\n\n"
                "MOVEMENT:\n• Shoulder peek — 5 мин\n• Jump timing — 5 мин\n\n"
                "FOCUS:\n• Тайминги, позиции."
            )
        else:  # demon
            plan = (
                "AIM:\n• One-clip drills — 15 мин\n\n"
                "MOVEMENT:\n• Aggressive peeks — 10 мин\n\n"
                "MENTAL:\n• Дави, не отступай.\n"
                "• Каждая дуэль — победа."
            )

        return type(
            "R",
            (),
            {
                "text": f"{base}🎯 Тренировка {minutes} мин\n\n{plan}",
            },
        )
