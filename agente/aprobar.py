"""Registra la respuesta a una propuesta: los aprobados pasan a productos/, el resto queda descartado.

Uso:
    python -m agente.aprobar 2026-10-19 1 3                 # números del mail (propuestas/<fecha>/indice.json)
    python -m agente.aprobar 2026-10-19 tee-de-altura-fija  # o nombres de carpeta
    python -m agente.aprobar 2026-10-19                     # ninguno aprobado
"""
import argparse
import json
import shutil
import sys
from datetime import date

import yaml

from .buscar import PROPUESTOS
from .calendario import RAIZ

CAMPOS = ["nombre", "descripcion", "personalizable", "precio", "gramos", "tiempo", "colores",
          "destacado", "notas", "origen", "diseno", "inspiracion", "printables_id", "url", "autor", "licencia",
          "piezas"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fecha")
    ap.add_argument("aprobados", nargs="*")
    a = ap.parse_args()

    carpeta = RAIZ / "propuestas" / a.fecha
    fichas = {p.parent.name: p for p in sorted(carpeta.glob("*/ficha.yaml"))}
    if not fichas:
        sys.exit(f"No hay propuestas en {carpeta.relative_to(RAIZ)}")
    indice_ruta = carpeta / "indice.json"
    indice = json.loads(indice_ruta.read_text(encoding="utf-8")) if indice_ruta.exists() else {}
    a.aprobados = [indice.get(x, x) for x in a.aprobados]
    desconocidos = set(a.aprobados) - set(fichas)
    if desconocidos:
        sys.exit(f"No existen en la propuesta: {sorted(desconocidos)}. Hay: {sorted(fichas)}")

    registro = json.loads(PROPUESTOS.read_text(encoding="utf-8")) if PROPUESTOS.exists() else []
    for slug, ruta in fichas.items():
        ficha = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        aprobado = slug in a.aprobados
        registro = [r for r in registro if str(r["printables_id"]) != str(ficha["printables_id"])]
        registro.append({"printables_id": ficha["printables_id"], "nombre": ficha["nombre"], "slug": slug,
                         "propuesto": a.fecha, "estado": "aprobado" if aprobado else "rechazado",
                         "respondido": date.today().isoformat()})
        if not aprobado:
            continue
        destino = RAIZ / "productos" / slug
        (destino / "fotos").mkdir(parents=True, exist_ok=True)
        for f in (ruta.parent / "fotos").glob("*.jpg"):
            shutil.copy2(f, destino / "fotos" / f.name)
        info = {k: ficha.get(k) for k in CAMPOS}
        info["colores"] = ficha.get("colores") or ficha.get("colores_render")
        info["personalizable"] = info["personalizable"] or "Color a elección (10 colores de PLA)"
        info["destacado"] = bool(info["destacado"])
        (destino / "info.yaml").write_text(yaml.safe_dump(info, allow_unicode=True, sort_keys=False),
                                           encoding="utf-8")
        print(f"aprobado  -> productos/{slug}")
    PROPUESTOS.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(a.aprobados)} aprobados, {len(fichas) - len(a.aprobados)} descartados")


if __name__ == "__main__":
    main()
