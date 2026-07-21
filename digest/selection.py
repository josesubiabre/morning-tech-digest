"""Filtros de selección y validación de las noticias del digest."""

import re
import urllib.parse

from config import MIN_NEWS, MAX_NEWS
from utils import log, normalize_link, normalize_title

# Palabras con las que una oración en español no puede terminar: si el resumen
# acaba en una de estas, quedó cortado a mitad de frase (ej: "...reactores por").
DANGLING_WORDS = {
    "a", "al", "ante", "bajo", "como", "con", "contra", "de", "del", "desde",
    "durante", "e", "en", "entre", "hacia", "hasta", "la", "las", "lo", "los",
    "mediante", "o", "para", "por", "que", "se", "según", "sin", "sobre",
    "su", "sus", "tras", "u", "un", "una", "unas", "unos", "y",
}

SENTENCE_CLOSERS = ".!?…"


def is_incomplete_sentence(text):
    """True si el texto termina abruptamente: sin puntuación de cierre o en
    una palabra con la que ninguna oración puede terminar."""
    t = (text or "").strip()
    if not t:
        return True
    if t[-1] not in SENTENCE_CLOSERS and t[-1] not in "\"»”)":
        return True
    words = re.findall(r"[\wáéíóúñü]+", t.lower())
    return bool(words) and words[-1] in DANGLING_WORDS


def is_valid_url(link):
    p = urllib.parse.urlsplit((link or "").strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


def validate_noticias(noticias):
    """Descarta noticias defectuosas (campos vacíos, URL inválida, resumen
    incompleto). Lanza ValueError si no sobrevive ninguna; avisa si quedan
    menos que el objetivo."""
    valid = []
    for i, n in enumerate(noticias, 1):
        titulo = (n.get("titulo") or "").strip()
        resumen = (n.get("resumen") or "").strip()
        link = (n.get("link") or "").strip()

        problema = None
        if not (titulo and resumen and link):
            problema = "campos obligatorios vacíos"
        elif not is_valid_url(link):
            problema = f"URL inválida: {link[:80]}"
        elif is_incomplete_sentence(resumen):
            problema = f"resumen incompleto (termina en “...{resumen[-25:]}”)"

        if problema:
            log(f"Noticia {i} descartada ({problema}): {titulo[:60] or '(sin título)'}")
            continue
        valid.append(n)

    if not valid:
        raise ValueError("ninguna noticia pasó la validación")
    if len(valid) < MIN_NEWS:
        log(f"Aviso: solo {len(valid)} noticias válidas "
            f"(objetivo: {MIN_NEWS}-{MAX_NEWS}); se envía igual.")
    return valid


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
