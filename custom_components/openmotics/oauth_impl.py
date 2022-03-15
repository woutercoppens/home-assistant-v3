"""Local implementation of OAuth2 specific to OpenMotics to hard code client id and secret and return a proper name."""

# from attr import has
import time
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2Implementation
from pyhaopenmotics.const import (
    CLOUD_API_AUTHORIZATION_URL,
    CLOUD_API_TOKEN_URL,
    CLOUD_API_VERSION,
    CLOUD_BASE_URL,
    CLOUD_SCOPE,
)

from .const import DOMAIN

base_url = f"{CLOUD_BASE_URL}/{CLOUD_API_VERSION}"
token_url = f"{base_url}{CLOUD_API_TOKEN_URL}"
authorize_url = f"{base_url}{CLOUD_API_AUTHORIZATION_URL}"


class OpenMoticsOauth2Implementation(LocalOAuth2Implementation):
    """Local implementation of OAuth2 specific to Ondilo to hard code client id and secret and return a proper name."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        client_secret: str,
        name: str,
    ) -> None:
        """Local Toon Oauth Implementation."""
        self._name = name
        """Just init default class with default values."""
        super().__init__(
            hass=hass,
            domain=domain,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url=authorize_url,
            token_url=token_url,
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return self._name

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(CLOUD_SCOPE)}

    # async def get_token(self, data: dict) -> dict:
    #     """Make a token request."""
    #     session = async_get_clientsession(self.hass)
    #     headers = {}

    #     data["client_id"] = self.client_id
    #     data["grant_type"] = "client_credentials"

    #     if self.client_secret is not None:
    #         data["client_secret"] = self.client_secret

    #     resp = await session.post(self.token_url, data=data, headers=headers)
    #     resp.raise_for_status()
    #     resp_json = cast(dict, await resp.json())
    #     # The OM API returns "expires_in" as a string for some tenants.
    #     # This is not according to OAuth specifications.
    #     resp_json["expires_in"] = float(resp_json["expires_in"])
    #     # LocalOAuth2Implementation requires expires_at
    #     resp_json["expires_at"] = time.time() + resp_json["expires_in"]
    #     return resp_json

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        # Overruling config_entry_oauth2_flow.
        return await self._token_request(
            {
                "grant_type": "client_credentials",
                # "code": external_data["code"],
                # "redirect_uri": external_data["state"]["redirect_uri"],
            }
        )

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        # Overruling config_entry_oauth2_flow.
        new_token = await self._token_request(
            {
                "grant_type": "client_credentials",
                # client_id and client_secret is added
                # by _token_request
                # "client_id": self.client_id,
                # "refresh_token": token["refresh_token"],
            }
        )
        return {**token, **new_token}
