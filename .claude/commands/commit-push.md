---
description: Format, lint, test, commit, and push changes
argument-hint: <commit-message>
allowed-tools:
  - Bash
  - Read
---

Complete git workflow with quality checks before committing.

## Usage

```
/commit-push "Fix RSS feed collection timeout"
```

## Steps

1. **Format code:**
   ```bash
   cd /Users/dgiliver/personal_projects/daily_news
   ruff format .
   ```

2. **Lint and fix:**
   ```bash
   ruff check --fix .
   ```

3. **Run tests:**
   ```bash
   pytest
   ```

4. **If all pass, stage changes:**
   ```bash
   git add -A
   git status
   ```

5. **Create commit:**
   ```bash
   git commit -m "$ARGUMENTS

   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
   ```

6. **Push to remote:**
   ```bash
   git push origin $(git branch --show-current)
   ```

## Pre-commit Checklist

- [ ] All tests pass (`pytest`)
- [ ] No lint errors (`ruff check .`)
- [ ] Code is formatted (`ruff format .`)
- [ ] Commit message is descriptive
