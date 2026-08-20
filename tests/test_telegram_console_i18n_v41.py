from app.services.telegram.console_i18n import install


def test_russian_command_console_buttons_are_localized():
    install()
    from app.ui.command_console import home_view
    view = home_view({"language":"ru","game":"Warzone","platform":"PC","input":"Controller","difficulty":"Demon","voice":"TEAMMATE","role":"Flex"})
    labels = [b["text"] for row in view.reply_markup["inline_keyboard"] for b in row]
    assert "🧠 AI СВОДКА" in labels
    assert "🎯 ТРЕНИРОВКА" in labels
    assert "🎮 ИГРА" in labels
    assert "🎬 VOD РАЗБОР" in labels
    assert "🛰 ЦЕНТР УПРАВЛЕНИЯ" in labels or all("COMMAND CENTER" not in x for x in labels)
    assert "↻ ОБНОВИТЬ" in labels
    assert "✕ ЗАКРЫТЬ" in labels
    assert "CURRENT CONTEXT:" not in view.text
    assert "ТЕКУЩИЙ КОНТЕКСТ:" in view.text


def test_english_command_console_has_no_russian_navigation():
    install()
    from app.ui.command_console import home_view
    view = home_view({"language":"en","game":"Warzone","platform":"PC","input":"Controller","difficulty":"Pro","voice":"COACH","role":"Flex"})
    labels = [b["text"] for row in view.reply_markup["inline_keyboard"] for b in row]
    assert "🧠 AI BRIEF" in labels
    assert "🎯 TRAINING" in labels
    assert "↻ REFRESH" in labels
    assert "✕ CLOSE" in labels
    assert "Выбери модуль" not in view.text
    assert "Choose a module" in view.text
