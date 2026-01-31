---
description: Analyze why duplicate articles are appearing in digests
allowed-tools:
  - Bash
  - Read
---

Diagnose duplicate article issues and analyze article age distribution.

## What This Does

1. Analyzes articles from recent days for duplicates
2. Checks article age distribution (how old are articles being collected?)
3. Identifies patterns causing duplicates

## Run Analysis

```bash
cd /Users/dgiliver/personal_projects/daily_news
python -c "
from datetime import datetime, timedelta
from collections import defaultdict
from difflib import SequenceMatcher
from daily_news.storage.database import NewsDatabase

db = NewsDatabase()
articles = db.get_recent_articles(days=3)

print(f'=== Duplicate Analysis ({len(articles)} articles) ===\n')

# Age distribution
now = datetime.utcnow()
age_buckets = defaultdict(int)
no_date_count = 0

for a in articles:
    if a.published_at:
        age = now - a.published_at
        if age < timedelta(hours=6):
            age_buckets['< 6 hours'] += 1
        elif age < timedelta(hours=12):
            age_buckets['6-12 hours'] += 1
        elif age < timedelta(hours=24):
            age_buckets['12-24 hours'] += 1
        elif age < timedelta(hours=48):
            age_buckets['24-48 hours'] += 1
        else:
            age_buckets['> 48 hours'] += 1
    else:
        no_date_count += 1

print('Age Distribution:')
for bucket, count in sorted(age_buckets.items()):
    print(f'  {bucket}: {count}')
if no_date_count:
    print(f'  No date: {no_date_count}')

# Find similar titles
print('\n\nPotential Duplicates (>70% similar):')
seen = []
duplicates = []

for a in articles:
    for s in seen:
        ratio = SequenceMatcher(None, a.title.lower(), s.title.lower()).ratio()
        if ratio > 0.7:
            duplicates.append((a.title[:60], s.title[:60], f'{ratio:.0%}'))
    seen.append(a)

for d in duplicates[:10]:
    print(f'  [{d[2]}] \"{d[0]}...\" vs \"{d[1]}...\"')

if len(duplicates) > 10:
    print(f'  ... and {len(duplicates) - 10} more')

print(f'\nTotal potential duplicates: {len(duplicates)}')
"
```

## Interpreting Results

- **Many articles > 24 hours**: Freshness filter not working or feeds have old content
- **Many duplicates same day**: Deduplication threshold may need adjustment
- **Duplicates across days**: Need to filter against previously sent articles
