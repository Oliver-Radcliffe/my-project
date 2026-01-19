# Network Driver Base Class
# Abstract interface for network connectivity

class NetworkDriverBase:
    """Abstract base class for network drivers."""

    def __init__(self):
        self._connected = False
        self._last_error = None

    @property
    def connected(self):
        """Check if currently connected to network."""
        return self._connected

    @property
    def last_error(self):
        """Get last error message."""
        return self._last_error

    def connect(self):
        """Connect to the network.

        Returns:
            bool: True if connected successfully
        """
        raise NotImplementedError

    def disconnect(self):
        """Disconnect from the network."""
        raise NotImplementedError

    def is_connected(self):
        """Check network connectivity status.

        Returns:
            bool: True if connected
        """
        raise NotImplementedError

    def send_tcp(self, host, port, data, timeout_ms=10000):
        """Send data via TCP.

        Args:
            host: Server hostname or IP
            port: Server port
            data: bytes or bytearray to send
            timeout_ms: Connection timeout in milliseconds

        Returns:
            bool: True if sent successfully
        """
        raise NotImplementedError

    def send_udp(self, host, port, data):
        """Send data via UDP.

        Args:
            host: Server hostname or IP
            port: Server port
            data: bytes or bytearray to send

        Returns:
            bool: True if sent successfully
        """
        raise NotImplementedError

    def get_rssi(self):
        """Get signal strength (RSSI).

        Returns:
            int: RSSI value in dBm, or 0 if not available
        """
        return 0

    def get_ip_address(self):
        """Get assigned IP address.

        Returns:
            str: IP address or empty string if not connected
        """
        return ""
