"""Recolección de noticias desde feeds RSS."""

import datetime

import feedparser

from config import (
    RSS_FEEDS,
    RSS_TIMEOUT,
    MAX_ITEMS_PER_RSS_FEED,
    HOURS_LOOKBACK,
    EXCERPT_MAX_CHARS,
)
from utils import log, http_get_bytes, strip_html, truncate


def fetch_rss_items():
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=HOURS_LOOKBACK)
    items = []
    per_feed = []

    for source, url in RSS_FEEDS.items():
        # Descarga propia con timeout: feedparser no acepta uno, y un feed
        # colgado dejaba el job pegado sin límite de tiempo.
        try:
            raw = http_get_bytes(url, timeout=RSS_TIMEOUT)
        except Exception as e:
            log(f"Error descargando {source}: {e}")
            continue

        # feedparser no lanza excepciones por contenido malo: deja el
        # problema en bozo_exception y devuelve entries vacío.
        parsed = feedparser.parse(raw)
        if not parsed.entries:
            reason = parsed.get("bozo_exception") or "feed sin entradas"
            log(f"Feed de {source} sin items utilizables: {reason}")
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

        per_feed.append(f"{source} {count}")

    detail = ", ".join(per_feed) or "ninguna fuente respondió"
    log(f"RSS: {len(items)} items recolectados ({detail})")
    return items
