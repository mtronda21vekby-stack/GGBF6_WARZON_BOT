# -*- coding: utf-8 -*-
import re
from typing import Dict, List, Any, Optional

from app.kb import GAME_KB, GAMES
from app.detect import detect_game, is_smalltalk, is_tilt, is_cheat_request
from app.state import CAUSES, CAUSE_LABEL, stat_inc, ensure_profile, USER_MEMORY

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
    if score[best] == 0:
        return "position"
    return best

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
            f"Похоже, главная причина — {CAUSE_LABEL.get(fallback_cause)}.\n\n"
            "✅ Что делать\n"
            "Сейчас — сыграй от инфо: звук/радар/пинг перед выходом.\n"
            "Дальше — после первого хита меняй угол (не репикай лоб в лоб).\n\n"
            "🧪 Дрилл\n"
            "7 минут: 3 файта → после каждого 1 фраза: «почему умер».\n\n"
            "😈 Панчик/мотивация\n"
            "Не ищем магию. Ищем привычку. 😈"
        )

    def resolve_game(self, chat_id: int, user_text: str) -> str:
        p = ensure_profile(chat_id)
        forced = p.get("game", "auto")
        if forced in GAMES:
            return forced
        d = detect_game(user_text)
        return d if d in GAMES else "warzone"

    def build_messages(self, chat_id: int, user_text: str, mode: str, cause: str) -> List[Dict[str, str]]:
        p = ensure_profile(chat_id)
        persona = p.get("persona", "spicy")
        verbosity = p.get("verbosity", "normal")
        game = self.resolve_game(chat_id, user_text)

        sys_prompt = SYSTEM_CHAT if mode == "chat" else SYSTEM_COACH
        sys_prompt += f"\nТекущая игра: {GAME_KB[game]['name']}. Предполагаемая причина: {CAUSE_LABEL.get(cause)}."

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

    def lightning_off_reply(self, chat_id: int, user_text: str) -> str:
        g = self.resolve_game(chat_id, user_text)
        cause = classify_cause(user_text)
        tips = {
            "info": "⚡ Сначала инфо: звук/радар → только потом выход.",
            "timing": "⚡ Не репикай сразу: подожди 1–2 сек и выйди с другого угла.",
            "position": "⚡ Смени угол/укрытие: не стой на линии прострела.",
            "discipline": "⚡ Ресет: плейты/перезаряд → потом файт.",
            "mechanics": "⚡ Упрости: ниже сенса/короче очереди — первые 5 пуль в тело.",
        }
        base = tips.get(cause, "⚡ Сыграй проще: инфо → позиция → короткий выход.")
        if g == "warzone":
            return base + " В WZ: после первого хита — меняй угол."
        if g == "bf6":
            return base + " В BF6: после контакта — репозиция."
        if g == "bo7":
            return base + " В BO7: префайр + смена угла."
        return base

    def ai_off_chat(self, chat_id: int, user_text: str) -> str:
        cause = classify_cause(user_text)
        st = CAUSE_LABEL.get(cause, cause)
        if is_tilt(user_text):
            return (
                "Слышу тильт 😈\n"
                "Давай без самоуничтожения. Быстро: что именно чаще всего ломает — звук/тайминг/аим/позиция?\n"
                f"По тексту похоже на: {st}."
            )
        if is_smalltalk(user_text):
            return "Йо 😄 Скажи: ты сейчас в WZ/BF6/BO7 и где чаще умираешь — ближка или средняя?"
        return (
            f"Ок, понял. Похоже, причина: {st}.\n"
            "Скажи одну сцену: где был, кто первый увидел, на чём умер — и я дам точнее."
        )

    def coach_reply(self, chat_id: int, user_text: str) -> str:
        cause = classify_cause(user_text)
        stat_inc(chat_id, cause)

        if is_cheat_request(user_text):
            return (
                "🎯 Диагноз\n"
                "Читы = бан + ноль прогресса.\n\n"
                "✅ Что делать\n"
                "Сейчас — скажи, где сыпешься: инфо/тайминг/позиция/аим.\n"
                "Дальше — соберём план без магии.\n\n"
                "🧪 Дрилл\n"
                "7 минут: 3×2 минуты микро-скилл + 1 минута разбор.\n\n"
                "😈 Панчик/мотивация\n"
                "Мы качаем руки, не софт. 😈"
            )

        if not self.client:
            return self.enforce_4_blocks("", fallback_cause=cause)

        p = ensure_profile(chat_id)
        msgs = self.build_messages(chat_id, user_text, mode="coach", cause=cause)
        max_out = 180 if p.get("speed", "normal") == "lightning" else (750 if p.get("verbosity") == "talkative" else 550)
        out = self._openai_chat(msgs, max_out)
        return self.enforce_4_blocks(out, fallback_cause=cause)

    def chat_reply(self, chat_id: int, user_text: str) -> str:
        cause = classify_cause(user_text)
        stat_inc(chat_id, cause)

        p = ensure_profile(chat_id)
        if p.get("speed", "normal") == "lightning" and not self.client:
            return self.lightning_off_reply(chat_id, user_text)

        if (is_tilt(user_text) or is_smalltalk(user_text)) and not self.client:
            return self.ai_off_chat(chat_id, user_text)

        if not self.client:
            return self.ai_off_chat(chat_id, user_text)

        msgs = self.build_messages(chat_id, user_text, mode="chat", cause=cause)
        max_out = 120 if p.get("speed", "normal") == "lightning" else (420 if p.get("verbosity") == "short" else 650)
        out = self._openai_chat(msgs, max_out)
        return (out or "").strip()[:3500] or self.ai_off_chat(chat_id, user_text)
