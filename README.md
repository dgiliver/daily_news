# World News Digest

A daily news aggregator that collects stories from 60+ global sources, uses AI to rank them by significance, and delivers a curated digest to your inbox each morning.

## Features

- **Global Coverage** — Sources from US, Europe, Asia-Pacific, Middle East, Africa, and Latin America
- **AI-Powered Ranking** — Claude analyzes and scores articles by global significance
- **Smart Deduplication** — Semantic clustering ensures you see 15 unique events, not 15 versions of the same story
- **Translation** — Non-English articles automatically translated
- **Paywall Bypass** — Links to paywalled sites route through archive.today
- **Searchable Archive** — SQLite database with full-text search via CLI

## How It Works

```
GitHub Actions (5 AM UTC daily)
         │
         ▼
┌─────────────────┐
│  Collect RSS    │  60+ feeds in parallel
│  (~500 articles)│
└────────┬────────┘
         ▼
┌─────────────────┐
│  Translate      │  Non-English → English
│  (Google Trans) │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Deduplicate    │  Text similarity + keyword overlap
│  (~200 unique)  │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Rank (Claude)  │  Score 0-100 by significance
│                 │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Semantic Dedup │  Claude clusters by event
│  (top 45 → 15)  │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Deliver Email  │  HTML digest to inbox
└─────────────────┘
```

## Project Structure

```
daily_news/
├── .github/workflows/
│   └── news_digest.yml      # Cron job (5 AM UTC)
├── src/daily_news/
│   ├── collectors/          # RSS feed collection
│   ├── processing/          # Translation, dedup, ranking
│   ├── delivery/            # Email formatting & sending
│   ├── storage/             # SQLite database
│   ├── sources/
│   │   └── feeds.yaml       # 60+ source definitions
│   └── cli.py               # Search interface
├── data/
│   └── news_archive.db      # Article archive (auto-created)
├── main.py                  # Pipeline orchestration
└── pyproject.toml
```

## Quick Start (Fork Setup)

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/daily_news.git
cd daily_news
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...      # From console.anthropic.com

# Email (Gmail)
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx  # App password, not regular password
EMAIL_RECIPIENTS=you@gmail.com
```

**Gmail App Password Setup:**
1. Enable 2FA on your Google account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Generate a new app password for "Mail"

### 3. Test Locally

```bash
# Run full pipeline (skip email delivery)
python main.py run --skip-delivery

# Just collect articles
python main.py collect

# View stats
python main.py stats
```

### 4. Set Up GitHub Actions

Add these secrets to your repo (Settings → Secrets → Actions):

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `GMAIL_ADDRESS` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail app password |
| `EMAIL_RECIPIENTS` | Comma-separated emails |

The workflow runs daily at 5 AM UTC. Trigger manually from Actions tab to test.

## CLI Commands

```bash
# Search the archive
daily-news search "climate change" --days 30

# View today's digest
daily-news digest

# List all sources
daily-news sources

# Show collection stats
daily-news stats

# Export to CSV/JSON
daily-news export articles.csv --days 7
```

## Customization

### Adding Sources

Edit `src/daily_news/sources/feeds.yaml`:

```yaml
- name: "Your News Source"
  region: europe          # americas_us, europe, asia_pacific, etc.
  category: general       # general, politics, economy, technology
  url: "https://example.com/rss"
  language: en            # en, es, fr, de, etc.
  priority: medium        # high, medium, low
```

### Adjusting Settings

In `.env` or as environment variables:

```bash
DIGEST_STORY_COUNT=15        # Stories in email
RANKING_BATCH_SIZE=50        # Articles per Claude call
DEDUP_SIMILARITY_THRESHOLD=0.7
MAX_ARTICLES_PER_SOURCE=10
```

### Changing Schedule

Edit `.github/workflows/news_digest.yml`:

```yaml
on:
  schedule:
    - cron: '0 5 * * *'  # 5 AM UTC daily
```

## Cost

- **GitHub Actions**: Free (runs ~10-15 min/day, well under limits)
- **Claude API**: ~$0.10-0.30/day depending on article volume
- **Translation**: Free (uses Google Translate via deep-translator)

## Architecture Notes

**Why RSS over scraping?**
RSS is more reliable, respects robots.txt, and doesn't break when sites update their HTML.

**Why SQLite?**
Simple, zero-config, and the DB is committed to the repo for persistence across workflow runs.

**Why semantic deduplication?**
Text similarity catches "Trump meets Zelensky" duplicates, but not "Peace talks progress" covering the same event. Claude identifies these semantic duplicates.

**Why archive.today for paywalls?**
It's free, reliable, and doesn't require browser extensions or account setup.

## License

MIT

---

Built with Claude Code
