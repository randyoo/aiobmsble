"""Module to support EG4 BMS.

Project: aiobmsble, https://pypi.org/p/aiobmsble/
License: Apache-2.0, http://www.apache.org/licenses/
"""

from typing import Final

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

from aiobmsble import BMSDp, BMSInfo, BMSSample, MatcherPattern
from aiobmsble.basebms import BaseBMS, crc_modbus


class BMS(BaseBMS):
    """EG4 BMS implementation."""

    INFO: BMSInfo = {"default_manufacturer": "EG4 electronics", "default_model": "LL"}
    _HEAD: Final[bytes] = b"\x01\x03"  # header for responses
    _MAX_CELLS: Final[int] = 16
    _MIN_LEN: Final[int] = 5
    _FIELDS: Final[tuple[BMSDp, ...]] = (
        BMSDp("voltage", 3, 2, False, lambda x: x / 100),
        BMSDp("current", 5, 2, True, lambda x: x / 10),
        BMSDp("battery_health", 49, 2, False),
        BMSDp("battery_level", 51, 2, False),
        BMSDp("cycle_charge", 45, 2, False, lambda x: x / 10),
        BMSDp("cycles", 61, 4, False, lambda x: x),
        BMSDp("cell_count", 75, 2, False),
        BMSDp("design_capacity", 77, 2, False, lambda x: x // 10),
        BMSDp("temperature", 39, 2, True),
        BMSDp("problem_code", 55, 6, False, lambda x: x),
        # BMSDP("balance", 79, 2, False),
    )

    def __init__(self, ble_device: BLEDevice, keep_alive: bool = False) -> None:
        """Initialize BMS."""
        super().__init__(ble_device, keep_alive)
        self._msg: bytes = b""
        self._exp_len: int = BMS._MIN_LEN

    @staticmethod
    def matcher_dict_list() -> list[MatcherPattern]:
        """Provide BluetoothMatcher definition."""
        return [{"service_uuid": BMS.uuid_services()[0], "connectable": True}]

    @staticmethod
    def uuid_services() -> tuple[str]:
        """Return list of 128-bit UUIDs of services required by BMS."""
        return (normalize_uuid_str("1000"),)

    @staticmethod
    def uuid_rx() -> str:
        """Return 16-bit UUID of characteristic that provides notification/read property."""
        return "1002"

    @staticmethod
    def uuid_tx() -> str:
        """Return 16-bit UUID of characteristic that provides write property."""
        return "1001"

    def _notification_handler(
        self, _sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle the RX characteristics notify event (new data arrives)."""

        # Check if this is a new frame starting (HEAD marker and enough data for length field)
        if len(data) > BMS._MIN_LEN and data.startswith(BMS._HEAD):
            self._log.debug(
                "New frame detected - clearing buffer. Expected=%d, got=%d",
                self._exp_len,
                len(self._frame),
            )
            # Reset frame buffer before processing new data
            self._frame = bytearray()
            # Length field is at position 2 (single byte)
            self._exp_len = BMS._MIN_LEN + data[2]
            self._log.debug("New frame length set to %d bytes", self._exp_len)

        # Append new data to frame buffer
        self._frame += data

        # Log the incoming data
        if len(self._frame) == len(data):  # First chunk of a new frame
            debug_msg = f"RX BLE data (start, {len(data)} bytes): {data.hex()}"
        else:
            debug_msg = (
                f"RX BLE data (cnt., total={len(self._frame)}, this={len(data)}) "
                f"{data.hex() if len(data) <= 32 else f'{data[:16].hex()}... ({len(data)} bytes)'}"
            )
        self._log.debug(debug_msg)

        # Verify we have enough data for the expected frame length
        if len(self._frame) < self._exp_len:
            self._log.debug(
                "Frame incomplete: need %d bytes, have %d",
                self._exp_len,
                len(self._frame),
            )
            # Clear frame buffer to prevent stale data from accumulating
            self._frame = bytearray()
            return

        # Calculate and verify CRC checksum using accumulated frame buffer
        crc_calculated = crc_modbus(self._frame[:-2])
        crc_expected = int.from_bytes(self._frame[-2:], byteorder="little")
        self._log.debug(
            "CRC check: calculated=0x%04X, expected=0x%04X (frame len=%d)",
            crc_calculated,
            crc_expected,
            len(self._frame),
        )

        if (crc := crc_calculated) != crc_expected:
            self._log.warning(
                "Invalid checksum 0x%X != 0x%X (frame len=%d)",
                crc,
                crc_expected,
                len(self._frame),
            )
            return

        self._msg = bytes(self._frame)
        self._log.debug("Frame successfully parsed and event set")
        self._msg_event.set()

    async def _async_update(self) -> BMSSample:
        """Update battery status information."""

        await self._await_msg(b"\x01\x03\x00\x00\x00\x27\x05\xd0")

        result: BMSSample = BMS._decode_data(BMS._FIELDS, self._msg)
        # result["temp_values"] = BMS._temp_values(self._msg, values=3, start=39, size=1)
        result["cell_voltages"] = BMS._cell_voltages(
            self._msg, cells=min(result.get("cell_count", 0), BMS._MAX_CELLS), start=7
        )
        return result
