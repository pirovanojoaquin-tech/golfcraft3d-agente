"""Avisos y respuestas por Telegram (gratis, corre en GitHub Actions).

Uso:
    python -m agente.telegram enviar --texto "<b>Hola</b>" [--fotos url1,url2]
    python -m agente.telegram leer      # guarda los mensajes nuevos del dueño en contenido/telegram.json

Variables de entorno:
    TELEGRAM_BOT_TOKEN   token del bot (secreto de GitHub)

El primer chat que le escribe /start al bot queda registrado como el del dueño; los mensajes
de cualquier otro chat se ignoran.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests

from .calendario import RAIZ

ESTADO = RAIZ / "contenido" / "telegram.json"
LIMITE_TEXTO = 4096
LIMITE_CAPTION = 1024


def _api(metodo, **datos):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("Falta TELEGRAM_BOT_TOKEN")
    r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", json=datos, timeout=60)
    respuesta = r.json()
    if not respuesta.get("ok"):
        raise RuntimeError(f"Telegram {metodo}: {respuesta.get('description')}")
    return respuesta["result"]


def cargar():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"chat_id": None, "offset": 0, "mensajes": []}


def guardar(estado):
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def leer():
    """Trae los mensajes nuevos del dueño. Devuelve la lista de mensajes agregados."""
    estado = cargar()
    nuevos = []
    for u in _api("getUpdates", offset=estado["offset"], timeout=0):
        estado["offset"] = u["update_id"] + 1
        m = u.get("message")
        if not m or "text" not in m:
            continue
        chat = m["chat"]["id"]
        if estado["chat_id"] is None:
            estado["chat_id"] = chat
            _api("sendMessage", chat_id=chat, text="¡Listo! Desde ahora te aviso por acá todo lo del agente de GolfCraft3D ⛳")
        if chat != estado["chat_id"]:
            continue
        if m["text"].strip() == "/start":
            continue
        msg = {"fecha": datetime.fromtimestamp(m["date"], timezone.utc).isoformat(), "texto": m["text"],
               "procesado": False}
        estado["mensajes"].append(msg)
        nuevos.append(msg)
    estado["mensajes"] = estado["mensajes"][-200:]
    guardar(estado)
    return nuevos


def enviar(texto, fotos=None):
    estado = cargar()
    if not estado["chat_id"]:
        leer()  # por si el dueño ya mandó /start y todavía no lo registramos
        estado = cargar()
    if not estado["chat_id"]:
        sys.exit("Todavía nadie le escribió /start al bot")
    chat = estado["chat_id"]
    fotos = [f for f in (fotos or []) if f][:10]
    if len(fotos) == 1:
        _api("sendPhoto", chat_id=chat, photo=fotos[0])
    elif fotos:
        _api("sendMediaGroup", chat_id=chat, media=[{"type": "photo", "media": f} for f in fotos])
    # el texto va aparte para no chocar con el límite de 1024 caracteres de las fotos
    for i in range(0, len(texto), LIMITE_TEXTO):
        _api("sendMessage", chat_id=chat, text=texto[i:i + LIMITE_TEXTO], parse_mode="HTML",
             disable_web_page_preview=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enviar")
    e.add_argument("--texto", required=True)
    e.add_argument("--fotos", default="", help="URLs separadas por coma")
    sub.add_parser("leer")
    a = ap.parse_args()
    if a.cmd == "enviar":
        enviar(a.texto, a.fotos.split(","))
        print("enviado")
    else:
        for m in leer():
            print(f"{m['fecha']}  {m['texto']}")


if __name__ == "__main__":
    main()
