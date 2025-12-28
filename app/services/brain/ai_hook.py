# app/services/brain/ai_hook.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _norm_role(r: str) -> str:
    r = (r or "").strip().lower()
    if r in ("assistant", "bot", "coach"):
        return "assistant"
    return "user"


def _history_to_messages(history: List[dict], limit: int = 12) -> List[dict]:
    """
    store.add(chat_id, "user"/"assistant", text) -> store.get(chat_id) -> list[dict]
    Поддерживаем разные форматы: {"role": "...", "text": "..."} или {"role": "...", "content": "..."}
    """
    msgs: List[dict] = []
    for item in (history or [])[-limit:]:
        if not isinstance(item, dict):
            continue
        role = _norm_role(str(item.get("role") or item.get("speaker") or "user"))
        content = item.get("content")
        if content is None:
            content = item.get("text")
        if content is None:
            content = item.get("message")
        if not content:
            continue
        msgs.append({"role": role, "content": str(content)})
    return msgs


def _pick_lang(profile: Dict[str, Any]) -> str:
    game = (profile.get("game") or "").strip().lower()
    # BF6 хотим EN, остальное RU
    return "en" if game == "bf6" else "ru"


def _style(profile: Dict[str, Any]) -> str:
    diff = (profile.get("difficulty") or profile.get("mode") or "Normal").strip().lower()
    if diff == "demon":
        return "DEMON"
    if diff == "pro":
        return "PRO"
    return "NORMAL"


def _world_header(profile: Dict[str, Any]) -> str:
    game = (profile.get("game") or "Warzone").strip()
    platform = (profile.get("platform") or "PC").strip()
    inp = (profile.get("input") or "Controller").strip()
    bf6_class = (profile.get("bf6_class") or "").strip()

    parts = [f"Game={game}", f"Platform={platform}", f"Input={inp}"]
    if game == "BF6" and bf6_class:
        parts.append(f"Class={bf6_class}")
    return " | ".join(parts)


def _system_prompt(profile: Dict[str, Any]) -> str:
    lang = _pick_lang(profile)
    style = _style(profile)
    world = _world_header(profile)

    if lang == "en":
        # BF6 world (EN)
        return (
            "You are an elite FPS coach and teammate. Be direct, practical, and specific.\n"
            f"Context: {world}\n\n"
            "Rules:\n"
            "- Ask at most 1 short question only if absolutely necessary.\n"
            "- Otherwise give: NOW (what to do immediately) + NEXT (drill/plan) + SETTINGS (only if relevant).\n"
            "- Use concrete callouts: crosshair placement, timing, spacing, cover usage, recoil control, peeks.\n"
            "- If BF6: tailor advice to class (Assault/Recon/Engineer/Medic) and input (KBM/Controller).\n"
            f"- Tone mode: {style} (NORMAL=calm, PRO=firm, DEMON=brutal but helpful).\n"
            "- No generic filler. No repetition.\n"
        )

    # Warzone/BO7 world (RU)
    return (
        "Ты элитный FPS-коуч и тиммейт. Говори по-русски, жёстко но по делу, без воды.\n"
        f"Контекст: {world}\n\n"
        "Правила:\n"
        "- Максимум 1 вопрос и только если реально нужно.\n"
        "- Иначе выдавай структуру: СЕЙЧАС (что делать прямо сейчас) + ДАЛЬШЕ (план/дрилл) + НАСТРОЙКИ (если уместно).\n"
        "- Конкретика: позиция, тайминги, пики, перекрёст, контроль отдачи, микро-движение, дисциплина.\n"
        "- Подстраивайся под input (KBM/Controller) и платформу.\n"
        f"- Режим тона: {style} (Normal=спокойно, Pro=жёстче, Demon=безжалостно но полезно).\n"
        "- Не повторяй одно и то же. Не отвечай шаблоном.\n"
    )


@dataclass
class AIHook:
    api_key: str
    model: str = "gpt-4.1-mini"
    timeout: int = 40

    def generate(self, *, profile: Dict[str, Any], history: List[dict], user_text: str) -> str:
        """
        Синхронный генератор: BrainEngine.reply() у тебя sync.
        """
        # lazy import, чтобы бот стартовал даже если openai не установлен (но тогда будет ошибка в generate)
        try:
            from openai import OpenAI
        except Exception:
            return (
                "🧠 ИИ: OFF\n"
                "Причина: openai package not installed\n\n"
                "Добавь в requirements.txt:\n"
                "openai>=1.40.0\n"
            )

        client = OpenAI(api_key=self.api_key)

        messages: List[dict] = [{"role": "system", "content": _system_prompt(profile)}]
        messages += _history_to_messages(history, limit=12)
        messages.append({"role": "user", "content": user_text})

        # Пытаемся chat.completions (самый совместимый способ)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=700,
            )
            out = (resp.choices[0].message.content or "").strip()
            return out if out else "⚠️ AI: empty response"
        except Exception as e:
            # максимально понятная ошибка (не ломаем бота)
            return (
                "🧠 ИИ: ERROR\n"
                f"{type(e).__name__}: {e}\n\n"
                "Проверь:\n"
                "• OPENAI_API_KEY\n"
                "• AI_ENABLED=1\n"
                "• openai>=1.40.0\n"
            )
