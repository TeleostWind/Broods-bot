import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 8080))


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is alive.\n")

    # silence normal logging (remove if you want logs)
    def log_message(self, format, *args):
        return


def _run_server():
    server = HTTPServer(("0.0.0.0", PORT), _Handler)
    try:
        server.serve_forever()
    except Exception:
        # server closed or interrupted
        pass


def keep_alive():
    """Call this from your main file to start the tiny webserver in a daemon thread."""
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
