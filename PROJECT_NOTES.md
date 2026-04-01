# DziemianMCAgent - Project Notes & Session Recap

## 📌 What This Project Is

AI-powered trend research agent for YouTube channel **"Dziemian - Muzyczne Commentary"**.
Runs every 2 days, scrapes Polish internet, analyzes with Claude AI, sends results to Notion + Telegram.

---

## 🏗️ How It Was Built

Project created from scratch on **2026-04-01** in `/Users/maciejdziemianczuk/DziemianMCAgent`.
GitHub repo: https://github.com/dZIEMIAAAN/DziemianMCAgent

### Tech Stack
- **Language**: Python 3.10+
- **AI**: Claude 3.5 Sonnet (Anthropic SDK)
- **Deployment**: Railway (cron job every 2 days at 8:00)
- **Scraping**: yt-dlp, pytrends, BeautifulSoup, feedparser, Apify

---

## 🔑 API Keys Needed

| Key | Where to Get | Cost |
|-----|-------------|------|
| `ANTHROPIC_API_KEY` | console.anthropic.com | ~$0.03/run |
| `NOTION_API_KEY` | notion.so/my-integrations | Free |
| `NOTION_DATABASE_ID` | From Notion DB URL | Free |
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram | Free |
| `TELEGRAM_CHAT_ID` | @userinfobot on Telegram | Free |
| `APIFY_API_TOKEN` | console.apify.com/account/integrations | Optional, $5/mo free credit |

**Notes:**
- YouTube (yt-dlp) — NO API KEY needed, bypasses YouTube API limits
- Google Trends (pytrends) — NO API KEY needed, uses unofficial API
- Wykop — NO API KEY needed, pure RSS + scraping
- Apify — ONE general token covers all actors (Twitter + TikTok)

---

## 💰 Cost Per Run (excluding Railway)

- **Claude API**: ~$0.02–0.05 per run
- **Everything else**: Free
- **Monthly total (15 runs)**: ~$0.50

---

## 📊 Notion Database Setup

Create a database with these **exact column names** (case-sensitive):

| Column | Type | Options |
|--------|------|---------|
| **Temat** | Title | — |
| **Link** | URL | — |
| **Status** | Select | `Do przejrzenia`, `W produkcji`, `Gotowe` |
| **Typ** | Select | `🔥 TOTALNY OUTLIER`, `💎 Duży potencjał`, `📈 Trend` |
| **VPH** | Number | — |
| **Kąt Muzyczny** | Text | — |
| **Złote Cytaty** | Text | — |
| **Uzasadnienie** | Text | — |
| **Cross-Platform Score** | Number | 0–100 |

After creating the database:
1. Go to the database settings
2. Add Notion integration (your `NOTION_API_KEY` integration)
3. Copy DB ID from URL: `notion.so/workspace/DATABASE_ID?v=...`

---

## 🚂 Railway Deployment

This is a **separate Railway project** from any existing Docker servers.
Each Railway project is fully isolated with its own env vars and billing.

**Steps:**
1. Go to railway.app/dashboard
2. Click **"New Project"** (not "add service")
3. Deploy from GitHub → select `DziemianMCAgent`
4. Add all env vars from `.env.example`
5. Railway auto-detects `railway.json` → sets up cron

**Schedule**: `0 8 */2 * *` = every 2 days at 8:00 AM

---

## 🗂️ Project Structure

```
src/dziemian_mc_agent/
├── config.py               # All env vars (Pydantic Settings)
├── main.py                 # Orchestrator - run with: python -m dziemian_mc_agent
├── scrapers/
│   ├── youtube.py          # yt-dlp: channels + keyword search, VPH calc, transcripts
│   ├── wykop.py            # RSS + BeautifulSoup scraping
│   ├── google_trends.py    # pytrends - Poland trending + related queries
│   └── apify.py            # X/TikTok via Apify (disabled if no token)
├── ai/
│   ├── prompts.py          # System prompt for Claude (Polish, with Dziemian context)
│   └── analyzer.py         # Sends scraped data to Claude, parses JSON response
├── notion/
│   └── client.py           # Creates pages in Notion DB
├── telegram/
│   └── bot.py              # Sends Markdown report to Telegram
└── models/
    └── schemas.py          # Pydantic models: VideoData, TrendData, AnalyzedTopic, etc.
```

---

## 🧪 How to Run Locally

```bash
cd /Users/maciejdziemianczuk/DziemianMCAgent
source venv/bin/activate
pip install -e .

# Test connections only
python -m dziemian_mc_agent --test

# Full dry run (no Notion/Telegram output)
python -m dziemian_mc_agent --dry-run

# Full production run
python -m dziemian_mc_agent
```

---

## 🎯 What Claude Outputs Per Run

10 analyzed topics, always including exactly 3 `🔥 TOTALNY OUTLIER`.

Each topic includes:
- **Temat** - topic title
- **Kąt Muzyczny** - specific musical angle suggestion (opera aria, trap, pop-punk, etc.)
- **Złote Cytaty** - 1-3 golden quotes perfect for hooks/choruses
- **VPH** - views per hour (YouTube topics)
- **Uzasadnienie** - why this topic was chosen

---

## 📝 YouTube Channels Monitored

```
KanalZero, Ksiazulo, Rembol, FameMMA, CLOUTMMA,
Matura2Bzdura, StuurTV, KrzysztofGonciarz,
LekkoStronniczy, Pyta, Imponderabilia, 20m2Lodzka
```

Keywords: `drama polska youtube`, `afera youtube`, `commentary pl`, `zgrzyt`, `beef youtube polska`, `patologia youtube`, `cringe polska`, `famemma`, `cloutmma`

To add more channels/keywords → edit `config.py`:
```python
youtube_channels: list[str] = Field(default=[...])
youtube_keywords: list[str] = Field(default=[...])
```

---

## ⚠️ Known Limitations / TODOs

- Wykop CSS selectors may need updating if Wykop changes layout
- Apify actor IDs (`quacker/twitter-scraper`, `clockworks/tiktok-scraper`) should be verified on Apify marketplace
- No deduplication between runs (same topic may appear across multiple runs)
- Tests in `tests/` are placeholder stubs - not yet implemented
