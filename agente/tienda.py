"""Página de tienda de GolfCraft3D (GitHub Pages): vidriera con todos los productos y botón a Mercado Libre.

Uso (lo corre el workflow tienda.yml cada vez que cambia un producto o una publicación de ML):
    python -m agente.tienda [--salida sitio]

Lee productos/*/info.yaml, los renders sin fondo de fotos/png/ y los links de contenido/mercadolibre.json,
y genera un sitio estático (index.html + imágenes webp) en `sitio/`. El link de esta página va en la bio de Instagram.
"""
import argparse
import json
import shutil
import time
from html import escape
from pathlib import Path

import yaml
from PIL import Image

from .calendario import RAIZ
from .disenio import recortar

CONFIG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
USUARIO_IG = CONFIG["marca"]["usuario"].lstrip("@")
DM = f"https://ig.me/m/{USUARIO_IG}"
PLANTILLA = RAIZ / "agente" / "plantillas" / "tienda.html"

CATEGORIAS = [  # (categoría, palabras del slug); la primera que coincide gana. info.yaml > categoria la pisa.
    ("Regalos", ("trofeo", "secreto", "regalo")),
    ("Entrenamiento", ("entrenador", "guia", "arco", "alineacion", "putting", "swing")),
    ("Accesorios", ("",)),
]


def categoria(slug, info):
    if info.get("categoria"):
        return info["categoria"]
    return next(c for c, claves in CATEGORIAS if any(k in slug for k in claves))


def webp(origen, destino, ancho):
    im = recortar(origen)
    # sombra más suave que en Instagram: en la web, sobre fondo claro, se ve como mancha
    alfa = im.getchannel("A").point(lambda v: v if v > 200 else int(v * 0.5))
    im.putalpha(alfa)
    im.thumbnail((ancho, ancho), Image.LANCZOS)
    destino.parent.mkdir(parents=True, exist_ok=True)
    im.save(destino, "WEBP", quality=82, method=6)


def precio(plata):
    return "$" + f"{round(plata):,}".replace(",", ".")


def productos(salida):
    ml = {}
    estado_ml = RAIZ / "contenido" / "mercadolibre.json"
    if estado_ml.exists():
        ml = json.loads(estado_ml.read_text(encoding="utf-8")).get("productos", {})
    aprobados = {}
    propuestos = RAIZ / "productos" / "propuestos.json"
    if propuestos.exists():
        aprobados = {p["slug"]: p.get("respondido") for p in json.loads(propuestos.read_text(encoding="utf-8"))
                     if p.get("estado") == "aprobado"}
    # "Nuevo" = el último lote aprobado (si hay más de un lote)
    ultimo = max(aprobados.values()) if len(set(aprobados.values())) > 1 else None
    lista = []
    for info_yaml in sorted((RAIZ / "productos").glob("*/info.yaml")):
        slug = info_yaml.parent.name
        png = info_yaml.parent / "fotos" / "png"
        if slug.startswith("_") or not (png / "hero.png").exists():
            continue
        info = yaml.safe_load(info_yaml.read_text(encoding="utf-8"))
        colores = [c for c in (info.get("colores_png") or []) if (png / f"{c}.png").exists()]
        for c in colores:
            webp(png / f"{c}.png", salida / "img" / slug / f"{c}.webp", 720)
        p = ml.get(slug, {})
        en_ml = p.get("estado") == "publicado" and p.get("link")
        fila = next((x for x in p.get("calculo", []) if x["pack"] == p.get("pack")), None)
        nuevo = ultimo is not None and aprobados.get(slug) == ultimo
        lista.append({
            "slug": slug, "nombre": info["nombre"], "descripcion": (info.get("descripcion") or "").strip(),
            "categoria": categoria(slug, info),
            "colores": [{"nombre": c, "hex": CONFIG["colores"][c]} for c in colores],
            "propio": info.get("origen") == "propio", "nuevo": nuevo,
            "ml": p.get("link") if en_ml else None,
            "pack": p.get("pack") if en_ml else None,
            "precio": precio(fila["precio"]) if en_ml and fila else None,
        })
    # primero lo que se puede comprar en Mercado Libre, después lo nuevo
    lista.sort(key=lambda x: (x["ml"] is None, not x["nuevo"], x["nombre"]))
    return lista


def generar(salida):
    salida = Path(salida)
    if salida.exists():
        shutil.rmtree(salida)
    (salida / "img").mkdir(parents=True)
    datos = productos(salida)
    shutil.copy(RAIZ / "assets" / "logo.png", salida / "img" / "logo.png")
    shutil.copy(RAIZ / "assets" / "logo-blanco.png", salida / "img" / "logo-blanco.png")
    shutil.copy(RAIZ / "assets" / "fonts" / "Montserrat.ttf", salida / "Montserrat.ttf")
    html = PLANTILLA.read_text(encoding="utf-8")
    html = (html.replace("{{PRODUCTOS}}", json.dumps(datos, ensure_ascii=False).replace("</", "<\\/"))
                .replace("{{DM}}", escape(DM))
                .replace("{{IG}}", escape(f"https://instagram.com/{USUARIO_IG}"))
                .replace("{{USUARIO}}", escape(CONFIG["marca"]["usuario"]))
                .replace("{{ANIO}}", time.strftime("%Y")))
    (salida / "index.html").write_text(html, encoding="utf-8")
    (salida / ".nojekyll").write_text("")
    print(f"Tienda: {len(datos)} productos ({sum(1 for d in datos if d['ml'])} en Mercado Libre) -> {salida}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=str(RAIZ / "sitio"))
    generar(ap.parse_args().salida)


if __name__ == "__main__":
    main()
