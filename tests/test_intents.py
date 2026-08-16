from app.services.brain.intents import Intent, classify_intent


def test_greeting():
    assert classify_intent("Привет").intent is Intent.CASUAL


def test_loadout():
    assert classify_intent("Дай сборку на AR под мою роль").intent is Intent.LOADOUT


def test_current_meta():
    result = classify_intent("Какая сейчас мета в Warzone?")
    assert result.intent is Intent.META_CURRENT
    assert result.needs_current_data is True


def test_death_analysis_beats_positioning_keyword():
    assert classify_intent("Почему я умираю на ротации?").intent is Intent.DEATH_ANALYSIS


def test_training():
    assert classify_intent("Сделай тренировку на аим").intent is Intent.TRAINING


def test_zombies():
    assert classify_intent("Что брать первым на Ashes?").intent is Intent.ZOMBIES


def test_settings():
    assert classify_intent("Настрой сенсу под Xbox controller").intent is Intent.GAME_SETTINGS
