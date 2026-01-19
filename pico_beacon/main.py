# Pico Beacon - Main Application
# ciNet-compatible GPS tracking beacon for Raspberry Pi Pico
# Implements RAPID 2 feature set
#
# Operating Modes (RAPID 2):
#   - "active": Normal tracking (moving/stopped adaptive rates)
#   - "deployment": First 20 minutes after power-on (fast reporting)
#   - "standby": Low power, wake on motion/command
#   - "hibernate": Deep sleep, wake on command only
#   - "forever_standby": Indefinite standby, SMS wake only
#   - "continuous": Continuous reporting at moving rate
#   - "logging": Local logging only (no network)

import time
import machine

from config import ConfigManager, Pins, State, Timing, OperatingMode, AlertType


class PicoBeacon:
    """Main beacon application with RAPID 2 state machine."""

    # Deployment mode duration (20 minutes in ms)
    DEPLOYMENT_DURATION_MS = 20 * 60 * 1000

    def __init__(self):
        """Initialize the beacon."""
        # Startup time for deployment mode
        self._startup_time = time.ticks_ms()

        # Late imports to reduce memory on startup
        from utils.logger import Logger, LogLevel
        self.log = Logger("Beacon", LogLevel.INFO)
        self.log.info("Pico Beacon initializing...")

        # Configuration
        self.config = ConfigManager()
        self._rf_enabled = self.config.get("rf_enabled", True)
        self._rf_mode = self.config.get("rf_mode", "auto")

        self.log.info(f"Serial: {self.config.get('serial_number')}")
        self.log.info(f"Server: {self.config.get('server_host')}:{self.config.get('server_port')}")

        # Initialize components
        self._init_leds()
        self._init_power()
        self._init_gps()
        self._init_network()
        self._init_protocol()
        self._init_data_logger()
        self._init_motion_sensor()
        self._init_io_controller()
        self._init_command_handlers()

        # State machine
        self.state = State.STARTUP
        self.last_transmit_time = 0
        self.last_log_time = 0
        self.retry_count = 0
        self.error_message = None

        # Motion state
        self._is_moving = False
        self._motion_woke_us = False
        self._motion_timeout_start = 0

        # Mode flags
        self._deployment_mode = True  # Start in deployment mode
        self._continuous_mode = False
        self._reboot_requested = False
        self._log_upload_requested = False

        # Alerts pending
        self._pending_alerts = []

        # Watchdog timer
        try:
            self.watchdog = machine.WDT(timeout=30000)
        except Exception:
            self.watchdog = None
            self.log.warning("Watchdog not available")

        self.log.info("Initialization complete")

    def _init_leds(self):
        """Initialize status LEDs."""
        from utils.led_status import StatusLED
        self.leds = StatusLED(
            gps_pin=Pins.LED_GPS,
            network_pin=Pins.LED_NETWORK,
            error_pin=Pins.LED_ERROR,
            onboard_pin=Pins.LED_ONBOARD
        )
        # RAPID 2 startup sequence: Green 1s -> Red 1s -> Blue constant
        self.leds.rapid2_startup_sequence()

    def _init_power(self):
        """Initialize power manager."""
        from utils.power_manager import PowerManager
        self.power = PowerManager(
            battery_adc_pin=Pins.BATTERY_ADC,
            gps_enable_pin=getattr(Pins, 'GPS_ENABLE', None),
            cell_enable_pin=getattr(Pins, 'CELL_ENABLE', None)
        )

    def _init_gps(self):
        """Initialize GPS driver."""
        from drivers.gps_driver import GPSDriver
        self.gps = GPSDriver(
            uart_id=0,
            tx_pin=Pins.GPS_TX,
            rx_pin=Pins.GPS_RX,
            baudrate=9600
        )

    def _init_network(self):
        """Initialize network driver."""
        network_type = self.config.get("network_type", "wifi")

        if network_type == "cellular":
            from drivers.network_cellular import CellularDriver
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
            from drivers.network_wifi import WiFiDriver
            self.log.info("Using WiFi network")
            self.network = WiFiDriver(
                ssid=self.config.get("wifi_ssid"),
                password=self.config.get("wifi_password")
            )

    def _init_protocol(self):
        """Initialize ciNet protocol handler."""
        from protocol.cinet_message import CiNetMessage, DeviceStatus
        self.protocol = CiNetMessage(self.config)
        self.device_status = DeviceStatus()

    def _init_data_logger(self):
        """Initialize data logger."""
        if not self.config.get("logging_enabled", True):
            self.data_logger = None
            return

        try:
            from utils.data_logger import DataLogger, SDCardLogger
            use_sd = self.config.get("log_to_sd_card", False)
            csv_enabled = self.config.get("log_format_csv", True)
            json_enabled = self.config.get("log_format_json", False)

            if use_sd:
                self.data_logger = SDCardLogger(enable_csv=csv_enabled, enable_json=json_enabled)
            else:
                self.data_logger = DataLogger(enable_csv=csv_enabled, enable_json=json_enabled)

            self.log.info("Data logging enabled")
        except Exception as e:
            self.log.error(f"Logger init failed: {e}")
            self.data_logger = None

    def _init_motion_sensor(self):
        """Initialize motion sensor."""
        if not self.config.get("motion_sensor_enabled", True):
            self.motion_sensor = None
            return

        try:
            from drivers.motion_sensor import create_motion_sensor
            sensor_type = self.config.get("motion_sensor_type", "accelerometer")

            self.motion_sensor = create_motion_sensor(
                sensor_type,
                pin=self.config.get("motion_sensor_pin", 22)
            )

            if self.motion_sensor:
                threshold = self.config.get("motion_threshold_g", 0.15)
                self.motion_sensor.configure_threshold(threshold)
                self.motion_sensor.set_callback(self._motion_callback)
                self.log.info(f"Motion sensor: {sensor_type}")
        except Exception as e:
            self.log.error(f"Motion sensor init failed: {e}")
            self.motion_sensor = None

    def _init_io_controller(self):
        """Initialize I/O controller and tamper detection."""
        if not self.config.get("io_enabled", True):
            self.io_controller = None
            self.tamper_detector = None
            return

        try:
            from handlers.io_controller import IOController, TamperDetector

            self.io_controller = IOController(
                self.config,
                input_pin=self.config.get("input_pin", 18),
                output_pin=self.config.get("output_pin", 19),
                input_active_high=self.config.get("input_active_high", True)
            )
            self.io_controller.set_alert_callback(self._handle_io_alert)

            if self.config.get("tamper_enabled", False):
                self.tamper_detector = TamperDetector(
                    self.config,
                    tamper_pin=self.config.get("tamper_pin", 21)
                )
                self.tamper_detector.set_alert_callback(self._handle_io_alert)
            else:
                self.tamper_detector = None

            self.log.info("I/O controller initialized")
        except Exception as e:
            self.log.error(f"I/O init failed: {e}")
            self.io_controller = None
            self.tamper_detector = None

    def _init_command_handlers(self):
        """Initialize SMS and GPRS command handlers."""
        try:
            from handlers.sms_commands import SMSCommandHandler
            from handlers.gprs_commands import GPRSCommandHandler

            self.sms_handler = SMSCommandHandler(
                self.config, self, self.gps, self.io_controller
            )

            self.gprs_handler = GPRSCommandHandler(
                self.config, self, self.data_logger, self.io_controller
            )

            self.log.info("Command handlers initialized")
        except Exception as e:
            self.log.error(f"Command handler init failed: {e}")
            self.sms_handler = None
            self.gprs_handler = None

    def _motion_callback(self):
        """Callback when motion is detected."""
        self._motion_woke_us = True
        self._is_moving = True
        self._motion_timeout_start = time.ticks_ms()

    def _handle_io_alert(self, alert_type, value):
        """Handle I/O or tamper alerts."""
        if alert_type == "input_change" and self.config.get("alert_input_change", True):
            self._pending_alerts.append((AlertType.INPUT_CHANGE, value))
        elif alert_type == "tamper" and self.config.get("alert_tamper", True):
            self._pending_alerts.append((AlertType.TAMPER, value))

    # ==========================================================================
    # STATE MACHINE METHODS (called by command handlers)
    # ==========================================================================

    def set_rf_enabled(self, enabled):
        """Enable/disable RF transmission."""
        self._rf_enabled = enabled
        self.log.info(f"RF {'enabled' if enabled else 'disabled'}")

    def set_rf_mode_auto(self):
        """Set RF to automatic mode."""
        self._rf_mode = "auto"
        self._rf_enabled = True

    def enter_standby(self):
        """Enter standby mode."""
        self.config.set("operating_mode", OperatingMode.STANDBY)
        self.state = State.STANDBY
        self.log.info("Entering standby mode")

    def exit_standby(self):
        """Exit standby mode."""
        self.config.set("operating_mode", OperatingMode.ACTIVE)
        self.state = State.GPS_ACQUIRE
        self.log.info("Exiting standby mode")

    def enter_hibernate(self):
        """Enter hibernate mode."""
        self.config.set("operating_mode", OperatingMode.HIBERNATE)
        self.state = State.HIBERNATE
        self.log.info("Entering hibernate mode")

    def enter_forever_standby(self):
        """Enter forever standby mode."""
        self.config.set("operating_mode", "forever_standby")
        self.state = State.STANDBY
        self.log.info("Entering forever standby mode")

    def enter_continuous_mode(self):
        """Enter continuous reporting mode."""
        self._continuous_mode = True
        self.config.set("operating_mode", "continuous")
        self.log.info("Entering continuous mode")

    def reset_to_config(self):
        """Reset to stored configuration."""
        self._continuous_mode = False
        self._rf_enabled = True
        self._rf_mode = "auto"
        self.config.set("operating_mode", OperatingMode.ACTIVE)
        self.state = State.GPS_ACQUIRE
        self.log.info("Reset to configuration")

    def request_reboot(self):
        """Request a system reboot."""
        self._reboot_requested = True

    def request_log_upload(self):
        """Request log upload."""
        self._log_upload_requested = True

    def get_battery_percent(self):
        """Get battery percentage."""
        return self.power.get_battery_percentage()

    def is_moving(self):
        """Check if device is moving."""
        return self._is_moving

    # ==========================================================================
    # MAIN LOOP
    # ==========================================================================

    def run(self):
        """Main application loop."""
        self.log.info("Starting main loop")

        while True:
            try:
                # Feed watchdog
                if self.watchdog:
                    self.watchdog.feed()

                # Check for reboot request
                if self._reboot_requested:
                    self.log.info("Rebooting...")
                    time.sleep_ms(500)
                    machine.reset()

                # Update GPS
                self.gps.update()

                # Update motion state
                self._update_motion_state()

                # Update I/O controller
                if self.io_controller:
                    self.io_controller.update()
                    self.io_controller.update_motion_state(self._is_moving)

                # Check deployment mode expiry
                self._check_deployment_mode()

                # Run state machine
                self._run_state_machine()

                # Handle data logging
                self._handle_data_logging()

                # Handle SMS tracking updates
                if self.sms_handler and self.sms_handler.is_tracking:
                    msg = self.sms_handler.update()
                    if msg:
                        self._send_sms_response(msg)

                # Small delay
                time.sleep_ms(100)

            except Exception as e:
                self.log.error(f"Main loop error: {e}")
                self.leds.indicate_error()
                self.state = State.ERROR
                self.error_message = str(e)
                time.sleep(1)

    def _update_motion_state(self):
        """Update motion state with timeout."""
        # Check motion sensor
        if self.motion_sensor:
            if self.motion_sensor.is_motion_detected():
                self._is_moving = True
                self._motion_timeout_start = time.ticks_ms()
            elif hasattr(self.motion_sensor, 'is_moving'):
                if self.motion_sensor.is_moving():
                    self._is_moving = True
                    self._motion_timeout_start = time.ticks_ms()
        else:
            # Use GPS speed
            if self.gps.speed_kmh > 2.0:
                self._is_moving = True
                self._motion_timeout_start = time.ticks_ms()

        # Check motion timeout
        if self._is_moving:
            timeout_sec = self.config.get("motion_timeout_sec", 120)
            elapsed = time.ticks_diff(time.ticks_ms(), self._motion_timeout_start)
            if elapsed > timeout_sec * 1000:
                self._is_moving = False
                self.log.info("Motion timeout - now stopped")

    def _check_deployment_mode(self):
        """Check if deployment mode should end (after 20 minutes)."""
        if not self._deployment_mode:
            return

        elapsed = time.ticks_diff(time.ticks_ms(), self._startup_time)
        if elapsed > self.DEPLOYMENT_DURATION_MS:
            self._deployment_mode = False
            self.log.info("Deployment mode ended - switching to normal operation")

    def _get_report_interval_ms(self):
        """Get current report interval based on mode and motion.

        RAPID 2 rates:
        - Deployment: Moving rate (first 20 minutes)
        - Continuous: Moving rate always
        - Moving: Moving rate (5-86400 sec)
        - Stopped: Stopped rate (5-86400 sec)
        - Standby: Standby rate (hourly check-in)
        """
        mode = self.config.get("operating_mode", OperatingMode.ACTIVE)

        # Deployment mode: use moving rate
        if self._deployment_mode:
            return self.config.get("gprs_rate_moving_sec", 10) * 1000

        # Continuous mode: use moving rate
        if self._continuous_mode:
            return self.config.get("gprs_rate_moving_sec", 10) * 1000

        # Standby mode: use standby rate
        if mode == OperatingMode.STANDBY or mode == "forever_standby":
            return self.config.get("gprs_rate_standby_sec", 3600) * 1000

        # Active mode: adaptive based on motion
        if self._is_moving:
            return self.config.get("gprs_rate_moving_sec", 10) * 1000
        else:
            return self.config.get("gprs_rate_stopped_sec", 60) * 1000

    def _handle_data_logging(self):
        """Handle local data logging."""
        if not self.data_logger:
            return

        log_interval = self.config.get("logging_rate_sec", 10) * 1000
        elapsed = time.ticks_diff(time.ticks_ms(), self.last_log_time)

        if elapsed >= log_interval or self.last_log_time == 0:
            gps_data = self.gps.get_position()
            self._update_device_status()

            if self.data_logger.log(gps_data, self.device_status.to_dict()):
                self.last_log_time = time.ticks_ms()

    def _run_state_machine(self):
        """Execute current state."""
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
        elif self.state == State.STANDBY:
            self._state_standby()
        elif self.state == State.HIBERNATE:
            self._state_hibernate()
        elif self.state == State.LOG_UPLOAD:
            self._state_log_upload()
        elif self.state == State.ERROR:
            self._state_error()

    def _state_startup(self):
        """Startup state."""
        self.log.info("State: STARTUP")

        battery_pct = self.power.get_battery_percentage()
        self.log.info(f"Battery: {battery_pct}%")

        if self.power.is_battery_critical():
            self.log.error("Battery critical!")
            self.leds.error_on()
            self.state = State.ERROR
            self.error_message = "Battery critical"
            return

        self.state = State.INIT

    def _state_init(self):
        """Initialization state."""
        self.log.info("State: INIT")

        self.power.enable_all_peripherals()

        # Power on cellular if needed
        if hasattr(self.network, 'power_on'):
            self.log.info("Powering on cellular...")
            self.network.power_on()

        self.state = State.GPS_ACQUIRE

    def _state_gps_acquire(self):
        """GPS acquisition state."""
        # RAPID 2 LED: Cyan when acquiring
        self.leds.update_gps_status(has_fix=False, acquiring=True)

        self.gps.update()

        if self.gps.valid:
            self.log.info(f"GPS fix: {self.gps.latitude:.6f}, {self.gps.longitude:.6f}")
            # RAPID 2 LED: Purple when has fix
            self.leds.update_gps_status(has_fix=True)

            mode = self.config.get("operating_mode", OperatingMode.ACTIVE)
            if mode == OperatingMode.LOGGING:
                self.state = State.READY
            else:
                self.state = State.NETWORK_CONNECT

    def _state_network_connect(self):
        """Network connection state."""
        if not self._rf_enabled:
            self.state = State.READY
            return

        self.log.info("State: NETWORK_CONNECT")
        self.leds.update_network_status(connected=False, connecting=True)

        if self.network.is_connected():
            self.leds.update_network_status(connected=True)
            self.state = State.READY
            return

        if self.network.connect(timeout_sec=30):
            self.log.info(f"Connected: {self.network.get_ip_address()}")
            self.leds.update_network_status(connected=True)
            self.state = State.READY
        else:
            self.log.error(f"Connect failed: {self.network.last_error}")
            self.retry_count += 1

            if self.retry_count >= Timing.MAX_RETRIES:
                self.log.warning("Network unavailable")
                self.state = State.READY  # Continue in logging mode
            else:
                time.sleep_ms(Timing.CONNECT_RETRY_MS)

    def _state_ready(self):
        """Ready state - waiting for next transmit."""
        # Check log upload request
        if self._log_upload_requested:
            self._log_upload_requested = False
            self.state = State.LOG_UPLOAD
            return

        # Check GPRS command requests
        if self.gprs_handler:
            if self.gprs_handler.is_status_requested():
                self.state = State.TRANSMIT  # Force immediate transmit
                return
            if self.gprs_handler.is_locate_requested():
                self.state = State.TRANSMIT
                return

        # Check alerts
        if self._pending_alerts:
            self.state = State.TRANSMIT
            return

        # Check time for next transmit
        report_interval = self._get_report_interval_ms()
        elapsed = time.ticks_diff(time.ticks_ms(), self.last_transmit_time)

        if elapsed >= report_interval or self.last_transmit_time == 0:
            if self._rf_enabled:
                self.state = State.TRANSMIT
            else:
                self.last_transmit_time = time.ticks_ms()
            return

        # Update GPS
        self.gps.update()
        self.leds.update_gps_status(has_fix=self.gps.valid, acquiring=not self.gps.valid)

        # Check network
        if self._rf_enabled and self.network and not self.network.is_connected():
            self.leds.update_network_status(connected=False)
            self.state = State.NETWORK_CONNECT

    def _state_transmit(self):
        """Transmit position to server."""
        if not self._rf_enabled:
            self.last_transmit_time = time.ticks_ms()
            self.state = State.READY
            return

        self.log.info("State: TRANSMIT")
        self._update_device_status()

        gps_data = self.gps.get_position()

        # Build message with any pending alerts
        alert_mask = 0
        for alert_type, _ in self._pending_alerts:
            alert_mask |= alert_type
        self._pending_alerts.clear()

        message = self.protocol.build(gps_data, self.device_status.to_dict(), alert_mask)

        host = self.config.get("server_host")
        port = self.config.get("server_port")

        self.leds.indicate_transmit()

        if self.network.send_tcp(host, port, message, timeout_ms=Timing.NETWORK_TIMEOUT_MS):
            self.log.info("Transmit OK")
            self.last_transmit_time = time.ticks_ms()
            self.retry_count = 0
            self.state = State.READY
        else:
            self.log.error(f"Transmit failed: {self.network.last_error}")
            self.retry_count += 1

            if self.retry_count >= Timing.MAX_RETRIES:
                self.state = State.NETWORK_CONNECT
                self.retry_count = 0
            else:
                time.sleep_ms(1000)

    def _state_sleep(self):
        """Sleep state between reports."""
        self.leds.all_off()

        interval_ms = self._get_report_interval_ms()

        if self.config.get("deep_sleep_enabled", False):
            self.power.deep_sleep(interval_ms)
        else:
            self.power.light_sleep(interval_ms)

        self.state = State.GPS_ACQUIRE

    def _state_standby(self):
        """Standby mode - low power with periodic wake."""
        self.log.info("State: STANDBY")
        self.leds.all_off()

        mode = self.config.get("operating_mode", OperatingMode.STANDBY)
        wake_on_motion = self.config.get("standby_wake_on_motion", True)

        # Forever standby only wakes on SMS command
        if mode == "forever_standby":
            # TODO: Implement SMS wake check
            self.power.light_sleep(60000)
            return

        # Normal standby - wake on motion or interval
        check_interval = self.config.get("standby_check_interval_sec", 60) * 1000

        self.power.light_sleep(check_interval)

        # Check wake conditions
        if wake_on_motion and self._motion_woke_us:
            self._motion_woke_us = False
            self.log.info("Woken by motion")
            self.config.set("operating_mode", OperatingMode.ACTIVE)
            self.state = State.GPS_ACQUIRE
            return

        # Periodic check-in
        report_interval = self._get_report_interval_ms()
        elapsed = time.ticks_diff(time.ticks_ms(), self.last_transmit_time)

        if elapsed >= report_interval:
            self.state = State.GPS_ACQUIRE

    def _state_hibernate(self):
        """Hibernate mode - deep sleep with command-only wake."""
        self.log.info("State: HIBERNATE")
        self.leds.all_off()

        wake_interval = self.config.get("hibernate_wake_interval_hr", 24) * 3600 * 1000

        if self.config.get("deep_sleep_enabled", False):
            self.power.deep_sleep(wake_interval)
        else:
            self.power.light_sleep(wake_interval)

        # Check for command to exit hibernate
        # TODO: Check for GPRS/SMS command

        self.state = State.GPS_ACQUIRE

    def _state_log_upload(self):
        """Upload stored logs to server."""
        self.log.info("State: LOG_UPLOAD")

        if not self.data_logger:
            self.state = State.READY
            return

        # Get log files
        log_files = self.data_logger.get_log_files()
        self.log.info(f"Uploading {len(log_files)} log files...")

        # TODO: Implement log upload protocol

        self.state = State.READY

    def _state_error(self):
        """Error state."""
        self.log.error(f"State: ERROR - {self.error_message}")

        self.leds.error_on()
        self.leds.gps_off()
        self.leds.network_off()

        time.sleep(5)

        if not self.power.is_battery_critical():
            self.log.info("Attempting recovery...")
            self.retry_count = 0
            self.error_message = None
            self.leds.error_off()
            self.state = State.INIT

    def _update_device_status(self):
        """Update device status."""
        self.device_status.battery = self.power.get_battery_percentage()

        if hasattr(self.network, 'get_cell_info'):
            cell_info = self.network.get_cell_info()
            self.device_status.rssi = cell_info.get('rssi', 0)
            self.device_status.lac = cell_info.get('lac', 0)
            self.device_status.cell_id = cell_info.get('cell_id', 0)
        elif hasattr(self.network, 'get_rssi'):
            self.device_status.rssi = self.network.get_rssi()

        self.device_status.motion = 1 if self._is_moving else 0

        if self.io_controller:
            self.device_status.input_state = 1 if self.io_controller.get_input_state() else 0
            self.device_status.output_state = 1 if self.io_controller.get_output_state() else 0

    def _send_sms_response(self, message):
        """Send SMS response (if cellular network)."""
        if hasattr(self.network, 'send_sms'):
            dest = self.config.get("sms_destination", "")
            if dest:
                self.network.send_sms(dest, message)


def main():
    """Entry point."""
    print("\n" + "=" * 50)
    print("    Pico Beacon - ciNet GPS Tracker")
    print("    RAPID 2 Compatible | FW v2.0.0")
    print("=" * 50 + "\n")

    try:
        beacon = PicoBeacon()
        beacon.run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        try:
            led = machine.Pin("LED", machine.Pin.OUT)
        except Exception:
            led = machine.Pin(25, machine.Pin.OUT)

        while True:
            led.toggle()
            time.sleep_ms(100)


if __name__ == "__main__":
    main()
