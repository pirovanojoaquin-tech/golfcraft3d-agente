"""Imagen "en uso": el producto real montado sobre una foto de Unsplash, a partir de la receta de info.yaml.

Uso (lo corre el workflow en-uso.yml; necesita blender y prusa-slicer):
    python -m agente.en_uso <carpeta de productos/> [--color rojo] [--muestras 32]

Receta en productos/<slug>/info.yaml (la arma el agente una vez por producto, ver AGENTE.md):
    en_uso:
      foto: {id: gcZcCqpGEw0, nombre: gorra-beige}   # foto de Unsplash (fondos/<nombre>.jpg)
      escena: gorra                                  # escena de agente/escenas.py
      params: {para_foto: true}                      # parámetros de la escena
      angulo: 40                                     # elevación de la cámara
      giro: -160                                     # giro de la cámara
      margen: 1.25
      punto: [2075, 1900]                            # dónde cae el apoyo del producto en la foto (px)
      escala: 1.1                                    # tamaño del render sobre la foto
      recorte: [300, 500, 2400, 3125]                # recorte final (idealmente 4:5)
Deja productos/<slug>/fotos/en-uso.jpg (y en-uso-<color>.jpg si se pide otro color).
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import yaml
from PIL import Image

from . import montaje
from .calendario import RAIZ
from .preparar import CONFIG
from .renders import stl_del_producto


def generar(slug, color=None, muestras=32):
    carpeta = RAIZ / "productos" / slug
    info = yaml.safe_load((carpeta / "info.yaml").read_text(encoding="utf-8"))
    receta = info.get("en_uso")
    if not receta:
        raise SystemExit(f"{slug} no tiene receta en_uso en info.yaml")
    foto = RAIZ / "fondos" / f"{receta['foto']['nombre']}.jpg"
    if not foto.exists():
        raise SystemExit(f"Falta {foto.relative_to(RAIZ)}: bajala antes con el workflow banco.yml (descargar)")
    color = color or (info.get("colores") or ["verde"])[0]
    with tempfile.TemporaryDirectory() as tmp:
        render = Path(tmp) / "render.png"
        cmd = ["blender", "-b", "-P", str(RAIZ / "agente" / "render.py"), "--", str(stl_del_producto(info)), str(render),
               "--color", CONFIG["colores"][color], "--angulo", str(receta["angulo"]), "--giro", str(receta["giro"]),
               "--tam", "1000", "--muestras", str(muestras), "--escena", receta["escena"],
               "--escena-params", json.dumps(receta.get("params", {})), "--margen", str(receta.get("margen", 1.25)),
               "--sin-piso", "--transparente", "--luz-relativa"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if not render.exists():
            raise RuntimeError(f"Falló el render: {r.stdout[-800:]}")
        ancla = json.loads(Path(str(render) + ".json").read_text())["ancla"]
        im = montaje.montar(Image.open(foto), Image.open(render), ancla, receta["punto"], receta.get("escala", 1.0),
                            grano=receta.get("grano", 2))
    if receta.get("recorte"):
        im = im.crop(tuple(receta["recorte"]))
    nombre = "en-uso.jpg" if color == (info.get("colores") or ["verde"])[0] else f"en-uso-{color}.jpg"
    destino = carpeta / "fotos" / nombre
    im.save(destino, quality=92)
    print(f"{slug}: {destino.relative_to(RAIZ)}")
    return destino


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--color")
    ap.add_argument("--muestras", type=int, default=32)
    a = ap.parse_args()
    generar(a.slug, a.color, a.muestras)


if __name__ == "__main__":
    main()
