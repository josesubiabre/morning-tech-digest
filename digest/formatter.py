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


def build_whatsapp_message(encabezado, noticias, now_local):
    """Arma el mensaje de forma determinista: encabezado con emoji y fecha,
    y noticias numeradas con fuente y link.
    Nunca emite separadores de guiones/underscores."""
    header = f"📰 *Resumen tech - {now_local.strftime('%d-%m-%Y')}*"

    encabezado = sanitize_whatsapp_text(encabezado)

    blocks = [header]
    if encabezado:
        blocks.append(f"_{encabezado}_")
    for i, n in enumerate(noticias, 1):
        titulo = sanitize_whatsapp_text(n["titulo"])
        resumen = sanitize_whatsapp_text(n["resumen"])
        blocks.append(f"*{i}. {titulo}*\n{resumen}\n{n['link']}")

    fixed_blocks = 1 + (1 if encabezado else 0)
    message = "\n\n".join(blocks)
    while len(message) > MAX_MESSAGE_CHARS and len(blocks) - fixed_blocks > 1:
        blocks.pop()  # quitar la última noticia
        log("Mensaje muy largo para WhatsApp; quitando la última noticia")
        message = "\n\n".join(blocks)

    # Nunca más de una línea en blanco seguida
    return re.sub(r"\n{3,}", "\n\n", message)


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
