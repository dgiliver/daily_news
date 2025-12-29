"""SQLite database for storing and searching news articles."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Iterator

from daily_news.config import settings
from daily_news.models import RankedArticle, NewsDigest, CollectionStats, Region, Category

logger = logging.getLogger(__name__)


class NewsDatabase:
    """SQLite database for news article storage and search."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        self._ensure_directory()
        self._init_db()

    def _ensure_directory(self) -> None:
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main articles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_region TEXT NOT NULL,
                    source_category TEXT NOT NULL,
                    original_title TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    description TEXT,
                    original_language TEXT NOT NULL,
                    published_at TIMESTAMP,
                    collected_at TIMESTAMP NOT NULL,
                    significance_score REAL,
                    ranking_rationale TEXT,
                    digest_date DATE,
                    included_in_digest BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_digest_date
                ON articles(digest_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_collected_at
                ON articles(collected_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_significance
                ON articles(significance_score DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_source_region
                ON articles(source_region)
            """)

            # FTS5 for full-text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    title,
                    description,
                    content='articles',
                    content_rowid='rowid'
                )
            """)

            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
                    INSERT INTO articles_fts(rowid, title, description)
                    VALUES (new.rowid, new.title, new.description);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
                    INSERT INTO articles_fts(articles_fts, rowid, title, description)
                    VALUES('delete', old.rowid, old.title, old.description);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
                    INSERT INTO articles_fts(articles_fts, rowid, title, description)
                    VALUES('delete', old.rowid, old.title, old.description);
                    INSERT INTO articles_fts(rowid, title, description)
                    VALUES (new.rowid, new.title, new.description);
                END
            """)

            # Digests tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS digests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    digest_date DATE UNIQUE NOT NULL,
                    email_sent BOOLEAN DEFAULT FALSE,
                    sms_sent BOOLEAN DEFAULT FALSE,
                    article_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Collection runs for monitoring
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TIMESTAMP NOT NULL,
                    sources_attempted INTEGER,
                    sources_succeeded INTEGER,
                    articles_collected INTEGER,
                    articles_after_dedup INTEGER,
                    errors TEXT,
                    duration_seconds REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def save_articles(
        self, articles: list[RankedArticle], digest_date: date | None = None
    ) -> int:
        """Save articles to database.

        Args:
            articles: List of ranked articles to save
            digest_date: Date of the digest (defaults to today)

        Returns:
            Number of articles saved
        """
        if digest_date is None:
            digest_date = date.today()

        saved = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for article in articles:
                try:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO articles
                        (id, source_name, source_region, source_category, original_title,
                         title, url, description, original_language, published_at,
                         collected_at, significance_score, ranking_rationale, digest_date,
                         included_in_digest)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            article.id,
                            article.source_name,
                            article.source_region.value,
                            article.source_category.value,
                            article.original_title,
                            article.title,
                            str(article.url),
                            article.description,
                            article.original_language,
                            article.published_at.isoformat() if article.published_at else None,
                            article.collected_at.isoformat(),
                            article.significance_score,
                            article.ranking_rationale,
                            digest_date.isoformat(),
                            True,
                        ),
                    )
                    saved += 1
                except sqlite3.IntegrityError:
                    logger.debug(f"Article already exists: {article.url}")

            conn.commit()

        logger.info(f"Saved {saved} articles to database")
        return saved

    def save_collection_stats(self, stats: CollectionStats) -> None:
        """Save collection run statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO collection_runs
                (run_date, sources_attempted, sources_succeeded, articles_collected,
                 articles_after_dedup, errors, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    stats.sources_attempted,
                    stats.sources_succeeded,
                    stats.articles_collected,
                    stats.articles_after_dedup,
                    json.dumps(stats.errors),
                    stats.duration_seconds,
                ),
            )
            conn.commit()

    def mark_digest_sent(
        self, digest_date: date, email_sent: bool = False, sms_sent: bool = False
    ) -> None:
        """Mark a digest as sent."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO digests (digest_date, email_sent, sms_sent, article_count)
                VALUES (?, ?, ?, (SELECT COUNT(*) FROM articles WHERE digest_date = ?))
                ON CONFLICT(digest_date) DO UPDATE SET
                    email_sent = COALESCE(excluded.email_sent, email_sent),
                    sms_sent = COALESCE(excluded.sms_sent, sms_sent)
                """,
                (digest_date.isoformat(), email_sent, sms_sent, digest_date.isoformat()),
            )
            conn.commit()

    def search_articles(
        self,
        query: str,
        since: datetime | None = None,
        region: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[RankedArticle]:
        """Search articles using full-text search.

        Args:
            query: Search query string
            since: Only return articles after this datetime
            region: Filter by region
            category: Filter by category
            limit: Maximum results

        Returns:
            List of matching articles
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            base_query = """
                SELECT a.* FROM articles a
                JOIN articles_fts fts ON a.rowid = fts.rowid
                WHERE articles_fts MATCH ?
            """
            params: list = [query]

            if since:
                base_query += " AND a.collected_at > ?"
                params.append(since.isoformat())

            if region:
                base_query += " AND a.source_region = ?"
                params.append(region)

            if category:
                base_query += " AND a.source_category = ?"
                params.append(category)

            base_query += " ORDER BY a.significance_score DESC LIMIT ?"
            params.append(limit)

            cursor.execute(base_query, params)
            rows = cursor.fetchall()

            return [self._row_to_article(row) for row in rows]

    def get_articles_by_date(
        self, digest_date: date, limit: int | None = None
    ) -> list[RankedArticle]:
        """Get articles for a specific digest date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM articles
                WHERE digest_date = ?
                ORDER BY significance_score DESC
            """
            params: list = [digest_date.isoformat()]

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_article(row) for row in rows]

    def get_recent_articles(self, days: int = 7, limit: int = 100) -> list[RankedArticle]:
        """Get recent articles."""
        since = datetime.utcnow() - timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM articles
                WHERE collected_at > ?
                ORDER BY significance_score DESC
                LIMIT ?
                """,
                (since.isoformat(), limit),
            )
            rows = cursor.fetchall()

            return [self._row_to_article(row) for row in rows]

    def get_stats(self, days: int = 30) -> dict:
        """Get collection statistics."""
        since = datetime.utcnow() - timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Article counts
            cursor.execute(
                "SELECT COUNT(*) FROM articles WHERE collected_at > ?",
                (since.isoformat(),),
            )
            total_articles = cursor.fetchone()[0]

            # Articles by region
            cursor.execute(
                """
                SELECT source_region, COUNT(*) as count
                FROM articles WHERE collected_at > ?
                GROUP BY source_region
                ORDER BY count DESC
                """,
                (since.isoformat(),),
            )
            by_region = {row["source_region"]: row["count"] for row in cursor.fetchall()}

            # Collection runs
            cursor.execute(
                "SELECT COUNT(*) FROM collection_runs WHERE run_date > ?",
                (since.isoformat(),),
            )
            run_count = cursor.fetchone()[0]

            return {
                "total_articles": total_articles,
                "articles_by_region": by_region,
                "collection_runs": run_count,
                "period_days": days,
            }

    def _row_to_article(self, row: sqlite3.Row) -> RankedArticle:
        """Convert database row to RankedArticle."""
        return RankedArticle(
            id=row["id"],
            source_name=row["source_name"],
            source_region=Region(row["source_region"]),
            source_category=Category(row["source_category"]),
            original_title=row["original_title"],
            title=row["title"],
            url=row["url"],
            description=row["description"] or "",
            original_language=row["original_language"],
            published_at=datetime.fromisoformat(row["published_at"])
            if row["published_at"]
            else datetime.utcnow(),
            collected_at=datetime.fromisoformat(row["collected_at"]),
            significance_score=row["significance_score"] or 50.0,
            ranking_rationale=row["ranking_rationale"] or "",
        )
