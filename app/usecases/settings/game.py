from app.core.outgoing import Outgoing
from app.ui.keyboards import KB
from app.domain.games import Game


def select_game(profiles, user_id: int, game: Game) -> Outgoing:
    p = profiles.get(user_id)
    p.game = game

    return Outgoing(
        text=f"🎮 Игра выбрана: {game.value.upper()}",
        inline_keyboard=KB.settings_device(game),
        ensure_quickbar=True,
    )
