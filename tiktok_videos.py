from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json
 
import tiktok_scraper
 
SESSION_DIR = Path(__file__).parent / "tiktok_session"
 
SAMESITE = {
    "no_restriction": "None",
    "none": "None",
    "lax": "Lax",
    "strict": "Strict",
    "unspecified": "Lax",
}
 
 
def _int(x) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0
 
 
def _load_cookies(path: str) -> list[dict]:
    """Convierte un JSON exportado por Cookie-Editor al formato de Playwright."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cookies = []
    for c in raw:
        if not c.get("name") or c.get("value") is None:
            continue
        item = {
            "name": c["name"],
            "value": str(c["value"]),
            "domain": c.get("domain", ".tiktok.com"),
            "path": c.get("path", "/"),
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
            "sameSite": SAMESITE.get(str(c.get("sameSite", "")).lower(), "Lax"),
        }
        exp = c.get("expirationDate") or c.get("expires")
        if isinstance(exp, (int, float)) and exp > 0:
            item["expires"] = exp
        cookies.append(item)
    return cookies
 
 
class _Collector:
    """Guarda lo que TikTok responde mientras navegamos."""
 
    def __init__(self):
        self.items: dict[str, dict] = {}
        self.comments: dict[str, dict] = {}
 
    def on_response(self, resp) -> None:
        url = resp.url
        try:
            if "/api/post/item_list" in url:
                for it in resp.json().get("itemList") or []:
                    self.items[str(it["id"])] = it
            elif "/api/comment/list" in url and "/reply" not in url:
                vid = parse_qs(urlparse(url).query).get("aweme_id", [None])[0]
                bucket = self.comments.setdefault(vid, {})
                for c in resp.json().get("comments") or []:
                    bucket[c.get("cid")] = {
                        "usuario": (c.get("user") or {}).get("unique_id") or "",
                        "texto": c.get("text") or "",
                        "likes": _int(c.get("digg_count")),
                        "respuestas": _int(c.get("reply_comment_total")),
                    }
        except Exception:
            pass  # respuestas sin JSON, bloqueadas, etc.
 
 
def _wait_until(page, cond, seconds: float, scroll: bool = False) -> bool:
    waited = 0
    while waited < seconds * 1000:
        if cond():
            return True
        if scroll and waited % 3000 == 0:
            page.mouse.wheel(0, 1500)
        page.wait_for_timeout(500)
        waited += 500
    return bool(cond())
 
 
def _open_video(page, username: str, vid: str, log=print) -> bool:
    """Abre un video. Plan A: URL directa (2 intentos). Plan B: clic desde el perfil."""
    url = f"https://www.tiktok.com/@{username}/video/{vid}"
    for attempt in range(2):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            return True
        except Exception as e:  # p. ej. net::ERR_HTTP_RESPONSE_CODE_FAILURE
            reason = str(e).splitlines()[0] if str(e) else type(e).__name__
            log(f"  Apertura directa fallida ({reason}).")
            page.wait_for_timeout(4000 * (attempt + 1))
    try:
        log("  Probando abrirlo con un clic desde el perfil...")
        page.goto(f"https://www.tiktok.com/@{username}", wait_until="domcontentloaded", timeout=60000)
        link = page.locator(f'a[href*="/video/{vid}"]').first
        link.wait_for(timeout=15000)
        link.click()
        page.wait_for_url(f"**/video/{vid}*", timeout=15000)
        return True
    except Exception:
        return False
 
 
def _read_profile(page, username: str, items: list[dict]) -> dict:
    try:
        scope = tiktok_scraper._parse_html(page.content())
        info = scope["webapp.user-detail"]["userInfo"]
        u, s = info["user"], info["stats"]
        return {
            "nombre": u.get("nickname"),
            "usuario": u.get("uniqueId"),
            "seguidores": s.get("followerCount"),
            "seguidos": s.get("followingCount"),
            "me_gustas_totales": s.get("heartCount"),
            "videos": s.get("videoCount"),
        }
    except Exception:
        pass
    # Respaldo: cada video trae los datos del autor
    if items:
        author = items[0].get("author")
        author = author if isinstance(author, dict) else {}
        st = items[0].get("authorStats") or {}
        return {
            "nombre": author.get("nickname"),
            "usuario": author.get("uniqueId", username),
            "seguidores": st.get("followerCount"),
            "seguidos": st.get("followingCount"),
            "me_gustas_totales": st.get("heartCount"),
            "videos": st.get("videoCount"),
        }
    return {"usuario": username, "seguidores": None}
 
 
def _build_video(it: dict, username: str, comments: list[dict]) -> dict:
    st = it.get("stats") or {}
    ts = _int(it.get("createTime"))
    vid = str(it["id"])
    return {
        "id": vid,
        "url": f"https://www.tiktok.com/@{username}/video/{vid}",
        "descripcion": it.get("desc") or "",
        "fecha": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if ts else "",
        "reproducciones": _int(st.get("playCount")),
        "me_gustas": _int(st.get("diggCount")),
        "comentarios": _int(st.get("commentCount")),
        "compartidos": _int(st.get("shareCount")),
        "guardados": _int(st.get("collectCount")),
        "comentarios_muestra": comments,
    }
 
 
def get_recent_videos(
    username: str,
    n: int = 5,
    n_comments: int = 10,
    cookies_file: str | None = None,
    headless: bool = False,
    log=print,
) -> dict:
    """Devuelve {"perfil": {...}, "videos": [...]} con los n videos mas recientes."""
    from playwright.sync_api import sync_playwright  # ImportError si no esta instalado
 
    username = username.lstrip("@")
    col = _Collector()
 
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=headless,
            locale="es-ES",
            viewport={"width": 1280, "height": 900},
        )
        try:
            if cookies_file:
                ctx.add_cookies(_load_cookies(cookies_file))
            page = ctx.new_page()
            page.on("response", col.on_response)
 
            log(f"Abriendo perfil @{username}...")
            page.goto(
                f"https://www.tiktok.com/@{username}",
                wait_until="domcontentloaded",
                timeout=60000,
            )
 
            if not _wait_until(page, lambda: col.items, 20, scroll=True) and not headless:
                log("No llegaron videos. Si ves un captcha en la ventana, resuelvelo (90 s)...")
                _wait_until(page, lambda: col.items, 90, scroll=True)
            if not col.items:
                raise RuntimeError(
                    "No se pudo obtener la lista de videos (captcha, cuenta privada o sin videos). "
                    "Prueba: python analyze.py --login, o usa --cookies."
                )
 
            perfil = _read_profile(page, username, list(col.items.values()))
            latest = sorted(
                col.items.values(), key=lambda it: _int(it.get("createTime")), reverse=True
            )[:n]
 
            videos = []
            for i, it in enumerate(latest, 1):
                vid = str(it["id"])
                log(f"Video {i}/{len(latest)} ({vid})...")
                opened = _open_video(page, username, vid, log)
                if not opened:
                    log("  No se pudo abrir este video; se guardan sus estadisticas sin comentarios.")
                if opened and n_comments > 0:
                    if not _wait_until(page, lambda: vid in col.comments, 10):
                        try:  # abrir el panel de comentarios si no se abrio solo
                            page.locator('[data-e2e="comment-icon"]').first.click(timeout=3000)
                        except Exception:
                            pass
                        _wait_until(page, lambda: vid in col.comments, 8)
                    page.wait_for_timeout(800)
                comments = list(col.comments.get(vid, {}).values())[:n_comments]
                videos.append(_build_video(it, username, comments))
                page.wait_for_timeout(2500)  # pausa entre videos para no parecer un robot
 
            return {"perfil": perfil, "videos": videos}
        finally:
            ctx.close()
 
 
def login() -> None:
    """Abre el navegador para iniciar sesion / resolver captcha una vez."""
    from playwright.sync_api import sync_playwright
 
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(SESSION_DIR), headless=False, locale="es-ES"
        )
        page = ctx.new_page()
        page.goto("https://www.tiktok.com/login")
        input("Inicia sesion (o resuelve el captcha) en la ventana y pulsa Enter aqui para guardar... ")
        ctx.close()
    print(f"Sesion guardada en {SESSION_DIR}")
 