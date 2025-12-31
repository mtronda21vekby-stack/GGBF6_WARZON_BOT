# app/core/router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ui.quickbar import (
    kb_main,
    kb_settings,
    kb_games,
    kb_platform,
    kb_input,
    kb_difficulty,
    kb_roles,
    kb_bf6_classes,
    kb_game_settings_menu,
    kb_premium,
    kb_voice,
)

from app.ui.zombies_kb import (
    kb_zombies_hub,
    kb_zombies_maps,
    kb_zombies_map_menu,
)

from app.worlds.bf6.presets import (
    bf6_class_text,
    bf6_aim_sens_text,
    bf6_controller_tuning_text,
    bf6_kbm_tuning_text,
)

# Warzone/BO7 presets (RU) — ты их уже вставил
try:
    from app.worlds.warzone.presets import (
        wz_role_setup_text,
        wz_aim_sens_text,
        wz_controller_tuning_text,
        wz_kbm_tuning_text,
        wz_movement_positioning_text,
        wz_audio_visual_text,
    )
except Exception as e:
    wz_role_setup_text = None
    wz_aim_sens_text = None
    wz_controller_tuning_text = None
    wz_kbm_tuning_text = None
    wz_movement_positioning_text = None
    wz_audio_visual_text = None
    _WARZONE_IMPORT_ERR = e
else:
    _WARZONE_IMPORT_ERR = None

try:
    from app.worlds.bo7.presets import (
        bo7_role_setup_text,
        bo7_aim_sens_text,
        bo7_controller_tuning_text,
        bo7_kbm_tuning_text,
        bo7_movement_positioning_text,
        bo7_audio_visual_text,
    )
except Exception as e:
    bo7_role_setup_text = None
    bo7_aim_sens_text = None
    bo7_controller_tuning_text = None
    bo7_kbm_tuning_text = None
    bo7_movement_positioning_text = None
    bo7_audio_visual_text = None
    _BO7_IMPORT_ERR = e
else:
    _BO7_IMPORT_ERR = None

# Zombies presets (RU) — новый мир
try:
    from app.worlds.zombies.presets import (
        zombies_hub_text,
        zombies_map_overview_text,
        zombies_map_perks_text,
        zombies_map_loadout_text,
        zombies_map_easter_eggs_text,
        zombies_map_round_strategy_text,
        zombies_map_quick_tips_text,
    )
except Exception as e:
    zombies_hub_text = None
    zombies_map_overview_text = None
    zombies_map_perks_text = None
    zombies_map_loadout_text = None
    zombies_map_easter_eggs_text = None
    zombies_map_round_strategy_text = None
    zombies_map_quick_tips_text = None
    _ZOMBIES_IMPORT_ERR = e
else:
    _ZOMBIES_IMPORT_ERR = None


log = logging.getLogger("router")
if not log.handlers:
    logging.basicConfig(level=logging.INFO)


# =========================
# UPDATE NORMALIZER (MAX SAFE)
# Принимаем И dict, И pydantic-объект Update (который приходит из app.adapters.telegram.types.Update)
# =========================
def _to_update_dict(update: Any) -> Dict[str, Any]:
    if isinstance(update, dict):
        return update

    # pydantic v2
    if hasattr(update, "model_dump") and callable(getattr(update, "model_dump")):
        try:
            d = update.model_dump()
            if isinstance(d, dict):
                return d
        except Exception:
            pass

    # pydantic v1
    if hasattr(update, "dict") and callable(getattr(update, "dict")):
        try:
            d = update.dict()
            if isinstance(d, dict):
                return d
        except Exception:
            pass

    # fallback: если есть raw/original
    for attr in ("raw", "_raw", "data", "_data"):
        if hasattr(update, attr):
            try:
                d = getattr(update, attr)
                if isinstance(d, dict):
                    return d
            except Exception:
                pass

    # крайний вариант
    return {}


def _safe_get(d: dict, path: list, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _norm_game(game: str) -> str:
    g = (game or "").strip().upper()
    if g in ("BF6", "BATTLEFIELD", "BATTLEFIELD6"):
        return "BF6"
    if g in ("BO7", "BLACKOPS7", "BLACK OPS 7", "BLACK_OPS_7"):
        return "BO7"
    if g in ("WZ", "WARZONE", "WARZONE2", "WARZONE 2"):
        return "Warzone"
    return "Warzone"


def _norm_input(inp: str) -> str:
    x = (inp or "").strip().upper()
    if "KBM" in x or "MOUSE" in x or "КЛАВ" in x:
        return "KBM"
    return "Controller"


def _norm_platform(p: str) -> str:
    x = (p or "").strip().lower()
    if "play" in x or "ps" in x:
        return "PlayStation"
    if "xbox" in x:
        return "Xbox"
    return "PC"


def _norm_diff(d: str) -> str:
    x = (d or "Normal").strip().lower()
    if "demon" in x or "демон" in x:
        return "Demon"
    if "pro" in x or "проф" in x:
        return "Pro"
    return "Normal"


def _norm_voice(v: str) -> str:
    # TEAMMATE — дефолт. Коуч только если выбран явно.
    x = (v or "TEAMMATE").strip().upper()
    if x in ("COACH", "КОУЧ"):
        return "COACH"
    return "TEAMMATE"


def _norm_focus(v: str) -> str:
    x = (v or "").strip().lower()
    if x in ("aim", "аим", "aiming", "target"):
        return "aim"
    if x in ("movement", "мувмент", "move", "movement/"):
        return "movement"
    if x in ("position", "позиционка", "позиция", "positioning", "map"):
        return "position"
    return "aim"


def _role_map_ru_to_en(text: str) -> str:
    m = {
        "⚔️ Слэйер": "Slayer",
        "🚪 Энтри": "Entry",
        "🧠 IGL": "IGL",
        "🛡 Саппорт": "Support",
        "🌀 Флекс": "Flex",
    }
    return m.get(text, "Flex")


# =========================
# PREMIUM DIALOG STYLE HELPERS
# =========================
def _cap(s: str) -> str:
    return (s or "").strip()


def _sig(voice: str) -> str:
    return "— BLACK CROWN OPS 😈" if voice == "COACH" else "— BCO 😈"


def _wrap_premium(text: str, *, profile: dict) -> str:
    voice = _norm_voice(profile.get("voice", "TEAMMATE"))

    t = _cap(text)
    if not t:
        return t
    if t.startswith("✅") or t.startswith("❗️") or t.startswith("📊") or t.startswith("🧹") or t.startswith("🧨"):
        return t

    header = "👑 BLACK CROWN OPS" if voice == "COACH" else "🖤 BLACK CROWN OPS"
    mode = "📚 КОУЧ" if voice == "COACH" else "🤝 ТИММЕЙТ"
    line = "━━━━━━━━━━━━━━━━━━"

    return (
        f"{header} · {mode}\n"
        f"{line}\n"
        f"{t}\n"
        f"{line}\n"
        f"{_sig(voice)}"
    )


def _start_text(profile: dict) -> str:
    voice = _norm_voice(profile.get("voice", "TEAMMATE"))
    mode_line = "🤝 ТИММЕЙТ — режим по умолчанию" if voice == "TEAMMATE" else "📚 КОУЧ — активен"

    body = (
        "BLACK CROWN OPS — это искусственный разум,\n"
        "созданный для соревновательных FPS.\n\n"
        "Он не отвечает.\n"
        "Он анализирует.\n\n"
        "Он не подсказывает.\n"
        "Он ведёт.\n\n"
        f"{mode_line}\n\n"
        "🤝 ТИММЕЙТ\n"
        "Ты говоришь с ним, как с бойцом из своего отряда.\n\n"
        "Без лекций и воды:\n"
        "• где тебя читают\n"
        "• почему ты умираешь именно здесь\n"
        "• что сделать в следующем файте\n\n"
        "Коротко. Жёстко. По ситуации.\n"
        "Как напарник, который всегда на шаг впереди.\n\n"
        "📚 КОУЧ — режим абсолютного контроля\n"
        "Здесь нет «попробуй».\n\n"
        "Я:\n"
        "• перестраиваю мышление\n"
        "• убираю хаос в решениях\n"
        "• выстраиваю путь от текущего уровня до мирового ТОП-1\n\n"
        "Это не мотивация.\n"
        "Это система доминирования.\n\n"
        "Ты выполняешь — ты растёшь.\n"
        "Ты растёшь — ты выигрываешь.\n"
        "Если не выполняешь — ты знаешь почему.\n\n"
        "BLACK CROWN OPS не обещает результат.\n"
        "Он создаёт игрока, способного его удерживать.\n\n"
        "Напиши одной строкой:\n"
        "Игра | input | где ты сейчас | где должен быть\n\n"
        "Дальше — контроль на моей стороне. 😈"
    )
    return _wrap_premium(body, profile=profile)


def _webapp_url() -> str:
    url = (os.getenv("WEBAPP_URL") or "").strip()
    if url:
        return url
    base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if base:
        return base + "/webapp"
    return ""


def _make_training_plan(profile: dict, focus: str) -> str:
    """
    Детерминированный план (не зависит от AI).
    focus: aim | movement | position
    """
    prof = dict(profile or {})
    game = _norm_game(prof.get("game", "Warzone"))
    inp = _norm_input(prof.get("input", "Controller"))
    diff = _norm_diff(prof.get("difficulty", "Normal"))
    voice = _norm_voice(prof.get("voice", "TEAMMATE"))
    focus = _norm_focus(focus)

    # микро-стиль: Demon/Pro/Normal влияет на жёсткость подачи
    if diff == "Demon":
        tone = "Жёстко. Быстро. Без оправданий."
    elif diff == "Pro":
        tone = "Плотно и дисциплинированно."
    else:
        tone = "Спокойно, но результативно."

    input_block = (
        "🎮 Input: Controller\n"
        "• правило: левый стик — позиция, правый — подтверждение.\n"
        "• цель: стабильность трекинга + меньше паники в файте.\n"
        if inp == "Controller" else
        "⌨️ Input: KBM\n"
        "• правило: мышь — микро, клавиатура — макро.\n"
        "• цель: чистый кроссхейр + тайминг на пике.\n"
    )

    focus_title = {"aim": "🎯 AIM", "movement": "🧠 МУВМЕНТ", "position": "🗺 ПОЗИЦИОНКА"}[focus]

    # “фокусный” 10-мин блок
    if focus == "aim":
        block10 = (
            "10 мин — AIM (ядро)\n"
            "1) 4 мин: трекинг (движущиеся цели)\n"
            "   • правило: кроссхейр на груди/верх-тело, не на голове\n"
            "2) 3 мин: микрофлики (короткие переносы)\n"
            "   • правило: перенос → стоп → выстрел (не наоборот)\n"
            "3) 3 мин: контроль отдачи/темпа\n"
            "   • правило: темп важнее скорости\n"
        )
        metric = "Метрика: 3 раза подряд “чистый клип” без лишнего тряса + меньше 1 паник-пика за катку."
    elif focus == "movement":
        block10 = (
            "10 мин — МУВМЕНТ (ядро)\n"
            "1) 4 мин: вход/выход из угла\n"
            "   • правило: не стой — режь угол, меняй высоту\n"
            "2) 3 мин: ресет после выстрела\n"
            "   • правило: дал урон → смена линии (не повторяй пик)\n"
            "3) 3 мин: “выживание”\n"
            "   • правило: если не можешь выиграть — живи и перезайди\n"
        )
        metric = "Метрика: минимум 3 ресета за катку вместо ‘умираю на повторном пике’."
    else:
        block10 = (
            "10 мин — ПОЗИЦИОНКА (ядро)\n"
            "1) 4 мин: правило углов\n"
            "   • правило: занимай позицию, где ты видишь первым\n"
            "2) 3 мин: ротации\n"
            "   • правило: двигайся раньше, чем ‘надо’ (на 10–15 сек)\n"
            "3) 3 мин: дисциплина в файте\n"
            "   • правило: один угол — один контакт, потом смена\n"
        )
        metric = "Метрика: 0 смертей ‘в спину’ по своей вине + 2 ранние ротации за матч."

    finisher5 = (
        "5 мин — закрепление в бою\n"
        "• 1 файт: играешь только по правилам фокуса (без геройства)\n"
        "• после: 1 фраза отчёта — что было легче/сложнее\n"
    )

    return (
        f"{focus_title} · 20-мин план\n"
        f"Игра: {game} | Режим: {diff}\n"
        f"{tone}\n\n"
        "5 мин — контроль (разминка)\n"
        "• 2 мин: кроссхейр-плейсмент (всегда на уровне контакта)\n"
        "• 3 мин: 3 коротких повторения ‘вижу → фиксирую → стреляю’\n\n"
        f"{block10}\n"
        f"{finisher5}\n"
        f"{input_block}\n"
        f"{metric}\n\n"
        + ("📚 Коуч-правило: если ты не можешь описать план в 1 строку — у тебя не план, у тебя надежда.\n" if voice == "COACH"
           else "🤝 Тиммейт: сделай это 2 дня подряд — и ты сам увидишь разницу.\n")
    )


def _vod_prompt(profile: dict, times: list[str], note: str) -> str:
    game = _norm_game((profile or {}).get("game", "Warzone"))
    inp = _norm_input((profile or {}).get("input", "Controller"))
    diff = _norm_diff((profile or {}).get("difficulty", "Normal"))
    role = (profile or {}).get("role", "Flex")
    bf6_class = (profile or {}).get("bf6_class", "Assault")

    t = [x for x in (times or []) if (x or "").strip()]
    tline = ", ".join(t) if t else "таймкоды не указаны"

    return (
        "VOD разбор без видео.\n"
        "Дай элитный анализ решений по каждому таймкоду:\n"
        "• что игрок хотел сделать\n"
        "• что было ошибкой (1-2 пункта)\n"
        "• что делать вместо этого (конкретно)\n"
        "• микро-чеклист на следующий раз\n\n"
        f"Контекст: game={game}, input={inp}, mode={diff}, role={role}, bf6_class={bf6_class}\n"
        f"Таймкоды: {tline}\n"
        f"План игрока/заметка: {note}\n"
    )


@dataclass
class Router:
    tg: Any
    brain: Any = None
    profiles: Any = None
    store: Any = None
    settings: Any = None

    # =========================================================
    # PUBLIC: Mini App data entrypoint (для webhook.py pre-handler)
    # Не ломает ничего: просто вызывает внутренний обработчик.
    # =========================================================
    async def handle_webapp_data(self, update: Any, data_raw: str) -> None:
        upd = _to_update_dict(update)
        msg = upd.get("message") or upd.get("edited_message")
        chat_id = _safe_get(msg, ["chat", "id"]) if msg else None
        if not chat_id:
            # если вдруг прилетело без message (редко), просто игнор
            return
        await self._on_webapp_data(int(chat_id), str(data_raw or ""))

    async def handle_update(self, update: Any) -> None:
        update = _to_update_dict(update)

        msg = update.get("message") or update.get("edited_message")
        cbq = update.get("callback_query")

        chat_id: Optional[int] = None
        text: str = ""
        webapp_data: Optional[str] = None

        if msg:
            chat_id = _safe_get(msg, ["chat", "id"])
            text = (msg.get("text") or "").strip()
            webapp_data = _safe_get(msg, ["web_app_data", "data"])
        elif cbq:
            chat_id = _safe_get(cbq, ["message", "chat", "id"])
            text = (cbq.get("data") or "").strip()
        else:
            return

        if not chat_id:
            return

        # =========================
        # MINI APP PAYLOAD (Telegram WebApp)
        # =========================
        if webapp_data:
            await self._on_webapp_data(chat_id, webapp_data)
            return

        # =========================
        # COMMANDS
        # =========================
        if text in ("/start", "/menu", "Меню", "📋 Меню"):
            prof = self._get_profile(chat_id)
            await self._send_main(chat_id, _start_text(prof))
            return

        if text in ("/status", "/health"):
            await self._on_status(chat_id)
            return

        # =========================
        # MAIN QUICKBAR
        # =========================
        if text == "🎮 Игра":
            await self._on_game(chat_id)
            return

        if text == "⚙️ Настройки":
            await self._send(chat_id, "⚙️ Настройки (профиль):", kb_settings())
            return

        if text == "🎭 Роль/Класс":
            await self._on_role_or_class(chat_id)
            return

        if text == "🛰 MINI APP":
            prof = self._get_profile(chat_id)
            url = _webapp_url()
            if url:
                await self._send_main(
                    chat_id,
                    _wrap_premium(
                        (
                            "🛰 MINI APP готов.\n"
                            "Нажми кнопку 🛰 MINI APP на клавиатуре — откроется панель.\n\n"
                            "Если не открывается:\n"
                            "• проверь WEBAPP_URL / PUBLIC_BASE_URL в Render\n"
                            "• проверь что домен https\n"
                        ),
                        profile=prof,
                    ),
                )
            else:
                await self._send_main(
                    chat_id,
                    _wrap_premium(
                        (
                            "🛰 MINI APP пока не подключён.\n\n"
                            "Нужно добавить в Render → Environment:\n"
                            "• WEBAPP_URL=https://<твой-домен>/webapp\n"
                            "или\n"
                            "• PUBLIC_BASE_URL=https://<твой-домен>\n\n"
                            "После этого кнопка откроет панель."
                        ),
                        profile=prof,
                    ),
                )
            return

        if text in ("🧠 ИИ", "ИИ"):
            prof = self._get_profile(chat_id)
            voice = _norm_voice(prof.get("voice", "TEAMMATE"))
            vv = "🤝 Тиммейт" if voice == "TEAMMATE" else "📚 Коуч"
            await self._send_main(
                chat_id,
                _wrap_premium(
                    (
                        f"🧠 ИИ активен | Стиль: {vv}\n\n"
                        "Формат (чтобы я дал элитный разбор):\n"
                        "• что случилось\n"
                        "• где умираешь (угол/ротация/трекинг/паника)\n"
                        "• цель (стабильность/киллы/выживание)\n\n"
                        "Сменить стиль: 💎 Premium → 🎙 Голос.\n"
                        "Отвечу без копипасты. По делу. 😈"
                    ),
                    profile=prof,
                ),
            )
            return

        if text == "🎯 Тренировка":
            prof = self._get_profile(chat_id)
            await self._send_main(
                chat_id,
                _wrap_premium(
                    (
                        "🎯 Тренировка\n\n"
                        "Напиши одной строкой:\n"
                        "Игра | input | что болит (аим/мувмент/позиционка) | где чаще умираешь\n\n"
                        "Сделаю план на 20 минут + метрика прогресса.\n"
                        "Юмор: «план без метрики — это мечта, а не тренировка» 😄"
                    ),
                    profile=prof,
                ),
            )
            return

        if text == "🎬 VOD":
            prof = self._get_profile(chat_id)
            await self._send_main(
                chat_id,
                _wrap_premium(
                    (
                        "🎬 VOD (разбор)\n\n"
                        "Пока без загрузки видео.\n"
                        "Кинь 3 таймкода текстом (00:12 / 01:40 / 03:05)\n"
                        "+ что ты хотел сделать.\n\n"
                        "Разберу решения как тиммейт/коуч."
                    ),
                    profile=prof,
                ),
            )
            return

        # ===== ZOMBIES MAIN ENTRY =====
        if text == "🧟 Zombies":
            prof = self._get_profile(chat_id)
            if zombies_hub_text:
                await self._send(chat_id, _wrap_premium(zombies_hub_text(prof), profile=prof), kb_zombies_hub())
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "📌 Профиль":
            await self._on_profile(chat_id)
            return

        if text == "📊 Статус":
            await self._on_status(chat_id)
            return

        if text == "💎 Premium":
            await self._send(chat_id, "💎 Premium Hub:", kb_premium())
            return

        if text == "🧹 Очистить память":
            await self._on_clear_memory(chat_id)
            return

        if text == "🧨 Сброс":
            await self._on_reset(chat_id)
            return

        # =========================
        # PREMIUM HUB
        # =========================
        if text == "🎙 Голос: Тиммейт/Коуч":
            await self._send(chat_id, "🎙 Выбери стиль общения:", kb_voice())
            return

        if text in ("🤝 Тиммейт", "📚 Коуч"):
            voice = "TEAMMATE" if "Тиммейт" in text else "COACH"
            self._set_profile_field(chat_id, "voice", voice)
            await self._send(chat_id, f"✅ Голос = {voice}", kb_premium())
            return

        if text == "🎯 Тренировка: План":
            prof = self._get_profile(chat_id)
            await self._send_main(
                chat_id,
                _wrap_premium(
                    (
                        "🎯 План тренировки (20 минут)\n"
                        "1) 5 мин — разминка (контроль)\n"
                        "2) 10 мин — основной фокус (твой слабый элемент)\n"
                        "3) 5 мин — закрепление в реальном бою\n\n"
                        "Напиши: игра | input | слабое место — сделаю план под тебя 😈"
                    ),
                    profile=prof,
                ),
            )
            return

        if text == "🎬 VOD: Разбор":
            prof = self._get_profile(chat_id)
            await self._send_main(chat_id, _wrap_premium("🎬 Кидай 3 таймкода + что хотел сделать. Разберу.", profile=prof))
            return

        if text == "🧠 Память: Статус":
            await self._on_status(chat_id)
            return

        # =========================
        # SETTINGS FLOW (PROFILE)
        # =========================
        if text in ("⬅️ Назад", "Назад"):
            await self._send_main(chat_id, "↩️ Ок. Меню снизу 👇")
            return

        if text == "🎮 Выбрать игру":
            await self._send(chat_id, "🎮 Выбери игру:", kb_games())
            return

        if text in ("🔥 Warzone", "💣 BO7", "🪖 BF6"):
            game = "Warzone" if "Warzone" in text else ("BO7" if "BO7" in text else "BF6")
            self._set_profile_field(chat_id, "game", game)
            await self._send(chat_id, f"✅ Игра = {game}", kb_settings())
            return

        if text == "🖥 Платформа":
            await self._send(chat_id, "🖥 Выбери платформу:", kb_platform())
            return

        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            platform = "PC" if "PC" in text else ("PlayStation" if "PlayStation" in text else "Xbox")
            self._set_profile_field(chat_id, "platform", platform)
            await self._send(chat_id, f"✅ Платформа = {platform}", kb_settings())
            return

        if text == "⌨️ Input":
            await self._send(chat_id, "⌨️ Выбери input:", kb_input())
            return

        if text in ("⌨️ KBM", "🎮 Controller"):
            inp = "KBM" if "KBM" in text else "Controller"
            self._set_profile_field(chat_id, "input", inp)
            await self._send(chat_id, f"✅ Input = {inp}", kb_settings())
            return

        if text == "😈 Режим мышления":
            await self._send(chat_id, "😈 Выбери режим:", kb_difficulty())
            return

        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            diff = "Normal" if "Normal" in text else ("Pro" if "Pro" in text else "Demon")
            self._set_profile_field(chat_id, "difficulty", diff)
            await self._send(chat_id, f"✅ Режим = {diff}", kb_settings())
            return

        # =========================
        # GAME SETTINGS (PER WORLD)
        # =========================
        if text == "🧩 Настройки игры":
            prof = self._get_profile(chat_id)
            game = _norm_game(prof.get("game", "Warzone"))
            await self._send(chat_id, f"🧩 Настройки игры: {game}", kb_game_settings_menu(game))
            return

        # =========================
        # ROLE / CLASS PICK
        # =========================
        if text in ("⚔️ Слэйер", "🚪 Энтри", "🧠 IGL", "🛡 Саппорт", "🌀 Флекс"):
            role = _role_map_ru_to_en(text)
            self._set_profile_field(chat_id, "role", role)
            await self._send_main(chat_id, f"✅ Роль = {role}\nТеперь открой 🧩 Настройки игры — там будут цифры и детали 😈")
            return

        if text in ("🟥 Assault", "🟦 Recon", "🟨 Engineer", "🟩 Medic"):
            cls = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "bf6_class", cls)
            await self._send_main(chat_id, bf6_class_text(self._get_profile(chat_id)))
            return

        # =========================
        # ZOMBIES HUB ROUTES
        # =========================
        if text == "🗺 Карты":
            await self._send(chat_id, "🗺 Выбери карту:", kb_zombies_maps())
            return

        if text in ("🧟 Ashes", "🧟 Astra"):
            map_name = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "zombies_map", map_name)
            await self._send(chat_id, f"✅ Карта = {map_name}", kb_zombies_map_menu(map_name))
            return

        if text == "🧪 Перки":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_perks_text:
                await self._send(chat_id, _wrap_premium(zombies_map_perks_text(m), profile=prof), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "🔫 Оружие":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_loadout_text:
                await self._send(chat_id, _wrap_premium(zombies_map_loadout_text(m), profile=prof), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "🥚 Пасхалки":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_easter_eggs_text:
                await self._send(chat_id, _wrap_premium(zombies_map_easter_eggs_text(m), profile=prof), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "🧠 Стратегия раундов":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_round_strategy_text:
                await self._send(chat_id, _wrap_premium(zombies_map_round_strategy_text(m), profile=prof), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "⚡ Быстрые советы":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_quick_tips_text:
                await self._send(chat_id, _wrap_premium(zombies_map_quick_tips_text(m), profile=prof), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text.startswith("🧟 ") and ":" in text:
            left, right = text.split(":", 1)
            map_name = left.replace("🧟", "").strip()
            action = right.strip().lower()

            self._set_profile_field(chat_id, "zombies_map", map_name)
            prof = self._get_profile(chat_id)

            if "обзор" in action and zombies_map_overview_text:
                await self._send(chat_id, _wrap_premium(zombies_map_overview_text(map_name), profile=prof), kb_zombies_map_menu(map_name))
                return
            if "перки" in action and zombies_map_perks_text:
                await self._send(chat_id, _wrap_premium(zombies_map_perks_text(map_name), profile=prof), kb_zombies_map_menu(map_name))
                return
            if "оружие" in action and zombies_map_loadout_text:
                await self._send(chat_id, _wrap_premium(zombies_map_loadout_text(map_name), profile=prof), kb_zombies_map_menu(map_name))
                return
            if "пасх" in action and zombies_map_easter_eggs_text:
                await self._send(chat_id, _wrap_premium(zombies_map_easter_eggs_text(map_name), profile=prof), kb_zombies_map_menu(map_name))
                return
            if "стратег" in action and zombies_map_round_strategy_text:
                await self._send(chat_id, _wrap_premium(zombies_map_round_strategy_text(map_name), profile=prof), kb_zombies_map_menu(map_name))
                return
            if ("быстр" in action or "совет" in action) and zombies_map_quick_tips_text:
                await self._send(chat_id, _wrap_premium(zombies_map_quick_tips_text(map_name), profile=prof), kb_zombies_map_menu(map_name))
                return

            await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        # =========================
        # MENU ITEMS (MUST MATCH quickbar.py)
        # =========================
        if text == "🎭 Warzone: Роль":
            self._set_profile_field(chat_id, "game", "Warzone")
            await self._send(chat_id, "🎭 Warzone: выбери роль:", kb_roles())
            return

        if text == "🎯 Warzone: Aim/Sens":
            if wz_aim_sens_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(wz_aim_sens_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "🎮 Warzone: Controller":
            if wz_controller_tuning_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(wz_controller_tuning_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "⌨️ Warzone: KBM":
            if wz_kbm_tuning_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(wz_kbm_tuning_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "🧠 Warzone: Мувмент/Позиционка":
            if wz_movement_positioning_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(wz_movement_positioning_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "🎧 Warzone: Аудио/Видео":
            if wz_audio_visual_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(wz_audio_visual_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "🎭 BO7: Роль":
            self._set_profile_field(chat_id, "game", "BO7")
            await self._send(chat_id, "🎭 BO7: выбери роль:", kb_roles())
            return

        if text == "🎯 BO7: Aim/Sens":
            if bo7_aim_sens_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(bo7_aim_sens_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "🎮 BO7: Controller":
            if bo7_controller_tuning_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(bo7_controller_tuning_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "⌨️ BO7: KBM":
            if bo7_kbm_tuning_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(bo7_kbm_tuning_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "🧠 BO7: Мувмент/Позиционка":
            if bo7_movement_positioning_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(bo7_movement_positioning_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "🎧 BO7: Аудио/Видео":
            if bo7_audio_visual_text:
                prof = self._get_profile(chat_id)
                await self._send_main(chat_id, _wrap_premium(bo7_audio_visual_text(prof), profile=prof))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "🪖 BF6: Class Settings":
            self._set_profile_field(chat_id, "game", "BF6")
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
            return

        if text == "🎯 BF6: Aim/Sens":
            self._set_profile_field(chat_id, "game", "BF6")
            prof = self._get_profile(chat_id)
            await self._send_main(chat_id, _wrap_premium(bf6_aim_sens_text(prof), profile=prof))
            return

        if text == "🎮 BF6: Controller Tuning":
            self._set_profile_field(chat_id, "game", "BF6")
            prof = self._get_profile(chat_id)
            await self._send_main(chat_id, _wrap_premium(bf6_controller_tuning_text(prof), profile=prof))
            return

        if text == "⌨️ BF6: KBM Tuning":
            self._set_profile_field(chat_id, "game", "BF6")
            prof = self._get_profile(chat_id)
            await self._send_main(chat_id, _wrap_premium(bf6_kbm_tuning_text(prof), profile=prof))
            return

        # =========================
        # DEFAULT -> AI CHAT (REAL)
        # =========================
        await self._chat_to_brain(chat_id, text)

    # ---------------- MINI APP receiver ----------------
    async def _on_webapp_data(self, chat_id: int, data: str) -> None:
        """
        Полная поддержка Mini App payload из app.js:
        type:
          - nav {target}
          - set_profile {profile}
          - sync_request
          - one_line {text, profile?}
          - training_plan {focus, profile?}
          - vod {times, note, profile?}
          - zombies_open {map}
          - zombies {action, map}
          - pay {plan}
        """
        prof = self._get_profile(chat_id)

        raw = (data or "").strip()
        if not raw:
            await self._send_main(chat_id, _wrap_premium("🛰 MINI APP прислал пустые данные.", profile=prof))
            return

        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"type": "text", "text": raw}

        if not isinstance(payload, dict):
            payload = {"type": "text", "text": raw}

        # ---- normalize: sometimes app packs {meta, v, t, ...}
        ptype = str(payload.get("type") or "text").strip().lower()

        # profile may come as payload.profile or flat keys
        profile_from_payload = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
        if not isinstance(profile_from_payload, dict):
            profile_from_payload = {}

        # helper: apply profile dict (max safe)
        def apply_profile_dict(pdict: dict) -> None:
            if not isinstance(pdict, dict):
                return
            for key in ("game", "platform", "input", "difficulty", "voice", "role", "bf6_class", "zombies_map"):
                if key in pdict and str(pdict.get(key)).strip():
                    self._set_profile_field(chat_id, key, str(pdict.get(key)).strip())

        # 1) If payload carries profile, apply it first (so next actions are consistent)
        if profile_from_payload:
            apply_profile_dict(profile_from_payload)
            prof = self._get_profile(chat_id)

        # Also accept flat keys (some clients may send directly)
        flat_profile_like = {}
        for k in ("game", "platform", "input", "difficulty", "voice", "role", "bf6_class", "zombies_map"):
            if k in payload and str(payload.get(k)).strip():
                flat_profile_like[k] = payload.get(k)
        if flat_profile_like:
            apply_profile_dict(flat_profile_like)
            prof = self._get_profile(chat_id)

        # ---------- ROUTES ----------
        if ptype == "nav":
            target = str(payload.get("target") or "").strip().lower()

            if target in ("main", "home", "menu", ""):
                await self._send_main(chat_id, _start_text(prof))
                return

            if target in ("premium", "premium_hub"):
                await self._send(chat_id, "💎 Premium Hub:", kb_premium())
                return

            if target in ("training", "coach"):
                # “open training” = показать экран тренировки в боте
                await self._send_main(chat_id, _wrap_premium("🎯 Открыл: Тренировка.\nЖми кнопки / отправь запрос одной строкой.", profile=prof))
                await self._send(chat_id, "🎯 Тренировка:", kb_main())
                return

            if target in ("vod",):
                await self._send_main(chat_id, _wrap_premium("🎬 Открыл: VOD.\nКинь 3 таймкода + план — разберу.", profile=prof))
                return

            if target in ("settings",):
                await self._send(chat_id, "⚙️ Настройки (профиль):", kb_settings())
                return

            if target in ("zombies", "zombies_open"):
                if zombies_hub_text:
                    await self._send(chat_id, _wrap_premium(zombies_hub_text(prof), profile=prof), kb_zombies_hub())
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            # fallback: unknown target
            await self._send_main(chat_id, _wrap_premium(f"🛰 NAV: неизвестная цель: {target}", profile=prof))
            return

        if ptype in ("set_profile", "profile", "settings"):
            pdict = payload.get("profile") if isinstance(payload.get("profile"), dict) else payload
            apply_profile_dict(pdict if isinstance(pdict, dict) else {})
            prof = self._get_profile(chat_id)
            await self._send_main(chat_id, _wrap_premium("✅ Профиль применён из MINI APP.\nТеперь кнопки в боте будут работать под новые настройки.", profile=prof))
            return

        if ptype in ("sync_request", "sync"):
            # Mini App сам хранит state в Cloud/Local, но полезно отдать текущий профиль
            await self._on_profile(chat_id)
            return

        if ptype in ("one_line",):
            text = str(payload.get("text") or "").strip()
            if not text:
                await self._send_main(chat_id, _wrap_premium("🧠 One-line пустой. Заполни строку и отправь.", profile=prof))
                return
            # отправляем в мозг как есть (это и есть формат “1 строка”)
            await self._chat_to_brain(chat_id, text)
            return

        if ptype in ("training_plan", "train", "training"):
            focus = _norm_focus(str(payload.get("focus") or "aim"))
            # жёсткий детерминированный план (всегда работает)
            plan = _make_training_plan(prof, focus)
            await self._send_main(chat_id, _wrap_premium(plan, profile=prof))
            return

        if ptype in ("vod",):
            times = payload.get("times") or payload.get("timecodes") or []
            if not isinstance(times, list):
                times = [str(times)]
            times = [str(x).strip() for x in times if str(x).strip()]
            note = str(payload.get("note") or payload.get("text") or "").strip()

            if self.brain and hasattr(self.brain, "reply"):
                # в brain отправляем максимально структурированный запрос
                prompt = _vod_prompt(prof, times, note)
                await self._chat_to_brain(chat_id, prompt)
                return

            # fallback без AI
            tline = ", ".join(times) if times else "—"
            await self._send_main(
                chat_id,
                _wrap_premium(
                    (
                        "🎬 VOD получен.\n\n"
                        f"Таймкоды: {tline}\n"
                        f"План/заметка: {note or '—'}\n\n"
                        "Чтобы сделать элитный разбор автоматически — включи AI (📊 Статус)."
                    ),
                    profile=prof,
                ),
            )
            return

        if ptype in ("zombies_open",):
            m = str(payload.get("map") or prof.get("zombies_map") or "Ashes").strip() or "Ashes"
            self._set_profile_field(chat_id, "zombies_map", m)
            prof = self._get_profile(chat_id)
            if zombies_hub_text:
                await self._send(chat_id, _wrap_premium(zombies_hub_text(prof), profile=prof), kb_zombies_hub())
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if ptype in ("zombies",):
            action = str(payload.get("action") or "").strip().lower()
            m = str(payload.get("map") or prof.get("zombies_map") or "Ashes").strip() or "Ashes"
            self._set_profile_field(chat_id, "zombies_map", m)
            prof = self._get_profile(chat_id)

            if action in ("perks", "perk", "перки"):
                if zombies_map_perks_text:
                    await self._send(chat_id, _wrap_premium(zombies_map_perks_text(m), profile=prof), kb_zombies_map_menu(m))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if action in ("loadout", "weapon", "weapons", "оружие"):
                if zombies_map_loadout_text:
                    await self._send(chat_id, _wrap_premium(zombies_map_loadout_text(m), profile=prof), kb_zombies_map_menu(m))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if action in ("eggs", "easter_eggs", "пасхалки"):
                if zombies_map_easter_eggs_text:
                    await self._send(chat_id, _wrap_premium(zombies_map_easter_eggs_text(m), profile=prof), kb_zombies_map_menu(m))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if action in ("rounds", "round_strategy", "strategy", "стратегия"):
                if zombies_map_round_strategy_text:
                    await self._send(chat_id, _wrap_premium(zombies_map_round_strategy_text(m), profile=prof), kb_zombies_map_menu(m))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if action in ("tips", "quick_tips", "советы"):
                if zombies_map_quick_tips_text:
                    await self._send(chat_id, _wrap_premium(zombies_map_quick_tips_text(m), profile=prof), kb_zombies_map_menu(m))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            # unknown zombies action -> open hub
            if zombies_hub_text:
                await self._send(chat_id, _wrap_premium(zombies_hub_text(prof), profile=prof), kb_zombies_hub())
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if ptype in ("pay", "payment"):
            plan = str(payload.get("plan") or "").strip()
            # Здесь реальная оплата через Invoice будет отдельным модулем/сервисом.
            # Сейчас: максимум UX — подтверждение + направление в Premium Hub.
            pretty = "Month" if "month" in plan else ("Lifetime" if "life" in plan else plan or "—")
            await self._send(
                chat_id,
                _wrap_premium(
                    (
                        f"💎 Запрос на оплату принят.\n"
                        f"План: {pretty}\n\n"
                        "Следующий шаг (Invoice):\n"
                        "• я создам счёт в боте и ты оплатишь в 2 тапа.\n\n"
                        "Сейчас открываю Premium Hub 👇"
                    ),
                    profile=prof,
                ),
                kb_premium(),
            )
            return

        # ---------- fallback ----------
        # если пришёл какой-то текст — отправим в мозг, иначе покажем payload
        text = str(payload.get("text") or payload.get("value") or "").strip()
        if text:
            await self._chat_to_brain(chat_id, text)
            return

        await self._send_main(chat_id, _wrap_premium(f"🛰 MINI APP payload принят, но без действия.\nТип: {ptype}", profile=prof))

    # ---------------- messaging helpers ----------------
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, kb_main())

    # ---------------- presets missing helper ----------------
    def _missing_presets_msg(self, world: str, err: Exception | None) -> str:
        base = f"❗️Не вижу пресеты для {world}.\nПроверь путь файла:\n"
        if world == "warzone":
            base += "• app/worlds/warzone/presets.py\n"
        elif world == "bo7":
            base += "• app/worlds/bo7/presets.py\n"
        elif world == "zombies":
            base += "• app/worlds/zombies/presets.py\n"
        else:
            base += "• app/worlds/<world>/presets.py\n"
        if err:
            base += f"\nТехнически: {type(err).__name__}: {err}\n"
        base += "\nЮмор: «бот не тупой — он просто не видит файл» 😄"
        return base

    # ---------------- profile helpers ----------------
    def _get_profile(self, chat_id: int) -> dict:
        if self.profiles:
            for name in ("get", "get_profile", "read"):
                if hasattr(self.profiles, name):
                    try:
                        prof = getattr(self.profiles, name)(chat_id)
                        if isinstance(prof, dict):
                            prof = dict(prof)
                            prof["game"] = _norm_game(prof.get("game", "Warzone"))
                            prof["platform"] = _norm_platform(prof.get("platform", "PC"))
                            prof["input"] = _norm_input(prof.get("input", "Controller"))
                            prof["difficulty"] = _norm_diff(prof.get("difficulty", "Normal"))
                            prof["voice"] = _norm_voice(prof.get("voice", "TEAMMATE"))
                            prof.setdefault("role", "Flex")
                            prof.setdefault("bf6_class", "Assault")
                            prof.setdefault("zombies_map", "Ashes")
                            return prof
                    except Exception as e:
                        log.exception("profiles.get failed: %s", e)

        return {
            "game": "Warzone",
            "platform": "PC",
            "input": "Controller",
            "difficulty": "Normal",
            "voice": "TEAMMATE",
            "role": "Flex",
            "bf6_class": "Assault",
            "zombies_map": "Ashes",
        }

    def _set_profile_field(self, chat_id: int, key: str, val: str) -> None:
        if key == "game":
            val = _norm_game(val)
        elif key == "platform":
            val = _norm_platform(val)
        elif key == "input":
            val = _norm_input(val)
        elif key == "difficulty":
            val = _norm_diff(val)
        elif key == "voice":
            val = _norm_voice(val)

        if self.profiles:
            for name in ("set_field", "set", "set_value", "update", "update_profile"):
                if hasattr(self.profiles, name):
                    try:
                        fn = getattr(self.profiles, name)
                        try:
                            fn(chat_id, key, val)
                        except TypeError:
                            fn(chat_id, {key: val})
                        return
                    except Exception as e:
                        log.exception("profiles.set failed: %s", e)

        if self.store and hasattr(self.store, "set_profile"):
            try:
                self.store.set_profile(chat_id, {key: val})
            except Exception as e:
                log.exception("store.set_profile failed: %s", e)

    # ---------------- UI handlers ----------------
    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        voice = "🤝 Тиммейт" if _norm_voice(prof.get("voice")) == "TEAMMATE" else "📚 Коуч"
        await self._send_main(
            chat_id,
            _wrap_premium(
                (
                    "🎮 Текущее:\n"
                    f"• Game: {prof.get('game')}\n"
                    f"• Platform: {prof.get('platform')}\n"
                    f"• Input: {prof.get('input')}\n"
                    f"• Brain Mode: {prof.get('difficulty')}\n"
                    f"• Voice: {voice}\n"
                    f"• Role: {prof.get('role')}\n"
                    f"• BF6 Class: {prof.get('bf6_class')}\n"
                    f"• Zombies Map: {prof.get('zombies_map')}\n\n"
                    "😄 Юмор: если всё выставил, но всё равно умираешь — значит пора не цифры менять, а решения."
                ),
                profile=prof,
            ),
        )

    async def _on_role_or_class(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = _norm_game(prof.get("game", "Warzone")).upper()
        if game == "BF6":
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
            return
        await self._send(chat_id, "🎭 Выбери роль:", kb_roles())

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        lines = [
            f"• game: {prof.get('game')}",
            f"• platform: {prof.get('platform')}",
            f"• input: {prof.get('input')}",
            f"• difficulty: {prof.get('difficulty')}",
            f"• voice: {prof.get('voice')}",
            f"• role: {prof.get('role')}",
            f"• bf6_class: {prof.get('bf6_class')}",
            f"• zombies_map: {prof.get('zombies_map')}",
        ]
        await self._send_main(chat_id, _wrap_premium("📌 Профиль:\n" + "\n".join(lines), profile=prof))

    async def _on_status(self, chat_id: int) -> None:
        mem = {}
        if self.store and hasattr(self.store, "stats"):
            try:
                mem = self.store.stats(chat_id)
            except Exception:
                mem = {}

        ai_key = (getattr(self.settings, "openai_api_key", "") or "").strip() if self.settings else ""
        ai_enabled = bool(getattr(self.settings, "ai_enabled", True)) if self.settings else False
        model = getattr(self.settings, "openai_model", "gpt-4.1-mini") if self.settings else "?"

        ai_state = "ON" if (ai_enabled and ai_key) else "OFF"
        why = "OK" if ai_state == "ON" else ("OPENAI_API_KEY missing" if not ai_key else "AI_ENABLED=0")

        await self._send_main(
            chat_id,
            "📊 Статус: OK\n"
            f"🧠 Memory: {mem or 'on'}\n"
            f"🤖 AI: {ai_state} | model={model} | reason={why}\n\n"
            "Если AI OFF — это не демоны, это ENV-переменные 😄",
        )

    async def _on_clear_memory(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧹 Память очищена ✅")

    async def _on_reset(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        if self.profiles and hasattr(self.profiles, "reset"):
            try:
                self.profiles.reset(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧨 Сброс выполнен ✅\nВернул дефолтные настройки.")

    # ---------------- AI chat ----------------
    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "user", text)
            except Exception:
                pass

        prof = self._get_profile(chat_id)

        history = []
        if self.store and hasattr(self.store, "get"):
            try:
                history = self.store.get(chat_id)
            except Exception:
                history = []

        reply = None
        if self.brain and hasattr(self.brain, "reply"):
            try:
                fn = self.brain.reply
                if inspect.iscoroutinefunction(fn):
                    reply = await fn(text=text, profile=prof, history=history)
                else:
                    out = fn(text=text, profile=prof, history=history)
                    reply = await out if inspect.isawaitable(out) else out
            except Exception as e:
                reply = (
                    "🧠 ИИ: ERROR\n"
                    f"{type(e).__name__}: {e}\n\n"
                    "Подсказка:\n"
                    "• проверь OPENAI_API_KEY\n"
                    "• AI_ENABLED=1\n"
                    "• OPENAI_MODEL\n"
                )

        if not reply:
            voice = _norm_voice(prof.get("voice", "TEAMMATE"))
            if voice == "COACH":
                reply = (
                    "📚 Коуч (fallback | абсолютный контроль):\n"
                    "1) Диагноз: мало вводных.\n"
                    "2) Дай 3 факта:\n"
                    "   • игра/режим\n"
                    "   • input\n"
                    "   • где умираешь (угол/ротация/трекинг/паника)\n"
                    "3) Я отвечу так:\n"
                    "   • причина → правило → чек-лист → микро-упражнение → метрика.\n\n"
                    "AI включим через ENV (📊 Статус)."
                )
            else:
                reply = (
                    "🤝 Тиммейт (fallback | но умный):\n"
                    "Ок, давай быстро и по-человечески.\n"
                    "Кинь одной строкой:\n"
                    "Игра | input | где умираешь | цель\n\n"
                    "Я дам:\n"
                    "• 1 главный косяк\n"
                    "• 3 правила на катку\n"
                    "• план на 10 минут тренировки\n\n"
                    "AI включим через ENV (📊 Статус). 😈"
                )

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, _wrap_premium(str(reply), profile=prof))
