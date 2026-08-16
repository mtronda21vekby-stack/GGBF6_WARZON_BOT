# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl


def bot_token() -> str:
    return (
        (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        or (os.getenv("BOT_TOKEN") or "").strip()
        or (os.getenv("TG_BOT_TOKEN") or "").strip()
    )


def verify_init_data(
    init_data: str,
    *,
    token: str | None = None,
    max_age_sec: int | None = 86400,
) -> tuple[bool, dict]:
    """Validate Telegram Mini App initData per Telegram Web Apps spec."""
    raw = (init_data or "").strip()
    token = (token or bot_token()).strip()
    if not raw or not token:
        return False, {}

    pairs = dict(parse_qsl(raw, keep_blank_values=True))
    their_hash = pairs.pop("hash", None)
    if not their_hash:
        return False, {}

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, their_hash):
        return False, {}

    if max_age_sec is not None:
        try:
            auth_date = int(pairs.get("auth_date") or "0")
            if auth_date <= 0 or abs(int(time.time()) - auth_date) > int(max_age_sec):
                return False, {}
        except Exception:
            return False, {}

    user_id = None
    chat_id = None
    try:
        if pairs.get("user"):
            user_id = json.loads(pairs["user"]).get("id")
    except Exception:
        pass
    try:
        if pairs.get("chat"):
            chat_id = json.loads(pairs["chat"]).get("id")
    except Exception:
        pass

    return True, {
        "user_id": user_id,
        "chat_id": chat_id,
        "auth_date": pairs.get("auth_date"),
        "query_id": pairs.get("query_id"),
    }
