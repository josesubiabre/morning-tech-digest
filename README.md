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
Esto lo ejecuta al toque, sin esperar al cron ni al control de horario.
Si el digest de hoy ya se envió, no lo reenvía — para forzar un reenvío
marca el checkbox **force** al lanzar el workflow.

### 6. Listo

El workflow corre todos los días a las 11:00 y 12:00 UTC, y el script decide
solo (usando la zona horaria `America/Santiago`) cuál de las dos ejecuciones
corresponde a las 08:00 de Chile — la otra sale sin enviar. No hay que tocar
nada cuando Chile entra o sale del horario de verano.

## Cómo funciona el digest

- Se recolectan titulares **con su extracto RSS**, y Gemini resume solo hechos
  respaldados por el titular y el extracto (sin completar con conocimiento externo).
- Se eligen **4 a 5 noticias** con esta mezcla aproximada: 1-2 de IA, 1 de
  startups/producto, 1 de big tech/mercado y 1 de seguridad/regulación o algo
  inesperado. Prioriza IA aplicada, startups, infraestructura/cloud, venture
  capital y regulación; baja el peso de reviews de gadgets, gaming y cultura tech.
- Gemini responde **JSON estructurado** y el script valida en Python: cantidad,
  largo máximo y que cada link exista realmente en las fuentes recolectadas.
- El mensaje abre con una frase editorial ("Hoy domina: ...") y cierra con un
  link a la versión extendida (todos los titulares del día) en `digests/`.
- **No se repiten noticias entre días**: el script guarda lo enviado en los
  últimos 7 días (`digest_state.json`) y descarta o penaliza temas ya cubiertos,
  salvo que haya una actualización real.

## Ajustar el contenido

Todo el criterio de filtrado y el tono del resumen está en la función `build_prompt()`
dentro de `news_digest.py`. Puedes editar ese texto para pedir más o menos noticias,
otro tono, otros temas prioritarios, etc. Las cantidades y largos están en las
constantes `MIN_NEWS`, `MAX_NEWS`, `MAX_SUMMARY_CHARS` y `MAX_MESSAGE_CHARS`.

Para agregar o quitar fuentes RSS, edita el diccionario `RSS_FEEDS` al inicio del archivo.

## Historial y estado

Cada digest queda guardado en `digests/YYYY-MM-DD.md` dentro del repo (el workflow
lo commitea al terminar) — incluye las noticias enviadas y la lista completa de
titulares considerados. Además, `digest_state.json` registra qué días ya se
enviaron (para no duplicar envíos si el workflow corre dos veces) y qué noticias
salieron en los últimos 7 días (para no repetirlas).

## Probar en tu computador (opcional)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=xxx
export CALLMEBOT_PHONE=xxx
export CALLMEBOT_API_KEY=xxx
python news_digest.py --force   # --force salta el control de hora y de ya-enviado
```
