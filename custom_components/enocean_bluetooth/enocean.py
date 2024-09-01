from dataclasses import dataclass
import logging

from bluetooth_sensor_state_data import BluetoothData
from habluetooth import BluetoothServiceInfo, BluetoothServiceInfoBleak

from .signature import Authentication
from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class PTM215B:
    @staticmethod
    def name():
        return "PTM_215B"

    @staticmethod
    def button_labels():
        return ["A0", "A1", "B0", "B1"]

    @staticmethod
    def actions():
        return ["release", "press"]

    @staticmethod
    def decoder():
        return PTM215BDataParser()


MAC_MODEL_MAP = {
    "E2:15": PTM215B,
}


@dataclass(frozen=True)
class PTM215BData:
    button_label: str
    action: str
    sequence: int


class PTM215BDataParser:
    def __init__(self) -> None:
        self._btn_map = {1 << i: v for i, v in enumerate(PTM215B.button_labels())}

    def _decode_action(self, btn_enc: int) -> str:
        return PTM215B.actions()[btn_enc & 0x1]

    def _decode_btn(self, btn_enc: int) -> str:
        shift = btn_enc >> 1
        return self._btn_map.get(shift, "")

    def parse_manufacturer_data(self, manufacturer_data: dict[int, bytes]):
        md = manufacturer_data[986]
        seq = int.from_bytes(md[0:4], byteorder="little")
        btn_enc = md[4]
        action = self._decode_action(btn_enc)
        button = self._decode_btn(btn_enc)

        return PTM215BData(
            button_label=button,
            action=action,
            sequence=seq,
        )

    def full_payload(self, manufacturer_data: dict[int, bytes], manufacturer_id: int):
        return (
            b"\x0c\xff"
            + manufacturer_id.to_bytes(2, byteorder="little")
            + manufacturer_data[manufacturer_id]
        )


@dataclass(frozen=True)
class Commissioning:
    mac: str
    manufacturer_id: int
    model: type[PTM215B]
    security_key: bytes
    ordering_code: str
    step_code: int
    serial_number: str

    @property
    def title(self):
        return f"{self.model.name()} {self.serial_number}"


class QRCommissioning(Commissioning):
    """Decode QR Codes like: 30SE21501500100+Z0123456789ABCDEF0123456789ABCDEF+30PS3221-A215+2PDC06+S01234567890123"""

    def __init__(self, qr_code: str) -> None:
        """Initialize the QRCommissioning class."""
        chunks = qr_code.split("+")
        if len(chunks) < 5:
            raise InvalidQRCode
        if chunks[0].startswith("30S"):
            mac = chunks[0][3:]
            mac = ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])
            manufacturer_id = 0x03DA
            if mac.startswith("E2:15"):
                model = MAC_MODEL_MAP["E2:15"]
        if chunks[1].startswith("Z"):
            security_key = bytes.fromhex(chunks[1][1:])
        if chunks[2].startswith("30P"):
            ordering_code = chunks[2][3:]
        if chunks[3].startswith("2P"):
            step_code = chunks[3][2:]
        if chunks[4].startswith("S"):
            serial_number = chunks[4][1:]

        super().__init__(
            mac=mac,
            manufacturer_id=manufacturer_id,
            model=model,
            security_key=security_key,
            ordering_code=ordering_code,
            step_code=step_code,
            serial_number=serial_number,
        )


class EnOceanBluetoothDeviceData(BluetoothData):
    def __init__(self, commissioning: Commissioning) -> None:
        super().__init__()
        self._commissioning = commissioning
        self._previous_seq = 0

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        model = self._commissioning.model
        self.set_device_name(self._commissioning.title)
        self.set_title(self._commissioning.title)
        self.set_device_type(model.name())
        self.set_device_manufacturer(service_info.manufacturer)
        # self.set_device_hw_version(self._commissioning.mac)
        if not (manufacturer_data := service_info.manufacturer_data):
            return
        decoder = model.decoder()
        data = decoder.parse_manufacturer_data(manufacturer_data)
        _LOGGER.debug("Received data: %s %s", data, manufacturer_data)

        auth = Authentication(
            mac=service_info.address,
            payload=decoder.full_payload(
                manufacturer_data, service_info.manufacturer_id
            ),
            security_key=self._commissioning.security_key,
        )
        if not auth.is_valid():
            _LOGGER.error(
                "Invalid signature detected for %s! %s", self._commissioning.title, data
            )

        if data.sequence <= self._previous_seq:
            _LOGGER.error("Replay detected for %s! %s", self._commissioning.title, data)

        self._previous_seq = data.sequence
        self.fire_event(
            key=f"button_{data.button_label}",
            event_type=data.action,
        )
        return


class InvalidQRCode(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid qr_code."""
