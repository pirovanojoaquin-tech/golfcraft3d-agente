"""Cliente mínimo de la API de Instagram (Instagram API with Instagram Login).

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
"""
import time

import requests

HOST = "https://graph.instagram.com"


class ErrorInstagram(Exception):
    pass


class Instagram:
    def __init__(self, token, api_version="v23.0"):
        self.token = token
        self.base = f"{HOST}/{api_version}"
        self._user_id = None

    def _req(self, metodo, ruta, **params):
        params["access_token"] = self.token
        if metodo == "GET":
            r = requests.get(f"{self.base}/{ruta}", params=params, timeout=60)
        else:
            r = requests.post(f"{self.base}/{ruta}", data=params, timeout=60)
        datos = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in datos:
            raise ErrorInstagram(f"{metodo} {ruta} -> {r.status_code}: {datos.get('error', datos)}")
        return datos

    @property
    def user_id(self):
        if self._user_id is None:
            self._user_id = self._req("GET", "me", fields="user_id,username")["user_id"]
        return self._user_id

    def cuenta(self):
        return self._req("GET", "me", fields="user_id,username,account_type,media_count")

    def _esperar(self, contenedor_id, intentos=30):
        for _ in range(intentos):
            estado = self._req("GET", contenedor_id, fields="status_code")["status_code"]
            if estado == "FINISHED":
                return
            if estado in ("ERROR", "EXPIRED"):
                raise ErrorInstagram(f"El contenedor {contenedor_id} quedó en estado {estado}")
            time.sleep(5)
        raise ErrorInstagram(f"El contenedor {contenedor_id} no terminó de procesarse")

    def _publicar(self, contenedor_id, intentos=4):
        self._esperar(contenedor_id)
        for n in range(intentos):
            try:
                return self._req("POST", f"{self.user_id}/media_publish", creation_id=contenedor_id)["id"]
            except ErrorInstagram as e:
                # Instagram a veces responde "The requested resource does not exist" (code 24) si se publica
                # apenas el contenedor quedó listo: esperamos y reintentamos.
                if "'code': 24" not in str(e) or n == intentos - 1:
                    raise
                time.sleep(15 * (n + 1))

    def publicar_imagen(self, url, caption):
        c = self._req("POST", f"{self.user_id}/media", image_url=url, caption=caption)["id"]
        return self._publicar(c)

    def publicar_carrusel(self, urls, caption):
        if not 2 <= len(urls) <= 10:
            raise ValueError("Un carrusel necesita entre 2 y 10 imágenes")
        hijos = []
        for url in urls:
            h = self._req("POST", f"{self.user_id}/media", image_url=url, is_carousel_item="true")["id"]
            self._esperar(h)
            hijos.append(h)
        c = self._req("POST", f"{self.user_id}/media", media_type="CAROUSEL",
                      children=",".join(hijos), caption=caption)["id"]
        return self._publicar(c)

    def publicar_historia(self, url):
        c = self._req("POST", f"{self.user_id}/media", image_url=url, media_type="STORIES")["id"]
        return self._publicar(c)

    def limite_publicacion(self):
        return self._req("GET", f"{self.user_id}/content_publishing_limit", fields="quota_usage,config")
