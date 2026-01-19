# Cellular Network Driver
# Handles SIM7600/SIM800L GSM/LTE modules via AT commands

from machine import UART, Pin
import time

from .network_base import NetworkDriverBase


class CellularDriver(NetworkDriverBase):
    """Cellular network driver for SIM7600/SIM800L modules."""

    def __init__(self, uart_id=1, tx_pin=4, rx_pin=5, pwr_pin=6,
                 baudrate=115200, apn="internet", user="", password=""):
        """Initialize cellular driver.

        Args:
            uart_id: UART peripheral ID
            tx_pin: GPIO pin for TX
            rx_pin: GPIO pin for RX
            pwr_pin: GPIO pin for power key (or None)
            baudrate: UART baudrate
            apn: Cellular APN name
            user: APN username (optional)
            password: APN password (optional)
        """
        super().__init__()

        self.uart = UART(uart_id, baudrate=baudrate,
                         tx=Pin(tx_pin), rx=Pin(rx_pin))

        self.pwr_pin = Pin(pwr_pin, Pin.OUT) if pwr_pin is not None else None
        self.apn = apn
        self.user = user
        self.password = password

        # Module state
        self._registered = False
        self._pdp_active = False
        self._rssi = 0
        self._operator = ""
        self._lac = 0
        self._cell_id = 0

    def power_on(self):
        """Power on the cellular module."""
        if self.pwr_pin is None:
            return

        # Pulse power key
        self.pwr_pin.value(1)
        time.sleep(1.0)
        self.pwr_pin.value(0)
        time.sleep(3.0)  # Wait for module to boot

    def power_off(self):
        """Power off the cellular module."""
        # Send shutdown command
        self._send_at("AT+CPOF", timeout_ms=5000)

        if self.pwr_pin:
            time.sleep(1.0)
            self.pwr_pin.value(1)
            time.sleep(2.0)
            self.pwr_pin.value(0)

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

    def init_module(self):
        """Initialize the cellular module.

        Returns:
            bool: True if initialization successful
        """
        # Test AT communication
        ok, _ = self._send_at("AT", timeout_ms=2000)
        if not ok:
            self._last_error = "Module not responding"
            return False

        # Disable echo
        self._send_at("ATE0")

        # Set full functionality
        self._send_at("AT+CFUN=1", timeout_ms=5000)

        # Wait for SIM ready
        for _ in range(10):
            ok, resp = self._send_at("AT+CPIN?", timeout_ms=2000)
            if "READY" in resp:
                break
            time.sleep(1)
        else:
            self._last_error = "SIM not ready"
            return False

        return True

    def connect(self, timeout_sec=60):
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
            ok, resp = self._send_at("AT+CREG?")
            if ",1" in resp or ",5" in resp:  # Home or roaming
                self._registered = True
                break
            time.sleep(1)

        if not self._registered:
            self._last_error = "Network registration failed"
            return False

        # Configure APN (for SIM7600)
        self._send_at(f'AT+CGDCONT=1,"IP","{self.apn}"')

        # Activate PDP context
        ok, resp = self._send_at("AT+CGACT=1,1", timeout_ms=30000)
        if not ok:
            # Try alternative method (for SIM800L)
            self._send_at(f'AT+CSTT="{self.apn}","{self.user}","{self.password}"')
            ok, resp = self._send_at("AT+CIICR", timeout_ms=30000)
            if not ok:
                self._last_error = "PDP activation failed"
                return False

        self._pdp_active = True
        self._connected = True
        self._last_error = None

        # Update network info
        self._update_network_info()

        return True

    def disconnect(self):
        """Disconnect from cellular network."""
        self._send_at("AT+CGACT=0,1", timeout_ms=5000)
        self._pdp_active = False
        self._connected = False
        self._registered = False

    def is_connected(self):
        """Check cellular connection status.

        Returns:
            bool: True if connected
        """
        if not self._pdp_active:
            return False

        # Check PDP context status
        ok, resp = self._send_at("AT+CGACT?")
        if ok and "+CGACT: 1,1" in resp:
            self._connected = True
            return True

        self._connected = False
        return False

    def send_tcp(self, host, port, data, timeout_ms=10000):
        """Send data via TCP using AT commands.

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

        # Start TCP connection (SIM7600 style)
        cmd = f'AT+CIPOPEN=0,"TCP","{host}",{port}'
        ok, resp = self._send_at(cmd, timeout_ms=timeout_ms, expect="CONNECT OK")

        if not ok and "CONNECT OK" not in resp:
            # Try SIM800L style
            cmd = f'AT+CIPSTART="TCP","{host}","{port}"'
            ok, resp = self._send_at(cmd, timeout_ms=timeout_ms, expect="CONNECT")
            if not ok:
                self._last_error = f"TCP connect failed: {resp}"
                return False

        # Send data
        data_len = len(data)

        # Enter data mode (SIM7600)
        ok, resp = self._send_at(f"AT+CIPSEND=0,{data_len}", timeout_ms=5000, expect=">")
        if not ok:
            # Try SIM800L style
            ok, resp = self._send_at(f"AT+CIPSEND={data_len}", timeout_ms=5000, expect=">")
            if not ok:
                self._last_error = "Send prompt not received"
                self._send_at("AT+CIPCLOSE=0")
                return False

        # Send actual data
        self.uart.write(data)
        time.sleep_ms(100)

        # Wait for send confirmation
        ok, resp = self._send_at("", timeout_ms=timeout_ms, expect="SEND OK")

        # Close connection
        self._send_at("AT+CIPCLOSE=0", timeout_ms=5000)

        if not ok:
            self._last_error = f"Send failed: {resp}"
            return False

        self._last_error = None
        return True

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

        # Start UDP connection
        cmd = f'AT+CIPOPEN=0,"UDP","{host}",{port}'
        ok, resp = self._send_at(cmd, timeout_ms=10000)

        if not ok:
            self._last_error = "UDP connection failed"
            return False

        # Send data
        data_len = len(data)
        ok, resp = self._send_at(f"AT+CIPSEND=0,{data_len}", timeout_ms=5000, expect=">")

        if ok:
            self.uart.write(data)
            time.sleep_ms(100)
            ok, resp = self._send_at("", timeout_ms=5000, expect="SEND OK")

        # Close
        self._send_at("AT+CIPCLOSE=0")

        if not ok:
            self._last_error = "UDP send failed"
            return False

        return True

    def _update_network_info(self):
        """Update network information (RSSI, operator, cell info)."""
        # Signal strength
        ok, resp = self._send_at("AT+CSQ")
        if ok and "+CSQ:" in resp:
            try:
                parts = resp.split("+CSQ:")[1].split(",")
                rssi_raw = int(parts[0].strip())
                # Convert to dBm (0-31 scale, 99=unknown)
                if rssi_raw < 99:
                    self._rssi = -113 + (rssi_raw * 2)
                else:
                    self._rssi = 0
            except (IndexError, ValueError):
                pass

        # Operator name
        ok, resp = self._send_at("AT+COPS?")
        if ok and ',"' in resp:
            try:
                self._operator = resp.split(',"')[1].split('"')[0]
            except IndexError:
                pass

        # Cell info (LAC, Cell ID)
        ok, resp = self._send_at("AT+CREG=2")
        ok, resp = self._send_at("AT+CREG?")
        if ok and "+CREG:" in resp:
            try:
                # Response: +CREG: n,stat[,lac,ci]
                parts = resp.split(",")
                if len(parts) >= 4:
                    self._lac = int(parts[2].strip('" \r\n'), 16)
                    self._cell_id = int(parts[3].strip('" \r\n'), 16)
            except (IndexError, ValueError):
                pass

        # Reset CREG format
        self._send_at("AT+CREG=0")

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
        ok, resp = self._send_at("AT+CGPADDR=1")
        if ok and "+CGPADDR:" in resp:
            try:
                parts = resp.split('"')
                if len(parts) >= 2:
                    return parts[1]
            except IndexError:
                pass
        return ""

    def get_cell_info(self):
        """Get cellular network info.

        Returns:
            dict: Cell info (operator, lac, cell_id, rssi)
        """
        self._update_network_info()
        return {
            'operator': self._operator,
            'lac': self._lac,
            'cell_id': self._cell_id,
            'rssi': self._rssi
        }

    def set_apn(self, apn, user="", password=""):
        """Set APN credentials.

        Args:
            apn: APN name
            user: Username (optional)
            password: Password (optional)
        """
        self.apn = apn
        self.user = user
        self.password = password
