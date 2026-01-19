# SIM7080G Cat-M/NB-IoT Driver for Waveshare Pico-SIM7080G
# Combined cellular modem and GNSS driver using AT commands
#
# Key features:
# - Cat-M1 / NB-IoT cellular connectivity
# - Integrated GNSS (GPS, GLONASS, BeiDou, Galileo)
# - UDP socket communication (TCP not supported with GNSS active)
# - Low power PSM mode support

from machine import UART, Pin
import time


class SIM7080G:
    """Driver for Waveshare Pico-SIM7080G Cat-M/NB-IoT module.

    This module combines cellular modem and GNSS in one chip.
    Note: TCP does not work while GNSS is active - use UDP instead.
    """

    # Default pins for Waveshare Pico-SIM7080G board
    DEFAULT_UART_ID = 0
    DEFAULT_TX_PIN = 0   # GP0
    DEFAULT_RX_PIN = 1   # GP1
    DEFAULT_PWR_PIN = 14  # GP14 - Power key
    DEFAULT_BAUDRATE = 115200

    def __init__(self, uart_id=None, tx_pin=None, rx_pin=None, pwr_pin=None,
                 baudrate=None, apn="internet"):
        """Initialize SIM7080G driver.

        Args:
            uart_id: UART peripheral ID (default 0)
            tx_pin: GPIO pin for TX (default GP0)
            rx_pin: GPIO pin for RX (default GP1)
            pwr_pin: GPIO pin for power key (default GP14)
            baudrate: UART baudrate (default 115200)
            apn: Cellular APN name
        """
        self.uart = UART(
            uart_id if uart_id is not None else self.DEFAULT_UART_ID,
            baudrate=baudrate if baudrate is not None else self.DEFAULT_BAUDRATE,
            tx=Pin(tx_pin if tx_pin is not None else self.DEFAULT_TX_PIN),
            rx=Pin(rx_pin if rx_pin is not None else self.DEFAULT_RX_PIN)
        )

        pwr = pwr_pin if pwr_pin is not None else self.DEFAULT_PWR_PIN
        self.pwr_pin = Pin(pwr, Pin.OUT) if pwr is not None else None

        self.apn = apn

        # Module state
        self._powered = False
        self._registered = False
        self._pdp_active = False
        self._gnss_enabled = False
        self._connected = False
        self._last_error = None

        # Network info
        self._rssi = 0
        self._operator = ""
        self._ip_address = ""

        # GNSS data
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.speed_kmh = 0.0
        self.heading = 0.0
        self.hdop = 99.9
        self.satellites = 0
        self.gnss_valid = False

        # Timestamp from GNSS
        self.year = 2000
        self.month = 1
        self.day = 1
        self.hour = 0
        self.minute = 0
        self.second = 0

    def power_on(self):
        """Power on the SIM7080G module."""
        if self.pwr_pin is None:
            return True

        # Check if already powered
        ok, _ = self._send_at("AT", timeout_ms=1000)
        if ok:
            self._powered = True
            return True

        # Pulse power key (>1s for power on)
        self.pwr_pin.value(1)
        time.sleep(1.5)
        self.pwr_pin.value(0)

        # Wait for module to boot
        time.sleep(3.0)

        # Verify communication
        for _ in range(5):
            ok, _ = self._send_at("AT", timeout_ms=1000)
            if ok:
                self._powered = True
                return True
            time.sleep(0.5)

        self._last_error = "Module not responding after power on"
        return False

    def power_off(self):
        """Power off the SIM7080G module."""
        # Send power down command
        self._send_at("AT+CPOWD=1", timeout_ms=5000, expect="NORMAL POWER DOWN")
        self._powered = False
        self._connected = False
        self._registered = False
        self._pdp_active = False

    def _send_at(self, command, timeout_ms=1000, expect="OK"):
        """Send AT command and wait for response.

        Args:
            command: AT command string
            timeout_ms: Response timeout in milliseconds
            expect: Expected response string (or None for any)

        Returns:
            tuple: (success: bool, response: str)
        """
        # Clear any pending data
        while self.uart.any():
            self.uart.read()

        # Send command
        if command:
            self.uart.write((command + "\r\n").encode())

        # Read response
        response = ""
        start = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self.uart.any():
                data = self.uart.read()
                if data:
                    response += data.decode('ascii', 'ignore')

                    if expect and expect in response:
                        return (True, response)
                    if "ERROR" in response:
                        return (False, response)

            time.sleep_ms(10)

        return (expect is None or expect in response, response)

    def _send_at_data(self, data, timeout_ms=5000):
        """Send raw data after AT+CASEND prompt.

        Args:
            data: bytes to send
            timeout_ms: Timeout in milliseconds

        Returns:
            bool: True if sent successfully
        """
        self.uart.write(data)

        # Wait for OK response
        response = ""
        start = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self.uart.any():
                chunk = self.uart.read()
                if chunk:
                    response += chunk.decode('ascii', 'ignore')
                    if "OK" in response:
                        return True
                    if "ERROR" in response:
                        return False
            time.sleep_ms(10)

        return False

    def init_module(self):
        """Initialize the SIM7080G module.

        Returns:
            bool: True if initialization successful
        """
        if not self._powered:
            if not self.power_on():
                return False

        # Disable echo
        self._send_at("ATE0")

        # Check SIM ready
        for _ in range(10):
            ok, resp = self._send_at("AT+CPIN?", timeout_ms=2000)
            if "READY" in resp:
                break
            time.sleep(1)
        else:
            self._last_error = "SIM not ready"
            return False

        # Set full functionality
        self._send_at("AT+CFUN=1", timeout_ms=5000)

        # Set preferred network mode (Cat-M preferred, NB-IoT fallback)
        # 1=Cat-M, 2=NB-IoT, 3=Cat-M and NB-IoT
        self._send_at("AT+CMNB=3")

        # Set LTE mode
        self._send_at("AT+CNMP=38")

        return True

    def connect(self, timeout_sec=120):
        """Connect to cellular network and activate PDP context.

        Args:
            timeout_sec: Connection timeout in seconds

        Returns:
            bool: True if connected successfully
        """
        if not self.init_module():
            return False

        start = time.ticks_ms()
        timeout_ms = timeout_sec * 1000

        # Wait for network registration
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            # Check EPS registration (for LTE)
            ok, resp = self._send_at("AT+CEREG?")
            if "+CEREG:" in resp:
                parts = resp.split(",")
                if len(parts) >= 2:
                    stat = parts[1].strip()
                    if stat in ("1", "5"):  # Home or roaming
                        self._registered = True
                        break

            # Also check CREG for 2G fallback
            ok, resp = self._send_at("AT+CREG?")
            if ",1" in resp or ",5" in resp:
                self._registered = True
                break

            time.sleep(2)

        if not self._registered:
            self._last_error = "Network registration failed"
            return False

        # Configure and activate PDP context using AT+CNACT
        # First, configure APN
        self._send_at(f'AT+CGDCONT=1,"IP","{self.apn}"')

        # Activate network using APP network commands
        self._send_at("AT+CNACT=0,0", timeout_ms=5000)  # Deactivate first
        time.sleep(0.5)

        ok, resp = self._send_at(f'AT+CNACT=0,1', timeout_ms=30000, expect="+APP PDP: 0,ACTIVE")
        if not ok:
            # Check if already active
            ok, resp = self._send_at("AT+CNACT?")
            if "+CNACT: 0,1" not in resp:
                self._last_error = "PDP activation failed"
                return False

        self._pdp_active = True
        self._connected = True

        # Get IP address
        ok, resp = self._send_at("AT+CNACT?")
        if "+CNACT:" in resp:
            try:
                # Format: +CNACT: 0,1,"10.x.x.x"
                parts = resp.split('"')
                if len(parts) >= 2:
                    self._ip_address = parts[1]
            except:
                pass

        self._update_network_info()
        self._last_error = None
        return True

    def disconnect(self):
        """Disconnect from cellular network."""
        self._send_at("AT+CNACT=0,0", timeout_ms=5000)
        self._pdp_active = False
        self._connected = False

    def is_connected(self):
        """Check if connected to network.

        Returns:
            bool: True if connected
        """
        if not self._pdp_active:
            return False

        ok, resp = self._send_at("AT+CNACT?")
        if ok and "+CNACT: 0,1" in resp:
            return True

        self._connected = False
        return False

    # =========================================================================
    # UDP Socket Methods (TCP not supported with GNSS active)
    # =========================================================================

    def send_udp(self, host, port, data):
        """Send data via UDP.

        Args:
            host: Server hostname or IP
            port: Server port
            data: bytes or bytearray to send

        Returns:
            bool: True if sent successfully
        """
        if not self._connected:
            self._last_error = "Not connected"
            return False

        # Close any existing connection
        self._send_at("AT+CACLOSE=0", timeout_ms=2000)
        time.sleep(0.2)

        # Open UDP connection
        # AT+CAOPEN=<cid>,<pdp_index>,<conn_type>,<server>,<port>
        cmd = f'AT+CAOPEN=0,0,"UDP","{host}",{port}'
        ok, resp = self._send_at(cmd, timeout_ms=10000, expect="+CAOPEN: 0,0")

        if not ok:
            self._last_error = f"UDP connection failed: {resp}"
            return False

        # Send data
        # AT+CASEND=<cid>,<length>
        data_len = len(data)
        ok, resp = self._send_at(f"AT+CASEND=0,{data_len}", timeout_ms=5000, expect=">")

        if not ok:
            self._last_error = "Send prompt not received"
            self._send_at("AT+CACLOSE=0")
            return False

        # Send actual data
        if not self._send_at_data(data, timeout_ms=10000):
            self._last_error = "Data send failed"
            self._send_at("AT+CACLOSE=0")
            return False

        # Close connection
        self._send_at("AT+CACLOSE=0", timeout_ms=2000)

        self._last_error = None
        return True

    def send_tcp(self, host, port, data, timeout_ms=10000):
        """Send data via TCP.

        Note: TCP does not work reliably while GNSS is active.
        Consider using send_udp() instead.

        Args:
            host: Server hostname or IP
            port: Server port
            data: bytes or bytearray to send
            timeout_ms: Timeout in milliseconds

        Returns:
            bool: True if sent successfully
        """
        if not self._connected:
            self._last_error = "Not connected"
            return False

        # Temporarily disable GNSS if enabled (TCP doesn't work with GNSS)
        gnss_was_enabled = self._gnss_enabled
        if gnss_was_enabled:
            self.gnss_stop()
            time.sleep(0.5)

        # Close any existing connection
        self._send_at("AT+CACLOSE=0", timeout_ms=2000)
        time.sleep(0.2)

        # Open TCP connection
        cmd = f'AT+CAOPEN=0,0,"TCP","{host}",{port}'
        ok, resp = self._send_at(cmd, timeout_ms=timeout_ms, expect="+CAOPEN: 0,0")

        if not ok:
            self._last_error = f"TCP connection failed: {resp}"
            if gnss_was_enabled:
                self.gnss_start()
            return False

        # Send data
        data_len = len(data)
        ok, resp = self._send_at(f"AT+CASEND=0,{data_len}", timeout_ms=5000, expect=">")

        if not ok:
            self._last_error = "Send prompt not received"
            self._send_at("AT+CACLOSE=0")
            if gnss_was_enabled:
                self.gnss_start()
            return False

        # Send actual data
        if not self._send_at_data(data, timeout_ms=timeout_ms):
            self._last_error = "Data send failed"
            self._send_at("AT+CACLOSE=0")
            if gnss_was_enabled:
                self.gnss_start()
            return False

        # Close connection
        self._send_at("AT+CACLOSE=0", timeout_ms=2000)

        # Re-enable GNSS if it was enabled
        if gnss_was_enabled:
            self.gnss_start()

        self._last_error = None
        return True

    # =========================================================================
    # GNSS Methods
    # =========================================================================

    def gnss_start(self):
        """Start GNSS (GPS/GLONASS/BeiDou/Galileo).

        Returns:
            bool: True if started successfully
        """
        # Power on GNSS
        ok, resp = self._send_at("AT+CGNSPWR=1", timeout_ms=3000)
        if ok:
            self._gnss_enabled = True
            time.sleep(1)  # Give GNSS time to initialize
            return True

        self._last_error = "Failed to start GNSS"
        return False

    def gnss_stop(self):
        """Stop GNSS to save power.

        Returns:
            bool: True if stopped successfully
        """
        ok, resp = self._send_at("AT+CGNSPWR=0", timeout_ms=2000)
        self._gnss_enabled = False
        self.gnss_valid = False
        return ok

    def gnss_cold_start(self):
        """Perform GNSS cold start (full satellite search)."""
        self._send_at("AT+CGNSCOLD", timeout_ms=2000)

    def gnss_warm_start(self):
        """Perform GNSS warm start (use cached data)."""
        self._send_at("AT+CGNSWARM", timeout_ms=2000)

    def gnss_hot_start(self):
        """Perform GNSS hot start (quickest, uses all cached data)."""
        self._send_at("AT+CGNSHOT", timeout_ms=2000)

    def gnss_update(self):
        """Read and parse GNSS data from module.

        Returns:
            bool: True if valid fix obtained
        """
        if not self._gnss_enabled:
            return False

        # Query GNSS info
        # Response format: +CGNSINF: <GNSS run status>,<Fix status>,<UTC>,<Lat>,<Lon>,
        #                  <MSL Alt>,<Speed>,<Course>,<Fix Mode>,<Reserved1>,<HDOP>,
        #                  <PDOP>,<VDOP>,<Reserved2>,<GNSS Sats in View>,<GNSS Sats Used>,
        #                  <GLONASS Sats Used>,<Reserved3>,<C/N0 max>,<HPA>,<VPA>
        ok, resp = self._send_at("AT+CGNSINF", timeout_ms=2000)

        if not ok or "+CGNSINF:" not in resp:
            return False

        try:
            # Parse the response
            info = resp.split("+CGNSINF:")[1].split("\r")[0].strip()
            parts = info.split(",")

            if len(parts) < 16:
                return False

            # GNSS run status
            gnss_run = int(parts[0]) if parts[0] else 0
            if gnss_run != 1:
                return False

            # Fix status (1=fix acquired)
            fix_status = int(parts[1]) if parts[1] else 0
            self.gnss_valid = fix_status == 1

            if not self.gnss_valid:
                return False

            # UTC date/time: YYYYMMDDHHMMSS.sss
            if parts[2]:
                utc = parts[2]
                self.year = int(utc[0:4])
                self.month = int(utc[4:6])
                self.day = int(utc[6:8])
                self.hour = int(utc[8:10])
                self.minute = int(utc[10:12])
                self.second = int(float(utc[12:]))

            # Latitude
            if parts[3]:
                self.latitude = float(parts[3])

            # Longitude
            if parts[4]:
                self.longitude = float(parts[4])

            # Altitude (MSL)
            if parts[5]:
                self.altitude = float(parts[5])

            # Speed (km/h)
            if parts[6]:
                self.speed_kmh = float(parts[6])

            # Course/heading
            if parts[7]:
                self.heading = float(parts[7])

            # HDOP
            if len(parts) > 10 and parts[10]:
                self.hdop = float(parts[10])

            # Satellites used
            if len(parts) > 15 and parts[15]:
                self.satellites = int(parts[15])

            return True

        except (ValueError, IndexError) as e:
            self._last_error = f"GNSS parse error: {e}"
            return False

    def gnss_wait_for_fix(self, timeout_sec=120, callback=None):
        """Wait for GNSS fix.

        Args:
            timeout_sec: Maximum time to wait
            callback: Optional callback(elapsed_sec, satellites)

        Returns:
            bool: True if fix acquired
        """
        if not self._gnss_enabled:
            if not self.gnss_start():
                return False

        start = time.ticks_ms()
        timeout_ms = timeout_sec * 1000

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self.gnss_update():
                return True

            elapsed = time.ticks_diff(time.ticks_ms(), start) // 1000
            if callback:
                callback(elapsed, self.satellites)

            time.sleep(1)

        return False

    def get_position(self):
        """Get current GNSS position data.

        Returns:
            dict: Position data suitable for CiNetMessage
        """
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed': self.speed_kmh,
            'heading': self.heading if self.heading else None,
            'hdop': self.hdop,
            'satellites': self.satellites,
            'valid': self.gnss_valid,
            'timestamp': (self.year, self.month, self.day,
                         self.hour, self.minute, self.second)
        }

    # =========================================================================
    # Network Info Methods
    # =========================================================================

    def _update_network_info(self):
        """Update network information (RSSI, operator)."""
        # Signal quality
        ok, resp = self._send_at("AT+CSQ")
        if ok and "+CSQ:" in resp:
            try:
                parts = resp.split("+CSQ:")[1].split(",")
                rssi_raw = int(parts[0].strip())
                if rssi_raw < 99:
                    self._rssi = -113 + (rssi_raw * 2)
                else:
                    self._rssi = 0
            except:
                pass

        # Operator
        ok, resp = self._send_at("AT+COPS?")
        if ok and ',"' in resp:
            try:
                self._operator = resp.split(',"')[1].split('"')[0]
            except:
                pass

    def get_rssi(self):
        """Get signal strength (RSSI).

        Returns:
            int: RSSI in dBm
        """
        self._update_network_info()
        return self._rssi

    def get_ip_address(self):
        """Get assigned IP address.

        Returns:
            str: IP address
        """
        return self._ip_address

    def get_cell_info(self):
        """Get cellular network info.

        Returns:
            dict: Cell info
        """
        self._update_network_info()
        return {
            'operator': self._operator,
            'rssi': self._rssi,
            'ip': self._ip_address,
            'registered': self._registered,
            'pdp_active': self._pdp_active
        }

    def get_last_error(self):
        """Get last error message.

        Returns:
            str: Error message or None
        """
        return self._last_error

    # =========================================================================
    # Power Management
    # =========================================================================

    def enable_psm(self, tau_minutes=60, active_time_sec=10):
        """Enable Power Saving Mode (PSM).

        In PSM, the module enters deep sleep and wakes periodically.

        Args:
            tau_minutes: Tracking Area Update timer (periodic wake)
            active_time_sec: Active time after wake

        Returns:
            bool: True if PSM enabled
        """
        # Convert to 3GPP timer format
        # This is a simplified version - full implementation would encode
        # the timer values properly
        ok, _ = self._send_at("AT+CPSMS=1", timeout_ms=5000)
        return ok

    def disable_psm(self):
        """Disable Power Saving Mode.

        Returns:
            bool: True if PSM disabled
        """
        ok, _ = self._send_at("AT+CPSMS=0", timeout_ms=5000)
        return ok

    def enter_sleep(self):
        """Enter sleep mode (module stays registered but reduces power)."""
        self._send_at("AT+CSCLK=2")  # Enable auto-sleep

    def wake_from_sleep(self):
        """Wake module from sleep."""
        # Send AT to wake
        self._send_at("AT", timeout_ms=1000)
        self._send_at("AT+CSCLK=0")  # Disable auto-sleep

    # =========================================================================
    # SMS Methods (for SMS command support)
    # =========================================================================

    def send_sms(self, number, message):
        """Send an SMS message.

        Args:
            number: Destination phone number
            message: Message text

        Returns:
            bool: True if sent successfully
        """
        # Set text mode
        self._send_at("AT+CMGF=1")

        # Start SMS
        ok, resp = self._send_at(f'AT+CMGS="{number}"', timeout_ms=5000, expect=">")
        if not ok:
            self._last_error = "SMS prompt not received"
            return False

        # Send message with Ctrl+Z (0x1A) to send
        self.uart.write(message.encode())
        self.uart.write(bytes([0x1A]))

        # Wait for confirmation
        ok, resp = self._send_at("", timeout_ms=30000, expect="+CMGS:")
        if not ok:
            self._last_error = "SMS send failed"
            return False

        return True

    def check_sms(self):
        """Check for new SMS messages.

        Returns:
            list: List of (index, sender, message) tuples
        """
        messages = []

        # Set text mode
        self._send_at("AT+CMGF=1")

        # Read all unread messages
        ok, resp = self._send_at('AT+CMGL="REC UNREAD"', timeout_ms=5000)
        if not ok:
            return messages

        # Parse messages
        lines = resp.split("\r\n")
        i = 0
        while i < len(lines):
            if "+CMGL:" in lines[i]:
                try:
                    # Parse header: +CMGL: <index>,<stat>,<sender>,...
                    header = lines[i].split(",")
                    index = int(header[0].split(":")[1].strip())
                    sender = header[2].strip('"')

                    # Message is on next line
                    if i + 1 < len(lines):
                        message = lines[i + 1].strip()
                        messages.append((index, sender, message))

                except (IndexError, ValueError):
                    pass
            i += 1

        return messages

    def delete_sms(self, index):
        """Delete an SMS message.

        Args:
            index: Message index to delete
        """
        self._send_at(f"AT+CMGD={index}")

    def __repr__(self):
        status = []
        if self._connected:
            status.append("CONNECTED")
        if self._gnss_enabled:
            status.append("GNSS")
        if self.gnss_valid:
            status.append("FIX")
        return f"SIM7080G({', '.join(status) or 'IDLE'})"
