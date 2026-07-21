"""Estado persistente del digest: envíos previos e historial para no repetir.

Vive en digest_state.json, que el workflow commitea de vuelta al repo para
que persista entre ejecuciones de GitHub Actions.
"""

import os
import json
import datetime

from config import STATE_PATH, HISTORY_DAYS, SENT_KEEP_DAYS
from utils import log


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                state = json.load(f)
            if isinstance(state, dict):
                state.setdefault("sent", {})
                state.setdefault("history", {})
                return state
        except (json.JSONDecodeError, OSError) as e:
            log(f"No se pudo leer {STATE_PATH} ({e}); partiendo con estado vacío")
    return {"sent": {}, "history": {}}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    log(f"Estado guardado en {STATE_PATH}")


def prune_state(state, today):
    t = datetime.date.fromisoformat(today)

    def keep(section, max_days):
        pruned = {}
        for date_str, value in section.items():
            try:
                d = datetime.date.fromisoformat(date_str)
            except ValueError:
                continue
            if (t - d).days <= max_days:
                pruned[date_str] = value
        return pruned

    state["sent"] = keep(state["sent"], SENT_KEEP_DAYS)
    state["history"] = keep(state["history"], HISTORY_DAYS)


def recent_coverage(state, today):
    """Devuelve (temas para el prompt, links normalizados, títulos de fuente
    normalizados) de lo enviado en los últimos HISTORY_DAYS días (sin incluir hoy,
    para que un reenvío con --force no se filtre a sí mismo)."""
    topics, links, source_titles = [], set(), set()
    for date_str in sorted(state["history"], reverse=True):
        if date_str == today:
            continue
        for entry in state["history"][date_str]:
            if entry.get("titulo"):
                topics.append(entry["titulo"])
            if entry.get("link"):
                links.add(entry["link"])
            if entry.get("source_title"):
                source_titles.add(entry["source_title"])
    return topics[:40], links, source_titles
