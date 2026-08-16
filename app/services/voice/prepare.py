# -*- coding: utf-8 -*-
from __future__ import annotations

from app.config import get_settings
from app.services.voice.piper_backend import PiperBackend, PiperModelManager


def main() -> int:
    settings = get_settings()
    if not bool(getattr(settings, "voice_enabled", True)):
        print("BCO voice preload: disabled")
        return 0

    manager = PiperModelManager(
        model_dir=getattr(settings, "voice_model_dir", ".bco_voice"),
        model_name=getattr(settings, "voice_model_name", "ru_RU-denis-medium"),
        timeout_s=getattr(settings, "voice_model_timeout_s", 120.0),
    )
    backend = PiperBackend(manager)
    try:
        model, config = backend.ensure_model()
        print(f"BCO voice preload: ready model={model.name} config={config.name}")
    except Exception as exc:
        # Build must remain deployable even if the external model host is
        # temporarily unavailable. Runtime performs the same lazy ensure.
        print(f"BCO voice preload: deferred error={type(exc).__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
