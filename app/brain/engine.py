# -*- coding: utf-8 -*-
import re
from typing import Dict, Any, List

from app.state import ensure_profile, USER_MEMORY, stat_inc, CAUSES, CAUSE_LABEL
from app.brain.rules import is_smalltalk, is_tilt, is_cheat_request
from app.games.registry import resolve_game, game_title

# OpenAI optional
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


PERSONA_HINT = {
    "spicy": "Стиль: дерзко и смешно, но без унижений. Сленг уместен.",
    "chill": "Стиль: спокойный, дружелюбный, мягко и по делу.",
    "pro": "Стиль: строго по делу, минимум шуток, чёткая структура.",
}
VERBOSITY_HINT = {
    "short": "Длина: коротко, без воды.",
    "normal": "Длина: нормально, плотная польза.",
    "talkative": "Длина: подробнее, но без занудства.",
}

SYSTEM_COACH = (
    "Ты FPS-коуч. Пишешь по-русски. Без токсичности.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
    "Отвечай живо, но практично.\n"
    "Если данных мало — задай 1 короткий уточняющий вопрос.\n\n"
    "Если режим COACH: дай 4 блока:\n"
    "🎯 Диагноз\n"
    "✅ Что делать (ровно 2 строки: 'Сейчас — ...' и 'Дальше — ...')\n"
    "🧪 Дрилл\n"
    "😈 Панчик/мотивация\n"
)

SYSTEM_CHAT = (
    "Ты тиммейт/коуч в чате. Пишешь по-русски.\n"
    "Твоя задача — общаться как живой: задавай вопросы, уточняй, подстраивайся.\n"
    "Не выдавай шаблон. Можно коротко. Можно пошутить.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
)

SYSTEM_LIGHTNING = (
    "РЕЖИМ ⚡ МОЛНИЯ:\n"
    "• Ответ максимум 1–3 строки.\n"
    "• Без вопросов.\n"
    "• Только конкретное действие прямо сейчас.\n"
    "• Без воды и длинных списков.\n"
)

def classify_cause(text: str) -> str:
    t = (text or "").lower()
    score = {c: 0 for c in CAUSES}

    for k in ["не слыш", "звук", "шаг", "радар", "пинг", "инфо", "увидел поздно"]:
        if k in t: score["info"] += 2
    for k in ["тайм", "поздно", "рано", "репик", "пикнул", "вышел", "задержал"]:
        if k in t: score["timing"] += 2
    for k in ["пози", "угол", "высот", "открыт", "прострел", "линия", "укрыт"]:
        if k in t: score["position"] += 2
    for k in ["жадн", "ресурс", "плейт", "пласти", "хил", "перезар", "вдвоём", "в соло", "погнал"]:
        if k in t: score["discipline"] += 2
    for k in ["аим", "отдач", "сенс", "фов", "перел", "дрейф", "не попал", "мимо"]:
        if k in t: score["mechanics"] += 2

    best = max(score.items(), key=lambda kv: kv[1])[0]
    return best if score[best] > 0 else "position"


class AIEngine:
    def __init__(self, openai_key: str, base_url: str, model: str, log):
        self.log = log
        self.model = model
        self.client = None

        if OpenAI and openai_key:
            try:
                self.client = OpenAI(api_key=openai_key, base_url=base_url, timeout=30, max_retries=0)
                self.log.info("OpenAI client: ON")
            except Exception as e:
                self.log.warning("OpenAI init failed: %r", e)
                self.client = None
        else:
            self.log.warning("OpenAI: OFF (missing key or package). Bot still works.")

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def _openai_chat(self, messages: List[Dict[str, str]], max_tokens: int) -> str:
        if not self.client:
            return ""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.9,
                presence_penalty=0.7,
                frequency_penalty=0.4,
                max_completion_tokens=max_tokens,
            )
        except TypeError:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.9,
                presence_penalty=0.7,
                frequency_penalty=0.4,
                max_tokens=max_tokens,
            )
        return (resp.choices[0].message.content or "").strip()

    def enforce_4_blocks(self, text: str, fallback_cause: str) -> str:
        t = (text or "").replace("\r", "").strip()
        needed = ["🎯", "✅", "🧪", "😈"]
        if all(x in t for x in needed):
            t = re.sub(r"\n{3,}", "\n\n", t).strip()
            t = re.sub(r"(?im)^\s*🎯.*$", "🎯 Диагноз", t)
            t = re.sub(r"(?im)^\s*✅.*$", "✅ Что делать", t)
            t = re.sub(r"(?im)^\s*🧪.*$", "🧪 Дрилл", t)
            t = re.sub(r"(?im)^\s*😈.*$", "😈 Панчик/мотивация", t)
            return t

        return (
            "🎯 Диагноз\n"
            f"Похоже, главная причина — {CAUSE_LABEL.get(fallback_cause, fallback_cause)}.\n\n"
            "✅ Что делать\n"
            "Сейчас — сыграй от инфо: звук/радар/пинг перед выходом.\n"
            "Дальше — после первого хита меняй угол (не репикай лоб в лоб).\n\n"
            "🧪 Дрилл\n"
            "7 минут: 3 файта → после каждого 1 фраза: «почему умер».\n\n"
            "😈 Панчик/мотивация\n"
            "Не ищем магию. Ищем привычку. 😈"
        )

    def build_messages(self, chat_id: int, user_text: str, mode: str, cause: str, game: str) -> List[Dict[str, str]]:
        p = ensure_profile(chat_id)
        persona = p.get("persona", "spicy")
        verbosity = p.get("verbosity", "normal")

        sys_prompt = SYSTEM_CHAT if mode == "chat" else SYSTEM_COACH
        sys_prompt += f"\nТекущая игра: {game_title(game)}. Предполагаемая причина: {CAUSE_LABEL.get(cause, cause)}."

        msgs: List[Dict[str, str]] = [
            {"role": "system", "content": sys_prompt},
            {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
            {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
        ]

        if p.get("speed", "normal") == "lightning":
            msgs.append({"role": "system", "content": SYSTEM_LIGHTNING})

        if p.get("memory") == "on":
            msgs.extend(USER_MEMORY.get(chat_id, []))

        last_ans = (p.get("last_answer") or "")[:800]
        if last_ans:
            msgs.append({"role": "system", "content": "Не повторяй прошлый ответ, меняй формулировки.\nПрошлый ответ:\n" + last_ans})

        msgs.append({"role": "user", "content": user_text})
        return msgs

    def ai_off_chat(self, user_text: str) -> str:
        cause = classify_cause(user_text)
        st = CAUSE_LABEL.get(cause, cause)

        if is_tilt(user_text):
            return (
                "Слышу тильт 😈\n"
                "Давай без самоуничтожения. Быстро: что чаще ломает — звук/тайминг/аим/позиция?\n"
                f"По тексту похоже на: {st}."
            )
        if is_smalltalk(user_text):
            return "Йо 😄 Скажи: ты сейчас в WZ/BF6/BO7 и где чаще умираешь — ближка или средняя?"
        return (
            f"Ок. Похоже, причина: {st}.\n"
            "Скинь 1 сцену: где был, кто первый увидел, на чём умер — и я дам точнее."
        )

    def reply(self, chat_id: int, user_text: str) -> str:
        p = ensure_profile(chat_id)
        mode = p.get("mode", "chat")

        game = resolve_game(chat_id, user_text)
        cause = classify_cause(user_text)
        stat_inc(chat_id, cause)

        if is_cheat_request(user_text):
            return (
                "🚫 Читы/хаки/обход античита — не помогу.\n"
                "Если хочешь прогресс: скажи где умираешь (инфо/тайминг/позиция/аим) — соберём план."
            )

        if not self.client:
            # оффлайн поведение
            if mode == "coach":
                return self.enforce_4_blocks("", fallback_cause=cause)
            return self.ai_off_chat(user_text)

        msgs = self.build_messages(chat_id, user_text, mode=mode, cause=cause, game=game)
        if mode == "coach":
            max_out = 180 if p.get("speed", "normal") == "lightning" else (750 if p.get("verbosity") == "talkative" else 550)
            out = self._openai_chat(msgs, max_out)
            return self.enforce_4_blocks(out, fallback_cause=cause)

        max_out = 120 if p.get("speed", "normal") == "lightning" else (420 if p.get("verbosity") == "short" else 650)
        out = self._openai_chat(msgs, max_out)
        return (out or "").strip()[:3500] or self.ai_off_chat(user_text)