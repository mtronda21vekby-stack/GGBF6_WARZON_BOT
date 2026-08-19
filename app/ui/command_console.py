# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from app.ui.native_buttons import decorate_reply_markup
from app.ui.presentation import tactical_card
from app.ui.quickbar import _webapp_url
CALLBACK_PREFIX="bco:"
@dataclass(frozen=True)
class ConsoleView:
    text:str
    reply_markup:dict[str,Any]
def _clean(value:Any,fallback:str,limit:int=32)->str:
    text=" ".join(str(value or "").split()).strip();return(text or fallback)[:limit]
def _profile(profile:Mapping[str,Any]|None)->dict[str,str]:
    s=dict(profile or {});return{"profile_name":_clean(s.get("profile_name"),"Оператор"),"game":_clean(s.get("game"),"Warzone"),"platform":_clean(s.get("platform"),"PC"),"input":_clean(s.get("input"),"Controller"),"difficulty":_clean(s.get("difficulty"),"Normal"),"voice":_clean(s.get("voice"),"TEAMMATE"),"role":_clean(s.get("role"),"Flex"),"bf6_class":_clean(s.get("bf6_class"),"Assault"),"zombies_map":_clean(s.get("zombies_map"),"Ashes"),"training_focus":_clean(s.get("training_focus"),"aim")}
def _callback(text,data,style=None):
    b={"text":text[:64],"callback_data":data[:64]};
    if style:b["style"]=style
    return b
def _url(text,url,style=None):
    b={"text":text[:64],"url":url};
    if style:b["style"]=style
    return b
def _webapp_button():
    url=_webapp_url();return None if not url else {"text":"🛰 КОМАНДНЫЙ ЦЕНТР","web_app":{"url":url},"style":"primary"}
def _markup(rows):
    raw={"inline_keyboard":[r for r in rows if r]};return decorate_reply_markup(raw) or raw
def _view(channel,body,rows):return ConsoleView(tactical_card(body,channel=channel),_markup(rows))
def _active(label,active,data,*,danger=False):return _callback(("✓ " if active else "")+label,data,"danger" if active and danger else "success" if active else "danger" if danger else "primary")
def _footer(*,include_webapp=True):
    rows=[];w=_webapp_button() if include_webapp else None
    if w:rows.append([w])
    rows.append([_callback("↻ ОБНОВИТЬ","bco:home","primary"),_callback("✕ ЗАКРЫТЬ","bco:close")]);return rows
def home_view(profile):
    p=_profile(profile);body=f"ОПЕРАТОР // {p['profile_name'].upper()}\nСВЯЗЬ // В СЕТИ\n\nТЕКУЩИЙ КОНТЕКСТ:\n• МИР — {p['game'].upper()}\n• ПЛАТФОРМА — {p['platform'].upper()} · {p['input'].upper()}\n• ЯДРО — {p['difficulty'].upper()} · {p['voice'].upper()}\n• РОЛЬ — {p['role'].upper()}\n\nВыбери модуль. Бот и Mini App используют один профиль оператора.";rows=[[_callback("🧠 CROWN ИИ","bco:ai","primary"),_callback("🎯 ТРЕНИРОВКА","bco:training","success")],[_callback("🎮 ИГРОВОЙ МИР","bco:world","primary"),_callback("🎬 VOD ЛАБ","bco:vod","success")],[_callback("🧟 ZOMBIES","bco:zombies","danger"),_callback("📌 ОПЕРАТОР","bco:profile","primary")],[_callback("💎 PREMIUM","bco:premium","success"),_callback("⚙️ СИСТЕМА","bco:system")]];rows.extend(_footer());return _view("КОМАНДНАЯ КОНСОЛЬ",body,rows)
def world_view(profile):
    p=_profile(profile);g=p['game'].casefold();pl=p['platform'].casefold();i=p['input'].casefold();return _view("ИГРОВОЙ МИР",f"ИГРОВОЕ ОКРУЖЕНИЕ\n\nАктивный мир: {p['game']}\nПлатформа: {p['platform']}\nУправление: {p['input']}\n\nИзменение применяется к ИИ, тренировкам, VOD и памяти игрока.",[[_active("WARZONE","warzone" in g,"bco:set:game:wz"),_active("BO7","bo7" in g,"bco:set:game:bo7"),_active("BF6","bf6" in g,"bco:set:game:bf6")],[_active("PC",pl=="pc","bco:set:platform:pc"),_active("PS","play" in pl,"bco:set:platform:ps"),_active("XBOX","xbox" in pl,"bco:set:platform:xbox")],[_active("CONTROLLER","controller" in i,"bco:set:input:controller"),_active("KBM","kbm" in i,"bco:set:input:kbm")],[_callback("‹ КОНСОЛЬ","bco:home")]])
def brain_view(profile):
    p=_profile(profile);m=p['difficulty'].casefold();return _view("ЯДРО CROWN",f"РЕЖИМ МЫШЛЕНИЯ\n\nАктивно: {p['difficulty']}\n\nNORMAL — стабильный анализ.\nPRO — плотнее и требовательнее.\nDEMON — максимум плотности и прямоты.",[[_active("NORMAL",m=="normal","bco:set:brain:normal"),_active("PRO",m=="pro","bco:set:brain:pro"),_active("DEMON",m=="demon","bco:set:brain:demon",danger=True)],[_callback("‹ КОНСОЛЬ","bco:home")]])
def ai_view(profile):
    p=_profile(profile);return _view("CROWN ИИ",f"CROWN ИИ\n\nОператор: {p['profile_name']}\nРежим: {p['voice']} · {p['difficulty']}\nМир: {p['game']} · {p['input']}\n\nНапиши ситуацию обычным сообщением. CROWN использует этот же профиль и память.",[[_callback("🎙 ГОЛОС CROWN","bco:voice","primary"),_callback("🧠 РЕЖИМ ЯДРА","bco:brain")],[_callback("‹ КОНСОЛЬ","bco:home")]])
def training_view(profile):
    p=_profile(profile);f=p['training_focus'].casefold();return _view("ТРЕНИРОВКА",f"ПЕРСОНАЛЬНАЯ ТРЕНИРОВКА\n\nОператор: {p['profile_name']}\nТекущий фокус: {p['training_focus']}\nМир: {p['game']} · {p['input']}\n\nMini App строит Personal Protocol из Operator Twin и текущей миссии.",[[_active("AIM",f=="aim","bco:set:focus:aim"),_active("МУВМЕНТ",f=="movement","bco:set:focus:movement"),_active("ПОЗИЦИЯ",f in{"position","positioning"},"bco:set:focus:position")],[_callback("‹ КОНСОЛЬ","bco:home")]])
def vod_view(profile):
    p=_profile(profile);rows=[[_callback("‹ КОНСОЛЬ","bco:home")]];rows.extend(_footer());return _view("VOD ЛАБ",f"VOD ЛАБ\n\nОператор: {p['profile_name']}\nМир: {p['game']} · {p['input']}\n\nОтправь клип/видео в чат или открой Mini App для Engagement Review и After Action.",rows)
def zombies_view(profile):
    p=_profile(profile);rows=[[_callback("‹ КОНСОЛЬ","bco:home")]];rows.extend(_footer());return _view("ZOMBIES",f"ZOMBIES\n\nКарта: {p['zombies_map']}\nОператор: {p['profile_name']}\n\nОткрой HQ или измени карту в Mini App.",rows)
def system_view(profile,stats=None):
    p=_profile(profile);return _view("СИСТЕМА",f"СИСТЕМА\n\nОператор: {p['profile_name']}\nПрофиль: СИНХРОНИЗИРОВАН\nМир: {p['game']}\nЯдро: {p['difficulty']}\nГолос: {p['voice']}\n\nCanonical identity и Premium остаются серверными.",[[_callback("🎙 ГОЛОС","bco:voice","primary"),_callback("🧠 ЯДРО","bco:brain")],[_callback("‹ КОНСОЛЬ","bco:home")]])
def premium_view(status,*,error:str="",link_url:str="",link_ttl_minutes:int=0,note:str="",profile:Mapping[str,Any]|None=None):
    p=_profile(profile);linked=bool(getattr(status,"linked",False));premium=bool(getattr(status,"premium",False));site=str(getattr(status,"site_user_id","") or "");linked_at=str(getattr(status,"linked_at","") or "");lines=["АККАУНТ И PREMIUM","",f"Оператор: {p['profile_name']}",f"Сайт ↔ Telegram: {'СВЯЗАНЫ' if linked else 'НЕ СВЯЗАНЫ'}",f"Premium: {'АКТИВЕН' if premium else 'СТАНДАРТ'}"]
    if site:lines.append(f"Website ID: {site[:42]}")
    if linked_at:lines.append(f"Связано: {linked_at[:19]}")
    if note:lines.extend(["",note])
    if error:lines.extend(["",f"Состояние authority: {error[:48]}"])
    rows=[]
    if link_url:rows.append([_url(f"🔗 ПОДТВЕРДИТЬ НА САЙТЕ ({max(1,link_ttl_minutes)} мин)",link_url,"success")])
    elif linked:rows.append([_callback("⛓ ОТВЯЗАТЬ TELEGRAM","bco:premium:unlink","danger")])
    else:rows.append([_callback("🔗 СВЯЗАТЬ С САЙТОМ","bco:premium:link","success")])
    rows.append([_callback("↻ ОБНОВИТЬ","bco:premium","primary"),_callback("‹ КОНСОЛЬ","bco:home")]);return _view("PREMIUM","\n".join(lines),rows)
def premium_unlink_confirm_view():return _view("PREMIUM","Подтвердить отключение Telegram от аккаунта? Premium не удаляется — удаляется только identity link.",[[_callback("ОТМЕНА","bco:premium"),_callback("ОТКЛЮЧИТЬ","bco:premium:unlink:confirm","danger")]])