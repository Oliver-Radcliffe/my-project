# SMS Command Handler for Pico Beacon
# Implements RAPID 2 SMS commands from Section 6.4 of the manual

import time


class SMSCommandHandler:
    """Handles incoming SMS commands and generates responses.

    RAPID 2 SMS Commands (Section 6.4):
    - Change Mode: RF On/Off/Auto, Continuous Report, Forever Standby, Reset, Button Enable/Disable
    - Output: Open, Close, Status
    - Tamper: On, Off
    - Ping: Confidence, Status, Map
    - Tracking: Stop, Track X,Y, Map Track X,Y
    """

    # Command constants
    CMD_RF_ON = "rf on"
    CMD_RF_OFF = "rf off"
    CMD_RF_AUTO = "rf auto"
    CMD_CONTINUOUS_REPORT = "continuous report"
    CMD_FOREVER_STANDBY = "forever standby"
    CMD_RESET = "reset"
    CMD_BUTTON_ENABLE = "button enable"
    CMD_BUTTON_DISABLE = "button disable"

    CMD_OUTPUT_OPEN = "output open"
    CMD_OUTPUT_CLOSE = "output close"
    CMD_OUTPUT_STATUS = "output status"

    CMD_TAMPER_ON = "tamper on"
    CMD_TAMPER_OFF = "tamper off"

    CMD_CONFIDENCE = "confidence"
    CMD_STATUS = "status"
    CMD_MAP = "map"

    CMD_STOP = "stop"
    CMD_TRACK = "track"
    CMD_MAP_TRACK = "map track"

    def __init__(self, config_manager, state_machine, gps_driver, io_controller=None):
        """Initialize SMS command handler.

        Args:
            config_manager: ConfigManager instance
            state_machine: Main state machine reference
            gps_driver: GPS driver for position data
            io_controller: I/O controller for output commands (optional)
        """
        self.config = config_manager
        self.state_machine = state_machine
        self.gps = gps_driver
        self.io = io_controller

        # Track SMS tracking state
        self._tracking_active = False
        self._tracking_count = 0
        self._tracking_interval = 0
        self._tracking_with_map = False
        self._last_track_time = 0

    def process_command(self, sender, message):
        """Process an incoming SMS command.

        Args:
            sender: Phone number of sender
            message: SMS message text

        Returns:
            str: Response message to send back, or None if no response needed
        """
        if not self.config.get("sms_commands_enabled", True):
            return None

        # Normalize command (lowercase, strip whitespace)
        cmd = message.lower().strip()

        # Parse command and parameters
        parts = cmd.split(',')
        base_cmd = parts[0].strip()
        params = [p.strip() for p in parts[1:]] if len(parts) > 1 else []

        # Route to appropriate handler
        try:
            # Change Mode Commands
            if base_cmd == self.CMD_RF_ON:
                return self._handle_rf_on()
            elif base_cmd == self.CMD_RF_OFF:
                return self._handle_rf_off()
            elif base_cmd == self.CMD_RF_AUTO:
                return self._handle_rf_auto()
            elif base_cmd == self.CMD_CONTINUOUS_REPORT:
                return self._handle_continuous_report()
            elif base_cmd == self.CMD_FOREVER_STANDBY:
                return self._handle_forever_standby()
            elif base_cmd == self.CMD_RESET:
                return self._handle_reset()
            elif base_cmd == self.CMD_BUTTON_ENABLE:
                return self._handle_button_enable()
            elif base_cmd == self.CMD_BUTTON_DISABLE:
                return self._handle_button_disable()

            # Output Commands
            elif base_cmd == self.CMD_OUTPUT_OPEN:
                return self._handle_output_open()
            elif base_cmd == self.CMD_OUTPUT_CLOSE:
                return self._handle_output_close()
            elif base_cmd == self.CMD_OUTPUT_STATUS:
                return self._handle_output_status()

            # Tamper Commands
            elif base_cmd == self.CMD_TAMPER_ON:
                return self._handle_tamper_on()
            elif base_cmd == self.CMD_TAMPER_OFF:
                return self._handle_tamper_off()

            # Ping Commands
            elif base_cmd == self.CMD_CONFIDENCE:
                return self._handle_confidence()
            elif base_cmd == self.CMD_STATUS:
                return self._handle_status()
            elif base_cmd == self.CMD_MAP:
                return self._handle_map()

            # Tracking Commands
            elif base_cmd == self.CMD_STOP:
                return self._handle_stop()
            elif base_cmd.startswith(self.CMD_MAP_TRACK):
                # "map track X,Y" format
                return self._handle_map_track(params)
            elif base_cmd.startswith(self.CMD_TRACK):
                # "track X,Y" format
                return self._handle_track(params)

            else:
                return f"Unknown command: {base_cmd}"

        except Exception as e:
            return f"Error: {e}"

    # ==========================================================================
    # CHANGE MODE COMMANDS
    # ==========================================================================

    def _handle_rf_on(self):
        """RF On - Enable RF transmission immediately."""
        self.config.set("rf_enabled", True)
        self.config.set("rf_mode", "on")
        self.config.save()

        if self.state_machine:
            self.state_machine.set_rf_enabled(True)

        return "RF transmission enabled"

    def _handle_rf_off(self):
        """RF Off - Disable RF transmission (logging only mode)."""
        self.config.set("rf_enabled", False)
        self.config.set("rf_mode", "off")
        self.config.save()

        if self.state_machine:
            self.state_machine.set_rf_enabled(False)

        return "RF transmission disabled - logging only"

    def _handle_rf_auto(self):
        """RF Auto - Automatic RF control based on configuration."""
        self.config.set("rf_mode", "auto")
        self.config.set("rf_enabled", True)
        self.config.save()

        if self.state_machine:
            self.state_machine.set_rf_mode_auto()

        return "RF set to automatic mode"

    def _handle_continuous_report(self):
        """Continuous Report - Enter continuous reporting mode.

        Device reports at moving rate continuously regardless of motion state.
        """
        self.config.set("operating_mode", "continuous")
        self.config.save()

        if self.state_machine:
            self.state_machine.enter_continuous_mode()

        rate = self.config.get("gprs_rate_moving_sec", 10)
        return f"Continuous report mode - {rate}s interval"

    def _handle_forever_standby(self):
        """Forever Standby - Enter indefinite standby mode.

        Device enters low power standby until commanded to wake.
        Only wakes for SMS commands.
        """
        self.config.set("operating_mode", "forever_standby")
        self.config.save()

        if self.state_machine:
            self.state_machine.enter_forever_standby()

        return "Entering forever standby mode"

    def _handle_reset(self):
        """Reset - Reset device to configured defaults."""
        self.config.set("operating_mode", "active")
        self.config.set("rf_mode", "auto")
        self.config.set("rf_enabled", True)
        self._tracking_active = False
        self.config.save()

        if self.state_machine:
            self.state_machine.reset_to_config()

        return "Device reset to configured defaults"

    def _handle_button_enable(self):
        """Button Enable - Enable physical button functionality."""
        self.config.set("button_enabled", True)
        self.config.save()
        return "Button enabled"

    def _handle_button_disable(self):
        """Button Disable - Disable physical button functionality."""
        self.config.set("button_enabled", False)
        self.config.save()
        return "Button disabled"

    # ==========================================================================
    # OUTPUT COMMANDS
    # ==========================================================================

    def _handle_output_open(self):
        """Output Open - Activate the output (open drain ON)."""
        if self.io:
            self.io.set_output(True)
            return "Output opened"
        else:
            self.config.set("output_state", True)
            return "Output opened (no I/O controller)"

    def _handle_output_close(self):
        """Output Close - Deactivate the output (open drain OFF)."""
        if self.io:
            self.io.set_output(False)
            return "Output closed"
        else:
            self.config.set("output_state", False)
            return "Output closed (no I/O controller)"

    def _handle_output_status(self):
        """Output Status - Report current output state."""
        if self.io:
            state = "OPEN" if self.io.get_output_state() else "CLOSED"
        else:
            state = "OPEN" if self.config.get("output_state", False) else "CLOSED"
        return f"Output: {state}"

    # ==========================================================================
    # TAMPER COMMANDS
    # ==========================================================================

    def _handle_tamper_on(self):
        """Tamper On - Enable tamper detection alerts."""
        self.config.set("tamper_enabled", True)
        self.config.set("tamper_alert_enabled", True)
        self.config.save()
        return "Tamper alerts enabled"

    def _handle_tamper_off(self):
        """Tamper Off - Disable tamper detection alerts."""
        self.config.set("tamper_alert_enabled", False)
        self.config.save()
        return "Tamper alerts disabled"

    # ==========================================================================
    # PING COMMANDS
    # ==========================================================================

    def _handle_confidence(self):
        """Confidence - Send a confidence ping (minimal response).

        Used to verify device is responding without full status.
        """
        return "OK"

    def _handle_status(self):
        """Status - Send full device status report."""
        status_parts = []

        # GPS status
        if self.gps:
            pos = self.gps.get_position()
            if pos and pos.get('valid'):
                status_parts.append(f"GPS:FIX {pos.get('satellites', 0)}sats")
            else:
                status_parts.append("GPS:NO FIX")

        # Battery
        if self.state_machine:
            battery = self.state_machine.get_battery_percent()
            status_parts.append(f"BAT:{battery}%")

        # Motion
        if self.state_machine:
            motion = "MOVING" if self.state_machine.is_moving() else "STOPPED"
            status_parts.append(motion)

        # Operating mode
        mode = self.config.get("operating_mode", "active").upper()
        status_parts.append(f"MODE:{mode}")

        # RF state
        rf = "ON" if self.config.get("rf_enabled", True) else "OFF"
        status_parts.append(f"RF:{rf}")

        # Input state
        if self.io:
            inp = "HIGH" if self.io.get_input_state() else "LOW"
            status_parts.append(f"IN:{inp}")

        # Output state
        if self.io:
            out = "OPEN" if self.io.get_output_state() else "CLOSED"
            status_parts.append(f"OUT:{out}")

        return " | ".join(status_parts)

    def _handle_map(self):
        """Map - Send Google Maps link to current position."""
        if not self.gps:
            return "GPS not available"

        pos = self.gps.get_position()
        if not pos or not pos.get('valid'):
            return "No GPS fix"

        lat = pos.get('latitude', 0)
        lon = pos.get('longitude', 0)

        # Generate Google Maps link
        return f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"

    # ==========================================================================
    # TRACKING COMMANDS
    # ==========================================================================

    def _handle_stop(self):
        """Stop - Stop any active SMS tracking."""
        self._tracking_active = False
        self._tracking_count = 0
        return "Tracking stopped"

    def _handle_track(self, params):
        """Track X,Y - Start SMS tracking.

        Args:
            params: [count, interval_minutes]
                count: Number of position reports to send
                interval: Interval between reports in minutes

        Example: "track 5,10" = 5 reports every 10 minutes
        """
        if len(params) < 2:
            return "Usage: track COUNT,INTERVAL_MINUTES"

        try:
            count = int(params[0])
            interval = int(params[1])
        except ValueError:
            return "Invalid parameters"

        if count < 1 or count > 100:
            return "Count must be 1-100"
        if interval < 1 or interval > 60:
            return "Interval must be 1-60 minutes"

        self._tracking_active = True
        self._tracking_count = count
        self._tracking_interval = interval * 60  # Convert to seconds
        self._tracking_with_map = False
        self._last_track_time = time.ticks_ms()

        return f"Tracking: {count} reports every {interval} min"

    def _handle_map_track(self, params):
        """Map Track X,Y - Start SMS tracking with map links.

        Same as track but includes Google Maps links.
        """
        if len(params) < 2:
            return "Usage: map track COUNT,INTERVAL_MINUTES"

        try:
            count = int(params[0])
            interval = int(params[1])
        except ValueError:
            return "Invalid parameters"

        if count < 1 or count > 100:
            return "Count must be 1-100"
        if interval < 1 or interval > 60:
            return "Interval must be 1-60 minutes"

        self._tracking_active = True
        self._tracking_count = count
        self._tracking_interval = interval * 60
        self._tracking_with_map = True
        self._last_track_time = time.ticks_ms()

        return f"Map tracking: {count} reports every {interval} min"

    def update(self):
        """Check if a tracking update is due.

        Call this periodically from the main loop.

        Returns:
            str: Position message to send, or None
        """
        if not self._tracking_active or self._tracking_count <= 0:
            return None

        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._last_track_time)

        if elapsed >= self._tracking_interval * 1000:
            self._last_track_time = now
            self._tracking_count -= 1

            if self._tracking_count <= 0:
                self._tracking_active = False

            # Generate position message
            if self._tracking_with_map:
                return self._handle_map()
            else:
                return self._generate_position_sms()

        return None

    def _generate_position_sms(self):
        """Generate a position SMS message."""
        if not self.gps:
            return "GPS not available"

        pos = self.gps.get_position()
        if not pos or not pos.get('valid'):
            return "No GPS fix"

        lat = pos.get('latitude', 0)
        lon = pos.get('longitude', 0)
        speed = pos.get('speed', 0)
        heading = pos.get('heading', 0)

        # Format: LAT,LON SPD:XX HDG:XXX
        return f"{lat:.6f},{lon:.6f} SPD:{speed:.0f}kph HDG:{heading:.0f}"

    @property
    def is_tracking(self):
        """Check if SMS tracking is active."""
        return self._tracking_active

    @property
    def tracking_remaining(self):
        """Get number of tracking reports remaining."""
        return self._tracking_count if self._tracking_active else 0
