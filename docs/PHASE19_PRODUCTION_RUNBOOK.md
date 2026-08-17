# BLACK CROWN OPS v19 — Production Runbook

## Required server configuration

```text
AI_ENABLED=1
STORAGE_BACKEND=auto
ADAPTIVE_MISSION_CONTROL_ENABLED=1
TELEGRAM_LIVE_DRAFTS_ENABLED=1
WEBAPP_LIVE_STREAM_ENABLED=1
WEBAPP_CINEMATIC_UI_ENABLED=1
```

`BOT_TOKEN`, `OPENAI_API_KEY` and `SUPABASE_SERVICE_ROLE_KEY` remain server-side secrets and must not be committed.

## Verification

```text
GET  /health/details
POST /webapp/api/runtime
GET  /webapp/command-center.js
GET  /webapp/command-center.css
```

Expected release:

```text
19.0.0 / bco-adaptive-mission-control-v19
```

Expected runtime flags:

```text
adaptive_mission_control=true
live_stream=true
cinematic_ui=true
```

## Safe rollback

Disable only the v19 mission surface:

```text
ADAPTIVE_MISSION_CONTROL_ENABLED=0
```

This preserves v18 Live Intelligence, Supabase memory, VOD, voice and Premium authority. No database rollback is required because mission records use the existing bounded progression-event persistence path.

## Full presentation rollback

```text
TELEGRAM_LIVE_DRAFTS_ENABLED=0
WEBAPP_LIVE_STREAM_ENABLED=0
WEBAPP_CINEMATIC_UI_ENABLED=0
```

The final Telegram answer remains authoritative even when live drafts are disabled.
