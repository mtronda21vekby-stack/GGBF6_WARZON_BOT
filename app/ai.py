# app/ai.py
# -*- coding: utf-8 -*-

import re
from typing import Dict, List, Optional
from app import config
from app.log import log
from app.state import ensure_profile, USER_MEMORY, update_memory, USER_STATS

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

openai_client = None
if OpenAI and config.OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL, timeout=30, max_retries=0)
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


GAME_KB = {
    "warzone": {"name": "Call of Duty: Warzone"},
    "bf6": {"name": "Battlefield 6 (BF6)"},
    "bo7": {"name": "Call of Duty: Black Ops 7 (BO7)"},
}
GAMES = tuple(GAME_KB.keys())

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
    return best if score[best] else "position"

def stat_inc(chat_id: int, cause: str) -> None:
    st = USER_STATS.setdefault(chat_id, {})
    st[cause] = int(st.get(cause, 0)) + 1

SYSTEM_CHAT = (
    "Ты FPS-коуч/тиммейт. Пишешь по-русски.\n"
    "Без токсичности. Без читов/хака/обхода античита.\n"
    "Отвечай живо, но практично.\n"
    "Если данных мало — задай 1 короткий уточняющий вопрос.\n"
)

SYSTEM_COACH = (
    "Ты FPS-коуч. Пишешь по-русски. Без токсичности.\n"
    "Запрещено: читы/хаки/обход античита/эксплойты.\n"
    "Если режим COACH: дай 4 блока:\n"
    "🎯 Диагноз\n✅ Что делать (2 строки: Сейчас—..., Дальше—...)\n🧪 Дрилл\n😈 Панчик\n"
)

def resolve_game(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    forced = p.get("game", "auto")
    if forced in GAMES:
        return forced
    d = detect_game(user_text)
    return d if d in GAMES else "warzone"

def _openai_chat(messages: List[Dict[str, str]], max_tokens: int, lightning: bool) -> str:
    if not openai_client:
        return ""
    temp = 0.7 if lightning else 0.9
    try:
        resp = openai_client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            temperature=temp,
            presence_penalty=0.6,
            frequency_penalty=0.3,
            max_completion_tokens=max_tokens,
        )
    except TypeError:
        resp = openai_client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            temperature=temp,
            presence_penalty=0.6,
            frequency_penalty=0.3,
            max_tokens=max_tokens,
        )
    return (resp.choices[0].message.content or "").strip()

def chat_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    lightning = (p.get("lightning") == "on")
    cause = classify_cause(user_text)
    stat_inc(chat_id, cause)

    if is_cheat_request(user_text):
        return "С читами не помогаю. Скажи лучше: где умираешь — инфо/тайминг/позиция/аим?"

    if not openai_client:
        return "ИИ сейчас OFF. Напиши 1 сцену: где был, кто увидел, как умер — и я разберу."

    game = resolve_game(chat_id, user_text)

    msgs = [{"role": "system", "content": SYSTEM_CHAT + f"\nИгра: {GAME_KB[game]['name']}. Причина: {CAUSE_LABEL.get(cause)}."}]
    if p.get("memory") == "on":
        msgs.extend(USER_MEMORY.get(chat_id, []))
    last_ans = (p.get("last_answer") or "")[:700]
    if last_ans:
        msgs.append({"role": "system", "content": "Не повторяй прошлый ответ. Прошлый ответ:\n" + last_ans})
    msgs.append({"role": "user", "content": user_text})

    max_out = 260 if lightning else 600
    out = _openai_chat(msgs, max_out, lightning=lightning)
    return out[:3500] if out else "Напиши ещё раз коротко: где умер и почему думаешь?"

def coach_reply(chat_id: int, user_text: str) -> str:
    p = ensure_profile(chat_id)
    lightning = (p.get("lightning") == "on")
    cause = classify_cause(user_text)
    stat_inc(chat_id, cause)

    if is_cheat_request(user_text):
        return (
            "🎯 Диагноз\nЧиты = бан.\n\n"
            "✅ Что делать\nСейчас — скажи, где сыпешься.\nДальше — соберём план.\n\n"
            "🧪 Дрилл\n7 минут: 3×2 минуты + 1 минута разбор.\n\n"
            "😈 Панчик\nКачаем руки, не софт. 😈"
        )

    if not openai_client:
        return (
            "🎯 Диагноз\nИИ OFF.\n\n"
            "✅ Что делать\nСейчас — дай 1 сцену смерти.\nДальше — разберём.\n\n"
            "🧪 Дрилл\n7 минут: 3 файта → после каждого 1 фраза «почему умер».\n\n"
            "😈 Панчик\nСтабильность = дисциплина. 😈"
        )

    game = resolve_game(chat_id, user_text)

    msgs = [{"role": "system", "content": SYSTEM_COACH + f"\nИгра: {GAME_KB[game]['name']}. Причина: {CAUSE_LABEL.get(cause)}."}]
    if p.get("memory") == "on":
        msgs.extend(USER_MEMORY.get(chat_id, []))
    msgs.append({"role": "user", "content": user_text})

    max_out = 420 if lightning else 750
    out = _openai_chat(msgs, max_out, lightning=lightning)
    return out[:3500] if out else "Опиши 1 сцену: где был, кто увидел, как умер."
