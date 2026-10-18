"""Lectura y escritura de contenido/calendario.json (la cola de publicaciones)."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "contenido" / "calendario.json"


def cargar():
    if not RUTA.exists():
        return []
    return json.loads(RUTA.read_text(encoding="utf-8"))


def guardar(items):
    RUTA.parent.mkdir(parents=True, exist_ok=True)
    items.sort(key=lambda i: (i["fecha"], i["hora"]))
    RUTA.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
