from collections.abc import Callable
from logging import Logger

from sensor_state_data import SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .enocean import Commissioning, EnOceanBluetoothDeviceData

type EnOceanConfigEntry = ConfigEntry[EnOceanPassiveBluetoothProcessorCoordinator]


def format_event_dispatcher_name(address: str, key: str) -> str:
    """Format an event dispatcher name."""
    return f"{DOMAIN}_{address}_{key}"


class EnOceanPassiveBluetoothProcessorCoordinator(
    PassiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Define a EnOcean Bluetooth Passive Update Processor Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        address: str,
        mode: BluetoothScanningMode,
        update_method: Callable[[BluetoothServiceInfoBleak], SensorUpdate],
        commissioning: Commissioning,
        device_data: EnOceanBluetoothDeviceData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the EnOcean BLE Bluetooth Passive Update Processor Coordinator."""
        super().__init__(hass, logger, address, mode, update_method)
        self.commissioning = commissioning
        self.entry = entry
        self.model_info = commissioning.model
        self.device_data = device_data


def process_service_info(
    hass: HomeAssistant,
    entry: EnOceanConfigEntry,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    coordinator = entry.runtime_data
    data = coordinator.device_data
    update = data.update(service_info)
    if update.events and hass.state is CoreState.running:
        # Do not fire events on data restore
        address = service_info.device.address
        for event in update.events.values():
            key = event.device_key.key
            signal = format_event_dispatcher_name(address, key)
            async_dispatcher_send(hass, signal, event)

    return update
