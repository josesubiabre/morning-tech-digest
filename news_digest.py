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
  - Envía cuando la hora de Chile (America/Santiago) cae entre las 08:00 y las
    09:59. El workflow corre a las 11:00 y 12:00 UTC; la ventana tolera los
    atrasos habituales del cron de Actions, y como el estado registra lo ya
    enviado, la ejecución sobrante queda como reintento si la primera falló.
  - Si el digest de hoy ya fue enviado (según digest_state.json), no reenvía.
  - Las ejecuciones manuales (workflow_dispatch) saltan el control de hora.
  - El flag --force salta ambos controles (hora y ya-enviado).
  - El flag --more envía EXTRA_NEWS noticias adicionales sin repetir nada de lo
    ya enviado hoy ni en días anteriores; no marca el digest como enviado. En
    GitHub se dispara con el workflow "Más noticias".

Uso local (para probar):
  export GEMINI_API_KEY=xxx
  export CALLMEBOT_PHONE=xxx
  export CALLMEBOT_API_KEY=xxx
  python news_digest.py --force   # digest normal
  python news_digest.py --more    # noticias adicionales
"""

import os
import sys

from config import SEND_HOUR_LOCAL, SEND_WINDOW_END_LOCAL, EXTRA_NEWS
from utils import log, now_santiago, normalize_link
from collectors import fetch_rss_items, fetch_hn_items
from state import load_state, save_state, prune_state, recent_coverage
from digest import (
    drop_recent_duplicates,
    validate_noticias,
    build_whatsapp_message,
    save_digest_to_history,
)
from summarizers import summarize_with_gemini
from senders import send_whatsapp


def main():
    force = "--force" in sys.argv
    more = "--more" in sys.argv
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

    # Idempotencia: no reenviar si el digest de hoy ya salió. El modo --more
    # envía noticias adicionales, así que este control no le aplica.
    if not force and not more and today in state["sent"]:
        log(f"El digest de hoy ya fue enviado a las {state['sent'][today]}. "
            "Usa --force para reenviar.")
        sys.exit(0)

    # Control de horario: el cron corre a las 11:00 y 12:00 UTC, pero los cron
    # de Actions suelen atrasarse, así que se acepta cualquier ejecución dentro
    # de la ventana local (el control de ya-enviado de arriba evita duplicados
    # y la ejecución sobrante sirve de reintento si la primera falló; el cambio
    # de hora chileno tampoco requiere editar el workflow). --more siempre es
    # a pedido, así que tampoco le aplica.
    if not force and not more and not is_manual and not (
        SEND_HOUR_LOCAL <= now_local.hour <= SEND_WINDOW_END_LOCAL
    ):
        log(f"Hora local en Chile: {now_local.strftime('%H:%M')}. "
            f"El envío corresponde a las {SEND_HOUR_LOCAL:02d}:00-"
            f"{SEND_WINDOW_END_LOCAL:02d}:59. Saliendo sin enviar.")
        sys.exit(0)

    items = fetch_rss_items() + fetch_hn_items()

    # En modo --more la cobertura incluye lo enviado hoy, para no repetir
    # nada del digest de la mañana (ni de un --more anterior).
    recent_topics, recent_links, recent_titles = recent_coverage(
        state, today, include_today=more
    )
    items = drop_recent_duplicates(items, recent_links, recent_titles)

    if not items:
        if more:
            # El botón se apretó a mano: avisar en vez de guardar silencio.
            send_whatsapp("📰 No quedan más noticias relevantes por hoy.",
                          phone, callmebot_key)
            log("Sin items nuevos para --more; avisado por WhatsApp.")
            sys.exit(0)
        log("No se recolectaron noticias nuevas. Abortando sin enviar mensaje.")
        sys.exit(0)

    items_by_norm_link = {normalize_link(it["link"]): it for it in items}

    if more:
        encabezado, noticias = summarize_with_gemini(
            items, gemini_key, recent_topics, items_by_norm_link, today,
            min_news=EXTRA_NEWS, max_news=EXTRA_NEWS, extra=True,
        )
        noticias = validate_noticias(noticias, min_news=EXTRA_NEWS, max_news=EXTRA_NEWS)
    else:
        encabezado, noticias = summarize_with_gemini(
            items, gemini_key, recent_topics, items_by_norm_link, today
        )
        noticias = validate_noticias(noticias)

    title = "Más noticias" if more else "Resumen tech"
    message = build_whatsapp_message(encabezado, noticias, now_local, today, title=title)
    send_whatsapp(message, phone, callmebot_key)

    if not more:
        state["sent"][today] = now_local.isoformat(timespec="seconds")

    # El historial del día acumula TODO lo enviado hoy (digest, extras y
    # reenvíos con --force), deduplicado por link, para que ningún envío
    # futuro repita algo que ya salió.
    entries = [
        {"titulo": n["titulo"], "link": n["norm_link"], "source_title": n["source_title"]}
        for n in noticias
    ]
    known = {e.get("link") for e in state["history"].get(today, [])}
    state["history"][today] = state["history"].get(today, []) + [
        e for e in entries if e["link"] not in known
    ]

    save_digest_to_history(encabezado, noticias, items, today, extra=more)
    save_state(state)

    log("Listo.")


if __name__ == "__main__":
    main()
