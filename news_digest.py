#!/usr/bin/env python3
"""
Digest diario de noticias tech -> resumen con Gemini -> envío por WhatsApp (CallMeBot).

Entrada principal: coordina recolección (collectors/), resumen (summarizers/),
formato (digest/), estado (state.py) y envío (senders/). La configuración vive
en config.py.

Variables de entorno requeridas (se configuran como GitHub Secrets):
  GEMINI_API_KEY        -> API key de Google AI Studio
  CALLMEBOT_PHONE       -> tu número de WhatsApp en formato internacional, ej: 56912345678
  CALLMEBOT_API_KEY     -> API key que te dio el bot de CallMeBot por WhatsApp

Comportamiento:
  - Solo envía a las 08:00 hora de Chile (America/Santiago). El workflow corre a las
    11:00 y 12:00 UTC; la ejecución que no calza con las 08:00 locales sale sin enviar.
  - Si el digest de hoy ya fue enviado (según digest_state.json), no reenvía.
  - Las ejecuciones manuales (workflow_dispatch) saltan el control de hora.
  - El flag --force salta ambos controles (hora y ya-enviado).

Uso local (para probar):
  export GEMINI_API_KEY=xxx
  export CALLMEBOT_PHONE=xxx
  export CALLMEBOT_API_KEY=xxx
  python news_digest.py --force
"""

import os
import sys

from config import SEND_HOUR_LOCAL
from utils import log, now_santiago, normalize_link
from collectors import fetch_rss_items, fetch_hn_items
from state import load_state, save_state, prune_state, recent_coverage
from digest import drop_recent_duplicates, build_whatsapp_message, save_digest_to_history
from summarizers import summarize_with_gemini
from senders import send_whatsapp


def main():
    force = "--force" in sys.argv
    is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

    now_local = now_santiago()
    today = now_local.date().isoformat()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    phone = os.environ.get("CALLMEBOT_PHONE")
    callmebot_key = os.environ.get("CALLMEBOT_API_KEY")

    missing = [name for name, val in [
        ("GEMINI_API_KEY", gemini_key),
        ("CALLMEBOT_PHONE", phone),
        ("CALLMEBOT_API_KEY", callmebot_key),
    ] if not val]
    if missing:
        log(f"Faltan variables de entorno: {', '.join(missing)}")
        sys.exit(1)

    state = load_state()
    prune_state(state, today)

    # Idempotencia: no reenviar si el digest de hoy ya salió
    if not force and today in state["sent"]:
        log(f"El digest de hoy ya fue enviado a las {state['sent'][today]}. "
            "Usa --force para reenviar.")
        sys.exit(0)

    # Control de horario: el cron corre a las 11:00 y 12:00 UTC; solo la
    # ejecución que cae a las 08:00 de Chile envía (así el cambio de hora
    # chileno no requiere editar el workflow).
    if not force and not is_manual and now_local.hour != SEND_HOUR_LOCAL:
        log(f"Hora local en Chile: {now_local.strftime('%H:%M')}. "
            f"El envío corresponde a las {SEND_HOUR_LOCAL:02d}:00. Saliendo sin enviar.")
        sys.exit(0)

    items = fetch_rss_items() + fetch_hn_items()

    recent_topics, recent_links, recent_titles = recent_coverage(state, today)
    items = drop_recent_duplicates(items, recent_links, recent_titles)

    if not items:
        log("No se recolectaron noticias nuevas. Abortando sin enviar mensaje.")
        sys.exit(0)

    items_by_norm_link = {normalize_link(it["link"]): it for it in items}

    encabezado, noticias = summarize_with_gemini(
        items, gemini_key, recent_topics, items_by_norm_link, today
    )

    message = build_whatsapp_message(encabezado, noticias, now_local, today)
    send_whatsapp(message, phone, callmebot_key)

    state["sent"][today] = now_local.isoformat(timespec="seconds")
    state["history"][today] = [
        {"titulo": n["titulo"], "link": n["norm_link"], "source_title": n["source_title"]}
        for n in noticias
    ]

    save_digest_to_history(encabezado, noticias, items, today)
    save_state(state)

    log("Listo.")


if __name__ == "__main__":
    main()
