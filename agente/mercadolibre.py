"""Mercado Libre: propone, publica y vigila las ventas (corre en GitHub Actions, workflow mercadolibre.yml).

Uso:
    python -m agente.mercadolibre pendientes            # productos ya publicados en Instagram que faltan en ML -> proponer
    python -m agente.mercadolibre proponer <slug>       # calcula el pack que conviene y genera las fotos
    python -m agente.mercadolibre avisar <slug> --sha X # manda la propuesta por Telegram y la anota en la planilla
    python -m agente.mercadolibre aprobaciones          # lee "ML SI 4" / "ML NO 4" de Telegram y lanza la publicación
    python -m agente.mercadolibre publicar <slug>       # valida y publica el aviso aprobado
    python -m agente.mercadolibre evento <topic> <recurso>  # notificación de ML (venta, pregunta, aviso, reclamo)
    python -m agente.mercadolibre revisar               # cada hora: renueva el permiso y repasa ventas y preguntas
    python -m agente.mercadolibre autorizar <code>      # primera vez: canjea el código de autorización

Secretos (variables de entorno): ML_APP_ID, ML_CLIENT_SECRET, ML_REFRESH_TOKEN, ML_ACCESS_TOKEN,
DRIVE_WEBAPP_URL (planilla y redirect de la autorización), TELEGRAM_BOT_TOKEN, GH_TOKEN (para guardar secretos
y lanzar workflows).

IMPORTANTE: el repo es público. Nada de datos de compradores (nombres, direcciones, mensajes) se imprime en
los logs ni se guarda en el repo: van solo a la planilla privada de Drive y a Telegram.
"""
import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
import yaml

from . import calendario, telegram
from .calendario import RAIZ

CONFIG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
CFG = CONFIG["mercadolibre"]
API = "https://api.mercadolibre.com"
ESTADO = RAIZ / "contenido" / "mercadolibre.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "pirovanojoaquin-tech/golfcraft3d-agente")
ARG = timezone(timedelta(hours=-3))
GTIN_SIN_CODIGO, GTIN_PACK = "17055160", "17055159"
ENVIO_ESTIMADO = set()  # packs cuyo envío no se pudo cotizar (falta activar Mercado Envíos)


class ErrorML(Exception):
    pass


# ---------- estado (solo datos de publicaciones) ----------

def cargar():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"user_id": None, "siguiente": 1, "productos": {}}


def guardar(estado):
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _git(*args, check=True):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check).stdout


def subir(mensaje, rutas=()):
    """Guarda el estado en el repo sin chocar con otros workflows que corren a la vez.

    Toma lo último de GitHub, le aplica solo los productos que cambió esta corrida y reintenta si alguien
    subió algo justo antes. Devuelve el commit (para armar links a las fotos).
    """
    vacio = {"user_id": None, "siguiente": 1, "productos": {}}
    rel = ESTADO.relative_to(RAIZ).as_posix()

    def leer(ref):
        try:
            return json.loads(_git("show", f"{ref}:{rel}"))
        except (subprocess.CalledProcessError, ValueError):
            return dict(vacio)

    base, mio = leer("HEAD"), cargar()
    cambiados = {s for s in set(base["productos"]) | set(mio["productos"])
                 if base["productos"].get(s) != mio["productos"].get(s)}
    for intento in range(6):
        _git("fetch", "-q", "origin", "main")
        suyo = leer("origin/main")
        for s in cambiados:
            if s in mio["productos"]:
                suyo["productos"][s] = mio["productos"][s]
            else:
                suyo["productos"].pop(s, None)
        if mio.get("user_id") != base.get("user_id"):
            suyo["user_id"] = mio.get("user_id")
        suyo["siguiente"] = max(suyo.get("siguiente", 1), mio.get("siguiente", 1))
        _git("reset", "-q", "--mixed", "origin/main")
        guardar(suyo)
        _git("add", "-A", rel, *rutas)
        if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
            return _git("rev-parse", "HEAD").strip()
        _git("commit", "-q", "-m", mensaje)
        if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], capture_output=True).returncode == 0:
            return _git("rev-parse", "HEAD").strip()
        time.sleep(3 * (intento + 1))
    raise ErrorML("No se pudo guardar el estado en GitHub después de 6 intentos")


def fallo(slug):
    """Marca una propuesta fallida: se reintenta sola más tarde (hasta 3 veces)."""
    estado = cargar()
    p = estado["productos"].get(slug, {})
    if p.get("estado") in (None, "preparando", "error"):
        estado["productos"][slug] = {**p, "estado": "error", "intentos": p.get("intentos", 0) + 1,
                                     "desde": int(time.time())}
        guardar(estado)


def rechazar(slug):
    estado = cargar()
    if slug in estado["productos"]:
        estado["productos"][slug]["estado"] = "rechazado"
        guardar(estado)


def info_producto(slug):
    return yaml.safe_load((RAIZ / "productos" / slug / "info.yaml").read_text(encoding="utf-8"))


# ---------- credenciales ----------

def _guardar_secreto(nombre, valor):
    r = subprocess.run(["gh", "secret", "set", nombre, "--body", valor, "--repo", REPO],
                       capture_output=True, text=True)
    if r.returncode:
        raise ErrorML(f"No se pudo guardar el secreto {nombre} (revisá GH_PAT)")


def app_id():
    """El App ID no es secreto (va en el link de autorización): está en config.yaml o en el secreto ML_APP_ID."""
    return os.environ.get("ML_APP_ID") or str(CFG.get("app_id") or "")


def _oauth(**datos):
    r = requests.post(f"{API}/oauth/token", data={"client_id": app_id(),
                                                 "client_secret": os.environ["ML_CLIENT_SECRET"], **datos}, timeout=60)
    if r.status_code != 200:
        raise ErrorML(f"oauth {datos['grant_type']} -> {r.status_code}: {r.json().get('message', '')}")
    t = r.json()
    if "refresh_token" not in t:
        # diagnóstico (sin claves): qué scopes dio ML y cuáles tiene registrados la app
        print(f"scope del token: {t.get('scope')!r}")
        app = requests.get(f"{API}/applications/{app_id()}", timeout=60,
                           headers={"Authorization": f"Bearer {t['access_token']}"})
        if app.status_code == 200:
            datos_app = app.json()
            print(f"scopes de la app: {datos_app.get('scopes')!r}")
            print("campos de la app:", sorted(datos_app))
        else:
            print(f"GET applications -> {app.status_code}")
        if datos["grant_type"] == "authorization_code" and t.get("user_id"):
            # ML reusó una autorización vieja sin offline_access: la revocamos para que la próxima vez
            # muestre la pantalla de permisos completa
            rev = requests.delete(f"{API}/users/{t['user_id']}/applications/{app_id()}",
                                  headers={"Authorization": f"Bearer {t['access_token']}"}, timeout=60)
            print(f"revocar autorización -> {rev.status_code} {rev.text[:150]}")
            link_autorizacion("Casi: Mercado Libre usó la autorización vieja (sin acceso offline). Ya la borré. "
                              "Tocá este link <b>una vez más</b> y aceptá todos los permisos:")
        else:
            telegram.enviar("⚠️ <b>Falta un permiso en la app de Mercado Libre</b>: activá <b>offline access</b> "
                            "(acceso sin conexión) en la configuración de la app y volvé a autorizar.")
        raise ErrorML("La app de ML no tiene el permiso offline_access: no devolvió refresh_token")
    if os.environ.get("GITHUB_ACTIONS"):  # que nunca aparezcan en los logs públicos
        print(f"::add-mask::{t['access_token']}")
        print(f"::add-mask::{t['refresh_token']}")
    # el refresh token es de un solo uso: se guarda el nuevo enseguida
    _guardar_secreto("ML_REFRESH_TOKEN", t["refresh_token"])
    _guardar_secreto("ML_ACCESS_TOKEN", f"{t['access_token']}|{int(time.time()) + t['expires_in']}")
    os.environ["ML_REFRESH_TOKEN"] = t["refresh_token"]
    os.environ["ML_ACCESS_TOKEN"] = f"{t['access_token']}|{int(time.time()) + t['expires_in']}"
    return t


def autorizar(codigo):
    t = _oauth(grant_type="authorization_code", code=codigo, redirect_uri=os.environ["DRIVE_WEBAPP_URL"])
    estado = cargar()
    estado["user_id"] = t["user_id"]
    guardar(estado)
    yo = api("GET", "/users/me")
    telegram.enviar(f"✅ <b>Mercado Libre conectado</b> con la cuenta <b>{yo.get('nickname', '')}</b>.\n"
                    "Desde ahora, cada producto nuevo que salga en Instagram te lo propongo para ML por acá.")


def link_autorizacion(texto=None):
    """Manda por Telegram el link para que el dueño autorice la app (la URL de vuelta es el Apps Script)."""
    from urllib.parse import urlencode
    url = "https://auth.mercadolibre.com.ar/authorization?" + urlencode(
        {"response_type": "code", "client_id": app_id(), "redirect_uri": os.environ["DRIVE_WEBAPP_URL"],
         "scope": "offline_access read write"})
    texto = texto or ("Tocá este link (con tu cuenta de vendedor abierta), aceptá con <b>Permitir</b> "
                      "y en un minuto te confirmo por acá:")
    telegram.enviar(f"🔗 <b>Conectar Mercado Libre</b>\n{texto}\n<a href=\"{url}\">Autorizar GolfCraft3D Agente</a>")
    print("link enviado por Telegram")


def token(margen=1800):
    """Access token vigente; lo renueva si vence en menos de `margen` segundos."""
    actual = os.environ.get("ML_ACCESS_TOKEN", "")
    if "|" in actual:
        tok, vence = actual.rsplit("|", 1)
        if int(vence) - time.time() > margen:
            return tok
    return _oauth(grant_type="refresh_token", refresh_token=os.environ["ML_REFRESH_TOKEN"])["access_token"]


def api(metodo, ruta, auth=True, **kw):
    cab = {"Authorization": f"Bearer {token()}"} if auth else {}
    r = requests.request(metodo, API + ruta, headers=cab, timeout=60, **kw)
    if r.status_code >= 400:
        try:
            d = r.json()
            causas = "; ".join(c.get("message", "") for c in d.get("cause", []) if isinstance(c, dict))
            msg = d.get("message", "") + (f" ({causas})" if causas else "")
        except ValueError:
            msg = r.text[:200]
        raise ErrorML(f"{metodo} {ruta.split('?')[0]} -> {r.status_code}: {msg}")
    return r.json() if r.content else {}


# ---------- planilla de Drive (vía el Apps Script) ----------

COLUMNAS = {
    "Publicaciones": ["Código", "Producto", "Pack", "Precio", "Comisión ML", "Envío a cargo", "Filamento",
                      "Ganancia", "Categoría", "Estado", "Link", "Actualizado"],
    "Ventas": ["Orden", "Fecha", "Producto", "Unidades", "Color", "Cobrado", "Comisión ML", "Ganancia aprox.",
               "Comprador", "Despachar antes de", "Estado"],
    "Preguntas": ["Id", "Fecha", "Producto", "Pregunta", "Estado"],
}


def planilla(pestania, clave, fila):
    """Agrega o actualiza la fila con esa clave. Devuelve True si la fila es nueva (None si falló)."""
    url = os.environ.get("DRIVE_WEBAPP_URL")
    if not url:
        return None
    try:
        r = requests.post(url, json={"accion": "planilla", "pestania": pestania, "columnas": COLUMNAS[pestania],
                                     "clave": str(clave), "fila": fila}, timeout=90)
        d = r.json()
        if not d.get("ok"):
            print(f"Planilla: {d.get('error')}")
            return None
        return d.get("nuevo")
    except (requests.RequestException, ValueError) as e:
        print(f"Planilla no disponible: {type(e).__name__}")
        return None


# ---------- cálculo del pack ----------

def redondear(x, paso=100):
    return int(math.ceil(x / paso) * paso)


def plata(x):
    return "$" + f"{round(x):,}".replace(",", ".")


def costo_filamento(info):
    return info["gramos"] * CONFIG["produccion"]["precio_kg_filamento"] / 1000


def dimensiones(info, n):
    """Paquete para el envío: 'LxAxH,gramos' en cm (unidades apiladas + embalaje)."""
    m = info.get("medidas_mm") or {"largo": 100, "ancho": 60, "alto": 30}
    lados = [math.ceil((m["largo"] + 20) / 10), math.ceil((m["ancho"] + 20) / 10),
             math.ceil((m["alto"] * n + 20) / 10)]
    return f"{lados[0]}x{lados[1]}x{lados[2]},{math.ceil(info['gramos'] * n + CFG['embalaje_g'])}"


def comision(precio, categoria):
    datos = api("GET", f"/sites/{CFG['sitio']}/listing_prices", params={
        "price": precio, "listing_type_id": CFG["tipo_publicacion"], "category_id": categoria})
    if isinstance(datos, list):
        datos = datos[0]
    det = datos.get("sale_fee_details") or {}
    # se toma lo mayor por si la comisión informada no incluye el cargo fijo
    return max(datos.get("sale_fee_amount", 0), det.get("gross_amount", 0) + det.get("fixed_fee", 0))


def envio_a_cargo(precio, info, n, user_id):
    if precio < CFG["umbral_envio_gratis"]:
        return 0  # lo paga el comprador
    try:
        d = api("GET", f"/users/{user_id}/shipping_options/free", params={"dimensions": dimensiones(info, n)})
        return d.get("coverage", {}).get("all_country", {}).get("list_cost", 0)
    except ErrorML as e:
        # sin Mercado Envíos activado ML no cotiza: usamos un estimado y lo avisamos en la propuesta
        print(f"Envío no cotizado ({e}); se usa el estimado de config.yaml")
        ENVIO_ESTIMADO.add(n)
        return CFG.get("envio_estimado", 9000)


def categoria(info):
    if info.get("ml_categoria"):
        cat = info["ml_categoria"]
    else:
        cat = CFG["categoria_defecto"]
        candidatos = api("GET", f"/sites/{CFG['sitio']}/domain_discovery/search", auth=False,
                         params={"q": f"{info['nombre']} golf", "limit": 5})
        for c in candidatos:
            ruta = [p["id"] for p in api("GET", f"/categories/{c['category_id']}", auth=False)["path_from_root"]]
            if CFG["categoria_golf"] in ruta:
                cat = c["category_id"]
                break
    datos = api("GET", f"/categories/{cat}", auth=False)
    return cat, " > ".join(p["name"] for p in datos["path_from_root"][1:])


def referencia_mercado(info):
    """Mediana de precios de avisos parecidos (solo como referencia para el dueño)."""
    try:
        res = api("GET", f"/sites/{CFG['sitio']}/search", params={"q": f"{info['nombre']} golf", "limit": 20})
        precios = [r["price"] for r in res.get("results", []) if r.get("price")]
        return statistics.median(precios) if len(precios) >= 3 else None
    except ErrorML:
        return None


def calcular(info, user_id):
    cat, cat_nombre = categoria(info)
    unidad = max(info["precio"] * CFG["multiplicador_precio"], CFG.get("precio_minimo_unidad", 0))
    filas = []
    for n in CFG["packs"]:
        precio = redondear(unidad * n * (1 - CFG["descuento_pack"].get(n, 0)))
        com = comision(precio, cat)
        env = envio_a_cargo(precio, info, n, user_id)
        fil = costo_filamento(info) * n
        filas.append({"pack": n, "precio": precio, "comision": round(com), "envio": round(env),
                      "filamento": round(fil), "ganancia": round(precio - com - env - fil)})
    ok = [f for f in filas if f["ganancia"] >= CFG["ganancia_minima"]]
    return {"categoria": cat, "categoria_nombre": cat_nombre, "filas": filas,
            "elegido": ok[0] if ok else None, "referencia": referencia_mercado(info)}


# ---------- propuesta ----------

def pendientes():
    """Productos que ya salieron en un post de Instagram y todavía no se propusieron en ML.

    Lo corre el publicador de Instagram: lanza de a UNA propuesta por vez y no escribe nada (así nunca puede
    trabar una publicación). Si hay un workflow de ML en curso, espera a la próxima corrida. Las propuestas
    que fallaron se reintentan a las 6 horas, hasta 3 veces.
    """
    estado = cargar()
    if not CFG["activo"] or not estado.get("user_id"):
        print("Mercado Libre todavía no está conectado (o está apagado en config.yaml)")
        return
    en_curso = json.loads(subprocess.run(
        ["gh", "run", "list", "--workflow", "mercadolibre.yml", "--repo", REPO, "--limit", "10", "--json", "status"],
        capture_output=True, text=True, check=True).stdout)
    if any(r["status"] in ("queued", "in_progress", "waiting", "pending", "requested") for r in en_curso):
        print("Hay un workflow de Mercado Libre en curso; la próxima propuesta sale en la siguiente corrida")
        return
    ahora = time.time()
    publicados = {i["producto"] for i in calendario.cargar()
                  if i["estado"] == "publicado" and i["tipo"] != "STORY" and i.get("producto")}
    reintentar = {s for s, p in estado["productos"].items()
                  if p.get("estado") in ("error", "preparando") and p.get("intentos", 0) < 3
                  and ahora - p.get("desde", 0) > 6 * 3600}
    candidatos = sorted((publicados - set(estado["productos"])) | reintentar)
    candidatos = [s for s in candidatos if (RAIZ / "productos" / s / "info.yaml").exists()]
    if not candidatos:
        print("Nada nuevo para proponer")
        return
    subprocess.run(["gh", "workflow", "run", "mercadolibre.yml", "--repo", REPO, "--ref", "main",
                    "-f", "accion=proponer", "-f", f"producto={candidatos[0]}"], check=True)
    print(f"{candidatos[0]}: propuesta en preparación ({len(candidatos) - 1} más en cola)")


def proponer(slug):
    from . import fotos_ml
    estado = cargar()
    info = info_producto(slug)
    calc = calcular(info, estado["user_id"])
    pack = (calc["elegido"] or calc["filas"][-1])["pack"]
    fotos_ml.generar(slug, pack)
    p = estado["productos"].get(slug, {})
    p.update({"codigo": p.get("codigo") or estado["siguiente"], "estado": "propuesto" if calc["elegido"] else "no_conviene",
              "pack": pack, "categoria": calc["categoria"], "categoria_nombre": calc["categoria_nombre"],
              "calculo": calc["filas"], "referencia": calc["referencia"],
              "envio_estimado": sorted(ENVIO_ESTIMADO),
              "fecha": datetime.now(ARG).strftime("%Y-%m-%d")})
    if p["codigo"] == estado["siguiente"]:
        estado["siguiente"] += 1
    estado["productos"][slug] = p
    guardar(estado)
    print(f"{slug}: pack x{pack} ({p['estado']})")


def url_foto(slug, nombre, sha):
    return f"https://raw.githubusercontent.com/{REPO}/{sha}/productos/{slug}/fotos/ml/{nombre}"


def avisar(slug, sha):
    estado = cargar()
    p = estado["productos"][slug]
    info = info_producto(slug)
    f = next(x for x in p["calculo"] if x["pack"] == p["pack"])
    envio = plata(f["envio"]) if f["envio"] else "$0 (lo paga el comprador)"
    if f["pack"] in p.get("envio_estimado", []):
        envio += " (estimado: activá Mercado Envíos para el valor real)"
    otras = "\n".join(f"• x{x['pack']}: {plata(x['precio'])} → te quedan {plata(x['ganancia'])}"
                      for x in p["calculo"] if x["pack"] != p["pack"])
    ref = f" (avisos parecidos en ML: ~{plata(p['referencia'])})" if p.get("referencia") else ""
    if p["estado"] == "propuesto":
        cabeza = f"🛒 <b>Mercado Libre · propuesta #{p['codigo']}</b>"
        pie = f"Respondé <b>ML SI {p['codigo']}</b> para publicarlo o <b>ML NO {p['codigo']}</b>."
    else:
        cabeza = f"⚠️ <b>Mercado Libre · #{p['codigo']}: no llega a la ganancia mínima</b>"
        pie = (f"Ni el pack más grande deja {plata(CFG['ganancia_minima'])}. Si igual lo querés publicar en x{p['pack']}, "
               f"respondé <b>ML SI {p['codigo']}</b>; si no, <b>ML NO {p['codigo']}</b>.")
    texto = (f"{cabeza}\n<b>{info['nombre']}</b> · pack x{p['pack']}\n"
             f"Categoría: {p['categoria_nombre']}\n\n"
             f"Precio: <b>{plata(f['precio'])}</b>{ref}\n"
             f"Comisión + cargo fijo ML: −{plata(f['comision'])}\n"
             f"Envío a tu cargo: {envio}\n"
             f"Filamento: −{plata(f['filamento'])}\n"
             f"<b>Te queda: {plata(f['ganancia'])} por venta</b>\n\n"
             f"Otras opciones:\n{otras}\n\n{pie}")
    fotos = [url_foto(slug, n, sha) for n in ("1-portada.jpg", "6-medidas.jpg", "7-colores.jpg")
             if (RAIZ / "productos" / slug / "fotos" / "ml" / n).exists()]
    telegram.enviar(texto, fotos)
    p["sha_fotos"] = sha
    guardar(estado)
    planilla("Publicaciones", p["codigo"], fila_publicacion(slug, p, f))


def fila_publicacion(slug, p, f):
    return {"Código": p["codigo"], "Producto": info_producto(slug)["nombre"], "Pack": f"x{f['pack']}",
            "Precio": f["precio"], "Comisión ML": f["comision"], "Envío a cargo": f["envio"],
            "Filamento": f["filamento"], "Ganancia": f["ganancia"], "Categoría": p["categoria_nombre"],
            "Estado": p["estado"], "Link": p.get("link", ""), "Actualizado": datetime.now(ARG).strftime("%Y-%m-%d %H:%M")}


def aprobaciones():
    """Lee 'ML SI 4, 5' / 'ML NO 4' en los mensajes de Telegram y lanza la publicación."""
    estado, tg = cargar(), telegram.cargar()
    por_codigo = {p.get("codigo"): s for s, p in estado["productos"].items()}
    for m in tg["mensajes"]:
        r = re.match(r"\s*ML\s+(SI|SÍ|NO)\s+([\d,\sy]+)$", m["texto"], re.I)
        if m["procesado"] or not r:
            continue
        si = r.group(1).upper() != "NO"
        for codigo in map(int, re.findall(r"\d+", r.group(2))):
            slug = por_codigo.get(codigo)
            if not slug or estado["productos"][slug]["estado"] not in ("propuesto", "no_conviene"):
                continue
            accion = "publicar" if si else "rechazar"
            subprocess.run(["gh", "workflow", "run", "mercadolibre.yml", "--repo", REPO, "--ref", "main",
                            "-f", f"accion={accion}", "-f", f"producto={slug}"], check=True)
            print(f"#{codigo} {slug}: {accion}")
        m["procesado"] = True
    telegram.guardar(tg)


# ---------- publicación ----------

def titulo(info, n):
    base = info.get("ml_titulo") or info["nombre"]
    if "golf" not in base.lower():
        base += " Golf"
    t = f"{base} Pack x{n}" if n > 1 else base
    return (t + " Impreso 3D" if len(t) <= 49 else t)[:60]


def descripcion(info, n, colores, con_variantes):
    m = info.get("medidas_mm")
    lineas = [info["nombre"].upper(), "", info.get("descripcion", "").strip(), ""]
    if n > 1:
        lineas.append(f"Pack de {n} unidades.")
    lineas += [f"Material: {CONFIG['produccion']['material']} (impreso en 3D).", f"Peso por unidad: {round(info['gramos'])} g."]
    if m and len(info.get("piezas", [])) == 1:
        lineas.append(f"Medidas aproximadas: {m['largo']} x {m['ancho']} x {m['alto']} mm.")
    lineas.append("")
    if con_variantes:
        lineas.append("Elegí el color al comprar.")
    else:
        lineas.append(f"Colores disponibles: {', '.join(c.capitalize() for c in colores)} y más. "
                      "Después de la compra indicanos por mensaje el color que querés.")
    lineas += ["", f"Se fabrica a pedido: se despacha dentro de los {CFG['dias_preparacion']} días hábiles.",
               "Diseños GolfCraft3D."]
    if info.get("autor") and info.get("licencia"):
        lineas.append(f"Diseño original: {info['autor']} (licencia {info['licencia']}).")
    return "\n".join(lineas)


def armar_item(slug, p, info):
    sha = p["sha_fotos"]
    f = next(x for x in p["calculo"] if x["pack"] == p["pack"])
    n, precio = p["pack"], f["precio"]
    carpeta = RAIZ / "productos" / slug / "fotos" / "ml"
    fotos = sorted(x.name for x in carpeta.glob("[0-9]-*.jpg"))
    colores = info.get("colores_png") or info.get("colores") or []
    atributos = {a["id"]: a for a in api("GET", f"/categories/{p['categoria']}/attributes", auth=False)}
    con_variantes = "COLOR" in atributos and atributos["COLOR"].get("tags", {}).get("allow_variations")
    gtin = {"id": "EMPTY_GTIN_REASON", "value_id": GTIN_PACK if n > 1 else GTIN_SIN_CODIGO}
    item = {
        "title": titulo(info, n), "category_id": p["categoria"], "price": precio, "currency_id": "ARS",
        "available_quantity": CFG["stock"], "buying_mode": "buy_it_now", "condition": "new",
        "listing_type_id": CFG["tipo_publicacion"],
        "sale_terms": [{"id": "MANUFACTURING_TIME", "value_name": f"{CFG['dias_preparacion']} días"}],
        "shipping": {"mode": "me2", "local_pick_up": False, "free_shipping": precio >= CFG["umbral_envio_gratis"]},
        "attributes": [{"id": "BRAND", "value_name": "GolfCraft3D"}, {"id": "MODEL", "value_name": info["nombre"][:60]}],
    }
    if con_variantes:
        variantes = [url_foto(slug, f"color-{c}.jpg", sha) for c in colores]
        item["pictures"] = [{"source": u} for u in [url_foto(slug, x, sha) for x in fotos][:12 - len(variantes)] + variantes]
        item["variations"] = [{"attribute_combinations": [{"id": "COLOR", "value_name": c.capitalize()}],
                               "price": precio, "available_quantity": CFG["stock"], "picture_ids": [u],
                               "attributes": [gtin]} for c, u in zip(colores, variantes)]
    else:
        item["pictures"] = [{"source": url_foto(slug, x, sha)} for x in fotos][:12]
        item["attributes"].append(gtin)
    return item, descripcion(info, n, colores, con_variantes)


def publicar(slug):
    estado = cargar()
    p = estado["productos"][slug]
    if p.get("item_id"):
        print(f"{slug} ya está publicado ({p['item_id']})")
        return
    info = info_producto(slug)
    item, texto = armar_item(slug, p, info)
    try:
        api("POST", "/items/validate", json=item)
        nuevo = api("POST", "/items", json=item)
    except ErrorML as e:
        p["estado"] = "error"
        guardar(estado)
        telegram.enviar(f"⚠️ <b>Mercado Libre no aceptó #{p['codigo']} {info['nombre']}</b>\n{e}\n\n"
                        "No se publicó nada. Lo reviso en la rutina de la semana.")
        raise
    api("POST", f"/items/{nuevo['id']}/description", json={"plain_text": texto})
    p.update({"estado": "publicado", "item_id": nuevo["id"], "link": nuevo.get("permalink", ""),
              "status_ml": nuevo.get("status")})
    guardar(estado)
    f = next(x for x in p["calculo"] if x["pack"] == p["pack"])
    planilla("Publicaciones", p["codigo"], fila_publicacion(slug, p, f))
    telegram.enviar(f"✅ <b>Publicado en Mercado Libre</b>: {item['title']}\n{plata(item['price'])} · "
                    f"te quedan ~{plata(f['ganancia'])} por venta\n<a href=\"{p['link']}\">Ver publicación</a>")


# ---------- ventas, preguntas y avisos ----------

def dias_habiles(desde, n):
    d = desde
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def slug_de_item(estado, item_id):
    return next((s for s, p in estado["productos"].items() if p.get("item_id") == item_id), None)


def procesar_orden(orden_id, avisar_nueva=True):
    estado = cargar()
    o = api("GET", f"/orders/{orden_id}")
    if o.get("status") not in ("paid", "confirmed"):
        return
    fecha = datetime.fromisoformat(o["date_created"]).astimezone(ARG)
    limite = dias_habiles(fecha, CFG["dias_preparacion"])
    lineas, productos, colores = [], [], []
    comision_total = filamento = 0
    for it in o.get("order_items", []):
        slug = slug_de_item(estado, it["item"]["id"])
        p = estado["productos"].get(slug, {})
        color = ", ".join(v.get("value_name", "") for v in it["item"].get("variation_attributes", [])
                          if v.get("id") == "COLOR") or "a confirmar por mensaje"
        unidades = it["quantity"] * p.get("pack", 1)
        comision_total += (it.get("sale_fee") or 0) * it["quantity"]
        if slug:
            filamento += costo_filamento(info_producto(slug)) * unidades
        productos.append(it["item"]["title"])
        colores.append(color)
        lineas.append(f"• {it['item']['title']} · {it['quantity']} × pack = <b>{unidades} unidades</b> · Color: <b>{color}</b>")
    ganancia = o["total_amount"] - comision_total - filamento
    nueva = planilla("Ventas", o["id"], {
        "Orden": o["id"], "Fecha": fecha.strftime("%Y-%m-%d %H:%M"), "Producto": " + ".join(productos),
        "Unidades": sum(it["quantity"] for it in o.get("order_items", [])), "Color": " / ".join(colores),
        "Cobrado": o["total_amount"], "Comisión ML": round(comision_total), "Ganancia aprox.": round(ganancia),
        "Comprador": (o.get("buyer") or {}).get("nickname", ""), "Despachar antes de": limite.strftime("%Y-%m-%d"),
        "Estado": o["status"]})
    if nueva or (nueva is None and avisar_nueva):
        telegram.enviar("🛒 <b>¡Venta en Mercado Libre!</b>\n" + "\n".join(lineas) +
                        f"\nCobrado: {plata(o['total_amount'])} · te quedan aprox. {plata(ganancia)}\n\n"
                        f"<b>Imprimí y despachá antes del {limite.strftime('%d/%m')}</b>.\n"
                        "La etiqueta está en la app de Mercado Libre > Ventas.")
    print("orden procesada")


def procesar_pregunta(pregunta_id, avisar_nueva=True):
    q = api("GET", f"/questions/{pregunta_id}")
    if q.get("status") != "UNANSWERED":
        return
    item = api("GET", f"/items/{q['item_id']}")
    nueva = planilla("Preguntas", q["id"], {"Id": q["id"], "Fecha": q.get("date_created", "")[:16].replace("T", " "),
                                           "Producto": item.get("title", ""), "Pregunta": q.get("text", ""),
                                           "Estado": "sin responder"})
    if nueva or (nueva is None and avisar_nueva):
        telegram.enviar(f"❓ <b>Pregunta en Mercado Libre</b> sobre <i>{item.get('title', '')}</i>:\n"
                        f"«{q.get('text', '')}»\n\nRespondela desde la app de Mercado Libre > Preguntas "
                        "(responder rápido mejora tu reputación).")
    print("pregunta procesada")


def procesar_aviso(item_id):
    estado = cargar()
    slug = slug_de_item(estado, item_id)
    if not slug:
        return
    item = api("GET", f"/items/{item_id}")
    p = estado["productos"][slug]
    if item.get("status") != p.get("status_ml"):
        if item.get("status") in ("paused", "closed", "under_review", "inactive"):
            motivo = ", ".join(item.get("sub_status") or []) or "sin detalle"
            telegram.enviar(f"⚠️ <b>Tu publicación cambió a «{item['status']}»</b>: {item.get('title', '')}\n"
                            f"Motivo: {motivo}\n<a href=\"{item.get('permalink', '')}\">Ver publicación</a>")
        p["status_ml"] = item.get("status")
        guardar(estado)
    print("aviso procesado")


def evento(topic, recurso):
    rid = recurso.rstrip("/").split("/")[-1]
    if topic in ("orders_v2", "orders"):
        procesar_orden(rid)
    elif topic == "questions":
        procesar_pregunta(rid)
    elif topic == "items":
        procesar_aviso(rid)
    elif topic in ("claims", "post_purchase"):
        telegram.enviar("🚨 <b>Se abrió un reclamo en una venta de Mercado Libre.</b>\n"
                        "Revisalo hoy en la app (Ventas > Reclamos): responder rápido evita que afecte tu reputación.")
    elif topic == "messages":
        telegram.enviar("💬 <b>Un comprador te escribió en Mercado Libre.</b> Respondelo desde la app > Ventas.")
    print(f"evento {topic} ok")


def revisar():
    """Red de seguridad por si se pierde una notificación: renueva el permiso y repasa ventas y preguntas."""
    if not CFG["activo"] or not os.environ.get("ML_REFRESH_TOKEN") or not cargar().get("user_id"):
        print("Mercado Libre no está activo")
        return
    token(margen=3 * 3600)
    estado = cargar()
    desde = (datetime.now(ARG) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000-03:00")
    ordenes = api("GET", "/orders/search", params={"seller": estado["user_id"], "order.status": "paid",
                                                   "order.date_created.from": desde, "sort": "date_desc"})
    for o in ordenes.get("results", []):
        procesar_orden(o["id"], avisar_nueva=False)
    preguntas = api("GET", "/questions/search", params={"seller_id": estado["user_id"], "status": "UNANSWERED",
                                                         "api_version": 4})
    for q in preguntas.get("questions", []):
        procesar_pregunta(q["id"], avisar_nueva=False)
    for p in estado["productos"].values():
        if p.get("item_id"):
            procesar_aviso(p["item_id"])
    print("revisión ok")


def diagnostico():
    """Datos técnicos de la cuenta (sin datos personales) para ver qué falta habilitar."""
    estado = cargar()
    uid = estado["user_id"]
    yo = api("GET", "/users/me")
    print("site_status:", yo.get("status", {}).get("site_status"),
          "| sell:", (yo.get("status", {}).get("sell") or {}).get("allow"),
          "| codes:", (yo.get("status", {}).get("sell") or {}).get("codes"))
    print("shipping_modes:", yo.get("shipping_modes"))
    try:
        pref = api("GET", f"/users/{uid}/shipping_preferences")
        print("modos de envío:", pref.get("modes"))
        print("logísticas:", [(l.get("mode"), [t.get("type") for t in l.get("types", [])]) for l in pref.get("logistics", [])])
    except ErrorML as e:
        print("shipping_preferences:", e)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("pendientes", "aprobaciones", "revisar", "link", "diagnostico"):
        sub.add_parser(c)
    for c in ("proponer", "publicar", "fallo", "rechazar"):
        sub.add_parser(c).add_argument("slug")
    sb = sub.add_parser("subir")
    sb.add_argument("mensaje")
    sb.add_argument("rutas", nargs="*")
    a_ = sub.add_parser("avisar")
    a_.add_argument("slug")
    a_.add_argument("--sha", required=True)
    e = sub.add_parser("evento")
    e.add_argument("topic")
    e.add_argument("recurso")
    sub.add_parser("autorizar").add_argument("codigo")
    a = ap.parse_args()
    if a.cmd == "link":
        link_autorizacion()
    elif a.cmd == "diagnostico":
        diagnostico()
    elif a.cmd in ("pendientes", "aprobaciones", "revisar"):
        globals()[a.cmd]()
    elif a.cmd in ("proponer", "publicar", "fallo", "rechazar"):
        globals()[a.cmd](a.slug)
    elif a.cmd == "subir":
        print(subir(a.mensaje, a.rutas))
    elif a.cmd == "avisar":
        avisar(a.slug, a.sha)
    elif a.cmd == "evento":
        evento(a.topic, a.recurso)
    else:
        autorizar(a.codigo)


if __name__ == "__main__":
    main()
