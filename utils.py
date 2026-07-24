"""Funciones pequeñas compartidas por todos los módulos."""

import re
import sys
import json
import html
import datetime
import urllib.parse
import urllib.request
import urllib.error
from zoneinfo import ZoneInfo

from config import TIMEZONE, USER_AGENT


def log(msg):
    print(f"[news_digest] {msg}", file=sys.stderr)


def now_santiago():
    return datetime.datetime.now(ZoneInfo(TIMEZONE))


def http_get_bytes(url, timeout=30, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        log(f"HTTP {e.code} en GET {url.split('?')[0]} -> {body[:300]}")
        raise


def http_get_json(url, timeout=30, headers=None):
    return json.loads(http_get_bytes(url, timeout=timeout, headers=headers))


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
