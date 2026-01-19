# Protocol Tests for Pico Beacon
# Validates CRC, Blowfish, and message building against known-good data
#
# Run on desktop Python (not MicroPython) for testing:
#   python -m pytest tests/test_protocol.py -v

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocol.crc import CRC16
from protocol.blowfish import Blowfish, derive_key
from protocol.pack import pack2, pack4, unpack2, unpack4
from protocol.cinet_message import CiNetMessage


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self):
        self._config = {
            "passphrase": "fredfred",
            "cinet_key": "06.EA.83.A3",
            "serial_number": "0001576627",
            "client_name": "Python Simulator",
            "source_type": "Millitag",
            "fw_version_major": 2,
            "fw_version_minor": 7,
            "fw_version_patch": 4,
        }

    def get(self, key, default=None):
        return self._config.get(key, default)

    def get_cinet_key_bytes(self):
        key_str = self._config["cinet_key"]
        parts = key_str.split('.')
        key_int = 0
        for i, part in enumerate(parts):
            key_int |= int(part, 16) << (24 - i * 8)
        return key_int

    def get_serial_bytes(self):
        serial = self._config["serial_number"][:23]
        buf = bytearray(24)
        for i, c in enumerate(serial):
            buf[i] = ord(c)
        return buf

    def get_client_name_bytes(self):
        name = self._config["client_name"][:19]
        buf = bytearray(20)
        for i, c in enumerate(name):
            buf[i] = ord(c)
        return buf

    def get_source_type_bytes(self):
        src = self._config["source_type"][:11]
        buf = bytearray(12)
        for i, c in enumerate(src):
            buf[i] = ord(c)
        return buf

    def get_operator_bytes(self):
        buf = bytearray(8)
        op = "O2 - UK"
        for i, c in enumerate(op[:7]):
            buf[i] = ord(c)
        return buf


def test_crc16_basic():
    """Test CRC16 calculation."""
    # Test with known data
    data = bytearray([0x01, 0x02, 0x03, 0x04])
    crc = CRC16.calculate(data)
    print(f"CRC16 of [01,02,03,04]: {crc:04X}")
    assert crc > 0, "CRC should be non-zero"


def test_crc16_inverted():
    """Test inverted CRC16 (as used in ciNet)."""
    data = bytearray(b"Hello World")
    crc = CRC16.calculate(data)
    inv_crc = CRC16.calculate_inverted(data)

    assert inv_crc == (~crc) & 0xFFFF, "Inverted CRC should be bitwise NOT"
    print(f"CRC16: {crc:04X}, Inverted: {inv_crc:04X}")


def test_key_derivation():
    """Test PBKDF2 key derivation."""
    key = derive_key("fredfred")

    print(f"Derived key ({len(key)} bytes): {key.hex()}")
    assert len(key) == 32, "Key should be 32 bytes"

    # The key should be deterministic
    key2 = derive_key("fredfred")
    assert key == key2, "Same passphrase should produce same key"

    # Different passphrase should produce different key
    key3 = derive_key("different")
    assert key != key3, "Different passphrase should produce different key"


def test_blowfish_encrypt_decrypt():
    """Test Blowfish encryption/decryption roundtrip."""
    key = derive_key("fredfred")
    cipher = Blowfish(key)

    # Test data (must be multiple of 8 bytes)
    original = bytearray(b"This is a test message!12345678")
    data = bytearray(original)  # Copy for encryption

    # Encrypt
    cipher.encrypt(data, 0, len(data) // 8)
    print(f"Original: {original.hex()}")
    print(f"Encrypted: {data.hex()}")

    assert data != original, "Encrypted data should differ from original"

    # Decrypt
    cipher2 = Blowfish(key)  # New instance
    cipher2.decrypt(data, 0, len(data) // 8)
    print(f"Decrypted: {data.hex()}")

    assert data == original, "Decrypted data should match original"


def test_pack_unpack():
    """Test pack/unpack functions."""
    buf = bytearray(8)

    # Test 16-bit
    pack2(buf, 0, 0x1234)
    assert buf[0] == 0x12 and buf[1] == 0x34, "pack2 should be big-endian"
    assert unpack2(buf, 0) == 0x1234, "unpack2 should match"

    # Test 32-bit
    pack4(buf, 2, 0xDEADBEEF)
    assert buf[2:6] == bytearray([0xDE, 0xAD, 0xBE, 0xEF]), "pack4 should be big-endian"
    assert unpack4(buf, 2) == 0xDEADBEEF, "unpack4 should match"


def test_datong_timestamp():
    """Test Datong timestamp encoding/decoding."""
    # Test encode
    ts = CiNetMessage._encode_datong_timestamp(2024, 12, 26, 4, 37, 0)
    print(f"Encoded timestamp: {ts.hex()}")

    # Decode and verify
    year, month, day, hour, minute, second = CiNetMessage.decode_datong_timestamp(ts)
    print(f"Decoded: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")

    assert year == 2024
    assert month == 12
    assert day == 26
    assert hour == 4
    assert minute == 37
    assert second == 0


def test_message_build():
    """Test building a complete ciNet message."""
    config = MockConfig()
    builder = CiNetMessage(config)

    gps_data = {
        'latitude': 53.82720,
        'longitude': -1.66470,
        'altitude': 100.0,
        'speed': 0,
        'heading': None,
        'hdop': 1.5,
        'satellites': 10,
        'valid': True,
        'timestamp': (2024, 12, 26, 4, 37, 0)
    }

    device_status = {
        'battery': 100,
        'temperature': 20,
        'rssi': -70,
        'motion': 0
    }

    message = builder.build(gps_data, device_status)

    print(f"\nBuilt message ({len(message)} bytes):")
    print(f"Header: {message[:51].hex()}")
    print(f"Encrypted: {message[51:147].hex()}")
    print(f"CRC: {message[147:149].hex()}")

    # Verify structure
    assert len(message) == 149, "Message should be 149 bytes"
    assert message[0] == 0x24, "Start byte should be '$'"
    assert message[1] == 0x55, "Packet type should be 'U'"
    assert (message[2] << 8 | message[3]) == 149, "Length should be 149"
    assert message[9] == 0x44, "ciNet type should be 'D'"

    # Verify source type
    source_type = bytes(message[10:22]).rstrip(b'\x00').decode()
    print(f"Source type: '{source_type}'")
    assert source_type == "Millitag"


def test_message_sequence():
    """Test message sequence number increments."""
    config = MockConfig()
    builder = CiNetMessage(config)

    gps_data = {'latitude': 0, 'longitude': 0, 'valid': False}

    msg1 = builder.build(gps_data)
    seq1 = msg1[4]

    msg2 = builder.build(gps_data)
    seq2 = msg2[4]

    msg3 = builder.build(gps_data)
    seq3 = msg3[4]

    print(f"Sequence numbers: {seq1}, {seq2}, {seq3}")

    assert seq2 == (seq1 + 1) & 0xFF, "Sequence should increment"
    assert seq3 == (seq2 + 1) & 0xFF, "Sequence should continue incrementing"


def test_coordinate_encoding():
    """Test GPS coordinate encoding."""
    # Positive latitude
    lat = 53.82720
    lat_encoded = int(lat * 60000)
    print(f"Latitude {lat} -> {lat_encoded} (0x{lat_encoded:08X})")
    assert lat_encoded == 3229632

    # Negative longitude
    lon = -1.66470
    lon_encoded = int(lon * 60000)
    print(f"Longitude {lon} -> {lon_encoded} (0x{lon_encoded & 0xFFFFFFFF:08X})")
    assert lon_encoded == -99882


def run_all_tests():
    """Run all tests (for MicroPython compatibility)."""
    print("=" * 50)
    print("Running Protocol Tests")
    print("=" * 50)

    tests = [
        test_crc16_basic,
        test_crc16_inverted,
        test_key_derivation,
        test_blowfish_encrypt_decrypt,
        test_pack_unpack,
        test_datong_timestamp,
        test_coordinate_encoding,
        test_message_build,
        test_message_sequence,
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\n--- {test.__name__} ---")
        try:
            test()
            print("PASSED")
            passed += 1
        except AssertionError as e:
            print(f"FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
