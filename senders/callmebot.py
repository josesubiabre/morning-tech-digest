"""Envío por WhatsApp vía CallMeBot, en partes para evitar cortes."""

import re
import time
import urllib.parse
import urllib.request
import urllib.error

from config import CALLMEBOT_CHUNK_CHARS, CALLMEBOT_DELAY_SECONDS, USER_AGENT
from utils import log


def split_whatsapp_message(text, limit=CALLMEBOT_CHUNK_CHARS):
    blocks = text.split("\n\n")
    chunks = []
    current = ""

    for block in blocks:
        candidate = block if not current else f"{current}\n\n{block}"

        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(block) <= limit:
            current = block
        else:
            # Fallback para bloques demasiado largos: cortar por caracteres.
            for i in range(0, len(block), limit):
                chunks.append(block[i:i + limit])
            current = ""

    if current:
        chunks.append(current)

    if len(chunks) <= 1:
        return chunks

    total = len(chunks)
    return [
        f"{chunk}\n\n_Parte {i}/{total}_"
        for i, chunk in enumerate(chunks, start=1)
    ]


def send_callmebot_message(text, phone, apikey):
    params = urllib.parse.urlencode({
        "phone": phone,
        "text": text,
        "apikey": apikey,
    })

    url = f"https://api.callmebot.com/whatsapp.php?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"CallMeBot falló con HTTP {e.code}: {body[:300]}"
        ) from e

    cleaned = re.sub(r"\s+", " ", result).strip()
    log(f"CallMeBot respondió: {cleaned[:300]}")

    lowered = cleaned.lower()

    hard_error_markers = (
        "invalid api key",
        "wrong api key",
        "api key is invalid",
        "phone number is not authorized",
        "not authorized",
        "not allowed",
        "missing parameter",
        "missing phone",
        "missing apikey",
    )

    if any(marker in lowered for marker in hard_error_markers):
        raise RuntimeError(f"CallMeBot no aceptó el envío: {cleaned[:300]}")

    return cleaned


def send_whatsapp(text, phone, apikey):
    chunks = split_whatsapp_message(text)

    log(f"Enviando WhatsApp en {len(chunks)} parte(s)")

    for idx, chunk in enumerate(chunks, start=1):
        log(f"Enviando parte {idx}/{len(chunks)} ({len(chunk)} caracteres)")
        send_callmebot_message(chunk, phone, apikey)

        if idx < len(chunks):
            time.sleep(CALLMEBOT_DELAY_SECONDS)
