# app/services/brain/engine.py
from __future__ import annotations

from typing import Any, Dict, List


class BrainEngine:
    """
    Локальный brain: без API-ключей, но умный коуч-тиммейт.
    Стиль ответа зависит от difficulty (Normal/Pro/Demon) + role.
    BF6: если просят "settings", выдаём EN-блок.
    """

    def __init__(self, store: Any, profiles: Any, settings: Any):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    def reply(self, text: str, profile: Dict[str, Any] | None = None, history: List[Dict[str, str]] | None = None) -> str:
        profile = profile or {}
        history = history or []

        t = (text or "").strip()
        if not t:
            return "Напиши ситуацию одной строкой: игра | input | роль | что болит (аим/мувмент/позиционка) — соберу план."

        game = (profile.get("game") or "Warzone").strip()
        platform = (profile.get("platform") or "PC").strip()
        input_ = (profile.get("input") or "Controller").strip()
        diff = (profile.get("difficulty") or "Normal").strip()
        role = (profile.get("role") or "Flex").strip()

        low = t.lower()

        # быстрые команды текстом
        if "настрой" in low or "sens" in low or "settings" in low or "сеттинг" in low:
            return self._settings_answer(game=game, platform=platform, input_=input_, diff=diff)

        if "план" in low or "трен" in low or "drill" in low or "размин" in low:
            return self._training_plan(game=game, input_=input_, diff=diff, role=role)

        # основная коуч-логика
        problem = self._classify_problem(low)
        return self._coach(game=game, platform=platform, input_=input_, diff=diff, role=role, problem=problem, raw=t)

    def _tone(self, diff: str) -> Dict[str, str]:
        d = (diff or "").lower()
        if "demon" in d:
            return {"head": "😈 DEMON COACH", "style": "жёстко, по делу, без воды"}
        if "pro" in d:
            return {"head": "🔥 PRO COACH", "style": "строго, системно, как скримы"}
        return {"head": "🧠 COACH", "style": "спокойно, понятно, шаг за шагом"}

    def _classify_problem(self, low: str) -> str:
        if any(k in low for k in ["aim", "аим", "мажу", "не попада", "трек", "контроль отдачи"]):
            return "aim"
        if any(k in low for k in ["move", "мув", "слайд", "страйф", "пози", "прыж", "пики", "угол"]):
            return "movement"
        if any(k in low for k in ["ротац", "рота", "зона", "позицион", "почему умер", "где стоять", "тайминг"]):
            return "positioning"
        return "mixed"

    def _settings_answer(self, game: str, platform: str, input_: str, diff: str) -> str:
        tone = self._tone(diff)
        is_bf6 = game.upper() == "BF6"

        # BF6 settings только EN (как ты хотел)
        if is_bf6:
            return (
                f"{tone['head']} | BF6 SETTINGS (EN)\n"
                f"Platform: {platform} | Input: {input_}\n\n"
                "Core:\n"
                "• Aim Assist: ON (Controller)\n"
                "• FOV: 100–110 (Controller) / 105–115 (KBM)\n"
                "• ADS FOV: Affected\n"
                "• Deadzones: as low as stable (no drift)\n"
                "• Sens: start 6–8 (Controller) / 800 DPI + 0.35–0.55 (KBM)\n\n"
                "Tell me: your current sens + where you lose fights (close/mid/long) — I’ll dial it in."
            )

        # Warzone/BO7 RU
        return (
            f"{tone['head']} | НАСТРОЙКИ (RU)\n"
            f"Игра: {game} | Платформа: {platform} | Input: {input_}\n\n"
            "База (универсально):\n"
            "• FOV: 105–110\n"
            "• ADS FOV: Affected\n"
            "• Motion Blur: OFF\n"
            "• Film Grain: 0\n"
            "• Audio: Boost High / Home Theater (что чище шаги)\n\n"
            "Controller:\n"
            "• Aim Assist: ON\n"
            "• Response Curve: Dynamic\n"
            "• Deadzone: минимальная без дрифта\n\n"
            "KBM:\n"
            "• DPI: 800 (или 1600) + sens под контроль\n"
            "• Raw input: ON\n\n"
            "Скинь: твой sens + ADS + FOV + deadzone — подгоню «демонически»."
        )

    def _training_plan(self, game: str, input_: str, diff: str, role: str) -> str:
        tone = self._tone(diff)
        return (
            f"{tone['head']} | ТРЕНИРОВКА\n"
            f"Игра: {game} | Input: {input_} | Роль: {role}\n\n"
            "15 минут (каждый день):\n"
            "1) Разогрев (3 мин): 1v0 контроль + префайр углов\n"
            "2) Aim (6 мин): трекинг → флик → микрокоррекция\n"
            "3) Movement (4 мин): пик-стрейф + ресет + выход из угла\n"
            "4) Decision (2 мин): «стреляю только когда есть выход»\n\n"
            "Напиши: где чаще умираешь (close/mid/long) — сделаю персональный план."
        )

    def _coach(self, game: str, platform: str, input_: str, diff: str, role: str, problem: str, raw: str) -> str:
        tone = self._tone(diff)

        # короткий “тиммейт”-разбор
        base = (
            f"{tone['head']} | {tone['style']}\n"
            f"Игра: {game} | Платформа: {platform} | Input: {input_} | Роль: {role}\n\n"
        )

        if problem == "aim":
            return base + (
                "Скорее всего это не «аим слабый», а:\n"
                "• ты начинаешь стрелять ДО того как стабилизировал прицел\n"
                "• или теряешь контроль при микро-стрейфе\n\n"
                "СЕЙЧАС (в следующей игре):\n"
                "1) Первый выстрел только после микро-паузы 0.1с (контроль)\n"
                "2) Стреляй очередями на средних, не жми в пол\n"
                "3) Не трекай телом — трекай прицелом + лёгкий стрейф\n\n"
                "ДАЛЬШЕ (10 минут):\n"
                "• 3×2 мин трекинг + 3×1 мин флик по углам\n\n"
                f"Твой кейс: «{raw}» — скажи дистанцию фейлов (close/mid/long)."
            )

        if problem == "movement":
            return base + (
                "Ты умираешь потому что даёшь врагу лёгкий трек.\n\n"
                "СЕЙЧАС:\n"
                "1) Пик только с планом выхода (2-й угол/укрытие)\n"
                "2) После урона — ресет (не репик сразу)\n"
                "3) Не прыгай «вникуда» — прыгай в укрытие\n\n"
                "ДАЛЬШЕ:\n"
                "• 10 повторов: пик → 6 пуль → откат → смена угла\n\n"
                f"Кинь: где именно умираешь (угол/лестница/дверь/опен)."
            )

        if problem == "positioning":
            return base + (
                "Позиционка = тайминг + выходы.\n\n"
                "СЕЙЧАС:\n"
                "1) Правило 2 выходов: если нет — ты уже в минусе\n"
                "2) Не стой в узком дольше 3–5 секунд\n"
                "3) Ротация раньше, а не «когда уже поздно»\n\n"
                "ДАЛЬШЕ:\n"
                "• Перед боем: «куда откат если 2 врага?» — ответ должен быть мгновенный\n\n"
                f"Напиши: зона/точка/как тебя зажали — соберу конкретный маршрут."
            )

        return base + (
            "Дай мне вводные одной строкой, и я сделаю точный план:\n"
            "Игра | режим | input | роль | от чего умер | на какой дистанции\n\n"
            f"Сейчас вижу: «{raw}» — уточни дистанцию и кто тебя убил (1v1 / 1v2 / 3rd party)."
        )
