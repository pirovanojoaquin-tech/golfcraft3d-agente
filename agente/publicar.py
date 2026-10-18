"""Publica en Instagram lo que esté pendiente para hoy en el calendario.

Uso:
    python -m agente.publicar               # publica lo pendiente de hoy con hora <= ahora
    python -m agente.publicar --simular     # muestra qué publicaría, sin publicar
    python -m agente.publicar --id 2026-10-20-post   # publica una entrada puntual ya
    python -m agente.publicar --verificar   # solo chequea que el token funcione

Variables de entorno:
    IG_ACCESS_TOKEN   token de larga duración de Instagram (obligatorio salvo --simular)
    MEDIA_BASE_URL    URL pública donde están los archivos del repo. En GitHub Actions
                      se arma sola con GITHUB_REPOSITORY y GITHUB_SHA.
"""
import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

from . import calendario
from .instagram import Instagram

RAIZ = calendario.RAIZ
CONFIG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
MAX_INTENTOS = 3


def base_url():
    if os.environ.get("MEDIA_BASE_URL"):
        return os.environ["MEDIA_BASE_URL"].rstrip("/") + "/"
    repo, sha = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_SHA")
    if not (repo and sha):
        sys.exit("Falta MEDIA_BASE_URL (o GITHUB_REPOSITORY + GITHUB_SHA)")
    return f"https://raw.githubusercontent.com/{repo}/{sha}/"


def pendientes(items, ahora):
    hoy, hora = ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M")
    return [i for i in items if i["estado"] == "pendiente" and i["fecha"] == hoy and i["hora"] <= hora]


def publicar_item(ig, item, base):
    urls = [base + r for r in item["imagenes"]]
    if item["tipo"] == "CAROUSEL":
        return ig.publicar_carrusel(urls, item["caption"])
    if item["tipo"] == "IMAGE":
        return ig.publicar_imagen(urls[0], item["caption"])
    if item["tipo"] == "STORY":
        return ig.publicar_historia(urls[0])
    raise ValueError(f"Tipo desconocido: {item['tipo']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--verificar", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token and not args.simular:
        sys.exit("Falta la variable IG_ACCESS_TOKEN")
    ig = Instagram(token, CONFIG["instagram"]["api_version"]) if token else None

    if args.verificar:
        print("Cuenta:", ig.cuenta())
        print("Límite de publicación:", ig.limite_publicacion())
        return

    ahora = datetime.now(ZoneInfo(CONFIG["zona_horaria"]))
    items = calendario.cargar()
    if args.id:
        cola = [i for i in items if i["id"] == args.id]
        if not cola:
            sys.exit(f"No existe la entrada {args.id}")
        if cola[0]["estado"] == "publicado":
            sys.exit(f"{args.id} ya está publicada")
    else:
        cola = pendientes(items, ahora)

    if not cola:
        print(f"Nada pendiente para {ahora:%Y-%m-%d %H:%M}.")
        return

    base = base_url() if not args.simular else "(simulado)/"
    hubo_error = False
    for item in cola:
        if args.simular:
            print(f"[simulado] {item['id']} {item['tipo']} -> {[base + r for r in item['imagenes']]}")
            continue
        try:
            media_id = publicar_item(ig, item, base)
            item.update(estado="publicado", ig_media_id=media_id, publicado_en=datetime.now(
                ZoneInfo(CONFIG["zona_horaria"])).isoformat(timespec="seconds"))
            item.pop("error", None)
            print(f"OK  {item['id']} -> {media_id}")
        except Exception as e:  # noqa: BLE001 - registramos cualquier falla y seguimos con el resto
            hubo_error = True
            item["intentos"] = item.get("intentos", 0) + 1
            item["error"] = str(e)[:500]
            if item["intentos"] >= MAX_INTENTOS:
                item["estado"] = "error"
            print(f"ERR {item['id']} (intento {item['intentos']}): {e}", file=sys.stderr)
        calendario.guardar(items)

    if hubo_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
