# -*- coding: utf-8 -*-
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args):
        return

def start_health_server(log):
    port = int(os.getenv("PORT", "10000"))
    host = "0.0.0.0"
    httpd = HTTPServer((host, port), _Handler)

    def _run():
        log.info("health: listening on %s:%s", host, port)
        httpd.serve_forever()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t