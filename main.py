#!/usr/bin/env python3
"""Main entry point for Daily News Aggregator.

This script orchestrates the full news collection, processing, and delivery pipeline.
Can be run manually or via GitHub Actions.

Usage:
    python main.py              # Run full pipeline
    python main.py collect      # Only collect articles
    python main.py rank         # Only rank (requires prior collection)
    python main.py deliver      # Only deliver (requires prior ranking)
    python main.py --help       # Show help
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import date, datetime

from dotenv import load_dotenv

# Load environment variables before importing config
load_dotenv()

from daily_news.collectors import RSSCollector
from daily_news.config import settings
from daily_news.delivery import EmailDelivery, SMSDelivery
from daily_news.models import CollectionStats, NewsDigest, RankedArticle
from daily_news.processing import (
    ArticleDeduplicator,
    ClaudeRanker,
    SemanticDeduplicator,
    TranslationService,
)
from daily_news.sources import load_sources
from daily_news.storage import NewsDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class NewsPipeline:
    """Orchestrates the full news aggregation pipeline."""

    def __init__(self):
        self.db = NewsDatabase()
        self.stats = CollectionStats()
        self.start_time = time.time()

    async def collect(self) -> list:
        """Collect articles from all sources."""
        logger.info("Starting article collection...")

        sources = load_sources()
        self.stats.sources_attempted = len(sources)
        logger.info(f"Loaded {len(sources)} sources")

        collector = RSSCollector()
        raw_articles = await collector.collect_all(sources)

        self.stats.articles_collected = len(raw_articles)
        self.stats.sources_succeeded = len({a.source_name for a in raw_articles})

        logger.info(
            f"Collected {len(raw_articles)} articles from "
            f"{self.stats.sources_succeeded}/{self.stats.sources_attempted} sources"
        )

        return raw_articles

    def translate(self, raw_articles: list) -> list:
        """Translate non-English articles."""
        logger.info("Translating articles...")

        translator = TranslationService()
        processed = translator.translate_articles(raw_articles)

        logger.info(f"Processed {len(processed)} articles with translations")
        return processed

    def deduplicate(self, processed_articles: list) -> list:
        """Remove duplicate articles."""
        logger.info("Deduplicating articles...")

        deduplicator = ArticleDeduplicator()
        unique = deduplicator.deduplicate(processed_articles)

        self.stats.articles_after_dedup = len(unique)
        logger.info(f"Deduplication: {len(processed_articles)} -> {len(unique)} articles")

        return unique

    def rank(self, articles: list) -> list[RankedArticle]:
        """Rank articles by significance using Claude."""
        logger.info("Ranking articles with Claude AI...")

        try:
            ranker = ClaudeRanker()
            ranked = ranker.rank_articles(articles)
            logger.info(f"Ranked {len(ranked)} articles")
            return ranked
        except ValueError as e:
            logger.error(f"Ranking failed: {e}")
            # Return articles with default scores
            return [
                RankedArticle(
                    **a.model_dump(),
                    significance_score=50.0,
                    ranking_rationale="Ranking unavailable",
                )
                for a in articles
            ]

    def save(self, ranked_articles: list[RankedArticle]) -> None:
        """Save articles to database."""
        logger.info("Saving articles to database...")

        saved = self.db.save_articles(ranked_articles)
        logger.info(f"Saved {saved} articles")

        # Save collection stats
        self.stats.duration_seconds = time.time() - self.start_time
        self.db.save_collection_stats(self.stats)

    def semantic_dedup(self, ranked_articles: list[RankedArticle]) -> list[RankedArticle]:
        """Remove semantically duplicate articles from top stories.

        Uses Claude to identify articles covering the same event and keeps
        only the highest-scored article from each event cluster.
        """
        logger.info("Running semantic deduplication on top stories...")

        try:
            deduplicator = SemanticDeduplicator()
            # Target slightly more than digest count to allow for SMS headlines
            unique = deduplicator.deduplicate_top_stories(
                ranked_articles, target_count=settings.digest_story_count + 5
            )
            logger.info(f"Semantic dedup: kept {len(unique)} unique events")
            return unique
        except ValueError as e:
            logger.warning(f"Semantic deduplication unavailable: {e}")
            return ranked_articles

    def create_digest(self, ranked_articles: list[RankedArticle]) -> NewsDigest:
        """Create news digest from ranked articles."""
        top_stories = ranked_articles[: settings.digest_story_count]
        sms_headlines = ranked_articles[: settings.sms_headline_count]

        return NewsDigest(
            date=datetime.utcnow(),
            top_stories=top_stories,
            sms_headlines=sms_headlines,
            collection_stats=self.stats,
        )

    def deliver_email(self, digest: NewsDigest) -> bool:
        """Send email digest."""
        logger.info("Sending email digest...")

        try:
            email = EmailDelivery()
            success = email.send_digest(digest)
            if success:
                self.db.mark_digest_sent(date.today(), email_sent=True)
                logger.info("Email digest sent successfully")
            return success
        except ValueError as e:
            logger.error(f"Email delivery not configured: {e}")
            return False

    def deliver_sms(self, digest: NewsDigest) -> bool:
        """Send SMS headlines."""
        logger.info("Sending SMS headlines...")

        try:
            sms = SMSDelivery()
            success = sms.send_headlines(digest)
            if success:
                self.db.mark_digest_sent(date.today(), sms_sent=True)
                logger.info("SMS headlines sent successfully")
            return success
        except ValueError as e:
            logger.error(f"SMS delivery not configured: {e}")
            return False

    async def run_full_pipeline(self, skip_delivery: bool = False) -> NewsDigest:
        """Run the complete pipeline."""
        logger.info("=" * 50)
        logger.info("Starting Daily News Pipeline")
        logger.info("=" * 50)

        # 1. Collect
        raw_articles = await self.collect()
        if not raw_articles:
            logger.error("No articles collected!")
            raise RuntimeError("Collection failed - no articles")

        # 2. Translate
        processed = self.translate(raw_articles)

        # 3. Deduplicate
        unique = self.deduplicate(processed)

        # 4. Rank
        ranked = self.rank(unique)

        # 5. Semantic deduplication of top stories
        top_unique = self.semantic_dedup(ranked)

        # 6. Save all ranked articles (not just deduplicated)
        self.save(ranked)

        # 7. Create digest from semantically deduplicated top stories
        digest = self.create_digest(top_unique)

        # 8. Deliver (unless skipped)
        if not skip_delivery:
            self.deliver_email(digest)
            self.deliver_sms(digest)

        # Summary
        duration = time.time() - self.start_time
        logger.info("=" * 50)
        logger.info("Pipeline Complete!")
        logger.info(f"Duration: {duration:.1f}s")
        logger.info(
            f"Articles: {self.stats.articles_collected} collected -> {self.stats.articles_after_dedup} unique"
        )
        logger.info(f"Top story: {ranked[0].title if ranked else 'None'}")
        logger.info("=" * 50)

        return digest


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Daily News Aggregator - World news with AI-powered ranking"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "collect", "rank", "deliver", "stats"],
        help="Command to run (default: run full pipeline)",
    )
    parser.add_argument(
        "--skip-delivery",
        action="store_true",
        help="Skip email/SMS delivery (for testing)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    pipeline = NewsPipeline()

    try:
        if args.command == "run":
            await pipeline.run_full_pipeline(skip_delivery=args.skip_delivery)

        elif args.command == "collect":
            raw = await pipeline.collect()
            processed = pipeline.translate(raw)
            unique = pipeline.deduplicate(processed)
            # Save without ranking for later
            logger.info(f"Collection complete: {len(unique)} unique articles ready for ranking")

        elif args.command == "rank":
            # Load today's articles and rank them
            db = NewsDatabase()
            articles = db.get_articles_by_date(date.today())
            if articles:
                ranked = pipeline.rank(articles)
                pipeline.save(ranked)
            else:
                logger.warning("No articles found to rank. Run 'collect' first.")

        elif args.command == "deliver":
            # Load today's ranked articles and deliver
            db = NewsDatabase()
            articles = db.get_articles_by_date(date.today(), limit=settings.digest_story_count)
            if articles:
                digest = pipeline.create_digest(articles)
                pipeline.deliver_email(digest)
                pipeline.deliver_sms(digest)
            else:
                logger.warning("No articles found to deliver. Run full pipeline first.")

        elif args.command == "stats":
            db = NewsDatabase()
            stats = db.get_stats()
            print("\nDatabase Statistics (last 30 days):")
            print(f"  Total articles: {stats['total_articles']:,}")
            print(f"  Collection runs: {stats['collection_runs']}")
            print("\nArticles by region:")
            for region, count in sorted(stats["articles_by_region"].items(), key=lambda x: -x[1]):
                print(f"  {region}: {count}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
