from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.operator_intelligence.strategy_outcomes import PremiumStrategyOutcomeService


class Store:
    def __init__(self):
        self.rows = []
        self.clock = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)

    def add_progression_event(self, chat_id, event):
        self.clock += timedelta(seconds=1)
        row = dict(event)
        row.setdefault("created_at", self.clock.isoformat())
        self.rows.append(row)

    def list_progression_events(self, chat_id, limit=120):
        return [dict(x) for x in reversed(self.rows[-limit:])]


def strategy(focus="rotations", strategy_class="regression_intercept"):
    return {
        "strategy_class": strategy_class,
        "focus": focus,
        "confidence": "medium",
        "objective": f"Run controlled {focus}",
        "success_condition": "2 of 3 clean explicit outcomes",
    }


def complete(store, outcome, focus="rotations"):
    store.add_progression_event(7, {
        "type": "operator_mission",
        "status": "completed",
        "mission_id": f"m-{len(store.rows)}",
        "focus": focus,
        "outcome": outcome,
        "source": "explicit_operator_report",
    })


def test_repeated_read_is_idempotent_until_new_explicit_cycle():
    store = Store()
    service = PremiumStrategyOutcomeService(store)
    first = service.record_issue(7, strategy())
    repeated = service.record_issue(7, strategy())
    assert first == repeated
    assert sum(row.get("type") == "premium_strategy" for row in store.rows) == 1

    complete(store, "clean")
    next_generation = service.record_issue(7, strategy())
    assert next_generation != first
    issued = [row for row in store.rows if row.get("type") == "premium_strategy"]
    assert [row["generation"] for row in issued] == [0, 1]


def test_two_clean_followups_support_association_without_causation():
    store = Store()
    service = PremiumStrategyOutcomeService(store)
    sid = service.record_issue(7, strategy())
    complete(store, "clean")
    complete(store, "clean")
    snap = service.snapshot(7)
    item = next(row for row in snap["evaluations"] if row["strategy_id"] == sid)
    assert item["verdict"] == "supported_association"
    assert item["matched_cycles"] == 2
    assert item["outcomes"] == {"clean": 2, "mixed": 0, "failed": 0}
    assert item["causal_claim"] is False
    assert snap["truth_contract"]["association_not_causation"] is True
    assert snap["truth_contract"]["causal_claims"] is False


def test_two_failed_followups_mark_unsupported_association():
    store = Store()
    service = PremiumStrategyOutcomeService(store)
    service.record_issue(7, strategy("positioning", "consistency_build"))
    complete(store, "failed", "positioning")
    complete(store, "failed", "positioning")
    snap = service.snapshot(7)
    assert snap["latest"]["verdict"] == "unsupported_association"
    assert snap["by_strategy_class"]["consistency_build"]["unsupported"] == 1


def test_mixed_and_unrelated_focus_do_not_fake_support():
    store = Store()
    service = PremiumStrategyOutcomeService(store)
    service.record_issue(7, strategy("movement", "consistency_build"))
    complete(store, "clean", "aim")
    complete(store, "clean", "movement")
    complete(store, "failed", "movement")
    snap = service.snapshot(7)
    assert snap["latest"]["matched_cycles"] == 2
    assert snap["latest"]["verdict"] == "mixed_association"
    assert snap["latest"]["outcomes"] == {"clean": 1, "mixed": 0, "failed": 1}


def test_prior_missions_are_not_attributed_to_later_strategy():
    store = Store()
    complete(store, "clean", "rotations")
    complete(store, "clean", "rotations")
    service = PremiumStrategyOutcomeService(store)
    service.record_issue(7, strategy())
    snap = service.snapshot(7)
    assert snap["latest"]["matched_cycles"] == 0
    assert snap["latest"]["verdict"] == "insufficient_followup"
