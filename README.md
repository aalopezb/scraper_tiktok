# TikTok Stats

Herramienta en Python para consultar **datos públicos** de TikTok y verlos en un panel web local.

- **Perfil:** nombre, usuario, seguidores, seguidos, me gustas totales, cantidad de videos, bio y si está verificado.
- **Video:** me gustas, comentarios, compartidos, guardados, reproducciones, interacciones totales y tasa de interacción (%).

> TikTok no entrega comentarios ni me gustas "por perfil", solo el total del perfil. El detalle de me gustas y comentarios se obtiene por video.

## Qué se usó

| Parte | Tecnología |
|---|---|
| Scraper | Python 3.10+, librería `requests`, módulos estándar (`re`, `json`, `csv`, `argparse`) |
| Servidor | `http.server` de la librería estándar de Python (sin Flask) |
| Interfaz | HTML + CSS + JavaScript puro (sin frameworks) |
| Respaldo opcional | `playwright` (Chromium real) cuando TikTok bloquea las peticiones simples |

## Estructura

```
tiktok_scraper.py   Lógica: descarga la página y extrae los datos. Se puede usar por consola.
server.py           Servidor local que expone /api/profile y /api/video y sirve index.html.
index.html          Panel web: formulario, tarjetas, tabla comparativa y descarga CSV.
README.md           Este archivo.
```

## Cómo funciona

1. TikTok incluye en el HTML de cada perfil/video un bloque JSON (`__UNIVERSAL_DATA_FOR_REHYDRATION__`) con las estadísticas.
2. `tiktok_scraper.py` descarga la página con `requests`, localiza ese bloque con una expresión regular y lo convierte a diccionario.
3. `server.py` recibe peticiones del navegador, llama al scraper y devuelve JSON.
4. `index.html` consulta al servidor con `fetch()` y dibuja los resultados.

```
Navegador (index.html) -> server.py -> tiktok_scraper.py -> tiktok.com
```

## Instalación en otra computadora

Requisitos: **Python 3.10 o superior** e internet.

```bash
# 1. Copia la carpeta con los 4 archivos y entra en ella
cd carpeta_del_proyecto

# 2. (Recomendado) crea un entorno virtual
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac / Linux:
source venv/bin/activate

# 3. Instala la dependencia
pip install requests

# 4. (Opcional) respaldo con navegador real
pip install playwright
playwright install chromium
```

## Uso

### Panel web

```bash
python server.py
```

Abre http://127.0.0.1:8000, elige la pestaña **Perfil** o **Video**, escribe el usuario (o la URL del video) y pulsa **Buscar**.

### Consola

```bash
python tiktok_scraper.py usuario1 usuario2 --csv perfiles.csv
python tiktok_scraper.py --video https://www.tiktok.com/@usuario/video/1234567890
```

## Cómo comprobar que funciona (checklist)

1. `python --version` muestra 3.10 o superior.
2. `python -c "import requests; print(requests.__version__)"` no da error.
3. `python tiktok_scraper.py tiktok` imprime nombre, seguidores, etc. de la cuenta oficial. Si falla aquí, el problema es el scraper o el bloqueo de TikTok, no el panel.
4. `python server.py` muestra "Panel en http://127.0.0.1:8000".
5. En el navegador, busca un usuario: debe aparecer una tarjeta y una fila en la tabla comparativa.
6. Prueba la pestaña **Video** con la URL completa de un video público.
7. Pulsa **Descargar CSV** y revisa que el archivo se abre en Excel.

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| "No se encontró el JSON de datos" / HTTP 403 | TikTok detectó tráfico automático o muestra captcha | Instalar Playwright (paso 4), esperar unos minutos, cambiar de red/IP |
| `SyntaxError` en `dict \| None` | Python menor a 3.10 | Actualizar Python |
| "No se encontró el usuario" | Usuario mal escrito o cuenta inexistente/privada | Verificar el nombre |
| El video no se lee | Video privado, eliminado o con restricción de región | Probar con otro video público |
| Puerto 8000 ocupado | Otro programa lo usa | Cambiar el puerto al final de `server.py` |

## Limitaciones y aviso legal

- Es scraping de la web pública: TikTok cambia su estructura con frecuencia y puede dejar de funcionar sin previo aviso.
- Hacer scraping va en contra de los términos de uso de TikTok. Úsalo solo con datos públicos, a baja frecuencia y con fines personales o educativos.
- Para uso comercial o a gran escala, usa la **API oficial de TikTok** (Research API / Display API).
- El servidor solo escucha en `127.0.0.1` (tu propia máquina) y solo acepta URLs de tiktok.com.
