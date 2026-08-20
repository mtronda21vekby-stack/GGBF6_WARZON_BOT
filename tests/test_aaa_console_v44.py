from pathlib import Path

from app.ui.aaa_console import aaa_home_view, modules_view, war_room_view


def _callbacks(view):
    return {
        button.get("callback_data")
        for row in view.reply_markup.get("inline_keyboard", [])
        for button in row
        if button.get("callback_data")
    }


def _snapshot():
    return {
        "operator": {"readiness": "CALIBRATING", "risk": "UNKNOWN", "confidence": "LOW", "session_momentum": "STABLE"},
        "mission": {"title": "Late Rotation Discipline", "objective": "Retain strong position before committing.", "success_condition": "2/3 clean executions"},
        "session": {"phase": "PRE_SESSION"},
    }


def test_home_is_calm_but_exposes_power_ru():
    view = aaa_home_view({"language": "ru", "game": "Warzone", "difficulty": "Demon", "voice": "TEAMMATE"}, _snapshot())
    assert "CROWN // READY" in view.text
    assert "PLAYER BRAIN" in view.text
    assert "Late Rotation Discipline" in view.text
    callbacks = _callbacks(view)
    assert {"bco:warroom", "bco:profile", "bco:voice", "bco:modules", "bco:home", "bco:close"}.issubset(callbacks)
    assert "bco:premium" not in callbacks  # specialist modules stay one level deeper


def test_modules_preserve_complete_capability_access():
    view = modules_view({"language": "ru"})
    callbacks = _callbacks(view)
    expected = {"bco:ai", "bco:training", "bco:world", "bco:vod", "bco:zombies", "bco:profile", "bco:premium", "bco:system", "bco:voice", "bco:home"}
    assert expected == callbacks
    labels = " ".join(button.get("text", "") for row in view.reply_markup["inline_keyboard"] for button in row)
    for label in ("AI СВОДКА", "ТРЕНИРОВКА", "VOD РАЗБОР", "ОПЕРАТОР", "ПРЕМИУМ", "СИСТЕМА", "ГОЛОС"):
        assert label in labels


def test_war_room_is_evidence_first_and_bilingual():
    ru = war_room_view({"language": "ru", "game": "Warzone"}, _snapshot())
    en = war_room_view({"language": "en", "game": "Warzone"}, _snapshot())
    assert "WAR ROOM // PRE_SESSION" in ru.text
    assert "УВЕРЕННОСТЬ — LOW" in ru.text
    assert "предположение не выдаётся за факт" in ru.text
    assert "CONFIDENCE — LOW" in en.text
    assert "inference is never presented as verified fact" in en.text
    assert "%" not in ru.text and "%" not in en.text


def test_mini_app_war_room_is_additive_and_loaded_after_operator():
    app = Path("app/webapp/static/app.js").read_text(encoding="utf-8")
    war = Path("app/webapp/static/bco.war-room.js").read_text(encoding="utf-8")
    assert app.index("/webapp/bco.operator.js") < app.index("/webapp/bco.war-room.js")
    assert "__BCO_WAR_ROOM_V44_LOADED__" in war
    assert "No hidden score" in war
    assert "Unknown remains unknown" in war
    assert "music visualizer" not in war.lower()
