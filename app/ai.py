# app/ai.py
# -*- coding: utf-8 -*-

import os
import re
import random
from typing import List, Dict, Optional

from app.state import ensure_profile, USER_MEMORY, update_memory

# OpenAI optional
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ===== OpenAI init (optional) =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

_client = None
if OpenAI and OPENAI_API_KEY:
    try:
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=30, max_retries=0)
    except Exception:
        _client = None


def ai_is_on() -> bool:
    return _client is not None


# ===== small detectors =====
_SMALLTALK_RX = re.compile(r"^\s*(привет|здаров|здравствуйте|йо|ку|qq|hello|hi|хай)\s*[!.\-–—]*\s*$", re.I)
_TILT_RX = re.compile(r"(я\s+говно|я\s+дно|не\s+прёт|не\s+идёт|тильт|бесит|сука|бля|заеб)", re.I)

def is_smalltalk(text: str) -> bool:
    return bool(_SMALLTALK_RX.match(text or ""))

def is_tilt(text: str) -> bool:
    return bool(_TILT_RX.search(text or ""))

def is_cheat_request(text: str) -> bool:
    t = (text or "").lower()
    banned = ["чит", "cheat", "hack", "обход", "античит", "exploit", "аимбот", "wallhack", "вх", "спуфер"]
    return any(w in t for w in banned)

def detect_game(text: str) -> Optional[str]:
    t = (text or "").lower()
    if any(x in t for x in ["bf6", "battlefield", "батлфилд", "конквест", "захват"]):
        return "bf6"
    if any(x in t for x in ["bo7", "black ops", "блэк опс", "hardpoint", "хардпоинт", "zombies", "зомби"]):
        return "bo7"
    if any(x in t for x in ["warzone", "wz", "варзон", "verdansk", "rebirth", "gulag", "бр"]):
        return "warzone"
    return None


CAUSES = ("info", "timing", "position", "discipline", "mechanics")
CAUSE_LABEL = {
    "info": "Инфо (звук/радар/пинги)",
    "timing": "Тайминг (когда пикнул/вышел)",
    "position": "Позиция (угол/высота/линия обзора)",
    "discipline": "Дисциплина (жадность/ресурсы/ресет)",
    "mechanics": "Механика (аим/отдача/сенса)",
}

def classify_cause(text: str) -> str:
    t = (text or "").lower()
    score = {c: 0 for c in CAUSES}
    for k in ["не слыш", "звук", "шаг", "радар", "пинг", "инфо"]:
        if k in t: score["info"] += 2
    for k in ["тайм", "поздно", "рано", "репик", "пикнул", "вышел"]:
        if k in t: score["timing"] += 2
    for k in ["пози", "угол", "высот", "открыт", "прострел", "линия", "укрыт"]:
        if k in t: score["position"] += 2
    for k in ["жадн", "ресурс", "плейт", "перезар", "в соло", "погнал"]:
        if k in t: score["discipline"] += 2
    for k in ["аим", "отдач", "сенс", "фов", "дрейф", "не попал", "мимо"]:
        if k in t: score["mechanics"] += 2
    best = max(score.items(), key=lambda kv: kv[1])[0]
    return best if score[best] > 0 else "position"


def looks_like_scene(text: str) -> bool:
    t = (text or "").lower()
    keys = ["умер", "снесли", "убили", "проиграл", "пикнул", "вышел", "зауглили", "в спину", "1v", "2v", "3v"]
    return any(k in t for k in keys) or ("|" in t and len(t) > 15)


# ===== anti-repeat =====
def _tokenize(s: str) -> List[str]:
    return re.findall(r"[а-яa-z0-9]+", (s or "").lower())

def _jaccard(a: str, b: str) -> float:
    sa = set(_tokenize(a))
    sb = set(_tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))

def _is_too_similar(a: str, b: str) -> bool:
    return _jaccard(a, b) >= 0.55


# ===== “живые” шаблоны на случай AI OFF =====
def _offline_chat(chat_id: int, text: str) -> str:
    cause = classify_cause(text)
    p = ensure_profile(chat_id)
    lightning = (p.get("lightning", "off") == "on")

    if is_cheat_request(text):
        return "Читы = бан. Давай без магии 😈 Скажи: где чаще ломает — инфо/тайминг/позиция/аим?"

    if lightning:
        return (
            f"⚡ Сейчас — упрись в {CAUSE_LABEL[cause].lower()} (один конкретный фикс на 3 файта).\n"
            "⚡ Дальше — после первого контакта всегда меняй угол (не репикай лоб).\n"
            "В каком режиме играешь и где чаще умираешь: ближка или средняя?"
        )

    if is_smalltalk(text):
        return "Йо 😄 Ок, по какой игре вопрос — WZ/BF6/BO7? И что болит: позиция, аим или тайминг?"

    if is_tilt(text):
        return "Слышу тильт 😈 Давай быстро: 1) где умер 2) кто видел первым 3) почему думаешь что так вышло?"

    variants = [
        f"Ок. По ощущениям тут {CAUSE_LABEL[cause]}. Дай одну сцену: где был/что видел/как пикнул — и я соберу план.",
        f"Понял. Скорее всего сыпет {CAUSE_LABEL[cause].lower()}. Скажи: ты чаще умираешь от спины или лоб-в-лоб?",
        f"Схватил мысль. Вероятная причина — {CAUSE_LABEL[cause].lower()}. Какой у тебя стиль: агро или аккуратно от инфо?",
    ]
    return random.choice(variants)


SYSTEM_CHAT = (
    "Ты тиммейт/коуч. Русский язык. Без токсичности.\n"
    "Никаких читов/хакинга.\n"
    "Не будь шаблонным: меняй структуру и формулировки.\n"
    "Задавай максимум 1 короткий вопрос в конце (если нужен).\n"
)

SYSTEM_COACH = (
    "Ты FPS-коуч. Русский язык. Без токсичности.\n"
    "Никаких читов/хакинга.\n"
    "Формат COACH (коротко, мощно):\n"
    "1) 🎯 Диагноз (1–2 строки)\n"
    "2) ✅ Сейчас / Дальше (2 строки)\n"
    "3) 🧪 Дрилл (1 мини-дрилл)\n"
    "4) ❓ 1 вопрос (один!)\n"
)

PERSONA_HINT = {
    "spicy": "Стиль: дерзко и смешно, но без унижений. Сленг уместен.",
    "chill": "Стиль: спокойно, дружелюбно, мягко.",
    "pro": "Стиль: строго по делу, структурно.",
}
VERBOSITY_HINT = {
    "short": "Длина: очень коротко.",
    "normal": "Длина: нормально, без воды.",
    "talkative": "Длина: подробнее, но без занудства.",
}

STRUCTURES_CHAT = [
    "Сделай ответ как разговор: 2-4 предложения + 1 вопрос.",
    "Сделай ответ как 'план на 2 шага': Сейчас/Дальше + 1 вопрос.",
    "Сделай ответ через метафору/шутку (аккуратно) + 1 совет + 1 вопрос.",
    "Сделай ответ как 'разбор ошибки': что произошло → почему → что поменять, и 1 вопрос.",
]

STRUCTURES_COACH = [
    "Дай максимально практичный COACH, без списков больше 4 пунктов.",
    "COACH очень коротко, но жёстко по делу.",
    "COACH в стиле 'диагноз врача': причина → лечение → контроль.",
]

def _openai(messages: List[Dict[str, str]], max_tokens: int) -> str:
    if not _client:
        return ""
    try:
        r = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.9,
            presence_penalty=0.7,
            frequency_penalty=0.4,
            max_completion_tokens=max_tokens,
        )
    except TypeError:
        r = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.9,
            presence_penalty=0.7,
            frequency_penalty=0.4,
            max_tokens=max_tokens,
        )
    return (r.choices[0].message.content or "").strip()


def generate_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    text = (user_text or "").strip()
    if not text:
        return ""

    # lightning = ультра-коротко всегда
    lightning = (p.get("lightning", "off") == "on")

    # AUTO выбор режима
    mode = p.get("mode", "chat")
    if mode == "auto":
        mode = "coach" if looks_like_scene(text) else "chat"

    if not _client:
        return _offline_chat(chat_id, text)

    cause = classify_cause(text)
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")

    sys = SYSTEM_COACH if mode == "coach" else SYSTEM_CHAT

    # ⚡ Молния заставляет формат “Сейчас/Дальше” даже в CHAT
    if lightning:
        sys += "\nЕсли включена ⚡ Молния: ответ строго в 2 строки (Сейчас/Дальше) + 1 вопрос."
    sys += f"\nПредполагаемая причина: {CAUSE_LABEL[cause]}."

    msgs: List[Dict[str, str]] = [
        {"role": "system", "content": sys},
        {"role": "system", "content": PERSONA_HINT.get(persona, PERSONA_HINT["spicy"])},
        {"role": "system", "content": VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"])},
    ]

    # вариативная структура
    if mode == "coach":
        msgs.append({"role": "system", "content": random.choice(STRUCTURES_COACH)})
    else:
        msgs.append({"role": "system", "content": random.choice(STRUCTURES_CHAT)})

    # память
    if p.get("memory", "on") == "on":
        msgs.extend(USER_MEMORY.get(chat_id, [])[-16:])

    last_ans = (p.get("last_answer") or "")[:900]
    if last_ans:
        msgs.append({"role": "system", "content": "Не повторяй прошлый ответ и не копируй его фразы.\nПрошлый ответ:\n" + last_ans})

    msgs.append({"role": "user", "content": text})

    max_out = 420 if verbosity == "short" else (650 if verbosity == "normal" else 850)
    out = _openai(msgs, max_out)

    # анти-повтор: если слишком похоже — пробуем ещё раз другой структурой
    if last_ans and _is_too_similar(out, last_ans):
        msgs.append({"role": "system", "content": "Ответ слишком похож. Перефразируй полностью и измени структуру."})
        msgs.append({"role": "system", "content": random.choice(STRUCTURES_CHAT if mode != "coach" else STRUCTURES_COACH)})
        out2 = _openai(msgs, max_out)
        if out2:
            out = out2

    return (out or "").strip()
