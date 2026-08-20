# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from app.services.operator_intelligence import MissionConflict, OperatorIntelligenceService
from app.ui.command_console import (
    CALLBACK_PREFIX,
    ConsoleView,
    ai_view,
    brain_view,
    home_view,
    premium_unlink_confirm_view,
    premium_view,
    system_view,
    training_view,
    vod_view,
    world_view,
    zombies_view,
)
from app.ui.crown_voice_console import crown_voice_view, inject_home_voice_button
from app.ui.operator_console import operator_view
from app.ui.quickbar import _webapp_url

log = logging.getLogger("bco.command_console")
_OPEN_COMMANDS={"/start","/menu","/deck","/console","/operator","/mission","Меню","📋 Меню","🧠 COMMAND DECK","🛰 COMMAND CONSOLE"}
def _message(raw):
    v=raw.get("message") or raw.get("edited_message") or {};return v if isinstance(v,Mapping) else {}
def _callback(raw):
    v=raw.get("callback_query") or {};return v if isinstance(v,Mapping) else {}
def _chat(message):
    v=message.get("chat") or {};return v if isinstance(v,Mapping) else {}
def _sender(container):
    v=container.get("from") or {};return v if isinstance(v,Mapping) else {}
def _int(value):
    try:return int(value)
    except Exception:return None
def _private_identity(message,sender):
    chat=_chat(message);chat_id=_int(chat.get("id"));user_id=_int(sender.get("id"));chat_type=str(chat.get("type") or "").strip().lower()
    if chat_type!="private" or chat_id is None or user_id is None or chat_id!=user_id:return None,None,chat_type
    return chat_id,user_id,chat_type
@dataclass
class CommandConsoleController:
    tg:Any;profiles:Any;store:Any;entitlements:Any;settings:Any
    @property
    def enabled(self):return bool(getattr(self.settings,"telegram_aaa_console_enabled",True))
    def _operator_service(self):return OperatorIntelligenceService(store=self.store,profiles=self.profiles,operator_enabled=bool(getattr(self.settings,"operator_intelligence_enabled",True)),missions_enabled=bool(getattr(self.settings,"adaptive_mission_control_enabled",True)))
    async def configure_bot_surface(self):
        if not self.enabled:return
        commands=[{"command":"menu","description":"Открыть COMMAND CONSOLE"},{"command":"operator","description":"OPERATOR TWIN и текущая миссия"},{"command":"premium","description":"Проверить Premium и связку аккаунта"},{"command":"voice","description":"Настроить голосовой режим"},{"command":"vod","description":"Открыть VOD-разбор"},{"command":"status","description":"Проверить состояние системы"}]
        try:await self.tg.set_my_commands(commands)
        except Exception as exc:log.warning("setMyCommands failed error=%s",type(exc).__name__)
        url=_webapp_url()
        if url:
            try:await self.tg.set_default_menu_button("COMMAND CENTER",url)
            except Exception as exc:log.warning("setChatMenuButton failed error=%s",type(exc).__name__)
    def _profile(self,chat_id):
        try:return dict(self.profiles.get(chat_id) or {})
        except Exception:return {}
    async def _patch(self,chat_id,patch):
        try:await asyncio.to_thread(self.profiles.patch,chat_id,dict(patch))
        except Exception as exc:log.warning("console profile patch failed error=%s",type(exc).__name__)
    async def _stats(self,chat_id):
        fn=getattr(self.store,"stats",None)
        if not callable(fn):return {}
        try:
            r=await asyncio.to_thread(fn,chat_id);return dict(r or {}) if isinstance(r,Mapping) else {}
        except Exception:return {}
    async def _operator_snapshot(self,chat_id):
        try:return await asyncio.to_thread(self._operator_service().snapshot,chat_id)
        except Exception as exc:
            log.warning("operator twin snapshot failed error=%s",type(exc).__name__);return{"operator":{"readiness":"UNAVAILABLE","risk":"UNKNOWN","confidence":"UNKNOWN","session_momentum":"UNKNOWN"},"mission":{"title":"OPERATOR INTELLIGENCE UNAVAILABLE","status":"candidate","basis":"Transient runtime failure."},"session":{"phase":"PRE_SESSION"}}
    async def _premium_status(self,user_id):
        try:return await self.entitlements.get_status(user_id),""
        except Exception as exc:log.warning("console Premium status failed error=%s",type(exc).__name__);return None,type(exc).__name__
    async def _show(self,chat_id,view,message_id=None):
        if message_id is None:await self.tg.send_message(chat_id,view.text,view.reply_markup);return
        try:await self.tg.edit_message(chat_id,message_id,view.text,view.reply_markup)
        except Exception as exc:log.warning("console edit failed error=%s; sending replacement",type(exc).__name__);await self.tg.send_message(chat_id,view.text,view.reply_markup)
    async def _view_for(self,action,chat_id,user_id):
        profile=self._profile(chat_id)
        if action=="home":return inject_home_voice_button(home_view(profile),profile)
        if action=="world":return world_view(profile)
        if action=="brain":return brain_view(profile)
        if action=="voice":return crown_voice_view(profile)
        if action in{"profile","operator","mission"}:return operator_view(await self._operator_snapshot(chat_id))
        if action=="system":return system_view(profile,await self._stats(chat_id))
        if action=="ai":return ai_view(profile)
        if action=="training":return training_view(profile)
        if action=="vod":return vod_view(profile)
        if action=="zombies":return zombies_view(profile)
        if action=="premium":
            status,error=await self._premium_status(user_id);return premium_view(status,error=error,profile=profile)
        return inject_home_voice_button(home_view(profile),profile)
    async def _open_from_message(self,message):
        sender=_sender(message);chat_id,user_id,_=_private_identity(message,sender)
        if chat_id is None or user_id is None:return False
        try:await self.tg.remove_reply_keyboard(chat_id)
        except Exception as exc:log.warning("reply keyboard removal failed error=%s",type(exc).__name__)
        text=str(message.get("text") or "").strip();view=await self._view_for("operator" if text in{"/operator","/mission"} else "home",chat_id,user_id);await self._show(chat_id,view);return True
    async def _handle_set(self,data,chat_id,user_id,message_id):
        parts=data.split(":")
        if len(parts)!=4 or parts[0]!="bco" or parts[1]!="set":return False
        field,value=parts[2],parts[3]
        if field=="game":mapped={"wz":"Warzone","bo7":"BO7","bf6":"BF6"}.get(value);patch={"game":mapped} if mapped else None;return_view="world"
        elif field=="platform":mapped={"pc":"PC","ps":"PlayStation","xbox":"Xbox"}.get(value);patch={"platform":mapped} if mapped else None;return_view="world"
        elif field=="input":mapped={"controller":"Controller","kbm":"KBM"}.get(value);patch={"input":mapped} if mapped else None;return_view="world"
        elif field=="brain":mapped={"normal":"Normal","pro":"Pro","demon":"Demon"}.get(value);patch={"difficulty":mapped} if mapped else None;return_view="brain"
        elif field=="voice":mapped={"teammate":"TEAMMATE","coach":"COACH"}.get(value);patch={"voice":mapped} if mapped else None;return_view="voice"
        elif field=="voiceid":patch={"female":{"voice_identity":"female","tts_voice":"marin"},"male":{"voice_identity":"male","tts_voice":"cedar"}}.get(value);return_view="voice"
        elif field=="ttsmode":patch={"tts_mode":value} if value in{"auto","on_demand","off"} else None;return_view="voice"
        elif field=="focus":patch={"training_focus":value} if value in{"aim","movement","position"} else None;return_view="training"
        elif field=="zmap":mapped={"ashes":"Ashes","astra":"Astra"}.get(value);patch={"zombies_map":mapped} if mapped else None;return_view="zombies"
        else:return False
        if not patch:return False
        await self._patch(chat_id,patch);await self._show(chat_id,await self._view_for(return_view,chat_id,user_id),message_id);return True
    async def _handle_premium(self,action,chat_id,user_id,username,message_id):
        profile=self._profile(chat_id)
        if action=="unlink":await self._show(chat_id,premium_unlink_confirm_view(),message_id);return
        if action=="confirm":
            note="Identity link удалён."
            try:
                removed=await self.entitlements.unlink(user_id);note="Identity link удалён." if removed else "Активной связки не было."
            except Exception as exc:
                status,error=await self._premium_status(user_id);await self._show(chat_id,premium_view(status,error=error or type(exc).__name__,note="Отвязка временно недоступна.",profile=profile),message_id);return
            status,error=await self._premium_status(user_id);await self._show(chat_id,premium_view(status,error=error,note=note,profile=profile),message_id);return
        if action!="link":await self._show(chat_id,await self._view_for("premium",chat_id,user_id),message_id);return
        if not bool(getattr(self.entitlements,"configured",False)):
            status,error=await self._premium_status(user_id);await self._show(chat_id,premium_view(status,error=error or "not_configured",note="Account Bridge не настроен.",profile=profile),message_id);return
        try:
            challenge=await self.entitlements.create_link_challenge(telegram_user_id=user_id,telegram_chat_id=chat_id,telegram_username=username);status,error=await self._premium_status(user_id);minutes=max(1,int(challenge.ttl_seconds or 60)//60);await self._show(chat_id,premium_view(status,error=error,link_url=str(challenge.url),link_ttl_minutes=minutes,note="Открой BlackCrown и подтверди текущий аккаунт.",profile=profile),message_id)
        except Exception as exc:
            status,error=await self._premium_status(user_id);await self._show(chat_id,premium_view(status,error=error or type(exc).__name__,note="Не удалось создать одноразовую ссылку.",profile=profile),message_id)
    async def _handle_mission(self,data,chat_id,message_id):
        parts=data.split(":");service=self._operator_service()
        try:
            if len(parts)==4 and parts[:3]==["bco","m","accept"]:
                snap=await asyncio.to_thread(service.accept,chat_id,parts[3]);await self._show(chat_id,operator_view(snap,note="Mission accepted. LIVE OBJECTIVE is now active."),message_id);return True
            if len(parts)==5 and parts[:3]==["bco","m","complete"]:
                snap=await asyncio.to_thread(service.complete,chat_id,parts[4],outcome=parts[3],metrics={});await self._show(chat_id,operator_view(snap,note="Post-session result persisted. Operator Twin recalibrated."),message_id);return True
        except Exception:
            snap=await self._operator_snapshot(chat_id);await self._show(chat_id,operator_view(snap,note="Mission action temporarily unavailable."),message_id);return True
        return False
    async def _handle_callback(self,callback):
        data=str(callback.get("data") or "").strip()
        if not data.startswith(CALLBACK_PREFIX):return False
        callback_id=str(callback.get("id") or "").strip();message=callback.get("message") or {};message=message if isinstance(message,Mapping) else {};sender=_sender(callback);chat_id,user_id,_=_private_identity(message,sender);message_id=_int(message.get("message_id"));username=str(sender.get("username") or "") or None
        try:
            if callback_id:await self.tg.answer_callback_query(callback_id)
        except Exception:pass
        if chat_id is None or user_id is None or message_id is None:return True
        if data=="bco:close":
            try:await self.tg.delete_message(chat_id,message_id)
            except Exception:pass
            return True
        if data.startswith("bco:set:"):return await self._handle_set(data,chat_id,user_id,message_id)
        if data.startswith("bco:premium:"):
            action=data.removeprefix("bco:premium:");action="confirm" if action=="unlink:confirm" else action;await self._handle_premium(action,chat_id,user_id,username,message_id);return True
        if data.startswith("bco:m:"):return await self._handle_mission(data,chat_id,message_id)
        action=data.removeprefix("bco:") or "home";await self._show(chat_id,await self._view_for(action,chat_id,user_id),message_id);return True
    async def maybe_handle(self,raw):
        if not self.enabled or not isinstance(raw,Mapping):return False
        callback=_callback(raw);adapted=raw
        if callback:
            data=str(callback.get("data") or "").strip()
            if data.startswith(CALLBACK_PREFIX):
                message=callback.get("message") or {};message=message if isinstance(message,Mapping) else {};sender=_sender(callback);chat_id,user_id,_=_private_identity(message,sender)
                if chat_id is None or user_id is None:
                    callback_id=str(callback.get("id") or "").strip()
                    if callback_id:
                        try:await self.tg.answer_callback_query(callback_id,"COMMAND CONSOLE доступна в личном чате с ботом.",show_alert=True)
                        except Exception:pass
                    return True
                if data.startswith("bco:p:"):
                    adapted_raw=dict(raw);adapted_callback=dict(callback);adapted_callback["data"]="bco:premium:"+data.removeprefix("bco:p:");adapted_raw["callback_query"]=adapted_callback;adapted=adapted_raw
        return await self.handle_update(adapted)
    async def handle_update(self,raw):
        if not self.enabled or not isinstance(raw,Mapping):return False
        cb=_callback(raw)
        if cb:return await self._handle_callback(cb)
        msg=_message(raw);text=str(msg.get("text") or "").strip()
        if text not in _OPEN_COMMANDS:return False
        return await self._open_from_message(msg)
