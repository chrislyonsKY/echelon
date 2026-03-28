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
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
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
]

# Pre-compiled regex for fast keyword matching (case-insensitive)
_KEYWORD_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(kw) for kw in CONFLICT_KEYWORDS),
    re.IGNORECASE,
)

RSS_FEEDS: dict[str, str] = {
    "Bellingcat": "https://www.bellingcat.com/feed/",
    "Crisis Group": "https://www.crisisgroup.org/rss.xml",
    "RUSI": "https://www.rusi.org/rss.xml",
    "War on the Rocks": "https://warontherocks.com/feed/",
    "Defense One": "https://www.defenseone.com/rss/",
    "The War Zone": "https://www.twz.com/feed",
    "Janes": "https://www.janes.com/feeds/news",
    "Reuters World": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
}

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
]

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
        all_items: list[dict[str, Any]] = []

        scrapers = [
            ("RSS feeds", self.scrape_rss_feeds),
            ("Telegram channels", self.scrape_telegram_channels),
            ("Reddit", self.scrape_reddit),
            ("ReliefWeb", self.scrape_reliefweb),
            ("Clearnet aggregators", self.scrape_onion_aggregators),
        ]

        for name, scraper in scrapers:
            try:
                items = await scraper()
                all_items.extend(items)
                logger.info("OSINT %s: collected %d items", name, len(items))
            except Exception:
                logger.warning("OSINT %s: scraper failed", name, exc_info=True)

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
    # Reddit JSON API
    # ------------------------------------------------------------------

    async def scrape_reddit(self) -> list[dict[str, Any]]:
        """Fetch recent posts from conflict-related subreddits via JSON API.

        Appends .json to subreddit new-post URLs to get structured data
        without requiring Reddit API credentials.

        Returns:
            List of normalized signal dicts filtered for conflict keywords.
        """
        results: list[dict[str, Any]] = []

        for subreddit in REDDIT_SUBREDDITS:
            url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=25"
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                body = response.json()
                items = _parse_reddit_json(body, subreddit)
                results.extend(items)
            except Exception:
                logger.warning(
                    "OSINT Reddit: failed to fetch r/%s", subreddit, exc_info=True
                )

        return results

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

    Returns:
        Dict with standardized keys.
    """
    return {
        "source": source,
        "title": title,
        "description": description,
        "url": url,
        "published_at": published_at,
        "latitude": latitude,
        "longitude": longitude,
    }


# ------------------------------------------------------------------
# RSS / Atom XML parser
# ------------------------------------------------------------------

# Common XML namespaces in Atom/RSS feeds
_ATOM_NS = "{http://www.w3.org/2005/Atom}"

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
# Reddit JSON parser
# ------------------------------------------------------------------

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
        title = post.get("title", "")
        selftext = post.get("selftext", "")
        combined = f"{title} {selftext}"

        if not _contains_conflict_keywords(combined):
            continue

        permalink = post.get("permalink", "")
        url = f"https://www.reddit.com{permalink}" if permalink else ""
        created_utc = post.get("created_utc", "")
        published_at = str(int(created_utc)) if created_utc else ""

        lat, lon = _geocode_item(combined)
        items.append(_normalize_item(
            source=source_key,
            title=title[:200],
            description=selftext[:500],
            url=url,
            published_at=published_at,
            latitude=lat,
            longitude=lon,
        ))

    return items


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
