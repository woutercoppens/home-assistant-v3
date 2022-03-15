"""Adds config flow for OpenMotics."""
from __future__ import annotations

import asyncio
import logging
import ssl
import time
from typing import Any

import async_timeout
import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import (
    ATTR_CREDENTIALS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from pyhaopenmotics import (
    Installation,
    LocalGateway,
    OpenMoticsCloud,
    OpenMoticsConnectionError,
    OpenMoticsConnectionTimeoutError,
    OpenMoticsError,
)

from .const import CONF_INSTALLATION_ID, DOMAIN, ENV_CLOUD, ENV_LOCAL
from .exceptions import CannotConnect, InvalidAuth
from .oauth_impl import OpenMoticsOauth2Implementation

DEFAULT_PORT = 443
DEFAULT_VERIFY_SSL = True

CLOUD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
    }
)

LOCAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)
_LOGGER = logging.getLogger(__name__)


# @config_entries.HANDLERS.register(DOMAIN)
class OpenMoticsFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow for OpenMotics."""

    VERSION = 2
    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    installations: list[Installation] | None = None
    data: dict[str, Any] = {}

    def __init__(self) -> None:
        #     """Create a new instance of the flow handler."""
        super().__init__()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    def is_local_device_already_added(self):
        """Check if a Local device has already been added."""
        for entry in self._async_current_entries():
            if entry.unique_id is not None and entry.unique_id.startswith(
                f"{DOMAIN}-Local-"
            ):
                return True
        return False

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow initiated by the user."""

        # If there is a Local entry already, abort a new entry
        # If you want to manage multiple devices, do it via cloud
        if self.is_local_device_already_added():
            return self.async_abort(reason="already_configured_local_device")

        return await self.async_step_environment()

    async def async_step_environment(self, user_input=None) -> FlowResult:
        """Decide environment, cloud or local."""
        if user_input is None:
            return self.async_show_form(
                step_id="environment",
                data_schema=vol.Schema(
                    {
                        vol.Required("environment", default=ENV_CLOUD): vol.In(
                            [ENV_CLOUD, ENV_LOCAL]
                        )
                    }
                ),
                errors={},
            )

        # Environment chosen, request additional host information for LOCAL or OAuth2 flow for CLOUD
        # Ask for host detail
        if user_input["environment"] == ENV_LOCAL:
            return await self.async_step_local()

        # Ask for cloud detail
        return await self.async_step_cloud()

    async def async_step_cloud(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            self.data[CONF_CLIENT_ID] = user_input[CONF_CLIENT_ID]
            self.data[CONF_CLIENT_SECRET] = user_input[CONF_CLIENT_SECRET]

            try:
                self.flow_impl = OpenMoticsOauth2Implementation(
                    self.hass,
                    domain=f"{DOMAIN}-config_flow",
                    client_id=self.data[CONF_CLIENT_ID],
                    client_secret=self.data[CONF_CLIENT_SECRET],
                    name=f"{DOMAIN}-config_flow",
                )

                # self.token = await self.flow_impl.get_token({})
                # _LOGGER.debug(self.token)

                self.token = await self.flow_impl.async_resolve_external_data(
                    self.external_data
                )
                # Force int for non-compliant oauth2 providers
                try:
                    self.token["expires_in"] = int(self.token["expires_in"])
                except ValueError as err:
                    _LOGGER.warning("Error converting expires_in to int: %s", err)
                    return self.async_abort(reason="oauth_error")
                self.token["expires_at"] = time.time() + self.token["expires_in"]

                self.logger.info("Successfully authenticated")

                self.oauth2_session = OAuth2Session(
                    self.hass,
                    {"domain": DOMAIN, "data": {"token": self.token}},
                    self.flow_impl,
                )

                omclient = OpenMoticsCloud(
                    token=self.token["access_token"],
                    session=async_get_clientsession(self.hass),
                )

                self.installations = await omclient.installations.get_all()

            #     # TODO: add proper error handling
            except (
                asyncio.TimeoutError,
                OpenMoticsError,
            ) as err:
                _LOGGER.error(err)
                raise CannotConnect from err

            # self.data["auth_implementation"] = self.flow_impl.domain
            # self.data["token"] = self.token

            if len(self.installations) > 0:
                # show selection form
                return await self.async_step_installation()

            errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="cloud", data_schema=CLOUD_SCHEMA, errors=errors
        )

    async def async_step_installation(self, user_input=None) -> FlowResult:
        """Ask user to select the Installation ID to use."""
        if user_input is None or CONF_INSTALLATION_ID not in user_input:
            # Get available installations
            existing_installations = [
                entry.data[CONF_INSTALLATION_ID]
                for entry in self._async_current_entries()
            ]

            installations_options = {
                installation.idx: installation.name
                for installation in self.installations
                if installation.idx not in existing_installations
            }
            if not installations_options:
                return self.async_abort(reason="no_available_installation")

            return self.async_show_form(
                step_id="installation",
                data_schema=vol.Schema(
                    {vol.Required(CONF_INSTALLATION_ID): vol.In(installations_options)}
                ),
            )

        self.data[CONF_INSTALLATION_ID] = user_input[CONF_INSTALLATION_ID]
        _LOGGER.debug(self.data[CONF_INSTALLATION_ID])
        return await self.async_step_create_cloudentry()

    async def async_step_create_cloudentry(self, data=None) -> FlowResult:
        """Create a config entry at completion of a flow and authorization of the app."""
        unique_id = self.construct_unique_id("Cloud", self.data[CONF_INSTALLATION_ID])
        await self.async_set_unique_id(unique_id)

        self.data[
            "auth_implementation"
        ] = f"{self.flow_impl.domain}-{self.data[CONF_INSTALLATION_ID]}"
        self.data["token"] = self.token

        return self.async_create_entry(title=unique_id, data=self.data)

    # async def async_step_zeroconf(
    #     self, discovery_info: zeroconf.ZeroconfServiceInfo
    # ) -> FlowResult:
    #     """Handle zeroconf discovery."""

    #     if not discovery_info.hostname.startswith("OpenMotics"):
    #         return self.async_abort(reason="invalid_mdns")

    #     ip_address = discovery_info.host

    #     await self.async_set_unique_id(ip_address)
    #     self._abort_if_unique_id_configured()
    #     self.discovered_ip_address = ip_address
    #     return await self.async_step_user()

    #     return await self.async_verify_local_connection()

    async def async_step_local(self, user_input=None) -> FlowResult:
        """Handle local flow."""
        errors = {}

        if user_input is not None:
            self.data[CONF_IP_ADDRESS] = user_input[CONF_IP_ADDRESS]
            self.data[CONF_NAME] = user_input[CONF_NAME]
            self.data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
            self.data[CONF_PORT] = user_input[CONF_PORT]
            self.data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]

            try:
                omclient = LocalGateway(
                    localgw=self.data[CONF_IP_ADDRESS],
                    username=self.data[CONF_NAME],
                    password=self.data[CONF_PASSWORD],
                    port=self.data[CONF_PORT],
                    tls=self.data[CONF_VERIFY_SSL],
                )
                await omclient.login()

                version = await omclient.exec_action("get_version")
                _LOGGER.debug(version)

            except ssl.SSLError:
                errors["base"] = "old_gateway"
            except (
                asyncio.TimeoutError,
                OpenMoticsError,
            ) as err:
                _LOGGER.error(err)
                raise CannotConnect from err

            if version is not None:
                return await self.async_step_create_localentry()
            errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="local", data_schema=LOCAL_SCHEMA, errors=errors
        )

    async def async_step_create_localentry(self, data=None) -> FlowResult:
        """Create a config entry at completion of a flow and authorization of the app."""
        unique_id = self.construct_unique_id("Local", self.data[CONF_IP_ADDRESS])
        await self.async_set_unique_id(unique_id)

        return self.async_create_entry(title=unique_id, data=self.data)

    @staticmethod
    def construct_unique_id(host: str, install_id: str) -> str:
        """Construct the unique id from the ssdp discovery or user_step."""
        return f"{host}-{install_id}"
