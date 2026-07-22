# 📰 morning-tech-digest

A daily tech news digest delivered straight to your WhatsApp, every morning. It gathers the
most relevant stories from tech media and communities, filters and summarizes them with AI,
and sends them to you at 8:00 AM — running entirely free on GitHub Actions, with no server.

![Digest example on WhatsApp](docs/whatsapp-example.png)

## ✨ What it does

- **Collects** news from multiple sources (tech RSS feeds + Hacker News).
- **Filters and summarizes** with the Google Gemini API, keeping only what matters that day.
- **Sends** the summary to WhatsApp via CallMeBot.
- **Stores** a history of every digest in the `digests/` folder.
- **Runs itself** every day via GitHub Actions (cron), with zero infrastructure.

## 🧱 Architecture

The pipeline is split by responsibility:

```
GitHub Actions (cron 08:00 Chile time)
        │
        ▼
   collectors/   →  fetch raw news (RSS, Hacker News)
        │
        ▼
   summarizers/  →  filter and summarize with Gemini
        │
        ▼
   senders/      →  deliver the message to WhatsApp (CallMeBot)
        │
        ▼
   digests/      →  Markdown history of each day
```

Supporting modules: `config.py` (central configuration), `state.py` (state across runs),
`utils.py` (shared helpers), and `tests/` (tests).

## 🛠️ Stack

- **Python 3.11**
- **Google Gemini API** — summarization and filtering
- **CallMeBot** — WhatsApp delivery (free, personal use)
- **GitHub Actions** — scheduler and execution (free)
- **feedparser** — RSS feed parsing

## 🚀 Setup

### 1. Accounts you'll need (all free)

| Service    | Purpose                    | How to get it                                                                                  |
|------------|----------------------------|------------------------------------------------------------------------------------------------|
| Gemini API | Summarize the news         | [Google AI Studio](https://aistudio.google.com/apikey)                                         |
| CallMeBot  | Send the WhatsApp message  | Add **+34 644 71 81 99** and send `I allow callmebot to send me messages`; it replies with your API key |

### 2. Configure GitHub Secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**.

| Name                 | Value                                                          |
|----------------------|----------------------------------------------------------------|
| `GEMINI_API_KEY`     | Your Gemini API key                                            |
| `CALLMEBOT_PHONE`    | Your number in international format, no `+` (e.g. `56912345678`) |
| `CALLMEBOT_API_KEY`  | The API key CallMeBot gave you                                 |

### 3. Run it

- **Manually:** the **Actions → Daily Tech News Digest → Run workflow** tab.
- **Automatically:** it's already scheduled via cron for 08:00 (Chile time).

> The cron runs at 12:00 UTC (08:00 in Chile standard time). If Chile switches to daylight
> saving time (UTC-3), change the cron to `0 11 * * *` to keep the same local hour.

## ⚙️ Customization

- **Sources:** edit the feed configuration in `config.py` / `collectors/`.
- **Summary criteria and tone:** tweak the prompt in `summarizers/`.
- **Schedule:** change the `cron` in `.github/workflows/`.

## 🧪 Run locally

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=xxx
export CALLMEBOT_PHONE=xxx
export CALLMEBOT_API_KEY=xxx
python news_digest.py
```

## 📄 License

MIT — see [LICENSE](LICENSE).
