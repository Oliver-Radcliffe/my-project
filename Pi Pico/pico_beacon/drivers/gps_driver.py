# GPS Driver for Pico Beacon
# Handles UART communication with NMEA GPS modules

from machine import UART, Pin
import time


class GPSDriver:
    """Driver for NMEA GPS modules (NEO-6M, NEO-M8N, etc.)."""

    def __init__(self, uart_id=0, tx_pin=0, rx_pin=1, baudrate=9600):
        """Initialize GPS driver.

        Args:
            uart_id: UART peripheral ID (0 or 1)
            tx_pin: GPIO pin for TX (to GPS RX)
            rx_pin: GPIO pin for RX (from GPS TX)
            baudrate: UART baudrate (default 9600)
        """
        self.uart = UART(uart_id, baudrate=baudrate,
                         tx=Pin(tx_pin), rx=Pin(rx_pin))

        # GPS data
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.speed_knots = 0.0
        self.speed_kmh = 0.0
        self.heading = None
        self.hdop = 99.9
        self.satellites = 0
        self.fix_quality = 0
        self.valid = False

        # Timestamp
        self.year = 2000
        self.month = 1
        self.day = 1
        self.hour = 0
        self.minute = 0
        self.second = 0

        # Internal parsing state
        self._buffer = bytearray(128)
        self._buf_idx = 0

    def update(self):
        """Read and parse available GPS data.

        Call this frequently (e.g., every 100ms) to process incoming NMEA sentences.

        Returns:
            bool: True if new valid position data was received
        """
        new_fix = False

        while self.uart.any():
            byte = self.uart.read(1)
            if byte is None:
                break

            char = byte[0]

            if char == ord('$'):
                # Start of new sentence
                self._buf_idx = 0
                self._buffer[self._buf_idx] = char
                self._buf_idx += 1

            elif char == ord('\n') or char == ord('\r'):
                # End of sentence
                if self._buf_idx > 0:
                    sentence = bytes(self._buffer[:self._buf_idx]).decode('ascii', 'ignore')
                    if self._parse_sentence(sentence):
                        new_fix = True
                    self._buf_idx = 0

            elif self._buf_idx < len(self._buffer) - 1:
                self._buffer[self._buf_idx] = char
                self._buf_idx += 1

        return new_fix

    def _parse_sentence(self, sentence):
        """Parse an NMEA sentence.

        Returns:
            bool: True if this was a position sentence with valid data
        """
        if not sentence.startswith('$'):
            return False

        # Verify checksum if present
        if '*' in sentence:
            data, checksum_str = sentence[1:].split('*', 1)
            try:
                expected = int(checksum_str[:2], 16)
                actual = 0
                for c in data:
                    actual ^= ord(c)
                if actual != expected:
                    return False
            except (ValueError, IndexError):
                pass
            sentence = '$' + data

        parts = sentence.split(',')
        msg_type = parts[0][3:] if len(parts[0]) > 3 else ''

        try:
            if msg_type == 'GGA':
                return self._parse_gga(parts)
            elif msg_type == 'RMC':
                return self._parse_rmc(parts)
            elif msg_type == 'GSA':
                self._parse_gsa(parts)
            elif msg_type == 'VTG':
                self._parse_vtg(parts)
        except (IndexError, ValueError):
            pass

        return False

    def _parse_gga(self, parts):
        """Parse GGA sentence (position and fix data)."""
        # $GPGGA,time,lat,N/S,lon,E/W,quality,sats,hdop,alt,M,geoid,M,age,station*cs

        if len(parts) < 10:
            return False

        # Fix quality (0=invalid, 1=GPS, 2=DGPS, etc.)
        if parts[6]:
            self.fix_quality = int(parts[6])
            self.valid = self.fix_quality > 0
        else:
            self.fix_quality = 0
            self.valid = False

        if not self.valid:
            return False

        # Time (HHMMSS.sss)
        if parts[1]:
            self._parse_time(parts[1])

        # Latitude (DDMM.MMMMM)
        if parts[2] and parts[3]:
            self.latitude = self._parse_coordinate(parts[2], parts[3])

        # Longitude (DDDMM.MMMMM)
        if parts[4] and parts[5]:
            self.longitude = self._parse_coordinate(parts[4], parts[5])

        # Satellites
        if parts[7]:
            self.satellites = int(parts[7])

        # HDOP
        if parts[8]:
            self.hdop = float(parts[8])

        # Altitude
        if parts[9]:
            self.altitude = float(parts[9])

        return True

    def _parse_rmc(self, parts):
        """Parse RMC sentence (recommended minimum data)."""
        # $GPRMC,time,status,lat,N/S,lon,E/W,speed,heading,date,magvar,E/W*cs

        if len(parts) < 10:
            return False

        # Status (A=active/valid, V=void)
        if parts[2]:
            self.valid = parts[2] == 'A'
        else:
            self.valid = False

        if not self.valid:
            return False

        # Time
        if parts[1]:
            self._parse_time(parts[1])

        # Date (DDMMYY)
        if parts[9]:
            self._parse_date(parts[9])

        # Latitude
        if parts[3] and parts[4]:
            self.latitude = self._parse_coordinate(parts[3], parts[4])

        # Longitude
        if parts[5] and parts[6]:
            self.longitude = self._parse_coordinate(parts[5], parts[6])

        # Speed (knots)
        if parts[7]:
            self.speed_knots = float(parts[7])
            self.speed_kmh = self.speed_knots * 1.852

        # Heading/course
        if parts[8]:
            self.heading = float(parts[8])
        else:
            self.heading = None

        return True

    def _parse_gsa(self, parts):
        """Parse GSA sentence (DOP and active satellites)."""
        # $GPGSA,mode,fix,sat1,sat2,...,sat12,pdop,hdop,vdop*cs

        if len(parts) < 17:
            return

        # HDOP
        if parts[16]:
            try:
                self.hdop = float(parts[16])
            except ValueError:
                pass

    def _parse_vtg(self, parts):
        """Parse VTG sentence (velocity and heading)."""
        # $GPVTG,heading,T,heading,M,speed,N,speed,K,mode*cs

        if len(parts) < 8:
            return

        # True heading
        if parts[1]:
            try:
                self.heading = float(parts[1])
            except ValueError:
                pass

        # Speed in km/h
        if parts[7]:
            try:
                self.speed_kmh = float(parts[7])
                self.speed_knots = self.speed_kmh / 1.852
            except ValueError:
                pass

    def _parse_time(self, time_str):
        """Parse NMEA time string (HHMMSS or HHMMSS.sss)."""
        if len(time_str) >= 6:
            self.hour = int(time_str[0:2])
            self.minute = int(time_str[2:4])
            self.second = int(float(time_str[4:]))

    def _parse_date(self, date_str):
        """Parse NMEA date string (DDMMYY)."""
        if len(date_str) >= 6:
            self.day = int(date_str[0:2])
            self.month = int(date_str[2:4])
            year = int(date_str[4:6])
            # Y2K handling
            self.year = 2000 + year if year < 80 else 1900 + year

    @staticmethod
    def _parse_coordinate(coord_str, direction):
        """Parse NMEA coordinate to decimal degrees.

        Args:
            coord_str: Coordinate string (DDMM.MMMMM or DDDMM.MMMMM)
            direction: Direction (N/S/E/W)

        Returns:
            float: Coordinate in decimal degrees
        """
        if not coord_str:
            return 0.0

        # Find the decimal point position
        dot_pos = coord_str.find('.')
        if dot_pos < 0:
            return 0.0

        # Degrees are everything before the last 2 digits before decimal
        # Minutes are the last 2 digits before decimal plus decimal part
        deg_end = dot_pos - 2
        if deg_end < 1:
            deg_end = dot_pos - 2  # Handle edge cases

        degrees = int(coord_str[:deg_end]) if deg_end > 0 else 0
        minutes = float(coord_str[deg_end:])

        # Convert to decimal degrees
        result = degrees + (minutes / 60.0)

        # Apply direction
        if direction in ('S', 'W'):
            result = -result

        return result

    def get_position(self):
        """Get current GPS position data.

        Returns:
            dict: GPS data suitable for CiNetMessage.build()
        """
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed': self.speed_kmh,
            'heading': self.heading,
            'hdop': self.hdop,
            'satellites': self.satellites,
            'valid': self.valid,
            'timestamp': (self.year, self.month, self.day,
                          self.hour, self.minute, self.second)
        }

    def wait_for_fix(self, timeout_sec=60, callback=None):
        """Wait for a GPS fix.

        Args:
            timeout_sec: Maximum time to wait (seconds)
            callback: Optional callback(elapsed_sec, satellites) called each second

        Returns:
            bool: True if fix acquired, False if timeout
        """
        start = time.ticks_ms()
        timeout_ms = timeout_sec * 1000

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            self.update()

            if self.valid:
                return True

            elapsed = time.ticks_diff(time.ticks_ms(), start) // 1000
            if callback:
                callback(elapsed, self.satellites)

            time.sleep_ms(100)

        return False

    def __repr__(self):
        status = "FIX" if self.valid else "NO FIX"
        return f"GPS({self.latitude:.6f}, {self.longitude:.6f}, {status}, sats={self.satellites})"
