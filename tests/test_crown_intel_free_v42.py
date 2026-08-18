from types import SimpleNamespace

from app.services.brain.crown_intel_runtime import FreeCrownIntelRuntime
from app.services.brain.knowledge_context import CompositeKnowledgeProvider


class FakeOfficialProvider:
    def __init__(self):
        self.games = []

    def _load_document(self, game):
        self.games.append(game)
        return SimpleNamespace(published="2026-08-18")


def test_autonomous_refresh_covers_supported_worlds_without_paid_api():
    provider = FakeOfficialProvider()
    runtime = FreeCrownIntelRuntime(provider=provider, interval_s=21600, enabled=False)
    result = runtime.refresh_once()
    assert result["ok"] is True
    assert result["success"] == 3
    assert provider.games == ["warzone", "bo7", "bf6"]
    snapshot = runtime.snapshot()
    assert snapshot["zero_extra_paid_api"] is True
    assert snapshot["sources"] == ["callofduty.com", "ea.com"]


def test_engine_uses_shared_free_provider(monkeypatch):
    from app.services.brain import engine as engine_module

    sentinel = FakeOfficialProvider()
    monkeypatch.setattr(engine_module, "get_free_official_provider", lambda **_: sentinel)
    settings = SimpleNamespace(
        live_knowledge_enabled=True,
        live_knowledge_ttl_s=900,
        live_knowledge_timeout_s=6.0,
    )
    brain = engine_module.BrainEngine(store=object(), profiles=object(), settings=settings)
    assert isinstance(brain.knowledge_provider, CompositeKnowledgeProvider)
    assert brain.knowledge_provider.providers[0] is sentinel


def test_refresh_failure_isolated_per_game():
    class PartialProvider:
        def _load_document(self, game):
            if game == "bo7":
                raise RuntimeError("source unavailable")
            return SimpleNamespace(published="2026-08-18")

    runtime = FreeCrownIntelRuntime(provider=PartialProvider(), interval_s=21600, enabled=False)
    result = runtime.refresh_once()
    assert result["ok"] is True
    assert result["success"] == 2
    assert result["errors"] == 1
    assert result["games"]["bo7"] == "RuntimeError"
