# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services.brain.knowledge_context import KnowledgeContext
from app.services.brain.response_policy import ResponsePolicy


def enforce_response_limit(text: str, policy: ResponsePolicy) -> str:
    text = (text or "").strip()
    if not text or len(text) <= policy.max_chars:
        return text
    cut = text[: policy.max_chars - 80].rstrip()
    for sep in ("\n\n", "\n", ". "):
        pos = cut.rfind(sep)
        if pos > int(policy.max_chars * 0.65):
            cut = cut[: pos + (1 if sep == ". " else 0)].rstrip()
            break
    return cut + "\n\n…"


def currentness_blocked_response(knowledge: KnowledgeContext) -> str:
    dated = ""
    if knowledge.last_updated:
        dated = f"\nПоследняя локальная база датирована: {knowledge.last_updated}."
    source = f"\nИсточник локальной базы: {knowledge.source}." if knowledge.source else ""
    return (
        "📡 Актуальность не подтверждена.\n"
        "Я не буду выдавать старые данные или память модели за текущую мету/последний патч."
        f"{dated}{source}\n\n"
        "Могу разобрать тактику или настройки по проверенной локальной базе, "
        "а live-мету включим отдельным источником данных."
    )
