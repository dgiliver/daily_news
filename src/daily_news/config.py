"""Application configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    data_dir: Path = Field(default=Path("data"), description="Directory for data storage")
    db_path: Path = Field(default=Path("data/news_archive.db"), description="SQLite database path")

    # Claude API
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    claude_model: str = Field(
        default="claude-sonnet-4-20250514", description="Claude model for ranking"
    )

    # Email Configuration
    gmail_address: str | None = Field(default=None, description="Gmail sender address")
    gmail_app_password: str | None = Field(default=None, description="Gmail app password")
    email_recipients: str = Field(default="", description="Comma-separated email recipients")

    # SMS Configuration
    sms_recipients: str = Field(default="", description="Comma-separated phone numbers")
    sms_carrier_gateway: str = Field(default="txt.att.net", description="SMS carrier gateway")

    # Collection Settings
    max_articles_per_source: int = Field(
        default=10, description="Max articles to collect per source"
    )
    collection_timeout: int = Field(
        default=30, description="Timeout for each source collection (seconds)"
    )
    max_concurrent_requests: int = Field(default=10, description="Max concurrent HTTP requests")

    # Digest Settings
    digest_story_count: int = Field(default=15, description="Number of stories in email digest")
    sms_headline_count: int = Field(default=5, description="Number of headlines in SMS")

    # Processing Settings
    dedup_similarity_threshold: float = Field(
        default=0.7, description="Similarity threshold for deduplication"
    )
    ranking_batch_size: int = Field(default=50, description="Articles per Claude ranking call")

    # Feature Flags
    enable_translation: bool = Field(
        default=True, description="Enable translation of non-English articles"
    )
    enable_deduplication: bool = Field(default=True, description="Enable duplicate article removal")

    @property
    def email_recipient_list(self) -> list[str]:
        """Parse email recipients into a list."""
        if not self.email_recipients:
            return []
        return [r.strip() for r in self.email_recipients.split(",") if r.strip()]

    @property
    def sms_recipient_list(self) -> list[str]:
        """Parse SMS recipients into a list."""
        if not self.sms_recipients:
            return []
        return [r.strip() for r in self.sms_recipients.split(",") if r.strip()]


settings = Settings()
