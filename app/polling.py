# -*- coding: utf-8 -*-
import time
from typing import Optional

class PollingLoop:
    def __init__(self, *, api, handlers, log):
        self.api = api
        self.handlers = handlers
        self.log = log

    def run_forever(self):
        offset: int = 0
        backoff: float = 1.0

        self.log.info("polling: started")
        while True:
            try:
                data = self.api.get_updates(offset=offset, timeout=50)
                if not data.get("ok"):
                    # частая ошибка: Conflict (если запущено 2 инстанса)
                    desc = str(data.get("description", ""))
                    self.log.warning("polling: telegram not ok: %s", desc[:200])
                    time.sleep(min(30, backoff))
                    backoff = min(30, backoff * 1.7)
                    continue

                backoff = 1.0
                result = data.get("result") or []
                for upd in result:
                    try:
                        update_id = upd.get("update_id")
                        if isinstance(update_id, int):
                            offset = update_id + 1
                        self.handlers.handle_update(upd)
                    except Exception as e:
                        self.log.warning("update handling error: %r", e)

            except Exception as e:
                self.log.warning("poll loop error: %r", e)
                time.sleep(min(30, backoff))
                backoff = min(30, backoff * 1.7)