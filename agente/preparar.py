"""Prepara la ficha de un producto de Printables: descarga, gramos, tiempo, precio y renders.

Uso:
    python -m agente.preparar 320193 --fecha 2026-10-19 --nombre "Tee de altura fija" \
        --archivos "golf tee.stl" --colores verde,blanco,rojo
    python -m agente.preparar propio:gate-de-putting --fecha 2026-10-26 --colores verde,blanco
    python -m agente.preparar makerworld:497253 --fecha 2026-10-26 --nombre "Arreglapiques con marcador"

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

from .buscar import CABECERAS, detalle, detalle_mw, gql, perfil_mw, texto_plano, url_mw
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
    """El render necesita STL/OBJ: los 3MF se convierten con PrusaSlicer (o a mano si PrusaSlicer no los abre,
    como los proyectos de Bambu Studio que vienen de MakerWorld)."""
    if ruta.suffix.lower() in (".stl", ".obj"):
        return ruta
    salida = ruta.with_suffix(".stl")
    r = subprocess.run(["prusa-slicer", "--export-stl", "-o", str(salida), str(ruta)], capture_output=True)
    if r.returncode != 0 or not salida.exists():
        tmf_a_stl(ruta, salida)
    return salida


def tmf_a_stl(ruta, salida):
    """Junta todas las mallas de un .3mf (incluye los 3D/Objects/*.model de Bambu) en un STL binario.
    Aplica la transformación de cada componente y de cada pieza de la placa."""
    import struct
    import zipfile
    import xml.etree.ElementTree as ET

    def local(tag):
        return tag.rsplit("}", 1)[-1]

    def matriz(texto):
        if not texto:
            return None
        v = [float(x) for x in texto.split()]  # 3MF: m00 m01 m02 m10 m11 m12 m20 m21 m22 m30 m31 m32
        return [[v[0], v[3], v[6], v[9]], [v[1], v[4], v[7], v[10]], [v[2], v[5], v[8], v[11]]]

    def aplicar(m, p):
        return p if m is None else tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3))

    def componer(a, b):  # primero b, después a
        if a is None or b is None:
            return a or b
        return [[sum(a[i][k] * b[k][j] for k in range(3)) + (a[i][3] if j == 3 else 0) for j in range(4)]
                for i in range(3)]

    with zipfile.ZipFile(ruta) as z:
        modelos = {"/" + n: ET.fromstring(z.read(n)) for n in z.namelist() if n.lower().endswith(".model")}
    objetos = {}  # (archivo, id) -> elemento <object>
    for archivo, raiz in modelos.items():
        for o in raiz.iter():
            if local(o.tag) == "object":
                objetos[(archivo, o.get("id"))] = o

    triangulos = []

    def volcar(archivo, oid, m, profundidad=0):
        o = objetos.get((archivo, oid))
        if o is None or profundidad > 8:
            return
        for hijo in o:
            if local(hijo.tag) == "mesh":
                vertices, tris = [], []
                for e in hijo.iter():
                    if local(e.tag) == "vertex":
                        vertices.append(aplicar(m, (float(e.get("x")), float(e.get("y")), float(e.get("z")))))
                    elif local(e.tag) == "triangle":
                        tris.append((int(e.get("v1")), int(e.get("v2")), int(e.get("v3"))))
                triangulos.extend((vertices[a], vertices[b], vertices[c]) for a, b, c in tris)
            elif local(hijo.tag) == "components":
                for c in hijo:
                    destino = next((v for k, v in c.attrib.items() if local(k) == "path"), None) or archivo
                    volcar(destino, c.get("objectid"), componer(m, matriz(c.get("transform"))), profundidad + 1)

    principal = next((a for a in modelos if a.lower().endswith("3dmodel.model")), next(iter(modelos)))
    items = [e for e in modelos[principal].iter() if local(e.tag) == "item"]
    for it in items:
        volcar(principal, it.get("objectid"), matriz(it.get("transform")))
    if not triangulos:
        raise RuntimeError(f"No encontré mallas en {ruta.name}")
    with open(salida, "wb") as f:
        f.write(b"GolfCraft3D".ljust(80, b" "))
        f.write(struct.pack("<I", len(triangulos)))
        for t in triangulos:
            f.write(struct.pack("<12fH", 0, 0, 0, *t[0], *t[1], *t[2], 0))


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


def foto_mw(url, destino, vertical):
    """Recorta al centro una foto de MakerWorld a 1080x1350 (portada) o 1080x1080."""
    tmp = descargar(url, destino.with_suffix(".orig"))
    im = Image.open(tmp).convert("RGB")
    tam = (1080, 1350) if vertical else (1080, 1080)
    escala = max(tam[0] / im.width, tam[1] / im.height)
    im = im.resize((round(im.width * escala), round(im.height * escala)), Image.LANCZOS)
    x, y = (im.width - tam[0]) // 2, (im.height - tam[1]) // 2
    im.crop((x, y, x + tam[0], y + tam[1])).save(destino, "JPEG", quality=88)
    tmp.unlink()


def preparar_makerworld(design_id, fecha, nombre=None, colores=None):
    """Modelo de MakerWorld: sin descarga (pide cuenta). Gramos y tiempo del perfil publicado; las fotos son
    las del autor y solo sirven para la propuesta privada (mail/Telegram), nunca se publican.
    Si se aprueba, el dueño baja el archivo y se lo manda al bot (agente/makerworld.py)."""
    d = detalle_mw(design_id)
    perfil = perfil_mw(d)
    if not perfil:
        sys.exit(f"El modelo {design_id} de MakerWorld no tiene perfil con gramos")
    nombre = nombre or d["title"]
    carpeta = RAIZ / "propuestas" / fecha / slug(nombre)
    (carpeta / "fotos").mkdir(parents=True, exist_ok=True)
    urls = [d.get("coverUrl")] + [f["url"] for f in d["designExtension"].get("design_pictures") or []]
    urls = list(dict.fromkeys(u for u in urls if u))[:4]
    colores = colores or ["negro", "blanco", "verde"]
    fotos = []
    for n, url in enumerate(urls, 1):
        foto_mw(url, carpeta / "fotos" / f"{n}.jpg", vertical=(n == 1))
        fotos.append({"archivo": f"{n}.jpg", "color": colores[(n - 1) % len(colores)]})
    gramos, minutos = float(perfil["weight"]), (perfil.get("prediction") or 0) / 60
    costo, final = precio(gramos)
    ficha = {
        "nombre": nombre,
        "nombre_original": d["title"],
        "descripcion": texto_plano(d.get("summary"))[:600],
        "origen": "makerworld",
        "printables_id": None,
        "makerworld_id": d["id"],
        "url": url_mw(d),
        "autor": d["designCreator"]["name"],
        "licencia": d["license"],
        "licencia_nombre": (d.get("licenseDescriptionInfo") or {}).get("title") or d["license"],
        "piezas": [],
        "archivo_pendiente": True,
        "gramos": round(gramos, 1),
        "tiempo_min": round(minutos),
        "tiempo": formato_tiempo(minutos),
        "costo_filamento": costo,
        "precio": final,
        "material": CONFIG["produccion"]["material"],
        "colores_render": colores,
        "fotos": fotos,
        "estimacion": f"Gramos y tiempo del perfil publicado en MakerWorld ({perfil.get('title')}). Las fotos son "
                      "del autor: si se aprueba, se rehacen con nuestros renders cuando llegue el archivo.",
    }
    (carpeta / "ficha.yaml").write_text(yaml.safe_dump(ficha, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return carpeta, ficha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("printables_id", help="id de Printables, propio:<carpeta de disenos/> o makerworld:<id>")
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
    elif a.printables_id.startswith("makerworld:"):
        carpeta, ficha = preparar_makerworld(a.printables_id.split(":", 1)[1], a.fecha, a.nombre, colores)
    else:
        carpeta, ficha = preparar(a.printables_id, a.fecha, a.nombre,
                                  a.archivos.split("|") if a.archivos else None, colores, a.muestras)
    print(f"{carpeta.relative_to(RAIZ)}: {ficha['gramos']} g, {ficha['tiempo']}, precio ${ficha['precio']}")


if __name__ == "__main__":
    main()
