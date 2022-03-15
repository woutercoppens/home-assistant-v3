"""Support for HomeAssistant lights."""
from __future__ import annotations

import logging

from homeassistant.components.light import (  # SUPPORT_BRIGHTNESS, # Deprecated, replaced by color modes
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NOT_IN_USE
from .coordinator import OpenMoticsDataUpdateCoordinator
from .entity import OpenMoticsDevice

# from typing import ValuesView


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Component doesn't support configuration through configuration.yaml."""
    return


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lights for OpenMotics Controller."""
    entities = []

    coordinator: OpenMoticsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for index, om_light in enumerate(coordinator.data["outputs"]):
        if om_light.name is None or om_light.name == "" or om_light.name == NOT_IN_USE:
            continue

        # Outputs can contain outlets and lights, so filter out only the lights
        if om_light.output_type == "LIGHT":
            entities.append(OpenMoticsOutputLight(coordinator, index, om_light))

    for index, om_light in enumerate(coordinator.data["lights"]):
        if om_light.name is None or om_light.name == "" or om_light.name == NOT_IN_USE:
            continue

        entities.append(OpenMoticsLight(coordinator, index, om_light))

    if not entities:
        _LOGGER.info("No OpenMotics Lights added")
        return False

    async_add_entities(entities, True)


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return round((byt * 100.0) / 255.0)


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return round((percent * 255.0) / 100.0)


class OpenMoticsOutputLight(OpenMoticsDevice, LightEntity):
    """Representation of a OpenMotics Output light."""

    coordinator: OpenMoticsDataUpdateCoordinator

    def __init__(self, coordinator: OpenMoticsDataUpdateCoordinator, index, device):
        """Initialize the light."""
        super().__init__(coordinator, index, device, "light")

        # self._device = self.coordinator.data["outputs"][self.index]

        self._attr_supported_color_modes = set()

        if "RANGE" in device.capabilities:
            self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        try:
            self._device = self.coordinator.data["outputs"][self.index]
            return self._device.status.on
        except (AttributeError, KeyError):
            return None

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        try:
            self._device = self.coordinator.data["outputs"][self.index]
            return self._device.status.value
        except (AttributeError, KeyError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # Openmotics brightness (value) is between 0..100
            _LOGGER.debug(
                "Turning on light: %s brightness %s",
                self.device_id,
                kwargs[ATTR_BRIGHTNESS],
            )
            response = await self.coordinator.omclient.outputs.turn_on(
                self.device_id,
                brightness_to_percentage(kwargs[ATTR_BRIGHTNESS]),  # value
            )
        else:
            _LOGGER.debug("Turning on light: %s", self.device_id)
            response = await self.coordinator.omclient.outputs.turn_on(
                self.device_id,
            )

        # Turns on a specified Output object.
        # The call can optionally receive a JSON object that states the value
        # in case the Output is dimmable.
        # if response:
        #     try:
        #         _LOGGER.debug("Light turned on: %s response OM %s", self.device_id, response["value"])
        #         self.device.status.value = brightness_from_percentage(response["value"])
        #     except KeyError:
        #         self.device.status.value = None

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn devicee off."""
        _LOGGER.debug("Turning off light: %s", self.device_id)
        await self.coordinator.omclient.outputs.turn_off(
            self.device_id,
        )
        await self.coordinator.async_refresh()

    # async def _async_update_callback(self) -> None:
    #     """Update the entity."""
    #     self._device = self.coordinator.data["outputs"][self.index]

    #     await self.async_update_ha_state(True)


class OpenMoticsLight(OpenMoticsDevice, LightEntity):
    """Representation of a OpenMotics light."""

    coordinator: OpenMoticsDataUpdateCoordinator

    def __init__(self, coordinator: OpenMoticsDataUpdateCoordinator, index, device):
        """Initialize the light."""
        super().__init__(coordinator, index, device, "light")

        self._attr_supported_color_modes = set()

        if "RANGE" in device.capabilities:
            self._attr_supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            # Default: Brightness (no color)
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS

        if "WHITE_TEMP" in device.capabilities:
            self._attr_supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
            self._attr_supported_color_modes.add(COLOR_MODE_HS)

        if "FULL_COLOR" in device.capabilities:
            self._attr_supported_color_modes.add(COLOR_MODE_RGBW)

    @property
    def is_on(self):
        """Return true if device is on."""
        try:
            self._device = self.coordinator.data["lights"][self.index]
            return self._device.status.on
        except (AttributeError, KeyError):
            return None

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        try:
            self._device = self.coordinator.data["lights"][self.index]
            return self._device.status.value
        except (AttributeError, KeyError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # Openmotics brightness (value) is between 0..100
            _LOGGER.debug(
                "Turning on light: %s brightness %s",
                self.device_id,
                kwargs[ATTR_BRIGHTNESS],
            )
            response = await self.coordinator.omclient.lights.turn_on(
                self.device_id,
                brightness_to_percentage(kwargs[ATTR_BRIGHTNESS]),  # value
            )
        else:
            _LOGGER.debug("Turning on light: %s", self.device_id)
            response = await self.coordinator.omclient.lights.turn_on(
                self.device_id,
            )

        # Turns on a specified Light object.
        # The call can optionally receive a JSON object that states the value
        # in case the Light is dimmable.
        # if response:
        #     try:
        #         _LOGGER.debug("Light turned on: %s response OM %s", self.device_id, response["value"])
        #         self.device.status.value = brightness_from_percentage(response["value"])
        #     except KeyError:
        #         self.device.status.value = None

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn devicee off."""
        _LOGGER.debug("Turning off light: %s", self.device_id)
        await self.coordinator.omclient.lights.turn_off(
            self.device_id,
        )
        await self.coordinator.async_refresh()
