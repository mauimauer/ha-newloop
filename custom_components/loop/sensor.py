"""Platform for the loop sensor integration."""
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import POWER_KILO_WATT
from . import LoopEnergyApi, LoopEntity
from .const import DOMAIN, SENSOR_POWER

from .const import (
    SENSOR_POWER,
    DOMAIN,
    ICON_POWER_USAGE,
    ICON_PHANTOM_LOAD,
    NAME_POWER_USAGE,
    NAME_PHANTOM_LOAD,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [LoopPowerUsageSensor(api), LoopPhantomLoadSensor(api)]

    # Add sensor entities.
    async_add_entities(entities, True)


class LoopPhantomLoadSensor(LoopEntity):
    """Representation of a Loop Phantom Load sensor."""

    def __init__(self, api: LoopEnergyApi) -> None:
        """Initialize protocol version sensor."""
        super().__init__(
            api=api,
            type_name=NAME_PHANTOM_LOAD,
            icon=ICON_PHANTOM_LOAD,
            unit=POWER_KILO_WATT,
            device_class=None,
        )

    async def async_update(self) -> None:
        self._state = self._api.phantom_load


class LoopPowerUsageSensor(LoopEntity):
    """Representation of a Loop Power Usage sensor."""

    def __init__(self, api: LoopEnergyApi) -> None:
        """Initialize protocol version sensor."""
        super().__init__(
            api=api,
            type_name=NAME_POWER_USAGE,
            icon=ICON_POWER_USAGE,
            unit=POWER_KILO_WATT,
            device_class=None,
        )

    async def async_update(self) -> None:
        self._state = self._api.power_usage