"""Reel de un producto: animación 3D (el producto girando) con textos animados, colores y cierre de marca.

Uso (lo corre el workflow reel.yml; necesita blender, prusa-slicer y ffmpeg):
    python -m agente.reel --plan planes/2026-11-17.yaml      # todos los reels agendados en el plan (días con `reel:`)
    python -m agente.reel <carpeta de productos/> --salida contenido/media/2026-11-17/reel.mp4 \
        --gancho "¿Tus putts quedan cortos?" --beneficios "Entrená la velocidad|En casa o en el green|En tu color"
    opciones: --color blanco  --angulo 28  --cuadros 100  --dir-cuadros <carpeta con f_000.png...> (ya renderizados)

Video vertical 1080x1920 a 25 cuadros por segundo, ~11 s, H.264 + música de assets/musica (o silencio
si no hay pistas). Escenas: gancho → beneficios → colores → cierre con logo.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from PIL import Image, ImageChops, ImageDraw

from . import disenio as D
from .calendario import RAIZ
from .preparar import CONFIG, acentos_arg
from .renders import stl_del_producto

FPS = 25
TAM = D.HISTORIA
ESCENAS = {"gancho": (0.0, 2.8), "beneficios": (2.8, 6.6), "colores": (6.6, 9.0), "cierre": (9.0, 11.2)}
DURACION = ESCENAS["cierre"][1]


def suave(t):
    """0..1 con arranque y frenado suaves."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def entra_y_sale(t, ini, fin, rampa=0.35):
    """Opacidad de un elemento visible entre ini y fin (segundos)."""
    return suave((t - ini) / rampa) * suave((fin - t) / rampa)


def con_opacidad(capa, op):
    if op >= 0.999:
        return capa
    c = capa.copy()
    c.putalpha(c.getchannel("A").point(lambda v: round(v * op)))
    return c


def capa_texto(dibujar):
    capa = Image.new("RGBA", TAM, (0, 0, 0, 0))
    dibujar(ImageDraw.Draw(capa), capa)
    return capa


def renderizar_cuadros(info, color, angulo, cuadros, carpeta, muestras=6):
    acentos = [(RAIZ / p["ruta"], p["color"]) for p in info["piezas"][1:] if p.get("color") and p.get("ruta")]
    cmd = ["blender", "-b", "-P", str(RAIZ / "agente" / "render.py"), "--", str(stl_del_producto(info)),
           str(carpeta / "f.png"), "--color", CONFIG["colores"][color], "--angulo", str(angulo), "--giro", "35",
           "--tam", "720", "--muestras", str(muestras), "--transparente", "--cuadros", str(cuadros),
           "--acentos", acentos_arg(acentos)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if len(list(carpeta.glob("f_*.png"))) < cuadros:
        raise RuntimeError(f"Falló el render del reel: {r.stdout[-600:]}")


def generar(slug, salida, gancho, beneficios, color=None, angulo=24, cuadros=100, dir_cuadros=None):
    carpeta = RAIZ / "productos" / slug
    info = yaml.safe_load((carpeta / "info.yaml").read_text(encoding="utf-8"))
    color = color or (info.get("colores") or ["verde"])[0]
    tono = D.tono_para(color)
    titulo_c, sub_c = D._colores_texto(tono)
    marca = D.VERDE
    tmp = tempfile.TemporaryDirectory()
    if dir_cuadros:
        dir_cuadros = Path(dir_cuadros)
    else:
        dir_cuadros = Path(tmp.name) / "cuadros"
        dir_cuadros.mkdir()
        renderizar_cuadros(info, color, angulo, cuadros, dir_cuadros)
    giro = [Image.open(f).convert("RGBA") for f in sorted(dir_cuadros.glob("f_*.png"))]
    # la sombra llega hasta el borde del cuadro: se difuminan los bordes para que no se vea un corte recto
    w0, h0 = giro[0].size
    borde = w0 // 7
    mascara = Image.new("L", (w0, h0), 255)
    dm = ImageDraw.Draw(mascara)
    for i in range(borde):
        dm.rectangle((i, i, w0 - 1 - i, h0 - 1 - i), outline=round(255 * (i / borde) ** 1.5))
    for c in giro:
        c.putalpha(ImageChops.multiply(c.getchannel("A"), mascara))
    # caja que ocupa el producto a lo largo de toda la vuelta: con eso se lo escala para que entre justo entre
    # el texto de arriba y el de abajo, sea alto (un arbolito) o chato y ancho (una rampa)
    cajas = [c.getchannel("A").point(lambda a: 255 if a > 150 else 0).getbbox() for c in giro[::4]]
    cajas = [c for c in cajas if c]
    bx0, by0 = min(c[0] for c in cajas), min(c[1] for c in cajas)
    bx1, by1 = max(c[2] for c in cajas), max(c[3] for c in cajas)
    lado_base = giro[0].width * min(980 / (bx1 - bx0), 700 / (by1 - by0))
    centro_y = (by0 + by1) / 2 / giro[0].height  # centro del producto dentro del cuadro (0..1)

    fondo = D.fondo(TAM, tono)
    fondo_cierre = D.fondo(TAM, "verde")
    d0 = ImageDraw.Draw(fondo)

    # --- capas fijas de cada escena (se dibujan una vez; por cuadro solo cambian opacidad y posición)
    f_gancho = D.ajustar_fuente(d0, gancho, 940, 250, 104, minimo=56)
    c_gancho = capa_texto(lambda d, _: D.texto_bloque(d, (70, 280), gancho, f_gancho, titulo_c, 940, 1.12, centrado=True))
    c_logo = capa_texto(lambda d, c: c.alpha_composite(D.logo(150, blanco=tono == "verde"), (465, 80)))
    f_nombre = D.ajustar_fuente(d0, info["nombre"], 920, 190, 78, minimo=52)
    c_nombre = capa_texto(lambda d, _: D.texto_bloque(d, (80, 300), info["nombre"], f_nombre, titulo_c, 920, 1.12,
                                                       centrado=True))
    f_ben = D.fuente(50, 700)
    fondo_p, letra_p = ((255, 255, 255), marca) if tono == "verde" else (marca, D.BLANCO)
    c_ben = [capa_texto(lambda d, _, b=b, n=n: D.pastilla(d, (540, 1330 + n * 104), b, f_ben, fondo_p, letra_p,
                                                          pad=(40, 20), centro=True))
             for n, b in enumerate(beneficios[:3])]
    c_colores = capa_texto(lambda d, _: (
        D.texto_bloque(d, (80, 290), "Elegí tu color", D.fuente(104, 800), titulo_c, 920, 1.1, centrado=True),
        D.texto_bloque(d, (80, 420), "Lo imprimimos a pedido", D.fuente(44, 500), sub_c, 920, 1.2, centrado=True)))
    pngs = [(carpeta / "fotos" / "png" / f"{c}.png", c) for c in (info.get("colores_png") or [])]
    pngs = [(Image.open(p).convert("RGBA"), c) for p, c in pngs if p.exists()][:6]
    f_color = D.fuente(54, 800)
    c_nombre_color = [capa_texto(lambda d, _, c=c: D.pastilla(d, (540, 1400), c.capitalize(), f_color, fondo_p, letra_p,
                                                              pad=(46, 22), centro=True)) for _, c in pngs]
    cta = f"¿Querés {info.get('nombre_corto') or 'el tuyo'}?"
    c_cierre = capa_texto(lambda d, c: (
        c.alpha_composite(D.logo(300, blanco=True), (390, 170)),
        D.texto_bloque(d, (80, 1200), cta, D.ajustar_fuente(d, cta, 920, 220, 96, minimo=60), D.BLANCO, 920, 1.12,
                       centrado=True),
        D.pastilla(d, (540, 1370), D.CTA, D.fuente(56, 800), (255, 255, 255), marca, pad=(52, 26), centro=True),
        d.text((540, 1540), D.USUARIO, font=D.fuente(46, 700), fill=(214, 236, 224), anchor="mm")))

    def producto(lienzo, t, escala=1.0, y=930, op=1.0):
        """El producto girando (una vuelta cada 4 s), con su centro en (540, y)."""
        cuadro = giro[int(t * FPS) % len(giro)]
        lado = round(lado_base * escala)
        im = con_opacidad(cuadro.resize((lado, lado), Image.BICUBIC), op)
        capa = Image.new("RGBA", TAM, (0, 0, 0, 0))
        capa.paste(im, (540 - lado // 2, round(y - lado * centro_y)))
        lienzo.alpha_composite(capa)

    n_cuadros = round(DURACION * FPS)
    carpeta_v = Path(tmp.name) / "video"
    carpeta_v.mkdir()
    for n in range(n_cuadros):
        t = n / FPS
        g0, g1 = ESCENAS["gancho"]
        b0, b1 = ESCENAS["beneficios"]
        c0, c1 = ESCENAS["colores"]
        z0, z1 = ESCENAS["cierre"]
        if t < z0:
            im = fondo.copy()
            im.alpha_composite(con_opacidad(c_logo, suave(t / 0.4)))
        else:
            im = fondo_cierre.copy()
        if t < c0:
            # producto: entra creciendo y sigue girando durante gancho y beneficios
            producto(im, t, escala=0.82 + 0.18 * suave(t / 0.7), op=suave(t / 0.4) * suave((c0 - t) / 0.3))
            op = entra_y_sale(t, 0.15, g1)
            if op > 0:
                im.alpha_composite(con_opacidad(c_gancho, op), (0, round(40 * (1 - suave((t - 0.15) / 0.5)))))
            op = entra_y_sale(t, b0, b1)
            if op > 0:
                im.alpha_composite(con_opacidad(c_nombre, op))
            for k, capa in enumerate(c_ben):
                ini = b0 + 0.25 + k * 0.7
                op = entra_y_sale(t, ini, b1)
                if op > 0:
                    im.alpha_composite(con_opacidad(capa, op), (0, round(50 * (1 - suave((t - ini) / 0.4)))))
        elif t < z0:
            im.alpha_composite(con_opacidad(c_colores, entra_y_sale(t, c0, c1)))
            if pngs:
                paso = (c1 - c0) / len(pngs)
                k = min(len(pngs) - 1, int((t - c0) / paso))
                local = (t - c0 - k * paso) / paso
                op = suave(local / 0.25) * suave((1 - local) / 0.2) if k < len(pngs) - 1 else suave(local / 0.25) * suave((c1 - t) / 0.3)
                capa = Image.new("RGBA", TAM, (0, 0, 0, 0))
                ImageDraw.Draw(capa).rounded_rectangle((130, 560, 950, 1340), radius=56, fill=(255, 255, 255, 238))
                D.pegar(capa, pngs[k][0], (190, 620, 700, 660))
                im.alpha_composite(con_opacidad(capa, op))
                im.alpha_composite(con_opacidad(c_nombre_color[k], op))
            else:
                producto(im, t, op=entra_y_sale(t, c0, c1))
        else:
            op = suave((t - z0) / 0.4)
            producto(im, t, escala=0.68, y=840, op=op)
            im.alpha_composite(con_opacidad(c_cierre, op), (0, round(30 * (1 - op))))
        im.convert("RGB").save(carpeta_v / f"{n:04d}.jpg", quality=93)

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    # música: una pista de assets/musica (uso comercial libre con crédito), siempre la misma para cada reel
    pistas = sorted((RAIZ / "assets" / "musica").glob("*.mp3"))
    pista = pistas[sum(map(ord, str(salida))) % len(pistas)] if pistas else None
    audio = ["-i", str(pista)] if pista else ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    r = subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", str(carpeta_v / "%04d.jpg"), *audio,
                        "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
                        "-r", str(FPS), "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart",
                        str(salida)], capture_output=True, text=True)
    if r.returncode != 0 or not salida.exists():
        raise RuntimeError(f"ffmpeg falló: {r.stderr[-600:]}")
    tmp.cleanup()
    # crédito de la música: publicar.py lo suma al texto del reel
    nota = salida.with_suffix(".musica.txt")
    if pista:
        c = yaml.safe_load((RAIZ / "assets" / "musica" / "creditos.yaml").read_text(encoding="utf-8"))[pista.stem]
        nota.write_text(f"🎵 Música: «{c['titulo']}» de {c['autor']}, {c['licencia']}\n", encoding="utf-8")
    elif nota.exists():
        nota.unlink()
    print(f"{slug}: {salida.relative_to(RAIZ) if salida.is_relative_to(RAIZ) else salida} ({salida.stat().st_size // 1024} KB)")
    return salida


def del_plan(ruta_plan, rehacer=False):
    """Genera los reels agendados en un plan (días con `reel:`) que todavía no tienen video."""
    plan = yaml.safe_load(Path(ruta_plan).read_text(encoding="utf-8"))
    for dia in plan["dias"]:
        rl = dia.get("reel")
        if not rl:
            continue
        salida = RAIZ / "contenido" / "media" / str(dia["fecha"]) / "reel.mp4"
        if salida.exists() and not rehacer:
            continue
        generar(rl.get("producto") or dia["post"]["producto"], salida, rl["gancho"], rl["beneficios"],
                rl.get("color"), rl.get("angulo", 24))


def main():
    if "--plan" in sys.argv:
        ap = argparse.ArgumentParser()
        ap.add_argument("--plan", required=True)
        ap.add_argument("--rehacer", action="store_true")
        a = ap.parse_args()
        return del_plan(a.plan, a.rehacer)
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--gancho", required=True)
    ap.add_argument("--beneficios", required=True, help="hasta 3, separados por |")
    ap.add_argument("--color")
    ap.add_argument("--angulo", type=float, default=24)
    ap.add_argument("--cuadros", type=int, default=100)
    ap.add_argument("--dir-cuadros")
    a = ap.parse_args()
    generar(a.slug, a.salida, a.gancho, [b.strip() for b in a.beneficios.split("|")], a.color, a.angulo, a.cuadros,
            a.dir_cuadros)


if __name__ == "__main__":
    main()
