"""Filtros de selección: descartar noticias ya enviadas en días anteriores."""

from utils import log, normalize_link, normalize_title


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
