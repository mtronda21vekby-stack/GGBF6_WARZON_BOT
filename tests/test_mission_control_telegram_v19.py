from __future__ import annotations

from app.ui.mission_control import mission_control_view


def _mission(status: str = "candidate") -> dict:
    return {
        "id": "mission-v19-test",
        "status": status,
        "focus": "positioning",
        "title": "ROTATION EDGE",
        "objective": "Начинать силовую ротацию до закрытия безопасного маршрута.",
        "why": "Повторяется поздняя ротация.",
        "protocol": [
            "До контакта отметить следующую сильную позицию.",
            "Начать движение до давления газа.",
            "После первого контакта не возвращаться на закрытую линию.",
        ],
        "match_rule": "Одна ранняя ротация в каждом матче.",
        "success_metric": "Три матча без смерти в газе по своей ошибке.",
        "duration_min": 25,
        "game": "Warzone",
        "input": "Controller",
        "difficulty": "Pro",
        "evidence": ["late_rotation ×3"],
    }


def test_candidate_view_is_actionable_and_structured():
    rendered = mission_control_view({"mission": _mission()})
    assert isinstance(rendered, tuple)
    text, markup = rendered
    assert "ROTATION EDGE" in text
    assert "пози" in text.casefold() or "rotation" in text.casefold()
    assert "метрик" in text.casefold() or "success" in text.casefold()
    assert isinstance(markup, dict)
    encoded = repr(markup)
    assert "mission-v19-test" in encoded
    assert "accept" in encoded.casefold() or "прин" in encoded.casefold()


def test_active_view_exposes_completion_action():
    text, markup = mission_control_view({"mission": _mission("active")})
    encoded = repr(markup)
    assert "ROTATION EDGE" in text
    assert "complete" in encoded.casefold() or "finish" in encoded.casefold() or "заверш" in encoded.casefold()
