import argparse
import json
import sys
 
import analysis
import tiktok_videos
 
 
def main() -> None:
    ap = argparse.ArgumentParser(description="Valor y veracidad de los ultimos videos de una cuenta")
    ap.add_argument("usuario", nargs="?", help="Usuario de TikTok (con o sin @)")
    ap.add_argument("--videos", type=int, default=5, help="Cantidad de videos (por defecto 5)")
    ap.add_argument("--comments", type=int, default=10, help="Comentarios de muestra por video")
    ap.add_argument("--cookies", help="JSON de cookies exportado (Cookie-Editor)")
    ap.add_argument("--headless", action="store_true", help="Navegador sin ventana (mas facil de bloquear)")
    ap.add_argument("--login", action="store_true", help="Abrir el navegador para iniciar sesion")
    ap.add_argument("--out", help="Archivo JSON de salida")
    args = ap.parse_args()
 
    try:
        if args.login:
            tiktok_videos.login()
            return
        if not args.usuario:
            ap.error("Indica un usuario (o usa --login)")
 
        data = tiktok_videos.get_recent_videos(
            args.usuario,
            n=args.videos,
            n_comments=args.comments,
            cookies_file=args.cookies,
            headless=args.headless,
        )
    except ImportError:
        sys.exit("Falta Playwright:  pip install playwright && playwright install chromium")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Error: {e}")
 
    result = analysis.analyze(data)
    user = args.usuario.lstrip("@")
    out = args.out or f"analisis_{user}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
 
    c = result["cuenta"]
    print(f"\n== @{user} ==")
    print(f"Valor:     {c['valor']:>5}  ({c['etiqueta_valor']})")
    print(f"Veracidad: {c['veracidad']:>5}  ({c['etiqueta_veracidad']})")
    for a in c["alertas"]:
        print(f"  ! {a}")
    print()
    for i, v in enumerate(result["videos"], 1):
        print(
            f"V{i} {v['fecha'][:10]}  vistas {v['reproducciones']:>9,}  likes {v['me_gustas']:>8,}  "
            f"coment. {v['comentarios']:>6,}  valor {v['valor']:>5}  veracidad {v['veracidad']:>5}"
        )
    print(f"\nGuardado en {out}")
 
 
if __name__ == "__main__":
    main()
 