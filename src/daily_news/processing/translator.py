"""Translation service for non-English articles."""

import logging

from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound

from daily_news.config import settings
from daily_news.models import ProcessedArticle, RawArticle

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating articles to English."""

    def __init__(self, target_language: str = "en"):
        self.target = target_language
        self._cache: dict[str, str] = {}

    def translate_text(self, text: str, source_language: str) -> str:
        """Translate text from source language to target.

        Args:
            text: Text to translate
            source_language: Source language code (e.g., 'fr', 'de') or 'auto' for detection

        Returns:
            Translated text, or original if translation fails
        """
        # Skip if empty or already target language
        if not text or source_language == self.target:
            return text

        # Check cache first (use auto for cache key since we always auto-detect now)
        cache_key = f"auto:{hash(text)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Translate with auto-detection for better accuracy
        result = text
        try:
            translator = GoogleTranslator(source="auto", target=self.target)
            translated: str = translator.translate(text)
            if translated:
                self._cache[cache_key] = translated
                result = translated
        except TranslationNotFound:
            logger.warning(f"Translation not found for text (hint: {source_language})")
        except Exception as e:
            logger.error(f"Translation error (hint: {source_language}): {e}")

        return result

    def translate_article(self, article: RawArticle) -> ProcessedArticle:
        """Translate a raw article to English.

        Args:
            article: Raw article to translate

        Returns:
            ProcessedArticle with translated title and description
        """
        if not settings.enable_translation or article.language == "en":
            return ProcessedArticle.from_raw(article)

        translated_title = self.translate_text(article.title, article.language)
        translated_description = None
        if article.description:
            translated_description = self.translate_text(article.description, article.language)

        return ProcessedArticle.from_raw(
            article,
            translated_title=translated_title,
            translated_description=translated_description,
        )

    def translate_articles(self, articles: list[RawArticle]) -> list[ProcessedArticle]:
        """Translate a batch of articles.

        Args:
            articles: List of raw articles

        Returns:
            List of processed articles with translations
        """
        processed = []
        for article in articles:
            try:
                processed_article = self.translate_article(article)
                processed.append(processed_article)
            except Exception as e:
                logger.error(f"Failed to process article {article.title[:50]}: {e}")
                # Still include the article without translation
                processed.append(ProcessedArticle.from_raw(article))

        logger.info(f"Processed {len(processed)} articles with translations")
        return processed
