"""Construcción del mensaje de WhatsApp y del archivo de historial en digests/."""

import os
import re

from config import MAX_MESSAGE_CHARS
from utils import log


def sanitize_whatsapp_text(text):
    """Limpia texto que va dentro del mensaje (no links): elimina separadores
    tipo "__________" o "----" que rompen el formato en WhatsApp, y colapsa
    espacios repetidos."""
    t = re.sub(r"_{3,}", " ", text or "")
    t = re.sub(r"-{4,}", " ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def digest_file_url(today):
    """Link al digest del día en GitHub (disponible solo corriendo en Actions)."""
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (server and repo):
        return None
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"{server}/{repo}/blob/{branch}/digests/{today}.md"


def build_whatsapp_message(encabezado, noticias, now_local, today, title="Resumen tech"):
    """Arma el mensaje de forma determinista: encabezado con emoji y fecha,
    noticias numeradas con fuente y link, y footer con la versión extendida.
    Nunca emite separadores de guiones/underscores."""
    header = f"📰 *{title} - {now_local.strftime('%d-%m-%Y')}*"
    footer = None
    url = digest_file_url(today)
    if url:
        footer = f"_Versión extendida: {url}_"

    encabezado = sanitize_whatsapp_text(encabezado)

    blocks = [header]
    if encabezado:
        blocks.append(f"_{encabezado}_")
    for i, n in enumerate(noticias, 1):
        titulo = sanitize_whatsapp_text(n["titulo"])
        resumen = sanitize_whatsapp_text(n["resumen"])
        blocks.append(f"*{i}. {titulo}*\n{resumen}\n{n['link']}")
    if footer:
        blocks.append(footer)

    fixed_blocks = 1 + (1 if encabezado else 0) + (1 if footer else 0)
    message = "\n\n".join(blocks)
    while len(message) > MAX_MESSAGE_CHARS and len(blocks) - fixed_blocks > 1:
        idx = -2 if footer else -1  # quitar la última noticia, no el footer
        blocks.pop(idx)
        log("Mensaje muy largo para WhatsApp; quitando la última noticia")
        message = "\n\n".join(blocks)

    # Nunca más de una línea en blanco seguida
    return re.sub(r"\n{3,}", "\n\n", message)


def save_digest_to_history(encabezado, noticias, items, today, extra=False):
    os.makedirs("digests", exist_ok=True)
    path = os.path.join("digests", f"{today}.md")

    # Las noticias extra se agregan al archivo del día sin repetir el listado
    # de titulares, que ya quedó escrito con el digest de la mañana.
    if extra and os.path.exists(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n## Más noticias (pedidas durante el día)\n\n")
            _write_noticias(f, encabezado, noticias)
        log(f"Noticias extra agregadas a {path}")
        return path

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Digest tech - {today}\n\n")
        _write_noticias(f, encabezado, noticias)
        f.write("---\n\n")
        f.write(f"## Versión extendida: los {len(items)} titulares considerados\n\n")
        for item in items:
            f.write(f"- [{item['source']}] {item['title']} — {item['link']}\n")

    log(f"Digest guardado en {path}")
    return path


def _write_noticias(f, encabezado, noticias):
    if encabezado:
        f.write(f"_{encabezado}_\n\n")
    for n in noticias:
        f.write(f"**{n['titulo']}**\n\n{n['resumen']}\n\n{n['link']}\n\n")
