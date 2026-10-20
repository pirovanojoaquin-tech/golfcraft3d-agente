"""Monta el render de un producto sobre una foto real (fondos/ de Unsplash) para las imágenes "en uso".

El render se hace con render.py --escena ... --sin-piso --transparente: así trae solo el producto, su
sombra sobre la superficie y un .json con el punto de apoyo ("ancla") en píxeles. Acá se escala, se
empareja con la foto (brillo, tono y grano) y se pega con el ancla sobre el punto indicado de la foto.

Uso:
    python -m agente.montaje fondos/gorra-beige.jpg render.png salida.jpg --punto 2070 1908 --escala 1.1 \
        [--recorte x0 y0 x1 y1] [--brillo 0.85] [--calidez 0.06] [--grano 5]
"""
import argparse
import json
import random

from PIL import Image, ImageChops, ImageEnhance, ImageFilter


def emparejar(render, brillo=0.85, calidez=0.06, grano=5.0, desenfoque=0.5):
    """Lleva el render (RGBA) al aspecto de una foto: menos brillo, tono cálido, grano y un toque de foco suave."""
    rgb, alfa = render.convert("RGB"), render.getchannel("A")
    rgb = ImageEnhance.Brightness(rgb).enhance(brillo)
    r, g, b = rgb.split()
    r = r.point(lambda v: min(255, v * (1 + calidez)))
    b = b.point(lambda v: v * (1 - calidez))
    rgb = Image.merge("RGB", (r, g, b))
    if desenfoque:
        rgb = rgb.filter(ImageFilter.GaussianBlur(desenfoque))
    if grano:
        # grano fino y monocromo, como el de la foto
        ruido = Image.effect_noise(rgb.size, grano * 3).filter(ImageFilter.GaussianBlur(0.6)).convert("RGB")
        rgb = ImageChops.add(rgb, ruido, 1, -128)
    out = rgb.convert("RGBA")
    out.putalpha(alfa)
    return out


def montar(foto, render, ancla, punto, escala=1.0, sombra=0.35, **ajustes):
    foto = foto.convert("RGBA")
    r = render.convert("RGBA").resize((round(render.width * escala), round(render.height * escala)), Image.LANCZOS)
    r = emparejar(r, **ajustes)
    pos = (round(punto[0] - ancla[0] * escala), round(punto[1] - ancla[1] * escala))
    if sombra:
        # sombra de contacto: la silueta desenfocada, un poco corrida hacia abajo a la derecha
        silueta = r.getchannel("A").point(lambda v: v * sombra).filter(ImageFilter.GaussianBlur(14 * escala))
        capa_s = Image.new("RGBA", foto.size, (0, 0, 0, 0))
        negro = Image.new("RGBA", r.size, (10, 8, 6, 255))
        negro.putalpha(silueta)
        capa_s.paste(negro, (pos[0] + round(8 * escala), pos[1] + round(12 * escala)))
        foto.alpha_composite(capa_s)
    capa = Image.new("RGBA", foto.size, (0, 0, 0, 0))
    capa.paste(r, pos)
    foto.alpha_composite(capa)
    return foto.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto")
    ap.add_argument("render")
    ap.add_argument("salida")
    ap.add_argument("--punto", type=float, nargs=2, required=True, help="dónde va el ancla en la foto (px)")
    ap.add_argument("--escala", type=float, default=1.0)
    ap.add_argument("--recorte", type=int, nargs=4, help="x0 y0 x1 y1 del resultado")
    ap.add_argument("--brillo", type=float, default=0.85)
    ap.add_argument("--calidez", type=float, default=0.06)
    ap.add_argument("--grano", type=float, default=5.0)
    a = ap.parse_args()
    ancla = json.load(open(a.render + ".json"))["ancla"]
    im = montar(Image.open(a.foto), Image.open(a.render), ancla, a.punto, a.escala,
                brillo=a.brillo, calidez=a.calidez, grano=a.grano)
    if a.recorte:
        im = im.crop(tuple(a.recorte))
    im.save(a.salida, quality=92)
    print(a.salida)


if __name__ == "__main__":
    main()
