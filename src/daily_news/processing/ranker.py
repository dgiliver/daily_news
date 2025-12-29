"""AI-powered article ranking using Claude."""

import json
import logging
from typing import Any

import anthropic

from daily_news.config import settings
from daily_news.models import ProcessedArticle, RankedArticle

logger = logging.getLogger(__name__)


class ClaudeRanker:
    """Rank articles by significance using Claude AI."""

    def __init__(self):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for ranking")
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.batch_size = settings.ranking_batch_size

    def rank_articles(self, articles: list[ProcessedArticle]) -> list[RankedArticle]:
        """Rank articles by significance.

        Args:
            articles: List of processed articles to rank

        Returns:
            List of ranked articles sorted by significance score
        """
        if not articles:
            return []

        ranked = []

        # Process in batches
        for i in range(0, len(articles), self.batch_size):
            batch = articles[i : i + self.batch_size]
            batch_ranked = self._rank_batch(batch)
            ranked.extend(batch_ranked)

        # Sort by significance score (highest first)
        ranked.sort(key=lambda x: x.significance_score, reverse=True)

        logger.info(f"Ranked {len(ranked)} articles")
        return ranked

    def _rank_batch(self, articles: list[ProcessedArticle]) -> list[RankedArticle]:
        """Rank a batch of articles.

        Args:
            articles: Batch of articles to rank

        Returns:
            List of ranked articles
        """
        prompt = self._build_ranking_prompt(articles)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text
            rankings = self._parse_ranking_response(response_text)

            ranked_articles = []
            for i, article in enumerate(articles):
                ranking = rankings.get(i, {"score": 50, "rationale": "Default score"})
                ranked_article = RankedArticle(
                    **article.model_dump(),
                    significance_score=ranking["score"],
                    ranking_rationale=ranking["rationale"],
                )
                ranked_articles.append(ranked_article)

            return ranked_articles

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            # Return articles with default scores on API failure
            return [
                RankedArticle(
                    **article.model_dump(),
                    significance_score=50.0,
                    ranking_rationale="API error - default score",
                )
                for article in articles
            ]
        except Exception as e:
            logger.error(f"Ranking error: {e}")
            return [
                RankedArticle(
                    **article.model_dump(),
                    significance_score=50.0,
                    ranking_rationale="Error - default score",
                )
                for article in articles
            ]

    def _build_ranking_prompt(self, articles: list[ProcessedArticle]) -> str:
        """Build the ranking prompt for Claude.

        Args:
            articles: Articles to include in prompt

        Returns:
            Prompt string
        """
        articles_text = ""
        for i, article in enumerate(articles):
            articles_text += f"""
[{i}]
Title: {article.title}
Source: {article.source_name} ({article.source_region.value})
Category: {article.source_category.value}
Description: {article.description[:200] if article.description else 'N/A'}
"""

        return f"""You are an expert news editor ranking stories for a world news digest for a reader in New York City.

Rate each story from 0-100 based on these criteria:
- Global significance and impact (weight: 40%)
- Relevance to US readers (weight: 25%)
- Uniqueness/underreported angle (weight: 20%)
- Timeliness and urgency (weight: 15%)

Important guidelines:
- Major global events (wars, disasters, elections in large countries) should score 80-100
- Significant policy changes or economic news affecting multiple countries: 60-80
- Regional news with limited global impact: 40-60
- Local/niche stories: 20-40
- Underreported stories from Africa, Latin America, etc. get a bonus if truly significant

Here are the stories to rank:
{articles_text}

Return ONLY a valid JSON array with your rankings. Each item should have:
- "index": the story number
- "score": 0-100 significance score
- "rationale": 1 sentence explaining the score

Example format:
[{{"index": 0, "score": 85, "rationale": "Major geopolitical development affecting multiple regions"}}]

Respond with only the JSON array, no other text:"""

    def _parse_ranking_response(self, response: str) -> dict[int, dict[str, Any]]:
        """Parse Claude's ranking response.

        Args:
            response: Raw response text from Claude

        Returns:
            Dict mapping article index to score and rationale
        """
        try:
            # Try to extract JSON from response
            response = response.strip()

            # Handle potential markdown code blocks
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1])

            rankings_list = json.loads(response)

            rankings = {}
            for item in rankings_list:
                idx = item.get("index", 0)
                rankings[idx] = {
                    "score": float(item.get("score", 50)),
                    "rationale": item.get("rationale", ""),
                }

            return rankings

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ranking response: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Error parsing rankings: {e}")
            return {}
