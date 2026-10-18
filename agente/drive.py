"""Guarda en Google Drive los archivos 3D y la ficha de productos aprobados.

Usa el script de Apps Script del usuario (herramientas/guardar_en_drive.gs), cuya URL
está en la variable DRIVE_WEBAPP_URL. Cada producto queda en PRODUCTOS 3D GOLF/<nombre>/.

Uso:
    DRIVE_WEBAPP_URL=... python -m agente.drive tee-de-altura-fija clip-de-gorra
"""
import argparse
import os
import sys

import requests
import yaml

from .calendario import RAIZ
from .preparar import link_descarga


def texto_ficha(info):
    piezas = "\n".join(f"  - {p['archivo']} ({p['gramos']} g)" for p in info.get("piezas") or [])
    return f"""{info['nombre']}
{'=' * len(info['nombre'])}

{info.get('descripcion') or ''}

Precio de venta: ${info['precio']}
Filamento: {info['gramos']} g de PLA
Tiempo estimado: {info['tiempo']}
Colores sugeridos: {', '.join(info.get('colores') or [])}
Personalizable: {info.get('personalizable') or '-'}

Archivos:
{piezas}

Modelo original: {info['url']}
Autor: {info['autor']} — Licencia: {info['licencia']}
(La licencia permite vender impresiones; si la pide, dar crédito al autor.)
"""


def guardar(slug, url_app):
    info = yaml.safe_load((RAIZ / "productos" / slug / "info.yaml").read_text(encoding="utf-8"))
    archivos = [{"nombre": p["archivo"], "url": link_descarga(info["printables_id"], p["printables_file_id"])}
                for p in info.get("piezas") or []]
    r = requests.post(url_app, json={"carpeta": info["nombre"], "archivos": archivos, "ficha": texto_ficha(info)},
                      timeout=300)
    r.raise_for_status()
    try:
        datos = r.json()
    except ValueError:
        # Apps Script devuelve una página HTML cuando la implementación no es pública o falla al iniciar
        import re
        titulo = re.search(r"<title>(.*?)</title>", r.text, re.S)
        cuerpo = re.sub(r"<[^>]+>", " ", r.text)
        raise RuntimeError(f"Drive no devolvió JSON (HTTP {r.status_code}, url final {r.url.split('?')[0]}): "
                           f"{titulo.group(1).strip() if titulo else ''} | {' '.join(cuerpo.split())[:300]}")
    if not datos.get("ok"):
        raise RuntimeError(datos.get("error"))
    return datos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="+")
    a = ap.parse_args()
    url_app = os.environ.get("DRIVE_WEBAPP_URL")
    if not url_app:
        sys.exit("Falta DRIVE_WEBAPP_URL")
    errores = 0
    for slug in a.slugs:
        try:
            d = guardar(slug, url_app)
            print(f"OK  {slug} -> {d['carpeta']} ({', '.join(d['archivos'])})")
        except Exception as e:  # noqa: BLE001 - seguimos con los demás
            errores += 1
            print(f"ERR {slug}: {e}", file=sys.stderr)
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
