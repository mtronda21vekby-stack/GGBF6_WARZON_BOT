# -*- coding: utf-8 -*-
import re
import random
from typing import Dict, Any, List, Optional

from app.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from app.log import log
from app.state import ensure_profile, USER_MEMORY, stat_inc

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

openai_client = None
if OpenAI and OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=30, max_retries=0)
        log.info("OpenAI client: ON")
    except Exception as e:
        log.warning("OpenAI init failed: %r", e)
        openai_client = None
else:
    log.warning("OpenAI: OFF (missing key or package). Bot still works.")

_SMALLTALK_RX = re.compile(r"^\s*(привет|здаров|здравствуйте|йо|ку|qq|hello|hi|хай)\s*[!.\-–—]*\s*$", re.I)
_TILT_RX = re.compile(r"(я\s+говно|я\s+дно|не\s+прёт|не\s+идёт|вечно\s+не\s+везёт|тильт|бесит|ненавижу|заеб|сука|бля)", re.I)

def is_smalltalk(text: str) -> bool:
    return bool(_SMALLTALK_RX.match(text or ""))

def is_tilt(text: str) -> bool:
    return bool(_TILT_RX.search(text or ""))

def is_cheat_request(text: str) -> bool:
    t = (text or "").lower()
    banned = ["чит", "cheat", "hack", "обход", "античит", "exploit", "эксплойт", "аимбот", "wallhack", "вх", "спуфер"]
    return any(w in t for w in banned)

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

SYSTEM_CHAT = (
    "Ты тиммейт/коуч в чате. Пишешь по-русски.\n"
    "Не выдавай шаблон. Общайся живо.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
    "Если данных мало — задай 1 короткий уточняющий вопрос.\n"
)
SYSTEM_COACH = (
    "Ты FPS-коуч. Пишешь по-русски. Без токсичности.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
    "Если данных мало — задай 1 короткий уточняющий вопрос.\n\n"
    "Если режим COACH: дай 4 блока:\n"
    "🎯 Диагноз\n"
    "✅ Что делать (ровно 2 строки: 'Сейчас — ...' и 'Дальше — ...')\n"
    "🧪 Дрилл\n"
    "😈 Панчик/мотивация\n"
)

def _openai_chat(messages: List[Dict[str, str]], max_tokens: int) -> str:
    if not openai_client:
        return ""
    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.9,
            presence_penalty=0.7,
            frequency_penalty=0.4,
            max_completion_tokens=max_tokens,
        )
    except TypeError:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.9,
            presence_penalty=0.7,
            frequency_penalty=0.4,
            max_tokens=max_tokens,
        )
    return (resp.choices[0].message.content or "").strip()

def enforce_4_blocks(text: str, fallback_cause: str) -> str:
    t = (text or "").replace("\r", "").strip()
    needed = ["🎯", "✅", "🧪", "😈"]
    if all(x in t for x in needed):
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
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

def build_messages(chat_id: int, user_text: str, mode: str, cause: str) -> List[Dict[str, str]]:
    p = ensure_profile(chat_id)
    sys_prompt = SYSTEM_CHAT if mode == "chat" else SYSTEM_COACH
    sys_prompt += f"\nПредполагаемая причина: {CAUSE_LABEL.get(cause)}."

    msgs: List[Dict[str, str]] = [{"role": "system", "content": sys_prompt}]

    if p.get("memory") == "on":
        msgs.extend(USER_MEMORY.get(chat_id, []))

    last_ans = (p.get("last_answer") or "")[:800]
    if last_ans:
        msgs.append({"role": "system", "content": "Не повторяй прошлый ответ, меняй формулировки.\nПрошлый ответ:\n" + last_ans})

    msgs.append({"role": "user", "content": user_text})
    return msgs

def ai_off_chat(user_text: str) -> str:
    cause = classify_cause(user_text)
    st = CAUSE_LABEL.get(cause, cause)
    if is_tilt(user_text):
        return f"Слышу тильт 😈 Быстро: что ломает чаще — звук/тайминг/аим/позиция?\nПо тексту похоже на: {st}."
    if is_smalltalk(user_text):
        return "Йо 😄 Скажи: где чаще умираешь — ближка или средняя? И что бесит больше всего?"
    return f"Ок. Похоже на: {st}. Дай 1 сцену: где был, кто первый увидел, на чём умер."

def chat_reply(chat_id: int, user_text: str) -> str:
    cause = classify_cause(user_text)
    stat_inc(chat_id, cause)

    if is_cheat_request(user_text):
        return "Читы не помогу. Давай по-честному: где именно умираешь и почему думаешь?"

    if not openai_client:
        return ai_off_chat(user_text)

    msgs = build_messages(chat_id, user_text, mode="chat", cause=cause)
    out = _openai_chat(msgs, 650)
    return (out or "").strip()[:3500] or ai_off_chat(user_text)

def coach_reply(chat_id: int, user_text: str) -> str:
    cause = classify_cause(user_text)
    stat_inc(chat_id, cause)

    if is_cheat_request(user_text):
        return enforce_4_blocks("", fallback_cause=cause)

    if not openai_client:
        return enforce_4_blocks("", fallback_cause=cause)

    msgs = build_messages(chat_id, user_text, mode="coach", cause=cause)
    out = _openai_chat(msgs, 650)
    return enforce_4_blocks(out, fallback_cause=cause)
