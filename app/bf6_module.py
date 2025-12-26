# -*- coding: utf-8 -*-
"""
BF6 MODULE (Premium wrapper)
НЕ УРЕЗАЕТ старый функционал.
Добавляет:
- HUB (inline)
- Навигацию на роли/смерти
- Поддержку ReplyKeyboard (нижние кнопки) для BF6 экранов
"""

from typing import Dict, Any, Optional

from app.state import ensure_profile


# =========================
# ТВОЙ СТАРЫЙ BF6 КОД — ВСТАВЛЕН 1:1
# (ничего не вырезано, только чуть адаптированы id-карты для клавиатуры)
# =========================

def _style_prefix(style: str) -> str:
    if style == "spicy":
        return "😈"
    if style == "pro":
        return "🧠"
    return "🙂"


def _coach_block(diag: str, now: str, later: str, drill: str, punch: str) -> str:
    return (
        "🎯 Диагноз\n" + diag + "\n\n"
        "✅ Что делать\n"
        f"Сейчас — {now}\n"
        f"Дальше — {later}\n\n"
        "🧪 Дрилл\n" + drill + "\n\n"
        "😈 Панчик\n" + punch
    )


def _lightning(text: str) -> str:
    return "⚡ " + text


BF6_ROLES = {
    "assault": {
        "title": "🟠 Assault",
        "coach": _coach_block(
            diag="Ты врываешься первым и умираешь без импакта.",
            now="Входи ТОЛЬКО после контакта союзника.",
            later="Меняй угол после килла, не стой на точке.",
            drill="3 файта подряд — не открывай бой первым.",
            punch="Ты не герой. Ты молот. Бей туда, где трещина."
        ),
        "chat": (
            "🟠 Assault\n"
            "Твоя ошибка — ты лезешь первым.\n"
            "Играй вторым номером: вход ПОСЛЕ контакта, сломай позицию и уйди."
        ),
        "lightning": _lightning("Врывайся вторым. После килла — смена угла.")
    },

    "support": {
        "title": "🟢 Support",
        "coach": _coach_block(
            diag="Ты дерёшься вместо поддержки сквада.",
            now="Стой за первой линией и держи инфо.",
            later="Ресай союзников и контролируй подходы.",
            drill="5 минут — живи дольше, чем Assault.",
            punch="Живой Support = выигранная точка."
        ),
        "chat": (
            "🟢 Support\n"
            "Ты не дуэлянт.\n"
            "Твоя сила — живой сквад и контроль линии."
        ),
        "lightning": _lightning("Живи. Дай инфо. Ресай.")
    },

    "engineer": {
        "title": "🔵 Engineer",
        "coach": _coach_block(
            diag="Ты стоишь там, где нет техники врага.",
            now="Играй рядом с техникой и choke-точками.",
            later="Меняй позицию после каждого контакта.",
            drill="Каждый бой — новый угол.",
            punch="Инженер без позиции — бесполезен."
        ),
        "chat": (
            "🔵 Engineer\n"
            "Ты не про киллы.\n"
            "Ты про контроль техники и пространства."
        ),
        "lightning": _lightning("Контроль техники. Репозиция.")
    },

    "recon": {
        "title": "🟣 Recon",
        "coach": _coach_block(
            diag="Ты играешь как снайпер, а не разведчик.",
            now="Дай инфо скваду, не стреляй первым.",
            later="Контролируй фланг, а не центр.",
            drill="3 файта — не стреляй без инфо.",
            punch="Твой выстрел — маяк. Используй с умом."
        ),
        "chat": (
            "🟣 Recon\n"
            "Ты — инфо и контроль фланга.\n"
            "Если ты умер — ты стоял не там."
        ),
        "lightning": _lightning("Инфо важнее килла.")
    },
}


BF6_DEATHS = {
    "no_vision": {
        "title": "👁 Меня не вижу",
        "coach": _coach_block(
            diag="Ты смотришь вперёд, но не читаешь карту.",
            now="Проверяй миникарту каждые 5–7 секунд.",
            later="Играй от укрытий, не от открытых линий.",
            drill="5 минут — смотри карту чаще, чем стреляешь.",
            punch="В BF побеждает не аим, а инфо."
        ),
        "chat": "Ты не слепой — ты не читаешь карту.",
        "lightning": _lightning("Читай карту. Играй от укрытий.")
    },

    "backstab": {
        "title": "🔙 Убивают со спины",
        "coach": _coach_block(
            diag="Твой тыл открыт.",
            now="Стань так, чтобы был ОДИН угол угрозы.",
            later="Контролируй фланг, а не центр.",
            drill="Каждый бой — позиция с тылом.",
            punch="Тыл важнее прицела."
        ),
        "chat": "Ты стоишь на линии движения врага.",
        "lightning": _lightning("Один угол угрозы. Всегда.")
    },

    "instadeath": {
        "title": "🔁 Умираю сразу",
        "coach": _coach_block(
            diag="Ты входишь без плана.",
            now="Жди контакта союзника.",
            later="Выходи с другого угла.",
            drill="3 файта — не репикай.",
            punch="BF не любит спешку."
        ),
        "chat": "Ты пушишь без инфо.",
        "lightning": _lightning("Жди контакт. Другой угол.")
    },

    "duel": {
        "title": "⚔️ Проигрываю дуэли",
        "coach": _coach_block(
            diag="Ты дерёшься там, где не должен.",
            now="Сократи дистанцию или отойди.",
            later="Дерись только в выгодной позиции.",
            drill="5 дуэлей — только из укрытия.",
            punch="Выбирай бой, а не принимай его."
        ),
        "chat": "Ты принимаешь невыгодные дуэли.",
        "lightning": _lightning("Дерись только выгодно.")
    },
}


def get_role_text(role_id: str, style: str, mode: str) -> str:
    role = BF6_ROLES.get(role_id)
    if not role:
        return "BF6: роль не найдена."
    prefix = _style_prefix(style)
    if mode == "coach":
        return role["coach"]
    if mode == "lightning":
        return role["lightning"]
    return prefix + " " + role["chat"]


def get_death_text(reason_id: str, style: str, mode: str) -> str:
    d = BF6_DEATHS.get(reason_id)
    if not d:
        return "BF6: причина не найдена."
    prefix = _style_prefix(style)
    if mode == "coach":
        return d["coach"]
    if mode == "lightning":
        return d["lightning"]
    return prefix + " " + d["chat"]


def roles_keyboard() -> Dict[str, Any]:
    return {
        "keyboard": [
            [{"text": "🟠 Assault"}, {"text": "🟢 Support"}],
            [{"text": "🔵 Engineer"}, {"text": "🟣 Recon"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True
    }


def deaths_keyboard() -> Dict[str, Any]:
    return {
        "keyboard": [
            [{"text": "👁 Меня не вижу"}, {"text": "🔙 Со спины"}],
            [{"text": "🔁 Сразу"}, {"text": "⚔️ Дуэли"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True
    }


# =========================
# PREMIUM UI (INLINE HUB)
# =========================

def bf6_menu_hub() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎭 Роли (нижние кнопки)", "callback_data": "bf6:roles"}],
        [{"text": "💀 Почему умираю (нижние кнопки)", "callback_data": "bf6:deaths"}],
        [{"text": "⚙️ Settings (device)", "callback_data": "bf6:settings"}],  # можно привязать к твоему pro_settings если хочешь
        [{"text": "⬅️ Назад", "callback_data": "nav:settings_game"}],
    ]}


def _bf6_hub_text() -> str:
    return (
        "🎮 BF6 — премиум модуль\n\n"
        "Тут всё отдельно и не режет Warzone/BO7.\n"
        "Выбери раздел:"
    )


# =========================
# Маппинг текста кнопок -> id
# =========================

_ROLE_TEXT_TO_ID = {
    "🟠 assault": "assault",
    "🟢 support": "support",
    "🔵 engineer": "engineer",
    "🟣 recon": "recon",
}

_DEATH_TEXT_TO_ID = {
    "👁 меня не вижу": "no_vision",
    "🔙 со спины": "backstab",
    "🔁 сразу": "instadeath",
    "⚔️ дуэли": "duel",
}


# =========================
# PUBLIC ROUTER API (для handlers.py)
# =========================

def handle_callback(data: str) -> Optional[Dict[str, Any]]:
    if not data.startswith("bf6:"):
        return None

    out: Dict[str, Any] = {"set_profile": {"page": "bf6"}}

    if data == "bf6:hub":
        out.update({"text": _bf6_hub_text(), "reply_markup": bf6_menu_hub()})
        return out

    if data == "bf6:roles":
        # ВАЖНО: это ReplyKeyboard (нижние кнопки)
        out.update({
            "text": "🎭 BF6 — Роли\nВыбери роль снизу 👇",
            "reply_markup": roles_keyboard(),
            "set_profile": {"page": "bf6_roles"}
        })
        return out

    if data == "bf6:deaths":
        out.update({
            "text": "💀 BF6 — Почему умираю\nВыбери причину снизу 👇",
            "reply_markup": deaths_keyboard(),
            "set_profile": {"page": "bf6_deaths"}
        })
        return out

    if data == "bf6:settings":
        # Сейчас просто хабовая заглушка. Можно подключить твой pro_settings позже
        out.update({
            "text": "⚙️ BF6 Settings\nСкоро добавим отдельный премиум-раздел настроек, без урезаний.",
            "reply_markup": bf6_menu_hub()
        })
        return out

    out.update({"text": _bf6_hub_text(), "reply_markup": bf6_menu_hub()})
    return out


def handle_text(chat_id: int, text: str) -> Optional[Dict[str, Any]]:
    """
    Обработка НИЖНИХ кнопок (ReplyKeyboard) для BF6 ролей/смертей.
    Вызывается из handlers.py ДО AI.
    """
    p = ensure_profile(chat_id)
    page = p.get("page", "main")
    t = (text or "").strip().lower()

    # Назад из нижней клавы BF6 -> вернуть BF6 HUB (inline)
    if t in ("⬅️ назад", "назад", "back", "⬅️ back"):
        p["page"] = "bf6"
        return {"text": _bf6_hub_text(), "reply_markup": bf6_menu_hub()}

    style = p.get("persona", "spicy")
    mode = p.get("mode", "chat")
    if p.get("speed", "normal") == "lightning":
        mode = "lightning"

    if page == "bf6_roles":
        rid = _ROLE_TEXT_TO_ID.get(t)
        if rid:
            return {"text": get_role_text(rid, style, mode), "reply_markup": roles_keyboard()}
        return None

    if page == "bf6_deaths":
        did = _DEATH_TEXT_TO_ID.get(t)
        if did:
            return {"text": get_death_text(did, style, mode), "reply_markup": deaths_keyboard()}
        return None

    return None
