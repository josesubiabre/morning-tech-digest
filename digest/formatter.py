"""Construcción del mensaje de WhatsApp y del archivo de historial en digests/."""

import os

from config import MAX_MESSAGE_CHARS
from utils import log


def digest_file_url(today):
    """Link al digest del día en GitHub (disponible solo corriendo en Actions)."""
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (server and repo):
        return None
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"{server}/{repo}/blob/{branch}/digests/{today}.md"


def build_whatsapp_message(encabezado, noticias, now_local, today):
    header = f"📰 *Resumen tech - {now_local.strftime('%d-%m-%Y')}*"
    footer = None
    url = digest_file_url(today)
    if url:
        footer = f"_Versión extendida: {url}_"

    blocks = [header]
    if encabezado:
        blocks.append(f"_{encabezado}_")
    for n in noticias:
        blocks.append(f"*{n['titulo']}*\n{n['resumen']}\n{n['link']}")
    if footer:
        blocks.append(footer)

    fixed_blocks = 1 + (1 if encabezado else 0) + (1 if footer else 0)
    message = "\n\n".join(blocks)
    while len(message) > MAX_MESSAGE_CHARS and len(blocks) - fixed_blocks > 1:
        idx = -2 if footer else -1  # quitar la última noticia, no el footer
        blocks.pop(idx)
        log("Mensaje muy largo para WhatsApp; quitando la última noticia")
        message = "\n\n".join(blocks)

    return message


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
