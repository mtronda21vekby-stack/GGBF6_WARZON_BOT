# -*- coding: utf-8 -*-
from typing import Dict, Optional
from app.metrics import push_event, last_pattern

def update_history(profile: Dict, cause: str) -> None:
    push_event(profile, cause)

def detect_pattern(profile: Dict) -> Optional[str]:
    insight = last_pattern(profile, window=5)
    if insight:
        return (
            insight +
            "\n\n😈 **Совет:** сыграй следующий матч, концентрируясь ТОЛЬКО на этом."
        )
    return None
