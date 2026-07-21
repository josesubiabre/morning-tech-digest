#!/usr/bin/env python3
"""
Digest diario de noticias tech -> resumen con Gemini -> envío por WhatsApp (CallMeBot).

Variables de entorno requeridas (se configuran como GitHub Secrets):
  GEMINI_API_KEY        -> API key de Google AI Studio
  CALLMEBOT_PHONE       -> tu número de WhatsApp en formato internacional, ej: 56912345678
  CALLMEBOT_API_KEY     -> API key que te dio el bot de CallMeBot por WhatsApp

Comportamiento:
  - Solo envía a las 08:00 hora de Chile (America/Santiago). El workflow corre a las
    11:00 y 12:00 UTC; la ejecución que no calza con las 08:00 locales sale sin enviar.
  - Si el digest de hoy ya fue enviado (según digest_state.json), no reenvía.
  - Las ejecuciones manuales (workflow_dispatch) saltan el control de hora.
  - El flag --force salta ambos controles (hora y ya-enviado).

Uso local (para probar):
  export GEMINI_API_KEY=xxx
  export CALLMEBOT_PHONE=xxx
  export CALLMEBOT_API_KEY=xxx
  python news_digest.py --force
"""

import os
import re
import sys
import json
import time
import html
import datetime
import http.client
import urllib.parse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import feedparser

# ---------------------------------------------------------------------------
# Configuración de fuentes
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
HOURS_LOOKBACK = 30       # ventana de tiempo para considerar una noticia "de hoy"
EXCERPT_MAX_CHARS = 1000  # largo máximo del extracto RSS que se le pasa a Gemini

# ---------------------------------------------------------------------------
# Horario, estado e historial
# ---------------------------------------------------------------------------

TIMEZONE = "America/Santiago"
SEND_HOUR_LOCAL = 8    # hora local (Chile) a la que corresponde enviar
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


def log(msg):
    print(f"[news_digest] {msg}", file=sys.stderr)


def now_santiago():
    return datetime.datetime.now(ZoneInfo(TIMEZONE))


def http_get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        log(f"HTTP {e.code} en GET {url.split('?')[0]} -> {body[:300]}")
        raise


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text, limit):
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def normalize_title(title):
    return re.sub(r"[^a-z0-9áéíóúñü ]", "", (title or "").lower()).strip()


def normalize_link(link):
    p = urllib.parse.urlsplit((link or "").strip())
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{host}{p.path.rstrip('/')}"


# ---------------------------------------------------------------------------
# Recolección de noticias
# ---------------------------------------------------------------------------

def fetch_rss_items():
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=HOURS_LOOKBACK)
    items = []

    for source, url in RSS_FEEDS.items():
        try:
            parsed = feedparser.parse(url, agent=USER_AGENT)
        except Exception as e:
            log(f"Error parseando {source}: {e}")
            continue

        count = 0
        for entry in parsed.entries:
            if count >= MAX_ITEMS_PER_RSS_FEED:
                break

            published = None
            for key in ("published_parsed", "updated_parsed"):
                if entry.get(key):
                    published = datetime.datetime(*entry[key][:6])
                    break

            # Si no hay fecha, igual la incluimos (mejor pecar de incluir)
            if published and published < cutoff:
                continue

            excerpt = strip_html(entry.get("summary") or entry.get("description") or "")

            items.append({
                "source": source,
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", "").strip(),
                "published": published.isoformat() if published else None,
                "excerpt": truncate(excerpt, EXCERPT_MAX_CHARS),
            })
            count += 1

    log(f"RSS: {len(items)} items recolectados")
    return items


def fetch_hn_items():
    items = []
    try:
        top_ids = http_get_json(HN_TOP_STORIES_URL, timeout=15)[:HN_ITEMS_TO_CHECK]
    except Exception as e:
        log(f"Error obteniendo top stories de HN: {e}")
        return items

    cutoff_ts = time.time() - HOURS_LOOKBACK * 3600

    def fetch_item(story_id):
        for attempt in (1, 2):
            try:
                return http_get_json(HN_ITEM_URL.format(story_id), timeout=15)
            except Exception as e:
                if attempt == 2:
                    log(f"Error obteniendo item HN {story_id}: {e}")
        return None

    with ThreadPoolExecutor(max_workers=HN_MAX_WORKERS) as pool:
        stories = list(pool.map(fetch_item, top_ids))

    for item in stories:
        if not item:
            continue
        if item.get("score", 0) < HN_MIN_SCORE:
            continue
        # Descartar historias antiguas que siguen sumando votos
        if item.get("time", 0) < cutoff_ts:
            continue

        story_id = item.get("id")
        link = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        items.append({
            "source": "Hacker News",
            "title": item.get("title", "").strip(),
            "link": link,
            "published": None,
            "excerpt": "",
            "score": item.get("score"),
        })

    log(f"Hacker News: {len(items)} items recolectados (score >= {HN_MIN_SCORE})")
    return items


# ---------------------------------------------------------------------------
# Estado: envíos previos e historial para no repetir noticias
# ---------------------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                state = json.load(f)
            if isinstance(state, dict):
                state.setdefault("sent", {})
                state.setdefault("history", {})
                return state
        except (json.JSONDecodeError, OSError) as e:
            log(f"No se pudo leer {STATE_PATH} ({e}); partiendo con estado vacío")
    return {"sent": {}, "history": {}}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    log(f"Estado guardado en {STATE_PATH}")


def prune_state(state, today):
    t = datetime.date.fromisoformat(today)

    def keep(section, max_days):
        pruned = {}
        for date_str, value in section.items():
            try:
                d = datetime.date.fromisoformat(date_str)
            except ValueError:
                continue
            if (t - d).days <= max_days:
                pruned[date_str] = value
        return pruned

    state["sent"] = keep(state["sent"], SENT_KEEP_DAYS)
    state["history"] = keep(state["history"], HISTORY_DAYS)


def recent_coverage(state, today):
    """Devuelve (temas para el prompt, links normalizados, títulos de fuente
    normalizados) de lo enviado en los últimos HISTORY_DAYS días (sin incluir hoy,
    para que un reenvío con --force no se filtre a sí mismo)."""
    topics, links, source_titles = [], set(), set()
    for date_str in sorted(state["history"], reverse=True):
        if date_str == today:
            continue
        for entry in state["history"][date_str]:
            if entry.get("titulo"):
                topics.append(entry["titulo"])
            if entry.get("link"):
                links.add(entry["link"])
            if entry.get("source_title"):
                source_titles.add(entry["source_title"])
    return topics[:40], links, source_titles


def drop_recent_duplicates(items, links, source_titles):
    kept = []
    for item in items:
        if normalize_link(item["link"]) in links:
            continue
        if normalize_title(item["title"]) in source_titles:
            continue
        kept.append(item)
    dropped = len(items) - len(kept)
    if dropped:
        log(f"{dropped} items descartados por haber sido enviados en días anteriores")
    return kept


# ---------------------------------------------------------------------------
# Selección automática de modelo Gemini
# ---------------------------------------------------------------------------

def rank_gemini_models(api_key):
    """Consulta los modelos disponibles para esta key y devuelve una lista
    ordenada de candidatos (mejores primero). No garantiza que funcionen:
    Google a veces lista modelos que luego devuelven 404 para keys nuevas,
    así que el que llama debe probar el siguiente si uno falla."""
    data = http_get_json(f"{GEMINI_BASE}/models?key={api_key}")
    models = data.get("models", [])

    # Solo modelos que soportan generateContent
    usable = []
    for m in models:
        methods = m.get("supportedGenerationMethods", [])
        name = m.get("name", "")  # viene como "models/gemini-2.5-flash"
        short = name.split("/")[-1]
        if "generateContent" not in methods:
            continue
        # Evitar modelos especializados (imagen, audio, embeddings, etc.)
        if any(bad in short for bad in ("image", "tts", "audio", "embedding", "vision")):
            continue
        # Excluir generaciones que esta cuenta no puede usar (404/cuota 0)
        if short.startswith(SKIP_MODEL_PREFIXES):
            continue
        usable.append(short)

    if not usable:
        raise RuntimeError("Tu API key no tiene ningún modelo con generateContent disponible.")

    # Ordenar: primero los que calzan con las pistas (sin preview), luego los
    # que calzan pero son preview, y al final el resto.
    ranked = []
    for allow_preview in (False, True):
        for hint in PREFERRED_MODEL_HINTS:
            for short in usable:
                if short in ranked:
                    continue
                if hint in short and (allow_preview or "preview" not in short):
                    ranked.append(short)
    for short in usable:
        if short not in ranked:
            ranked.append(short)

    log(f"Modelos Gemini candidatos (en orden): {', '.join(ranked[:MAX_MODEL_ATTEMPTS])}")
    return ranked


# ---------------------------------------------------------------------------
# Resumen con Gemini
# ---------------------------------------------------------------------------

def build_prompt(items, recent_topics, today):
    lines = []
    for i, item in enumerate(items, 1):
        score = f" (HN score: {item['score']})" if item.get("score") else ""
        excerpt = item.get("excerpt") or "(sin extracto)"
        lines.append(
            f"{i}. [{item['source']}]{score} {item['title']}\n"
            f"   Extracto: {excerpt}\n"
            f"   Link: {item['link']}"
        )
    raw_list = "\n".join(lines)

    covered = "\n".join(f"- {t}" for t in recent_topics) or "- (nada aún)"

    prompt = f"""Eres el editor de un digest diario de tecnología para un lector en Chile \
interesado en: IA aplicada, startups, producto, infraestructura/cloud, venture capital, \
regulación tecnológica y movimientos de empresas relevantes. Le interesan poco: reviews \
de teléfonos y gadgets menores, gaming y cultura tech.

Abajo tienes la lista cruda de titulares de hoy ({today}), cada uno con su extracto y link.

Tu tarea:
1. Elige entre {MIN_NEWS} y {MAX_NEWS} noticias, las más importantes del día, intentando \
esta mezcla (ajústala si algún rubro no tiene nada relevante hoy):
   - 1 o 2 de IA
   - 1 de startups/producto
   - 1 de big tech/mercado
   - 1 de seguridad, regulación o algo inesperado
2. Elimina duplicados o noticias muy similares (quédate con la mejor fuente).
3. Resume cada noticia elegida en 1-2 frases en español (Chile), directo y sin relleno: \
qué pasó y por qué importa. Usa SOLO hechos respaldados por el titular y el extracto; \
no completes con conocimiento externo ni especules.
4. Escribe además un encabezado editorial de UNA frase que capture el día, por ejemplo: \
"Hoy domina: Google acelera X y el mercado reacciona a Y".
5. Estos temas ya fueron cubiertos en días anteriores; NO los repitas salvo que haya una \
actualización real (y en ese caso menciona que es una actualización):
{covered}

Responde SOLO con un objeto JSON válido, sin texto adicional ni markdown, con esta \
estructura exacta:
{{"encabezado": "...", "noticias": [{{"titulo": "...", "resumen": "...", "link": "..."}}]}}

Reglas del JSON:
- "titulo": corto (máximo 60 caracteres), sin asteriscos ni comillas internas.
- "resumen": 1-2 frases.
- "link": copiado EXACTAMENTE desde la lista de titulares. No lo inventes ni lo modifiques.

Lista cruda de titulares:
{raw_list}
"""
    return prompt


def parse_digest_json(text, items_by_norm_link):
    """Valida la respuesta de Gemini: JSON con encabezado y 1..MAX_NEWS noticias
    cuyos links existan en las fuentes recolectadas. Lanza ValueError si no sirve."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", cleaned).strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("la respuesta no es un objeto JSON")

    encabezado = str(data.get("encabezado") or "").strip()

    noticias, seen = [], set()
    for n in data.get("noticias") or []:
        if not isinstance(n, dict):
            continue
        titulo = str(n.get("titulo") or "").strip().strip("*")
        resumen = str(n.get("resumen") or "").strip()
        link = str(n.get("link") or "").strip()
        if not (titulo and resumen and link):
            continue

        norm = normalize_link(link)
        source_item = items_by_norm_link.get(norm)
        if not source_item:
            log(f"Descartada noticia con link que no está en las fuentes: {link}")
            continue
        if norm in seen:
            continue
        seen.add(norm)

        noticias.append({
            "titulo": truncate(titulo, 80),
            "resumen": truncate(resumen, MAX_SUMMARY_CHARS),
            "link": source_item["link"],
            "norm_link": norm,
            "source_title": normalize_title(source_item["title"]),
        })
        if len(noticias) >= MAX_NEWS:
            break

    if not noticias:
        raise ValueError("el JSON no traía ninguna noticia válida")
    return encabezado, noticias


def summarize_with_gemini(items, api_key, recent_topics, items_by_norm_link, today):
    prompt = build_prompt(items, recent_topics, today)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")

    candidates = rank_gemini_models(api_key)[:MAX_MODEL_ATTEMPTS]
    last_error = None

    for model in candidates:
        url = f"{GEMINI_BASE}/models/{model}:generateContent?key={api_key}"

        for attempt in range(1, TRIES_PER_MODEL + 1):
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT) as resp:
                    data = json.load(resp)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="ignore")
                log(f"HTTP {e.code} desde Gemini ({model}) -> {detail[:400]}")
                last_error = e
                # 404: modelo listado pero no disponible para esta key.
                # 429: sin cuota en este modelo. 403: sin permiso.
                # Reintentar no ayuda -> probar el siguiente modelo.
                if e.code in (403, 404, 429):
                    break
                # 5xx suele ser transitorio (ej: 503 high demand) -> esperar y
                # reintentar; si se agotan los intentos, siguiente modelo.
                if e.code >= 500:
                    if attempt < TRIES_PER_MODEL:
                        log(
                            f"{model} respondió {e.code}. "
                            f"Esperando {RETRY_DELAY}s antes de reintentar "
                            f"({attempt}/{TRIES_PER_MODEL})."
                        )
                        time.sleep(RETRY_DELAY)
                        continue
                    break
                raise
            except (OSError, http.client.HTTPException) as e:
                # Timeout de lectura, corte de conexión, error de red, etc.
                log(f"Error de red con {model} (intento {attempt}/{TRIES_PER_MODEL}): {e}")
                last_error = e
                if attempt < TRIES_PER_MODEL:
                    log(
                        f"Esperando {RETRY_DELAY}s antes de reintentar "
                        f"({attempt}/{TRIES_PER_MODEL})."
                    )
                    time.sleep(RETRY_DELAY)
                continue  # reintenta; si se agotan los intentos, siguiente modelo

            # Extraer el texto y validar el JSON. Si el modelo no respetó el
            # formato, probamos con el siguiente modelo.
            try:
                parts = data["candidates"][0]["content"]["parts"]
                text = "\n".join(p["text"] for p in parts if p.get("text")).strip()
                encabezado, noticias = parse_digest_json(text, items_by_norm_link)
            except (KeyError, IndexError, TypeError, ValueError) as e:
                log(f"Respuesta inválida de {model}: {e}")
                last_error = e
                break  # probar el siguiente modelo

            log(f"Resumen generado con {model} ({len(noticias)} noticias)")
            return encabezado, noticias

    raise RuntimeError(
        f"Ningún modelo Gemini funcionó (probados: {', '.join(candidates)})."
    ) from last_error


# ---------------------------------------------------------------------------
# Construcción y envío del mensaje
# ---------------------------------------------------------------------------

def digest_file_url(today):
    """Link al digest del día en GitHub (disponible solo corriendo en Actions)."""
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (server and repo):
        return None
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"{server}/{repo}/blob/{branch}/digests/{today}.md"


def build_whatsapp_message(encabezado, noticias, now_local, today):
    header = f"📰 *Resumen tech - {now_local.strftime('%d-%m-%Y')}*"
    footer = None
    url = digest_file_url(today)
    if url:
        footer = f"_Versión extendida: {url}_"

    blocks = [header]
    if encabezado:
        blocks.append(f"_{encabezado}_")
    for n in noticias:
        blocks.append(f"*{n['titulo']}*\n{n['resumen']}\n{n['link']}")
    if footer:
        blocks.append(footer)

    fixed_blocks = 1 + (1 if encabezado else 0) + (1 if footer else 0)
    message = "\n\n".join(blocks)
    while len(message) > MAX_MESSAGE_CHARS and len(blocks) - fixed_blocks > 1:
        idx = -2 if footer else -1  # quitar la última noticia, no el footer
        blocks.pop(idx)
        log("Mensaje muy largo para WhatsApp; quitando la última noticia")
        message = "\n\n".join(blocks)

    return message


def send_whatsapp(text, phone, apikey):
    params = urllib.parse.urlencode({
        "phone": phone,
        "text": text,
        "apikey": apikey,
    })

    url = f"https://api.callmebot.com/whatsapp.php?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"CallMeBot falló con HTTP {e.code}: {body[:300]}"
        ) from e

    cleaned = re.sub(r"\s+", " ", result).strip()
    log(f"CallMeBot respondió: {cleaned[:300]}")

    lowered = cleaned.lower()
    error_markers = (
        "error",
        "invalid",
        "not authorized",
        "not allowed",
        "wrong",
        "missing",
        "phone number",
        "api key",
    )

    if any(marker in lowered for marker in error_markers):
        raise RuntimeError(f"CallMeBot no aceptó el envío: {cleaned[:300]}")

    return cleaned


# ---------------------------------------------------------------------------
# Historial en el repo
# ---------------------------------------------------------------------------

def save_digest_to_history(encabezado, noticias, items, today):
    os.makedirs("digests", exist_ok=True)
    path = os.path.join("digests", f"{today}.md")

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Digest tech - {today}\n\n")
        if encabezado:
            f.write(f"_{encabezado}_\n\n")
        for n in noticias:
            f.write(f"**{n['titulo']}**\n\n{n['resumen']}\n\n{n['link']}\n\n")
        f.write("---\n\n")
        f.write(f"## Versión extendida: los {len(items)} titulares considerados\n\n")
        for item in items:
            f.write(f"- [{item['source']}] {item['title']} — {item['link']}\n")

    log(f"Digest guardado en {path}")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    force = "--force" in sys.argv
    is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

    now_local = now_santiago()
    today = now_local.date().isoformat()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    phone = os.environ.get("CALLMEBOT_PHONE")
    callmebot_key = os.environ.get("CALLMEBOT_API_KEY")

    missing = [name for name, val in [
        ("GEMINI_API_KEY", gemini_key),
        ("CALLMEBOT_PHONE", phone),
        ("CALLMEBOT_API_KEY", callmebot_key),
    ] if not val]
    if missing:
        log(f"Faltan variables de entorno: {', '.join(missing)}")
        sys.exit(1)

    state = load_state()
    prune_state(state, today)

    # Idempotencia: no reenviar si el digest de hoy ya salió
    if not force and today in state["sent"]:
        log(f"El digest de hoy ya fue enviado a las {state['sent'][today]}. "
            "Usa --force para reenviar.")
        sys.exit(0)

    # Control de horario: el cron corre a las 11:00 y 12:00 UTC; solo la
    # ejecución que cae a las 08:00 de Chile envía (así el cambio de hora
    # chileno no requiere editar el workflow).
    if not force and not is_manual and now_local.hour != SEND_HOUR_LOCAL:
        log(f"Hora local en Chile: {now_local.strftime('%H:%M')}. "
            f"El envío corresponde a las {SEND_HOUR_LOCAL:02d}:00. Saliendo sin enviar.")
        sys.exit(0)

    items = fetch_rss_items() + fetch_hn_items()

    recent_topics, recent_links, recent_titles = recent_coverage(state, today)
    items = drop_recent_duplicates(items, recent_links, recent_titles)

    if not items:
        log("No se recolectaron noticias nuevas. Abortando sin enviar mensaje.")
        sys.exit(0)

    items_by_norm_link = {normalize_link(it["link"]): it for it in items}

    encabezado, noticias = summarize_with_gemini(
        items, gemini_key, recent_topics, items_by_norm_link, today
    )

    message = build_whatsapp_message(encabezado, noticias, now_local, today)
    send_whatsapp(message, phone, callmebot_key)

    state["sent"][today] = now_local.isoformat(timespec="seconds")
    state["history"][today] = [
        {"titulo": n["titulo"], "link": n["norm_link"], "source_title": n["source_title"]}
        for n in noticias
    ]

    save_digest_to_history(encabezado, noticias, items, today)
    save_state(state)

    log("Listo.")


if __name__ == "__main__":
    main()
