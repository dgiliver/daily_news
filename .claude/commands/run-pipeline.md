---
description: Execute the news collection pipeline with optional delivery skip
argument-hint: [--skip-delivery] [--verbose]
allowed-tools:
  - Bash
  - Read
---

Run the Daily News pipeline to collect, rank, and optionally deliver the news digest.

## Usage

```
/run-pipeline                    # Full pipeline with email/SMS delivery
/run-pipeline --skip-delivery    # Test without sending
/run-pipeline --verbose          # Enable debug logging
```

## Steps

1. **Verify environment:**
   - Check .env file exists with required keys
   - Confirm we're in the daily_news directory

2. **Run the pipeline:**
   ```bash
   cd /Users/dgiliver/personal_projects/daily_news
   python main.py $ARGUMENTS
   ```

3. **Monitor output:**
   - Watch for collection errors (failed feeds)
   - Check deduplication stats
   - Verify ranking completed

4. **Post-run verification:**
   ```bash
   python -m daily_news.cli stats
   ```

## Common Issues

- **ANTHROPIC_API_KEY missing**: Check .env file
- **SMTP auth failed**: Regenerate Gmail App Password
- **Many feeds failing**: Run `/test-feeds` to diagnose
