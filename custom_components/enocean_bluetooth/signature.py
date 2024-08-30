import logging
from Crypto.Cipher import AES

_LOGGER = logging.getLogger(__name__)


def xorb(byte_str1, byte_str2):
    if len(byte_str1) != len(byte_str2):
        raise ValueError("Byte strings must be of the same length")
    return bytes([b1 ^ b2 for b1, b2 in zip(byte_str1, byte_str2)])


class Authentication:
    def __init__(self, mac: str, payload: bytes, security_key: bytes) -> None:
        self._source_address = bytes.fromhex(mac.replace(":", ""))[::-1]
        self._sequence_counter = payload[4:8]
        self._input_data = payload[:9]
        self._signature = payload[9:]
        self._input_length = len(self._input_data).to_bytes(2)
        self._cipher = AES.new(security_key, AES.MODE_ECB)
        self._a0_flag = b"\x01"
        self._b0_flag = b"\x49"

    def _digest(self) -> bytes:
        nonce = (self._source_address + self._sequence_counter).ljust(13, b"\x00")
        a0 = self._a0_flag + nonce + b"\x00\x00"
        b0 = self._b0_flag + nonce + b"\x00\x00"
        b1 = (self._input_length + self._input_data).ljust(16, b"\x00")

        x1 = self._cipher.encrypt(b0)
        x_1a = xorb(x1, b1)
        x2 = self._cipher.encrypt(x_1a)

        s0 = self._cipher.encrypt(a0)
        t0 = xorb(x2, s0)
        return t0[:4]

    def is_valid(self):
        digest = self._digest()
        _LOGGER.debug(
            "digest: %s -- expected: %s, %s",
            digest.hex(),
            self._signature.hex(),
            digest == self._signature,
        )
        return digest == self._signature
