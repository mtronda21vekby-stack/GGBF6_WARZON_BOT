# -*- coding: utf-8 -*-
from __future__ import annotations

from .service import TTSMode, VoiceArtifact, VoiceService, normalize_tts_mode
from .locale_patch import install as _install_voice_locale

_install_voice_locale()

__all__ = ["TTSMode", "VoiceArtifact", "VoiceService", "normalize_tts_mode"]
