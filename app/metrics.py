# -*- coding: utf-8 -*-
from collections import deque, Counter
from typing import Dict, Optional

MAX_HISTORY = 20

def ensure_metrics(profile: Dict) -> Dict:
    metrics = profile.setdefault("metrics", {})
    metrics.setdefault("history", deque(maxlen=MAX_HISTORY))
    metrics.setdefault("total", Counter())
    return metrics

def push_event(profile: Dict, cause: str) -> None:
    m = ensure_metrics(profile)
    m["history"].append(cause)
    m["total"][cause] += 1

def last_pattern(profile: Dict, window: int = 5) -> Optional[str]:
    m = ensure_metrics(profile)
    hist = list(m["history"])[-window:]

    if len(hist) < window:
        return None

    counter = Counter(hist)
    top, count = counter.most_common(1)[0]

    if count >= window - 1:
        return (
            "🧠 **Наблюдение (pattern):**\n"
            f"За последние {window} ситуаций проблема почти всегда одна — **{top}**.\n"
            "Это не случайность, это привычка."
        )
    return None

def summary(profile: Dict) -> str:
    m = ensure_metrics(profile)
    if not m["total"]:
        return "📊 Аналитики пока мало — нужны ситуации."

    lines = ["📊 **Общая аналитика:**"]
    for k, v in m["total"].most_common():
        lines.append(f"• {k}: {v}")
    return "\n".join(lines)
