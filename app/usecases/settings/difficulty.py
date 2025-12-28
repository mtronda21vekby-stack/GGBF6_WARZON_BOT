from app.core.outgoing import Outgoing
from app.ui.keyboards import KB
from app.domain.difficulty import Difficulty


def select_difficulty(profiles, user_id: int, level: Difficulty) -> Outgoing:
    p = profiles.get(user_id)
    p.difficulty = level

    label = {
        Difficulty.NORMAL: "🧠 NORMAL",
        Difficulty.PRO: "🔥 PRO",
        Difficulty.DEMON: "😈 DEMON",
    }[level]

    return Outgoing(
        text=f"Режим сложности: {label}",
        inline_keyboard=KB.main_inline(),
        ensure_quickbar=True,
    )
