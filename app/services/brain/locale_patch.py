# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from app.i18n import normalize_locale
from app.services.brain.prompt_builder import PromptBuilder

_ORIGINAL_BUILD_SYSTEM = PromptBuilder.build_system


def _localized_build_system(self: PromptBuilder, *, profile: Mapping[str, Any], **kwargs) -> str:
    text = _ORIGINAL_BUILD_SYSTEM(self, profile=profile, **kwargs)
    locale = normalize_locale(profile.get("language") or profile.get("language_override") or "en")
    old = "- Write in Russian unless the user explicitly requests another language."
    if locale == "ru":
        rule = "- Respond in Russian. If the current user message is clearly English, answer in English and treat that as the active conversation language."
    else:
        rule = "- Respond in English. If the current user message is clearly Russian, answer in Russian and treat that as the active conversation language."
    return text.replace(old, rule)


def install() -> None:
    if getattr(PromptBuilder, "_bco_i18n_v38", False):
        return
    PromptBuilder.build_system = _localized_build_system  # type: ignore[assignment]
    PromptBuilder._bco_i18n_v38 = True  # type: ignore[attr-defined]
