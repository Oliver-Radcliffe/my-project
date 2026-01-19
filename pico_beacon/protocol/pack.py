# Data packing utilities for ciNet protocol
# Optimized for MicroPython on RP2040

def pack2(buf, offset, value):
    """Pack a 16-bit value (big-endian) into buffer at offset."""
    buf[offset] = (value >> 8) & 0xFF
    buf[offset + 1] = value & 0xFF

def pack4(buf, offset, value):
    """Pack a 32-bit value (big-endian) into buffer at offset."""
    buf[offset] = (value >> 24) & 0xFF
    buf[offset + 1] = (value >> 16) & 0xFF
    buf[offset + 2] = (value >> 8) & 0xFF
    buf[offset + 3] = value & 0xFF

def unpack2(buf, offset):
    """Unpack a 16-bit value (big-endian) from buffer at offset."""
    return (buf[offset] << 8) | buf[offset + 1]

def unpack4(buf, offset):
    """Unpack a 32-bit value (big-endian) from buffer at offset."""
    return ((buf[offset] << 24) |
            (buf[offset + 1] << 16) |
            (buf[offset + 2] << 8) |
            buf[offset + 3])

def swap2(value):
    """Swap bytes in a 16-bit value."""
    return ((value >> 8) & 0xFF) | ((value & 0xFF) << 8)

def pack_signed4(buf, offset, value):
    """Pack a signed 32-bit value (big-endian) into buffer."""
    if value < 0:
        value = value & 0xFFFFFFFF  # Convert to unsigned representation
    pack4(buf, offset, value)

def string_to_buffer(string, buf, max_len=None):
    """Copy string to buffer, null-padded."""
    if max_len is None:
        max_len = len(buf)
    length = min(len(string), max_len - 1)
    for i in range(length):
        buf[i] = ord(string[i])
    for i in range(length, max_len):
        buf[i] = 0

def buffer_to_string(buf, max_len=None):
    """Convert buffer to string, stopping at null."""
    if max_len is None:
        max_len = len(buf)
    result = ""
    for i in range(max_len):
        if buf[i] == 0:
            break
        result += chr(buf[i])
    return result
