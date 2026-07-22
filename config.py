"""Configuración central del digest: fuentes, horario, formato y Gemini."""

# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------

RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Wired": "https://www.wired.com/feed/rss",
}

USER_AGENT = "whatsapp-news-digest/1.0 (GitHub Actions; digest personal)"

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_ITEMS_TO_CHECK = 40  # cuántos top stories de HN revisar
HN_MIN_SCORE = 80       # solo considerar historias con este puntaje o más
HN_MAX_WORKERS = 8      # consultas en paralelo a la API de HN

MAX_ITEMS_PER_RSS_FEED = 12
RSS_TIMEOUT = 30          # segundos máximos de descarga por feed
HOURS_LOOKBACK = 30       # ventana de tiempo para considerar una noticia "de hoy"
EXCERPT_MAX_CHARS = 1000  # largo máximo del extracto RSS que se le pasa a Gemini

# ---------------------------------------------------------------------------
# Horario, estado e historial
# ---------------------------------------------------------------------------

TIMEZONE = "America/Santiago"
SEND_HOUR_LOCAL = 8    # hora local (Chile) a la que debe LLEGAR el mensaje
# Los cron de GitHub Actions suelen atrasarse (a veces más de una hora), así
# que el workflow parte varias veces ANTES de las 08:00: la ejecución que cae
# dentro de esta antesala prepara el digest y duerme hasta las 08:00:00 en
# punto para enviar. Ejecuciones más tempranas que esto salen sin hacer nada.
MAX_WAIT_MINUTES = 100
# Si todas las ejecuciones tempranas se atrasaron más allá de las 08:00, se
# acepta enviar de inmediato hasta esta hora local inclusive (08:00-09:59).
# El control de ya-enviado evita duplicados; la ejecución sobrante queda como
# reintento automático si la primera falló.
SEND_WINDOW_END_LOCAL = 9
STATE_PATH = "digest_state.json"
HISTORY_DAYS = 7       # días hacia atrás para no repetir noticias
SENT_KEEP_DAYS = 14    # cuánto conservar el registro de envíos

# ---------------------------------------------------------------------------
# Formato del digest
# ---------------------------------------------------------------------------

MIN_NEWS = 4
MAX_NEWS = 5
MAX_SUMMARY_CHARS = 350   # tope por resumen individual
MAX_MESSAGE_CHARS = 3500  # tope del mensaje completo de WhatsApp

# CallMeBot mutila los mensajes que superan ~700 caracteres: corta a mitad
# de palabra, descarta texto e inserta su propio separador "__________".
# Por eso cada parte (incluido el sufijo "Parte i/n") debe quedar bajo ese
# umbral con margen.
CALLMEBOT_CHUNK_CHARS = 650    # tamaño objetivo de cada parte, sufijo incluido
CALLMEBOT_MAX_CHARS = 700      # tope duro: nunca enviar una parte mayor que esto
CALLMEBOT_DELAY_SECONDS = 3    # pausa entre partes para que lleguen en orden

# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Orden de preferencia de modelos. Primero versiones concretas (más
# predecibles); el alias "latest" queda como respaldo porque puede
# cambiar internamente o estar temporalmente saturado. Si un modelo
# devuelve 404 (no disponible para esta key), se pasa al siguiente.
PREFERRED_MODEL_HINTS = [
    "gemini-3.5-flash-lite",  # suficiente y económico para resumir noticias
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

# Modelos que esta cuenta no puede usar: 2.5 devuelve 404 para cuentas nuevas
# y 2.0 está retirado (429 con cuota limit: 0). Se excluyen del ranking para
# que no reaparezcan por el listado automático de la API.
SKIP_MODEL_PREFIXES = (
    "gemini-2.0-",
    "gemini-2.5-",
)

MAX_MODEL_ATTEMPTS = 5   # cuántos modelos probar antes de rendirse
GEMINI_TIMEOUT = 180     # segundos de espera por respuesta (modelos con thinking demoran)
TRIES_PER_MODEL = 3      # intentos por modelo ante timeout, error de red o 5xx
RETRY_DELAY = 20         # segundos de espera entre reintentos del mismo modelo
