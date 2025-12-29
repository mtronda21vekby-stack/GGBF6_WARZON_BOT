# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import logging
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
    x = (v or "TEAMMATE").strip().upper()
    if x in ("COACH", "КОУЧ"):
        return "COACH"
    return "TEAMMATE"


def _role_map_ru_to_en(text: str) -> str:
    m = {
        "⚔️ Слэйер": "Slayer",
        "🚪 Энтри": "Entry",
        "🧠 IGL": "IGL",
        "🛡 Саппорт": "Support",
        "🌀 Флекс": "Flex",
    }
    return m.get(text, "Flex")


@dataclass
class Router:
    tg: Any
    brain: Any = None
    profiles: Any = None
    store: Any = None
    settings: Any = None

    async def handle_update(self, update: Dict[str, Any]) -> None:
        msg = update.get("message") or update.get("edited_message")
        cbq = update.get("callback_query")

        chat_id: Optional[int] = None
        text: str = ""

        if msg:
            chat_id = _safe_get(msg, ["chat", "id"])
            text = (msg.get("text") or "").strip()
        elif cbq:
            chat_id = _safe_get(cbq, ["message", "chat", "id"])
            text = (cbq.get("data") or "").strip()
        else:
            return

        if not chat_id:
            return

        # =========================
        # COMMANDS
        # =========================
        if text in ("/start", "/menu", "Меню", "📋 Меню"):
            await self._send_main(
                chat_id,
                "🧠 FPS Coach Bot | Warzone / BO7 / BF6\n"
                "Premium UI снизу закреплён 👇\n\n"
                "🤝 Тиммейт — живо и по-человечески.\n"
                "📚 Коуч — по пунктам, как учебник, но без занудства.\n\n"
                "Пиши ситуацию одной строкой — разберу и дам план 😈",
            )
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

        if text in ("🧠 ИИ", "ИИ"):
            prof = self._get_profile(chat_id)
            voice = _norm_voice(prof.get("voice", "TEAMMATE"))
            vv = "🤝 Тиммейт" if voice == "TEAMMATE" else "📚 Коуч"
            await self._send_main(
                chat_id,
                f"🧠 ИИ включён | Голос: {vv}\n\n"
                "Пиши как в обычный чат:\n"
                "• что случилось\n"
                "• где умираешь\n"
                "• что хочешь улучшить\n\n"
                "Отвечу живо, без копипасты 😈",
            )
            return

        if text == "🎯 Тренировка":
            await self._send_main(
                chat_id,
                "🎯 Тренировка\n\n"
                "Напиши одной строкой:\n"
                "Игра | input | что болит (аим/мувмент/позиционка) | где чаще умираешь\n\n"
                "Сделаю план на 20 минут + метрика прогресса.\n"
                "Юмор: «план без метрики — это мечта, а не тренировка» 😄",
            )
            return

        if text == "🎬 VOD":
            await self._send_main(
                chat_id,
                "🎬 VOD (разбор)\n\n"
                "Пока без загрузки видео.\n"
                "Кинь 3 таймкода текстом (00:12 / 01:40 / 03:05)\n"
                "+ что ты хотел сделать.\n\n"
                "Разберу решения как тиммейт/коуч.",
            )
            return

        # ===== ZOMBIES MAIN ENTRY =====
        if text == "🧟 Zombies":
            # показываем хаб зомби + (если есть пресеты) короткий текст
            if zombies_hub_text:
                await self._send(chat_id, zombies_hub_text(self._get_profile(chat_id)), kb_zombies_hub())
            else:
                await self._send(
                    chat_id,
                    self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR),
                    kb_zombies_hub(),
                )
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
            await self._send_main(
                chat_id,
                "🎯 План тренировки (20 минут)\n"
                "1) 5 мин — разминка (контроль)\n"
                "2) 10 мин — основной фокус (твой слабый элемент)\n"
                "3) 5 мин — закрепление в реальном бою\n\n"
                "Напиши: игра | input | слабое место — сделаю план под тебя 😈",
            )
            return

        if text == "🎬 VOD: Разбор":
            await self._send_main(chat_id, "🎬 Кидай 3 таймкода + что хотел сделать. Разберу.")
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
            await self._send_main(
                chat_id,
                f"✅ Роль = {role}\n"
                "Теперь открой 🧩 Настройки игры — там будут цифры и детали 😈",
            )
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
                await self._send(chat_id, zombies_map_perks_text(m), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "🔫 Оружие":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_loadout_text:
                await self._send(chat_id, zombies_map_loadout_text(m), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "🥚 Пасхалки":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_easter_eggs_text:
                await self._send(chat_id, zombies_map_easter_eggs_text(m), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "🧠 Стратегия раундов":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_round_strategy_text:
                await self._send(chat_id, zombies_map_round_strategy_text(m), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        if text == "⚡ Быстрые советы":
            prof = self._get_profile(chat_id)
            m = prof.get("zombies_map", "Ashes")
            if zombies_map_quick_tips_text:
                await self._send(chat_id, zombies_map_quick_tips_text(m), kb_zombies_map_menu(m))
            else:
                await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
            return

        # map menu buttons (per-map)
        # Examples:
        # "🧟 Ashes: Обзор", "🧟 Astra: Перки", etc.
        if text.startswith("🧟 ") and ":" in text:
            left, right = text.split(":", 1)
            map_name = left.replace("🧟", "").strip()
            action = right.strip().lower()

            self._set_profile_field(chat_id, "zombies_map", map_name)

            if "обзор" in action:
                if zombies_map_overview_text:
                    await self._send(chat_id, zombies_map_overview_text(map_name), kb_zombies_map_menu(map_name))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if "перки" in action:
                if zombies_map_perks_text:
                    await self._send(chat_id, zombies_map_perks_text(map_name), kb_zombies_map_menu(map_name))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if "оружие" in action:
                if zombies_map_loadout_text:
                    await self._send(chat_id, zombies_map_loadout_text(map_name), kb_zombies_map_menu(map_name))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if "пасх" in action:
                if zombies_map_easter_eggs_text:
                    await self._send(chat_id, zombies_map_easter_eggs_text(map_name), kb_zombies_map_menu(map_name))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if "стратег" in action:
                if zombies_map_round_strategy_text:
                    await self._send(chat_id, zombies_map_round_strategy_text(map_name), kb_zombies_map_menu(map_name))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

            if "быстр" in action or "совет" in action:
                if zombies_map_quick_tips_text:
                    await self._send(chat_id, zombies_map_quick_tips_text(map_name), kb_zombies_map_menu(map_name))
                else:
                    await self._send(chat_id, self._missing_presets_msg("zombies", _ZOMBIES_IMPORT_ERR), kb_zombies_hub())
                return

        # =========================
        # MENU ITEMS (MUST MATCH quickbar.py)
        # Warzone/BO7 = RU
        # BF6 settings menu = EN (ONLY BF6 settings are EN)
        # =========================

        # --- Warzone ---
        if text == "🎭 Warzone: Роль":
            self._set_profile_field(chat_id, "game", "Warzone")
            await self._send(chat_id, "🎭 Warzone: выбери роль:", kb_roles())
            return

        if text == "🎯 Warzone: Aim/Sens":
            if wz_aim_sens_text:
                await self._send_main(chat_id, wz_aim_sens_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "🎮 Warzone: Controller":
            if wz_controller_tuning_text:
                await self._send_main(chat_id, wz_controller_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "⌨️ Warzone: KBM":
            if wz_kbm_tuning_text:
                await self._send_main(chat_id, wz_kbm_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "🧠 Warzone: Мувмент/Позиционка":
            if wz_movement_positioning_text:
                await self._send_main(chat_id, wz_movement_positioning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        if text == "🎧 Warzone: Аудио/Видео":
            if wz_audio_visual_text:
                await self._send_main(chat_id, wz_audio_visual_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("warzone", _WARZONE_IMPORT_ERR))
            return

        # --- BO7 ---
        if text == "🎭 BO7: Роль":
            self._set_profile_field(chat_id, "game", "BO7")
            await self._send(chat_id, "🎭 BO7: выбери роль:", kb_roles())
            return

        if text == "🎯 BO7: Aim/Sens":
            if bo7_aim_sens_text:
                await self._send_main(chat_id, bo7_aim_sens_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "🎮 BO7: Controller":
            if bo7_controller_tuning_text:
                await self._send_main(chat_id, bo7_controller_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "⌨️ BO7: KBM":
            if bo7_kbm_tuning_text:
                await self._send_main(chat_id, bo7_kbm_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "🧠 BO7: Мувмент/Позиционка":
            if bo7_movement_positioning_text:
                await self._send_main(chat_id, bo7_movement_positioning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        if text == "🎧 BO7: Аудио/Видео":
            if bo7_audio_visual_text:
                await self._send_main(chat_id, bo7_audio_visual_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, self._missing_presets_msg("bo7", _BO7_IMPORT_ERR))
            return

        # --- BF6 (EN settings menu ONLY) ---
        if text == "🪖 BF6: Class Settings":
            self._set_profile_field(chat_id, "game", "BF6")
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
            return

        if text == "🎯 BF6: Aim/Sens":
            self._set_profile_field(chat_id, "game", "BF6")
            await self._send_main(chat_id, bf6_aim_sens_text(self._get_profile(chat_id)))
            return

        if text == "🎮 BF6: Controller Tuning":
            self._set_profile_field(chat_id, "game", "BF6")
            await self._send_main(chat_id, bf6_controller_tuning_text(self._get_profile(chat_id)))
            return

        if text == "⌨️ BF6: KBM Tuning":
            self._set_profile_field(chat_id, "game", "BF6")
            await self._send_main(chat_id, bf6_kbm_tuning_text(self._get_profile(chat_id)))
            return

        # =========================
        # DEFAULT -> AI CHAT (REAL)
        # =========================
        await self._chat_to_brain(chat_id, text)

    # ---------------- messaging helpers ----------------
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, kb_main())

    # ---------------- presets missing helper ----------------
    def _missing_presets_msg(self, world: str, err: Exception | None) -> str:
        base = (
            f"❗️Не вижу пресеты для {world}.\n"
            "Проверь путь файла:\n"
        )
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
            "🎮 Текущее:\n"
            f"• Game: {prof.get('game')}\n"
            f"• Platform: {prof.get('platform')}\n"
            f"• Input: {prof.get('input')}\n"
            f"• Brain Mode: {prof.get('difficulty')}\n"
            f"• Voice: {voice}\n"
            f"• Role: {prof.get('role')}\n"
            f"• BF6 Class: {prof.get('bf6_class')}\n"
            f"• Zombies Map: {prof.get('zombies_map')}\n\n"
            "😄 Юмор: если всё выставил, но всё равно умираешь — значит пора не цифры менять, а решения.",
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
        await self._send_main(chat_id, "📌 Профиль:\n" + "\n".join(lines))

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
                    "📚 Коуч (fallback):\n"
                    "1) Диагноз: мало вводных\n"
                    "2) Сейчас: напиши где умираешь (угол/ротация/трекинг/паника)\n"
                    "3) Дальше: игра | input | дистанции файтов — соберу план\n\n"
                    "AI включим через ENV (📊 Статус)."
                )
            else:
                reply = (
                    "🤝 Тиммейт (fallback):\n"
                    "Ок. Скажи быстро:\n"
                    "• игра\n"
                    "• input\n"
                    "• где умираешь (узко/переоткрываюсь/не тяну трекинг)\n\n"
                    "И я дам план. А AI включим через ENV (📊 Статус)."
                )

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
