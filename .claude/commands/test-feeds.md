---
description: Validate that all RSS feeds are accessible and returning valid content
allowed-tools:
  - Bash
  - Read
---

Test all configured RSS feeds for accessibility and valid responses.

## What This Does

1. Loads all feed configurations from `src/daily_news/sources/feeds.yaml`
2. Tests each feed URL for HTTP accessibility
3. Validates RSS/Atom XML structure
4. Reports working vs broken feeds

## Run Test

```bash
cd /Users/dgiliver/personal_projects/daily_news
python -c "
import asyncio
from daily_news.collectors.rss import RSSCollector
from daily_news.sources.registry import load_sources

async def test_feeds():
    sources = load_sources()
    collector = RSSCollector()

    working = []
    broken = []

    for source in sources:
        healthy = await collector.health_check(source)
        if healthy:
            working.append(source.name)
        else:
            broken.append(source.name)

    print(f'\n=== Feed Health Report ===')
    print(f'Working: {len(working)}/{len(sources)}')
    print(f'Broken: {len(broken)}/{len(sources)}')

    if broken:
        print(f'\nBroken feeds:')
        for name in broken:
            print(f'  - {name}')

asyncio.run(test_feeds())
"
```

## If Feeds Are Broken

1. Check if the publication changed their RSS URL
2. Search for alternative RSS endpoints (common paths: /rss, /feed, /feeds/rss.xml)
3. Update `src/daily_news/sources/feeds.yaml` with working URLs
4. Consider disabling persistently broken feeds
