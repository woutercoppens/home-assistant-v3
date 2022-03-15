"""DataUpdateCoordinator for the OpenMotics integration."""
from __future__ import annotations

import logging
from typing import Any

from async_timeout import timeout
from homeassistant.components import cloud, webhook
from homeassistant.components.webhook import async_register as webhook_register
from homeassistant.components.webhook import async_unregister as webhook_unregister
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyhaopenmotics import (
    LocalGateway,
    OpenMoticsCloud,
    OpenMoticsConnectionError,
    OpenMoticsConnectionTimeoutError,
    OpenMoticsError,
)

from .const import CONF_INSTALLATION_ID, DEFAULT_SCAN_INTERVAL, DOMAIN
from .exceptions import CannotConnect, InvalidAuth

_LOGGER = logging.getLogger(__name__)


class OpenMoticsDataUpdateCoordinator(DataUpdateCoordinator):
    """Query OpenMotics devices and keep track of seen conditions."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the OpenMotics gateway."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.session = None
        self.entry = entry
        self._omclient = None
        self._install_id = None

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables so entities can quickly look up their data.
        """

        try:
            my_outputs = await self._omclient.outputs.get_all()
            my_lights = await self._omclient.lights.get_all()
            my_groupactions = await self._omclient.groupactions.get_all()
            my_shutters = await self._omclient.shutters.get_all()
            my_sensors = await self._omclient.sensors.get_all()

        except OpenMoticsError as err:
            _LOGGER.error("Could not retrieve the data from the OpenMotics API")
            _LOGGER.error("Too many errors: %s", err)
            return {
                "lights": [],
                "outputs": [],
                "groupactions": [],
                "shutters": [],
                "sensors": [],
            }
        # Store data in a way Home Assistant can easily consume it
        return {
            "outputs": my_outputs,
            "lights": my_lights,
            "groupactions": my_groupactions,
            "shutters": my_shutters,
            "sensors": my_sensors,
        }

    @property
    def omclient(self) -> Any:
        """Return the backendclient."""
        return self._omclient

    @property
    def install_id(self) -> int:
        """Return the backendclient."""
        return self._install_id


class OpenMoticsCloudDataUpdateCoordinator(OpenMoticsDataUpdateCoordinator):
    """Query OpenMotics devices and keep track of seen conditions."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, session: OAuth2Session
    ) -> None:
        """Initialize the OpenMotics gateway."""
        super().__init__(
            hass,
            entry,
        )
        self.session = session
        self._install_id = entry.data.get(CONF_INSTALLATION_ID)

        async def async_token_refresh() -> str:
            await session.async_ensure_token_valid()
            return session.token["access_token"]

        self._omclient = OpenMoticsCloud(
            token=session.token["access_token"],
            session=async_get_clientsession(hass),
            token_refresh_method=async_token_refresh,
        )


class OpenMoticsLocalDataUpdateCoordinator(OpenMoticsDataUpdateCoordinator):
    """Query OpenMotics devices and keep track of seen conditions."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the OpenMotics gateway."""
        super().__init__(
            hass,
            entry,
        )
        self._install_id = entry.data.get(CONF_IP_ADDRESS)

        """Set up a OpenMotics controller"""
        self._omclient = LocalGateway(
            localgw=entry.data.get(CONF_IP_ADDRESS),
            username=entry.data.get(CONF_USERNAME),
            password=entry.data.get(CONF_PASSWORD),
            port=entry.data.get(CONF_PORT),
            ssl_context=ssl_context,
        )
