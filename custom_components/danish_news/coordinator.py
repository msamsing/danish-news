"""Data coordinator for Danish News."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MAX_ARTICLES,
    CONF_PROVIDERS,
    CONF_REFRESH_MINUTES,
    DEFAULT_MAX_ARTICLES,
    DEFAULT_PROVIDERS,
    DEFAULT_REFRESH_MINUTES,
    DOMAIN,
    PROVIDERS,
    REQUEST_HEADERS,
)
from .feeds import (
    extract_article_from_html,
    is_today,
    parse_feed,
    parse_tv2_frontpage,
    provider_url_allowed,
    sort_and_limit_articles,
)

_LOGGER = logging.getLogger(__name__)
TIMEOUT = ClientTimeout(total=20)


class DanishNewsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and cache Danish news headlines."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self.config_entry = config_entry
        self.session = async_get_clientsession(hass)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=self.refresh_minutes),
        )

    @property
    def providers(self) -> list[str]:
        """Return configured providers."""

        providers = self.config_entry.options.get(
            CONF_PROVIDERS,
            self.config_entry.data.get(CONF_PROVIDERS, DEFAULT_PROVIDERS),
        )
        return [provider for provider in providers if provider in PROVIDERS] or DEFAULT_PROVIDERS

    @property
    def max_articles(self) -> int:
        """Return number of articles to keep per provider."""

        return int(
            self.config_entry.options.get(
                CONF_MAX_ARTICLES,
                self.config_entry.data.get(CONF_MAX_ARTICLES, DEFAULT_MAX_ARTICLES),
            )
        )

    @property
    def refresh_minutes(self) -> int:
        """Return refresh interval."""

        return int(
            self.config_entry.options.get(
                CONF_REFRESH_MINUTES,
                self.config_entry.data.get(CONF_REFRESH_MINUTES, DEFAULT_REFRESH_MINUTES),
            )
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest headlines from configured providers."""

        now = dt_util.now()
        tasks = [self._async_fetch_provider(provider_key, now) for provider_key in self.providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        providers: dict[str, list[dict[str, Any]]] = {}
        errors: dict[str, str] = {}
        all_articles: list[dict[str, Any]] = []

        for provider_key, result in zip(self.providers, results, strict=True):
            if isinstance(result, Exception):
                _LOGGER.warning("Could not update %s news", provider_key, exc_info=result)
                errors[provider_key] = str(result)
                providers[provider_key] = []
                continue

            providers[provider_key] = result
            all_articles.extend(result)

        if errors and not all_articles and self.data is None:
            raise UpdateFailed("; ".join(errors.values()))

        return {
            "articles": sorted(
                all_articles,
                key=lambda article: article.get("published", ""),
                reverse=True,
            ),
            "providers": providers,
            "errors": errors,
            "provider_info": {
                key: {
                    "name": provider["name"],
                    "short_name": provider["short_name"],
                    "accent": provider["accent"],
                }
                for key, provider in PROVIDERS.items()
            },
            "updated_at": now.isoformat(),
        }

    async def _async_fetch_provider(self, provider_key: str, now) -> list[dict[str, Any]]:
        """Fetch one provider."""

        provider = PROVIDERS[provider_key]
        articles: list[dict[str, Any]] = []
        last_error: Exception | None = None

        for rss_url in provider.get("rss_urls", []):
            try:
                feed_text = await self._async_fetch_text(rss_url)
                articles.extend(parse_feed(provider_key, feed_text, now))
            except Exception as err:  # noqa: BLE001 - keep other feeds/fallbacks alive
                last_error = err
                _LOGGER.debug("RSS fetch failed for %s from %s", provider_key, rss_url, exc_info=True)

            if articles:
                break

        if not articles and provider_key == "tv2" and provider.get("frontpage_url"):
            try:
                html_text = await self._async_fetch_text(provider["frontpage_url"])
                articles.extend(parse_tv2_frontpage(provider_key, html_text, now))
            except Exception as err:  # noqa: BLE001
                last_error = err
                _LOGGER.debug("TV 2 frontpage fallback failed", exc_info=True)

        if not articles and last_error:
            raise UpdateFailed(f"{PROVIDERS[provider_key]['name']}: {last_error}") from last_error

        todays_articles = [article for article in articles if is_today(article, now)]
        return sort_and_limit_articles(todays_articles, self.max_articles)

    async def async_get_article(
        self,
        *,
        provider_key: str,
        article_id: str | None,
        url: str,
    ) -> dict[str, Any]:
        """Fetch and parse a single article for the Lovelace card."""

        if provider_key not in PROVIDERS:
            raise HomeAssistantError("Ukendt nyhedsudbyder")
        if not provider_url_allowed(provider_key, url):
            raise HomeAssistantError("Artiklens URL passer ikke til den valgte udbyder")

        fallback = self._find_cached_article(provider_key, article_id, url)
        if fallback is None:
            fallback = {
                "id": article_id or "",
                "provider": provider_key,
                "provider_name": PROVIDERS[provider_key]["name"],
                "title": "",
                "summary": "",
                "url": url,
                "published": "",
                "image": "",
            }

        try:
            html_text = await self._async_fetch_text(url)
        except (ClientError, ClientResponseError, TimeoutError, asyncio.TimeoutError) as err:
            raise HomeAssistantError(f"Kunne ikke hente artiklen: {err}") from err

        article = extract_article_from_html(provider_key, html_text, fallback)
        if not article["title"]:
            article["title"] = fallback.get("title", "")
        return article

    def _find_cached_article(
        self,
        provider_key: str,
        article_id: str | None,
        url: str,
    ) -> dict[str, Any] | None:
        """Find an article in the latest coordinator data."""

        data = self.data or {}
        for article in data.get("providers", {}).get(provider_key, []):
            if article_id and article.get("id") == article_id:
                return article
            if article.get("url") == url:
                return article
        return None

    async def _async_fetch_text(self, url: str) -> str:
        """Fetch a URL and return response text."""

        async with self.session.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        ) as response:
            response.raise_for_status()
            return await response.text()
