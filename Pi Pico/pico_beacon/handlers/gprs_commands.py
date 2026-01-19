# GPRS Command Handler for Pico Beacon
# Implements RAPID 2 GPRS commands from Section 6.3 of the manual

import time


class GPRSCommandHandler:
    """Handles GPRS commands received from ciNet server.

    RAPID 2 GPRS Commands (Section 6.3):
    - Reset to Config: Reset device to stored configuration
    - Hibernate: Enter hibernate mode
    - Standby: Enter standby mode
    - Clear Standby: Exit standby mode
    - Status: Request status report
    - Tamper Alarm: Enable/disable tamper alerts
    - Output: Control output state
    - Forever Standby: Enter indefinite standby
    - Remote Log Erase: Erase stored logs
    - RF Transmission: Enable/disable/auto RF
    - Audio: Control audio alerts (not implemented on Pico)
    - Button Enable/Disable: Control button functionality
    """

    # Command codes (as sent by server)
    CMD_RESET_TO_CONFIG = 0x01
    CMD_HIBERNATE = 0x02
    CMD_STANDBY = 0x03
    CMD_CLEAR_STANDBY = 0x04
    CMD_STATUS = 0x05
    CMD_TAMPER_ON = 0x06
    CMD_TAMPER_OFF = 0x07
    CMD_OUTPUT_ON = 0x08
    CMD_OUTPUT_OFF = 0x09
    CMD_FOREVER_STANDBY = 0x0A
    CMD_LOG_ERASE = 0x0B
    CMD_RF_ON = 0x0C
    CMD_RF_OFF = 0x0D
    CMD_RF_AUTO = 0x0E
    CMD_AUDIO_ON = 0x0F
    CMD_AUDIO_OFF = 0x10
    CMD_BUTTON_ENABLE = 0x11
    CMD_BUTTON_DISABLE = 0x12
    CMD_LOCATE = 0x13
    CMD_SET_RATE = 0x14
    CMD_UPLOAD_LOG = 0x15
    CMD_REBOOT = 0xFF

    def __init__(self, config_manager, state_machine, data_logger=None, io_controller=None):
        """Initialize GPRS command handler.

        Args:
            config_manager: ConfigManager instance
            state_machine: Main state machine reference
            data_logger: DataLogger instance for log operations
            io_controller: I/O controller for output commands
        """
        self.config = config_manager
        self.state_machine = state_machine
        self.logger = data_logger
        self.io = io_controller

        # Command queue for responses
        self._response_queue = []

        # Pending status request
        self._status_requested = False

        # Pending locate request
        self._locate_requested = False

        # Pending log upload
        self._log_upload_requested = False

    def process_command(self, cmd_code, cmd_data=None):
        """Process a GPRS command from the server.

        Args:
            cmd_code: Command code byte
            cmd_data: Optional command data bytes

        Returns:
            bool: True if command was processed successfully
        """
        try:
            if cmd_code == self.CMD_RESET_TO_CONFIG:
                return self._handle_reset_to_config()

            elif cmd_code == self.CMD_HIBERNATE:
                return self._handle_hibernate()

            elif cmd_code == self.CMD_STANDBY:
                return self._handle_standby()

            elif cmd_code == self.CMD_CLEAR_STANDBY:
                return self._handle_clear_standby()

            elif cmd_code == self.CMD_STATUS:
                return self._handle_status()

            elif cmd_code == self.CMD_TAMPER_ON:
                return self._handle_tamper_on()

            elif cmd_code == self.CMD_TAMPER_OFF:
                return self._handle_tamper_off()

            elif cmd_code == self.CMD_OUTPUT_ON:
                return self._handle_output_on()

            elif cmd_code == self.CMD_OUTPUT_OFF:
                return self._handle_output_off()

            elif cmd_code == self.CMD_FOREVER_STANDBY:
                return self._handle_forever_standby()

            elif cmd_code == self.CMD_LOG_ERASE:
                return self._handle_log_erase()

            elif cmd_code == self.CMD_RF_ON:
                return self._handle_rf_on()

            elif cmd_code == self.CMD_RF_OFF:
                return self._handle_rf_off()

            elif cmd_code == self.CMD_RF_AUTO:
                return self._handle_rf_auto()

            elif cmd_code == self.CMD_AUDIO_ON:
                return self._handle_audio_on()

            elif cmd_code == self.CMD_AUDIO_OFF:
                return self._handle_audio_off()

            elif cmd_code == self.CMD_BUTTON_ENABLE:
                return self._handle_button_enable()

            elif cmd_code == self.CMD_BUTTON_DISABLE:
                return self._handle_button_disable()

            elif cmd_code == self.CMD_LOCATE:
                return self._handle_locate()

            elif cmd_code == self.CMD_SET_RATE:
                return self._handle_set_rate(cmd_data)

            elif cmd_code == self.CMD_UPLOAD_LOG:
                return self._handle_upload_log()

            elif cmd_code == self.CMD_REBOOT:
                return self._handle_reboot()

            else:
                print(f"Unknown GPRS command: 0x{cmd_code:02X}")
                return False

        except Exception as e:
            print(f"GPRS command error: {e}")
            return False

    # ==========================================================================
    # MODE COMMANDS
    # ==========================================================================

    def _handle_reset_to_config(self):
        """Reset to Config - Reset device to stored configuration."""
        self.config.set("operating_mode", "active")
        self.config.set("rf_mode", "auto")
        self.config.set("rf_enabled", True)
        self.config.save()

        if self.state_machine:
            self.state_machine.reset_to_config()

        return True

    def _handle_hibernate(self):
        """Hibernate - Enter low power hibernate mode."""
        self.config.set("operating_mode", "hibernate")
        self.config.save()

        if self.state_machine:
            self.state_machine.enter_hibernate()

        return True

    def _handle_standby(self):
        """Standby - Enter standby mode with periodic wake."""
        self.config.set("operating_mode", "standby")
        self.config.save()

        if self.state_machine:
            self.state_machine.enter_standby()

        return True

    def _handle_clear_standby(self):
        """Clear Standby - Exit standby and return to active mode."""
        self.config.set("operating_mode", "active")
        self.config.save()

        if self.state_machine:
            self.state_machine.exit_standby()

        return True

    def _handle_forever_standby(self):
        """Forever Standby - Enter indefinite standby mode."""
        self.config.set("operating_mode", "forever_standby")
        self.config.save()

        if self.state_machine:
            self.state_machine.enter_forever_standby()

        return True

    # ==========================================================================
    # STATUS AND LOCATE COMMANDS
    # ==========================================================================

    def _handle_status(self):
        """Status - Request a status report."""
        self._status_requested = True
        return True

    def _handle_locate(self):
        """Locate - Request immediate position report."""
        self._locate_requested = True
        return True

    # ==========================================================================
    # TAMPER COMMANDS
    # ==========================================================================

    def _handle_tamper_on(self):
        """Tamper On - Enable tamper detection alerts."""
        self.config.set("tamper_enabled", True)
        self.config.set("tamper_alert_enabled", True)
        self.config.save()
        return True

    def _handle_tamper_off(self):
        """Tamper Off - Disable tamper detection alerts."""
        self.config.set("tamper_alert_enabled", False)
        self.config.save()
        return True

    # ==========================================================================
    # OUTPUT COMMANDS
    # ==========================================================================

    def _handle_output_on(self):
        """Output On - Activate the output."""
        if self.io:
            self.io.set_output(True)
        else:
            self.config.set("output_state", True)
        return True

    def _handle_output_off(self):
        """Output Off - Deactivate the output."""
        if self.io:
            self.io.set_output(False)
        else:
            self.config.set("output_state", False)
        return True

    # ==========================================================================
    # LOG COMMANDS
    # ==========================================================================

    def _handle_log_erase(self):
        """Log Erase - Erase stored position logs."""
        if self.logger:
            # Close current logs
            self.logger.close()
            # Delete log files
            for filepath in self.logger.get_log_files():
                try:
                    import os
                    os.remove(filepath)
                except OSError:
                    pass
            # Reopen fresh logs
            self.logger._open_logs()
        return True

    def _handle_upload_log(self):
        """Upload Log - Request log upload to server."""
        self._log_upload_requested = True
        if self.state_machine:
            self.state_machine.request_log_upload()
        return True

    # ==========================================================================
    # RF COMMANDS
    # ==========================================================================

    def _handle_rf_on(self):
        """RF On - Enable RF transmission."""
        self.config.set("rf_enabled", True)
        self.config.set("rf_mode", "on")
        self.config.save()

        if self.state_machine:
            self.state_machine.set_rf_enabled(True)

        return True

    def _handle_rf_off(self):
        """RF Off - Disable RF transmission (logging only)."""
        self.config.set("rf_enabled", False)
        self.config.set("rf_mode", "off")
        self.config.save()

        if self.state_machine:
            self.state_machine.set_rf_enabled(False)

        return True

    def _handle_rf_auto(self):
        """RF Auto - Automatic RF control."""
        self.config.set("rf_mode", "auto")
        self.config.set("rf_enabled", True)
        self.config.save()

        if self.state_machine:
            self.state_machine.set_rf_mode_auto()

        return True

    # ==========================================================================
    # AUDIO COMMANDS (STUB - No audio on Pico)
    # ==========================================================================

    def _handle_audio_on(self):
        """Audio On - Enable audio alerts (not implemented)."""
        self.config.set("audio_enabled", True)
        return True

    def _handle_audio_off(self):
        """Audio Off - Disable audio alerts (not implemented)."""
        self.config.set("audio_enabled", False)
        return True

    # ==========================================================================
    # BUTTON COMMANDS
    # ==========================================================================

    def _handle_button_enable(self):
        """Button Enable - Enable physical button."""
        self.config.set("button_enabled", True)
        self.config.save()
        return True

    def _handle_button_disable(self):
        """Button Disable - Disable physical button."""
        self.config.set("button_enabled", False)
        self.config.save()
        return True

    # ==========================================================================
    # RATE COMMAND
    # ==========================================================================

    def _handle_set_rate(self, cmd_data):
        """Set Rate - Change reporting rate.

        Args:
            cmd_data: bytes containing rate configuration
                      Format: [rate_type, rate_value_hi, rate_value_lo]
        """
        if not cmd_data or len(cmd_data) < 3:
            return False

        rate_type = cmd_data[0]
        rate_value = (cmd_data[1] << 8) | cmd_data[2]

        # Rate types
        RATE_MOVING = 0x01
        RATE_STOPPED = 0x02
        RATE_STANDBY = 0x03

        if rate_type == RATE_MOVING:
            self.config.set("gprs_rate_moving_sec", rate_value)
        elif rate_type == RATE_STOPPED:
            self.config.set("gprs_rate_stopped_sec", rate_value)
        elif rate_type == RATE_STANDBY:
            self.config.set("gprs_rate_standby_sec", rate_value)
        else:
            return False

        self.config.save()
        return True

    # ==========================================================================
    # REBOOT COMMAND
    # ==========================================================================

    def _handle_reboot(self):
        """Reboot - Restart the device."""
        if self.state_machine:
            self.state_machine.request_reboot()
        else:
            # Direct reboot
            import machine
            machine.reset()
        return True

    # ==========================================================================
    # STATUS CHECKING
    # ==========================================================================

    def is_status_requested(self):
        """Check if status report was requested."""
        result = self._status_requested
        self._status_requested = False
        return result

    def is_locate_requested(self):
        """Check if locate (immediate position) was requested."""
        result = self._locate_requested
        self._locate_requested = False
        return result

    def is_log_upload_requested(self):
        """Check if log upload was requested."""
        result = self._log_upload_requested
        self._log_upload_requested = False
        return result
