from __future__ import annotations


class BrainEngine:
    def __init__(self, store, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    async def handle_text(self, user_id: int, text: str):
        p = self.profiles.get(user_id)

        # -------- CLASSES / ROLES --------
        if text.startswith("CLASS_"):
            return self._class_response(p, text)

        # -------- ZOMBIES --------
        if text.startswith("ZOMBIE_"):
            return self._zombie_plan(text)

        # -------- TRAINING --------
        if text.startswith("TRAIN_"):
            return self._training(p, text)

        # -------- DEFAULT --------
        return type(
            "R",
            (),
            {
                "text": (
                    f"🎮 {p.game.upper()} | 😈 {p.mode.upper()}\n\n"
                    "Опиши ситуацию:\n"
                    "• где умер\n"
                    "• чем\n"
                    "• дистанция\n\n"
                    "Я дам точный разбор."
                )
            },
        )

    # ---------------- CLASSES ----------------
    def _class_response(self, p, text: str):
        mode = p.mode

        if p.game == "bf6":
            # English only
            if "ASSAULT" in text:
                body = (
                    "BF6 — ASSAULT\n\n"
                    "ROLE:\n"
                    "- Frontline pressure\n"
                    "- Mid-range control\n\n"
                    "LOADOUT:\n"
                    "- AR\n"
                    "- Frag / Flash\n\n"
                    "TIP:\n"
                    "- Push after utility."
                )
            elif "ENGINEER" in text:
                body = (
                    "BF6 — ENGINEER\n\n"
                    "ROLE:\n"
                    "- Vehicle denial\n\n"
                    "LOADOUT:\n"
                    "- SMG / Carbine\n"
                    "- AT gadgets\n\n"
                    "TIP:\n"
                    "- Always flank armor."
                )
            elif "SUPPORT" in text:
                body = (
                    "BF6 — SUPPORT\n\n"
                    "ROLE:\n"
                    "- Sustain squad\n\n"
                    "LOADOUT:\n"
                    "- LMG\n"
                    "- Ammo / Heal\n\n"
                    "TIP:\n"
                    "- Hold power positions."
                )
            else:  # recon
                body = (
                    "BF6 — RECON\n\n"
                    "ROLE:\n"
                    "- Intel / picks\n\n"
                    "LOADOUT:\n"
                    "- Sniper / DMR\n"
                    "- Spot tools\n\n"
                    "TIP:\n"
                    "- Play information."
                )
        else:
            # Russian
            if p.game == "warzone":
                body = (
                    "WARZONE — КЛАСС\n\n"
                    "РОЛЬ:\n"
                    "• Контроль дистанции\n\n"
                    "СБОРКА:\n"
                    "• Основное оружие по роли\n"
                    "• Перки под выживание\n\n"
                    "СОВЕТ:\n"
                    "• Игра от позиции."
                )
            else:  # bo7
                body = (
                    "BO7 — РОЛЬ\n\n"
                    "РОЛЬ:\n"
                    "• Давление и контроль\n\n"
                    "СОВЕТ:\n"
                    "• Игра от таймингов\n"
                    "• Контроль спавнов"
                )

        prefix = {
            "normal": "🧠 Normal — стабильно.\n\n",
            "pro": "🔥 Pro — жёстко.\n\n",
            "demon": "😈 Demon — доминируй.\n\n",
        }.get(mode, "")

        return type("R", (), {"text": prefix + body})

    # ---------------- ZOMBIES ----------------
    def _zombie_plan(self, text: str):
        if "BEGINNER" in text:
            body = "🧟 Zombies Beginner — выживание и маршрут."
        elif "PRO" in text:
            body = "🔥 Zombies Pro — контроль орд."
        else:
            body = "😈 Zombies Demon — абсолютный контроль."
        return type("R", (), {"text": body})

    # ---------------- TRAINING ----------------
    def _training(self, p, text: str):
        minutes = text.replace("TRAIN_", "")
        return type(
            "R",
            (),
            {
                "text": (
                    f"🎯 {minutes} мин | {p.mode.upper()}\n\n"
                    "• AIM\n"
                    "• MOVEMENT\n"
                    "• MINDSET\n\n"
                    "Дисциплина > талант."
                )
            },
        )
