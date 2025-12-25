# -*- coding: utf-8 -*-
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from app.log import log

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return
    def _ok(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
    def do_HEAD(self):
        if self.path in ("/", "/healthz"):
            self._ok()
        else:
            self.send_response(404)
            self.end_headers()
    def do_GET(self):
        if self.path in ("/", "/healthz", "/"):
            self._ok()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_http_server() -> None:
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    log.info("HTTP server listening on :%s", port)
    server.serve_forever()
