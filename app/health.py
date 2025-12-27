# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading


class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):
        # тихо, чтобы не спамило логи
        return


def start_health_server(port: int, log):
    def _run():
        srv = HTTPServer(("0.0.0.0", port), _H)
        log.info("Health server listening on :%s", port)
        srv.serve_forever()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
