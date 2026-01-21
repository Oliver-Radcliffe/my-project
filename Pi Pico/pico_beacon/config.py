# Pico Beacon Configuration
# MicroPython firmware for ciNet-compatible GPS tracking beacon
# Based on RAPID 2 feature set

import json

# ==============================================================================
# DEFAULT CONFIGURATION - RAPID 2 COMPATIBLE
# ==============================================================================

DEFAULT_CONFIG = {
    # ==========================================================================
    # TEST MODE
    # ==========================================================================
    # When enabled, disables features that could interfere with hardware testing:
    # - Motion sensors disabled
    # - Battery monitoring disabled (no low battery shutdown)
    # - Sleep modes disabled (device stays awake)
    # - Deployment mode disabled (uses normal rates immediately)
    # - Watchdog disabled
    # Set to False for production use
    "test_mode": True,

    # ==========================================================================
    # OPERATING MODE
    # ==========================================================================
    # "active" - Normal tracking mode
    # "standby" - Reduced power, wake on motion or command
    # "hibernate" - Deep sleep, wake on command only
    # "logging" - Local logging only (no network transmission)
    "operating_mode": "active",

    # ==========================================================================
    # CINET SERVER SETTINGS
    # ==========================================================================
    "server_host": "86.188.208.143",  # ciNet server IP
    "server_port": 4509,               # TCP port
    "passphrase": "fredfred",          # Encryption passphrase (256-bit Blowfish)

    # ==========================================================================
    # DEVICE IDENTITY
    # ==========================================================================
    "cinet_key": "06.EA.83.A3",        # 4-byte device key (hex format)
    "serial_number": "PICO00000001",   # Device serial (max 23 chars)
    "client_name": "Pico Beacon",      # Display name (max 19 chars)
    "source_type": "Millitag",         # Device type (max 11 chars)

    # ==========================================================================
    # GPRS MESSAGE RATES (RAPID 2: 5 seconds to 24 hours)
    # ==========================================================================
    "gprs_rate_moving_sec": 10,        # Rate when moving (5-86400 sec)
    "gprs_rate_stopped_sec": 60,       # Rate when stopped (5-86400 sec)
    "gprs_rate_standby_sec": 3600,     # Rate in standby mode (hourly check-in)

    # ==========================================================================
    # LOGGING SETTINGS (RAPID 2: 260,096 points, 5 sec to 30 min)
    # ==========================================================================
    "logging_enabled": True,
    "logging_rate_sec": 10,            # Local log rate (5-1800 sec)
    "max_log_points": 260000,          # Max log points (RAPID 2: 260,096)
    "log_to_sd_card": False,           # Use SD card if available
    "log_format_csv": True,            # CSV format
    "log_format_json": False,          # JSON Lines format
    "log_circular_buffer": True,       # Overwrite oldest when full
    "auto_upload_logs": True,          # Upload logs after connection recovery

    # ==========================================================================
    # SMS SETTINGS (RAPID 2: 30s to 60min rate)
    # ==========================================================================
    "sms_enabled": False,              # Enable SMS reporting
    "sms_rate_sec": 300,               # SMS rate (30-3600 sec)
    "sms_destination": "",             # Phone number for SMS reports
    "sms_commands_enabled": True,      # Allow SMS commands

    # ==========================================================================
    # MOTION SENSING (RAPID 2: Two state - moving/stopped)
    # ==========================================================================
    "motion_sensor_enabled": True,
    "motion_sensor_type": "accelerometer",  # "none", "interrupt", "accelerometer"
    "motion_sensor_pin": 22,           # GPIO pin for interrupt sensor
    "motion_threshold_g": 0.15,        # Motion detection threshold (g)
    "motion_timeout_sec": 120,         # Time to declare "stopped" after last motion
    "wake_on_motion": True,            # Wake from standby on motion

    # ==========================================================================
    # INPUT/OUTPUT (RAPID 2: Input 2.2-30V, Output 500mA open drain)
    # ==========================================================================
    "io_enabled": True,
    "input_pin": 18,                   # External input GPIO
    "input_active_high": True,         # True = high is active
    "input_alert_enabled": True,       # Send alert on input change
    "output_pin": 19,                  # External output GPIO (open drain)
    "output_default_state": False,     # Default output state

    # ==========================================================================
    # TAMPER DETECTION
    # ==========================================================================
    "tamper_enabled": False,
    "tamper_pin": 21,                  # Tamper switch GPIO
    "tamper_alert_enabled": True,      # Send alert on tamper

    # ==========================================================================
    # POWER MANAGEMENT
    # ==========================================================================
    "external_power_pin": 27,          # GPIO to detect external power (9-30V)
    "external_power_enabled": True,    # Monitor external power
    "battery_backup_mode": True,       # Use internal as backup when external present
    "low_battery_threshold": 20,       # Low battery warning (%)
    "critical_battery_threshold": 10,  # Critical battery level (%)
    "deep_sleep_enabled": False,       # Allow deep sleep (device resets on wake)

    # ==========================================================================
    # HIBERNATE MODE SETTINGS
    # ==========================================================================
    "hibernate_wake_interval_hr": 24,  # Wake interval in hibernate (hours)
    "hibernate_check_motion": False,   # Check motion sensor in hibernate

    # ==========================================================================
    # STANDBY MODE SETTINGS
    # ==========================================================================
    "standby_wake_on_motion": True,    # Wake from standby on motion
    "standby_wake_on_input": True,     # Wake from standby on input change
    "standby_check_interval_sec": 60,  # How often to check for wake events

    # ==========================================================================
    # NETWORK SETTINGS
    # ==========================================================================
    "network_type": "sim7080g",        # "wifi", "cellular", or "sim7080g"
    "wifi_ssid": "",                   # WiFi SSID (Pico W only)
    "wifi_password": "",               # WiFi password
    "cellular_apn": "internet",        # Cellular APN
    "cellular_user": "",               # APN username
    "cellular_pass": "",               # APN password
    "connection_retry_count": 3,       # Retries before fallback
    "connection_timeout_sec": 120,     # Connection timeout (longer for Cat-M/NB-IoT)

    # ==========================================================================
    # SIM7080G SETTINGS (Waveshare Pico-SIM7080G board)
    # ==========================================================================
    "sim7080g_use_udp": True,          # Use UDP (recommended - TCP doesn't work with GNSS)
    "sim7080g_network_mode": 3,        # 1=Cat-M, 2=NB-IoT, 3=Both (auto)

    # ==========================================================================
    # GPS SOURCE SETTINGS
    # ==========================================================================
    # When True, use an external GPS module (NEO-6M, NEO-M8N, etc.) connected
    # via UART instead of the integrated GNSS in the SIM7080G modem.
    # This is useful if the integrated GNSS has poor reception.
    # External GPS uses UART1 (GP4=TX, GP5=RX) at 9600 baud by default.
    "use_external_gps": False,
    "external_gps_uart_id": 1,         # UART ID for external GPS (0 or 1)
    "external_gps_tx_pin": 4,          # TX pin (Pico -> GPS RX)
    "external_gps_rx_pin": 5,          # RX pin (GPS TX -> Pico)
    "external_gps_baudrate": 9600,     # GPS module baudrate

    # ==========================================================================
    # REMOTE COMMANDS (RAPID 2 GPRS Commands)
    # ==========================================================================
    "remote_commands_enabled": True,   # Allow remote commands
    "command_poll_interval_sec": 60,   # How often to check for commands

    # ==========================================================================
    # ALERTS
    # ==========================================================================
    "alert_low_battery": True,
    "alert_motion_start": False,
    "alert_motion_stop": False,
    "alert_input_change": True,
    "alert_tamper": True,
    "alert_external_power_lost": True,
    "alert_geofence": False,

    # ==========================================================================
    # GEOFENCING (Optional)
    # ==========================================================================
    "geofence_enabled": False,
    "geofence_lat": 0.0,               # Center latitude
    "geofence_lon": 0.0,               # Center longitude
    "geofence_radius_m": 1000,         # Radius in meters

    # ==========================================================================
    # STATUS REPORTING (Battery, motion, GPS, GSM, I/O)
    # ==========================================================================
    "status_in_message": True,         # Include full status in position messages

    # ==========================================================================
    # FIRMWARE VERSION
    # ==========================================================================
    "fw_version_major": 2,
    "fw_version_minor": 0,
    "fw_version_patch": 0,
}

# ==============================================================================
# OPERATING MODES (RAPID 2 Compatible)
# ==============================================================================

class OperatingMode:
    ACTIVE = "active"          # Normal tracking
    STANDBY = "standby"        # Low power, wake on motion/input/command
    HIBERNATE = "hibernate"    # Deep sleep, wake on command only
    LOGGING = "logging"        # Local logging only, no network


# ==============================================================================
# REMOTE COMMANDS (RAPID 2 GPRS/SMS Commands)
# ==============================================================================

class RemoteCommand:
    # GPRS Commands
    HIBERNATE = "hibernate"           # Enter hibernate mode
    STANDBY = "standby"               # Enter standby mode
    CLEAR_STANDBY = "clear_standby"   # Exit standby, return to active
    ACTIVATE = "activate"             # Enter active tracking mode
    GET_STATUS = "get_status"         # Request status report
    OUTPUT_ON = "output_on"           # Turn output on
    OUTPUT_OFF = "output_off"         # Turn output off
    TAMPER_ALERT_ON = "tamper_on"     # Enable tamper alerts
    TAMPER_ALERT_OFF = "tamper_off"   # Disable tamper alerts
    ERASE_LOG = "erase_log"           # Erase stored logs
    UPLOAD_LOG = "upload_log"         # Upload stored logs now
    SET_RATE = "set_rate"             # Set reporting rate
    REBOOT = "reboot"                 # Reboot device
    LOCATE = "locate"                 # Request immediate position

    # SMS Commands (RAPID 2)
    SMS_STATUS = "status"             # Get status via SMS
    SMS_MAP = "map"                   # Get map link via SMS
    SMS_MAPTRACK = "maptrack"         # Start SMS tracking
    SMS_OUTPUT_OPEN = "output open"   # Open output
    SMS_OUTPUT_CLOSE = "output close" # Close output


# ==============================================================================
# ALERT TYPES
# ==============================================================================

class AlertType:
    LOW_BATTERY = 0x0001
    MOTION_START = 0x0002
    MOTION_STOP = 0x0004
    INPUT_CHANGE = 0x0008
    TAMPER = 0x0010
    EXTERNAL_POWER_LOST = 0x0020
    EXTERNAL_POWER_RESTORED = 0x0040
    GEOFENCE_ENTER = 0x0080
    GEOFENCE_EXIT = 0x0100
    CONNECTION_LOST = 0x0200
    CONNECTION_RESTORED = 0x0400


# ==============================================================================
# PIN DEFINITIONS
# ==============================================================================

class Pins:
    # SIM7080G Module (Waveshare Pico-SIM7080G board)
    # Uses UART0 for AT commands (cellular + GNSS integrated)
    SIM7080G_TX = 0      # GP0 -> SIM7080G RX
    SIM7080G_RX = 1      # GP1 -> SIM7080G TX
    SIM7080G_PWR = 14    # GP14 -> SIM7080G Power Key
    SIM7080G_UART_ID = 0

    # Legacy GPS Module pins (for standalone GPS, not used with SIM7080G)
    GPS_TX = 0   # GP0 -> GPS RX
    GPS_RX = 1   # GP1 -> GPS TX

    # External GPS Module pins (when using SIM7080G with external GPS)
    # Uses UART1 to avoid conflict with SIM7080G on UART0
    EXT_GPS_TX = 4   # GP4 -> External GPS RX
    EXT_GPS_RX = 5   # GP5 -> External GPS TX
    EXT_GPS_UART_ID = 1

    # Legacy Cellular Module (UART1) - for SIM7600/SIM800L
    CELL_TX = 4   # GP4 -> SIM TX
    CELL_RX = 5   # GP5 -> SIM RX
    CELL_PWR = 6  # GP6 -> SIM Power Key
    CELL_STATUS = 7  # GP7 -> SIM Status

    # Status LEDs (directly on Pico or external)
    LED_GPS = 15      # Green - GPS fix status
    LED_NETWORK = 16  # Blue - Network status
    LED_ERROR = 17    # Red - Error indicator
    LED_ONBOARD = "LED"  # Onboard LED (Pico W)

    # I/O Pins (directly on Pico)
    INPUT_PIN = 18         # External input
    OUTPUT_PIN = 19        # External output (open drain)

    # Sensors
    MOTION_INT = 22        # Motion sensor interrupt
    TAMPER_PIN = 21        # Tamper switch

    # Power
    BATTERY_ADC = 26       # ADC0 - Battery voltage divider
    EXT_POWER_DETECT = 27  # External power detection

    # I2C (for accelerometer)
    I2C_SDA = 20
    I2C_SCL = 21

    # Power Control
    GPS_ENABLE = 28        # GPS module power enable (not used with SIM7080G)


# ==============================================================================
# PROTOCOL CONSTANTS
# ==============================================================================

class Protocol:
    MESSAGE_LENGTH = 149
    HEADER_LENGTH = 51
    ENCRYPTED_LENGTH = 96
    CRC_LENGTH = 2

    START_BYTE = 0x24  # '$'
    PACKET_TYPE = 0x55  # 'U'
    CINET_TYPE = 0x44   # 'D'
    MESSAGE_TYPE = 0x02
    ALARM_DEFAULT = 0xFF
    MILLITAG_SPECIFIC_LENGTH = 0x2E

    BLOWFISH_KEY_LEN = 32
    PBKDF2_ITERATIONS = 1000
    PBKDF2_SALT = bytes([0x74, 0xC4, 0x89, 0x4C, 0x4F, 0x38, 0xFF, 0xCC])


# ==============================================================================
# UART SETTINGS
# ==============================================================================

class UART:
    GPS_BAUDRATE = 9600
    GPS_UART_ID = 0
    CELL_BAUDRATE = 115200
    CELL_UART_ID = 1
    SIM7080G_BAUDRATE = 115200
    SIM7080G_UART_ID = 0


# ==============================================================================
# TIMING CONSTANTS
# ==============================================================================

class Timing:
    GPS_UPDATE_MS = 1000
    NETWORK_TIMEOUT_MS = 10000
    CONNECT_RETRY_MS = 5000
    MAX_RETRIES = 3
    COMMAND_POLL_MS = 60000
    LOG_FLUSH_INTERVAL_MS = 30000


# ==============================================================================
# STATE MACHINE STATES
# ==============================================================================

class State:
    STARTUP = 0
    INIT = 1
    GPS_ACQUIRE = 2
    NETWORK_CONNECT = 3
    READY = 4
    TRANSMIT = 5
    SLEEP = 6
    STANDBY = 7
    HIBERNATE = 8
    LOG_UPLOAD = 9
    ERROR = 10


# ==============================================================================
# DEVICE STATUS FLAGS
# ==============================================================================

class StatusFlags:
    GPS_FIX = 0x0001
    NETWORK_CONNECTED = 0x0002
    MOTION_DETECTED = 0x0004
    EXTERNAL_POWER = 0x0008
    INPUT_ACTIVE = 0x0010
    OUTPUT_ACTIVE = 0x0020
    TAMPER_DETECTED = 0x0040
    LOW_BATTERY = 0x0080
    LOGGING_ACTIVE = 0x0100
    STANDBY_MODE = 0x0200
    HIBERNATE_MODE = 0x0400


# ==============================================================================
# CONFIGURATION MANAGER
# ==============================================================================

class ConfigManager:
    """Manages configuration storage and retrieval."""

    CONFIG_FILE = "/config.json"

    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        """Load configuration from flash storage."""
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                self.config.update(saved)
        except (OSError, ValueError):
            pass

    def save(self):
        """Save configuration to flash storage."""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.config, f)
            return True
        except OSError:
            return False

    def get(self, key, default=None):
        """Get a configuration value."""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value."""
        self.config[key] = value

    def update(self, updates):
        """Update multiple configuration values."""
        self.config.update(updates)

    def reset(self):
        """Reset to default configuration."""
        self.config = DEFAULT_CONFIG.copy()
        self.save()

    def get_cinet_key_bytes(self):
        """Convert hex string ciNet key to integer."""
        key_str = self.config.get("cinet_key", "00.00.00.00")
        parts = key_str.split('.')
        key_int = 0
        for i, part in enumerate(parts):
            key_int |= int(part, 16) << (24 - i * 8)
        return key_int

    def get_serial_bytes(self):
        """Get serial number as 24-byte array."""
        serial = self.config.get("serial_number", "")[:23]
        buf = bytearray(24)
        for i, c in enumerate(serial):
            buf[i] = ord(c)
        return buf

    def get_client_name_bytes(self):
        """Get client name as 20-byte array."""
        name = self.config.get("client_name", "")[:19]
        buf = bytearray(20)
        for i, c in enumerate(name):
            buf[i] = ord(c)
        return buf

    def get_source_type_bytes(self):
        """Get source type as 12-byte array."""
        src = self.config.get("source_type", "Millitag")[:11]
        buf = bytearray(12)
        for i, c in enumerate(src):
            buf[i] = ord(c)
        return buf

    def get_operator_bytes(self):
        """Get operator name as 8-byte array."""
        op = "Pico"[:7]
        buf = bytearray(8)
        for i, c in enumerate(op):
            buf[i] = ord(c)
        return buf

    def get_current_rate(self, is_moving):
        """Get current GPRS reporting rate based on motion state.

        Args:
            is_moving: True if device is moving

        Returns:
            int: Rate in seconds
        """
        mode = self.config.get("operating_mode", "active")

        if mode == OperatingMode.STANDBY:
            return self.config.get("gprs_rate_standby_sec", 3600)
        elif mode == OperatingMode.HIBERNATE:
            return self.config.get("hibernate_wake_interval_hr", 24) * 3600
        elif is_moving:
            return self.config.get("gprs_rate_moving_sec", 10)
        else:
            return self.config.get("gprs_rate_stopped_sec", 60)
