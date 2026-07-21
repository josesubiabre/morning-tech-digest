#!/usr/bin/env python3
"""
Digest diario de noticias tech -> resumen con Gemini -> envío por WhatsApp (CallMeBot).

Variables de entorno requeridas (se configuran como GitHub Secrets):
  GEMINI_API_KEY       -> API key de Google AI Studio
  CALLMEBOT_PHONE       -> tu número de WhatsApp en formato internacional, ej: 56912345678
  CALLMEBOT_API_KEY     -> API key que te dio el bot de CallMeBot por WhatsApp

Uso local (para probar):
  export GEMINI_API_KEY=xxx
  export CALLMEBOT_PHONE=xxx
  export CALLMEBOT_API_KEY=xxx
  python news_digest.py
"""

import os
import sys
import json
import datetime
import http.client
import urllib.parse
import urllib.request
import urllib.error

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

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_ITEMS_TO_CHECK = 40  # cuántos top stories de HN revisar
HN_MIN_SCORE = 80       # solo considerar historias con este puntaje o más

MAX_ITEMS_PER_RSS_FEED = 12
HOURS_LOOKBACK = 30  # ventana de tiempo para considerar una noticia "de hoy"

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Orden de preferencia de modelos. El script arma una lista ordenada de
# candidatos y los va probando: si uno devuelve 404 (Google a veces lista
# modelos que ya no están disponibles para keys nuevas), pasa al siguiente.
PREFERRED_MODEL_HINTS = [
    "gemini-3-flash",
    "flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "flash",
]

MAX_MODEL_ATTEMPTS = 5   # cuántos modelos probar antes de rendirse
GEMINI_TIMEOUT = 180     # segundos de espera por respuesta (modelos con thinking demoran)
TRIES_PER_MODEL = 2      # reintentos por modelo ante timeout o error de red


def log(msg):
    print(f"[news_digest] {msg}", file=sys.stderr)


def http_get_json(url, timeout=30):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        log(f"HTTP {e.code} en GET {url.split('?')[0]} -> {body[:300]}")
        raise


# ---------------------------------------------------------------------------
# Recolección de noticias
# ---------------------------------------------------------------------------

def fetch_rss_items():
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=HOURS_LOOKBACK)
    items = []

    for source, url in RSS_FEEDS.items():
        try:
            parsed = feedparser.parse(url)
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

            items.append({
                "source": source,
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", "").strip(),
                "published": published.isoformat() if published else None,
            })
            count += 1

    log(f"RSS: {len(items)} items recolectados")
    return items


def fetch_hn_items():
    items = []
    try:
        with urllib.request.urlopen(HN_TOP_STORIES_URL, timeout=15) as resp:
            top_ids = json.load(resp)[:HN_ITEMS_TO_CHECK]
    except Exception as e:
        log(f"Error obteniendo top stories de HN: {e}")
        return items

    for story_id in top_ids:
        try:
            with urllib.request.urlopen(HN_ITEM_URL.format(story_id), timeout=15) as resp:
                item = json.load(resp)
        except Exception as e:
            log(f"Error obteniendo item HN {story_id}: {e}")
            continue

        if not item:
            continue
        if item.get("score", 0) < HN_MIN_SCORE:
            continue

        link = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        items.append({
            "source": "Hacker News",
            "title": item.get("title", "").strip(),
            "link": link,
            "published": None,
            "score": item.get("score"),
        })

    log(f"Hacker News: {len(items)} items recolectados (score >= {HN_MIN_SCORE})")
    return items


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

def build_prompt(items):
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. [{item['source']}] {item['title']} -- {item['link']}")
    raw_list = "\n".join(lines)

    today = datetime.date.today().isoformat()

    prompt = f"""Eres un editor de noticias de tecnología. A continuación te doy una lista cruda \
de titulares recolectados hoy ({today}) desde RSS de medios tech y Hacker News.

Tu tarea:
1. Filtra y elige SOLO las 6 a 10 noticias más importantes/relevantes del día para alguien \
que sigue la industria tech (IA, startups, big tech, productos, seguridad, mercado). Ignora \
notas de opinión genéricas, listículos, reviews de productos menores o contenido irrelevante.
2. Elimina duplicados o noticias muy similares entre sí (quédate con la mejor fuente).
3. Para cada noticia elegida, escribe un resumen de 1-2 frases en español (Chile), directo y \
sin relleno, explicando qué pasó y por qué importa.
4. Devuelve el resultado en texto plano listo para enviar por WhatsApp, con este formato exacto \
por cada noticia:

*<título corto>*
<resumen de 1-2 frases>
<link>

5. Sepára cada noticia con una línea en blanco.
6. No agregues introducción, encabezado ni conclusión. Solo la lista de noticias.
7. No inventes noticias que no estén en la lista.

Lista cruda de titulares:
{raw_list}
"""
    return prompt


def summarize_with_gemini(items, api_key):
    prompt = build_prompt(items)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3},
    }).encode("utf-8")

    candidates = rank_gemini_models(api_key)[:MAX_MODEL_ATTEMPTS]
    last_error = None

    for model in candidates:
        url = f"{GEMINI_BASE}/models/{model}:generateContent?key={api_key}"

        for attempt in range(1, TRIES_PER_MODEL + 1):
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
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
                # 5xx suele ser transitorio -> reintentar este modelo.
                if e.code >= 500 and attempt < TRIES_PER_MODEL:
                    continue
                raise
            except (OSError, http.client.HTTPException) as e:
                # Timeout de lectura, corte de conexión, error de red, etc.
                log(f"Error de red con {model} (intento {attempt}/{TRIES_PER_MODEL}): {e}")
                last_error = e
                continue  # reintenta; si se agotan los intentos, siguiente modelo

            # Extraer el texto de forma tolerante (algunos modelos devuelven
            # varias partes, o respuestas vacías por filtros de seguridad).
            try:
                parts = data["candidates"][0]["content"]["parts"]
                text = "\n".join(p["text"] for p in parts if p.get("text")).strip()
            except (KeyError, IndexError, TypeError) as e:
                log(f"Respuesta inesperada de {model}: {json.dumps(data)[:400]}")
                last_error = e
                break  # probar el siguiente modelo

            if text:
                log(f"Resumen generado con {model}")
                return text

            log(f"{model} devolvió una respuesta vacía, probando el siguiente modelo")
            break

    raise RuntimeError(
        f"Ningún modelo Gemini funcionó (probados: {', '.join(candidates)})."
    ) from last_error


# ---------------------------------------------------------------------------
# Envío por WhatsApp (CallMeBot)
# ---------------------------------------------------------------------------

def send_whatsapp(text, phone, apikey):
    encoded_text = urllib.parse.quote(text)
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={phone}&text={encoded_text}&apikey={apikey}"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        result = resp.read().decode("utf-8", errors="ignore")
    log(f"CallMeBot respondió: {result[:200]}")


# ---------------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------------

def save_digest_to_history(digest_text, items):
    os.makedirs("digests", exist_ok=True)
    today = datetime.date.today().isoformat()
    path = os.path.join("digests", f"{today}.md")

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Digest tech - {today}\n\n")
        f.write(digest_text)
        f.write("\n\n---\n\n")
        f.write(f"_Generado a partir de {len(items)} noticias crudas recolectadas._\n")

    log(f"Digest guardado en {path}")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
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

    items = fetch_rss_items() + fetch_hn_items()

    if not items:
        log("No se recolectaron noticias. Abortando sin enviar mensaje.")
        sys.exit(0)

    digest_text = summarize_with_gemini(items, gemini_key)

    today_label = datetime.date.today().strftime("%d-%m-%Y")
    whatsapp_message = f"📰 *Resumen tech - {today_label}*\n\n{digest_text}"

    send_whatsapp(whatsapp_message, phone, callmebot_key)
    save_digest_to_history(digest_text, items)

    log("Listo.")


if __name__ == "__main__":
    main()