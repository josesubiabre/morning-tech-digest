"""Recolectores de noticias: feeds RSS y Hacker News."""

from collectors.rss import fetch_rss_items
from collectors.hacker_news import fetch_hn_items

__all__ = ["fetch_rss_items", "fetch_hn_items"]
