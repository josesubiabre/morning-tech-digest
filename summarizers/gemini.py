"""Resumen del digest con Gemini: ranking de modelos, prompt y validación JSON."""

import re
import json
import time
import http.client
import urllib.request
import urllib.error

from config import (
    GEMINI_BASE,
    PREFERRED_MODEL_HINTS,
    SKIP_MODEL_PREFIXES,
    MAX_MODEL_ATTEMPTS,
    GEMINI_TIMEOUT,
    TRIES_PER_MODEL,
    RETRY_DELAY,
    MIN_NEWS,
    MAX_NEWS,
    MAX_SUMMARY_CHARS,
    USER_AGENT,
)
from utils import log, http_get_json, truncate, normalize_link, normalize_title


def rank_gemini_models(api_key):
    """Consulta los modelos disponibles para esta key y devuelve una lista
    ordenada de candidatos (mejores primero). No garantiza que funcionen:
    Google a veces lista modelos que luego devuelven 404 para keys nuevas,
    así que el que llama debe probar el siguiente si uno falla."""
    data = http_get_json(f"{GEMINI_BASE}/models?key={api_key}")
    models = data.get("models", [])

    # Solo modelos que soportan generateContent
    usable = []
    for m in models:
        methods = m.get("supportedGenerationMethods", [])
        name = m.get("name", "")  # viene como "models/gemini-2.5-flash"
        short = name.split("/")[-1]
        if "generateContent" not in methods:
            continue
        # Evitar modelos especializados (imagen, audio, embeddings, etc.)
        if any(bad in short for bad in ("image", "tts", "audio", "embedding", "vision")):
            continue
        # Excluir generaciones que esta cuenta no puede usar (404/cuota 0)
        if short.startswith(SKIP_MODEL_PREFIXES):
            continue
        usable.append(short)

    if not usable:
        raise RuntimeError("Tu API key no tiene ningún modelo con generateContent disponible.")

    # Ordenar: primero los que calzan con las pistas (sin preview), luego los
    # que calzan pero son preview, y al final el resto.
    ranked = []
    for allow_preview in (False, True):
        for hint in PREFERRED_MODEL_HINTS:
            for short in usable:
                if short in ranked:
                    continue
                if hint in short and (allow_preview or "preview" not in short):
                    ranked.append(short)
    for short in usable:
        if short not in ranked:
            ranked.append(short)

    log(f"Modelos Gemini candidatos (en orden): {', '.join(ranked[:MAX_MODEL_ATTEMPTS])}")
    return ranked


def build_prompt(items, recent_topics, today, min_news=MIN_NEWS, max_news=MAX_NEWS,
                 extra=False):
    lines = []
    for i, item in enumerate(items, 1):
        score = f" (HN score: {item['score']})" if item.get("score") else ""
        excerpt = item.get("excerpt") or "(sin extracto)"
        lines.append(
            f"{i}. [{item['source']}]{score} {item['title']}\n"
            f"   Extracto: {excerpt}\n"
            f"   Link: {item['link']}"
        )
    raw_list = "\n".join(lines)

    covered = "\n".join(f"- {t}" for t in recent_topics) or "- (nada aún)"

    if extra:
        seleccion = f"""1. El lector ya recibió el digest de hoy y pidió más noticias. Elige exactamente \
{max_news} noticias adicionales, las mejores que queden (menos solo si de verdad no hay \
más material relevante)."""
        encabezado_instr = """4. Escribe además un encabezado de UNA frase que abra con "También hoy:" y \
capture estas noticias adicionales."""
        cubiertos_instr = """5. Estos temas ya fueron cubiertos en días anteriores o en el digest de esta \
mañana; NO los repitas salvo que haya una actualización real (y en ese caso menciona que \
es una actualización):"""
    else:
        seleccion = f"""1. Elige entre {min_news} y {max_news} noticias, las más importantes del día, intentando \
esta mezcla (ajústala si algún rubro no tiene nada relevante hoy):
   - 1 o 2 de IA
   - 1 de startups/producto
   - 1 de big tech/mercado
   - 1 de seguridad, regulación o algo inesperado"""
        encabezado_instr = """4. Escribe además un encabezado editorial de UNA frase que capture el día, por ejemplo: \
"Hoy domina: Google acelera X y el mercado reacciona a Y"."""
        cubiertos_instr = """5. Estos temas ya fueron cubiertos en días anteriores; NO los repitas salvo que haya una \
actualización real (y en ese caso menciona que es una actualización):"""

    prompt = f"""Eres el editor de un digest diario de tecnología para un lector en Chile \
interesado en: IA aplicada, startups, producto, infraestructura/cloud, venture capital, \
regulación tecnológica y movimientos de empresas relevantes. Le interesan poco: reviews \
de teléfonos y gadgets menores, gaming y cultura tech.

Abajo tienes la lista cruda de titulares de hoy ({today}), cada uno con su extracto y link.

Tu tarea:
{seleccion}
2. Elimina duplicados o noticias muy similares (quédate con la mejor fuente).
3. Resume cada noticia elegida en 1-2 frases en español (Chile), directo y sin relleno: \
qué pasó y por qué importa. Usa SOLO hechos respaldados por el titular y el extracto; \
no completes con conocimiento externo ni especules.
{encabezado_instr}
{cubiertos_instr}
{covered}

Responde SOLO con un objeto JSON válido, sin texto adicional ni markdown, con esta \
estructura exacta:
{{"encabezado": "...", "noticias": [{{"titulo": "...", "resumen": "...", "link": "..."}}]}}

Reglas del JSON:
- "titulo": corto (máximo 60 caracteres), sin asteriscos ni comillas internas.
- "resumen": 1-2 frases.
- "link": copiado EXACTAMENTE desde la lista de titulares. No lo inventes ni lo modifiques.

Lista cruda de titulares:
{raw_list}
"""
    return prompt


def parse_digest_json(text, items_by_norm_link, max_news=MAX_NEWS):
    """Valida la respuesta de Gemini: JSON con encabezado y 1..max_news noticias
    cuyos links existan en las fuentes recolectadas. Lanza ValueError si no sirve."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", cleaned).strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("la respuesta no es un objeto JSON")

    encabezado = str(data.get("encabezado") or "").strip()

    noticias, seen = [], set()
    for n in data.get("noticias") or []:
        if not isinstance(n, dict):
            continue
        titulo = str(n.get("titulo") or "").strip().strip("*")
        resumen = str(n.get("resumen") or "").strip()
        link = str(n.get("link") or "").strip()
        if not (titulo and resumen and link):
            continue

        norm = normalize_link(link)
        source_item = items_by_norm_link.get(norm)
        if not source_item:
            log(f"Descartada noticia con link que no está en las fuentes: {link}")
            continue
        if norm in seen:
            continue
        seen.add(norm)

        noticias.append({
            "titulo": truncate(titulo, 80),
            "resumen": truncate(resumen, MAX_SUMMARY_CHARS),
            "link": source_item["link"],
            "source": source_item["source"],
            "norm_link": norm,
            "source_title": normalize_title(source_item["title"]),
        })
        if len(noticias) >= max_news:
            break

    if not noticias:
        raise ValueError("el JSON no traía ninguna noticia válida")
    return encabezado, noticias


def summarize_with_gemini(items, api_key, recent_topics, items_by_norm_link, today,
                          min_news=MIN_NEWS, max_news=MAX_NEWS, extra=False):
    prompt = build_prompt(items, recent_topics, today, min_news, max_news, extra)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")

    candidates = rank_gemini_models(api_key)[:MAX_MODEL_ATTEMPTS]
    last_error = None

    for model in candidates:
        url = f"{GEMINI_BASE}/models/{model}:generateContent?key={api_key}"
        json_retry_used = False  # máximo un segundo intento por JSON inválido

        for attempt in range(1, TRIES_PER_MODEL + 1):
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT) as resp:
                    data = json.load(resp)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="ignore")
                log(f"HTTP {e.code} desde Gemini ({model}) -> {detail[:400]}")
                last_error = e
                # 404: modelo listado pero no disponible para esta key.
                # 429: sin cuota en este modelo. 403: sin permiso.
                # Reintentar no ayuda -> probar el siguiente modelo.
                if e.code in (403, 404, 429):
                    break
                # 5xx suele ser transitorio (ej: 503 high demand) -> esperar y
                # reintentar; si se agotan los intentos, siguiente modelo.
                if e.code >= 500:
                    if attempt < TRIES_PER_MODEL:
                        log(
                            f"{model} respondió {e.code}. "
                            f"Esperando {RETRY_DELAY}s antes de reintentar "
                            f"({attempt}/{TRIES_PER_MODEL})."
                        )
                        time.sleep(RETRY_DELAY)
                        continue
                    break
                raise
            except (OSError, http.client.HTTPException) as e:
                # Timeout de lectura, corte de conexión, error de red, etc.
                log(f"Error de red con {model} (intento {attempt}/{TRIES_PER_MODEL}): {e}")
                last_error = e
                if attempt < TRIES_PER_MODEL:
                    log(
                        f"Esperando {RETRY_DELAY}s antes de reintentar "
                        f"({attempt}/{TRIES_PER_MODEL})."
                    )
                    time.sleep(RETRY_DELAY)
                continue  # reintenta; si se agotan los intentos, siguiente modelo

            # Extraer el texto y parsear el JSON. Si el modelo no respetó el
            # formato, se reintenta UNA vez con el mismo modelo y después se
            # pasa al siguiente.
            try:
                parts = data["candidates"][0]["content"]["parts"]
                text = "\n".join(p["text"] for p in parts if p.get("text")).strip()
                encabezado, noticias = parse_digest_json(text, items_by_norm_link, max_news)
            except (KeyError, IndexError, TypeError, ValueError) as e:
                log(f"Respuesta inválida de {model}: {e}")
                last_error = e
                if not json_retry_used and attempt < TRIES_PER_MODEL:
                    json_retry_used = True
                    log(f"Reintentando una vez con {model} por JSON inválido.")
                    continue
                break  # probar el siguiente modelo

            log(f"Resumen generado con {model} ({len(noticias)} noticias)")
            return encabezado, noticias

    raise RuntimeError(
        f"Ningún modelo Gemini funcionó (probados: {', '.join(candidates)})."
    ) from last_error
