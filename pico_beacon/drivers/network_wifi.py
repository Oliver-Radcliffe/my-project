# WiFi Network Driver for Pico W
# Handles WiFi connectivity and TCP/UDP transmission

import time
import socket

try:
    import network
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

from .network_base import NetworkDriverBase


class WiFiDriver(NetworkDriverBase):
    """WiFi network driver for Raspberry Pi Pico W."""

    def __init__(self, ssid=None, password=None):
        """Initialize WiFi driver.

        Args:
            ssid: WiFi network SSID
            password: WiFi password
        """
        super().__init__()

        self.ssid = ssid
        self.password = password

        if WIFI_AVAILABLE:
            self.wlan = network.WLAN(network.STA_IF)
        else:
            self.wlan = None
            self._last_error = "WiFi not available (not Pico W?)"

    def connect(self, timeout_sec=30):
        """Connect to WiFi network.

        Args:
            timeout_sec: Connection timeout in seconds

        Returns:
            bool: True if connected successfully
        """
        if not WIFI_AVAILABLE or self.wlan is None:
            self._last_error = "WiFi not available"
            return False

        if not self.ssid:
            self._last_error = "No SSID configured"
            return False

        try:
            # Activate interface
            self.wlan.active(True)

            # Disconnect if already connected
            if self.wlan.isconnected():
                self.wlan.disconnect()
                time.sleep(0.5)

            # Connect to network
            self.wlan.connect(self.ssid, self.password)

            # Wait for connection
            start = time.ticks_ms()
            timeout_ms = timeout_sec * 1000

            while not self.wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                    self._last_error = "Connection timeout"
                    self._connected = False
                    return False
                time.sleep_ms(100)

            self._connected = True
            self._last_error = None
            return True

        except Exception as e:
            self._last_error = str(e)
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from WiFi network."""
        if self.wlan:
            try:
                self.wlan.disconnect()
                self.wlan.active(False)
            except Exception:
                pass
        self._connected = False

    def is_connected(self):
        """Check WiFi connection status.

        Returns:
            bool: True if connected
        """
        if not WIFI_AVAILABLE or self.wlan is None:
            return False

        try:
            self._connected = self.wlan.isconnected()
            return self._connected
        except Exception:
            self._connected = False
            return False

    def send_tcp(self, host, port, data, timeout_ms=10000):
        """Send data via TCP connection.

        Args:
            host: Server hostname or IP address
            port: Server TCP port
            data: bytes or bytearray to send
            timeout_ms: Socket timeout in milliseconds

        Returns:
            bool: True if sent successfully
        """
        if not self.is_connected():
            self._last_error = "Not connected to WiFi"
            return False

        sock = None
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_ms / 1000.0)

            # Connect to server
            addr = socket.getaddrinfo(host, port)[0][-1]
            sock.connect(addr)

            # Send data
            sock.send(data)

            self._last_error = None
            return True

        except Exception as e:
            self._last_error = f"TCP send error: {e}"
            return False

        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def send_udp(self, host, port, data):
        """Send data via UDP.

        Args:
            host: Server hostname or IP address
            port: Server UDP port
            data: bytes or bytearray to send

        Returns:
            bool: True if sent successfully
        """
        if not self.is_connected():
            self._last_error = "Not connected to WiFi"
            return False

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            addr = socket.getaddrinfo(host, port)[0][-1]
            sock.sendto(data, addr)

            self._last_error = None
            return True

        except Exception as e:
            self._last_error = f"UDP send error: {e}"
            return False

        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def get_rssi(self):
        """Get WiFi signal strength (RSSI).

        Returns:
            int: RSSI in dBm
        """
        if not WIFI_AVAILABLE or self.wlan is None:
            return 0

        try:
            status = self.wlan.status('rssi')
            return status if isinstance(status, int) else 0
        except Exception:
            return 0

    def get_ip_address(self):
        """Get assigned IP address.

        Returns:
            str: IP address or empty string
        """
        if not WIFI_AVAILABLE or self.wlan is None:
            return ""

        try:
            if self.wlan.isconnected():
                config = self.wlan.ifconfig()
                return config[0] if config else ""
            return ""
        except Exception:
            return ""

    def scan_networks(self):
        """Scan for available WiFi networks.

        Returns:
            list: List of (ssid, bssid, channel, rssi, security, hidden) tuples
        """
        if not WIFI_AVAILABLE or self.wlan is None:
            return []

        try:
            self.wlan.active(True)
            networks = self.wlan.scan()
            return networks
        except Exception:
            return []

    def set_credentials(self, ssid, password):
        """Set WiFi credentials.

        Args:
            ssid: WiFi network SSID
            password: WiFi password
        """
        self.ssid = ssid
        self.password = password
