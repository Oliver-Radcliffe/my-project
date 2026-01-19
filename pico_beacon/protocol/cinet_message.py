# ciNet Message Builder for Pico Beacon
# Builds 149-byte ciNet protocol messages compatible with Millitag devices

from .pack import pack2, pack4, pack_signed4, string_to_buffer
from .crc import CRC16
from .blowfish import Blowfish, derive_key


class CiNetMessage:
    """Builder for ciNet protocol messages."""

    # Message structure constants
    MSG_LENGTH = 149
    HEADER_LENGTH = 51
    ENCRYPTED_LENGTH = 96
    ENCRYPTED_BLOCKS = 12  # 96 bytes / 8 bytes per block

    # Fixed protocol values
    START_BYTE = 0x24       # '$'
    PACKET_TYPE = 0x55      # 'U'
    CINET_TYPE = 0x44       # 'D'
    MESSAGE_TYPE = 0x02
    ALARM_DEFAULT = 0xFF
    MILLITAG_SPECIFIC_LEN = 0x2E  # 46 bytes

    def __init__(self, config):
        """Initialize message builder with configuration.

        Args:
            config: ConfigManager instance with device settings
        """
        self.config = config
        self.sequence = 0

        # Pre-compute encryption key from passphrase
        passphrase = config.get("passphrase", "fredfred")
        self._key = derive_key(passphrase)
        self._cipher = Blowfish(self._key)

        # Cache device identity bytes
        self._cinet_key = config.get_cinet_key_bytes()
        self._serial = config.get_serial_bytes()
        self._client_name = config.get_client_name_bytes()
        self._source_type = config.get_source_type_bytes()
        self._operator = config.get_operator_bytes()

        # Pre-allocate message buffer
        self._buffer = bytearray(self.MSG_LENGTH)

    def build(self, gps_data, device_status=None):
        """Build a complete ciNet message.

        Args:
            gps_data: dict with GPS data:
                - latitude: float (degrees, negative for S)
                - longitude: float (degrees, negative for W)
                - altitude: float (meters, optional)
                - speed: float (km/h, optional)
                - heading: float (degrees, optional)
                - hdop: float (optional)
                - satellites: int (optional)
                - valid: bool (GPS fix status)
                - timestamp: tuple (year, month, day, hour, min, sec)

            device_status: dict with device status (optional):
                - battery: int (0-100 percentage)
                - temperature: int (Celsius)
                - rssi: int (signal strength)
                - motion: int (motion state)

        Returns:
            bytearray: Complete 149-byte message ready to send
        """
        buf = self._buffer

        # Increment sequence number (0-255)
        self.sequence = (self.sequence + 1) & 0xFF

        # Get timestamp from GPS or use current time placeholder
        if gps_data.get('timestamp'):
            ts = gps_data['timestamp']
            year, month, day, hour, minute, second = ts
        else:
            # Default timestamp (will be overwritten with actual time)
            year, month, day, hour, minute, second = 2024, 1, 1, 0, 0, 0

        datong_ts = self._encode_datong_timestamp(year, month, day, hour, minute, second)

        # Build plain header (bytes 0-50)
        self._build_header(buf, datong_ts)

        # Build encrypted payload (bytes 51-146)
        self._build_payload(buf, gps_data, device_status, datong_ts)

        # Calculate encrypted data CRC (bytes 55-146 -> stored at 53-54)
        crc_value = CRC16.calculate(buf, 55, 92)
        buf[53] = (~crc_value) & 0xFF
        buf[54] = (~(crc_value >> 8)) & 0xFF

        # Encrypt payload (bytes 51-146, 96 bytes = 12 blocks)
        self._cipher.encrypt(buf, 51, self.ENCRYPTED_BLOCKS)

        # Calculate overall message CRC (bytes 0-146 -> stored at 147-148)
        crc_value = CRC16.calculate(buf, 0, 147)
        buf[147] = (~crc_value) & 0xFF
        buf[148] = (~(crc_value >> 8)) & 0xFF

        return buf

    def _build_header(self, buf, datong_ts):
        """Build the plain-text header (bytes 0-50)."""
        # Byte 0: Start byte
        buf[0] = self.START_BYTE

        # Byte 1: Packet type
        buf[1] = self.PACKET_TYPE

        # Bytes 2-3: Message length (big-endian)
        pack2(buf, 2, self.MSG_LENGTH)

        # Byte 4: Sequence number
        buf[4] = self.sequence

        # Bytes 5-8: ciNet key (big-endian)
        pack4(buf, 5, self._cinet_key)

        # Byte 9: ciNet type
        buf[9] = self.CINET_TYPE

        # Bytes 10-21: Source type (12 bytes)
        buf[10:22] = self._source_type

        # Bytes 22-45: Source ID / Serial number (24 bytes)
        buf[22:46] = self._serial

        # Bytes 46-50: Datong timestamp (5 bytes)
        buf[46:51] = datong_ts

    def _build_payload(self, buf, gps_data, device_status, datong_ts):
        """Build the encrypted payload (bytes 51-146)."""
        status = device_status or {}

        # Bytes 51-52: Encrypted data length
        pack2(buf, 51, self.ENCRYPTED_LENGTH)

        # Bytes 53-54: CRC placeholder (filled later)
        buf[53] = 0
        buf[54] = 0

        # Byte 55: Message type
        buf[55] = self.MESSAGE_TYPE

        # Bytes 56-75: Client name (20 bytes)
        buf[56:76] = self._client_name

        # Bytes 76-79: Latitude (int32, degrees * 60000)
        lat = gps_data.get('latitude', 0.0)
        lat_int = int(lat * 60000)
        pack_signed4(buf, 76, lat_int)

        # Bytes 80-83: Longitude (int32, degrees * 60000)
        lon = gps_data.get('longitude', 0.0)
        lon_int = int(lon * 60000)
        pack_signed4(buf, 80, lon_int)

        # Bytes 84-85: Heading (uint16, degrees * 100, or 0xFFFF if invalid)
        heading = gps_data.get('heading')
        if heading is not None:
            pack2(buf, 84, int(heading * 100) & 0xFFFF)
        else:
            pack2(buf, 84, 0xFFFF)

        # Bytes 86-87: Speed (uint16)
        speed = gps_data.get('speed', 0)
        pack2(buf, 86, int(speed) & 0xFFFF)

        # Bytes 88-92: GPS timestamp (5 bytes, same as datong)
        buf[88:93] = datong_ts

        # Bytes 93-94: HDOP (uint16, * 100)
        hdop = gps_data.get('hdop', 99.9)
        pack2(buf, 93, int(hdop * 100) & 0xFFFF)

        # Byte 95: GPS valid (1 = fix, 0 = no fix)
        buf[95] = 1 if gps_data.get('valid', False) else 0

        # Byte 96: Motion state
        buf[96] = status.get('motion', 0)

        # Byte 97: Alarm
        buf[97] = self.ALARM_DEFAULT

        # === Millitag-specific data (bytes 98-146) ===

        # Bytes 98-99: Millitag specific length
        pack2(buf, 98, self.MILLITAG_SPECIFIC_LEN)

        # Byte 100: Battery level (0-100)
        buf[100] = min(100, max(0, status.get('battery', 100)))

        # Byte 101: Temperature (signed byte, Celsius)
        temp = status.get('temperature', 20)
        buf[101] = temp & 0xFF

        # Byte 102: Satellites used
        buf[102] = gps_data.get('satellites', 0) & 0xFF

        # Bytes 103-106: RSSI (int32)
        pack4(buf, 103, status.get('rssi', 0) & 0xFFFFFFFF)

        # Bytes 107-110: RSSI bit error rate (int32)
        pack4(buf, 107, 0)

        # Bytes 111-112: Status flags (uint16)
        pack2(buf, 111, status.get('status_flags', 0))

        # Bytes 113-114: LAC (uint16)
        pack2(buf, 113, status.get('lac', 0))

        # Bytes 115-116: Cell ID (uint16)
        pack2(buf, 115, status.get('cell_id', 0))

        # Bytes 117-118: Act (uint16)
        pack2(buf, 117, status.get('act', 7))

        # Bytes 119-126: Current numeric operator (8 bytes)
        buf[119:127] = self._operator

        # Byte 127: SW version major
        buf[127] = self.config.get('fw_version_major', 1)

        # Byte 128: SW version minor
        buf[128] = self.config.get('fw_version_minor', 0)

        # Byte 129: SW version tertiary
        buf[129] = self.config.get('fw_version_patch', 0)

        # Bytes 130-133: Log limits earliest (uint32)
        pack4(buf, 130, 0)

        # Bytes 134-137: Log limits latest (uint32)
        pack4(buf, 134, 0)

        # Byte 138: Current beacon mode
        buf[138] = status.get('beacon_mode', 0)

        # Byte 139: Current motion sensitivity
        buf[139] = status.get('motion_sensitivity', 1)

        # Byte 140: Wake trigger
        buf[140] = status.get('wake_trigger', 0)

        # Byte 141: Current output switch state
        buf[141] = status.get('output_state', 0)

        # Byte 142: Current geozone
        buf[142] = status.get('geozone', 0)

        # Byte 143: Input switch state
        buf[143] = status.get('input_state', 0)

        # Bytes 144-145: Alerts flag (uint16)
        pack2(buf, 144, status.get('alerts', 0))

        # Byte 146: Padding
        buf[146] = 0

    @staticmethod
    def _encode_datong_timestamp(year, month, day, hour, minute, second):
        """Encode date/time to Datong 5-byte timestamp format.

        Args:
            year: 4-digit year (1980-2107)
            month: 1-12
            day: 1-31
            hour: 0-23
            minute: 0-59
            second: 0-59

        Returns:
            bytearray: 5-byte Datong timestamp
        """
        ts = bytearray(5)

        # Byte 0: day (5 bits) | month high (3 bits)
        ts[0] = ((day & 0x1F) << 3) | ((month >> 1) & 0x07)

        # Byte 1: year-1980 (7 bits) | month low (1 bit)
        ts[1] = ((year - 1980) & 0x7F) | ((month & 0x01) << 7)

        # Byte 2: hour (5 bits) | minute high (3 bits)
        ts[2] = ((hour & 0x1F) << 3) | ((minute >> 3) & 0x07)

        # Byte 3: minute low (3 bits) | second high (5 bits)
        ts[3] = ((minute & 0x07) << 5) | ((second >> 1) & 0x1F)

        # Byte 4: second low (1 bit) | padding (7 bits)
        ts[4] = (second & 0x01) << 7

        return ts

    @staticmethod
    def decode_datong_timestamp(ts):
        """Decode Datong 5-byte timestamp to components.

        Args:
            ts: 5-byte Datong timestamp

        Returns:
            tuple: (year, month, day, hour, minute, second)
        """
        day = (ts[0] >> 3) & 0x1F
        month = ((ts[0] & 0x07) << 1) | ((ts[1] >> 7) & 0x01)
        year = (ts[1] & 0x7F) + 1980

        hour = (ts[2] >> 3) & 0x1F
        minute = ((ts[2] & 0x07) << 3) | ((ts[3] >> 5) & 0x07)
        second = ((ts[3] & 0x1F) << 1) | ((ts[4] >> 7) & 0x01)

        return (year, month, day, hour, minute, second)


class GPSData:
    """Container for GPS position data."""

    def __init__(self):
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.speed = 0.0
        self.heading = None
        self.hdop = 99.9
        self.satellites = 0
        self.valid = False
        self.timestamp = None

    def to_dict(self):
        """Convert to dictionary for message builder."""
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed': self.speed,
            'heading': self.heading,
            'hdop': self.hdop,
            'satellites': self.satellites,
            'valid': self.valid,
            'timestamp': self.timestamp
        }

    def __repr__(self):
        fix = "FIX" if self.valid else "NO FIX"
        return f"GPS({self.latitude:.6f}, {self.longitude:.6f}, {fix}, sats={self.satellites})"


class DeviceStatus:
    """Container for device status data."""

    def __init__(self):
        self.battery = 100
        self.temperature = 20
        self.rssi = 0
        self.motion = 0
        self.status_flags = 0
        self.lac = 0
        self.cell_id = 0
        self.act = 7
        self.beacon_mode = 0
        self.motion_sensitivity = 1
        self.wake_trigger = 0
        self.output_state = 0
        self.geozone = 0
        self.input_state = 0
        self.alerts = 0

    def to_dict(self):
        """Convert to dictionary for message builder."""
        return {
            'battery': self.battery,
            'temperature': self.temperature,
            'rssi': self.rssi,
            'motion': self.motion,
            'status_flags': self.status_flags,
            'lac': self.lac,
            'cell_id': self.cell_id,
            'act': self.act,
            'beacon_mode': self.beacon_mode,
            'motion_sensitivity': self.motion_sensitivity,
            'wake_trigger': self.wake_trigger,
            'output_state': self.output_state,
            'geozone': self.geozone,
            'input_state': self.input_state,
            'alerts': self.alerts
        }
