
import argparse
import csv
import json
import re
import sys
import time

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

SCRIPT_RE = re.compile(
    r'<script[^>]*id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.DOTALL,
)

_session = requests.Session()
_session.headers.update(HEADERS)


def _parse_html(html: str) -> dict | None:
    match = SCRIPT_RE.search(html)
    if not match:
        return None
    return json.loads(match.group(1))["__DEFAULT_SCOPE__"]


def _fetch_with_browser(url: str) -> str:
    """Respaldo: abre un Chromium real (pip install playwright && playwright install chromium)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA, locale="es-ES")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(
            "#__UNIVERSAL_DATA_FOR_REHYDRATION__", state="attached", timeout=20000
        )
        html = page.content()
        browser.close()
    return html


def get_page_data(url: str) -> dict:
    """Descarga la pagina y extrae el JSON embebido de TikTok."""
    resp = _session.get(url, timeout=20)
    data = _parse_html(resp.text) if resp.status_code == 200 else None
    if data:
        return data

    
    try:
        html = _fetch_with_browser(url)
        data = _parse_html(html)
        if data:
            return data
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Fallo tambien el navegador de respaldo: {e}")

    raise RuntimeError(
        f"TikTok no devolvio los datos (HTTP {resp.status_code}). Probablemente bloqueo o captcha. "
        "Prueba: pip install playwright && playwright install chromium, y vuelve a intentar."
    )


def get_profile(username: str) -> dict:
    username = username.lstrip("@")
    scope = get_page_data(f"https://www.tiktok.com/@{username}")
    info = scope.get("webapp.user-detail", {}).get("userInfo")
    if not info:
        raise RuntimeError(f"No se encontro el usuario @{username}")
    user, stats = info["user"], info["stats"]
    return {
        "nombre": user.get("nickname"),
        "usuario": user.get("uniqueId"),
        "seguidores": stats.get("followerCount"),
        "seguidos": stats.get("followingCount"),
        "me_gustas_totales": stats.get("heartCount"),
        "videos": stats.get("videoCount"),
        "verificado": user.get("verified"),
        "bio": user.get("signature"),
    }


def get_video(url: str) -> dict:
    scope = get_page_data(url)
    item = scope.get("webapp.video-detail", {}).get("itemInfo", {}).get("itemStruct")
    if not item:
        raise RuntimeError("No se pudo leer el video (privado, eliminado o bloqueado).")
    s = item["stats"]
    likes = s.get("diggCount", 0)
    comments = s.get("commentCount", 0)
    shares = s.get("shareCount", 0)
    saves = int(s.get("collectCount", 0) or 0)
    plays = s.get("playCount", 0)
    interacciones = likes + comments + shares + saves
    return {
        "usuario": item["author"]["uniqueId"],
        "nombre": item["author"]["nickname"],
        "descripcion": item.get("desc"),
        "me_gustas": likes,
        "comentarios": comments,
        "compartidos": shares,
        "guardados": saves,
        "reproducciones": plays,
        "interacciones": interacciones,
        "tasa_interaccion_%": round(interacciones / plays * 100, 2) if plays else 0,
    }


def print_dict(d: dict) -> None:
    for k, v in d.items():
        print(f"  {k.replace('_', ' ').capitalize():<22} {v}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper de datos publicos de TikTok")
    parser.add_argument("usuarios", nargs="*", help="Usuarios (con o sin @)")
    parser.add_argument("--video", action="append", default=[], help="URL de un video")
    parser.add_argument("--csv", help="Guardar perfiles en un archivo CSV")
    args = parser.parse_args()

    if not args.usuarios and not args.video:
        parser.error("Indica al menos un usuario o un --video")

    perfiles = []
    for u in args.usuarios:
        try:
            p = get_profile(u)
            print(f"== Perfil @{p['usuario']} ==")
            print_dict(p)
            perfiles.append(p)
        except Exception as e:
            print(f"[!] @{u}: {e}", file=sys.stderr)
        time.sleep(2)  # pausa para no saturar

    for url in args.video:
        try:
            v = get_video(url)
            print(f"== Video de @{v['usuario']} ==")
            print_dict(v)
        except Exception as e:
            print(f"[!] {url}: {e}", file=sys.stderr)
        time.sleep(2)

    if args.csv and perfiles:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=perfiles[0].keys())
            w.writeheader()
            w.writerows(perfiles)
        print(f"Guardado en {args.csv}")


if __name__ == "__main__":
    main()