# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.ui.native_buttons import decorate_reply_markup
from app.ui.presentation import tactical_card
from app.ui.quickbar import _webapp_url

CALLBACK_PREFIX = "bco:"

@dataclass(frozen=True)
class ConsoleView:
    text: str
    reply_markup: dict[str, Any]

def _clean(value: Any, fallback: str, limit: int = 32) -> str:
    text = " ".join(str(value or "").split()).strip()
    return (text or fallback)[:limit]

def _profile(profile: Mapping[str, Any] | None) -> dict[str, str]:
    source = dict(profile or {})
    return {
        "profile_name": _clean(source.get("profile_name"), "Оператор"),
        "game": _clean(source.get("game"), "Warzone"),
        "platform": _clean(source.get("platform"), "PC"),
        "input": _clean(source.get("input"), "Controller"),
        "difficulty": _clean(source.get("difficulty"), "Normal"),
        "voice": _clean(source.get("voice"), "TEAMMATE"),
        "role": _clean(source.get("role"), "Flex"),
        "bf6_class": _clean(source.get("bf6_class"), "Assault"),
        "zombies_map": _clean(source.get("zombies_map"), "Ashes"),
        "training_focus": _clean(source.get("training_focus"), "aim"),
    }

def _callback(text: str, data: str, style: str | None = None) -> dict[str, Any]:
    button={"text":text[:64],"callback_data":data[:64]}
    if style: button["style"]=style
    return button

def _url(text: str, url: str, style: str | None = None) -> dict[str, Any]:
    button={"text":text[:64],"url":url}
    if style: button["style"]=style
    return button

def _webapp_button():
    url=_webapp_url()
    if not url:return None
    return {"text":"🛰 КОМАНДНЫЙ ЦЕНТР","web_app":{"url":url},"style":"primary"}

def _markup(rows):
    cleaned=[row for row in rows if row];raw={"inline_keyboard":cleaned};return decorate_reply_markup(raw) or raw

def _view(channel,body,rows):return ConsoleView(text=tactical_card(body,channel=channel),reply_markup=_markup(rows))
def _active(label,active,data,*,danger=False):return _callback(("✓ " if active else "")+label,data,"danger" if active and danger else "success" if active else "danger" if danger else "primary")
def _footer(*,include_webapp=True):
    rows=[];webapp=_webapp_button() if include_webapp else None
    if webapp:rows.append([webapp])
    rows.append([_callback("↻ ОБНОВИТЬ","bco:home","primary"),_callback("✕ ЗАКРЫТЬ","bco:close")]);return rows

def home_view(profile):
    p=_profile(profile);body=(f"ОПЕРАТОР // {p['profile_name'].upper()}\nСВЯЗЬ // В СЕТИ\n\nТЕКУЩИЙ КОНТЕКСТ:\n• МИР — {p['game'].upper()}\n• ПЛАТФОРМА — {p['platform'].upper()} · {p['input'].upper()}\n• ЯДРО — {p['difficulty'].upper()} · {p['voice'].upper()}\n• РОЛЬ — {p['role'].upper()}\n\nВыбери модуль. Бот и Mini App используют один профиль оператора.")
    rows=[[_callback("🧠 CROWN ИИ","bco:ai","primary"),_callback("🎯 ТРЕНИРОВКА","bco:training","success")],[_callback("🎮 ИГРОВОЙ МИР","bco:world","primary"),_callback("🎬 VOD ЛАБ","bco:vod","success")],[_callback("🧟 ZOMBIES","bco:zombies","danger"),_callback("📌 ОПЕРАТОР","bco:profile","primary")],[_callback("💎 PREMIUM","bco:premium","success"),_callback("⚙️ СИСТЕМА","bco:system")]];rows.extend(_footer());return _view("КОМАНДНАЯ КОНСОЛЬ",body,rows)

def world_view(profile):
    p=_profile(profile);game=p['game'].casefold();platform=p['platform'].casefold();inp=p['input'].casefold();body=f"ИГРОВОЕ ОКРУЖЕНИЕ\n\nАктивный мир: {p['game']}\nПлатформа: {p['platform']}\nУправление: {p['input']}\n\nИзменение применяется к ИИ, тренировкам, VOD и памяти игрока."
    rows=[[_active("WARZONE","warzone" in game,"bco:set:game:wz"),_active("BO7","bo7" in game,"bco:set:game:bo7"),_active("BF6","bf6" in game,"bco:set:game:bf6")],[_active("PC",platform=="pc","bco:set:platform:pc"),_active("PS","play" in platform,"bco:set:platform:ps"),_active("XBOX","xbox" in platform,"bco:set:platform:xbox")],[_active("CONTROLLER","controller" in inp,"bco:set:input:controller"),_active("KBM","kbm" in inp,"bco:set:input:kbm")],[_callback("‹ КОНСОЛЬ","bco:home")]];return _view("ИГРОВОЙ МИР",body,rows)

def brain_view(profile):
    p=_profile(profile);mode=p['difficulty'].casefold();body=f"РЕЖИМ МЫШЛЕНИЯ\n\nАктивно: {p['difficulty']}\n\nNORMAL — стабильный анализ.\nPRO — плотнее и требовательнее.\nDEMON — максимум плотности и прямоты."
    rows=[[_active("NORMAL",mode=="normal","bco:set:brain:normal"),_active("PRO",mode=="pro","bco:set:brain:pro"),_active("DEMON",mode=="demon","bco:set:brain:demon",danger=True)],[_callback("‹ КОНСОЛЬ","bco:home")]];return _view("ЯДРО CROWN",body,rows)

def ai_view(profile):
    p=_profile(profile);body=f"CROWN ИИ\n\nОператор: {p['profile_name']}\nРежим: {p['voice']} · {p['difficulty']}\nМир: {p['game']} · {p['input']}\n\nНапиши ситуацию обычным сообщением. CROWN использует этот же профиль и память."
    rows=[[_callback("🎙 ГОЛОС CROWN","bco:voice","primary"),_callback("🧠 РЕЖИМ ЯДРА","bco:brain")],[_callback("‹ КОНСОЛЬ","bco:home")]];return _view("CROWN ИИ",body,rows)

def training_view(profile):
    p=_profile(profile);focus=p['training_focus'].casefold();body=f"ПЕРСОНАЛЬНАЯ ТРЕНИРОВКА\n\nОператор: {p['profile_name']}\nТекущий фокус: {p['training_focus']}\nМир: {p['game']} · {p['input']}\n\nMini App строит Personal Protocol из Operator Twin и текущей миссии. Здесь можно изменить ручной фокус."
    rows=[[_active("AIM",focus=="aim","bco:set:training:aim"),_active("МУВМЕНТ",focus=="movement","bco:set:training:movement"),_active("ПОЗИЦИЯ",focus in {"position","positioning"},"bco:set:training:position")],[_callback("‹ КОНСОЛЬ","bco:home")]];return _view("ТРЕНИРОВКА",body,rows)

def vod_view(profile):
    p=_profile(profile);body=f"VOD ЛАБ\n\nОператор: {p['profile_name']}\nМир: {p['game']} · {p['input']}\n\nОтправь клип/видео в чат или открой Mini App для Engagement Review и After Action.";rows=[[_callback("‹ КОНСОЛЬ","bco:home")]];rows.extend(_footer());return _view("VOD ЛАБ",body,rows)

def zombies_view(profile):
    p=_profile(profile);body=f"ZOMBIES\n\nКарта: {p['zombies_map']}\nОператор: {p['profile_name']}\n\nОткрой HQ или измени карту в Mini App.";rows=[[_callback("‹ КОНСОЛЬ","bco:home")]];rows.extend(_footer());return _view("ZOMBIES",body,rows)

def system_view(profile,stats=None):
    p=_profile(profile);body=f"СИСТЕМА\n\nОператор: {p['profile_name']}\nПрофиль: СИНХРОНИЗИРОВАН\nМир: {p['game']}\nЯдро: {p['difficulty']}\nГолос: {p['voice']}\n\nCanonical identity и Premium остаются серверными.";rows=[[_callback("🎙 ГОЛОС","bco:voice","primary"),_callback("🧠 ЯДРО","bco:brain")],[_callback("‹ КОНСОЛЬ","bco:home")]];return _view("СИСТЕМА",body,rows)

def premium_view(status,profile=None):
    linked=bool(getattr(status,"linked",False)) if status is not None else False;premium=bool(getattr(status,"premium",False)) if status is not None else False;name=_profile(profile).get('profile_name','Оператор');body=f"АККАУНТ И PREMIUM\n\nОператор: {name}\nСвязка аккаунта: {'АКТИВНА' if linked else 'НЕ ПРИВЯЗАНА'}\nPremium: {'АКТИВЕН' if premium else 'СТАНДАРТ'}\n\nСайт остаётся центром аккаунта; Telegram и Mini App используют ту же identity.";rows=[[_callback("‹ КОНСОЛЬ","bco:home")]];return _view("PREMIUM",body,rows)
def premium_unlink_confirm_view():return _view("PREMIUM","Подтвердить отключение Telegram от аккаунта?",[[_callback("ОТМЕНА","bco:premium"),_callback("ОТКЛЮЧИТЬ","bco:premium:unlink:confirm","danger")]])
