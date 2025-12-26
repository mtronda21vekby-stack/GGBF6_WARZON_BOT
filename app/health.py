# -*- coding: utf-8 -*-
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Render ждёт открытый порт из ENV PORT.
# Этот health-сервер нужен ТОЛЬКО чтобы деплой не падал по "no open ports detected".

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = b"OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = b"Not Found"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # чтобы не спамило в логи
    def log_message(self, format, *args):
        return


def start_health(log=None) -> None:
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "10000"))

    def _run():
        try:
            httpd = HTTPServer((host, port), _Handler)
            if log:
                log.info("Health server listening on %s:%s", host, port)
            httpd.serve_forever()
        except Exception as e:
            if log:
                log.warning("Health server failed: %r", e)

    t = threading.Thread(target=_run, name="health-server", daemon=True)
    t.start()