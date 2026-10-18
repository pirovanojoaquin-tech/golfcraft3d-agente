# Agente de marketing de GolfCraft3D

Publica automáticamente en Instagram (@golfcraft3d) **1 carrusel y 3 historias por día**.

## Cómo funciona

```
 Cada semana (Claude)                         Todos los días (GitHub Actions)
 ─────────────────────                        ────────────────────────────────
 lee productos/ y AGENTE.md                   10:00  historia 1
 escribe planes/AAAA-MM-DD.yaml        ──►    12:30  carrusel
 genera las imágenes (agente/planificar.py)   16:00  historia 2
 sube todo al repo                            20:30  historia 3
                                              (agente/publicar.py)
```

- `productos/` — una carpeta por producto con `info.yaml` y sus fotos en `fotos/`.
- `AGENTE.md` — estrategia, tono y reglas que sigue el agente al escribir.
- `config.yaml` — colores, horarios y hashtags fijos.
- `contenido/calendario.json` — la cola de publicaciones y su estado (pendiente / publicado / error).
- `contenido/media/` — las imágenes ya armadas de cada día.

## Cargar un producto

1. En GitHub: **Add file → Upload files**.
2. Arrastrá las fotos y escribí como nombre de carpeta `productos/<nombre-del-producto>/fotos/`.
3. Copiá `productos/_plantilla/info.yaml` a `productos/<nombre-del-producto>/info.yaml` y completalo.

## Configuración inicial (una sola vez)

### 1. Instagram
La cuenta tiene que ser **profesional de tipo Empresa**.

### 2. App de Meta y token
1. Entrá a https://developers.facebook.com/apps con tu Facebook → **Crear app**.
2. Caso de uso: **"Administrar mensajes y contenido en Instagram"** → tipo **Empresa**.
3. En **Configuración de la API con inicio de sesión de Instagram** → *Generar tokens de acceso* →
   **Agregar cuenta** → entrá con @golfcraft3d y aceptá los permisos.
4. Copiá el token que aparece (empieza con `IG...`). **No lo compartas en ningún chat.**

### 3. Secretos en GitHub
En el repo: **Settings → Secrets and variables → Actions → New repository secret**
- `IG_ACCESS_TOKEN` = el token del paso anterior.
- `GH_PAT` = un token de GitHub para renovar el de Instagram solo:
  https://github.com/settings/personal-access-tokens/new → *Only select repositories* (este repo) →
  permiso **Secrets: Read and write**.

### 4. Probar
**Actions → Publicar en Instagram → Run workflow → modo `verificar`**. Si muestra el usuario
`golfcraft3d`, está todo listo.

## Comandos útiles (local)

```bash
pip install -r requirements.txt
python -m agente.planificar planes/2026-10-20.yaml    # genera imágenes + calendario
python -m agente.publicar --simular                   # qué se publicaría ahora
```

## Google Drive

- Carpeta: **PRODUCTOS 3D GOLF** (Drive de pirovanojoaquin@gmail.com).
- El programa de Apps Script (`herramientas/guardar_en_drive.gs`) está instalado en la cuenta
  **franciscopirovano@gmail.com**, que tiene permiso de edición sobre la carpeta. Si se deja de
  compartir la carpeta con esa cuenta, el guardado en Drive falla con "No item with the given ID".
- La URL de la aplicación web (termina en `/exec`) está en el secreto `DRIVE_WEBAPP_URL`.
