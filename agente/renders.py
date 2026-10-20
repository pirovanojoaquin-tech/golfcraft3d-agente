"""Imágenes "de catálogo" de un producto aprobado: renders sin fondo para las plantillas nuevas.

Uso (lo corre el workflow renders.yml en GitHub; necesita blender y prusa-slicer):
    python -m agente.renders <carpeta de productos/> [--muestras 48]

Genera en productos/<slug>/fotos/png/:
    <color>.png        el producto en 6 colores del stock, sin fondo (para la tabla de colores)
    hero.png           vista principal con una pelota de golf a escala, sin fondo
    detalle.png        vista de arriba, sin fondo
    ml-<vista>.png     vistas para Mercado Libre (frente, lateral, arriba, atras), color principal
y agrega `medidas_mm` (largo, ancho, alto) a productos/<slug>/info.yaml.
"""
import argparse
import re
import subprocess

import yaml

from .calendario import RAIZ
from .preparar import CONFIG, DESCARGAS, a_stl, descargar, link_descarga

# (elevación, giro) de las vistas extra para las fotos de Mercado Libre
VISTAS_ML = {"frente": (10, 0), "angulo": (45, -40), "arriba": (89, 0), "atras": (35, 215)}
ORDEN_COLORES = ["negro", "blanco", "rojo", "azul", "verde", "amarillo", "cian", "gris", "piel", "marroncito"]


def stl_del_producto(info):
    pieza = info["piezas"][0]
    if pieza.get("ruta"):
        return RAIZ / pieza["ruta"]
    destino = DESCARGAS / str(info["printables_id"]) / pieza["archivo"]
    if not destino.exists():
        descargar(link_descarga(info["printables_id"], pieza["printables_file_id"]), destino)
    return a_stl(destino)


def medidas(stl):
    r = subprocess.run(["prusa-slicer", "--info", str(stl)], capture_output=True, text=True)
    m = {k: float(v) for k, v in re.findall(r"size_([xyz]) = ([\d.]+)", r.stdout)}
    largo, ancho = sorted([m.get("x", 0), m.get("y", 0)], reverse=True)
    return {"largo": round(largo), "ancho": round(ancho), "alto": round(m.get("z", 0))}


def render(stl, destino, color, angulo, giro, muestras, pelota=False):
    cmd = ["blender", "-b", "-P", str(RAIZ / "agente" / "render.py"), "--", str(stl), str(destino),
           "--color", CONFIG["colores"][color], "--angulo", str(angulo), "--giro", str(giro),
           "--tam", "1080", "--muestras", str(muestras), "--transparente"]
    if pelota:
        cmd.append("--pelota")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not destino.exists():
        raise RuntimeError(f"Falló el render {destino.name}: {r.stdout[-500:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--muestras", type=int, default=48)
    ap.add_argument("--solo-ml", action="store_true", help="solo las vistas de Mercado Libre que falten")
    a = ap.parse_args()
    carpeta = RAIZ / "productos" / a.slug
    info = yaml.safe_load((carpeta / "info.yaml").read_text(encoding="utf-8"))
    stl = stl_del_producto(info)
    salida = carpeta / "fotos" / "png"
    salida.mkdir(parents=True, exist_ok=True)

    principal = (info.get("colores") or ["verde"])[0]
    for vista, (ang, giro) in VISTAS_ML.items():
        if not (salida / f"ml-{vista}.png").exists():
            render(stl, salida / f"ml-{vista}.png", principal, ang, giro, a.muestras)
    if a.solo_ml and info.get("medidas_mm"):
        return
    colores = list(dict.fromkeys((info.get("colores") or []) + ORDEN_COLORES))[:6]
    render(stl, salida / "hero.png", principal, 26, 35, a.muestras, pelota=True)
    render(stl, salida / "detalle.png", principal, 70, 15, a.muestras)
    for c in colores:
        render(stl, salida / f"{c}.png", c, 30, 35, a.muestras)

    info["medidas_mm"] = medidas(stl)
    info["colores_png"] = colores
    (carpeta / "info.yaml").write_text(yaml.safe_dump(info, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"{a.slug}: {len(colores) + 2 + len(VISTAS_ML)} renders, medidas {info['medidas_mm']}")


if __name__ == "__main__":
    main()
