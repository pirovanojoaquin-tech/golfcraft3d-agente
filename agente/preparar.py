"""Prepara la ficha de un producto de Printables: descarga, gramos, tiempo, precio y renders.

Uso:
    python -m agente.preparar 320193 --fecha 2026-10-19 --nombre "Tee de altura fija" \
        --archivos "golf tee.stl" --colores verde,blanco,rojo
    python -m agente.preparar propio:gate-de-putting --fecha 2026-10-26 --colores verde,blanco

Necesita `prusa-slicer`, `blender` y (para diseños propios) `openscad` instalados (el workflow de GitHub los instala).
Deja todo en propuestas/<fecha>/<slug>/:
    ficha.yaml        datos del producto (lo que va al mail y luego a productos/)
    fotos/1.jpg ...   renders (1 = vertical para portada, resto cuadradas)
Los archivos 3D descargados quedan en descargas/ (no se suben al repo).
"""
import argparse
import math
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import requests
import yaml
from PIL import Image

from .buscar import CABECERAS, detalle, gql
from .calendario import RAIZ

CONFIG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
PERFIL = RAIZ / "agente" / "perfiles" / "bambu_pla.ini"
DESCARGAS = RAIZ / "descargas"

LINK = """
mutation($id: ID!, $printId: ID!) {
  getDownloadLink(id: $id, printId: $printId, fileType: stl, source: model_detail) {
    ok errors { messages } output { link }
  }
}"""

# (elevación, giro) de cámara para cada render
ANGULOS = [(32, 35), (24, -40), (55, 10), (18, 160)]


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:50]


def link_descarga(print_id, archivo_id):
    r = gql(LINK, id=str(archivo_id), printId=str(print_id))["getDownloadLink"]
    if not r["ok"]:
        raise RuntimeError(r["errors"])
    return r["output"]["link"]


def descargar(url, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=CABECERAS, timeout=300, stream=True) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for parte in r.iter_content(1 << 16):
                f.write(parte)
    return destino


def a_stl(ruta):
    """El render necesita STL/OBJ: los 3MF se convierten con PrusaSlicer."""
    if ruta.suffix.lower() in (".stl", ".obj"):
        return ruta
    salida = ruta.with_suffix(".stl")
    subprocess.run(["prusa-slicer", "--export-stl", "-o", str(salida), str(ruta)],
                   check=True, capture_output=True)
    return salida


def medidas(ruta):
    r = subprocess.run(["prusa-slicer", "--info", str(ruta)], capture_output=True, text=True)
    return {k: float(v) for k, v in re.findall(r"size_([xyz]) = ([\d.]+)", r.stdout)}


def laminar(ruta):
    """Devuelve (gramos, minutos) estimados para una pieza.

    Si la pieza viene parada de forma que no apoya en la cama (ej: un disco de canto),
    se reintenta acostándola sobre su cara más ancha.
    """
    gcode = ruta.with_suffix(".gcode")
    base = ["prusa-slicer", "--export-gcode", "--load", str(PERFIL), "--center", "128,128", "-o", str(gcode)]
    r = subprocess.run(base + [str(ruta)], capture_output=True, text=True)
    if r.returncode != 0 or not gcode.exists():
        m = medidas(ruta)
        menor = min(m, key=m.get) if m else "z"
        giro = {"x": ["--rotate-y", "90"], "y": ["--rotate-x", "90"]}.get(menor)
        if giro:
            r = subprocess.run(base + giro + [str(ruta)], capture_output=True, text=True)
    if r.returncode != 0 or not gcode.exists():
        raise RuntimeError(f"No se pudo laminar {ruta.name}: {r.stderr[-400:] or r.stdout[-400:]}")
    texto = gcode.read_text(errors="ignore")
    gramos = float(re.search(r"; filament used \[g\] = ([\d.]+)", texto).group(1))
    t = re.search(r"; estimated printing time \(normal mode\) = (.+)", texto).group(1)
    minutos = sum(int(n) * {"d": 1440, "h": 60, "m": 1, "s": 1 / 60}[u] for n, u in re.findall(r"(\d+)([dhms])", t))
    gcode.unlink()
    return gramos, minutos


def precio(gramos):
    p = CONFIG["produccion"]
    costo = gramos * p["precio_kg_filamento"] / 1000
    final = math.ceil(costo * p["multiplicador"] / p["redondeo"]) * p["redondeo"]
    return round(costo), final


def renderizar(modelo, destino, color, angulo, giro, vertical, muestras):
    png = destino.with_suffix(".png")
    cmd = ["blender", "-b", "-P", str(RAIZ / "agente" / "render.py"), "--", str(modelo), str(png),
           "--color", color, "--angulo", str(angulo), "--giro", str(giro),
           "--tam", "1080", "--muestras", str(muestras)]
    if vertical:
        cmd += ["--alto", "1350"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not png.exists():
        raise RuntimeError(f"Falló el render: {r.stdout[-600:]}")
    Image.open(png).convert("RGB").save(destino, "JPEG", quality=90)
    png.unlink()


def formato_tiempo(minutos):
    h, m = divmod(round(minutos), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def preparar(print_id, fecha, nombre=None, archivos=None, colores=None, muestras=64):
    d = detalle(print_id)
    nombre = nombre or d["name"]
    carpeta = RAIZ / "propuestas" / fecha / slug(nombre)
    (carpeta / "fotos").mkdir(parents=True, exist_ok=True)

    disponibles = [s for s in d["stls"] if s["name"].lower().endswith((".stl", ".3mf", ".obj"))]
    if archivos:
        # respetamos el orden pedido: el primero es el que se renderiza
        por_nombre = {s["name"]: s for s in disponibles}
        elegidos = [por_nombre[n] for n in archivos if n in por_nombre]
        faltan = set(archivos) - {s["name"] for s in elegidos}
        if faltan:
            sys.exit(f"No existen en el modelo: {sorted(faltan)}. Hay: {[s['name'] for s in disponibles]}")
    else:
        elegidos = [next((s for s in disponibles if s["name"].lower().endswith(".stl")), disponibles[0])]

    piezas, gramos, minutos = [], 0.0, 0.0
    for s in elegidos:
        local = descargar(link_descarga(d["id"], s["id"]), DESCARGAS / str(d["id"]) / s["name"])
        stl = a_stl(local)
        g, m = laminar(local if local.suffix.lower() == ".3mf" else stl)
        gramos, minutos = gramos + g, minutos + m
        piezas.append({"archivo": s["name"], "printables_file_id": s["id"], "gramos": round(g, 1)})

    modelo_render = a_stl(DESCARGAS / str(d["id"]) / elegidos[0]["name"])
    return terminar(carpeta, piezas, gramos, minutos, modelo_render, colores, muestras, {
        "nombre": nombre,
        "nombre_original": d["name"],
        "descripcion": (d.get("summary") or "").strip(),
        "origen": "printables",
        "printables_id": d["id"],
        "url": f"https://www.printables.com/model/{d['id']}-{d['slug']}",
        "autor": d["user"]["publicUsername"],
        "licencia": d["license"]["abbreviation"],
        "licencia_nombre": d["license"]["name"],
    })


def terminar(carpeta, piezas, gramos, minutos, modelo_render, colores, muestras, datos):
    """Renderiza en los colores pedidos y escribe ficha.yaml (común a Printables y diseños propios)."""
    costo, final = precio(gramos)
    paleta = CONFIG["colores"]
    colores = colores or ["negro", "blanco", "verde"]
    fotos = []
    for n, color in enumerate(colores[:len(ANGULOS)], 1):
        angulo, giro = ANGULOS[n - 1]
        destino = carpeta / "fotos" / f"{n}.jpg"
        renderizar(modelo_render, destino, paleta[color], angulo, giro, vertical=(n == 1), muestras=muestras)
        fotos.append({"archivo": f"{n}.jpg", "color": color})

    ficha = {
        **datos,
        "piezas": piezas,
        "gramos": round(gramos, 1),
        "tiempo_min": round(minutos),
        "tiempo": formato_tiempo(minutos),
        "costo_filamento": costo,
        "precio": final,
        "material": CONFIG["produccion"]["material"],
        "colores_render": colores,
        "fotos": fotos,
        "estimacion": "Gramos y tiempo estimados con perfil genérico (0,2 mm, 15 % relleno, 2 perímetros). "
                      "Verificar en Bambu Studio antes de cotizar piezas grandes.",
    }
    (carpeta / "ficha.yaml").write_text(yaml.safe_dump(ficha, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return carpeta, ficha


def preparar_propio(slug_diseno, fecha, colores=None, muestras=64):
    """Diseño propio de disenos/<slug>/: compila los .scad con OpenSCAD, lamina y renderiza.

    disenos/<slug>/info.yaml tiene: nombre, descripcion, inspiracion y piezas (lista de .scad o .stl).
    Los STL generados quedan en disenos/<slug>/ (se suben al repo: son nuestros).
    """
    base = RAIZ / "disenos" / slug_diseno
    info = yaml.safe_load((base / "info.yaml").read_text(encoding="utf-8"))
    carpeta = RAIZ / "propuestas" / fecha / slug(info["nombre"])
    (carpeta / "fotos").mkdir(parents=True, exist_ok=True)
    piezas, gramos, minutos, stls = [], 0.0, 0.0, []
    for archivo in info["piezas"]:
        fuente = base / archivo
        stl = fuente.with_suffix(".stl")
        if fuente.suffix.lower() == ".scad":
            r = subprocess.run(["openscad", "-o", str(stl), str(fuente)], capture_output=True, text=True)
            if r.returncode != 0 or not stl.exists():
                raise RuntimeError(f"OpenSCAD falló con {archivo}: {r.stderr[-600:]}")
        g, m = laminar(stl)
        gramos, minutos = gramos + g, minutos + m
        stls.append(stl)
        piezas.append({"archivo": stl.name, "ruta": stl.relative_to(RAIZ).as_posix(), "gramos": round(g, 1)})
    return terminar(carpeta, piezas, gramos, minutos, stls[0], colores, muestras, {
        "nombre": info["nombre"],
        "descripcion": info.get("descripcion", ""),
        "inspiracion": info.get("inspiracion", ""),
        "origen": "propio",
        "printables_id": None,
        "url": None,
        "autor": "GolfCraft3D",
        "licencia": "Diseño propio",
        "licencia_nombre": "Diseño propio de GolfCraft3D (sin restricciones)",
        "diseno": slug_diseno,
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("printables_id", help="id de Printables, o propio:<carpeta de disenos/>")
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--nombre")
    ap.add_argument("--archivos", help="nombres de archivo separados por | (por defecto el primer STL)")
    ap.add_argument("--colores", help="colores del stock separados por coma (ej: verde,blanco,rojo)")
    ap.add_argument("--muestras", type=int, default=64)
    a = ap.parse_args()
    colores = a.colores.split(",") if a.colores else None
    if colores:
        malos = [c for c in colores if c not in CONFIG["colores"]]
        if malos:
            sys.exit(f"Colores que no están en el stock: {malos}")
    if a.printables_id.startswith("propio:"):
        carpeta, ficha = preparar_propio(a.printables_id.split(":", 1)[1], a.fecha, colores, a.muestras)
    else:
        carpeta, ficha = preparar(a.printables_id, a.fecha, a.nombre,
                                  a.archivos.split("|") if a.archivos else None, colores, a.muestras)
    print(f"{carpeta.relative_to(RAIZ)}: {ficha['gramos']} g, {ficha['tiempo']}, precio ${ficha['precio']}")


if __name__ == "__main__":
    main()
