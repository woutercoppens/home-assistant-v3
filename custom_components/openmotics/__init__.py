"""The Openmotics integration.

    Support for OpenMotics.
    For more details about this component, please refer to the documentation at
    https://github.com/openmotics/home-assistant

    For examples of the output of the api, look at openmotics_api.md
"""
# pylint: disable=import-outside-toplevel
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from pyhaopenmotics.const import (
    CLOUD_API_AUTHORIZATION_URL,
    CLOUD_API_TOKEN_URL,
    CLOUD_API_VERSION,
    CLOUD_BASE_URL,
)

from .const import CONF_INSTALLATION_ID, DOMAIN, PLATFORMS
from .coordinator import (
    OpenMoticsCloudDataUpdateCoordinator,
    OpenMoticsLocalDataUpdateCoordinator,
)
from .oauth_impl import OpenMoticsOauth2Implementation

CONF_AUTH_IMPLEMENTATION = "auth_implementation"

base_url = f"{CLOUD_BASE_URL}/{CLOUD_API_VERSION}"
token_url = f"{base_url}{CLOUD_API_TOKEN_URL}"
authorize_url = f"{base_url}{CLOUD_API_AUTHORIZATION_URL}"

_LOGGER = logging.getLogger(__name__)


async def async_setup_openmotics_installation(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry, openmotics_installation
):
    """Set up the OpenMotics Installation."""
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, openmotics_installation["id"])},
        manufacturer="OpenMotics",
        name=openmotics_installation["name"],
        model=openmotics_installation["gateway_model"],
        sw_version=openmotics_installation["version"],
    )

    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up OpenMotics Gateway from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if CONF_IP_ADDRESS in entry.data:
        # Local gateway
        coordinator = OpenMoticsLocalDataUpdateCoordinator(
            hass,
            entry=entry,
        )

    else:
        # Cloud
        implementation = OpenMoticsOauth2Implementation(
            hass,
            domain=entry.data.get(CONF_AUTH_IMPLEMENTATION),
            client_id=entry.data.get(CONF_CLIENT_ID),
            client_secret=entry.data.get(CONF_CLIENT_SECRET),
            name=entry.data.get(CONF_AUTH_IMPLEMENTATION),
        )
        oauth2_session = OAuth2Session(hass, entry, implementation)

        """Set up OpenMotics from a config entry."""
        coordinator = OpenMoticsCloudDataUpdateCoordinator(
            hass,
            entry=entry,
            session=oauth2_session,
        )

        coordinator.omclient.installation_id = entry.data.get(CONF_INSTALLATION_ID)

    # await coordinator.async_refresh()

    # if not coordinator.last_update_success:
    #     raise ConfigEntryNotReady(f"Unable to connect to OpenMoticsApi")

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Spin up the platforms
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # If Home Assistant is already in a running state, register the webhook
    # immediately, else trigger it after Home Assistant has finished starting.
    # if hass.state == CoreState.running:
    #     await coordinator.register_webhook()
    # else:
    #     hass.bus.async_listen_once(
    #         EVENT_HOMEASSISTANT_STARTED, coordinator.register_webhook
    #     )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    # Remove webhooks registration
    # await hass.data[DOMAIN][entry.entry_id].unregister_webhook()

    # Unload entities for this entry/device.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cleanup
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
