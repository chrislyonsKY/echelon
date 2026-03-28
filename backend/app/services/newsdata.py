"""
News aggregation service.

Pulls conflict-related articles from three independent sources:
  1. NewsData.io  — /api/1/latest (free: 200 credits/day)
  2. NewsAPI.org   — /v2/everything (free: 100 requests/day)
  3. GNews.io      — /api/v4/search (free: 100 requests/day)

All three feed the same signal type (newsdata_article, weight 0.12).
Articles are geocoded via country-name → centroid mapping.
"""
import hashlib
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

CONFLICT_QUERY = "military conflict OR airstrike OR missile attack OR drone strike"

# Country name → approximate centroid for geocoding articles
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "ukraine": (48.38, 31.17),
    "russia": (61.52, 105.32),
    "israel": (31.05, 34.85),
    "palestine": (31.95, 35.23),
    "syria": (34.80, 38.99),
    "iraq": (33.22, 43.68),
    "iran": (32.43, 53.69),
    "yemen": (15.55, 48.52),
    "libya": (26.34, 17.23),
    "somalia": (5.15, 46.20),
    "sudan": (12.86, 30.22),
    "ethiopia": (9.15, 40.49),
    "myanmar": (21.91, 95.96),
    "afghanistan": (33.94, 67.71),
    "pakistan": (30.38, 69.35),
    "lebanon": (33.85, 35.86),
    "nigeria": (9.08, 8.68),
    "democratic republic of the congo": (-4.04, 21.76),
    "china": (35.86, 104.20),
    "taiwan": (23.70, 120.96),
    "north korea": (40.34, 127.51),
    "south korea": (35.91, 127.77),
    "philippines": (12.88, 121.77),
    "united states": (37.09, -95.71),
    "united kingdom": (55.38, -3.44),
    "turkey": (38.96, 35.24),
    "saudi arabia": (23.89, 45.08),
    "egypt": (26.82, 30.80),
    "india": (20.59, 78.96),
    "mali": (17.57, -4.00),
}


class NewsService:
    """Aggregated news client pulling from NewsData, NewsAPI, and GNews."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def fetch_all_sources(self) -> list[dict[str, Any]]:
        """Fetch articles from all three news APIs and merge results.

        Each source is called independently — failures in one don't block others.

        Returns:
            Deduplicated list of geocoded article dicts.
        """
        all_articles: list[dict[str, Any]] = []

        if settings.newsdata_api_key:
            articles = await self._fetch_newsdata()
            all_articles.extend(articles)
            logger.info("NewsData: %d articles", len(articles))

        if settings.newsapi_api_key:
            articles = await self._fetch_newsapi()
            all_articles.extend(articles)
            logger.info("NewsAPI: %d articles", len(articles))

        if settings.gnews_api_key:
            articles = await self._fetch_gnews()
            all_articles.extend(articles)
            logger.info("GNews: %d articles", len(articles))

        logger.info("News total: %d articles from all sources", len(all_articles))
        return all_articles

    async def _fetch_newsdata(self) -> list[dict[str, Any]]:
        """Fetch from NewsData.io /api/1/latest."""
        try:
            response = await self._client.get(
                "https://newsdata.io/api/1/latest",
                params={
                    "apikey": settings.newsdata_api_key,
                    "q": CONFLICT_QUERY,
                    "language": "en",
                    "size": 10,
                },
            )
            response.raise_for_status()
            body = response.json()
        except Exception:
            logger.warning("NewsData fetch failed", exc_info=True)
            return []

        articles: list[dict[str, Any]] = []
        for a in body.get("results", []):
            if a.get("duplicate"):
                continue
            lat, lon = _geocode_countries(a.get("country", []))
            if lat is None:
                continue
            articles.append({
                "article_id": f"nd_{a.get('article_id', '')}",
                "title": a.get("title", ""),
                "description": (a.get("description") or "")[:500],
                "url": a.get("link", ""),
                "pubDate": a.get("pubDate", ""),
                "source_name": a.get("source_name", ""),
                "provider": "newsdata",
                "latitude": lat,
                "longitude": lon,
            })
        return articles

    async def _fetch_newsapi(self) -> list[dict[str, Any]]:
        """Fetch from NewsAPI.org /v2/everything."""
        try:
            response = await self._client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "apiKey": settings.newsapi_api_key,
                    "q": CONFLICT_QUERY,
                    "language": "en",
                    "pageSize": 20,
                    "sortBy": "publishedAt",
                },
            )
            response.raise_for_status()
            body = response.json()
        except Exception:
            logger.warning("NewsAPI fetch failed", exc_info=True)
            return []

        articles: list[dict[str, Any]] = []
        for a in body.get("articles", []):
            title = a.get("title", "")
            desc = a.get("description") or ""
            lat, lon = _geocode_text(f"{title} {desc}")
            if lat is None:
                continue
            articles.append({
                "article_id": f"na_{hashlib.md5(a.get('url', '').encode()).hexdigest()[:16]}",
                "title": title,
                "description": desc[:500],
                "url": a.get("url", ""),
                "pubDate": a.get("publishedAt", ""),
                "source_name": a.get("source", {}).get("name", ""),
                "provider": "newsapi",
                "latitude": lat,
                "longitude": lon,
            })
        return articles

    async def _fetch_gnews(self) -> list[dict[str, Any]]:
        """Fetch from GNews.io /api/v4/search."""
        try:
            response = await self._client.get(
                "https://gnews.io/api/v4/search",
                params={
                    "apikey": settings.gnews_api_key,
                    "q": CONFLICT_QUERY,
                    "lang": "en",
                    "max": 10,
                },
            )
            response.raise_for_status()
            body = response.json()
        except Exception:
            logger.warning("GNews fetch failed", exc_info=True)
            return []

        articles: list[dict[str, Any]] = []
        for a in body.get("articles", []):
            title = a.get("title", "")
            desc = a.get("description") or ""
            lat, lon = _geocode_text(f"{title} {desc}")
            if lat is None:
                continue
            articles.append({
                "article_id": f"gn_{a.get('id', hashlib.md5(a.get('url', '').encode()).hexdigest()[:16])}",
                "title": title,
                "description": desc[:500],
                "url": a.get("url", ""),
                "pubDate": a.get("publishedAt", ""),
                "source_name": a.get("source", {}).get("name", "") if isinstance(a.get("source"), dict) else str(a.get("source", "")),
                "provider": "gnews",
                "latitude": lat,
                "longitude": lon,
            })
        return articles

    def build_dedup_hash(self, article: dict[str, Any]) -> str:
        """Compute deduplication hash for a news article.

        Args:
            article: Parsed article dict with 'article_id' key.

        Returns:
            SHA-256 hex string.
        """
        key = f"news:{article['article_id']}"
        return hashlib.sha256(key.encode()).hexdigest()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def _geocode_countries(countries: list | None) -> tuple[float | None, float | None]:
    """Geocode from a list of country names.

    Args:
        countries: List of country name strings.

    Returns:
        (lat, lon) of first matching centroid, or (None, None).
    """
    if not countries or not isinstance(countries, list):
        return None, None
    for country in countries:
        coords = COUNTRY_CENTROIDS.get(country.lower().strip())
        if coords:
            return coords
    return None, None


def _geocode_text(text: str) -> tuple[float | None, float | None]:
    """Geocode by scanning text for city/country names.

    Uses GeoNames city-level geocoding first (33k+ cities), falls back
    to country centroids if no city match.

    Args:
        text: Article title + description.

    Returns:
        (lat, lon) or (None, None).
    """
    # Try city-level geocoding via GeoNames reference data
    from app.services.reference_data import geocode_text as geo_city
    lat, lon, _ = geo_city(text)
    if lat is not None:
        return lat, lon

    # Fall back to country centroids
    text_lower = text.lower()
    for country, coords in COUNTRY_CENTROIDS.items():
        if country in text_lower:
            return coords
    return None, None
