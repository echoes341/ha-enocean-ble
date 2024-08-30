import logging

from habluetooth import BluetoothServiceInfoBleak
from sensor_state_data import Event

from homeassistant.components.bluetooth.api import async_last_service_info
from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EnOceanConfigEntry, format_event_dispatcher_name
from .enocean import PTM215B, Commissioning

_LOGGER = logging.getLogger(__name__)


BUTTON_DESCRIPTIONS = {
    PTM215B.name(): [
        EventEntityDescription(
            name=label,
            key=f"button_{label}",
            translation_key=f"button_{label}",
            event_types=PTM215B.actions(),
            device_class=EventDeviceClass.BUTTON,
        )
        for label in PTM215B.button_labels()
    ]
}


class EnOceanBluetoothEventEntity(EventEntity):
    """Representation of a EnOcean event entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        commissioning: Commissioning,
        address: str,
        description: EventEntityDescription,
    ) -> None:
        """Initialise a EnOcean event entity."""
        self.entity_description = description
        name = commissioning.title
        self._attr_device_info = dr.DeviceInfo(
            name=name,
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
        )
        self._attr_unique_id = f"{address}-{description.key}"
        self._address = address
        self._signal = format_event_dispatcher_name(
            self._address, self.entity_description.key
        )

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._signal,
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event: Event) -> None:
        _LOGGER.debug("relay event: %s", event)
        self._trigger_event(event.event_type)
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnOceanConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a EnOcean event."""
    coordinator = entry.runtime_data
    if not (model_info := coordinator.model_info):
        return
    address = coordinator.address
    descriptions = BUTTON_DESCRIPTIONS[model_info.name()]
    async_add_entities(
        EnOceanBluetoothEventEntity(
            commissioning=coordinator.commissioning,
            address=address,
            description=description,
        )
        for description in descriptions
    )
