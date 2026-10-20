"""Fotos para Mercado Libre: fondo blanco, 1200x1200, distintas a las de Instagram.

Uso:
    python -m agente.fotos_ml <carpeta de productos/> [--pack 3]

Usa los renders sin fondo de productos/<slug>/fotos/png/ (agente/renders.py) y deja en
productos/<slug>/fotos/ml/:
    1-portada.jpg     el producto (o las N unidades del pack) sin texto, como pide ML para la portada
    2-frente.jpg ...  vistas desde distintos ángulos
    6-medidas.jpg     vista de arriba y de frente con las medidas (no en productos de varias piezas)
    7-colores.jpg     el producto en 6 colores con sus nombres
    color-<c>.jpg     una por color, para las variantes de la publicación
"""
import argparse
import math

import yaml
from PIL import Image, ImageDraw

from .disenio import RAIZ, fuente, recortar

TAM = 1200
BLANCO = (255, 255, 255)
GRIS = (60, 66, 63)
VERDE = (1, 96, 64)
VISTAS = ["frente", "angulo", "arriba", "atras"]


def lienzo():
    return Image.new("RGBA", (TAM, TAM), BLANCO + (255,))


def nucleo(prod):
    """Caja del producto sin la sombra suave."""
    return prod.getchannel("A").point(lambda a: 255 if a > 150 else 0).getbbox() or (0, 0, *prod.size)


def pegar(im, png, caja):
    """Pega el producto encuadrado por su contorno dentro de caja=(x, y, w, h). Devuelve su caja final."""
    prod = recortar(png)
    nx0, ny0, nx1, ny1 = nucleo(prod)
    x, y, w, h = caja
    esc = min(w / (nx1 - nx0), h / (ny1 - ny0))
    prod = prod.resize((round(prod.width * esc), round(prod.height * esc)), Image.LANCZOS)
    px = round(x + (w - (nx1 - nx0) * esc) / 2 - nx0 * esc)
    py = round(y + (h - (ny1 - ny0) * esc) / 2 - ny0 * esc)
    capa = Image.new("RGBA", im.size, (0, 0, 0, 0))
    capa.paste(prod, (px, py))
    im.alpha_composite(capa)
    return (px + nx0 * esc, py + ny0 * esc, px + nx1 * esc, py + ny1 * esc)


def guardar(im, ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(ruta, quality=92)
    return ruta


def portada(png, unidades=1):
    """Una unidad grande, o las N del pack acomodadas en grilla."""
    im = lienzo()
    if unidades == 1:
        pegar(im, png, (90, 90, TAM - 180, TAM - 180))
        return im
    nx0, ny0, nx1, ny1 = nucleo(recortar(png))
    w, h = nx1 - nx0, ny1 - ny0
    # la grilla que deja cada unidad más grande (productos largos van apilados)
    cols = max(range(1, unidades + 1),
               key=lambda c: min((TAM - 140) / c / w, (TAM - 140) / math.ceil(unidades / c) / h))
    filas = math.ceil(unidades / cols)
    margen, cw, ch = 70, (TAM - 140) / cols, (TAM - 140) / filas
    for n in range(unidades):
        f, c = divmod(n, cols)
        en_fila = min(cols, unidades - f * cols)
        x0 = margen + (cols - en_fila) * cw / 2  # centra la última fila si queda incompleta
        pegar(im, png, (round(x0 + c * cw + 12), round(margen + f * ch + 12), round(cw - 24), round(ch - 24)))
    return im


def flecha(d, a, b, texto, lado):
    """Cota con flechas de a a b y el texto al costado (lado: 'abajo' o 'derecha')."""
    d.line([a, b], fill=GRIS, width=4)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for p, s in ((a, 1), (b, -1)):
        for g in (0.45, -0.45):
            d.line([p, (p[0] + s * 22 * math.cos(ang + g), p[1] + s * 22 * math.sin(ang + g))], fill=GRIS, width=4)
    f = fuente(40, 800)
    medio = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if lado == "abajo":
        d.text((medio[0], medio[1] + 40), texto, font=f, fill=VERDE, anchor="mm")
    else:
        d.text((medio[0] + 24, medio[1]), texto, font=f, fill=VERDE, anchor="lm")


def medidas(arriba, frente, m):
    """Vista de arriba (largo x ancho) y de frente (alto) con cotas."""
    im = lienzo()
    d = ImageDraw.Draw(im)
    d.text((TAM / 2, 70), "Medidas", font=fuente(56, 800), fill=VERDE, anchor="mm")
    x0, y0, x1, y1 = pegar(im, arriba, (140, 150, TAM - 420, 560))
    d = ImageDraw.Draw(im)
    horizontal, vertical = (m["largo"], m["ancho"]) if x1 - x0 >= y1 - y0 else (m["ancho"], m["largo"])
    flecha(d, (x0, y1 + 30), (x1, y1 + 30), f"{horizontal} mm", "abajo")
    flecha(d, (x1 + 30, y0), (x1 + 30, y1), f"{vertical} mm", "derecha")
    fx0, fy0, fx1, fy1 = pegar(im, frente, (140, 830, TAM - 420, 260))
    d = ImageDraw.Draw(im)
    flecha(d, (fx1 + 30, fy0), (fx1 + 30, fy1), f"{m['alto']} mm", "derecha")
    d.text((TAM / 2, TAM - 50), "Medidas aproximadas", font=fuente(30, 600), fill=GRIS, anchor="mm")
    return im


def colores(items):
    """items: [(png, nombre)] hasta 6, en grilla de 3x2."""
    im = lienzo()
    d = ImageDraw.Draw(im)
    d.text((TAM / 2, 80), "Colores disponibles", font=fuente(56, 800), fill=VERDE, anchor="mm")
    cw, ch = (TAM - 120) / 3, (TAM - 200) / 2
    for n, (png, nombre) in enumerate(items[:6]):
        f, c = divmod(n, 3)
        x, y = 60 + c * cw, 150 + f * ch
        pegar(im, png, (round(x + 20), round(y + 10), round(cw - 40), round(ch - 110)))
        ImageDraw.Draw(im).text((x + cw / 2, y + ch - 60), nombre.capitalize(), font=fuente(40, 700), fill=GRIS,
                                anchor="mm")
    return im


def generar(slug, pack=1):
    carpeta = RAIZ / "productos" / slug
    info = yaml.safe_load((carpeta / "info.yaml").read_text(encoding="utf-8"))
    png = carpeta / "fotos" / "png"
    salida = carpeta / "fotos" / "ml"
    principal = (info.get("colores") or ["verde"])[0]
    lista = info.get("colores_png") or [principal]
    rutas = [guardar(portada(png / f"{principal}.png", pack), salida / "1-portada.jpg")]
    en_uso = carpeta / "fotos" / "en-uso.jpg"
    if en_uso.exists():
        # la foto en uso va segunda: ML pide la portada con fondo blanco
        im = Image.open(en_uso).convert("RGB")
        lado = min(im.size)
        im = im.crop(((im.width - lado) // 2, (im.height - lado) // 2, (im.width + lado) // 2, (im.height + lado) // 2))
        rutas.append(guardar(im.resize((TAM, TAM), Image.LANCZOS), salida / "1b-en-uso.jpg"))
    for n, vista in enumerate(VISTAS, 2):
        rutas.append(guardar(portada(png / f"ml-{vista}.png"), salida / f"{n}-{vista}.jpg"))
    if info.get("medidas_mm") and len(info.get("piezas", [])) == 1:
        rutas.append(guardar(medidas(png / "ml-arriba.png", png / "ml-frente.png", info["medidas_mm"]),
                             salida / "6-medidas.jpg"))
    rutas.append(guardar(colores([(png / f"{c}.png", c) for c in lista]), salida / "7-colores.jpg"))
    variantes = {c: guardar(portada(png / f"{c}.png", pack), salida / f"color-{c}.jpg") for c in lista}
    return rutas, variantes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--pack", type=int, default=1)
    a = ap.parse_args()
    rutas, variantes = generar(a.slug, a.pack)
    print(f"{a.slug}: {len(rutas)} fotos + {len(variantes)} variantes de color")


if __name__ == "__main__":
    main()
