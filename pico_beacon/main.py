# Pico Beacon - Main Application
# ciNet-compatible GPS tracking beacon for Raspberry Pi Pico
#
# This is the main entry point for the beacon firmware.
# Copy all files to the Pico's filesystem and this will run automatically.
#
# Operating Modes:
#   - "cinet": Transmit to ciNet server only
#   - "logging": Local logging only (no network required)
#   - "both": Transmit AND log locally

import time
import machine

from config import ConfigManager, Pins, State, Timing
from protocol.cinet_message import CiNetMessage, DeviceStatus
from drivers.gps_driver import GPSDriver
from drivers.network_wifi import WiFiDriver
from drivers.network_cellular import CellularDriver
from drivers.motion_sensor import create_motion_sensor
from utils.power_manager import PowerManager
from utils.led_status import StatusLED
from utils.logger import Logger, LogLevel
from utils.data_logger import DataLogger, SDCardLogger


class PicoBeacon:
    """Main beacon application with state machine."""

    def __init__(self):
        """Initialize the beacon."""
        # Logger
        self.log = Logger("Beacon", LogLevel.INFO)
        self.log.info("Pico Beacon initializing...")

        # Configuration
        self.config = ConfigManager()
        self.operating_mode = self.config.get("operating_mode", "both")
        self.log.info(f"Operating mode: {self.operating_mode}")
        self.log.info(f"Serial: {self.config.get('serial_number')}")

        if self.operating_mode in ("cinet", "both"):
            self.log.info(f"Server: {self.config.get('server_host')}:{self.config.get('server_port')}")

        # Status LEDs
        self.leds = StatusLED(
            gps_pin=Pins.LED_GPS,
            network_pin=Pins.LED_NETWORK,
            error_pin=Pins.LED_ERROR,
            onboard_pin=Pins.LED_ONBOARD
        )
        self.leds.indicate_startup()

        # Power manager
        self.power = PowerManager(
            battery_adc_pin=Pins.BATTERY_ADC,
            gps_enable_pin=getattr(Pins, 'GPS_ENABLE', None),
            cell_enable_pin=getattr(Pins, 'CELL_ENABLE', None)
        )

        # GPS driver
        self.gps = GPSDriver(
            uart_id=0,
            tx_pin=Pins.GPS_TX,
            rx_pin=Pins.GPS_RX,
            baudrate=9600
        )

        # Network driver (only if needed)
        self.network = None
        if self.operating_mode in ("cinet", "both"):
            self._init_network()

        # Protocol handler (only if ciNet mode)
        self.protocol = None
        if self.operating_mode in ("cinet", "both"):
            self.protocol = CiNetMessage(self.config)

        # Device status container
        self.device_status = DeviceStatus()

        # Data logger (if enabled or in logging mode)
        self.data_logger = None
        if self.operating_mode in ("logging", "both") or self.config.get("logging_enabled", False):
            self._init_data_logger()

        # Motion sensor (if enabled)
        self.motion_sensor = None
        if self.config.get("motion_sensor_enabled", False):
            self._init_motion_sensor()

        # State machine
        self.state = State.STARTUP
        self.last_transmit_time = 0
        self.last_log_time = 0
        self.retry_count = 0
        self.error_message = None

        # Motion detection for adaptive reporting
        self._last_position = None
        self._is_moving = False
        self._motion_woke_us = False

        # Watchdog timer (reset every loop iteration)
        try:
            self.watchdog = machine.WDT(timeout=30000)  # 30 second watchdog
        except Exception:
            self.watchdog = None
            self.log.warning("Watchdog not available")

        self.log.info("Initialization complete")

    def _init_network(self):
        """Initialize network driver based on configuration."""
        network_type = self.config.get("network_type", "wifi")

        if network_type == "cellular":
            self.log.info("Using cellular network")
            self.network = CellularDriver(
                uart_id=1,
                tx_pin=Pins.CELL_TX,
                rx_pin=Pins.CELL_RX,
                pwr_pin=Pins.CELL_PWR,
                apn=self.config.get("cellular_apn", "internet"),
                user=self.config.get("cellular_user", ""),
                password=self.config.get("cellular_pass", "")
            )
        else:
            self.log.info("Using WiFi network")
            self.network = WiFiDriver(
                ssid=self.config.get("wifi_ssid"),
                password=self.config.get("wifi_password")
            )

    def _init_data_logger(self):
        """Initialize data logger based on configuration."""
        try:
            use_sd = self.config.get("log_to_sd_card", False)
            csv_enabled = self.config.get("log_format_csv", True)
            json_enabled = self.config.get("log_format_json", False)

            if use_sd:
                self.log.info("Initializing SD card logger...")
                self.data_logger = SDCardLogger(
                    enable_csv=csv_enabled,
                    enable_json=json_enabled
                )
            else:
                self.log.info("Initializing flash logger...")
                self.data_logger = DataLogger(
                    enable_csv=csv_enabled,
                    enable_json=json_enabled
                )

            self.log.info("Data logging enabled")
        except Exception as e:
            self.log.error(f"Failed to initialize logger: {e}")
            self.data_logger = None

    def _init_motion_sensor(self):
        """Initialize motion sensor."""
        try:
            sensor_type = self.config.get("motion_sensor_type", "none")
            self.log.info(f"Initializing motion sensor: {sensor_type}")

            self.motion_sensor = create_motion_sensor(
                sensor_type,
                pin=self.config.get("motion_sensor_pin", 22)
            )

            if self.motion_sensor:
                # Configure threshold
                threshold = self.config.get("motion_threshold_g", 0.1)
                self.motion_sensor.configure_threshold(threshold)

                # Set callback for wake-on-motion
                if self.config.get("wake_on_motion", False):
                    self.motion_sensor.set_callback(self._motion_callback)

                self.log.info("Motion sensor initialized")
        except Exception as e:
            self.log.error(f"Failed to initialize motion sensor: {e}")
            self.motion_sensor = None

    def _motion_callback(self):
        """Callback when motion is detected."""
        self._motion_woke_us = True

    def run(self):
        """Main application loop."""
        self.log.info("Starting main loop")

        while True:
            try:
                # Feed watchdog
                if self.watchdog:
                    self.watchdog.feed()

                # Update GPS data
                self.gps.update()

                # Check schedule (if enabled)
                if not self._is_within_schedule():
                    self._handle_scheduled_sleep()
                    continue

                # Run state machine
                self._run_state_machine()

                # Handle data logging (separate from transmission)
                self._handle_data_logging()

                # Small delay to prevent tight loop
                time.sleep_ms(100)

            except Exception as e:
                self.log.error(f"Main loop error: {e}")
                self.leds.indicate_error()
                self.state = State.ERROR
                self.error_message = str(e)
                time.sleep(1)

    def _is_within_schedule(self):
        """Check if current time is within scheduled awake hours.

        Returns:
            bool: True if should be active
        """
        if not self.config.get("schedule_enabled", False):
            return True

        # Need valid GPS time for scheduling
        if not self.gps.valid:
            return True  # Can't determine schedule without time

        try:
            current_hour = self.gps.hour
            current_minute = self.gps.minute

            # Parse schedule times
            start_str = self.config.get("schedule_awake_start", "06:00")
            end_str = self.config.get("schedule_awake_end", "22:00")

            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))

            current_mins = current_hour * 60 + current_minute
            start_mins = start_hour * 60 + start_min
            end_mins = end_hour * 60 + end_min

            # Check if within schedule
            if start_mins <= end_mins:
                return start_mins <= current_mins <= end_mins
            else:
                # Schedule crosses midnight
                return current_mins >= start_mins or current_mins <= end_mins

        except Exception:
            return True  # On error, stay active

    def _handle_scheduled_sleep(self):
        """Handle sleep when outside scheduled hours."""
        self.log.info("Outside scheduled hours, sleeping...")
        self.leds.all_off()

        # Calculate sleep duration (check every 5 minutes)
        sleep_duration = 5 * 60 * 1000  # 5 minutes in ms

        if self.config.get("wake_on_motion", False) and self.motion_sensor:
            # Light sleep to allow motion wake
            self.power.light_sleep(sleep_duration)
            if self._motion_woke_us:
                self.log.info("Woken by motion")
                self._motion_woke_us = False
        else:
            self.power.light_sleep(sleep_duration)

    def _handle_data_logging(self):
        """Handle local data logging (separate from transmission)."""
        if not self.data_logger:
            return

        if self.operating_mode not in ("logging", "both"):
            return

        # Check logging interval
        log_interval = self.config.get("logging_interval_sec", 5) * 1000
        elapsed = time.ticks_diff(time.ticks_ms(), self.last_log_time)

        if elapsed >= log_interval or self.last_log_time == 0:
            gps_data = self.gps.get_position()
            self._update_device_status()

            if self.data_logger.log(gps_data, self.device_status.to_dict()):
                self.log.debug(f"Logged position: {gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}")
                self.last_log_time = time.ticks_ms()

    def _get_report_interval(self):
        """Get current report interval based on adaptive settings.

        Returns:
            int: Report interval in milliseconds
        """
        base_interval = self.config.get("report_interval_sec", 10)

        if self.config.get("adaptive_reporting", False):
            # Check motion
            if self.motion_sensor:
                if self.motion_sensor.is_motion_detected():
                    self._is_moving = True
                elif hasattr(self.motion_sensor, 'is_moving'):
                    self._is_moving = self.motion_sensor.is_moving()
            else:
                # Use GPS speed to detect motion
                self._is_moving = self.gps.speed_kmh > 2.0

            if self._is_moving:
                base_interval = self.config.get("moving_interval_sec", 10)
            else:
                base_interval = self.config.get("stationary_interval_sec", 60)

        return base_interval * 1000

    def _run_state_machine(self):
        """Execute current state and handle transitions."""

        if self.state == State.STARTUP:
            self._state_startup()

        elif self.state == State.INIT:
            self._state_init()

        elif self.state == State.GPS_ACQUIRE:
            self._state_gps_acquire()

        elif self.state == State.NETWORK_CONNECT:
            self._state_network_connect()

        elif self.state == State.READY:
            self._state_ready()

        elif self.state == State.TRANSMIT:
            self._state_transmit()

        elif self.state == State.SLEEP:
            self._state_sleep()

        elif self.state == State.ERROR:
            self._state_error()

    def _state_startup(self):
        """Startup state - initial checks."""
        self.log.info("State: STARTUP")

        # Check battery
        battery_pct = self.power.get_battery_percentage()
        self.log.info(f"Battery: {battery_pct}%")

        if self.power.is_battery_critical():
            self.log.error("Battery critically low!")
            self.leds.error_on()
            self.state = State.ERROR
            self.error_message = "Battery critical"
            return

        self.state = State.INIT

    def _state_init(self):
        """Initialization state."""
        self.log.info("State: INIT")

        # Power on peripherals
        self.power.enable_all_peripherals()

        # If using cellular, power on the module
        if self.network and isinstance(self.network, CellularDriver):
            self.log.info("Powering on cellular module...")
            self.network.power_on()

        self.state = State.GPS_ACQUIRE

    def _state_gps_acquire(self):
        """GPS acquisition state."""
        self.log.debug("State: GPS_ACQUIRE")
        self.leds.update_gps_status(has_fix=False, acquiring=True)

        # Update GPS
        self.gps.update()

        if self.gps.valid:
            self.log.info(f"GPS fix acquired: {self.gps.latitude:.6f}, {self.gps.longitude:.6f}")
            self.log.info(f"Satellites: {self.gps.satellites}, HDOP: {self.gps.hdop}")
            self.leds.update_gps_status(has_fix=True)

            # Skip network if logging-only mode
            if self.operating_mode == "logging":
                self.state = State.READY
            else:
                self.state = State.NETWORK_CONNECT
            return

    def _state_network_connect(self):
        """Network connection state."""
        # Skip if logging-only mode
        if self.operating_mode == "logging":
            self.state = State.READY
            return

        self.log.info("State: NETWORK_CONNECT")
        self.leds.update_network_status(connected=False, connecting=True)

        if self.network.is_connected():
            self.log.info("Already connected to network")
            self.leds.update_network_status(connected=True)
            self.state = State.READY
            return

        self.log.info("Connecting to network...")

        if self.network.connect(timeout_sec=30):
            ip = self.network.get_ip_address()
            self.log.info(f"Connected! IP: {ip}")
            self.leds.update_network_status(connected=True)
            self.state = State.READY
        else:
            self.log.error(f"Network connection failed: {self.network.last_error}")
            self.retry_count += 1

            if self.retry_count >= Timing.MAX_RETRIES:
                if self.operating_mode == "both":
                    # Fall back to logging-only
                    self.log.warning("Network unavailable, falling back to logging mode")
                    self.state = State.READY
                else:
                    self.state = State.ERROR
                    self.error_message = "Network connection failed"
            else:
                self.log.info(f"Retrying... ({self.retry_count}/{Timing.MAX_RETRIES})")
                time.sleep_ms(Timing.CONNECT_RETRY_MS)

    def _state_ready(self):
        """Ready state - waiting for next transmit time."""
        self.log.debug("State: READY")

        # Check if it's time to transmit
        report_interval = self._get_report_interval()
        elapsed = time.ticks_diff(time.ticks_ms(), self.last_transmit_time)

        if elapsed >= report_interval or self.last_transmit_time == 0:
            if self.operating_mode in ("cinet", "both"):
                self.state = State.TRANSMIT
            else:
                # Logging-only mode: just update timestamp
                self.last_transmit_time = time.ticks_ms()
            return

        # Update GPS while waiting
        self.gps.update()
        self.leds.update_gps_status(has_fix=self.gps.valid, acquiring=not self.gps.valid)

        # Check network status (if applicable)
        if self.operating_mode in ("cinet", "both") and self.network:
            if not self.network.is_connected():
                self.log.warning("Network connection lost")
                self.leds.update_network_status(connected=False)
                self.state = State.NETWORK_CONNECT

    def _state_transmit(self):
        """Transmit state - send position to server."""
        # Skip if logging-only mode
        if self.operating_mode == "logging":
            self.last_transmit_time = time.ticks_ms()
            self.state = State.READY
            return

        self.log.info("State: TRANSMIT")

        # Update device status
        self._update_device_status()

        # Get GPS data
        gps_data = self.gps.get_position()

        # Build message
        self.log.debug("Building ciNet message...")
        message = self.protocol.build(gps_data, self.device_status.to_dict())

        # Log message (debug)
        self.log.debug(f"Message ({len(message)} bytes)")

        # Send to server
        host = self.config.get("server_host")
        port = self.config.get("server_port")

        self.log.info(f"Sending to {host}:{port}...")
        self.leds.indicate_transmit()

        if self.network.send_tcp(host, port, message, timeout_ms=Timing.NETWORK_TIMEOUT_MS):
            self.log.info("Transmission successful!")
            self.last_transmit_time = time.ticks_ms()
            self.retry_count = 0

            # Check if sleep mode enabled
            if self.config.get("sleep_enabled", False):
                self.state = State.SLEEP
            else:
                self.state = State.READY
        else:
            self.log.error(f"Transmission failed: {self.network.last_error}")
            self.retry_count += 1

            if self.retry_count >= Timing.MAX_RETRIES:
                # Try reconnecting
                self.state = State.NETWORK_CONNECT
                self.retry_count = 0
            else:
                # Retry transmit
                time.sleep_ms(1000)

    def _state_sleep(self):
        """Sleep state - power saving between reports."""
        self.log.info("State: SLEEP")

        interval_sec = self.config.get("report_interval_sec", 10)
        self.log.info(f"Sleeping for {interval_sec} seconds...")

        # Update LEDs
        self.leds.all_off()

        # Choose sleep mode
        if self.config.get("deep_sleep_enabled", False):
            self.power.deep_sleep(interval_sec * 1000)
            # Note: Device resets after deep sleep
        else:
            self.power.light_sleep(interval_sec * 1000)

        # Wake up
        self.log.info("Waking up")
        self.state = State.GPS_ACQUIRE

    def _state_error(self):
        """Error state - handle errors."""
        self.log.error(f"State: ERROR - {self.error_message}")

        self.leds.error_on()
        self.leds.gps_off()
        self.leds.network_off()

        # Wait and retry
        time.sleep(5)

        # Check if recoverable
        if not self.power.is_battery_critical():
            self.log.info("Attempting recovery...")
            self.retry_count = 0
            self.error_message = None
            self.leds.error_off()
            self.state = State.INIT

    def _update_device_status(self):
        """Update device status for transmission."""
        self.device_status.battery = self.power.get_battery_percentage()

        # Get network info if cellular
        if self.network and isinstance(self.network, CellularDriver):
            cell_info = self.network.get_cell_info()
            self.device_status.rssi = cell_info.get('rssi', 0)
            self.device_status.lac = cell_info.get('lac', 0)
            self.device_status.cell_id = cell_info.get('cell_id', 0)
        elif self.network:
            self.device_status.rssi = self.network.get_rssi()

        # Motion state
        if self.motion_sensor:
            self.device_status.motion = 1 if self._is_moving else 0


def main():
    """Entry point."""
    print("\n" + "=" * 50)
    print("    Pico Beacon - ciNet GPS Tracker")
    print("    Firmware v1.0.0")
    print("=" * 50 + "\n")

    try:
        beacon = PicoBeacon()
        beacon.run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        # Blink onboard LED rapidly to indicate fatal error
        try:
            led = machine.Pin("LED", machine.Pin.OUT)
        except Exception:
            led = machine.Pin(25, machine.Pin.OUT)

        while True:
            led.toggle()
            time.sleep_ms(100)


# Run when module is executed directly
if __name__ == "__main__":
    main()
