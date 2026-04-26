"""Feed and article parsing helpers for Danish News."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha1
from html import unescape
from html.parser import HTMLParser
import json
import logging
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from .const import PROVIDERS

_LOGGER = logging.getLogger(__name__)

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
SCRIPT_JSON_TYPE = "application/ld+json"


class FeedParseError(ValueError):
    """Raised when a feed cannot be parsed."""


class PageHTMLParser(HTMLParser):
    """Small HTML parser for metadata, JSON-LD and readable paragraphs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.json_ld_scripts: list[str] = []
        self.meta: dict[str, str] = {}
        self.article_paragraphs: list[str] = []
        self.all_paragraphs: list[str] = []
        self.title = ""
        self._capture_script = False
        self._script_chunks: list[str] = []
        self._article_depth = 0
        self._capture_text_tag: str | None = None
        self._text_chunks: list[str] = []
        self._capture_title = False
        self._title_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name.lower(): value or "" for name, value in attrs}
        tag = tag.lower()

        if tag == "script" and SCRIPT_JSON_TYPE in attrs_dict.get("type", "").lower():
            self._capture_script = True
            self._script_chunks = []
            return

        if tag == "meta":
            key = attrs_dict.get("property") or attrs_dict.get("name")
            content = attrs_dict.get("content")
            if key and content:
                self.meta[key.lower()] = clean_text(content)
            return

        if tag == "title":
            self._capture_title = True
            self._title_chunks = []
            return

        if tag in {"article", "main"}:
            self._article_depth += 1

        if tag in {"p", "h2", "li"}:
            self._capture_text_tag = tag
            self._text_chunks = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag == "script" and self._capture_script:
            self._capture_script = False
            script = "".join(self._script_chunks).strip()
            if script:
                self.json_ld_scripts.append(script)
            self._script_chunks = []
            return

        if tag == "title" and self._capture_title:
            self._capture_title = False
            self.title = clean_text(" ".join(self._title_chunks))
            self._title_chunks = []
            return

        if tag == self._capture_text_tag:
            text = clean_text(" ".join(self._text_chunks))
            if is_useful_paragraph(text):
                self.all_paragraphs.append(text)
                if self._article_depth > 0:
                    self.article_paragraphs.append(text)
            self._capture_text_tag = None
            self._text_chunks = []

        if tag in {"article", "main"} and self._article_depth:
            self._article_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_script:
            self._script_chunks.append(data)
        if self._capture_title:
            self._title_chunks.append(data)
        if self._capture_text_tag:
            self._text_chunks.append(data)


def parse_feed(
    provider_key: str,
    xml_text: str,
    now: datetime,
) -> list[dict[str, Any]]:
    """Parse RSS or Atom into compact article dictionaries."""

    provider = PROVIDERS[provider_key]
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as err:
        raise FeedParseError(str(err)) from err

    nodes = list(root.findall(".//item"))
    if not nodes:
        nodes = [node for node in root.iter() if local_name(node.tag) == "entry"]

    articles: list[dict[str, Any]] = []
    for item in nodes:
        title = clean_text(child_text(item, "title"))
        url = child_link(item)
        if not title or not url:
            continue

        published_dt = parse_datetime(
            first_text(item, ["pubDate", "published", "updated", "dc:date"])
        )
        summary = clean_text(
            first_text(item, ["description", "summary", "encoded", "content"])
        )
        category = clean_text(first_text(item, ["category"]))
        image = child_image(item)

        article = make_article(
            provider_key=provider_key,
            provider_name=provider["name"],
            title=title,
            url=url,
            summary=summary,
            published_dt=published_dt,
            category=category,
            image=image,
        )
        if not is_paywalled_candidate(provider_key, article):
            articles.append(article)

    return articles


def parse_tv2_frontpage(provider_key: str, html_text: str, now: datetime) -> list[dict[str, Any]]:
    """Parse TV 2 frontpage JSON-LD when the RSS host is unavailable."""

    provider = PROVIDERS[provider_key]
    parser = PageHTMLParser()
    parser.feed(html_text)

    articles: list[dict[str, Any]] = []
    for data in json_ld_objects(parser.json_ld_scripts):
        if "collectionpage" not in json_types(data):
            continue

        main = data.get("mainEntity")
        if not isinstance(main, dict):
            continue
        elements = main.get("itemListElement")
        if not isinstance(elements, list):
            continue

        for element in elements:
            if not isinstance(element, dict):
                continue
            item = element.get("item")
            url = element.get("url") or (item.get("@id") if isinstance(item, dict) else "")
            title = element.get("name")
            if not isinstance(url, str) or not isinstance(title, str):
                continue
            article = make_article(
                provider_key=provider_key,
                provider_name=provider["name"],
                title=title,
                url=url,
                summary="",
                published_dt=now,
                category="",
                image="",
            )
            if not is_paywalled_candidate(provider_key, article):
                articles.append(article)

    return articles


def extract_article_from_html(
    provider_key: str,
    html_text: str,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract a readable article view from a provider page."""

    fallback = fallback or {}
    parser = PageHTMLParser()
    parser.feed(html_text)

    article_data = first_article_json_ld(parser.json_ld_scripts)
    headline = string_or_empty(article_data.get("headline")) or fallback.get("title") or parser.title
    description = (
        string_or_empty(article_data.get("description"))
        or parser.meta.get("og:description")
        or parser.meta.get("description")
        or fallback.get("summary")
        or ""
    )
    image = (
        image_from_json_ld(article_data.get("image"))
        or parser.meta.get("og:image")
        or fallback.get("image")
        or ""
    )
    published_dt = parse_datetime(
        string_or_empty(article_data.get("datePublished"))
        or parser.meta.get("article:published_time")
        or fallback.get("published")
        or ""
    )
    byline = byline_from_json_ld(article_data.get("author"))
    url = fallback.get("url") or parser.meta.get("og:url") or ""

    body = string_or_empty(article_data.get("articleBody"))
    paragraphs = split_article_body(body)
    if not paragraphs:
        paragraphs = unique_texts(parser.article_paragraphs or parser.all_paragraphs)

    paragraphs = filter_article_paragraphs(paragraphs, headline)
    if not paragraphs and description:
        paragraphs = [description]

    result = {
        "id": fallback.get("id") or article_id(provider_key, url or headline),
        "provider": provider_key,
        "provider_name": PROVIDERS[provider_key]["name"],
        "title": clean_text(headline),
        "summary": clean_text(description),
        "url": url,
        "image": image,
        "published": published_dt.isoformat() if published_dt else fallback.get("published", ""),
        "byline": byline,
        "body": paragraphs[:48],
        "paywalled": is_paywalled_article(provider_key, html_text, fallback, article_data),
    }

    if result["paywalled"]:
        result["body"] = []

    return result


def make_article(
    *,
    provider_key: str,
    provider_name: str,
    title: str,
    url: str,
    summary: str,
    published_dt: datetime | None,
    category: str,
    image: str,
) -> dict[str, Any]:
    """Build a compact article dictionary used by the sensor and card."""

    canonical = canonical_url(url)
    timestamp = published_dt.timestamp() if published_dt else 0
    return {
        "id": article_id(provider_key, canonical),
        "provider": provider_key,
        "provider_name": provider_name,
        "title": clean_text(title),
        "summary": clean_text(summary),
        "url": canonical,
        "published": published_dt.isoformat() if published_dt else "",
        "category": category,
        "image": image,
        "paywalled": False,
        "breaking": is_breaking_news(title, summary, category, canonical),
        "_sort_timestamp": timestamp,
    }


def article_id(provider_key: str, value: str) -> str:
    """Create a stable article id."""

    return sha1(f"{provider_key}:{value}".encode("utf-8")).hexdigest()[:16]


def strip_private_keys(article: dict[str, Any]) -> dict[str, Any]:
    """Remove internal keys before storing articles as entity attributes."""

    return {key: value for key, value in article.items() if not key.startswith("_")}


def canonical_url(url: str) -> str:
    """Drop query string and fragments to improve de-duplication."""

    parts = urlsplit(unescape(url.strip()))
    scheme = parts.scheme or "https"
    netloc = parts.netloc
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, "", ""))


def provider_url_allowed(provider_key: str, url: str) -> bool:
    """Return true if a URL belongs to the configured provider."""

    host = urlsplit(url).netloc.lower()
    allowed_hosts = PROVIDERS[provider_key].get("hosts", [])
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def is_today(article: dict[str, Any], now: datetime) -> bool:
    """Return true if an article was published today in Home Assistant local time."""

    published = parse_datetime(article.get("published", ""))
    if published is None:
        return True
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return published.astimezone(now.tzinfo).date() == now.date()


def sort_and_limit_articles(
    articles: Iterable[dict[str, Any]],
    max_articles: int,
) -> list[dict[str, Any]]:
    """De-duplicate, sort and strip private fields."""

    unique: dict[str, dict[str, Any]] = {}
    for article in articles:
        if article["url"] not in unique:
            unique[article["url"]] = article

    sorted_articles = sorted(
        unique.values(),
        key=lambda article: (article.get("_sort_timestamp") or 0, article.get("title", "")),
        reverse=True,
    )
    return [strip_private_keys(article) for article in sorted_articles[:max_articles]]


def is_paywalled_candidate(provider_key: str, article: dict[str, Any]) -> bool:
    """Best-effort filter for paid articles before they reach the UI."""

    text = " ".join(
        [
            article.get("title", ""),
            article.get("summary", ""),
            article.get("url", ""),
            article.get("category", ""),
        ]
    ).lower()
    url_path = urlsplit(article.get("url", "")).path.lower()

    if any(marker in url_path for marker in ["/plus", "/abonnement", "/login"]):
        return True

    if provider_key == "eb":
        return any(marker in text for marker in ["ekstra bladet+", "eb+", " eb plus", "abonnent"])

    if provider_key == "bt":
        return any(marker in text for marker in ["b.t.+", "bt+", " bt plus", "abonnent"])

    if provider_key == "tv2":
        return "play.tv2.dk" in text or "tv 2 play" in text

    return "kun for abonnenter" in text or "betalingsmur" in text


def is_breaking_news(title: str, summary: str, category: str, url: str) -> bool:
    """Return true when provider metadata marks an article as breaking/current live news."""

    text = " ".join([title, summary, category, url]).lower()
    markers = [
        "breaking",
        "breaking news",
        "lige nu",
    ]
    return any(marker in text for marker in markers)


def is_paywalled_article(
    provider_key: str,
    html_text: str,
    fallback: dict[str, Any],
    article_data: dict[str, Any],
) -> bool:
    """Detect paywalled pages without attempting to bypass them."""

    accessible = article_data.get("isAccessibleForFree")
    if isinstance(accessible, bool):
        return not accessible
    if isinstance(accessible, str) and accessible.lower() in {"false", "0", "no"}:
        return True
    if is_paywalled_candidate(provider_key, fallback):
        return True

    lowered = html_text[:300000].lower()
    strong_markers = [
        '"isaccessibleforfree":false',
        "'isaccessibleforfree':false",
        "kun for abonnenter",
        "allerede abonnent",
        "køb abonnement",
        "koeb abonnement",
    ]
    return any(marker in lowered for marker in strong_markers)


def child_text(item: ET.Element, name: str) -> str:
    """Find text from a direct child by local tag name."""

    wanted = name.split(":")[-1]
    for child in item:
        if local_name(child.tag) == wanted:
            return "".join(child.itertext())
    return ""


def first_text(item: ET.Element, names: list[str]) -> str:
    """Find the first non-empty child text from a list of tag names."""

    for name in names:
        text = child_text(item, name)
        if text:
            return text
    return ""


def child_link(item: ET.Element) -> str:
    """Find an RSS or Atom link."""

    for child in item:
        if local_name(child.tag) != "link":
            continue
        if child.text and child.text.strip():
            return canonical_url(child.text)
        href = child.attrib.get("href")
        if href:
            return canonical_url(href)

    guid = child_text(item, "guid")
    if guid.startswith("http"):
        return canonical_url(guid)
    return ""


def child_image(item: ET.Element) -> str:
    """Find a feed image URL from common RSS extensions."""

    for child in item.iter():
        name = local_name(child.tag)
        if name in {"content", "thumbnail", "enclosure"}:
            url = child.attrib.get("url")
            media_type = child.attrib.get("type", "")
            if url and (not media_type or media_type.startswith("image")):
                return canonical_url(url)
    return ""


def local_name(tag: str) -> str:
    """Return an XML tag name without namespace."""

    return tag.rsplit("}", 1)[-1].split(":")[-1]


def parse_datetime(value: str | None) -> datetime | None:
    """Parse RSS or ISO datetimes into timezone-aware datetimes."""

    if not value:
        return None

    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        parsed = None

    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def clean_text(value: Any) -> str:
    """Clean HTML and normalize whitespace."""

    if value is None:
        return ""
    text = TAG_RE.sub(" ", str(value))
    text = unescape(text)
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def is_useful_paragraph(text: str) -> bool:
    """Filter obvious navigation, ads and tiny fragments."""

    if len(text) < 35:
        return False
    lowered = text.lower()
    blocked = [
        "cookie",
        "privatlivspolitik",
        "annonc",
        "log ind",
        "nyhedsbrev",
        "copyright",
        "javascript",
    ]
    return not any(marker in lowered for marker in blocked)


def json_ld_objects(scripts: Iterable[str]) -> Iterable[dict[str, Any]]:
    """Yield dictionaries from JSON-LD script tags."""

    for script in scripts:
        try:
            data = json.loads(script)
        except json.JSONDecodeError:
            _LOGGER.debug("Could not parse JSON-LD script", exc_info=True)
            continue
        yield from iter_dicts(data)


def iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    """Recursively yield dictionaries from JSON-like data."""

    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from iter_dicts(nested)
    elif isinstance(value, list):
        for item in value:
            yield from iter_dicts(item)


def json_types(data: dict[str, Any]) -> set[str]:
    """Return lower-case JSON-LD @type values."""

    raw_type = data.get("@type")
    if isinstance(raw_type, list):
        return {str(item).lower() for item in raw_type}
    if raw_type:
        return {str(raw_type).lower()}
    return set()


def first_article_json_ld(scripts: Iterable[str]) -> dict[str, Any]:
    """Find the first NewsArticle or Article JSON-LD object."""

    for data in json_ld_objects(scripts):
        types = json_types(data)
        if {"newsarticle", "article", "reportagenewsarticle"} & types:
            return data
    return {}


def string_or_empty(value: Any) -> str:
    """Return a clean string when possible."""

    if isinstance(value, str):
        return clean_text(value)
    return ""


def image_from_json_ld(value: Any) -> str:
    """Extract image URL from common JSON-LD shapes."""

    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return image_from_json_ld(value[0])
    if isinstance(value, dict):
        url = value.get("url") or value.get("@id")
        if isinstance(url, str):
            return url
    return ""


def byline_from_json_ld(value: Any) -> str:
    """Extract author names from JSON-LD."""

    if isinstance(value, dict):
        return clean_text(value.get("name"))
    if isinstance(value, list):
        names = [byline_from_json_ld(item) for item in value]
        return ", ".join(name for name in names if name)
    if isinstance(value, str):
        return clean_text(value)
    return ""


def split_article_body(value: str) -> list[str]:
    """Split JSON-LD articleBody into display paragraphs."""

    if not value:
        return []
    candidates = re.split(r"(?:\n{2,}|(?<=[.!?])\s{2,})", value)
    return [clean_text(candidate) for candidate in candidates if is_useful_paragraph(clean_text(candidate))]


def unique_texts(values: Iterable[str]) -> list[str]:
    """Keep paragraphs in order while dropping duplicates."""

    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def filter_article_paragraphs(values: Iterable[str], headline: str) -> list[str]:
    """Remove repeated headline and source boilerplate."""

    result = []
    headline_key = clean_text(headline).lower()
    for value in unique_texts(values):
        key = value.lower()
        if headline_key and key == headline_key:
            continue
        if key.startswith("læs også") or key.startswith("se også"):
            continue
        result.append(value)
    return result
