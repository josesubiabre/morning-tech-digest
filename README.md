# whatsapp_news — Digest diario de noticias tech por WhatsApp

Todos los días a las 8:00 (hora de Chile), este proyecto:

1. Recolecta noticias de TechCrunch, The Verge, Ars Technica, Wired (RSS) y Hacker News (API).
2. Le pide a Gemini que filtre y resuma lo más relevante del día.
3. Te envía el resumen por WhatsApp usando CallMeBot.
4. Guarda una copia del digest en la carpeta `digests/` como historial.

Todo corre gratis sobre GitHub Actions — no necesitas ningún servidor prendido.

## Setup (una sola vez)

### 1. Activar CallMeBot

1. Agrega a tus contactos de WhatsApp el número: **+34 644 71 81 99**
2. Envíale el mensaje exacto: `I allow callmebot to send me messages`
3. En un par de minutos te va a responder con tu **API key**. Guárdala.
4. Anota también tu propio número de WhatsApp en formato internacional sin el `+`
   (ejemplo: si tu número es +56 9 1234 5678, es `56912345678`).

### 2. Conseguir API key de Gemini

1. Ve a [Google AI Studio](https://aistudio.google.com/apikey)
2. Inicia sesión con tu cuenta de Google.
3. Genera una API key (gratis, sin tarjeta de crédito).

### 3. Subir este proyecto a tu repo de GitHub

Ya creaste el repo `whatsapp_news`. Ahora, desde tu computador, en una carpeta vacía:

```bash
git clone https://github.com/josesubiabre/whatsapp_news.git
cd whatsapp_news
# copia aquí todos los archivos de este proyecto (news_digest.py, requirements.txt,
# README.md, y la carpeta .github/)
git add .
git commit -m "Setup inicial del digest diario"
git push
```

Si prefieres no usar la terminal: en la página de tu repo puedes usar el link
**"uploading an existing file"** y arrastrar los archivos directamente desde el navegador
(en ese caso crea manualmente la carpeta `.github/workflows/` al subir `daily-digest.yml`).

### 4. Configurar los Secrets en GitHub

En tu repo: **Settings → Secrets and variables → Actions → New repository secret**.
Crea estos tres secrets:

| Nombre               | Valor                                              |
|----------------------|-----------------------------------------------------|
| `GEMINI_API_KEY`     | La API key de Gemini del paso 2                     |
| `CALLMEBOT_PHONE`    | Tu número, ej: `56912345678`                        |
| `CALLMEBOT_API_KEY`   | La API key que te dio CallMeBot por WhatsApp        |

### 5. Probar manualmente

En tu repo: pestaña **Actions → Daily Tech News Digest → Run workflow**.
Esto lo ejecuta al toque, sin esperar al cron. Si todo está bien configurado,
en menos de un minuto te debería llegar el WhatsApp.

### 6. Listo

El cron ya está configurado para correr todos los días a las 12:00 UTC (8:00 Chile,
horario estándar). Si Chile entra en horario de verano (UTC-3) y quieres que siga
llegando siempre a las 8:00 en punto, cambia el cron en
`.github/workflows/daily-digest.yml` de `0 12 * * *` a `0 11 * * *`.

## Ajustar el contenido

Todo el criterio de filtrado y el tono del resumen está en la función `build_prompt()`
dentro de `news_digest.py`. Puedes editar ese texto para pedir más o menos noticias,
otro tono, otros temas prioritarios, etc.

Para agregar o quitar fuentes RSS, edita el diccionario `RSS_FEEDS` al inicio del archivo.

## Historial

Cada digest queda guardado en `digests/YYYY-MM-DD.md` dentro del repo — puedes
revisar cualquier día anterior ahí. Además, el mensaje completo queda en tu
chat de WhatsApp con CallMeBot.

## Probar en tu computador (opcional)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=xxx
export CALLMEBOT_PHONE=xxx
export CALLMEBOT_API_KEY=xxx
python news_digest.py
```
