"""The Detailed Hello World Push integration."""

from __future__ import annotations

from functools import partial
import logging

from bluetooth_sensor_state_data import BluetoothData
from habluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    BluetoothServiceInfoBleak,
)

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import (
    EnOceanConfigEntry,
    EnOceanPassiveBluetoothProcessorCoordinator,
    process_service_info,
)
from .enocean import Commissioning, EnOceanBluetoothDeviceData, QRCommissioning

PLATFORMS = [Platform.SENSOR, Platform.EVENT]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: EnOceanConfigEntry) -> bool:
    """Set up example BLE device from a config entry."""
    deviceCommissioning = QRCommissioning(entry.data["qr_code_string"])
    address = deviceCommissioning.mac
    data = EnOceanBluetoothDeviceData(deviceCommissioning)
    entry.runtime_data = coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = EnOceanPassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=partial(process_service_info, hass, entry),
        commissioning=deviceCommissioning,
        device_data=data,
        entry=entry,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        # only start after all platforms have had a chance to subscribe
        coordinator.async_start()
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok
