# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib, inspect, json, logging, os, tempfile, time
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Header, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from app.webapp.security import verify_init_data
from app.services.voice.transcription import build_transcription_prompt

log=logging.getLogger("webapp");router=APIRouter();BASE_DIR=Path(__file__).resolve().parent;STATIC_DIR=(BASE_DIR/"static").resolve();INDEX_FILE=(STATIC_DIR/"index.html").resolve()
_WEBAPP_MAX_BYTES=int(os.getenv("WEBAPP_MAX_BYTES","16000") or "16000");_BUILD_CACHE_VALUE=None;_BUILD_CACHE_AT=0.0;_BUILD_CACHE_TTL_SEC=2.0
APP_BRAIN=APP_PROFILES=APP_STORE=APP_SETTINGS=APP_TRANSCRIPTION=APP_VOICE=None

def _truncate(value,limit):
    try:text=str(value if value is not None else "")
    except Exception:text=""
    return "" if limit<=0 else text if len(text)<=limit else text[:limit-1]+"…"
def _etag_for_bytes(data):return hashlib.sha1(data).hexdigest()[:16]
def _etag_for_file(path):
    try:st=path.stat();return hashlib.sha1(f"{path.name}:{int(st.st_mtime)}:{st.st_size}".encode()).hexdigest()[:16]
    except Exception:return str(int(time.time()))
def _cache_headers(kind,etag=None):
    h={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0","Pragma":"no-cache","Expires":"0"} if kind=="html" else {"Cache-Control":"public, max-age=0, must-revalidate"}
    if etag:h["ETag"]=etag
    return h
def _scan_static_mtime():
    newest=0
    try:
        for path in STATIC_DIR.rglob("*"):
            if path.is_file():newest=max(newest,int(path.stat().st_mtime))
    except Exception:return int(time.time())
    return newest or int(time.time())
def _build_id():
    global _BUILD_CACHE_VALUE,_BUILD_CACHE_AT
    now=time.time()
    if _BUILD_CACHE_VALUE and now-_BUILD_CACHE_AT<_BUILD_CACHE_TTL_SEC:return _BUILD_CACHE_VALUE
    value=(os.getenv("WEBAPP_BUILD_ID") or os.getenv("RENDER_GIT_COMMIT") or "").strip() or str(_scan_static_mtime());_BUILD_CACHE_VALUE=value[:12];_BUILD_CACHE_AT=now;return _BUILD_CACHE_VALUE
def _is_safe_rel_path(path):
    value=(path or "").strip();return not ("\x00" in value or value.startswith(("/","\\")) or "\\" in value) and all(part!=".." for part in value.split("/") if part)
def _render_index_html(request=None):
    if not INDEX_FILE.exists():return HTMLResponse("<h3>Mini App is not configured</h3>",status_code=503,headers=_cache_headers("html"))
    html=INDEX_FILE.read_text(encoding="utf-8",errors="ignore");build=_build_id();html=html.replace("__BUILD__",build).replace("%BUILD%",build);etag=_etag_for_bytes(html.encode())
    if request is not None and (request.headers.get("if-none-match") or "").strip()==etag:return HTMLResponse(status_code=304,content="",headers=_cache_headers("html",etag))
    return HTMLResponse(content=html,headers=_cache_headers("html",etag))
def bind_runtime(*,brain=None,profiles=None,store=None,settings=None,transcription=None,voice=None):
    global APP_BRAIN,APP_PROFILES,APP_STORE,APP_SETTINGS,APP_TRANSCRIPTION,APP_VOICE
    APP_BRAIN=brain;APP_PROFILES=profiles;APP_STORE=store;APP_SETTINGS=settings;APP_TRANSCRIPTION=transcription;APP_VOICE=voice
    log.info("bind_runtime ok brain=%s profiles=%s store=%s voice=%s stt=%s",bool(brain),bool(profiles),bool(store),bool(voice),bool(transcription))
@router.get("/webapp")
def webapp_root(request:Request):return _render_index_html(request)
@router.get("/webapp/health")
def webapp_health():return JSONResponse({"ok":True,"build":_build_id(),"static_dir_exists":STATIC_DIR.exists(),"index_exists":INDEX_FILE.exists()})
@router.get("/webapp/version.json")
def webapp_version():return JSONResponse({"bco_webapp":True,"build":_build_id(),"ts":int(time.time())})
@router.get("/webapp/{req_path:path}")
def webapp_files(req_path:str,request:Request):
    req_path=(req_path or "").strip()
    if not _is_safe_rel_path(req_path):raise HTTPException(status_code=400,detail="bad path")
    if "." not in Path(req_path).name:return _render_index_html(request)
    target=(STATIC_DIR/req_path).resolve()
    try:target.relative_to(STATIC_DIR)
    except Exception:raise HTTPException(status_code=400,detail="bad path")
    if not target.exists() or not target.is_file():return Response(status_code=404,content="Not Found")
    etag=_etag_for_file(target)
    if (request.headers.get("if-none-match") or "").strip()==etag:return Response(status_code=304,headers=_cache_headers("asset",etag))
    return FileResponse(path=str(target),headers=_cache_headers("asset",etag))
class AskBody(BaseModel):
    initData:str="";text:str=Field(default="",max_length=6000);profile:dict=Field(default_factory=dict);history:list=Field(default_factory=list)
def _safe_profile(profile):
    if not isinstance(profile,dict):return {}
    allowed={"game","mode","platform","input","difficulty","voice","voice_identity","tts_mode","tts_voice","profile_name","role","bf6_class","zombies_active","zombies_map","rank","kd","playstyle","current_goal","training_focus","weekly_focus"};return {str(k):v for k,v in profile.items() if k in allowed}
def _safe_history(history):
    if not isinstance(history,list):return []
    out=[]
    for item in history[-20:]:
        if not isinstance(item,dict):continue
        role=str(item.get("role") or "").lower();content=str(item.get("content") or item.get("text") or "").strip()
        if role in {"user","assistant"} and content:
            row={"role":role,"content":content[:2000]}
            if item.get("ts") is not None:row["ts"]=item.get("ts")
            out.append(row)
    return out
def _trusted_server_context(meta):
    identity=meta.get("chat_id") or meta.get("user_id")
    try:identity=int(identity) if identity is not None else None
    except Exception:identity=None
    profile={};history=[]
    if identity is not None and APP_PROFILES is not None:
        try:profile=APP_PROFILES.get(identity) or {}
        except Exception:pass
    if identity is not None and APP_STORE is not None:
        try:history=APP_STORE.get(identity) or []
        except Exception:pass
    return profile,_safe_history(history),identity
@router.post("/webapp/api/conversation-history")
async def webapp_conversation_history(x_telegram_init_data:str|None=Header(default=None,alias="X-Telegram-Init-Data")):
    trusted,meta=verify_init_data(str(x_telegram_init_data or "").strip())
    if not trusted:raise HTTPException(status_code=401,detail="trusted_telegram_context_required")
    _,history,identity=_trusted_server_context(dict(meta or {}))
    if identity is None:raise HTTPException(status_code=401,detail="telegram_identity_missing")
    return JSONResponse({"ok":True,"trusted":True,"authority":"shared_server_conversation_store","history":history[-20:],"count":len(history[-20:]),"build":_build_id()},headers={"Cache-Control":"no-store"})
@router.post("/webapp/api/ask")
async def webapp_api_ask(body:AskBody,x_telegram_init_data:str|None=Header(default=None,alias="X-Telegram-Init-Data"),x_bco_version:str|None=Header(default=None,alias="X-BCO-Version")):
    text=(body.text or "").strip()
    if not text:return {"ok":False,"error":"empty_text","build":_build_id()}
    trusted,meta=verify_init_data((x_telegram_init_data or body.initData or "").strip());meta=dict(meta or {})
    if trusted:profile,history,identity=_trusted_server_context(meta);meta.update({"trusted":True,"identity":identity})
    else:profile=_safe_profile(body.profile);history=_safe_history(body.history);meta={"untrusted":True,"trusted":False}
    reply_text=None
    try:
        brain=APP_BRAIN;settings=APP_SETTINGS;ai_key=(getattr(settings,"openai_api_key","") or "").strip() if settings else "";ai_on=bool(getattr(settings,"ai_enabled",True) and ai_key and brain and hasattr(brain,"reply")) if settings else False
        if ai_on:
            fn=brain.reply;reply_text=await fn(text=text,profile=profile,history=history) if inspect.iscoroutinefunction(fn) else fn(text=text,profile=profile,history=history)
            if inspect.isawaitable(reply_text):reply_text=await reply_text
    except Exception:log.exception("webapp_api_ask failed")
    if not reply_text:reply_text="🧠 AI временно недоступен. Повтори запрос через несколько секунд."
    return {"ok":True,"reply":str(reply_text),"meta":{**meta,"bco_version":x_bco_version or "","webapp_build":_build_id()},"build":_build_id()}
@router.post("/webapp/api/voice-turn")
async def webapp_voice_turn(audio:UploadFile=File(...),x_telegram_init_data:str|None=Header(default=None,alias="X-Telegram-Init-Data")):
    trusted,meta=verify_init_data(str(x_telegram_init_data or "").strip())
    if not trusted:raise HTTPException(status_code=401,detail="trusted_telegram_context_required")
    profile,history,identity=_trusted_server_context(dict(meta or {}))
    if identity is None:raise HTTPException(status_code=401,detail="telegram_identity_missing")
    if APP_TRANSCRIPTION is None or APP_BRAIN is None:raise HTTPException(status_code=503,detail="voice_runtime_unavailable")
    raw=await audio.read(12*1024*1024+1)
    if not raw or len(raw)>12*1024*1024:raise HTTPException(status_code=413,detail="audio_too_large_or_empty")
    suffix=Path(audio.filename or "voice.webm").suffix or ".webm"
    tmp=Path(tempfile.mkdtemp(prefix="bco-web-voice-"));src=tmp/f"input{suffix}"
    try:
        src.write_bytes(raw);result=await APP_TRANSCRIPTION.transcribe(src,prompt=build_transcription_prompt(profile));text=str(result.text or "").strip()
        if not text:raise HTTPException(status_code=422,detail="transcription_empty")
        fn=APP_BRAIN.reply;reply=await fn(text=text,profile=profile,history=history) if inspect.iscoroutinefunction(fn) else fn(text=text,profile=profile,history=history)
        if inspect.isawaitable(reply):reply=await reply
        return JSONResponse({"ok":True,"trusted":True,"transcript":text,"reply":str(reply),"confidence":result.confidence,"voice_identity":str(profile.get("voice_identity") or "female"),"tts_available":bool(APP_VOICE and getattr(APP_VOICE,"enabled",False)),"build":_build_id()},headers={"Cache-Control":"no-store"})
    finally:
        import shutil;shutil.rmtree(tmp,ignore_errors=True)
class GameEventBody(BaseModel):
    initData:str="";event:str=Field(default="",max_length=64);payload:dict=Field(default_factory=dict)
@router.post("/webapp/api/game/event")
async def webapp_game_event(body:GameEventBody,x_telegram_init_data:str|None=Header(default=None,alias="X-Telegram-Init-Data")):
    trusted,meta=verify_init_data((x_telegram_init_data or body.initData or "").strip());event=(body.event or "").strip()[:64];payload=body.payload if isinstance(body.payload,dict) else {};stored=False
    if trusted and APP_STORE is not None and hasattr(APP_STORE,"add_progression_event"):
        identity=(meta or {}).get("chat_id") or (meta or {}).get("user_id")
        try:APP_STORE.add_progression_event(int(identity),{"event":event,"payload":payload});stored=True
        except Exception:pass
    return {"ok":True,"stored":stored,"build":_build_id(),"meta":{"trusted":bool(trusted)}}