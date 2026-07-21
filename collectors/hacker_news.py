"""Recolección de top stories desde la API de Hacker News."""

import time
from concurrent.futures import ThreadPoolExecutor

from config import (
    HN_TOP_STORIES_URL,
    HN_ITEM_URL,
    HN_ITEMS_TO_CHECK,
    HN_MIN_SCORE,
    HN_MAX_WORKERS,
    HOURS_LOOKBACK,
)
from utils import log, http_get_json


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
