from __future__ import annotations

import pytest

from app.services.missions.contracts import MissionCompletionReport, validate_mission_payload


def _mission():
    return {
        "id": "m-19",
        "status": "candidate",
        "focus": "decision",
        "title": "CONTACT DISCIPLINE",
        "objective": "Не повторять проигранный пик.",
        "success_metric": "Три контакта с обязательной сменой линии.",
        "protocol": ["Первый контакт", "Смена линии", "Повторная оценка"],
    }


def test_completion_report_is_bounded():
    report = MissionCompletionReport(
        success=True,
        note="x" * 4000,
        score=10_000_000,
        matches=1_000_000,
        evidence={str(index): index for index in range(100)},
    ).normalized()
    assert report["success"] is True
    assert len(report["note"]) == 1200
    assert report["score"] == 1_000_000.0
    assert report["matches"] == 10_000
    assert len(report["evidence"]) == 20


def test_validate_mission_payload_rejects_non_measurable_or_foreign_shapes():
    valid = validate_mission_payload(_mission())
    assert valid["id"] == "m-19"
    assert valid["focus"] == "decision"

    broken = _mission()
    broken["success_metric"] = ""
    with pytest.raises(ValueError):
        validate_mission_payload(broken)

    broken = _mission()
    broken["focus"] = "unknown"
    with pytest.raises(ValueError):
        validate_mission_payload(broken)
