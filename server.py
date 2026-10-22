
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import tiktok_scraper as ts

BASE = Path(__file__).parent
ALLOWED_HOSTS = {"www.tiktok.com", "tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
COOKIES_FILE = BASE / "cookies.json"      # opcional: cookies exportadas
ANALYSIS_LOCK = threading.Lock()          # el perfil del navegador solo admite 1 analisis a la vez


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        qs = parse_qs(url.query)

        if url.path in ("/", "/index.html"):
            html = (BASE / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")

        try:
            if url.path == "/api/profile":
                user = (qs.get("u") or [""])[0].strip()
                if not user:
                    return self._json(400, {"error": "Falta el usuario"})
                return self._json(200, ts.get_profile(user))

            if url.path == "/api/analysis":
                user = (qs.get("u") or [""])[0].strip().lstrip("@")
                if not user:
                    return self._json(400, {"error": "Falta el usuario"})
                n = max(1, min(int((qs.get("n") or ["5"])[0]), 10))
                c = max(0, min(int((qs.get("c") or ["10"])[0]), 30))
                if not ANALYSIS_LOCK.acquire(blocking=False):
                    return self._json(429, {"error": "Ya hay un análisis en curso, espera a que termine."})
                try:
                    import analysis
                    import tiktok_videos

                    data = tiktok_videos.get_recent_videos(
                        user,
                        n=n,
                        n_comments=c,
                        cookies_file=str(COOKIES_FILE) if COOKIES_FILE.exists() else None,
                        headless=os.environ.get("TIKTOK_HEADLESS") == "1",
                    )
                    return self._json(200, analysis.analyze(data))
                except ImportError:
                    return self._json(
                        500,
                        {"error": "Falta Playwright: pip install playwright && playwright install chromium"},
                    )
                finally:
                    ANALYSIS_LOCK.release()

            if url.path == "/api/video":
                video = (qs.get("url") or [""])[0].strip()
                if urlparse(video).hostname not in ALLOWED_HOSTS:
                    return self._json(400, {"error": "La URL debe ser de tiktok.com"})
                return self._json(200, ts.get_video(video))
        except Exception as e:  # noqa: BLE001
            return self._json(502, {"error": str(e)})

        self._json(404, {"error": "No encontrado"})

    def log_message(self, *args) -> None:  # silencia el log
        pass


if __name__ == "__main__":
    print("Panel en http://127.0.0.1:8000  (Ctrl+C para salir)")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()