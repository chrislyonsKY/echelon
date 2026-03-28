"""
Multi-source OSINT scraper service.

Monitors open-source intelligence feeds for conflict-related keywords and
creates geolocated signal events. Sources include:

1. RSS/Atom feeds from conflict-focused outlets (Bellingcat, Crisis Group, etc.)
2. Telegram public channel preview pages (no API key needed)
3. Reddit JSON API (conflict/OSINT subreddits)
4. UN OCHA ReliefWeb API (structured, geolocated humanitarian reports)
5. Clearnet dark web aggregators (ransomware trackers, mirrors — never .onion)

All sources are free and require no API keys. Each source fails independently;
a single unreachable feed never crashes the full scrape cycle.
"""
import asyncio
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import Any

import httpx

from app.services.reference_data import geocode_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFLICT_KEYWORDS: list[str] = [
    "airstrike", "missile", "shelling", "military convoy", "troop movement",
    "naval deployment", "drone strike", "ceasefire violation", "ammunition depot",
    "air defense", "fighter jet", "warship", "submarine", "nuclear", "sanctions",
    "weapons transfer", "casualties", "evacuation", "martial law", "coup",
    "military", "defense", "defence", "armed forces", "army", "navy",
    "brigade", "artillery", "munition", "infantry", "air force",
    "war", "weapons", "battle",
]

# Pre-compiled regex for fast keyword matching (case-insensitive)
_KEYWORD_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in CONFLICT_KEYWORDS),
    re.IGNORECASE,
)

RSS_FEEDS: dict[str, str] = {
    "Bellingcat": "https://www.bellingcat.com/feed/",
    "Crisis Group": "https://www.crisisgroup.org/rss.xml",
    "War on the Rocks": "https://warontherocks.com/feed/",
    "Defense One": "https://www.defenseone.com/rss/all/",
    "The War Zone": "https://www.twz.com/feed",
}

HTML_SOURCES: dict[str, str] = {
    "RUSI": "https://www.rusi.org/news-and-comment",
    "Janes": "https://www.janes.com/defence-news",
    "PressTV": "https://www.presstv.ir/Default/",
}

REUTERS_SITEMAP_INDEX_URL = "https://www.reuters.com/arc/outboundfeeds/news-sitemap-index/?outputType=xml"
REUTERS_SITEMAP_FALLBACK_URL = "https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml"
REUTERS_WORLD_PATH_FRAGMENT = "/world/"

TELEGRAM_CHANNELS: list[str] = [
    "rybar_en",
    "intelooperX",
    "TheIntelligenceWorker",
    "ukabordfro",
]

REDDIT_SUBREDDITS: list[str] = [
    "OSINT",
    "UkraineConflict",
    "geopolitics",
    "CredibleDefense",
    "iran",
]
PULLPUSH_SUBMISSION_URL = "https://api.pullpush.io/reddit/search/submission/"
OLD_REDDIT_SUBREDDIT_URL = "https://old.reddit.com/r/{subreddit}/new/"
REDDIT_LOOKBACK_DAYS = 7

RELIEFWEB_URL: str = (
    "https://api.reliefweb.int/v1/reports"
    "?appname=echelon"
    "&limit=20"
    "&filter[field]=primary_country"
    "&filter[operator]=OR"
    "&preset=latest"
    "&fields[include][]=title"
    "&fields[include][]=url"
    "&fields[include][]=date.created"
    "&fields[include][]=primary_country.name"
    "&fields[include][]=source.name"
)

# Clearnet aggregators that mirror/track dark web activity.
# NEVER connect to .onion addresses — these are all regular HTTPS URLs.
CLEARNET_AGGREGATORS: dict[str, str] = {
    "RansomWatch": "https://raw.githubusercontent.com/joshhighet/ransomwatch/main/posts.json",
    "DarkFeed": "https://darkfeed.io/api/latest",
}

_USER_AGENT: str = "Echelon OSINT Monitor (research)"
_REQUEST_TIMEOUT: float = 30.0

# Structured, no-auth context feeds. These are ingested as contextual
# natural-hazard signals so the broader scoring layer can decide how to use
# them without this scraper owning the weighting policy.
GDACS_RSS_URL: str = "https://www.gdacs.org/contentdata/xml/rss_7d.xml"
USGS_EARTHQUAKE_FEED_URL: str = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
)
EONET_EVENTS_URL: str = (
    "https://eonet.gsfc.nasa.gov/api/v3/events/geojson"
    "?status=open&days=14&limit=100"
)
IRANWARLIVE_FEED_URL: str = "https://iranwarlive.com/feed.json"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class OSINTScraperService:
    """Multi-source OSINT scraper for conflict-related signal detection.

    Fetches from RSS feeds, Telegram public previews, Reddit, ReliefWeb,
    and clearnet dark-web aggregators. Each source is independent — a
    failure in one never blocks the others.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    async def scrape_all_sources(self) -> list[dict[str, Any]]:
        """Run all individual scrapers and merge results.

        Returns:
            Combined list of normalized signal dicts from every source.
        """
        scrapers = [
            ("RSS feeds", self.scrape_rss_feeds),
            ("HTML sources", self.scrape_html_sources),
            ("Reuters", self.scrape_reuters),
            ("Telegram channels", self.scrape_telegram_channels),
            ("Reddit", self.scrape_reddit),
            ("ReliefWeb", self.scrape_reliefweb),
            ("Clearnet aggregators", self.scrape_onion_aggregators),
            ("YouTube", self.scrape_youtube),
            ("Mastodon", self.scrape_mastodon),
            ("Bluesky", self.scrape_bluesky),
            ("Nitter/X", self.scrape_nitter),
            ("GDACS", self.scrape_gdacs),
            ("USGS earthquakes", self.scrape_usgs_earthquakes),
            ("NASA EONET", self.scrape_eonet),
            ("IranWarLive", self.scrape_iranwarlive),
        ]

        all_items: list[dict[str, Any]] = []
        results = await asyncio.gather(
            *(scraper() for _, scraper in scrapers),
            return_exceptions=True,
        )

        for (name, _), result in zip(scrapers, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("OSINT %s: scraper failed", name, exc_info=result)
                continue

            items = result
            try:
                all_items.extend(items)
                logger.info("OSINT %s: collected %d items", name, len(items))
            except Exception:
                logger.warning("OSINT %s: result handling failed", name, exc_info=True)

        logger.info("OSINT scrape complete: %d total items", len(all_items))
        return all_items

    # ------------------------------------------------------------------
    # RSS / Atom feeds
    # ------------------------------------------------------------------

    async def scrape_rss_feeds(self) -> list[dict[str, Any]]:
        """Fetch and parse RSS/Atom feeds from conflict-focused outlets.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        results: list[dict[str, Any]] = []

        for feed_name, feed_url in RSS_FEEDS.items():
            try:
                response = await self._client.get(feed_url)
                response.raise_for_status()
                items = _parse_rss_xml(response.text, feed_name)
                results.extend(items)
            except Exception:
                logger.warning("OSINT RSS: failed to fetch %s (%s)", feed_name, feed_url, exc_info=True)

        return results

    async def scrape_html_sources(self) -> list[dict[str, Any]]:
        """Fetch and parse public HTML listing pages where RSS is unavailable."""
        results: list[dict[str, Any]] = []

        for source_name, source_url in HTML_SOURCES.items():
            try:
                response = await self._client.get(source_url)
                response.raise_for_status()

                if source_name == "RUSI":
                    items = _parse_rusi_html(response.text)
                elif source_name == "Janes":
                    items = _parse_janes_html(response.text)
                elif source_name == "PressTV":
                    items = _parse_presstv_html(response.text)
                else:
                    items = []

                results.extend(items)
            except Exception:
                logger.warning(
                    "OSINT HTML: failed to fetch %s (%s)",
                    source_name,
                    source_url,
                    exc_info=True,
                )

        return results

    async def scrape_reuters(self) -> list[dict[str, Any]]:
        """Fetch Reuters World headlines from Reuters' outbound news sitemap."""
        sitemap_urls: list[str] = []

        try:
            response = await self._client.get(REUTERS_SITEMAP_INDEX_URL)
            response.raise_for_status()
            sitemap_urls = _parse_sitemap_index_xml(response.text)
        except Exception:
            logger.warning("OSINT Reuters: failed to fetch sitemap index", exc_info=True)

        if not sitemap_urls:
            sitemap_urls = [REUTERS_SITEMAP_FALLBACK_URL]

        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for sitemap_url in sitemap_urls[:2]:
            try:
                response = await self._client.get(sitemap_url)
                response.raise_for_status()
                items = _parse_reuters_sitemap_xml(response.text)
                for item in items:
                    url = str(item.get("url", ""))
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append(item)
            except Exception:
                logger.warning("OSINT Reuters: failed to fetch sitemap %s", sitemap_url, exc_info=True)

        return results

    # ------------------------------------------------------------------
    # Telegram public preview pages
    # ------------------------------------------------------------------

    async def scrape_telegram_channels(self) -> list[dict[str, Any]]:
        """Fetch posts from Telegram public channel preview pages.

        Uses the t.me/s/{channel} public HTML preview — no Telegram API
        key is required.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        results: list[dict[str, Any]] = []

        for channel in TELEGRAM_CHANNELS:
            url = f"https://t.me/s/{channel}"
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                items = _parse_telegram_html(response.text, channel)
                results.extend(items)
            except Exception:
                logger.warning(
                    "OSINT Telegram: failed to fetch channel %s", channel, exc_info=True
                )

        return results

    # ------------------------------------------------------------------
    # Reddit
    # ------------------------------------------------------------------

    async def scrape_reddit(self) -> list[dict[str, Any]]:
        """Fetch recent posts from conflict-related subreddits.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        results_by_url: dict[str, dict[str, Any]] = {}

        for subreddit in REDDIT_SUBREDDITS:
            url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=25"
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                body = response.json()
                items = _parse_reddit_json(body, subreddit)
                for item in items:
                    item_url = str(item.get("url", ""))
                    if item_url and item_url not in results_by_url:
                        results_by_url[item_url] = item
            except Exception:
                logger.warning(
                    "OSINT Reddit: failed to fetch r/%s", subreddit, exc_info=True
                )

            try:
                unofficial_items = await self.scrape_reddit_unofficial(subreddit)
                for item in unofficial_items:
                    item_url = str(item.get("url", ""))
                    if item_url and item_url not in results_by_url:
                        results_by_url[item_url] = item
            except Exception:
                logger.warning(
                    "OSINT Reddit unofficial: failed to fetch r/%s", subreddit, exc_info=True
                )

            try:
                old_items = await self.scrape_reddit_old(subreddit)
                for item in old_items:
                    item_url = str(item.get("url", ""))
                    if item_url and item_url not in results_by_url:
                        results_by_url[item_url] = item
            except Exception:
                logger.warning(
                    "OSINT Reddit old.reddit: failed to fetch r/%s", subreddit, exc_info=True
                )

        return list(results_by_url.values())

    async def scrape_reddit_unofficial(self, subreddit: str) -> list[dict[str, Any]]:
        """Fetch recent subreddit posts via PullPush without Reddit auth."""
        after_ts = int((datetime.now(UTC) - timedelta(days=REDDIT_LOOKBACK_DAYS)).timestamp())
        params = {
            "subreddit": subreddit,
            "size": "25",
            "sort": "desc",
            "sort_type": "created_utc",
            "after": str(after_ts),
        }

        response = await self._client.get(PULLPUSH_SUBMISSION_URL, params=params)
        response.raise_for_status()
        body = response.json()
        return _parse_pullpush_json(body, subreddit)

    async def scrape_reddit_old(self, subreddit: str) -> list[dict[str, Any]]:
        """Fetch subreddit posts from old.reddit as a tertiary fallback."""
        url = OLD_REDDIT_SUBREDDIT_URL.format(subreddit=subreddit)
        response = await self._client.get(url)
        response.raise_for_status()
        return _parse_old_reddit_html(response.text, subreddit)

    async def scrape_iranwarlive(self) -> list[dict[str, Any]]:
        """Fetch the structured IranWarLive machine feed."""
        try:
            response = await self._client.get(IRANWARLIVE_FEED_URL)
            response.raise_for_status()
            body = response.json()
            return _parse_iranwarlive_json(body)
        except Exception:
            logger.warning("OSINT IranWarLive: fetch failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # ReliefWeb (UN OCHA)
    # ------------------------------------------------------------------

    async def scrape_reliefweb(self) -> list[dict[str, Any]]:
        """Fetch latest humanitarian reports from the ReliefWeb API.

        ReliefWeb provides structured, geolocated data with country-level
        tagging. Free and open — no API key required.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        try:
            response = await self._client.get(RELIEFWEB_URL)
            response.raise_for_status()
            body = response.json()
            return _parse_reliefweb_json(body)
        except Exception:
            logger.warning("OSINT ReliefWeb: fetch failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Clearnet dark-web aggregators
    # ------------------------------------------------------------------

    async def scrape_onion_aggregators(self) -> list[dict[str, Any]]:
        """Scrape CLEARNET aggregator sites that republish dark web content.

        NEVER connects to .onion addresses. Only fetches from regular HTTPS
        URLs that track or mirror dark web activity (e.g., ransomware post
        trackers, dark.fail mirrors).

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        results: list[dict[str, Any]] = []

        # RansomWatch — GitHub-hosted JSON of ransomware group posts
        try:
            response = await self._client.get(CLEARNET_AGGREGATORS["RansomWatch"])
            response.raise_for_status()
            posts = response.json()
            items = _parse_ransomwatch_json(posts)
            results.extend(items)
        except Exception:
            logger.warning("OSINT RansomWatch: fetch failed", exc_info=True)

        # DarkFeed — may be unreliable or rate-limited
        try:
            response = await self._client.get(CLEARNET_AGGREGATORS["DarkFeed"])
            response.raise_for_status()
            body = response.json()
            items = _parse_darkfeed_json(body)
            results.extend(items)
        except Exception:
            logger.warning(
                "OSINT DarkFeed: fetch failed (source may be unreliable)",
                exc_info=True,
            )

        return results

    # ------------------------------------------------------------------
    # YouTube (Data API v3)
    # ------------------------------------------------------------------

    async def scrape_youtube(self) -> list[dict[str, Any]]:
        """Fetch recent conflict-related videos from YouTube Data API v3.

        Requires ``settings.youtube_api_key`` to be set. If the key is
        empty or missing, the scraper is silently skipped.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        try:
            from app.config import settings
            api_key = getattr(settings, "youtube_api_key", "") or ""
            if not api_key:
                logger.info("OSINT YouTube: no API key configured, skipping")
                return []

            results: list[dict[str, Any]] = []
            query = "military conflict OR airstrike OR missile strike"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "date",
                "maxResults": 10,
                "relevanceLanguage": "en",
                "key": api_key,
            }

            response = await self._client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params,
            )
            response.raise_for_status()
            body = response.json()

            for item in body.get("items", []):
                snippet = item.get("snippet", {})
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                combined = f"{title} {description}"

                if not _contains_conflict_keywords(combined):
                    continue

                video_id = item.get("id", {}).get("videoId", "")
                url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                published_at = snippet.get("publishedAt", "")

                lat, lon = _geocode_item(combined)
                results.append(_normalize_item(
                    source="youtube",
                    title=title[:200],
                    description=description[:500],
                    url=url,
                    published_at=published_at,
                    latitude=lat,
                    longitude=lon,
                ))

            return results
        except Exception:
            logger.warning("OSINT YouTube: scraper failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Mastodon (public timeline tag search)
    # ------------------------------------------------------------------

    async def scrape_mastodon(self) -> list[dict[str, Any]]:
        """Fetch conflict-related toots from public Mastodon timelines.

        Searches public tag timelines on mastodon.social — no API key
        required.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        try:
            results: list[dict[str, Any]] = []
            tags = ["osint", "geoint", "ukraine", "conflict"]

            for tag in tags:
                try:
                    url = f"https://mastodon.social/api/v1/timelines/tag/{tag}?limit=20"
                    response = await self._client.get(url)
                    response.raise_for_status()
                    toots = response.json()

                    for toot in toots:
                        raw_content = toot.get("content", "")
                        text = _strip_html(raw_content)

                        if not _contains_conflict_keywords(text):
                            continue

                        toot_url = toot.get("url", "")
                        created_at = toot.get("created_at", "")

                        lat, lon = _geocode_item(text)
                        results.append(_normalize_item(
                            source="mastodon",
                            title=text[:80],
                            description=text[:500],
                            url=toot_url,
                            published_at=created_at,
                            latitude=lat,
                            longitude=lon,
                        ))
                except Exception:
                    logger.warning(
                        "OSINT Mastodon: failed to fetch tag #%s", tag, exc_info=True
                    )

            return results
        except Exception:
            logger.warning("OSINT Mastodon: scraper failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Bluesky (public search API)
    # ------------------------------------------------------------------

    async def scrape_bluesky(self) -> list[dict[str, Any]]:
        """Fetch conflict-related posts from Bluesky public search API.

        Uses the unauthenticated public search endpoint — no credentials
        required.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        try:
            results: list[dict[str, Any]] = []
            query = "military conflict OR airstrike OR missile"

            response = await self._client.get(
                "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
                params={"q": query, "limit": 20},
            )
            response.raise_for_status()
            body = response.json()

            for post_wrapper in body.get("posts", []):
                record = post_wrapper.get("record", {})
                text = record.get("text", "")

                if not _contains_conflict_keywords(text):
                    continue

                # Construct profile URL from AT URI
                # URI format: at://did:plc:xxx/app.bsky.feed.post/yyy
                uri = post_wrapper.get("uri", "")
                author_handle = post_wrapper.get("author", {}).get("handle", "")
                rkey = uri.rsplit("/", 1)[-1] if "/" in uri else ""
                post_url = (
                    f"https://bsky.app/profile/{author_handle}/post/{rkey}"
                    if author_handle and rkey
                    else ""
                )

                created_at = record.get("createdAt", "")

                lat, lon = _geocode_item(text)
                results.append(_normalize_item(
                    source="bluesky",
                    title=text[:80],
                    description=text[:500],
                    url=post_url,
                    published_at=created_at,
                    latitude=lat,
                    longitude=lon,
                ))

            return results
        except Exception:
            logger.warning("OSINT Bluesky: scraper failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Nitter (X/Twitter public mirrors)
    # ------------------------------------------------------------------

    NITTER_INSTANCES: list[str] = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
    ]

    async def scrape_nitter(self) -> list[dict[str, Any]]:
        """Scrape public Nitter instances for conflict-related X/Twitter posts.

        Tries multiple Nitter instances in order. If all instances are
        unreachable (common — Nitter mirrors are notoriously unreliable),
        logs a warning and returns an empty list.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        try:
            query = "military+conflict+OR+airstrike+OR+missile"
            html = None
            used_instance = ""

            for instance in self.NITTER_INSTANCES:
                try:
                    url = f"{instance}/search?q={query}&f=tweets"
                    response = await self._client.get(url)
                    response.raise_for_status()
                    html = response.text
                    used_instance = instance
                    break
                except Exception:
                    logger.warning(
                        "OSINT Nitter: instance %s unreachable", instance, exc_info=True
                    )

            if html is None:
                logger.warning("OSINT Nitter: all instances failed, skipping")
                return []

            results: list[dict[str, Any]] = []

            # Nitter tweet blocks contain class="tweet-content" for text
            # and class="tweet-date" with <a> containing title attr for timestamps
            tweet_texts = re.findall(
                r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>',
                html,
                re.DOTALL,
            )
            tweet_dates = re.findall(
                r'<span class="tweet-date"[^>]*>\s*<a[^>]*title="([^"]*)"',
                html,
            )
            tweet_links = re.findall(
                r'<a class="tweet-link"[^>]*href="([^"]*)"',
                html,
            )

            for idx, raw_text in enumerate(tweet_texts):
                text = _strip_html(raw_text)

                if not _contains_conflict_keywords(text):
                    continue

                published_at = tweet_dates[idx] if idx < len(tweet_dates) else ""
                relative_link = tweet_links[idx] if idx < len(tweet_links) else ""
                tweet_url = (
                    f"{used_instance}{relative_link}" if relative_link else ""
                )

                lat, lon = _geocode_item(text)
                results.append(_normalize_item(
                    source="nitter_x",
                    title=text[:80],
                    description=text[:500],
                    url=tweet_url,
                    published_at=published_at,
                    latitude=lat,
                    longitude=lon,
                ))

            return results
        except Exception:
            logger.warning("OSINT Nitter: scraper failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # GDACS RSS (structured disaster context)
    # ------------------------------------------------------------------

    async def scrape_gdacs(self) -> list[dict[str, Any]]:
        """Fetch recent GDACS disaster alerts from the public RSS feed.

        GDACS is a high-signal geospatial context source for sudden-onset
        disasters. These items are stored as contextual natural-hazard
        signals.

        Returns:
            List of normalized signal dicts with explicit coordinates.
        """
        try:
            response = await self._client.get(GDACS_RSS_URL)
            response.raise_for_status()
            return _parse_gdacs_rss(response.text)
        except Exception:
            logger.warning("OSINT GDACS: fetch failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # USGS Earthquake GeoJSON (structured disaster context)
    # ------------------------------------------------------------------

    async def scrape_usgs_earthquakes(self) -> list[dict[str, Any]]:
        """Fetch significant recent earthquakes from the USGS GeoJSON feed.

        Returns:
            List of normalized natural-hazard context signals.
        """
        try:
            response = await self._client.get(USGS_EARTHQUAKE_FEED_URL)
            response.raise_for_status()
            return _parse_usgs_geojson(response.json())
        except Exception:
            logger.warning("OSINT USGS: fetch failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # NASA EONET GeoJSON (structured disaster context)
    # ------------------------------------------------------------------

    async def scrape_eonet(self) -> list[dict[str, Any]]:
        """Fetch recent open natural events from NASA EONET.

        Returns:
            List of normalized natural-hazard context signals.
        """
        try:
            response = await self._client.get(EONET_EVENTS_URL)
            response.raise_for_status()
            return _parse_eonet_geojson(response.json())
        except Exception:
            logger.warning("OSINT EONET: fetch failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def build_dedup_hash(self, item: dict[str, Any]) -> str:
        """Compute SHA-256 deduplication hash for a scraped OSINT item.

        Hash format: ``osint_scrape:{source}:{url_or_id}``

        Args:
            item: Normalized signal dict with ``source`` and ``url`` keys.

        Returns:
            SHA-256 hex digest string.
        """
        source = item.get("source", "unknown")
        url_or_id = item.get("url", "") or item.get("source_id", "")
        key = f"osint_scrape:{source}:{url_or_id}"
        return hashlib.sha256(key.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Parsers (module-level helpers)
# ---------------------------------------------------------------------------

def _contains_conflict_keywords(text: str) -> bool:
    """Check whether *text* contains any conflict keyword.

    Args:
        text: Combined title + description string to scan.

    Returns:
        True if at least one keyword matches.
    """
    return bool(_KEYWORD_PATTERN.search(text))


def _geocode_item(text: str) -> tuple[float | None, float | None]:
    """Geocode an item by scanning text for country/city names.

    Args:
        text: Combined title + description to scan for place names.

    Returns:
        (latitude, longitude) or (None, None) if no location found.
    """
    lat, lon, _ = geocode_text(text)
    return lat, lon


def _normalize_item(
    *,
    source: str,
    title: str,
    description: str,
    url: str,
    published_at: str,
    latitude: float | None,
    longitude: float | None,
    source_group: str = "osint_scrape",
    signal_type: str = "osint_scrape",
    source_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized signal dict.

    Args:
        source: Source identifier (e.g. ``rss_bellingcat``, ``telegram_rybar_en``).
        title: Item headline.
        description: Summary or body excerpt.
        url: Canonical URL of the item.
        published_at: ISO-8601-ish publication timestamp string.
        latitude: WGS-84 latitude or None.
        longitude: WGS-84 longitude or None.
        source_group: High-level source family stored in the signals table.
        signal_type: Normalized signal type used for convergence weighting.
        source_id: Stable source-native identifier.
        metadata: Optional source-specific structured metadata.

    Returns:
        Dict with standardized keys.
    """
    return {
        "source": source,
        "source_group": source_group,
        "signal_type": signal_type,
        "title": title,
        "description": description,
        "url": url,
        "published_at": published_at,
        "latitude": latitude,
        "longitude": longitude,
        "source_id": source_id,
        "metadata": metadata or {},
    }


# ------------------------------------------------------------------
# RSS / Atom XML parser
# ------------------------------------------------------------------

# Common XML namespaces in Atom/RSS feeds
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_GEORSS_NS = "{http://www.georss.org/georss}"
_GEO_NS = "{http://www.w3.org/2003/01/geo/wgs84_pos#}"
_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_NEWS_NS = "{http://www.google.com/schemas/sitemap-news/0.9}"
_IMAGE_NS = "{http://www.google.com/schemas/sitemap-image/1.1}"

def _parse_rss_xml(xml_text: str, feed_name: str) -> list[dict[str, Any]]:
    """Parse an RSS 2.0 or Atom feed and filter for conflict keywords.

    Args:
        xml_text: Raw XML string from feed response.
        feed_name: Human-readable feed name for source labelling.

    Returns:
        List of normalized signal dicts.
    """
    items: list[dict[str, Any]] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("OSINT RSS: XML parse error for %s", feed_name)
        return items

    source_key = f"rss_{feed_name.lower().replace(' ', '_')}"

    # --- RSS 2.0 ---
    for item_el in root.iter("item"):
        title = _xml_text(item_el, "title")
        description = _xml_text(item_el, "description")
        link = _xml_text(item_el, "link")
        pub_date = _xml_text(item_el, "pubDate")

        combined = f"{title} {description}"
        if not _contains_conflict_keywords(combined):
            continue

        lat, lon = _geocode_item(combined)
        items.append(_normalize_item(
            source=source_key,
            title=title,
            description=description[:500],
            url=link,
            published_at=pub_date,
            latitude=lat,
            longitude=lon,
        ))

    # --- Atom ---
    for entry_el in root.iter(f"{_ATOM_NS}entry"):
        title = _xml_text(entry_el, f"{_ATOM_NS}title")
        summary = _xml_text(entry_el, f"{_ATOM_NS}summary")
        content = _xml_text(entry_el, f"{_ATOM_NS}content")
        description = summary or content
        link_el = entry_el.find(f"{_ATOM_NS}link")
        link = (link_el.get("href", "") if link_el is not None else "")
        updated = _xml_text(entry_el, f"{_ATOM_NS}updated")
        published = _xml_text(entry_el, f"{_ATOM_NS}published")

        combined = f"{title} {description}"
        if not _contains_conflict_keywords(combined):
            continue

        lat, lon = _geocode_item(combined)
        items.append(_normalize_item(
            source=source_key,
            title=title,
            description=description[:500],
            url=link,
            published_at=published or updated,
            latitude=lat,
            longitude=lon,
        ))

    return items


def _xml_text(parent: ET.Element, tag: str) -> str:
    """Safely extract text content from an XML element.

    Args:
        parent: Parent element to search within.
        tag: Tag name (optionally namespace-prefixed).

    Returns:
        Stripped text content, or empty string if not found.
    """
    el = parent.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return ""


# ------------------------------------------------------------------
# Reuters sitemap parsers
# ------------------------------------------------------------------

def _parse_sitemap_index_xml(xml_text: str) -> list[str]:
    """Parse a sitemap index into a list of sitemap URLs."""
    urls: list[str] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("OSINT Reuters: sitemap index XML parse error")
        return urls

    for sitemap_el in root.iter(f"{_SITEMAP_NS}sitemap"):
        loc = _xml_text(sitemap_el, f"{_SITEMAP_NS}loc")
        if loc:
            urls.append(loc)

    return urls


def _parse_reuters_sitemap_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parse Reuters' outbound news sitemap and keep Reuters World items."""
    items: list[dict[str, Any]] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("OSINT Reuters: sitemap XML parse error")
        return items

    for url_el in root.iter(f"{_SITEMAP_NS}url"):
        loc = _xml_text(url_el, f"{_SITEMAP_NS}loc")
        if not loc or REUTERS_WORLD_PATH_FRAGMENT not in loc:
            continue

        title = _xml_text(url_el, f"{_NEWS_NS}news/{_NEWS_NS}title")
        published_at = _xml_text(url_el, f"{_NEWS_NS}news/{_NEWS_NS}publication_date")
        keywords_text = _xml_text(url_el, f"{_NEWS_NS}news/{_NEWS_NS}keywords")
        caption = _xml_text(url_el, f"{_IMAGE_NS}image/{_IMAGE_NS}caption")

        combined = f"{title} {caption} {keywords_text}"
        if not _contains_conflict_keywords(combined):
            continue

        lat, lon = _geocode_item(combined)
        keywords = [part.strip() for part in keywords_text.split(",") if part.strip()]

        items.append(_normalize_item(
            source="reuters_world",
            source_group="reuters",
            title=title[:200],
            description=(caption or title)[:500],
            url=loc,
            published_at=published_at,
            latitude=lat,
            longitude=lon,
            metadata={
                "keywords": keywords,
                "provenance_family": "western_wire",
                "confirmation_policy": "wire_confirmed",
            },
        ))

    return items


# ------------------------------------------------------------------
# HTML listing parsers
# ------------------------------------------------------------------

_RUSI_LINK_PATTERN: re.Pattern[str] = re.compile(
    r'aria-label="(?P<title>[^"]+)"[^>]*href="(?P<url>/news-and-comment/[^"]+)"',
    re.DOTALL | re.IGNORECASE,
)
_JANES_LINK_PATTERN: re.Pattern[str] = re.compile(
    r'href="(?P<url>https://www\.janes\.com/osint-insights/defence-news/[^"]+)"',
    re.IGNORECASE,
)
_JANES_TIME_PATTERN: re.Pattern[str] = re.compile(r'<time[^>]*datetime="(?P<date>[^"]+)"', re.IGNORECASE)
_JANES_TITLE_PATTERN: re.Pattern[str] = re.compile(r"<h3[^>]*>(?P<title>.*?)</h3>", re.DOTALL | re.IGNORECASE)
_JANES_ALT_PATTERN: re.Pattern[str] = re.compile(r'<img[^>]*alt="(?P<alt>[^"]*)"', re.IGNORECASE)
_PRESSTV_LINK_PATTERN: re.Pattern[str] = re.compile(
    r'href=(?P<url>/Detail/\d{4}/\d{2}/\d{2}/\d+/[^ >]+)',
    re.IGNORECASE,
)
_PRESSTV_TITLE_PATTERN: re.Pattern[str] = re.compile(
    r'<div class=(?:normal-news-title|latest-news-title)>(?P<title>.*?)(?:<time|</div>)',
    re.DOTALL | re.IGNORECASE,
)
_PRESSTV_TIME_PATTERN: re.Pattern[str] = re.compile(
    r'<time datetime=(?P<date>[^ >]+)',
    re.IGNORECASE,
)


def _parse_rusi_html(html_text: str) -> list[dict[str, Any]]:
    """Parse RUSI's public listing page when RSS is unavailable."""
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for match in _RUSI_LINK_PATTERN.finditer(html_text):
        title = unescape(match.group("title")).strip()
        relative_url = match.group("url").strip()
        url = f"https://www.rusi.org{relative_url}" if relative_url.startswith("/") else relative_url

        if not title or url in seen_urls:
            continue
        seen_urls.add(url)

        if not _contains_conflict_keywords(title):
            continue

        lat, lon = _geocode_item(title)
        items.append(_normalize_item(
            source="html_rusi",
            title=title[:200],
            description=title[:500],
            url=url,
            published_at="",
            latitude=lat,
            longitude=lon,
        ))

    return items


def _parse_janes_html(html_text: str) -> list[dict[str, Any]]:
    """Parse Janes' public defence-news listing page."""
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for match in _JANES_LINK_PATTERN.finditer(html_text):
        url = match.group("url").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        body = html_text[match.start():match.start() + 1800]
        title = _extract_regex_group(_JANES_TITLE_PATTERN, body, "title")
        published_at = _extract_regex_group(_JANES_TIME_PATTERN, body, "date")
        description = _extract_regex_group(_JANES_ALT_PATTERN, body, "alt") or title

        title = _strip_html(unescape(title))
        description = _strip_html(unescape(description))
        combined = f"{title} {description}"

        if not _contains_conflict_keywords(combined):
            continue

        lat, lon = _geocode_item(combined)
        items.append(_normalize_item(
            source="html_janes",
            title=title[:200],
            description=description[:500],
            url=url,
            published_at=published_at,
            latitude=lat,
            longitude=lon,
        ))

    return items


def _parse_presstv_html(html_text: str) -> list[dict[str, Any]]:
    """Parse PressTV's homepage headlines as context-only source items."""
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for match in _PRESSTV_LINK_PATTERN.finditer(html_text):
        relative_url = match.group("url").strip()
        url = f"https://www.presstv.ir{relative_url}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        body = html_text[match.start():match.start() + 1400]
        title = _strip_html(unescape(_extract_regex_group(_PRESSTV_TITLE_PATTERN, body, "title")))
        published_at = _extract_regex_group(_PRESSTV_TIME_PATTERN, body, "date")
        if not title or not _contains_conflict_keywords(title):
            continue

        lat, lon = _geocode_item(title)
        items.append(_normalize_item(
            source="html_presstv",
            source_group="press_tv",
            title=title[:200],
            description=title[:500],
            url=url,
            published_at=published_at,
            latitude=lat,
            longitude=lon,
            metadata={
                "provenance_family": "iranian_state_media",
                "confirmation_policy": "context_only",
            },
        ))

    return items


def _extract_regex_group(pattern: re.Pattern[str], text: str, group: str) -> str:
    """Return one named regex group or an empty string."""
    match = pattern.search(text)
    if match is None:
        return ""
    return match.group(group).strip()


# ------------------------------------------------------------------
# Telegram HTML parser
# ------------------------------------------------------------------

# Telegram preview pages embed posts in <div class="tgme_widget_message_text">
_TG_MESSAGE_PATTERN: re.Pattern[str] = re.compile(
    r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL,
)
_TG_DATE_PATTERN: re.Pattern[str] = re.compile(
    r'<time[^>]*datetime="([^"]+)"',
)
_TG_POST_LINK_PATTERN: re.Pattern[str] = re.compile(
    r'data-post="([^"]+)"',
)
_HTML_TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    """Remove HTML tags from a string.

    Args:
        html: Raw HTML fragment.

    Returns:
        Plain text with tags stripped.
    """
    return _HTML_TAG_PATTERN.sub("", html).strip()


def _parse_telegram_html(html: str, channel: str) -> list[dict[str, Any]]:
    """Parse Telegram public preview HTML for conflict-related posts.

    Args:
        html: Raw HTML from t.me/s/{channel}.
        channel: Channel username for source labelling.

    Returns:
        List of normalized signal dicts.
    """
    items: list[dict[str, Any]] = []
    source_key = f"telegram_{channel}"

    messages = _TG_MESSAGE_PATTERN.findall(html)
    dates = _TG_DATE_PATTERN.findall(html)
    post_ids = _TG_POST_LINK_PATTERN.findall(html)

    for idx, raw_msg in enumerate(messages):
        text = _strip_html(raw_msg)
        if not _contains_conflict_keywords(text):
            continue

        pub_date = dates[idx] if idx < len(dates) else ""
        post_id = post_ids[idx] if idx < len(post_ids) else ""
        url = f"https://t.me/{post_id}" if post_id else f"https://t.me/s/{channel}"

        lat, lon = _geocode_item(text)
        items.append(_normalize_item(
            source=source_key,
            title=text[:120],
            description=text[:500],
            url=url,
            published_at=pub_date,
            latitude=lat,
            longitude=lon,
        ))

    return items


# ------------------------------------------------------------------
# Reddit parsers
# ------------------------------------------------------------------

_OLD_REDDIT_THING_PATTERN: re.Pattern[str] = re.compile(
    r'<div class="thing[^"]*"[^>]*data-permalink="(?P<permalink>/r/[^"]+/comments/[^"]+)"'
    r'[^>]*data-url="(?P<link_url>[^"]*)"[^>]*>(?P<body>.*?)</div>\s*</div>',
    re.DOTALL | re.IGNORECASE,
)
_OLD_REDDIT_TITLE_PATTERN: re.Pattern[str] = re.compile(
    r'<a class="title[^"]*"[^>]*>(?P<title>.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_OLD_REDDIT_SELFTEXT_PATTERN: re.Pattern[str] = re.compile(
    r'<div class="expando"[^>]*>.*?<div class="usertext-body[^"]*"[^>]*>(?P<selftext>.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
_OLD_REDDIT_TIME_PATTERN: re.Pattern[str] = re.compile(
    r'<time[^>]*datetime="(?P<date>[^"]+)"',
    re.IGNORECASE,
)


def _parse_old_reddit_html(html_text: str, subreddit: str) -> list[dict[str, Any]]:
    """Parse classic old.reddit listing HTML when accessible."""
    if "blocked by network security" in html_text.lower():
        return []

    items: list[dict[str, Any]] = []
    for match in _OLD_REDDIT_THING_PATTERN.finditer(html_text):
        permalink = match.group("permalink").strip()
        body = match.group("body")
        title = _strip_html(unescape(_extract_regex_group(_OLD_REDDIT_TITLE_PATTERN, body, "title")))
        selftext = _strip_html(unescape(_extract_regex_group(_OLD_REDDIT_SELFTEXT_PATTERN, body, "selftext")))
        published_at = _extract_regex_group(_OLD_REDDIT_TIME_PATTERN, body, "date")

        post = {
            "title": title,
            "selftext": selftext,
            "permalink": permalink,
            "url": match.group("link_url").strip(),
            "created_utc": published_at,
            "subreddit": subreddit,
            "author": None,
            "score": None,
            "num_comments": None,
            "link_flair_text": None,
        }
        item = _build_reddit_item(post, subreddit, provider="old_reddit_html")
        if item is not None:
            items.append(item)

    return items

def _parse_reddit_json(body: dict[str, Any], subreddit: str) -> list[dict[str, Any]]:
    """Parse Reddit JSON listing and filter for conflict keywords.

    Args:
        body: Decoded JSON from Reddit .json endpoint.
        subreddit: Subreddit name for source labelling.

    Returns:
        List of normalized signal dicts.
    """
    items: list[dict[str, Any]] = []
    source_key = f"reddit_{subreddit.lower()}"

    posts = body.get("data", {}).get("children", [])
    for post_wrapper in posts:
        post = post_wrapper.get("data", {})
        item = _build_reddit_item(post, subreddit, provider="reddit_json")
        if item is not None:
            items.append(item)

    return items


def _parse_pullpush_json(body: dict[str, Any], subreddit: str) -> list[dict[str, Any]]:
    """Parse PullPush Reddit archive results for a subreddit."""
    items: list[dict[str, Any]] = []

    for post in body.get("data", []):
        if not isinstance(post, dict):
            continue
        item = _build_reddit_item(post, subreddit, provider="pullpush")
        if item is not None:
            items.append(item)

    return items


def _build_reddit_item(
    post: dict[str, Any],
    subreddit: str,
    *,
    provider: str,
) -> dict[str, Any] | None:
    """Normalize one Reddit or PullPush post record."""
    source_key = f"reddit_{subreddit.lower()}"
    title = post.get("title", "")
    selftext = post.get("selftext", "")

    if str(post.get("subreddit", "")).lower() not in ("", subreddit.lower()):
        return None

    url_hint = str(post.get("url", "") or "")
    combined = f"{title} {selftext} {url_hint}"

    if not _contains_conflict_keywords(combined):
        return None

    permalink = str(post.get("permalink", "") or "")
    full_link = str(post.get("full_link", "") or "")
    url = full_link or (f"https://www.reddit.com{permalink}" if permalink else "")
    created_utc = post.get("created_utc") or post.get("created")
    published_at = ""
    if created_utc not in (None, ""):
        try:
            published_at = str(int(float(created_utc)))
        except (TypeError, ValueError):
            published_at = str(created_utc)

    lat, lon = _geocode_item(combined)
    return _normalize_item(
        source=source_key,
        title=str(title)[:200],
        description=str(selftext)[:500],
        url=url,
        published_at=published_at,
        latitude=lat,
        longitude=lon,
        metadata={
            "provider": provider,
            "subreddit": subreddit,
            "author": post.get("author"),
            "score": post.get("score"),
            "num_comments": post.get("num_comments"),
            "link_flair_text": post.get("link_flair_text"),
            "provenance_family": "social_unofficial",
            "confirmation_policy": "context_only",
        },
    )


# ------------------------------------------------------------------
# ReliefWeb JSON parser
# ------------------------------------------------------------------

def _parse_reliefweb_json(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse ReliefWeb API response and filter for conflict keywords.

    Args:
        body: Decoded JSON from the ReliefWeb reports endpoint.

    Returns:
        List of normalized signal dicts.
    """
    items: list[dict[str, Any]] = []

    for entry in body.get("data", []):
        fields = entry.get("fields", {})
        title = fields.get("title", "")

        if not _contains_conflict_keywords(title):
            continue

        url = fields.get("url", "")
        date_created = fields.get("date", {}).get("created", "")
        country_name = ""
        countries = fields.get("primary_country", [])
        if isinstance(countries, list) and countries:
            country_name = countries[0].get("name", "")
        elif isinstance(countries, dict):
            country_name = countries.get("name", "")

        source_name = ""
        sources = fields.get("source", [])
        if isinstance(sources, list) and sources:
            source_name = sources[0].get("name", "")

        # Geocode using country name + title
        geocode_text_combined = f"{title} {country_name}"
        lat, lon = _geocode_item(geocode_text_combined)

        items.append(_normalize_item(
            source="reliefweb",
            title=title[:200],
            description=f"Source: {source_name}. Country: {country_name}",
            url=url,
            published_at=date_created,
            latitude=lat,
            longitude=lon,
        ))

    return items


# ------------------------------------------------------------------
# IranWarLive JSON parser
# ------------------------------------------------------------------

def _parse_iranwarlive_json(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the IranWarLive machine feed into normalized signal items."""
    items: list[dict[str, Any]] = []

    for entry in body.get("items", []):
        if not isinstance(entry, dict):
            continue

        title = str(entry.get("event_summary", "") or entry.get("type", "IranWarLive event"))
        event_type = str(entry.get("type", "") or "")
        location = str(entry.get("location", "") or "")
        description = f"{event_type}. Location: {location}".strip(". ")
        published_at = str(entry.get("timestamp", "") or body.get("last_updated", ""))
        url = str(entry.get("source_url", "") or body.get("home_page_url", "https://iranwarlive.com"))

        coords = entry.get("_osint_meta", {}).get("coordinates", {})
        lat = _coerce_float(coords.get("lat"))
        lon = _coerce_float(coords.get("lng"))
        if lat is None or lon is None:
            lat, lon = _geocode_item(f"{title} {location}")

        items.append(_normalize_item(
            source="iranwarlive",
            title=title[:200],
            description=description[:500],
            url=url,
            published_at=published_at,
            latitude=lat,
            longitude=lon,
            source_group="iranwarlive",
            signal_type="osint_scrape",
            source_id=str(entry.get("event_id", "") or url or title),
            metadata={
                "event_type": event_type,
                "location": location,
                "confidence": entry.get("confidence"),
                "casualties": entry.get("_osint_meta", {}).get("casualties"),
                "provenance_family": "aggregator",
                "confirmation_policy": "aggregated_context",
            },
        ))

    return items


# ------------------------------------------------------------------
# Clearnet aggregator parsers
# ------------------------------------------------------------------

def _parse_ransomwatch_json(posts: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    """Parse RansomWatch posts JSON for conflict-related ransomware activity.

    Args:
        posts: List of post dicts from the ransomwatch GitHub repo.

    Returns:
        List of normalized signal dicts.
    """
    items: list[dict[str, Any]] = []

    if not isinstance(posts, list):
        logger.warning("OSINT RansomWatch: unexpected JSON structure")
        return items

    for post in posts:
        title = post.get("post_title", "")
        group_name = post.get("group_name", "")
        discovered = post.get("discovered", "")
        post_url = post.get("post_url", "")

        combined = f"{title} {group_name}"
        if not _contains_conflict_keywords(combined):
            continue

        lat, lon = _geocode_item(combined)
        items.append(_normalize_item(
            source="ransomwatch",
            title=f"[{group_name}] {title}"[:200],
            description=f"Ransomware group: {group_name}",
            url=post_url,
            published_at=discovered,
            latitude=lat,
            longitude=lon,
        ))

    return items


def _parse_darkfeed_json(body: dict[str, Any] | list[Any] | Any) -> list[dict[str, Any]]:
    """Parse DarkFeed API response for conflict-related dark web activity.

    Args:
        body: Decoded JSON from the DarkFeed API (structure may vary).

    Returns:
        List of normalized signal dicts.
    """
    items: list[dict[str, Any]] = []

    # DarkFeed structure varies — handle list or dict with "data" key
    entries: list[Any] = []
    if isinstance(body, list):
        entries = body
    elif isinstance(body, dict):
        entries = body.get("data", body.get("items", body.get("results", [])))
        if not isinstance(entries, list):
            logger.warning("OSINT DarkFeed: unexpected JSON structure")
            return items

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        title = entry.get("title", "") or entry.get("name", "")
        description = entry.get("description", "") or entry.get("body", "")
        url = entry.get("url", "") or entry.get("link", "")
        published = entry.get("published", "") or entry.get("date", "")

        combined = f"{title} {description}"
        if not _contains_conflict_keywords(combined):
            continue

        lat, lon = _geocode_item(combined)
        items.append(_normalize_item(
            source="darkfeed",
            title=title[:200],
            description=description[:500],
            url=url,
            published_at=published,
            latitude=lat,
            longitude=lon,
        ))

    return items


def _parse_gdacs_rss(xml_text: str) -> list[dict[str, Any]]:
    """Parse GDACS RSS items with embedded GeoRSS coordinates."""
    items: list[dict[str, Any]] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("OSINT GDACS: XML parse error")
        return items

    for item_el in root.iter("item"):
        title = _xml_text(item_el, "title")
        description = _strip_html(_xml_text(item_el, "description"))
        link = _xml_text(item_el, "link")
        pub_date = _xml_text(item_el, "pubDate")

        lat, lon = _extract_rss_point(item_el)
        if lat is None or lon is None:
            continue

        categories = [
            (cat.text or "").strip()
            for cat in item_el.findall("category")
            if cat.text
        ]

        items.append(_normalize_item(
            source="gdacs_rss",
            source_group="gdacs",
            signal_type="natural_hazard",
            source_id=link or title,
            title=title[:200],
            description=description[:500],
            url=link,
            published_at=pub_date,
            latitude=lat,
            longitude=lon,
            metadata={"categories": categories},
        ))

    return items


def _parse_usgs_geojson(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the USGS GeoJSON earthquake summary feed."""
    items: list[dict[str, Any]] = []

    for feature in body.get("features", []):
        if not isinstance(feature, dict):
            continue

        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            continue

        lon = _coerce_float(coordinates[0])
        lat = _coerce_float(coordinates[1])
        if lat is None or lon is None:
            continue

        props = feature.get("properties", {})
        mag = props.get("mag")
        place = props.get("place", "")
        title = props.get("title") or (
            f"M{mag:.1f} earthquake" if isinstance(mag, (int, float)) else "Earthquake"
        )
        published_at = _epoch_millis_to_iso(props.get("time"))
        url = props.get("url", "")

        items.append(_normalize_item(
            source="usgs_earthquakes",
            source_group="usgs",
            signal_type="natural_hazard",
            source_id=feature.get("id", "") or url or title,
            title=title[:200],
            description=str(place)[:500],
            url=url,
            published_at=published_at,
            latitude=lat,
            longitude=lon,
            metadata={
                "magnitude": mag,
                "place": place,
                "alert": props.get("alert"),
                "event_type": props.get("type"),
                "felt_reports": props.get("felt"),
                "tsunami": props.get("tsunami"),
            },
        ))

    return items


def _parse_eonet_geojson(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the NASA EONET GeoJSON events feed."""
    items: list[dict[str, Any]] = []

    for feature in body.get("features", []):
        if not isinstance(feature, dict):
            continue

        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        lat, lon = _extract_geojson_centroid(geometry)
        if lat is None or lon is None:
            continue

        categories = _extract_titles(props.get("categories", []))
        sources = _extract_titles(props.get("sources", []), key="id")
        url = props.get("link", "")
        if not url and isinstance(props.get("sources"), list) and props["sources"]:
            first_source = props["sources"][0]
            if isinstance(first_source, dict):
                url = str(first_source.get("url", ""))

        description = props.get("description") or ", ".join(categories) or "Natural event"
        published_at = (
            props.get("date")
            or props.get("closed")
            or _first_geometry_date(props.get("geometryDates"))
            or ""
        )

        items.append(_normalize_item(
            source="eonet",
            source_group="eonet",
            signal_type="natural_hazard",
            source_id=str(props.get("id") or feature.get("id") or url or props.get("title", "")),
            title=str(props.get("title", "Natural event"))[:200],
            description=str(description)[:500],
            url=url,
            published_at=str(published_at),
            latitude=lat,
            longitude=lon,
            metadata={
                "categories": categories,
                "sources": sources,
                "closed": props.get("closed"),
                "magnitude_value": props.get("magnitudeValue"),
                "magnitude_unit": props.get("magnitudeUnit"),
                "magnitude_description": props.get("magnitudeDescription"),
            },
        ))

    return items


def _extract_rss_point(item_el: ET.Element) -> tuple[float | None, float | None]:
    """Extract a point from GeoRSS or WGS84 geo RSS fields."""
    georss_point = _xml_text(item_el, f"{_GEORSS_NS}point")
    if georss_point:
        parts = georss_point.split()
        if len(parts) >= 2:
            lat = _coerce_float(parts[0])
            lon = _coerce_float(parts[1])
            if lat is not None and lon is not None:
                return lat, lon

    lat = _coerce_float(_xml_text(item_el, f"{_GEO_NS}lat"))
    lon = _coerce_float(_xml_text(item_el, f"{_GEO_NS}long"))
    return lat, lon


def _extract_geojson_centroid(geometry: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract a representative point from a GeoJSON geometry."""
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geom_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        lon = _coerce_float(coordinates[0])
        lat = _coerce_float(coordinates[1])
        return lat, lon

    points = _flatten_geojson_points(coordinates)
    if not points:
        return None, None

    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    return lat, lon


def _flatten_geojson_points(coordinates: Any) -> list[tuple[float, float]]:
    """Flatten nested GeoJSON coordinate arrays into lon/lat pairs."""
    points: list[tuple[float, float]] = []

    if not isinstance(coordinates, list):
        return points

    if len(coordinates) >= 2 and all(isinstance(value, (int, float)) for value in coordinates[:2]):
        lon = _coerce_float(coordinates[0])
        lat = _coerce_float(coordinates[1])
        if lon is not None and lat is not None:
            points.append((lon, lat))
        return points

    for child in coordinates:
        points.extend(_flatten_geojson_points(child))

    return points


def _coerce_float(value: Any) -> float | None:
    """Coerce a scalar to float, returning None on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _epoch_millis_to_iso(value: Any) -> str:
    """Convert epoch milliseconds to an ISO-8601 UTC timestamp."""
    try:
        if value is None:
            return ""
        ts = float(value) / 1000.0
        return datetime.fromtimestamp(ts, tz=UTC).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _extract_titles(entries: list[Any], key: str = "title") -> list[str]:
    """Extract a list of text labels from structured dict entries."""
    titles: list[str] = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get(key):
            titles.append(str(entry[key]))
    return titles


def _first_geometry_date(value: Any) -> str | None:
    """Return the first geometry date from an EONET geometryDates array."""
    if isinstance(value, list) and value:
        first = value[0]
        if first:
            return str(first)
    return None
