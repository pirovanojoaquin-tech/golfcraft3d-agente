"""Busca modelos de golf en Printables y MakerWorld (Bambu) con licencia que permita vender las impresiones.

Uso:
    python -m agente.buscar                  # imprime candidatos en JSON (de los dos sitios)
    python -m agente.buscar --max 20 --salida candidatos.json
    python -m agente.buscar --fuente makerworld

Cada candidato trae `origen` ("printables" o "makerworld"). De MakerWorld no se pueden bajar archivos sin
cuenta: los gramos y el tiempo salen del perfil publicado en el sitio, y si el dueño lo aprueba, baja el
archivo él y se lo manda al bot de Telegram (ver agente/makerworld.py).

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
MW_API = "https://api.bambulab.com/v1"  # el mismo buscador que usan makerworld.com y Bambu Studio
PROPUESTOS = RAIZ / "productos" / "propuestos.json"
# Printables rechaza el User-Agent por defecto de requests
CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; GolfCraft3D-agente/1.0)", "Accept": "application/json"}

BUSQUEDAS = [
    # accesorios
    "golf", "golf ball", "golf ball marker", "golf tee", "golf tee holder", "divot tool", "pitch mark repair",
    "golf ball holder", "golf ball clip", "golf glove holder", "golf towel clip", "golf scorecard",
    "golf pencil", "golf bag", "golf bag tag", "golf club", "golf headcover", "golf shoe", "golf hat clip",
    "golf cart", "golf cart holder", "golf cup holder",
    # entrenamiento
    "golf training", "golf training aid", "golf alignment", "alignment stick", "putting", "putting gate",
    "putting trainer", "putting cup", "golf swing trainer", "golf grip trainer", "golf chipping",
    "golf practice", "golf impact", "golf wrist", "putting alignment", "putting mirror", "putting stroke",
    "putting guide", "golf swing plane", "golf tempo", "golf driving", "golf stance", "chipping target",
    "golf distance marker",
    # regalos, decoración y organización
    "golf gift", "golf ball display", "golf ball stand", "golf trophy", "golf keychain", "golf ornament",
    "golf storage", "golf organizer", "golf bottle opener", "golf coaster",
]

# Licencias que permiten vender las impresiones (con atribución al autor cuando corresponde)
LICENCIAS_OK = {"CC-BY", "CC-BY-SA", "CC0", "PD", "GNU-GPL", "GNU-LGPL", "BSD"}
# En MakerWorld casi todo es "Standard Digital File License", que prohíbe cobrar por las impresiones
MW_LICENCIAS_OK = {"BY", "BY-SA", "CC0"}

NO_GOLF = re.compile(r"\b(gti|volkswagen|vw|mk ?[1-8]|tdi|gtd|r32|scirocco|polo|passat|jetta|wheel ?cap|hubcap)\b", re.I)
SI_GOLF = re.compile(r"golf|putt|divot|\btee\b|caddie|caddy|fairway|birdie|scorecard", re.I)
# Entrenamiento primero (lo que más le interesa al dueño desde 25/10/2026); decoración y regalos al final
ENTRENAMIENTO = re.compile(r"train|practi|putt|align|swing|tempo|chip|drill|target|stance|grip|wrist|plane|aim", re.I)
DECORACION = re.compile(r"trophy|ornament|keychain|display|coaster|gift|gag|funny|decor|figure|statue|lamp", re.I)


def prioridad(nombre):
    return 0 if DECORACION.search(nombre) else 2 if ENTRENAMIENTO.search(nombre) else 1

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
    """Ids ya propuestos o cargados: "123" para Printables y "mw123" para MakerWorld."""
    vistos = set()
    if PROPUESTOS.exists():
        for p in json.loads(PROPUESTOS.read_text(encoding="utf-8")):
            if p.get("printables_id"):
                vistos.add(str(p["printables_id"]))
            if p.get("makerworld_id"):
                vistos.add(f"mw{p['makerworld_id']}")
    # también los propuestos que todavía no tienen respuesta
    for info in list((RAIZ / "productos").glob("*/info.yaml")) + list((RAIZ / "propuestas").glob("*/*/ficha.yaml")):
        texto = info.read_text(encoding="utf-8")
        m = re.search(r"printables_id:\s*['\"]?(\d+)", texto)
        if m:
            vistos.add(m.group(1))
        m = re.search(r"makerworld_id:\s*['\"]?(\d+)", texto)
        if m:
            vistos.add(f"mw{m.group(1)}")
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
    orden = sorted(encontrados.values(), key=lambda i: (prioridad(i["name"]),
                                                        (i["likesCount"] or 0) * 3 + (i["downloadCount"] or 0) / 10),
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
            "origen": "printables",
            "printables_id": d["id"],
            "nombre": d["name"],
            "resumen": (d.get("summary") or "").strip(),
            "autor": d["user"]["publicUsername"],
            "licencia": d["license"]["abbreviation"],
            "likes": d["likesCount"],
            "descargas": d["downloadCount"],
            "url": f"https://www.printables.com/model/{d['id']}-{d['slug']}",
            "tipo": ["decoración/regalo", "accesorio", "entrenamiento"][prioridad(d["name"])],
            "imagen": f"https://media.printables.com/{d['images'][0]['filePath']}" if d.get("images") else None,
            "archivos": [a["name"] for a in archivos],
        })
        if len(candidatos) >= maximo:
            break
    return candidatos


def mw(ruta, **params):
    r = requests.get(f"{MW_API}/{ruta}", params=params, headers=CABECERAS, timeout=60)
    r.raise_for_status()
    return r.json()


def detalle_mw(design_id):
    d = mw(f"design-service/design/{design_id}")
    if not d.get("id"):
        raise RuntimeError(f"MakerWorld no tiene el modelo {design_id}")
    return d


def perfil_mw(d):
    """El perfil de impresión publicado que se usa para gramos y tiempo (el por defecto, o el más impreso)."""
    perfiles = [i for i in d.get("instances") or [] if i.get("weight")]
    if not perfiles:
        return None
    return next((i for i in perfiles if i["id"] == d.get("defaultInstanceId")),
                max(perfiles, key=lambda i: i.get("printCount") or 0))


def texto_plano(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def url_mw(d):
    return f"https://makerworld.com/es/models/{d['id']}-{d['slug']}"


def buscar_makerworld(maximo=15, por_busqueda=50):
    vistos = ya_vistos()
    encontrados = {}
    for q in BUSQUEDAS:
        for it in mw("search-service/select/design2", keyword=q, limit=por_busqueda, offset=0).get("hits") or []:
            clave = f"mw{it['id']}"
            if clave in vistos or clave in encontrados or it.get("license") not in MW_LICENCIAS_OK:
                continue
            if it.get("nsfw") or NO_GOLF.search(it["title"]) or not SI_GOLF.search(it["title"] + " " + q):
                continue
            encontrados[clave] = it

    orden = sorted(encontrados.values(), key=lambda i: (prioridad(i["title"]),
                                                        (i["likeCount"] or 0) * 3 + (i["downloadCount"] or 0) / 10),
                   reverse=True)
    candidatos = []
    for it in orden:
        d = detalle_mw(it["id"])
        resumen = texto_plano(d.get("summary"))
        texto = " ".join([d["title"], resumen, " ".join(d.get("tags") or [])])
        perfil = perfil_mw(d)
        if NO_GOLF.search(texto) or not SI_GOLF.search(texto) or not perfil:
            continue
        candidatos.append({
            "origen": "makerworld",
            "makerworld_id": d["id"],
            "nombre": d["title"],
            "resumen": resumen[:600],
            "autor": d["designCreator"]["name"],
            "licencia": d["license"],
            "likes": d["likeCount"],
            "descargas": d["downloadCount"],
            "url": url_mw(d),
            "tipo": ["decoración/regalo", "accesorio", "entrenamiento"][prioridad(d["title"])],
            "imagen": d.get("coverUrl"),
            "gramos": perfil["weight"],
            "tiempo_min": round((perfil.get("prediction") or 0) / 60),
            "perfil": perfil.get("title"),
        })
        if len(candidatos) >= maximo:
            break
    return candidatos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=15, help="máximo por sitio")
    ap.add_argument("--fuente", choices=["todas", "printables", "makerworld"], default="todas")
    ap.add_argument("--salida")
    args = ap.parse_args()
    candidatos = []
    if args.fuente in ("todas", "printables"):
        candidatos += buscar(args.max)
    if args.fuente in ("todas", "makerworld"):
        try:
            candidatos += buscar_makerworld(args.max)
        except requests.RequestException as e:  # si MakerWorld no responde, seguimos con Printables
            print(f"MakerWorld no respondió: {e}", file=sys.stderr)
    texto = json.dumps(candidatos, ensure_ascii=False, indent=2)
    if args.salida:
        open(args.salida, "w", encoding="utf-8").write(texto + "\n")
        print(f"{len(candidatos)} candidatos -> {args.salida}", file=sys.stderr)
    else:
        print(texto)


if __name__ == "__main__":
    main()
