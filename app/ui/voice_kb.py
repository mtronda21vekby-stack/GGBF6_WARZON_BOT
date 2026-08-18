# -*- coding: utf-8 -*-
from __future__ import annotations


def kb_voice_panel() -> dict:
    return {
        "keyboard": [
            [{"text": "♀ CROWN // FEMALE"}, {"text": "♂ CROWN // MALE"}],
            [{"text": "🤝 Тиммейт"}, {"text": "📚 Коуч"}],
            [{"text": "🔇 Voice OFF"}, {"text": "🔊 Voice AUTO"}],
            [{"text": "🎧 Voice ON-DEMAND"}, {"text": "🔊 Озвучить ответ"}],
            [{"text": "🎙 MARIN · SOFT"}, {"text": "🎙 CORAL · WARM"}],
            [{"text": "🎙 SHIMMER · LIGHT"}, {"text": "🎙 CEDAR · TACTICAL"}],
            [{"text": "🧪 Тест голоса"}, {"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "BLACK CROWN VOICE…",
    }
