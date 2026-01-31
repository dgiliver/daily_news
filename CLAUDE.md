# Daily News Aggregator - Claude Development Guide

## Project Overview

A news aggregation pipeline that collects articles from 60+ RSS feeds worldwide, ranks them using Claude AI, and delivers a digest via email and SMS.

## Architecture

```
main.py                          # Pipeline orchestrator (NewsPipeline class)
src/daily_news/
  cli.py                         # CLI commands (search, digest, stats, export)
  config.py                      # Pydantic settings from .env
  models.py                      # Article, Digest, Source models
  collectors/
    base.py                      # Abstract collector interface
    rss.py                       # Async RSS/Atom feed collection
  processing/
    deduplicator.py              # Title similarity + Claude semantic dedup
    ranker.py                    # Claude-powered article significance scoring
    translator.py                # Google Translate for non-English articles
  delivery/
    email.py                     # Gmail SMTP + archive.ph paywall bypass
    sms.py                       # SMS via email-to-SMS gateway
  storage/
    database.py                  # SQLite with FTS5 full-text search
  sources/
    registry.py                  # Load and filter source configs
    feeds.yaml                   # 60+ RSS feed definitions by region
```

## Pipeline Flow

```
Collection -> Translation -> Deduplication -> Ranking -> Semantic Dedup -> Save -> Delivery
```

1. **Collection**: Fetch articles from 60+ RSS feeds in parallel (async)
2. **Translation**: Translate non-English articles via Google Translate
3. **Deduplication**: Remove duplicates by title similarity (70% threshold)
4. **Ranking**: Claude scores articles 0-100 by global significance
5. **Semantic Dedup**: Claude clusters articles by underlying event
6. **Save**: Persist to SQLite with full-text search indexing
7. **Delivery**: Email digest + SMS headlines to recipients

## Development Commands

### Running the Pipeline
```bash
python main.py                   # Full pipeline with email/SMS delivery
python main.py --skip-delivery   # Test without sending (dry run)
python main.py --verbose         # Enable debug logging
```

### CLI Commands
```bash
daily-news search "query"        # Full-text search of archive
daily-news digest 2025-01-15     # View digest for specific date
daily-news sources               # List all configured feeds
daily-news stats                 # Collection statistics
daily-news export --format csv   # Export to CSV/JSON
daily-news recent --days 3       # Show top articles from past N days
```

### Testing
```bash
pytest                           # Run all tests
pytest -v tests/test_processing.py  # Specific test file
pytest -x                        # Stop on first failure
```

### Code Quality
```bash
ruff check --fix .               # Lint and auto-fix
ruff format .                    # Format code
pre-commit run --all-files       # Run all hooks
```

## Known Issues and Solutions

### 1. Archive.ph Links Failing
**Symptom:** Paywall bypass links return 403 or don't load content
**Cause:** archive.ph may not have a snapshot, rate-limiting, or URL encoding issues
**Solution:**
- The code now uses fallback services: archive.ph -> archive.today -> 12ft.io
- If all fail, returns original URL
**Files:** `src/daily_news/delivery/email.py:_get_reader_url()`

### 2. Duplicate Headlines Appearing Across Days
**Symptom:** Same stories appear in multiple consecutive digests
**Cause:** No freshness filtering; dedup only checked current batch
**Solution:**
- Articles must be published within last 24 hours (`max_article_age_hours` config)
- Articles already sent in previous 48h are filtered out
- Title similarity check against recently sent articles
**Files:** `src/daily_news/collectors/rss.py`, `src/daily_news/main.py`

### 3. RSS Feed Returning Old Articles
**Symptom:** Articles from weeks ago appearing in digest
**Cause:** Some RSS feeds include very old articles in their feed
**Solution:** `max_article_age_hours` setting filters by `published_at` date
**Files:** `src/daily_news/config.py`, `src/daily_news/collectors/rss.py`

### 4. Missing Published Dates
**Symptom:** Articles with no date get included regardless of age
**Cause:** Some feeds don't provide `published_parsed` or `updated_parsed`
**Solution:** Articles without valid published_at dates are assigned current time
**Files:** `src/daily_news/collectors/rss.py:_parse_entry()`

## Common Errors

### API Errors
- `ANTHROPIC_API_KEY is required`: Set in .env file
- `anthropic.RateLimitError`: Reduce `ranking_batch_size` in config or add delays
- `anthropic.APIConnectionError`: Check network, retry with backoff

### Collection Errors
- `httpx.ConnectTimeout`: Increase `collection_timeout` in config (default 30s)
- `feedparser.CharacterEncodingOverride`: Feed has encoding issues, usually harmless
- Empty feed responses: RSS URL may have changed; run `/test-feeds` command

### Email Errors
- `SMTPAuthenticationError`: Regenerate Gmail App Password (not regular password)
- `No email recipients configured`: Set `EMAIL_RECIPIENTS` in .env
- SSL certificate errors: Update certifi package

### Database Errors
- `sqlite3.OperationalError: database is locked`: Close other connections
- FTS index corruption: Delete `news_archive.db` and re-run pipeline

## Testing Requirements

Before merging any changes:
1. `pytest` passes with no failures
2. `ruff check .` has no errors
3. `python main.py --skip-delivery` completes successfully
4. New features have corresponding tests in `tests/`

## Environment Variables

**Required:**
- `ANTHROPIC_API_KEY`: Claude API key for ranking
- `GMAIL_ADDRESS`: Sender email address
- `GMAIL_APP_PASSWORD`: Gmail app-specific password (not regular password)
- `EMAIL_RECIPIENTS`: Comma-separated recipient list

**Optional:**
- `SMS_RECIPIENTS`: Phone numbers for SMS headlines
- `SMS_CARRIER_GATEWAY`: Default `txt.att.net`
- `MAX_ARTICLE_AGE_HOURS`: Maximum article age (default 24)

## Configuration Settings

Key settings in `src/daily_news/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `max_articles_per_source` | 10 | Articles collected per RSS feed |
| `collection_timeout` | 30 | HTTP timeout in seconds |
| `max_concurrent_requests` | 10 | Parallel feed fetches |
| `dedup_similarity_threshold` | 0.7 | Title similarity threshold (0-1) |
| `digest_story_count` | 15 | Number of stories in email |
| `sms_headline_count` | 5 | Number of SMS headlines |
| `max_article_age_hours` | 24 | Maximum article age in hours |
| `skip_previously_sent` | True | Filter out already-sent articles |
| `ranking_batch_size` | 50 | Articles per Claude API call |

## Adding New RSS Sources

Edit `src/daily_news/sources/feeds.yaml`:

```yaml
sources:
  - name: "New Publication"
    url: "https://example.com/rss"
    region: americas_us  # or europe, asia_pacific, etc.
    category: news
    language: en
    priority: medium
```

Regions: `americas_us`, `americas_latam`, `europe`, `asia_pacific`, `middle_east`, `africa`, `local_ny`, `global`

## Debugging Tips

1. **Check feed health**: Run `/test-feeds` to validate all RSS URLs
2. **Inspect article ages**: Run `/debug-duplicates` to see age distribution
3. **Test paywall bypass**: Run `/check-links` on recent articles
4. **View collection stats**: `daily-news stats` shows success rates
5. **Enable verbose logging**: `python main.py --verbose`

## Claude Code Commands

- `/run-pipeline` - Execute pipeline with optional flags
- `/test-feeds` - Validate all RSS feeds are working
- `/check-links` - Test archive.ph links for recent articles
- `/debug-duplicates` - Analyze duplicate article issues
- `/commit-push` - Format, lint, test, commit, and push
