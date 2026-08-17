# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass
class AdminUsageAnalytics:
    store: Any
    def _primary(self): return getattr(self.store,"primary",self.store)
    def record(self,*,user_id:int,chat_id:int,language:str,surface:str,is_message:bool=False,is_voice:bool=False,is_miniapp:bool=False)->None:
        primary=self._primary(); request=getattr(primary,"_request",None)
        if callable(request): request("POST","rpc/bco_record_user_activity",json={"p_user_id":int(user_id),"p_chat_id":int(chat_id),"p_language":str(language or "")[:16],"p_surface":str(surface or "telegram")[:32],"p_is_message":bool(is_message),"p_is_voice":bool(is_voice),"p_is_miniapp":bool(is_miniapp)},extra_headers={"Prefer":"return=minimal"})
    def summary(self)->dict[str,int]:
        primary=self._primary(); request=getattr(primary,"_request",None); rows_fn=getattr(primary,"_rows",None)
        if callable(request) and callable(rows_fn):
            rows=rows_fn(request("POST","rpc/bco_admin_usage_summary",json={})); raw=dict(rows[0]) if rows else {}; return {str(k):int(v or 0) for k,v in raw.items()}
        return {}
    @staticmethod
    def render(summary:Mapping[str,Any],locale:str="ru")->str:
        s={str(k):int(v or 0) for k,v in dict(summary or {}).items()}
        if locale=="en": return ("BLACK CROWN OPS // ADMIN REPORT\n\n"f"TOTAL TRACKED USERS — {s.get('total_users',0)}\n"f"ACTIVE 24H — {s.get('active_24h',0)}\n"f"ACTIVE 7D — {s.get('active_7d',0)}\n"f"ACTIVE 30D — {s.get('active_30d',0)}\n"f"NEW 24H — {s.get('new_24h',0)}\n"f"NEW 7D — {s.get('new_7d',0)}\n\n"f"UPDATES — {s.get('total_updates',0)}\n"f"MESSAGES — {s.get('total_messages',0)}\n"f"VOICE — {s.get('total_voice',0)}\n"f"MINI APP — {s.get('total_miniapp',0)}\n\nAuthority: server-side Supabase activity ledger. Telegram header member counts are not bot MAU/DAU analytics.")
        return ("BLACK CROWN OPS // ОТЧЁТ АДМИНА\n\n"f"ВСЕ ОТСЛЕЖИВАЕМЫЕ ПОЛЬЗОВАТЕЛИ — {s.get('total_users',0)}\n"f"АКТИВНЫЕ 24Ч — {s.get('active_24h',0)}\n"f"АКТИВНЫЕ 7Д — {s.get('active_7d',0)}\n"f"АКТИВНЫЕ 30Д — {s.get('active_30d',0)}\n"f"НОВЫЕ 24Ч — {s.get('new_24h',0)}\n"f"НОВЫЕ 7Д — {s.get('new_7d',0)}\n\n"f"UPDATES — {s.get('total_updates',0)}\n"f"СООБЩЕНИЯ — {s.get('total_messages',0)}\n"f"VOICE — {s.get('total_voice',0)}\n"f"MINI APP — {s.get('total_miniapp',0)}\n\nИсточник: серверный activity ledger в Supabase. Число участников в шапке Telegram не является DAU/MAU бота.")
