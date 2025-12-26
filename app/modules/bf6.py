# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
from app.state import ensure_profile
from app.pro_settings import get_tier_text

def _kb(rows):
    return {"inline_keyboard": rows}

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

class BF6Module:
    key = "bf6"

    def hub(self, chat_id: int) -> Dict[str, Any]:
        p = ensure_profile(chat_id)
        return {
            "text": "🟧 BF6 Hub\nВыбирай 👇",
            "reply_markup": _kb([
                [{"text": "🎭 Роли", "callback_data": "mod:bf6:roles"}],
                [{"text": "💀 Почему умираю", "callback_data": "mod:bf6:deaths"}],
                [{"text": "⚙️ Premium-настройки (EN)", "callback_data": "mod:bf6:settings"}],
                [{"text": "⬅️ Назад в меню", "callback_data": "nav:main"}],
            ])
        }

    def _roles_menu(self) -> Dict[str, Any]:
        return _kb([
            [{"text": "🟠 Assault", "callback_data": "mod:bf6:role:assault"},
             {"text": "🟢 Support", "callback_data": "mod:bf6:role:support"}],
            [{"text": "🔵 Engineer", "callback_data": "mod:bf6:role:engineer"},
             {"text": "🟣 Recon", "callback_data": "mod:bf6:role:recon"}],
            [{"text": "⬅️ Назад", "callback_data": "mod:bf6:hub"}],
        ])

    def _deaths_menu(self) -> Dict[str, Any]:
        return _kb([
            [{"text": "👁 Меня не вижу", "callback_data": "mod:bf6:death:no_vision"},
             {"text": "🔙 Со спины", "callback_data": "mod:bf6:death:backstab"}],
            [{"text": "🔁 Сразу", "callback_data": "mod:bf6:death:instadeath"},
             {"text": "⚔️ Дуэли", "callback_data": "mod:bf6:death:duel"}],
            [{"text": "⬅️ Назад", "callback_data": "mod:bf6:hub"}],
        ])

    def _settings_menu(self, chat_id: int) -> Dict[str, Any]:
        p = ensure_profile(chat_id)
        dev = p.get("bf6_device", "pad")
        tier = p.get("bf6_tier", "normal")
        return {
            "text": f"🟧 BF6 Premium (EN)\nDevice: {dev} | Tier: {tier}\n\nChoose 👇",
            "reply_markup": _kb([
                [{"text": "🎮 Controller", "callback_data": "mod:bf6:setdev:pad"},
                 {"text": "🖥 MnK", "callback_data": "mod:bf6:setdev:mnk"}],
                [{"text": "🙂 Normal", "callback_data": "mod:bf6:settier:normal"},
                 {"text": "😈 Demon", "callback_data": "mod:bf6:settier:demon"}],
                [{"text": "🎯 Pro", "callback_data": "mod:bf6:settier:pro"}],
                [{"text": "📌 Show preset", "callback_data": "mod:bf6:show"}],
                [{"text": "⬅️ Back", "callback_data": "mod:bf6:hub"}],
            ])
        }

    def _format_block(self, block: Dict[str, Any], style: str, mode: str) -> str:
        prefix = _style_prefix(style)
        if mode == "coach":
            return block["coach"]
        if mode == "lightning":
            return block["lightning"]
        return prefix + " " + block["chat"]

    def handle_callback(self, chat_id: int, data: str) -> Optional[Dict[str, Any]]:
        p = ensure_profile(chat_id)
        style = p.get("persona", "spicy")
        mode = p.get("mode", "chat")
        speed = p.get("speed", "normal")
        if speed == "lightning":
            mode = "lightning"

        if data == "mod:bf6:hub":
            p["page"] = "bf6"
            return self.hub(chat_id)

        if data == "mod:bf6:roles":
            p["page"] = "bf6"
            return {"text": "🎭 BF6 — Роли:", "reply_markup": self._roles_menu()}

        if data.startswith("mod:bf6:role:"):
            role_id = data.split(":")[-1]
            role = BF6_ROLES.get(role_id)
            if not role:
                return {"text": "BF6: роль не найдена.", "reply_markup": self._roles_menu()}
            return {"text": self._format_block(role, style, mode), "reply_markup": self._roles_menu()}

        if data == "mod:bf6:deaths":
            p["page"] = "bf6"
            return {"text": "💀 BF6 — Почему умираю:", "reply_markup": self._deaths_menu()}

        if data.startswith("mod:bf6:death:"):
            did = data.split(":")[-1]
            d = BF6_DEATHS.get(did)
            if not d:
                return {"text": "BF6: причина не найдена.", "reply_markup": self._deaths_menu()}
            return {"text": self._format_block(d, style, mode), "reply_markup": self._deaths_menu()}

        if data == "mod:bf6:settings":
            p["page"] = "bf6"
            return self._settings_menu(chat_id)

        if data.startswith("mod:bf6:setdev:"):
            dev = data.split(":")[-1]
            if dev in ("pad", "mnk"):
                p["bf6_device"] = dev
            return self._settings_menu(chat_id)

        if data.startswith("mod:bf6:settier:"):
            tier = data.split(":")[-1]
            if tier in ("normal", "demon", "pro"):
                p["bf6_tier"] = tier
            return self._settings_menu(chat_id)

        if data == "mod:bf6:show":
            dev = p.get("bf6_device", "pad")
            tier = p.get("bf6_tier", "normal")
            txt = get_tier_text("bf6", dev, tier)
            return {"text": txt, "reply_markup": self._settings_menu(chat_id)["reply_markup"]}

        return None

    def handle_text(self, chat_id: int, text: str) -> Optional[Dict[str, Any]]:
        return None
