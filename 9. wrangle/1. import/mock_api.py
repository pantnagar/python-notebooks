"""Tiny local REST API so you can practice requests -> DataFrame without internet or credentials.
Endpoints (all need header  Authorization: Bearer demo-token-123):
    GET /api/v1/customers?page=1&page_size=100   -> paginated customer records
    GET /api/v1/rates                            -> small JSON object (synthetic)
"""
import json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

TOKEN = "demo-token-123"
_DATA = json.load(open(Path(__file__).parent / "data" / "customers_flat.json"))
_server = None


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u, q = urlparse(self.path), parse_qs(urlparse(self.path).query)
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self._send(401, {"error": "missing or invalid token"})
        if u.path == "/api/v1/customers":
            page = int(q.get("page", [1])[0])
            size = min(int(q.get("page_size", [100])[0]), 200)
            total_pages = -(-len(_DATA) // size)
            return self._send(200, {"page": page, "page_size": size, "total_pages": total_pages,
                                    "total_records": len(_DATA),
                                    "data": _DATA[(page - 1) * size: page * size]})
        if u.path == "/api/v1/rates":
            return self._send(200, {"as_of": "2026-10-01", "synthetic_base_rate_pct": 4.1})
        return self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


def start_server(port=8765):
    """Start once in a background thread. Safe to call again."""
    global _server
    if _server is not None:
        return _server
    try:
        _server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    except OSError:
        return None  # port already in use -> assume it's running from an earlier run
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    return _server
