from types import SimpleNamespace

from app.services.brain.crown_intel_ledger import CrownIntelLedger
from app.services.brain.crown_intel_runtime import FreeCrownIntelRuntime


class MemoryLedger(CrownIntelLedger):
    def __init__(self):
        self.snapshots = []
        self.changes = []

    def _rows(self, method, table, *, params=None, payload=None, prefer=""):
        if method == "GET" and table == "bco_game_intel_snapshots":
            game = str((params or {}).get("game", "")).replace("eq.", "")
            rows = [x for x in self.snapshots if x["game"] == game]
            return rows[-1:] if rows else []
        if method == "GET" and table == "bco_game_intel_changes":
            game = str((params or {}).get("game", "")).replace("eq.", "")
            rows = [x for x in self.changes if x["game"] == game]
            return rows[-1:] if rows else []
        if method == "POST" and table == "bco_game_intel_snapshots":
            if not any(x["game"] == payload["game"] and x["content_hash"] == payload["content_hash"] for x in self.snapshots):
                self.snapshots.append(dict(payload))
            return []
        if method == "POST" and table == "bco_game_intel_changes":
            if not any(x["game"] == payload["game"] and x["to_hash"] == payload["to_hash"] for x in self.changes):
                self.changes.append(dict(payload))
            return []
        return []


def doc(*blocks):
    return SimpleNamespace(
        game="warzone",
        title="Warzone Patch Notes",
        url="https://www.callofduty.com/patchnotes/warzone",
        published="2026-08-18",
        fetched_at="2026-08-18T02:00:00+00:00",
        blocks=blocks,
    )


def test_first_snapshot_is_baseline_then_only_real_diff_becomes_change():
    ledger = MemoryLedger()

    first = ledger.record_document(doc("Weapons", "Rifle damage 30"))
    assert first["changed"] is False
    assert first["baseline"] is True
    assert ledger.latest_change("warzone") == {}

    same = ledger.record_document(doc("Weapons", "Rifle damage 30"))
    assert same["changed"] is False
    assert same["baseline"] is False
    assert ledger.latest_change("warzone") == {}

    changed = ledger.record_document(doc("Weapons", "Rifle damage 27", "Recoil increased"))
    assert changed["changed"] is True
    assert changed["baseline"] is False
    assert "weapons" in changed["categories"]
    assert "Rifle damage 27" in changed["added_blocks"]
    assert "Rifle damage 30" in changed["removed_blocks"]
    assert len(ledger.snapshots) == 2
    assert len(ledger.changes) == 1


def test_personal_meta_suppresses_irrelevant_noise_and_promotes_weapon_change():
    ledger = MemoryLedger()
    weapon_change = {
        "categories": ["weapons"],
        "added_blocks": ["SMG damage range increased"],
    }
    impact = ledger.personalize(weapon_change, {"game": "Warzone", "role": "Entry"}, query_text="what is current meta")
    assert impact.relevant is True
    assert impact.score >= 3
    assert impact.alert

    map_change = {"categories": ["maps"], "added_blocks": ["Map lighting adjusted"]}
    quiet = ledger.personalize(map_change, {"game": "Warzone", "role": "Entry"}, query_text="best smg meta")
    assert quiet.relevant is False
    assert quiet.alert == ""


def test_runtime_persists_documents_without_turning_ledger_failure_into_source_failure():
    class Provider:
        def _load_document(self, game):
            return SimpleNamespace(game=game, published="2026-08-18", title="Patch", url="https://www.callofduty.com/patchnotes/x", fetched_at="2026-08-18T02:00:00+00:00", blocks=("Weapons changed",))

    class Ledger:
        def __init__(self): self.games = []
        def record_document(self, document):
            self.games.append(document.game)
            return {"changed": True}

    ledger = Ledger()
    runtime = FreeCrownIntelRuntime(provider=Provider(), ledger=ledger, enabled=False)
    result = runtime.refresh_once()
    assert result["success"] == 3
    assert result["changed"] == 3
    assert ledger.games == ["warzone", "bo7", "bf6"]
