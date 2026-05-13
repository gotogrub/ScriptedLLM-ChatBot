from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json
import mimetypes

from aho_bot.config import load_settings
from aho_bot.schemas import to_plain
from aho_bot.service import AhoBotService


SERVICE = None
SETTINGS = None


class AhoRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.serve_file(SETTINGS.static_dir / "index.html")
            return
        if parsed.path.startswith("/static/"):
            target = SETTINGS.static_dir / parsed.path.removeprefix("/static/")
            self.serve_file(target)
            return
        if parsed.path == "/api/health":
            self.send_json({"status": "ok"})
            return
        if parsed.path == "/api/settings":
            self.send_json(
                {
                    "provider": SETTINGS.llm_provider,
                    "model": SETTINGS.llm_model,
                    "base_url": SETTINGS.llm_base_url,
                    "temperature": SETTINGS.llm_temperature,
                    "top_p": SETTINGS.llm_top_p,
                    "top_k": SETTINGS.llm_top_k,
                    "num_ctx": SETTINGS.llm_num_ctx,
                    "timeout": SETTINGS.llm_timeout,
                    "rag_top_k": SETTINGS.rag_top_k,
                }
            )
            return
        if parsed.path == "/api/models":
            query = parse_qs(parsed.query)
            base_url = query.get("base_url", [SETTINGS.llm_base_url])[0]
            self.send_json(SERVICE.llm.list_ollama_models(base_url))
            return
        if parsed.path == "/api/tickets":
            query = parse_qs(parsed.query)
            user_id = query.get("user_id", ["demo"])[0]
            self.send_json({"tickets": SERVICE.storage.list_tickets(user_id)})
            return
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/chat":
            payload = self.read_json()
            user_id = str(payload.get("user_id") or "demo")
            message = str(payload.get("message") or "")
            options = payload.get("options") or {}
            result = SERVICE.handle_message(user_id, message, options)
            self.send_json(to_plain(result))
            return
        if parsed.path == "/api/reset":
            payload = self.read_json()
            user_id = str(payload.get("user_id") or "demo")
            SERVICE.storage.reset_session(user_id)
            self.send_json({"status": "reset"})
            return
        self.send_error(404)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, path):
        resolved = Path(path).resolve()
        static_root = SETTINGS.static_dir.resolve()
        if static_root not in resolved.parents and resolved != static_root:
            self.send_error(403)
            return
        if not resolved.exists() or not resolved.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        data = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        return


def main():
    global SERVICE, SETTINGS
    SETTINGS = load_settings()
    SERVICE = AhoBotService(SETTINGS)
    server = ThreadingHTTPServer((SETTINGS.host, SETTINGS.port), AhoRequestHandler)
    print(f"Server started at http://{SETTINGS.host}:{SETTINGS.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
