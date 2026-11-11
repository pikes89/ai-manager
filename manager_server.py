#!/usr/bin/env python3
"""AI Manager: a local-only web server for the Mac system manager (macOS only).

Serves the SYSTEM panel from ./web and the /api/mgr/* routes from mac_manager.py.
Listens on 127.0.0.1 only. Set AI_MANAGER_PORT to change the port (default 8767).
"""
import json, os, sys, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import mac_manager

PORT = int(os.environ.get("AI_MANAGER_PORT", "8767"))
WEB = (Path(__file__).resolve().parent / "web").resolve()
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
         ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    server_version = "AIManager/1.0"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _trusted(self):
        """Only this app's own page may call the API (blocks other websites)."""
        if self.headers.get("X-Manager") != "1":
            return False
        return self.headers.get("Origin") in (None, f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")

    def _host_ok(self):
        """Blocks DNS rebinding: the Host header must be this machine."""
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/mgr/"):
            if not (self._trusted() and self._host_ok()):
                return self._send(403, {"error": "forbidden"})
            code, obj = mac_manager.route_get(path, parsed.query)
            return self._send(code, obj)
        if not self._host_ok():
            return self._send(403, b"Forbidden", "text/plain")
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        file = (WEB / name).resolve()
        if WEB not in file.parents or not file.is_file():
            return self._send(404, b"Not found", "text/plain")
        self._send(200, file.read_bytes(), TYPES.get(file.suffix, "application/octet-stream"))

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not (path.startswith("/api/mgr/") and self._trusted() and self._host_ok()):
            return self._send(403, {"error": "forbidden"})
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 100_000)
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "bad json"})
        code, obj = mac_manager.route_post(path, body)
        self._send(code, obj)


def main():
    if sys.platform != "darwin":
        sys.exit("AI Manager only runs on macOS.")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    mac_manager.start_background()
    print(f"[ai-manager] http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
