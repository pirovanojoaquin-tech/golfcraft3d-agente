"""Arma el HTML del mail de propuesta semanal a partir de propuestas/<fecha>/*/ficha.yaml.

Uso:
    python -m agente.mail 2026-10-19 --sha <commit con las fotos> > propuesta.html

Las imágenes se enlazan desde GitHub (raw) con el commit fijo, así el mail no pesa.
"""
import argparse
import html
import json

import yaml

from .calendario import RAIZ

REPO = "pirovanojoaquin-tech/golfcraft3d-agente"
VERDE, CREMA = "#016040", "#F4F1EA"


def miles(n):
    return f"{int(n):,}".replace(",", ".")


def tarjeta(n, ficha, carpeta, sha):
    base = f"https://raw.githubusercontent.com/{REPO}/{sha}/{carpeta.relative_to(RAIZ).as_posix()}/fotos/"
    fotos = "".join(
        f'<img src="{base}{f["archivo"]}" alt="{html.escape(f["color"])}" width="170" '
        f'style="border-radius:10px;margin:0 6px 6px 0;vertical-align:top">' for f in ficha["fotos"])
    colores = ", ".join(f["color"] for f in ficha["fotos"])
    e = html.escape
    return f"""
<div style="background:#fff;border-radius:14px;padding:18px;margin:0 0 18px;border:1px solid #e3ded2">
  <div style="font-size:13px;color:{VERDE};font-weight:bold;letter-spacing:.5px">PRODUCTO {n}</div>
  <div style="font-size:20px;font-weight:bold;margin:2px 0 6px">{e(ficha["nombre"])}</div>
  <div style="color:#55625b;font-size:14px;margin-bottom:12px">{e(ficha.get("descripcion_es") or ficha["descripcion"])}</div>
  <div>{fotos}</div>
  <table style="font-size:14px;border-collapse:collapse;margin-top:8px">
    <tr><td style="padding:3px 14px 3px 0;color:#55625b">Precio sugerido</td><td><b style="font-size:17px">${miles(ficha["precio"])}</b> (filamento ${miles(ficha["costo_filamento"])} × 3)</td></tr>
    <tr><td style="padding:3px 14px 3px 0;color:#55625b">Filamento</td><td>{ficha["gramos"]} g de {e(ficha["material"])}</td></tr>
    <tr><td style="padding:3px 14px 3px 0;color:#55625b">Tiempo estimado</td><td>{e(ficha["tiempo"])}</td></tr>
    <tr><td style="padding:3px 14px 3px 0;color:#55625b">Colores sugeridos</td><td>{e(colores)}</td></tr>
    <tr><td style="padding:3px 14px 3px 0;color:#55625b">Licencia</td><td>{e(ficha["licencia"])} · autor {e(ficha["autor"])} · <a href="{ficha["url"]}" style="color:{VERDE}">ver modelo</a></td></tr>
  </table>
  {f'<div style="margin-top:8px;font-size:13px;color:#7a5a00">⚠️ {e(ficha["aviso"])}</div>' if ficha.get("aviso") else ""}
</div>"""


def armar(fecha, sha, intro=None):
    carpeta = RAIZ / "propuestas" / fecha
    rutas = sorted(carpeta.glob("*/ficha.yaml"))
    # el número que ve el usuario en el mail -> carpeta del producto (lo usa la aprobación)
    indice = {str(n): r.parent.name for n, r in enumerate(rutas, 1)}
    (carpeta / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tarjetas = "".join(tarjeta(n, yaml.safe_load(r.read_text(encoding="utf-8")), r.parent, sha)
                       for n, r in enumerate(rutas, 1))
    ejemplo = ", ".join(str(i) for i in range(1, min(len(rutas), 3) + 1, 2)) or "1"
    intro = intro or "Encontré estos productos de golf con licencia que permite venderlos. ¿Cuáles sumamos al catálogo?"
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;color:#14231C">
<div style="background:{VERDE};color:#fff;padding:18px 22px;border-radius:14px 14px 0 0">
  <div style="font-size:20px;font-weight:bold">GolfCraft3D · Productos nuevos</div>
  <div style="opacity:.85;font-size:14px">Propuesta de la semana del {fecha}</div>
</div>
<div style="background:{CREMA};padding:20px 22px;border-radius:0 0 14px 14px">
  <p style="margin-top:0">{html.escape(intro)}</p>
  <div style="background:#fff;border-left:4px solid {VERDE};padding:12px 14px;border-radius:8px;margin-bottom:18px">
    <b>Para aprobar, respondé este mail</b> con los números que querés, por ejemplo:<br>
    <span style="font-size:18px;font-family:monospace">SI {ejemplo}</span><br>
    <span style="color:#55625b;font-size:13px">Si no querés ninguno: <span style="font-family:monospace">NO</span>.
    Los aprobados se guardan en tu Drive (PRODUCTOS 3D GOLF) y empiezan a publicarse.</span>
  </div>
  {tarjetas}
  <p style="color:#55625b;font-size:12px">Gramos y tiempos estimados con un perfil genérico (0,2 mm, 15 % de relleno).
  Fotos: render del modelo 3D original en tus colores de PLA.</p>
</div></div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fecha")
    ap.add_argument("--sha", required=True)
    ap.add_argument("--intro")
    a = ap.parse_args()
    print(armar(a.fecha, a.sha, a.intro))


if __name__ == "__main__":
    main()
