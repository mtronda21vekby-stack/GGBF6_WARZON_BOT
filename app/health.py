# -*- coding: utf-8 -*-
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return  # отключаем стандартный лог


def start_health(log=None):
    port = int(os.environ.get("PORT", "10000"))

    def run():
        try:
            server = HTTPServer(("0.0.0.0", port), HealthHandler)
            if log:
                log.info(f"Health server started on port {port}")
            server.serve_forever()
        except Exception as e:
            if log:
                log.error(f"Health server failed: {e}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
