# 📰 morning-tech-digest

Resumen diario de noticias tech directo a tu WhatsApp, cada mañana. Recolecta lo más
relevante de medios y comunidades tech, lo filtra y resume con IA, y te lo envía a las
8:00 AM — todo corriendo gratis sobre GitHub Actions, sin ningún servidor.

<!-- Reemplaza esta línea por una captura real del mensaje que te llega:
![Ejemplo del digest en WhatsApp](docs/ejemplo-whatsapp.png)
-->

## ✨ Qué hace

- **Recolecta** noticias desde múltiples fuentes (RSS de medios tech + Hacker News).
- **Filtra y resume** con la API de Google Gemini, quedándose solo con lo importante del día.
- **Envía** el resumen por WhatsApp usando CallMeBot.
- **Guarda** un historial de cada digest en la carpeta `digests/`.
- **Se ejecuta solo** todos los días vía GitHub Actions (cron), sin infraestructura propia.

## 🧱 Arquitectura

El flujo está modularizado por responsabilidad:

```
GitHub Actions (cron 08:00 Chile)
        │
        ▼
   collectors/   →  obtienen las noticias crudas (RSS, Hacker News)
        │
        ▼
   summarizers/  →  filtran y resumen con Gemini
        │
        ▼
   senders/      →  envían el mensaje a WhatsApp (CallMeBot)
        │
        ▼
   digests/      →  historial en Markdown de cada día
```

Módulos de apoyo: `config.py` (configuración central), `state.py` (estado entre corridas),
`utils.py` (utilidades comunes) y `tests/` (pruebas).

## 🛠️ Stack

- **Python 3.11**
- **Google Gemini API** — resumen y filtrado
- **CallMeBot** — envío a WhatsApp (gratis, uso personal)
- **GitHub Actions** — scheduler y ejecución (gratis)
- **feedparser** — lectura de feeds RSS

## 🚀 Setup

### 1. Requisitos de cuentas (gratis)

| Servicio      | Para qué                        | Cómo obtenerlo                                              |
|---------------|---------------------------------|------------------------------------------------------------|
| Gemini API    | Resumir las noticias            | [Google AI Studio](https://aistudio.google.com/apikey)     |
| CallMeBot     | Enviar el WhatsApp              | Agrega **+34 644 71 81 99** y envía `I allow callmebot to send me messages`; te responde con tu API key |

### 2. Configurar los Secrets en GitHub

En el repo: **Settings → Secrets and variables → Actions → New repository secret**.

| Nombre               | Valor                                              |
|----------------------|-----------------------------------------------------|
| `GEMINI_API_KEY`     | Tu API key de Gemini                               |
| `CALLMEBOT_PHONE`    | Tu número en formato internacional sin `+` (ej: `56912345678`) |
| `CALLMEBOT_API_KEY`  | La API key que te dio CallMeBot                    |

### 3. Ejecutar

- **Manual:** pestaña **Actions → Daily Tech News Digest → Run workflow**.
- **Automático:** ya está agendado vía cron para las 08:00 (hora de Chile).

> Los cron de GitHub Actions parten con atrasos impredecibles, así que el workflow
> arranca varias veces antes de las 08:00 de Chile: la primera ejecución que caiga
> suficientemente cerca de las 08:00 prepara el digest y duerme hasta las 08:00:00 en
> punto para enviarlo. Las ejecuciones posteriores quedan de respaldo inmediato si todas
> las tempranas se atrasaron más allá de las 08:00. El horario cubre invierno (UTC-4) y
> verano (UTC-3) chilenos sin necesidad de editarlo.

## ⚙️ Personalización

- **Fuentes:** edita la configuración de feeds en `config.py` / `collectors/`.
- **Criterio y tono del resumen:** ajusta el prompt en `summarizers/`.
- **Horario:** modifica el `cron` en `.github/workflows/`.

## 🧪 Correr localmente

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=xxx
export CALLMEBOT_PHONE=xxx
export CALLMEBOT_API_KEY=xxx
python news_digest.py
```

## 📄 Licencia

MIT — ver [LICENSE](LICENSE).
