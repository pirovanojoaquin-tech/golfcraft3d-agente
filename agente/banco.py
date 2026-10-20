"""Fotos de fondo de Unsplash (licencia gratis para uso comercial, se pueden editar).

Uso (corre en el workflow banco.yml, que tiene el secreto UNSPLASH_ACCESS_KEY):
    python -m agente.banco buscar "baseball cap" [--orientacion squarish]
        -> fondos/busquedas/<consulta>.json con los resultados (id, descripción, miniatura, autor)
    python -m agente.banco descargar <id> <nombre>
        -> fondos/<nombre>.jpg en alta y su crédito en fondos/creditos.yaml

La guía de la API pide avisar cada descarga (download_location) y guardar el crédito del autor.
"""
import argparse
import os
import re
import sys

import requests
import yaml

from .calendario import RAIZ

API = "https://api.unsplash.com"
FONDOS = RAIZ / "fondos"


def _api(ruta, **params):
    clave = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not clave:
        sys.exit("Falta UNSPLASH_ACCESS_KEY")
    r = requests.get(API + ruta, params=params, timeout=60,
                     headers={"Authorization": f"Client-ID {clave}", "Accept-Version": "v1"})
    if r.status_code != 200:
        sys.exit(f"Unsplash {ruta} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def nombre_archivo(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:60]


def buscar(consulta, orientacion=None, paginas=2):
    resultados = []
    for pagina in range(1, paginas + 1):
        params = {"query": consulta, "per_page": 30, "page": pagina, "content_filter": "high"}
        if orientacion:
            params["orientation"] = orientacion
        for f in _api("/search/photos", **params)["results"]:
            resultados.append({
                "id": f["id"], "ancho": f["width"], "alto": f["height"],
                "descripcion": f.get("alt_description") or f.get("description") or "",
                "miniatura": f["urls"]["small"], "autor": f["user"]["name"],
                "link": f["links"]["html"],
            })
    destino = FONDOS / "busquedas" / f"{nombre_archivo(consulta)}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(yaml.safe_dump(resultados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"{len(resultados)} fotos para '{consulta}' -> {destino.relative_to(RAIZ)}")


def descargar(foto_id, nombre):
    f = _api(f"/photos/{foto_id}")
    _api(f"/photos/{foto_id}/download")  # aviso de descarga que pide la guía de Unsplash
    r = requests.get(f["urls"]["raw"], params={"w": 2400, "q": 90, "fm": "jpg"}, timeout=120)
    r.raise_for_status()
    FONDOS.mkdir(exist_ok=True)
    (FONDOS / f"{nombre}.jpg").write_bytes(r.content)
    creditos_path = FONDOS / "creditos.yaml"
    creditos = yaml.safe_load(creditos_path.read_text(encoding="utf-8")) if creditos_path.exists() else {}
    creditos[nombre] = {"id": foto_id, "autor": f["user"]["name"], "link": f["links"]["html"],
                        "licencia": "Unsplash License"}
    creditos_path.write_text(yaml.safe_dump(creditos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"fondos/{nombre}.jpg ({f['width']}x{f['height']}) de {f['user']['name']}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("buscar")
    b.add_argument("consulta")
    b.add_argument("--orientacion", choices=["landscape", "portrait", "squarish"])
    d = sub.add_parser("descargar")
    d.add_argument("id")
    d.add_argument("nombre")
    a = ap.parse_args()
    if a.cmd == "buscar":
        buscar(a.consulta, a.orientacion)
    else:
        descargar(a.id, a.nombre)


if __name__ == "__main__":
    main()
