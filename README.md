# DziemianMCAgent 🎵🤖

AI-powered trend research agent for YouTube channel **"Dziemian - Muzyczne Commentary"**.

Automatically scrapes Polish internet (YouTube, Wykop, Google Trends, X, TikTok), analyzes content with Claude AI, and delivers top 10 viral topics with musical angle suggestions.

## 🎯 What It Does

1. **Scrapes** trending content from multiple sources (last 48h)
2. **Analyzes** with Claude 3.5 Sonnet - filters, scores, suggests musical angles
3. **Saves** results to Notion database
4. **Notifies** via Telegram with top 3 "TOTALNY OUTLIER" topics

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/DziemianMCAgent.git
cd DziemianMCAgent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required keys:**
- `ANTHROPIC_API_KEY` - Claude API key
- `NOTION_API_KEY` - Notion integration token
- `NOTION_DATABASE_ID` - Your Notion database ID
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Your chat ID

### 3. Run

```bash
# Full run
python -m dziemian_mc_agent

# Dry run (no Notion/Telegram output)
python -m dziemian_mc_agent --dry-run

# Test connections
python -m dziemian_mc_agent --test
```

## 📁 Project Structure

```
DziemianMCAgent/
��── src/dziemian_mc_agent/
│   ├── scrapers/          # Data ingestion
│   │   ├── youtube.py     # YouTube (yt-dlp)
│   │   ├── wykop.py       # Wykop.pl
│   │   ├── google_trends.py
│   │   └── apify.py       # X/TikTok
│   ├── ai/                # Claude analysis
│   │   ├── analyzer.py
│   │   └── prompts.py
│   ├��─ notion/            # Notion integration
│   ├── telegram/          # Notifications
│   ├── models/            # Data schemas
│   ├── config.py          # Settings
│   └── main.py            # Orchestrator
├── .env.example
├── requirements.txt
├── Dockerfile
└── railway.json           # Railway cron config
```

## 🚂 Railway Deployment

1. Push to GitHub
2. Create new Railway project
3. Connect your repo
4. Add environment variables in Railway dashboard
5. Deploy!

The agent runs as a cron job every 12 hours (8:00 and 20:00).

## 📊 Notion Database Setup

Create a Notion database with these properties:

| Property | Type | Description |
|----------|------|-------------|
| Temat | Title | Topic title |
| Link | URL | Source link |
| Status | Select | "Do przejrzenia", "W produkcji", "Gotowe" |
| Typ | Select | "🔥 TOTALNY OUTLIER", "💎 Duży potencjał", "📈 Trend" |
| VPH | Number | Views per hour |
| Kąt Muzyczny | Text | Musical angle suggestion |
| Złote Cytaty | Text | Golden quotes for hooks |
| Uzasadnienie | Text | Reasoning |
| Cross-Platform Score | Number | Cross-platform presence (0-100) |

## 🤖 Telegram Bot Setup

1. Message @BotFather on Telegram
2. Create new bot: `/newbot`
3. Copy the token to `TELEGRAM_BOT_TOKEN`
4. Get your chat ID: message @userinfobot
5. Set `TELEGRAM_CHAT_ID`

## 📝 License

MIT

## 👨‍💻 Author

**Dziemian** (Maciej Dziemiańczuk)
- Co-creator of "The Dziemians" (120M+ views)
- Opera vocalist & multi-instrumentalist
- AI/Automation expert
