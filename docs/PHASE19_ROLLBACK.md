# Adaptive Mission Control rollback

Set `ADAPTIVE_MISSION_CONTROL_ENABLED=0` and redeploy. This disables mission generation and mutation while preserving v18 Live Intelligence, persistent Player Intelligence, VOD, voice, Premium authority and all stored progression events.

No database rollback is required because v19 mission lifecycle records use the existing progression/training event boundary and are ignored by older runtimes.
