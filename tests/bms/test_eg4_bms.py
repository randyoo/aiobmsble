"""Test the EG4 BMS implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.uuids import normalize_uuid_str
import pytest

from aiobmsble.basebms import BMSSample
from aiobmsble.bms.eg4_bms import BMS as EG4BMS
from tests.bluetooth import generate_ble_device
from tests.conftest import MockBleakClient

BT_FRAME_SIZE: Final[int] = 80

_RESULT_DEFS: Final[BMSSample] = {
    "voltage": 13.3,
    "current": 0.0,
    "battery_health": 100,
    "battery_level": 92,
    "cell_count": 4,
    "cycles": 5,
    "cycle_charge": 369.8,
    "cell_voltages": [3.326, 3.327, 3.327, 3.323],
    "delta_voltage": 0.004,
    "temperature": 14,
    "cycle_capacity": 4918.34,
    "design_capacity": 400,
    "power": 0.0,
    # "runtime": 54770,
    "battery_charging": False,
    "problem_code": 0,
    "problem": False,
}


class MockEG4BleakClient(MockBleakClient):
    """Emulate a EG4 BMS BleakClient."""

    _TX_CHAR_UUID: Final[str] = "1001"
    _RESP: dict[bytes, bytearray] = {
        b"\x01\x03\x00\x00\x00\x27\x05\xd0": bytearray(
            b"\x01\x03\x4e\x05\x32\x00\x00\x0c\xfe\x0c\xff\x0c\xff\x0c\xfb\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0e\x00\x0e\x00"
            b"\x0e\x0e\x72\x08\x98\x00\x64\x00\x5c\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x55"
            b"\xd4\xa8\x00\x0e\x0e\x00\x00\x00\x00\x00\x04\x0f\xa0\x00\x00\xe0\x65"
        )
    }

    def _response(
        self, char_specifier: BleakGATTCharacteristic | int | str | UUID, data: Buffer
    ) -> bytes:
        """Generate response based on command."""
        if not isinstance(char_specifier, str) or normalize_uuid_str(
            char_specifier
        ) != normalize_uuid_str(self._TX_CHAR_UUID):
            return b""

        resp = self._RESP.get(bytes(data), bytearray())
        if isinstance(resp, bytearray):
            return bytes(resp)
        return resp

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""
        await super().write_gatt_char(char_specifier, data, response)
        assert self._notify_callback is not None
        self._notify_callback(
            "MockGobelBleakClient", self._response(char_specifier, data)
        )


async def test_update(patch_bleak_client, keep_alive_fixture: bool) -> None:
    """Test EG4 BMS data update."""

    patch_bleak_client(MockEG4BleakClient)

    bms = EG4BMS(generate_ble_device(), keep_alive_fixture)

    assert await bms.async_update() == _RESULT_DEFS

    # query again to check already connected state
    await bms.async_update()
    assert bms._client and bms._client.is_connected is keep_alive_fixture

    await bms.disconnect()


async def test_device_info(patch_bleak_client) -> None:
    """Test that the EG4 BMS returns initialized dynamic device information."""
    patch_bleak_client(MockEG4BleakClient)
    bms = EG4BMS(generate_ble_device())
    assert await bms.device_info() == {
        "fw_version": "mock_FW_version",
        "hw_version": "mock_HW_version",
        "sw_version": "mock_SW_version",
        "manufacturer": "mock_manufacturer",
        "model": "mock_model",
        "serial_number": "mock_serial_number",
    }


@pytest.mark.parametrize(
    "wrong_response",
    [
        b"\x02\x03\x4e\x05\x32\x00\x00\x0c\xfe\x0c\xff\x0c\xff\x0c\xfb\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0e\x00\x0e\x00"
        b"\x0e\x0e\x72\x08\x98\x00\x64\x00\x5c\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x55"
        b"\xd4\xa8\x00\x0e\x0e\x00\x00\x00\x00\x00\x04\x0f\xa0\x00\x00\x2c\x1d",
        b"\x01\x03\x4e\x05\x32\x00\x00\x0c\xfe\x0c\xff\x0c\xff\x0c\xfb\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0e\x00\x0e\x00"
        b"\x0e\x0e\x72\x08\x98\x00\x64\x00\x5c\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x55"
        b"\xd4\xa8\x00\x0e\x0e\x00\x00\x00\x00\x00\x04\x0f\xa0\x00\x00\xe1\x65",
        b"\x01\x03\x4e\x05\x32\x00\x00\x0c\xfe\x0c\xff\x0c\xff\x0c\xfb\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0e\x00\x0e\x00"
        b"\x0e\x0e\x72\x08\x98\x00\x64\x00\x5c\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x55"
        b"\xd4\xa8\x00\x0e\x0e\x00\x00\x00\x00\x00\x04\x0f\xa0\x00\x00\xe0\x65\x00",
        b"\x01\03",
    ],
    ids=["wrong_SOF", "wrong_CRC", "wrong_LEN", "too_short"],
)
async def test_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
    patch_bleak_client,
    patch_bms_timeout,
    wrong_response: bytes,
) -> None:
    """Test data up date with EG4 BMS returning invalid data."""

    patch_bms_timeout("eg4_bms")
    monkeypatch.setattr(MockEG4BleakClient, "_RESP", bytearray(wrong_response))
    patch_bleak_client(MockEG4BleakClient)

    bms = EG4BMS(generate_ble_device())

    result: BMSSample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()


async def test_fragmented_packet_normal(patch_bleak_client) -> None:
    """Test normal fragmented packet handling (split into two parts)."""
    patch_bleak_client(MockEG4BleakClient)

    # The response is 83 bytes total. Split into first chunk (75 bytes) and second chunk (8 bytes)
    full_response = MockEG4BleakClient._RESP[b"\x01\x03\x00\x00\x00\x27\x05\xd0"]

    eg4_bms = EG4BMS(generate_ble_device())

    # First fragment - 75 bytes (incomplete, needs 83)
    first_fragment = full_response[:75]
    assert len(first_fragment) < 83
    eg4_bms._notification_handler(None, first_fragment)
    assert not eg4_bms._msg_event.is_set()

    # Second fragment - completes the frame
    second_fragment = full_response[75:]
    eg4_bms._notification_handler(None, second_fragment)
    assert eg4_bms._msg_event.is_set()  # Event should be set after completing frame

    await eg4_bms.disconnect()


async def test_fragmented_packet_multiple_chunks(patch_bleak_client) -> None:
    """Test fragmented packet with multiple small chunks."""
    patch_bleak_client(MockEG4BleakClient)

    full_response = MockEG4BleakClient._RESP[b"\x01\x03\x00\x00\x00\x27\x05\xd0"]
    eg4_bms = EG4BMS(generate_ble_device())

    # Split into 4 chunks of ~20 bytes each
    chunk_size = 20
    chunks = [full_response[i:i+chunk_size] for i in range(0, len(full_response), chunk_size)]

    assert sum(len(c) for c in chunks) == len(full_response)

    # Process all chunks
    for chunk in chunks:
        eg4_bms._notification_handler(None, bytearray(chunk))

    # All data should be accumulated and frame completed successfully
    assert eg4_bms._msg_event.is_set()

    await eg4_bms.disconnect()


async def test_fragmented_packet_out_of_order(patch_bleak_client) -> None:
    """Test handling of out-of-order fragments."""
    patch_bleak_client(MockEG4BleakClient)

    full_response = MockEG4BleakClient._RESP[b"\x103\x00\x00\x00\x27\x05\xd0"]
    eg4_bms = EG4BMS(generate_ble_device())

    # Send second half first, then first half
    chunk2 = full_response[40:]
    chunk1 = full_response[:40]

    eg4_bms._notification_handler(None, bytearray(chunk2))
    # First fragment should be kept (no new HEAD marker)
    assert not eg4_bms._msg_event.is_set()

    eg4_bms._notification_handler(None, bytearray(chunk1))
    # Should accumulate correctly regardless of order
    assert not eg4_bms._msg_event.is_set()  # Still incomplete

    await eg4_bms.disconnect()


async def test_fragmented_packet_repeated(patch_bleak_client) -> None:
    """Test handling of repeated/retransmitted fragments."""
    patch_bleak_client(MockEG4BleakClient)

    full_response = MockEG4BleakClient._RESP[b"\x01\x03\x00\x00\x00\x27\x05\xd0"]
    eg4_bms = EG4BMS(generate_ble_device())

    # Send the same fragment twice
    first_chunk = full_response[:30]

    eg4_bms._notification_handler(None, bytearray(first_chunk))
    assert not eg4_bms._msg_event.is_set()

    # Same fragment again - should be handled gracefully (no duplicate data)
    eg4_bms._notification_handler(None, bytearray(first_chunk))
    assert not eg4_bms._msg_event.is_set()

    await eg4_bms.disconnect()


async def test_fragmented_packet_too_short(patch_bleak_client) -> None:
    """Test handling of fragments that are too short."""
    patch_bleak_client(MockEG4BleakClient)

    full_response = MockEG4BleakClient._RESP[b"\x01\x03\x00\x00\x00\x27\x05\xd0"]
    eg4_bms = EG4BMS(generate_ble_device())

    # Send only 1 byte fragment
    single_byte = full_response[:1]
    eg4_bms._notification_handler(None, bytearray(single_byte))
    assert not eg4_bms._msg_event.is_set()

    # Should keep accumulating
    next_chunk = full_response[1:50]
    eg4_bms._notification_handler(None, bytearray(next_chunk))
    assert not eg4_bms._msg_event.is_set()  # Still incomplete

    await eg4_bms.disconnect()


async def test_fragmented_packet_too_long(patch_bleak_client) -> None:
    """Test handling of fragments that exceed expected length (should be truncated)."""
    patch_bleak_client(MockEG4BleakClient)

    full_response = MockEG4BleakClient._RESP[b"\x01\x03\x00\x00\x00\x27\x05\xd0"]
    eg4_bms = EG4BMS(generate_ble_device())

    # Send complete frame + extra bytes
    extended_data = full_response + b"\x00\x00\x00"  # Add 3 extra bytes

    eg4_bms._notification_handler(None, bytearray(extended_data))
    # Frame should be processed correctly (CRC at end)
    assert not eg4_bms._msg_event.is_set()  # CRC check will fail with wrong checksum

    await eg4_bms.disconnect()


async def test_fragmented_packet_garbled_data(patch_bleak_client) -> None:
    """Test handling of garbled/corrupted data in fragments."""
    patch_bleak_client(MockEG4BleakClient)

    full_response = MockEG4BleakClient._RESP[b"\x01\x03\x00\x00\x00\x27\x05\xd0"]
    eg4_bms = EG4BMS(generate_ble_device())

    # Send good data, then garbled fragment
    good_chunk = full_response[:50]
    garbled_chunk = bytearray(b"\xff\xff\xff\xff\xff")  # All 1s - corrupted

    eg4_bms._notification_handler(None, bytearray(good_chunk))
    assert not eg4_bms._msg_event.is_set()

    eg4_bms._notification_handler(None, garbled_chunk)
    # Should keep accumulating but CRC will fail
    assert not eg4_bms._msg_event.is_set()

    await eg4_bms.disconnect()


async def test_fragmented_packet_multiple_frames(patch_bleak_client) -> None:
    """Test handling of multiple consecutive frames arriving as fragments."""
    patch_bleak_client(MockEG4BleakClient)

    full_response = MockEG4BleakClient._RESP[b"\x01\x03\x00\x00\x00\x27\x05\xd0"]
    eg4_bms = EG4BMS(generate_ble_device())

    # Simulate two complete frames arriving as fragments
    chunk1 = full_response[:40]
    chunk2 = full_response[40:]

    # First frame
    eg4_bms._notification_handler(None, bytearray(chunk1))
    assert not eg4_bms._msg_event.is_set()

    eg4_bms._notification_handler(None, bytearray(chunk2))
    assert eg4_bms._msg_event.is_set()  # First frame complete

    # Reset for second frame
    eg4_bms._frame = bytearray()
    eg4_bms._exp_len = EG4BMS._MIN_LEN
    eg4_bms._frame_complete = False
    eg4_bms._msg_event.clear()

    # Second frame (same data)
    eg4_bms._notification_handler(None, bytearray(chunk1))
    assert not eg4_bms._msg_event.is_set()

    eg4_bms._notification_handler(None, bytearray(chunk2))
    assert eg4_bms._msg_event.is_set()  # Second frame complete

    await eg4_bms.disconnect()


@pytest.mark.parametrize(
    "problem_response",
    [
        b"\x01\x03\x4e\x05\x32\x00\x00\x0c\xfe\x0c\xff\x0c\xff\x0c\xfb\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0e\x00\x0e\x00"
        b"\x0e\x0e\x72\x08\x98\x00\x64\x00\x5c\x03\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x05\x55"
        b"\xd4\xa8\x00\x0e\x0e\x00\x00\x00\x00\x00\x04\x0f\xa0\x00\x00\x4a\x19",
        b"\x01\x03\x4e\x05\x32\x00\x00\x0c\xfe\x0c\xff\x0c\xff\x0c\xfb\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0e\x00\x0e\x00"
        b"\x0e\x0e\x72\x08\x98\x00\x64\x00\x5c\x03\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x05\x55"
        b"\xd4\xa8\x00\x0e\x0e\x00\x00\x00\x00\x00\x04\x0f\xa0\x00\x00\xf0\xb4",
    ],
    ids=["last_bit", "first_bit"],
)
async def test_problem_response(
    monkeypatch, patch_bleak_client, problem_response, request
) -> None:
    """Test data update with EG4 BMS returning error flags."""
    monkeypatch.setattr(MockEG4BleakClient, "_RESP", bytearray(problem_response))
    patch_bleak_client(MockEG4BleakClient)
    bms = EG4BMS(generate_ble_device())

    assert await bms.async_update() == _RESULT_DEFS | {
        "problem": True,
        "problem_code": (1 if request.node.callspec.id == "first_bit" else 2**47),
    }

    await bms.disconnect()
