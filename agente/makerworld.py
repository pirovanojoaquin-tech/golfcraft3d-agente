"""Archivos de los productos de MakerWorld (Bambu): el dueño los baja y se los manda al bot de Telegram.

MakerWorld no deja descargar sin cuenta, así que cuando se aprueba un modelo de ahí su info.yaml queda con
`archivo_pendiente: true` y el dueño lo baja (MakerWorld o Bambu Studio) y lo manda al bot como archivo.

Uso (lo corre telegram.yml cada hora, después de `telegram leer`):
    python -m agente.makerworld recibir     # asigna los archivos recibidos a su producto (imprime los slugs en JSON)
    python -m agente.makerworld pendientes  # productos aprobados que esperan su archivo

El archivo no se guarda en el repo (es público): queda en Telegram y se baja con su file_id cuando hace falta.
Si el mensaje trae texto (ej: "divot"), se usa para elegir el producto; si hay uno solo pendiente, va a ese.
"""
import argparse
import json
import os
import re
import unicodedata
import zipfile
from pathlib import Path

import requests
import yaml

from .calendario import RAIZ
from .telegram import _api, cargar, enviar, guardar

DESCARGAS = RAIZ / "descargas"
MODELOS = (".stl", ".3mf", ".obj")
LIMITE_BOT = 20 * 1024 * 1024  # la API de bots no baja archivos más grandes


def _normal(texto):
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return set(re.findall(r"[a-z0-9]{3,}", t))


def pendientes():
    lista = []
    for ruta in sorted((RAIZ / "productos").glob("*/info.yaml")):
        info = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        if info.get("origen") == "makerworld" and info.get("archivo_pendiente"):
            lista.append((ruta.parent.name, info))
    return lista


def bajar(file_id, nombre, carpeta):
    """Baja un archivo de Telegram y devuelve los modelos 3D que trae (los .zip se descomprimen)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / Path(nombre).name
    if not destino.exists():
        ruta = _api("getFile", file_id=file_id)["file_path"]
        r = requests.get(f"https://api.telegram.org/file/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{ruta}", timeout=300)
        r.raise_for_status()
        destino.write_bytes(r.content)
    if destino.suffix.lower() != ".zip":
        return [destino]
    modelos = []
    with zipfile.ZipFile(destino) as z:
        for n in z.namelist():
            if n.lower().endswith(MODELOS) and not n.startswith("__MACOSX"):
                salida = carpeta / Path(n).name
                salida.write_bytes(z.read(n))
                modelos.append(salida)
    return modelos


def modelo_de_pieza(info, pieza):
    """Ruta local del modelo de una pieza recibida por Telegram (lo baja si hace falta)."""
    carpeta = DESCARGAS / f"mw{info['makerworld_id']}"
    for m in bajar(pieza["telegram_file_id"], pieza.get("zip") or pieza["archivo"], carpeta):
        if m.name == pieza["archivo"]:
            return m
    raise RuntimeError(f"No encontré {pieza['archivo']} en lo que mandó el dueño")


def elegir(texto, lista):
    if len(lista) == 1:
        return lista[0]
    palabras = _normal(texto)
    # el nombre en español, el del modelo en MakerWorld (está en la URL) y el del archivo
    puntaje = [(len(palabras & _normal(" ".join([slug, info["nombre"], info.get("url") or ""]).replace("-", " "))
                    - {"golf", "makerworld", "models", "https", "com"}), slug, info) for slug, info in lista]
    puntaje.sort(key=lambda x: -x[0])
    if puntaje and puntaje[0][0] and (len(puntaje) == 1 or puntaje[0][0] > puntaje[1][0]):
        return puntaje[0][1], puntaje[0][2]
    return None


def recibir():
    """Devuelve los slugs que recibieron archivo (para lanzar sus renders)."""
    estado = cargar()
    nuevos = [m for m in estado["mensajes"] if m.get("archivo") and not m.get("procesado")]
    if not nuevos:
        return []
    listos = []
    for m in nuevos:
        a = m["archivo"]
        espera = pendientes()
        if not a["nombre"].lower().endswith(MODELOS + (".zip",)):
            continue  # no es un modelo 3D: lo deja para la rutina semanal
        m["procesado"] = True
        if not espera:
            enviar(f"Recibí <b>{a['nombre']}</b>, pero no hay ningún producto de MakerWorld esperando archivo.")
            continue
        if (a.get("tamanio") or 0) > LIMITE_BOT:
            enviar(f"<b>{a['nombre']}</b> pesa más de 20 MB y el bot no lo puede bajar. Mandá el STL solo "
                   "(en MakerWorld: Descargar → archivos STL) o comprimilo en .zip.")
            continue
        elegido = elegir(f"{m.get('texto')} {a['nombre']}", espera)
        if not elegido:
            nombres = ", ".join(i["nombre"] for _, i in espera)
            enviar(f"Recibí <b>{a['nombre']}</b>, pero esperan archivo: {nombres}. Reenvialo con el nombre del "
                   "producto en el texto del mensaje.")
            continue
        slug, info = elegido
        modelos = bajar(a["file_id"], a["nombre"], DESCARGAS / f"mw{info['makerworld_id']}")
        if not modelos:
            enviar(f"<b>{a['nombre']}</b> no trae archivos 3D (.stl, .3mf u .obj).")
            continue
        zip_ = a["nombre"] if a["nombre"].lower().endswith(".zip") else None
        info["piezas"] = (info.get("piezas") or []) + [
            {"archivo": p.name, "telegram_file_id": a["file_id"], **({"zip": zip_} if zip_ else {})} for p in modelos]
        info["archivo_pendiente"] = False
        (RAIZ / "productos" / slug / "info.yaml").write_text(
            yaml.safe_dump(info, allow_unicode=True, sort_keys=False), encoding="utf-8")
        listos.append(slug)
        piezas = "\n".join(f"• {p.name}" for p in modelos)
        enviar(f"✅ Recibí el archivo de <b>{info['nombre']}</b>:\n{piezas}\n\nArmo las fotos con nuestros renders "
               "(tarda unos 15 min) y lo sumo a la tienda y al próximo contenido.")
    guardar(estado)
    return list(dict.fromkeys(listos))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["recibir", "pendientes"])
    a = ap.parse_args()
    if a.cmd == "pendientes":
        for slug, info in pendientes():
            print(f"{slug}: {info['url']}")
        return
    # la última línea es el JSON de slugs: telegram.yml lanza renders.yml con eso después de subir los info.yaml
    print(json.dumps(recibir()))


if __name__ == "__main__":
    main()
