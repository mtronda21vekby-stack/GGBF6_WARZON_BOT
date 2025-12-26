# -*- coding: utf-8 -*-
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args, **kwargs):
        return  # без лишнего спама в логах


def start_health_server(log=None) -> None:
    port = int(os.environ.get("PORT", "10000"))
    httpd = HTTPServer(("0.0.0.0", port), _H)

    def _run():
        if log:
            log.info("Health server listening on 0.0.0.0:%s", port)
        httpd.serve_forever()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
