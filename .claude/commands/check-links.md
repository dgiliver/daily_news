---
description: Test archive.ph paywall bypass links for recent articles
allowed-tools:
  - Bash
  - Read
  - WebFetch
---

Verify that archive.ph links are working for paywall sites in recent articles.

## What This Does

1. Gets recent articles from the database that are from paywall sites
2. Tests the archive.ph links to verify they resolve correctly
3. Reports success/failure rates

## Run Check

```bash
cd /Users/dgiliver/personal_projects/daily_news
python -c "
import httpx
from datetime import date
from daily_news.storage.database import NewsDatabase
from daily_news.delivery.email import EmailDelivery

PAYWALL_DOMAINS = [
    'nytimes.com', 'washingtonpost.com', 'wsj.com', 'ft.com',
    'economist.com', 'bloomberg.com', 'theatlantic.com', 'newyorker.com',
]

db = NewsDatabase()
articles = db.get_articles_by_date(date.today(), limit=50)

paywall_articles = [
    a for a in articles
    if any(d in str(a.url) for d in PAYWALL_DOMAINS)
]

print(f'Found {len(paywall_articles)} paywall articles to test')

if paywall_articles:
    email = EmailDelivery.__new__(EmailDelivery)
    email.sender = None

    working = 0
    failed = 0

    for article in paywall_articles[:10]:  # Test first 10
        archive_url = email._get_reader_url(str(article.url))
        try:
            response = httpx.head(archive_url, follow_redirects=True, timeout=10)
            if response.status_code < 400:
                print(f'  OK: {article.source_name}')
                working += 1
            else:
                print(f'  FAIL ({response.status_code}): {article.source_name}')
                failed += 1
        except Exception as e:
            print(f'  ERROR: {article.source_name} - {e}')
            failed += 1

    print(f'\nResults: {working} working, {failed} failed')
"
```

## If Links Are Failing

1. Check if archive.ph is being rate-limited or blocked
2. Try archive.today as an alternative domain
3. Consider using 12ft.io as a fallback
4. For persistent failures, link to original URL instead
