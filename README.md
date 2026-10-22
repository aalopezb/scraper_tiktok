# TikTok Stats

Herramienta en Python para consultar **datos públicos** de TikTok y analizarlos en un panel web local.

Tiene tres modos:

| Modo | Qué entrega | Cómo lo obtiene |
|---|---|---|
| **Perfil** | nombre, usuario, seguidores, seguidos, me gustas totales, videos, bio | `requests` leyendo el HTML público |
| **Video** | me gustas, comentarios, compartidos, guardados, reproducciones, tasa de interacción | `requests` leyendo el HTML público |
| **Análisis (5 videos)** | los 5 últimos videos con sus estadísticas, una muestra de comentarios y dos puntajes (0–100): **Valor** y **Veracidad**, con gráfica | Navegador real (Playwright) con sesión/cookies guardadas |

> TikTok no entrega comentarios ni me gustas "por perfil", solo el total. El detalle sale por video.

## Qué se usó

| Parte | Tecnología |
|---|---|
| Perfil y video sueltos | Python 3.10+, `requests`, `re`, `json`, `csv`, `argparse` |
| Últimos videos y comentarios | `playwright` (Chromium real) que intercepta las respuestas internas `/api/post/item_list` y `/api/comment/list` |
| Análisis | Python estándar (`statistics`, `re`, `collections`), sin librerías extra |
| Servidor | `http.server` (`ThreadingHTTPServer`), sin Flask |
| Interfaz y gráfica | HTML + CSS + JavaScript puro; la gráfica es SVG dibujado a mano |

## Estructura

```
tiktok_scraper.py   Perfil y video por separado (requests). Se usa por consola o desde el servidor.
tiktok_videos.py    Últimos N videos + comentarios con Playwright, sesión persistente y cookies.
analysis.py         Puntajes de Valor y Veracidad, alertas y análisis de comentarios.
analyze.py          Comando de consola para el análisis completo (guarda un JSON).
server.py           Servidor local: /api/profile, /api/video, /api/analysis y sirve index.html.
index.html          Panel web: pestañas, tarjetas, tabla comparativa, gráfica de análisis.
.gitignore          Evita subir la sesión del navegador y las cookies.
README.md           Este archivo.
```

## Cómo funciona

```
Navegador (index.html) -> server.py -> tiktok_scraper.py -> tiktok.com        (Perfil / Video)
                                    -> tiktok_videos.py  -> Chromium -> tiktok.com
                                    -> analysis.py       -> puntajes          (Análisis)
```

1. **Perfil / Video:** TikTok incluye en su HTML un bloque JSON (`__UNIVERSAL_DATA_FOR_REHYDRATION__`) con las estadísticas. `tiktok_scraper.py` lo descarga y lo lee.
2. **Análisis:** la lista de videos y los comentarios no vienen en ese HTML; la página los pide después a endpoints internos firmados. En vez de falsificar esa firma, `tiktok_videos.py` abre un Chromium real, navega como una persona e **intercepta las respuestas** que TikTok ya envía al navegador.
3. Se toman los 5 videos más recientes (por fecha de publicación), se abre cada uno y se guarda una muestra de comentarios.
4. `analysis.py` calcula los puntajes y `index.html` los dibuja.

## Sesión y cookies

TikTok bloquea con frecuencia a los visitantes anónimos, por eso el modo Análisis usa una sesión:

- **Sesión persistente (recomendada):** el navegador guarda su perfil en `./tiktok_session`. Se inicia sesión o se resuelve el captcha **una sola vez**:
  ```bash
  python analyze.py --login
  ```
- **Cookies exportadas (opcional):** exporta tus cookies de tiktok.com en formato JSON (por ejemplo con la extensión *Cookie-Editor*), guárdalas como `cookies.json` junto al proyecto y el servidor las usará solas. En consola: `--cookies cookies.json`.

> **Seguridad:** `tiktok_session/` y `cookies.json` equivalen a tener tu cuenta abierta. No los compartas ni los subas a ningún repositorio (el `.gitignore` ya los excluye). Lo ideal es usar una **cuenta secundaria**, porque TikTok puede limitar cuentas que automatizan.

## Qué significan Valor y Veracidad

Ambos van de 0 a 100 y se calculan por video; el de la cuenta es el promedio de los videos.

**Valor** = qué tan bien rinde el contenido:
- 40 % tasa de interacción: (me gustas + comentarios + compartidos + guardados) / reproducciones. 10 % equivale a 100 puntos.
- 20 % alcance: reproducciones / seguidores.
- 25 % conversación: (comentarios + compartidos) / reproducciones.
- 15 % sentimiento de los comentarios de la muestra (positivos vs. negativos).

**Veracidad** = qué tan orgánica parece la interacción:
- 35 % proporción me gustas / reproducciones (hasta 20 % es normal; por encima baja).
- 30 % comentarios por me gusta (menos de 0,05 % sugiere me gustas comprados o inflados).
- 35 % calidad de comentarios: porcentaje de comentarios únicos, spam/promoción ("sígueme", enlaces…) y solo emojis.

Si falta una señal (por ejemplo no se pudieron leer comentarios), las demás se reponderan. Cada video también muestra **alertas** en lenguaje claro, como "33 % de los comentarios parecen spam".

**Interpretación:** Valor ≥ 70 alto, 40–69 medio, < 40 bajo. Veracidad ≥ 75 alta, 50–74 media, < 50 baja.

> **Son heurísticas, no pruebas.** Los umbrales son aproximaciones típicas, la muestra es de unos 10 comentarios por video (los que TikTok muestra primero, ordenados por relevancia) y un video viral puede verse "raro" sin serlo. Un puntaje bajo es motivo para revisar la cuenta a mano, no para acusarla.

## Instalación en otra computadora

Requisitos: **Python 3.10 o superior** e internet.

```bash
# 1. Copia la carpeta con todos los archivos y entra en ella
cd carpeta_del_proyecto

# 2. (Recomendado) entorno virtual
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac / Linux:
source venv/bin/activate

# 3. Dependencias
pip install requests playwright
playwright install chromium

# 4. (Solo modo Análisis) iniciar sesión una vez
python analyze.py --login
```

Los modos Perfil y Video solo necesitan `requests`; Playwright es obligatorio únicamente para el Análisis.

## Uso

### Panel web

```bash
python server.py
```

Abre http://127.0.0.1:8000 y elige una pestaña:

- **Perfil / Video:** escribe el usuario o la URL del video y pulsa **Buscar**.
- **Análisis (5 videos):** escribe el usuario y pulsa **Analizar**. Se abre una ventana de Chromium (tarda 1–2 minutos). Si aparece un captcha, resuélvelo ahí. El resultado muestra los puntajes, la gráfica de barras Valor vs. Veracidad por video y, desplegando cada video, sus métricas, alertas y comentarios de muestra.

Para ejecutar el navegador sin ventana (más fácil de bloquear): `TIKTOK_HEADLESS=1 python server.py`.

### Consola

```bash
python tiktok_scraper.py usuario1 usuario2 --csv perfiles.csv
python tiktok_scraper.py --video https://www.tiktok.com/@usuario/video/1234567890

python analyze.py usuario
python analyze.py usuario --videos 5 --comments 10 --out resultado.json
python analyze.py usuario --cookies cookies.json
```

## Cómo comprobar que funciona (checklist)

1. `python --version` muestra 3.10 o superior.
2. `python -c "import requests, playwright; print('ok')"` no da error.
3. `python tiktok_scraper.py tiktok` imprime datos de la cuenta oficial (prueba del modo simple).
4. `python analyze.py --login`, iniciar sesión, pulsar Enter en la consola.
5. `python analyze.py tiktok --videos 2` imprime los puntajes y crea `analisis_tiktok.json`.
6. `python server.py` y, en el panel, probar las tres pestañas.
7. Comprobar que en **Análisis** aparece la gráfica y que los comentarios de cada video se pueden desplegar.

Si el paso 3 funciona pero el 5 no, el problema es la sesión o el bloqueo de TikTok, no el código del panel.

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| "No se encontró el JSON de datos" / HTTP 403 | TikTok detectó tráfico automático (modos Perfil/Video) | Esperar unos minutos, cambiar de red, o usar el modo Análisis |
| "No se pudo obtener la lista de videos" | Captcha, cuenta privada o sin videos | `python analyze.py --login`, resolver el captcha en la ventana, o usar `--cookies` |
| "Falta Playwright" | No está instalado | `pip install playwright && playwright install chromium` |
| "Ya hay un análisis en curso" | Solo se permite uno a la vez (el perfil del navegador no se comparte) | Esperar a que termine el anterior |
| Error de "profile in use" al abrir Chromium | Otro análisis o `--login` abierto con el mismo perfil | Cerrar la otra ventana de Chromium |
| Comentarios vacíos en un video | TikTok no cargó el panel o los comentarios están desactivados | Reintentar; la alerta "No se pudo leer la muestra" lo indica |
| `SyntaxError` en `dict \| None` | Python menor a 3.10 | Actualizar Python |
| Puerto 8000 ocupado | Otro programa lo usa | Cambiar el puerto al final de `server.py` |

## Limitaciones y aviso legal

- TikTok cambia sus endpoints y su HTML con frecuencia: el scraper puede dejar de funcionar sin aviso y necesitar ajustes (en `tiktok_videos.py`, los nombres de endpoints y el selector `data-e2e="comment-icon"`).
- Automatizar TikTok va en contra de sus términos de uso, y usar tu cuenta con cookies puede llevar a limitaciones o bloqueo de esa cuenta. Úsalo solo con datos públicos, a baja frecuencia y con fines personales o educativos.
- Para uso comercial o a gran escala, usa la **API oficial de TikTok** (Research API / Display API).
- El servidor solo escucha en `127.0.0.1` (tu propia máquina) y solo acepta URLs de tiktok.com.
- No se hizo ninguna prueba contra TikTok real: el código se verificó por sintaxis y con datos de ejemplo para el análisis. La primera ejecución real puede requerir ajustes.