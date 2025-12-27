# -*- coding: utf-8 -*-
import time
from typing import Any, Dict, Optional


def poll_forever(api, handlers, log, *, timeout: int = 50):
    """
    Long-polling без падений + backoff.
    """
    # важное: при polling лучше удалить webhook
    try:
        api.delete_webhook_on_start()
    except Exception as e:
        log.warning("delete_webhook_on_start failed: %r", e)

    offset: Optional[int] = None
    backoff = 1.0

    log.info("BOT STARTED (polling)")

    while True:
        try:
            params = {"timeout": timeout}
            if offset is not None:
                params["offset"] = offset

            data = api.request("getUpdates", params=params, retries=3)  # GET
            results = data.get("result") or []

            for upd in results:
                try:
                    handlers.handle_update(upd)
                except Exception as e:
                    log.exception("handler error: %r", e)

                upd_id = upd.get("update_id")
                if isinstance(upd_id, int):
                    offset = upd_id + 1

            backoff = 1.0

        except Exception as e:
            log.error("poll loop error: %r", e)
            time.sleep(min(10.0, backoff))
            backoff = min(10.0, backoff * 1.6)
