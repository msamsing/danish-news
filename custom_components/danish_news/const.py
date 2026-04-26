"""Constants for the Danish News integration."""

from __future__ import annotations

DOMAIN = "danish_news"

CONF_MAX_ARTICLES = "max_articles"
CONF_PROVIDERS = "providers"
CONF_REFRESH_MINUTES = "refresh_minutes"

DEFAULT_MAX_ARTICLES = 8
DEFAULT_PROVIDERS = ["tv2", "dr", "eb", "bt"]
DEFAULT_REFRESH_MINUTES = 15

CARD_FILENAME = "danish-news-card.js"
CARD_URL_PATH = f"/{DOMAIN}/{CARD_FILENAME}"

REQUEST_HEADERS = {
    "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.6",
    "User-Agent": "HomeAssistant-DanishNews/0.1 (+https://www.home-assistant.io/)",
}

PROVIDERS = {
    "tv2": {
        "name": "TV 2",
        "short_name": "TV 2",
        "rss_urls": ["https://services.tv2.dk/api/feeds/nyheder/rss"],
        "frontpage_url": "https://nyheder.tv2.dk",
        "hosts": ["nyheder.tv2.dk", "sport.tv2.dk", "vejr.tv2.dk", "www.tv2.dk"],
        "accent": "#0b5fff",
    },
    "dr": {
        "name": "DR",
        "short_name": "DR",
        "rss_urls": ["https://www.dr.dk/nyheder/service/feeds/allenyheder"],
        "hosts": ["www.dr.dk", "dr.dk"],
        "accent": "#c70039",
    },
    "eb": {
        "name": "Ekstra Bladet",
        "short_name": "EB",
        "rss_urls": ["https://ekstrabladet.dk/rssfeed/all/"],
        "hosts": ["ekstrabladet.dk", "www.ekstrabladet.dk"],
        "accent": "#f3c500",
    },
    "bt": {
        "name": "B.T.",
        "short_name": "B.T.",
        "rss_urls": ["https://www.bt.dk/bt/seneste/rss"],
        "hosts": ["www.bt.dk", "bt.dk"],
        "accent": "#e30613",
    },
}

PROVIDER_NAMES = {key: provider["name"] for key, provider in PROVIDERS.items()}
