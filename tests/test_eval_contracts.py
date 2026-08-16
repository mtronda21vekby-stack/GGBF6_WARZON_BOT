from __future__ import annotations

import json
from pathlib import Path

from app.services.brain.intents import classify_intent
from app.services.brain.response_policy import get_response_policy


def test_offline_eval_contracts_route_deterministically():
    path = Path(__file__).parent / "evals" / "bco_answer_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) >= 18

    for case in cases:
        result = classify_intent(case["text"], {"game": "Warzone", "zombies_active": "0"})
        assert result.intent.value == case["intent"], case["text"]
        assert result.needs_current_data is bool(case.get("needs_current_data", False)), case["text"]
        policy = get_response_policy(result, {"voice": "TEAMMATE", "difficulty": "Normal"})
        assert policy.max_clarifying_questions <= int(case.get("max_clarifying_questions", 1)), case["text"]


def test_current_eval_cases_explicitly_require_freshness_guard():
    path = Path(__file__).parent / "evals" / "bco_answer_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    current = [c for c in cases if c.get("needs_current_data")]
    assert current
    assert all(c.get("must_refuse_unverified_currentness") is True for c in current)
