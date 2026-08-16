from __future__ import annotations

from types import SimpleNamespace

from app.services.brain.ai_hook import AIHook


class FakeCompletions:
    def __init__(self, outputs=None, error=None):
        self.outputs = list(outputs or [])
        self.error = error
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        text = self.outputs.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class FakeClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def test_generation_meta_records_anti_repeat_recovery(monkeypatch):
    completions = FakeCompletions(outputs=["Same answer", "Different tactical angle"])
    hook = AIHook(api_key="test", max_attempts=2, base_sleep=0)
    monkeypatch.setattr(hook, "_client", lambda: FakeClient(completions))

    result = hook.generate(
        profile={"game": "Warzone"},
        history=[{"role": "assistant", "content": "Same answer"}],
        user_text="Почему умираю в ротации?",
    )
    assert result == "Different tactical angle"
    assert hook.last_generation_meta["attempts"] == 1
    assert hook.last_generation_meta["anti_repeat_retry"] is True
    assert hook.last_generation_meta["outcome"] == "ok"
    assert completions.calls == 2


def test_generation_meta_records_retry_exhaustion(monkeypatch):
    completions = FakeCompletions(error=RuntimeError("provider down"))
    hook = AIHook(api_key="test", max_attempts=3, base_sleep=0)
    monkeypatch.setattr(hook, "_client", lambda: FakeClient(completions))

    result = hook.generate(
        profile={"game": "Warzone"},
        history=[],
        user_text="Разбери мой файт",
    )
    assert "временно недоступен" in result
    assert hook.last_generation_meta["attempts"] == 3
    assert hook.last_generation_meta["outcome"] == "error"
    assert hook.last_generation_meta["error_class"] == "RuntimeError"
    assert completions.calls == 3
