from __future__ import annotations

from types import SimpleNamespace

from app.services.brain.ai_hook import AIHook


class FakeStream:
    def __init__(self, parts: list[str]):
        self.parts = parts
        self.closed = False

    def __iter__(self):
        for part in self.parts:
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=part))]
            )

    def close(self):
        self.closed = True


class FakeCompletions:
    def __init__(self):
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        if kwargs.get("stream"):
            return FakeStream(["Держи ", "высоту. ", "Ротируй раньше."])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="fallback"))]
        )


class FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeCompletions())
        self.closed = False

    def close(self):
        self.closed = True


def test_ai_hook_streams_accumulated_partial_text_and_final(monkeypatch):
    client = FakeClient()
    hook = AIHook(api_key="test", model="test-model")
    monkeypatch.setattr(hook, "_client", lambda: client)

    events: list[tuple[str, dict]] = []
    result = hook.generate(
        profile={
            "game": "Warzone",
            "platform": "Xbox",
            "input": "Controller",
            "difficulty": "Pro",
            "voice": "TEAMMATE",
        },
        history=[],
        user_text="Почему я поздно ротирую?",
        on_partial=lambda text, meta: events.append((text, dict(meta))),
    )

    assert result == "Держи высоту. Ротируй раньше."
    assert any(meta["phase"] == "generating" for _, meta in events)
    assert events[-1][0] == result
    assert events[-1][1]["phase"] == "final"
    assert hook.last_generation_meta["streamed"] is True
    assert hook.last_generation_meta["stream_chunks"] == 3
    assert client.chat.completions.calls[0]["stream"] is True
    assert client.closed is True


def test_partial_callback_failure_never_breaks_generation(monkeypatch):
    client = FakeClient()
    hook = AIHook(api_key="test", model="test-model")
    monkeypatch.setattr(hook, "_client", lambda: client)

    def broken_callback(_text, _meta):
        raise RuntimeError("presentation unavailable")

    result = hook.generate(
        profile={"game": "Warzone", "difficulty": "Normal", "voice": "TEAMMATE"},
        history=[],
        user_text="Дай совет по позиции",
        on_partial=broken_callback,
    )

    assert result.endswith("Ротируй раньше.")
    assert hook.last_generation_meta["outcome"] == "ok"
