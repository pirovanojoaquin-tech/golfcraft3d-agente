"""Busca modelos de golf en Printables con licencia que permita vender las impresiones.

Uso:
    python -m agente.buscar                  # imprime candidatos en JSON
    python -m agente.buscar --max 20 --salida candidatos.json

Descarta:
  - licencias no comerciales (NC) o desconocidas
  - modelos que no son de golf (ej: "VW Golf GTI")
  - modelos ya propuestos o ya cargados (productos/propuestos.json)
"""
import argparse
import json
import re
import sys

import requests

from .calendario import RAIZ

API = "https://api.printables.com/graphql/"
PROPUESTOS = RAIZ / "productos" / "propuestos.json"
# Printables rechaza el User-Agent por defecto de requests
CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; GolfCraft3D-agente/1.0)", "Accept": "application/json"}

BUSQUEDAS = [
    "golf", "golf ball", "golf ball marker", "golf tee", "golf tee holder", "divot tool",
    "golf ball holder", "golf bag", "golf club", "golf scorecard", "golf putter",
    "golf training", "golf alignment", "golf glove", "golf cart", "golf gift",
    "golf ball display", "golf pencil", "golf towel", "putting",
]

# Licencias que permiten vender las impresiones (con atribución al autor cuando corresponde)
LICENCIAS_OK = {"CC-BY", "CC-BY-SA", "CC0", "PD", "GNU-GPL", "GNU-LGPL", "BSD"}

NO_GOLF = re.compile(r"\b(gti|volkswagen|vw|mk ?[1-8]|tdi|gtd|r32|scirocco|polo|passat|jetta|wheel ?cap|hubcap)\b", re.I)
SI_GOLF = re.compile(r"golf|putt|divot|\btee\b|caddie|caddy|fairway|birdie|scorecard", re.I)

CONSULTA_BUSQUEDA = """
query($q: String!, $limit: Int!) {
  searchPrints2(query: $q, limit: $limit) {
    items { id name slug likesCount downloadCount license { name abbreviation } }
  }
}"""

CONSULTA_DETALLE = """
query($id: ID!) {
  print(id: $id) {
    id name slug summary likesCount downloadCount
    user { publicUsername }
    license { name abbreviation }
    tags { name }
    images { filePath }
    stls { id name fileSize }
  }
}"""


def gql(query, **variables):
    r = requests.post(API, json={"query": query, "variables": variables}, headers=CABECERAS, timeout=60)
    r.raise_for_status()
    datos = r.json()
    if datos.get("errors"):
        raise RuntimeError(datos["errors"])
    return datos["data"]


def detalle(print_id):
    return gql(CONSULTA_DETALLE, id=str(print_id))["print"]


def ya_vistos():
    vistos = set()
    if PROPUESTOS.exists():
        vistos |= {str(p["printables_id"]) for p in json.loads(PROPUESTOS.read_text(encoding="utf-8"))}
    # también los propuestos que todavía no tienen respuesta
    for info in list((RAIZ / "productos").glob("*/info.yaml")) + list((RAIZ / "propuestas").glob("*/*/ficha.yaml")):
        m = re.search(r"printables_id:\s*['\"]?(\d+)", info.read_text(encoding="utf-8"))
        if m:
            vistos.add(m.group(1))
    return vistos


def licencia_ok(lic):
    return bool(lic) and lic.get("abbreviation", "").upper() in LICENCIAS_OK


def buscar(maximo=15, por_busqueda=40):
    vistos = ya_vistos()
    encontrados = {}
    for q in BUSQUEDAS:
        for it in gql(CONSULTA_BUSQUEDA, q=q, limit=por_busqueda)["searchPrints2"]["items"]:
            pid = str(it["id"])
            if pid in vistos or pid in encontrados or not licencia_ok(it.get("license")):
                continue
            if NO_GOLF.search(it["name"]) or not SI_GOLF.search(it["name"] + " " + q):
                continue
            encontrados[pid] = it

    # los más populares primero
    orden = sorted(encontrados.values(), key=lambda i: (i["likesCount"] or 0) * 3 + (i["downloadCount"] or 0) / 10,
                   reverse=True)
    candidatos = []
    for it in orden:
        d = detalle(it["id"])
        texto = " ".join([d["name"], d.get("summary") or "", " ".join(t["name"] for t in d.get("tags") or [])])
        if NO_GOLF.search(texto) or not SI_GOLF.search(texto):
            continue
        archivos = [s for s in d.get("stls") or [] if s["name"].lower().endswith((".stl", ".3mf", ".obj"))]
        if not archivos:
            continue
        candidatos.append({
            "printables_id": d["id"],
            "nombre": d["name"],
            "resumen": (d.get("summary") or "").strip(),
            "autor": d["user"]["publicUsername"],
            "licencia": d["license"]["abbreviation"],
            "likes": d["likesCount"],
            "descargas": d["downloadCount"],
            "url": f"https://www.printables.com/model/{d['id']}-{d['slug']}",
            "imagen": f"https://media.printables.com/{d['images'][0]['filePath']}" if d.get("images") else None,
            "archivos": [a["name"] for a in archivos],
        })
        if len(candidatos) >= maximo:
            break
    return candidatos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=15)
    ap.add_argument("--salida")
    args = ap.parse_args()
    candidatos = buscar(args.max)
    texto = json.dumps(candidatos, ensure_ascii=False, indent=2)
    if args.salida:
        open(args.salida, "w", encoding="utf-8").write(texto + "\n")
        print(f"{len(candidatos)} candidatos -> {args.salida}", file=sys.stderr)
    else:
        print(texto)


if __name__ == "__main__":
    main()
