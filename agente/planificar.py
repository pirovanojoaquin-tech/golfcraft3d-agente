"""Convierte un plan semanal (YAML) en imágenes listas + entradas del calendario.

Uso:
    python -m agente.planificar planes/2026-10-20.yaml

Formato del plan: ver planes/EJEMPLO.yaml
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

from . import calendario, disenio

RAIZ = disenio.RAIZ
CONFIG = disenio.CONFIG
PRODUCTOS = RAIZ / "productos"


def producto(slug):
    carpeta = PRODUCTOS / slug
    info = carpeta / "info.yaml"
    if not info.exists():
        sys.exit(f"No existe el producto '{slug}' (falta {info.relative_to(RAIZ)})")
    datos = yaml.safe_load(info.read_text(encoding="utf-8")) or {}
    datos["carpeta"] = carpeta
    return datos


def foto(slug, nombre):
    ruta = PRODUCTOS / slug / "fotos" / nombre
    if not ruta.exists():
        sys.exit(f"No existe la foto {ruta.relative_to(RAIZ)}")
    return disenio.cargar_foto(ruta)


def png(slug, nombre):
    """Render sin fondo de productos/<slug>/fotos/png/ (lo genera agente/renders.py)."""
    ruta = PRODUCTOS / slug / "fotos" / "png" / nombre
    if not ruta.exists():
        sys.exit(f"No existe {ruta.relative_to(RAIZ)} (corré el workflow renders.yml para ese producto)")
    return ruta


def en_ml(slug):
    """True si el producto ya se vende en Mercado Libre (el cierre manda a la tienda de la bio)."""
    import json
    estado = RAIZ / "contenido" / "mercadolibre.json"
    p = json.loads(estado.read_text(encoding="utf-8")).get("productos", {}).get(slug, {}) if estado.exists() else {}
    return p.get("estado") == "publicado" and bool(p.get("link"))


def color_principal(slug):
    return (producto(slug).get("colores") or ["verde"])[0]


def armar_caption(texto):
    texto = texto.strip()
    existentes = {h.lower() for h in re.findall(r"#\w+", texto)}
    faltan = [h for h in CONFIG["hashtags_base"] if h.lower() not in existentes]
    if faltan:
        texto += ("\n" if existentes else "\n\n") + " ".join(faltan)
    if len(texto) > 2200:
        sys.exit(f"Caption demasiado largo ({len(texto)} > 2200 caracteres)")
    if len(re.findall(r"#\w+", texto)) > 30:
        sys.exit("Instagram permite como máximo 30 hashtags")
    return texto


def render_slide(s, slug_default):
    slug = s.get("producto", slug_default)
    tipo = s["tipo"]
    if tipo == "portada":
        return disenio.slide_portada(foto(slug, s["foto"]), s["titulo"], s.get("subtitulo"), s.get("etiqueta"))
    if tipo == "foto":
        return disenio.slide_foto(foto(slug, s["foto"]))
    if tipo == "info":
        return disenio.slide_info(s["titulo"], s["items"])
    if tipo == "cta":
        return disenio.slide_cta(s.get("nombre_corto"))
    # estilo catálogo (renders sin fondo de fotos/png/)
    tono = s.get("tono") or disenio.tono_para(color_principal(slug))
    if tipo == "hero":
        return disenio.slide_hero(png(slug, s.get("png", "hero.png")), s["titulo"], s.get("subtitulo"),
                                  s.get("etiqueta"), tono, s.get("sellos", disenio.SELLOS))
    if tipo == "colores":
        info = producto(slug)
        colores = info.get("colores_png") or sys.exit(f"{slug} no tiene renders por color (renders.yml)")
        return disenio.slide_colores([(png(slug, f"{c}.png"), c) for c in colores], s.get("titulo", "Elegí tu color"))
    if tipo == "medidas":
        info = producto(slug)
        if "medidas_mm" not in info:
            sys.exit(f"{slug} no tiene medidas_mm (renders.yml)")
        return disenio.slide_medidas(png(slug, s.get("png", "detalle.png")), info["medidas_mm"], info["gramos"],
                                     s.get("tono", "crema"), s.get("titulo", "Medidas reales"))
    if tipo == "pasos":
        return disenio.slide_pasos(s["titulo"], s["pasos"], png(slug, s.get("png", "hero.png")),
                                   s.get("tono", "verde"))
    if tipo == "cta_producto":
        return disenio.slide_cta_producto(png(slug, s.get("png", "hero.png")), s.get("nombre_corto"), en_ml(slug))
    sys.exit(f"Tipo de slide desconocido: {tipo}")


def render_historia(h):
    tipo = h["tipo"]
    if tipo == "foto":
        return disenio.historia_foto(foto(h["producto"], h["foto"]), h["titulo"], h.get("subtitulo"), h.get("etiqueta"))
    if tipo == "texto":
        return disenio.historia_texto(h["titulo"], h["texto"], h.get("etiqueta"))
    if tipo == "hero":
        tono = h.get("tono") or disenio.tono_para(color_principal(h["producto"]))
        return disenio.historia_hero(png(h["producto"], h.get("png", "hero.png")), h["titulo"], h.get("subtitulo"),
                                     h.get("etiqueta"), tono)
    sys.exit(f"Tipo de historia desconocido: {tipo}")


def procesar(plan, reemplazar=False):
    items = calendario.cargar()
    horarios = CONFIG["horarios"]
    nuevos = []
    for dia in plan["dias"]:
        fecha = str(dia["fecha"])
        carpeta = RAIZ / "contenido" / "media" / fecha
        rel = lambda p: p.relative_to(RAIZ).as_posix()

        if "post" in dia:
            p = dia["post"]
            producto(p["producto"])
            rutas = []
            for n, s in enumerate(p["slides"], 1):
                rutas.append(rel(disenio.guardar(render_slide(s, p["producto"]), carpeta / f"post-{n}.jpg")))
            nuevos.append({
                "id": f"{fecha}-post", "fecha": fecha, "hora": horarios["post"],
                "tipo": "CAROUSEL" if len(rutas) > 1 else "IMAGE",
                "producto": p["producto"], "imagenes": rutas,
                "caption": armar_caption(p["caption"]), "estado": "pendiente",
            })

        for n, h in enumerate(dia.get("historias", []), 1):
            ruta = rel(disenio.guardar(render_historia(h), carpeta / f"historia-{n}.jpg"))
            nuevos.append({
                "id": f"{fecha}-historia-{n}", "fecha": fecha, "hora": horarios[f"historia-{n}"],
                "tipo": "STORY", "producto": h.get("producto"), "imagenes": [ruta],
                "estado": "pendiente",
            })

    ids_nuevos = {n["id"] for n in nuevos}
    choques = [i["id"] for i in items if i["id"] in ids_nuevos]
    publicados = [i["id"] for i in items if i["id"] in ids_nuevos and i["estado"] == "publicado"]
    if publicados:
        sys.exit(f"Estas entradas ya se publicaron, no se pueden reemplazar: {publicados}")
    if choques and not reemplazar:
        sys.exit(f"Ya hay entradas con estos ids (usá --reemplazar): {choques}")
    items = [i for i in items if i["id"] not in ids_nuevos] + nuevos
    calendario.guardar(items)
    return nuevos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--reemplazar", action="store_true", help="pisa entradas pendientes con el mismo id")
    args = ap.parse_args()
    plan = yaml.safe_load(Path(args.plan).read_text(encoding="utf-8"))
    nuevos = procesar(plan, args.reemplazar)
    for n in nuevos:
        print(f"{n['id']:<24} {n['hora']}  {n['tipo']:<8} {len(n['imagenes'])} img")


if __name__ == "__main__":
    main()
