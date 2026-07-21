"""Envío por WhatsApp vía CallMeBot, en partes cortas para evitar que los mutile.

CallMeBot corta los mensajes que superan ~700 caracteres: trunca a mitad de
palabra, descarta texto e inserta su propio separador "__________". Por eso
cada parte enviada debe quedar bajo CALLMEBOT_CHUNK_CHARS, y
send_callmebot_message rechaza cualquier texto que supere CALLMEBOT_MAX_CHARS
como defensa final.
"""

import re
import time
import urllib.parse
import urllib.request
import urllib.error

from config import (
    CALLMEBOT_CHUNK_CHARS,
    CALLMEBOT_MAX_CHARS,
    CALLMEBOT_DELAY_SECONDS,
    USER_AGENT,
)
from utils import log


def split_whatsapp_message(text, limit=CALLMEBOT_CHUNK_CHARS):
    """Divide el mensaje en partes de a lo más `limit` caracteres, respetando
    los bloques separados por línea en blanco (sin partir noticias)."""
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

    return chunks


def _mask_secrets(text, phone, apikey):
    """Evita que el número o la API key terminen en los logs o excepciones."""
    masked = text
    for secret in (str(apikey or ""), str(phone or "")):
        if secret:
            masked = masked.replace(secret, "***")
    return masked


def send_callmebot_message(text, phone, apikey):
    if len(text) > CALLMEBOT_MAX_CHARS:
        raise RuntimeError(
            f"Parte de {len(text)} caracteres supera el máximo de "
            f"{CALLMEBOT_MAX_CHARS}; no se envía para evitar que llegue mutilada."
        )

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
        body = _mask_secrets(e.read().decode("utf-8", errors="ignore"), phone, apikey)
        raise RuntimeError(
            f"CallMeBot falló con HTTP {e.code}: {body[:300]}"
        ) from e

    cleaned = re.sub(r"\s+", " ", result).strip()
    safe = _mask_secrets(cleaned, phone, apikey)
    log(f"CallMeBot respondió: {safe[:300]}")

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
        raise RuntimeError(f"CallMeBot no aceptó el envío: {safe[:300]}")

    return cleaned


def send_whatsapp(text, phone, apikey):
    chunks = split_whatsapp_message(text)

    log(f"Enviando WhatsApp en {len(chunks)} parte(s)")

    for idx, chunk in enumerate(chunks, start=1):
        log(f"Enviando parte {idx}/{len(chunks)} ({len(chunk)} caracteres)")
        send_callmebot_message(chunk, phone, apikey)

        if idx < len(chunks):
            time.sleep(CALLMEBOT_DELAY_SECONDS)
