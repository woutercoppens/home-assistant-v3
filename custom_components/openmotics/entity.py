"""Generic OpenMoticDevice Entity."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenMoticsDataUpdateCoordinator


class OpenMoticsDevice(CoordinatorEntity):
    """Representation a base OpenMotics device."""

    coordinator: OpenMoticsDataUpdateCoordinator

    def __init__(
        self,
        coordinator: OpenMoticsDataUpdateCoordinator,
        index: str,
        device,
        device_type: str,
    ) -> None:
        """Initialize the device."""
        super().__init__(coordinator)

        # self._attr_coordinator = coordinator
        self.omclient = coordinator.omclient
        # self._install_id = coordinator.omclient.installation_id
        self._install_id = coordinator.install_id
        self._index = index
        self._device = device

        self._name = device.name
        self._local_id = device.local_id
        self._idx = device.idx
        self._type = device_type

        self._extra_state_attributes = {}
        self._attr_available = True
        # Because polling is so common, Home Assistant by default assumes
        # that your entity is based on polling.
        self._attr_should_poll = False

    # @property
    # def available(self) -> bool:
    #     """Return if entity is available."""
    #     return super().available and True

    @property
    def device(self) -> Any:
        """Return the device."""
        return self._device

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def floor(self) -> str:
        """Return the floor of the device."""
        try:
            location = self._device["location"]
            return location["floor_id"]
        except (AttributeError, KeyError):
            return "N/A"

    @property
    def room(self) -> str:
        """Return the room of the device."""
        try:
            location = self._device["location"]
            return location["room_id"]
        except (AttributeError, KeyError):
            return "N/A"

    @property
    def index(self) -> int:
        """Return the index."""
        return self._index

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.install_id}-{self.device_id}"

    @property
    def device_id(self) -> str:
        """Return a unique ID."""
        return self._idx

    @property
    def type(self) -> str:
        """Return a unique ID."""
        return self._type

    @property
    def install_id(self):
        """Return the installation ID."""
        return self._install_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self._name,
            model=self._type,
            id=self._idx,
            installation=self._install_id,
            manufacturer="OpenMotics",
        )
