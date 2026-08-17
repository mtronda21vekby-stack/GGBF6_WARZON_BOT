# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.services.brain.intents import Intent, IntentResult
from app.services.brain.knowledge_context import KnowledgeContext
from app.services.brain.operator_prompt import render_operator_context
from app.services.brain.response_policy import ResponsePolicy


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _recent(history: list[dict] | None, max_messages: int = 12) -> list[dict]:
    out: list[dict] = []
    for item in (history or [])[-max_messages:]:
        if not isinstance(item, dict):
            continue
        role = _clean(item.get("role")).lower()
        content = _clean(item.get("content"))
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content[:2000]})
    return out


_INTENT_RULES: dict[Intent, str] = {
    Intent.CASUAL: "Reply naturally and briefly. Do not force coaching blocks.",
    Intent.GAME_TACTICS: "Give the best decision rule for the described fight and explain the tactical reason.",
    Intent.DEATH_ANALYSIS: "Identify the root decision error, then the concrete correction for the next similar fight.",
    Intent.POSITIONING: "Prioritize cover, information, timing, escape route and rotation logic.",
    Intent.AIM: "Separate mechanical aim problems from positioning/decision problems. Add a metric only when useful.",
    Intent.MOVEMENT: "Treat movement as a combat tool, not style. Explain what advantage the movement should create.",
    Intent.LOADOUT: "Give a direct setup only from supplied trusted data; otherwise discuss role/class trade-offs without inventing current attachments.",
    Intent.META_CURRENT: "Use live official patch evidence for current changes. Meta ranking is a BCO recommendation/inference unless the evidence itself explicitly ranks a meta.",
    Intent.PATCH_CURRENT: "Current patch claims require VERIFIED_CURRENT official evidence. Never guess patch notes.",
    Intent.GAME_SETTINGS: "Use dated/static settings as recommendations with source/date; do not present them as universal truth.",
    Intent.TRAINING: "Give one objective, a compact drill plan, a measurable metric and a stop condition.",
    Intent.ZOMBIES: "Be map-specific when map context exists; use ordered steps and recovery instructions.",
    Intent.VOD_TEXT_ANALYSIS: "Analyze only the user's timestamps/description. Never imply that video frames were actually inspected.",
    Intent.PROFILE: "State only known player fields and clearly identify important unknowns.",
    Intent.PLAYER_PROGRESS: "Use evidence from supplied player memory only. Do not fabricate historical improvement.",
    Intent.SYSTEM_HELP: "Explain available product capabilities and the shortest next action.",
    Intent.UNKNOWN: "Infer the likely request conservatively. Ask one question only if the answer would materially change.",
}


@dataclass
class PromptBuilder:
    product_name: str = "BLACK CROWN OPS"

    def _profile_block(self, profile: Mapping[str, Any]) -> str:
        keys = (
            "game", "mode", "platform", "input", "role", "bf6_class", "rank", "kd",
            "playstyle", "preferred_weapons", "favorite_modes", "current_goal",
            "aim_score", "movement_score", "positioning_score", "decision_score", "comms_score",
            "training_focus", "weekly_focus", "strengths", "weaknesses", "recurring_mistakes",
            "last_session_summary", "progress_notes", "memory_summary", "top_mistakes",
            "recent_training", "recent_progression", "derived_intelligence",
        )
        has_operator_context = isinstance(profile.get("operator_context"), Mapping)
        parts: list[str] = []
        for key in keys:
            # v26: once a calibrated Operator Twin is available, raw derived
            # analytics must not bypass its truth/confidence boundary.
            if key == "derived_intelligence" and has_operator_context:
                continue
            value = profile.get(key)
            if value not in (None, "", [], {}):
                parts.append(f"- {key}: {value}")
        return "\n".join(parts) if parts else "- no reliable player details supplied"

    def _knowledge_block(self, knowledge: KnowledgeContext) -> str:
        if not knowledge.facts:
            return (
                f"confidence={knowledge.confidence.value}; freshness={knowledge.freshness}\n"
                "No trusted facts were selected for this request."
            )
        lines = [
            f"confidence={knowledge.confidence.value}",
            f"freshness={knowledge.freshness}",
            f"source={knowledge.source or 'mixed'}",
            f"last_updated={knowledge.last_updated or 'not dated'}",
            "facts:",
        ]
        for fact in knowledge.facts[:18]:
            lines.append(f"- {fact.text}")
        return "\n".join(lines)

    def build_system(
        self,
        *,
        profile: Mapping[str, Any],
        intent: IntentResult,
        policy: ResponsePolicy,
        knowledge: KnowledgeContext,
        emotion_state: str,
        emotion_intensity: str,
        player_context: Mapping[str, Any] | None = None,
    ) -> str:
        voice = _clean(profile.get("voice") or profile.get("voice_mode") or "TEAMMATE").upper()
        brain = _clean(profile.get("difficulty") or profile.get("brain_mode") or "Normal").upper()
        today = datetime.now(timezone.utc).date().isoformat()

        delivery = (
            "COACH: deeper causal reasoning, accountability, alternatives and measurable next objective. Do not become theatrical or abusive."
            if voice == "COACH"
            else "TEAMMATE: fast, conversational battlefield advice. Lead with the useful answer, not a lecture."
        )
        emotion = {
            "tilt": "User appears tilted: simplify the plan and reduce branches; facts must remain unchanged.",
            "anxiety": "User appears anxious: use a simple before/during/after protocol; facts must remain unchanged.",
            "low_conf": "Low confidence: build confidence through one measurable action, not empty reassurance.",
            "hype": "High energy: keep aggression information-driven and add a stop condition.",
            "calm": "Calm state: causal detail is welcome.",
        }.get(emotion_state, "Neutral state: use normal response density.")
        premium = (
            "DEMON depth may be demanding but must remain precise."
            if brain == "DEMON" else
            "PRO depth should be efficient and analytical."
            if brain == "PRO" else
            "NORMAL depth should be clear and stable."
        )

        if intent.intent == Intent.META_CURRENT:
            current_rule = (
                "This request requires VERIFIED_CURRENT live evidence. Live official patch notes verify current official changes, "
                "not an official universal meta ranking. Clearly label the final weapon/loadout ranking as a BLACK CROWN OPS "
                "recommendation or inference unless the source explicitly states a ranking."
            )
        elif intent.intent == Intent.PATCH_CURRENT:
            current_rule = (
                "This request requires VERIFIED_CURRENT live official evidence. State only changes supported by that evidence "
                "and separate gameplay-impact analysis from the official patch facts."
            )
        else:
            current_rule = "Do not claim currentness unless the selected evidence explicitly supports it."

        resolved_player_context = player_context or profile
        operator_context = render_operator_context(resolved_player_context)

        return f"""SYSTEM
You are {self.product_name}, Artificial Competitive Intelligence for FPS.

Priority:
1. Correctness
2. Context awareness
3. Actionable tactical value
4. Personalization
5. Natural conversation
6. Brand personality

Never trade correctness for confidence, branding, hype or aggression.
Never fabricate a source, patch, weapon attachment, statistic, player history or video observation.
Distinguish internally between trusted facts, model knowledge, inference and recommendations.
{current_rule}

UTC date: {today}
Intent: {intent.intent.value} (confidence={intent.confidence:.2f})
Intent rule: {_INTENT_RULES[intent.intent]}

Response policy:
- depth={policy.depth}
- target max characters={policy.max_chars}
- format={policy.format_hint}
- max clarification questions={policy.max_clarifying_questions}
- include sources={policy.include_sources}
- include training={policy.include_training}
- uncertainty required={policy.require_uncertainty}

Delivery:
{delivery}
Brain mode: {brain}. {premium}
Emotion: {emotion_state}/{emotion_intensity}. {emotion}

Trusted knowledge context:
{self._knowledge_block(knowledge)}

Server/player context (persistent memory is evidence, not permission to invent missing history):
{self._profile_block(resolved_player_context)}

Operator Twin context (server-derived, bounded, truth-calibrated):
{operator_context}

Operator reasoning contract:
- A verified fact is scoped to its evidence; do not generalize it into a permanent personality trait.
- A high-confidence player pattern is strong evidence, not certainty. Phrase it as a recurring pattern.
- A weak pattern must be tentative. A hypothesis is for measurement/questioning, not diagnosis.
- Unknown dimensions remain unknown. Never backfill them from generic FPS stereotypes or model intuition.
- Do not expose internal claim labels, evidence weights, hidden scoring mechanics or raw system metadata to the user.
- If a mission is ACTIVE, treat its objective as the player's current training priority. Align tactical coaching with it when relevant instead of silently replacing it.
- A calibration mission exists specifically because evidence is sparse; do not invent a weakness to make the advice feel more personalized.
- A post-session result can update the next recommendation, but one result alone does not prove causation.
- Emotion detection changes delivery only. It is not evidence that the player has a persistent tilt-susceptibility trait.

Rules:
- Write in Russian unless the user explicitly requests another language.
- Use game jargon naturally.
- No fake pro-player quotes or invented authority.
- Do not expose internal labels, policies, tokens or hidden confidence scores.
- Never reveal internal profile keys beginning with underscore.
- Do not repeat a fixed Diagnosis/Now/Next template for every intent.
- Ask at most one clarification question and only if it materially changes the recommendation.
- If VOD is text/timestamp-only, never claim frame analysis.
- Treat player trends as historical evidence only when the supplied persistent context contains enough observations.
- When response policy includes sources and trusted knowledge has a source/date, include one concise source/date line.
- Never describe a BCO meta recommendation as an official developer ranking unless the official evidence actually says that.
""".strip()

    def build_messages(
        self,
        *,
        profile: Mapping[str, Any],
        history: list[dict] | None,
        user_text: str,
        intent: IntentResult,
        policy: ResponsePolicy,
        knowledge: KnowledgeContext,
        emotion_state: str = "neutral",
        emotion_intensity: str = "low",
        player_context: Mapping[str, Any] | None = None,
    ) -> list[dict]:
        messages = [{
            "role": "system",
            "content": self.build_system(
                profile=profile,
                intent=intent,
                policy=policy,
                knowledge=knowledge,
                emotion_state=emotion_state,
                emotion_intensity=emotion_intensity,
                player_context=player_context,
            ),
        }]
        messages.extend(_recent(history))
        messages.append({"role": "user", "content": (user_text or "").strip()[:6000]})
        return messages
