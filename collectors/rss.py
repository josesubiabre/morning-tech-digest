"""Recolección de noticias desde feeds RSS."""

import datetime

import feedparser

from config import (
    RSS_FEEDS,
    USER_AGENT,
    MAX_ITEMS_PER_RSS_FEED,
    HOURS_LOOKBACK,
    EXCERPT_MAX_CHARS,
)
from utils import log, strip_html, truncate


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
