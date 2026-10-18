"""Plantillas visuales de GolfCraft3D (carrusel 1080x1350 e historias 1080x1920)."""
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"
CONFIG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))

POST = (1080, 1350)
HISTORIA = (1080, 1920)


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


VERDE = _hex(CONFIG["marca"]["color_principal"])
CREMA = _hex(CONFIG["marca"]["color_claro"])
TEXTO = _hex(CONFIG["marca"]["color_texto"])
BLANCO = (255, 255, 255)
USUARIO = CONFIG["marca"]["usuario"]
CTA = CONFIG["marca"]["cta"]


def fuente(tamanio, peso=700):
    f = ImageFont.truetype(str(ASSETS / "fonts" / "Montserrat.ttf"), tamanio)
    f.set_variation_by_axes([peso])
    return f


def logo(ancho, blanco=False):
    im = Image.open(ASSETS / ("logo-blanco.png" if blanco else "logo.png")).convert("RGBA")
    return im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)


def cargar_foto(ruta):
    return ImageOps.exif_transpose(Image.open(ruta)).convert("RGB")


def encajar(foto, tamanio):
    """Mete la foto entera en `tamanio`, rellenando con una versión desenfocada de sí misma."""
    w, h = tamanio
    fondo = ImageOps.fit(foto, tamanio, Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    fondo = Image.blend(fondo, Image.new("RGB", tamanio, (0, 0, 0)), 0.15)
    escala = min(w / foto.width, h / foto.height)
    chica = foto.resize((round(foto.width * escala), round(foto.height * escala)), Image.LANCZOS)
    fondo.paste(chica, ((w - chica.width) // 2, (h - chica.height) // 2))
    return fondo


def _lineas(draw, texto, f, ancho_max):
    lineas = []
    for parrafo in texto.split("\n"):
        actual = ""
        for palabra in parrafo.split():
            prueba = f"{actual} {palabra}".strip()
            if draw.textlength(prueba, font=f) <= ancho_max:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = palabra
        lineas.append(actual)
    return lineas


def texto_bloque(draw, xy, texto, f, color, ancho_max, interlineado=1.2, centrado=False):
    """Dibuja texto con salto de línea automático. Devuelve la y final."""
    x, y = xy
    alto = round(f.size * interlineado)
    for linea in _lineas(draw, texto, f, ancho_max):
        dx = (ancho_max - draw.textlength(linea, font=f)) / 2 if centrado else 0
        draw.text((x + dx, y), linea, font=f, fill=color)
        y += alto
    return y


def alto_texto(draw, texto, f, ancho_max, interlineado=1.2):
    return len(_lineas(draw, texto, f, ancho_max)) * round(f.size * interlineado)


def ajustar_fuente(draw, texto, ancho_max, alto_max, inicial, minimo=40, peso=800, interlineado=1.15):
    """Achica la fuente hasta que el texto entre en la caja."""
    tam = inicial
    while tam > minimo:
        f = fuente(tam, peso)
        if len(_lineas(draw, texto, f, ancho_max)) * tam * interlineado <= alto_max:
            return f
        tam -= 4
    return fuente(minimo, peso)


def pastilla(draw, xy, texto, f, fondo, color, pad=(28, 14), centro=False):
    x, y = xy
    w = draw.textlength(texto, font=f) + pad[0] * 2
    h = f.size + pad[1] * 2
    if centro:
        x -= w / 2
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h / 2, fill=fondo)
    draw.text((x + pad[0], y + pad[1] - f.size * 0.08), texto, font=f, fill=color)
    return y + h


def _degradado_inferior(im, desde, opacidad=210):
    w, h = im.size
    capa = Image.new("L", (1, h), 0)
    for y in range(desde, h):
        capa.putpixel((0, y), round(opacidad * (y - desde) / (h - desde)))
    capa = capa.resize((w, h))
    negro = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(negro, im, capa)


# ---------- Carrusel (1080x1350) ----------

def slide_portada(foto, titulo, subtitulo=None, etiqueta=None):
    im = encajar(foto, POST)
    im = _degradado_inferior(im, 700)
    d = ImageDraw.Draw(im)
    if etiqueta:
        pastilla(d, (60, 60), etiqueta.upper(), fuente(30, 700), VERDE, BLANCO)
    y_texto = 1350 - 90
    f_sub = fuente(38, 500)
    if subtitulo:
        lineas_sub = _lineas(d, subtitulo, f_sub, 960)
        y_texto -= len(lineas_sub) * round(38 * 1.25)
    f_tit = ajustar_fuente(d, titulo, 960, 320, 92)
    n = len(_lineas(d, titulo, f_tit, 960))
    y = y_texto - n * round(f_tit.size * 1.1) - 10
    y = texto_bloque(d, (60, y), titulo, f_tit, BLANCO, 960, 1.1)
    if subtitulo:
        texto_bloque(d, (60, y + 10), subtitulo, f_sub, (235, 235, 235), 960, 1.25)
    return im


def slide_foto(foto):
    return encajar(foto, POST)


def slide_info(titulo, items):
    im = Image.new("RGB", POST, CREMA)
    d = ImageDraw.Draw(im)
    l = logo(110)
    im.paste(l, (60, 60), l)
    f_tit = ajustar_fuente(d, titulo, 960, 300, 84)
    f = fuente(48, 500)
    # centramos verticalmente el bloque título + items entre el logo y el pie
    alto = alto_texto(d, titulo, f_tit, 960, 1.1) + 60 + sum(alto_texto(d, i, f, 870, 1.25) + 40 for i in items)
    y = max(230, 200 + (1030 - alto) // 2)
    y = texto_bloque(d, (60, y), titulo, f_tit, VERDE, 960, 1.1) + 60
    for item in items:
        d.ellipse((60, y + 6, 110, y + 56), fill=VERDE)
        d.line((72, y + 31, 82, y + 42, 98, y + 20), fill=BLANCO, width=7, joint="curve")
        y = texto_bloque(d, (140, y), item, f, TEXTO, 870, 1.25) + 40
    d.text((60, 1350 - 100), USUARIO, font=fuente(34, 700), fill=VERDE)
    return im


def slide_cta(producto=None):
    im = Image.new("RGB", POST, VERDE)
    d = ImageDraw.Draw(im)
    l = logo(300, blanco=True)
    im.paste(l, ((1080 - l.width) // 2, 230), l)
    y = 230 + l.height + 90
    titulo = f"¿Querés el {producto.lower()}?" if producto else "¿Lo querés?"
    f_tit = ajustar_fuente(d, titulo, 940, 250, 84)
    y = texto_bloque(d, (70, y), titulo, f_tit, BLANCO, 940, 1.1, centrado=True) + 40
    y = pastilla(d, (540, y), CTA, fuente(46, 800), BLANCO, VERDE, pad=(44, 22), centro=True) + 60
    texto_bloque(d, (70, y), "Diseños únicos y personalizados\nImpreso en 3D", fuente(36, 500),
                 (210, 230, 220), 940, 1.35, centrado=True)
    d.text((540, 1350 - 90), USUARIO, font=fuente(36, 700), fill=BLANCO, anchor="mm")
    return im


# ---------- Historias (1080x1920) ----------
# Zonas seguras: Instagram tapa ~250px arriba y ~300px abajo.

def _tarjeta(foto, tamanio, radio=48):
    t = ImageOps.fit(foto, tamanio, Image.LANCZOS) if abs(foto.width / foto.height - tamanio[0] / tamanio[1]) < 0.25 \
        else encajar(foto, tamanio)
    mascara = Image.new("L", tamanio, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, *tamanio), radius=radio, fill=255)
    return t, mascara


def historia_foto(foto, titulo, subtitulo=None, etiqueta=None):
    im = Image.new("RGB", HISTORIA, CREMA)
    d = ImageDraw.Draw(im)
    l = logo(90)
    im.paste(l, (70, 260), l)
    d.text((180, 305), "GolfCraft3D", font=fuente(40, 800), fill=VERDE, anchor="lm")
    if etiqueta:
        f = fuente(30, 700)
        w = d.textlength(etiqueta.upper(), font=f) + 56
        pastilla(d, (1010 - w, 280), etiqueta.upper(), f, VERDE, BLANCO)
    tarjeta, mascara = _tarjeta(foto, (900, 900))
    im.paste(tarjeta, (90, 390), mascara)
    y = 390 + 900 + 40
    f_tit = ajustar_fuente(d, titulo, 900, 150, 66)
    y = texto_bloque(d, (90, y), titulo, f_tit, TEXTO, 900, 1.1)
    if subtitulo:
        y = texto_bloque(d, (90, y + 8), subtitulo, fuente(36, 500), (70, 85, 78), 900, 1.25)
    # el botón va debajo del texto, sin entrar en la zona que tapa Instagram (últimos ~300px)
    pastilla(d, (540, min(y + 30, 1920 - 300 - 80)), f"{CTA} → {USUARIO}", fuente(34, 700), VERDE, BLANCO,
             pad=(40, 22), centro=True)
    return im


def historia_texto(titulo, texto, etiqueta=None):
    im = Image.new("RGB", HISTORIA, VERDE)
    d = ImageDraw.Draw(im)
    l = logo(240, blanco=True)
    f_eti = fuente(36, 700)
    f_tit = ajustar_fuente(d, titulo, 920, 420, 110)
    f_txt = ajustar_fuente(d, texto, 920, 520, 60, minimo=36, peso=500, interlineado=1.3)
    # centramos verticalmente todo el bloque entre las zonas seguras (260..1560)
    alto = (l.height + 70 + (f_eti.size + 28 + 60 if etiqueta else 0)
            + alto_texto(d, titulo, f_tit, 920, 1.1) + 60 + alto_texto(d, texto, f_txt, 920, 1.3))
    y = max(260, 260 + (1300 - alto) // 2)
    im.paste(l, ((1080 - l.width) // 2, y), l)
    y += l.height + 70
    if etiqueta:
        y = pastilla(d, (540, y), etiqueta.upper(), f_eti, BLANCO, VERDE, centro=True) + 60
    y = texto_bloque(d, (80, y), titulo, f_tit, BLANCO, 920, 1.1, centrado=True) + 60
    texto_bloque(d, (80, y), texto, f_txt, (225, 238, 230), 920, 1.3, centrado=True)
    d.text((540, 1920 - 330), f"{CTA} · {USUARIO}", font=fuente(34, 700), fill=BLANCO, anchor="mm")
    return im


def guardar(im, ruta):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(ruta, "JPEG", quality=92, optimize=True, progressive=False)
    return ruta
