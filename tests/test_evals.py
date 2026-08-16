import json
from pathlib import Path

from app.services.brain.intents import classify_intent


def test_eval_cases_route_as_expected():
    cases = json.loads(Path("tests/evals/bco_answer_cases.json").read_text(encoding="utf-8"))
    for case in cases:
        result = classify_intent(case["text"])
        assert result.intent.value == case["intent"], case["text"]
