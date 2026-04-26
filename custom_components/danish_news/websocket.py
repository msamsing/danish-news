"""WebSocket API for the Danish News Lovelace card."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def async_register_websocket(hass: HomeAssistant) -> None:
    """Register WebSocket commands once."""

    if hass.data.setdefault(DOMAIN, {}).get("websocket_registered"):
        return

    websocket_api.async_register_command(hass, websocket_get_article)
    hass.data[DOMAIN]["websocket_registered"] = True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "danish_news/get_article",
        vol.Required("entry_id"): str,
        vol.Required("provider"): str,
        vol.Optional("article_id"): str,
        vol.Required("url"): str,
    }
)
@websocket_api.async_response
async def websocket_get_article(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return an extracted article body to the frontend card."""

    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Danish News entry was not found")
        return

    try:
        article = await coordinator.async_get_article(
            provider_key=msg["provider"],
            article_id=msg.get("article_id"),
            url=msg["url"],
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "article_error", str(err))
        return

    connection.send_result(msg["id"], article)
