# I/O Controller for Pico Beacon
# Implements RAPID 2 I/O functionality from Section 5.5 of the manual
#
# Input: 2.2V to 30V active, configurable trigger behaviors
# Output: Open drain, 500mA max, configurable behaviors

from machine import Pin
import time


class IOController:
    """Controls input monitoring and output switching.

    RAPID 2 I/O Specifications (Section 5.5):
    - Input: 2.2V to 30V range, active high/low configurable
    - Output: Open drain, 500mA max sink current
    - Trigger behaviors: On input change, on motion, timed, etc.
    """

    # Input trigger modes
    TRIGGER_DISABLED = 0
    TRIGGER_CHANGE = 1      # Trigger on any change
    TRIGGER_ACTIVE = 2      # Trigger when input goes active
    TRIGGER_INACTIVE = 3    # Trigger when input goes inactive

    # Output trigger modes
    OUTPUT_MANUAL = 0       # Manual control only
    OUTPUT_FOLLOW_INPUT = 1  # Follow input state
    OUTPUT_INVERT_INPUT = 2  # Inverted input state
    OUTPUT_ON_MOTION = 3     # Active when moving
    OUTPUT_ON_STOPPED = 4    # Active when stopped
    OUTPUT_TIMED = 5         # Timed output (pulse)

    def __init__(self, config_manager,
                 input_pin=18, output_pin=19,
                 input_active_high=True):
        """Initialize I/O controller.

        Args:
            config_manager: ConfigManager instance
            input_pin: GPIO pin for external input
            output_pin: GPIO pin for external output (open drain)
            input_active_high: True if high voltage = active
        """
        self.config = config_manager
        self._input_active_high = input_active_high

        # Initialize input pin
        self._input_pin = Pin(input_pin, Pin.IN, Pin.PULL_DOWN)
        self._last_input_state = self._input_pin.value()

        # Initialize output pin (open drain = output low when active)
        self._output_pin = Pin(output_pin, Pin.OUT)
        self._output_pin.value(0)  # Default off
        self._output_active = False

        # Callbacks
        self._input_change_callback = None
        self._alert_callback = None

        # Timed output state
        self._timed_output_active = False
        self._timed_output_end = 0

        # Input trigger mode
        self._input_trigger = self.TRIGGER_CHANGE

        # Output behavior mode
        self._output_mode = self.OUTPUT_MANUAL

        # Debounce
        self._last_change_time = 0
        self._debounce_ms = 50

        # Setup interrupt for input changes
        self._setup_input_interrupt()

    def _setup_input_interrupt(self):
        """Setup interrupt for input pin changes."""
        self._input_pin.irq(
            trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
            handler=self._input_irq_handler
        )

    def _input_irq_handler(self, pin):
        """Handle input pin changes."""
        # Debounce
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_change_time) < self._debounce_ms:
            return
        self._last_change_time = now

        new_state = pin.value()
        if new_state != self._last_input_state:
            self._last_input_state = new_state

            # Check trigger conditions
            active = self._is_input_active(new_state)
            should_trigger = False

            if self._input_trigger == self.TRIGGER_CHANGE:
                should_trigger = True
            elif self._input_trigger == self.TRIGGER_ACTIVE and active:
                should_trigger = True
            elif self._input_trigger == self.TRIGGER_INACTIVE and not active:
                should_trigger = True

            if should_trigger:
                # Call callbacks
                if self._input_change_callback:
                    self._input_change_callback(active)
                if self._alert_callback:
                    self._alert_callback("input_change", active)

            # Update output if following input
            self._update_output_on_input(active)

    def _is_input_active(self, pin_value):
        """Determine if input is active based on configuration."""
        if self._input_active_high:
            return pin_value == 1
        else:
            return pin_value == 0

    def _update_output_on_input(self, input_active):
        """Update output based on input state (if configured)."""
        if self._output_mode == self.OUTPUT_FOLLOW_INPUT:
            self.set_output(input_active)
        elif self._output_mode == self.OUTPUT_INVERT_INPUT:
            self.set_output(not input_active)

    # ==========================================================================
    # INPUT METHODS
    # ==========================================================================

    def get_input_state(self):
        """Get current input state.

        Returns:
            bool: True if input is active
        """
        return self._is_input_active(self._input_pin.value())

    def get_input_raw(self):
        """Get raw input pin value.

        Returns:
            int: 0 or 1
        """
        return self._input_pin.value()

    def set_input_callback(self, callback):
        """Set callback for input changes.

        Args:
            callback: Function(active: bool) called on input change
        """
        self._input_change_callback = callback

    def set_alert_callback(self, callback):
        """Set callback for generating alerts.

        Args:
            callback: Function(alert_type: str, value: any)
        """
        self._alert_callback = callback

    def set_input_trigger(self, mode):
        """Set input trigger mode.

        Args:
            mode: TRIGGER_DISABLED, TRIGGER_CHANGE, TRIGGER_ACTIVE, or TRIGGER_INACTIVE
        """
        self._input_trigger = mode

    def set_input_active_high(self, active_high):
        """Configure input polarity.

        Args:
            active_high: True if high voltage = active
        """
        self._input_active_high = active_high

    # ==========================================================================
    # OUTPUT METHODS
    # ==========================================================================

    def set_output(self, active):
        """Set output state.

        Args:
            active: True to activate output (sink current)
        """
        self._output_active = active
        # Open drain: output LOW to sink current (active), HIGH-Z when inactive
        # For Pico, we set pin to 1 when active (sinking), 0 when inactive
        self._output_pin.value(1 if active else 0)

    def get_output_state(self):
        """Get current output state.

        Returns:
            bool: True if output is active
        """
        return self._output_active

    def toggle_output(self):
        """Toggle output state.

        Returns:
            bool: New output state
        """
        self.set_output(not self._output_active)
        return self._output_active

    def pulse_output(self, duration_ms):
        """Activate output for a specified duration.

        Args:
            duration_ms: Duration in milliseconds
        """
        self.set_output(True)
        self._timed_output_active = True
        self._timed_output_end = time.ticks_add(time.ticks_ms(), duration_ms)

    def set_output_mode(self, mode):
        """Set output behavior mode.

        Args:
            mode: OUTPUT_MANUAL, OUTPUT_FOLLOW_INPUT, OUTPUT_INVERT_INPUT,
                  OUTPUT_ON_MOTION, OUTPUT_ON_STOPPED, or OUTPUT_TIMED
        """
        self._output_mode = mode

    # ==========================================================================
    # MOTION-TRIGGERED OUTPUT
    # ==========================================================================

    def update_motion_state(self, is_moving):
        """Update output based on motion state (if configured).

        Args:
            is_moving: True if device is moving
        """
        if self._output_mode == self.OUTPUT_ON_MOTION:
            self.set_output(is_moving)
        elif self._output_mode == self.OUTPUT_ON_STOPPED:
            self.set_output(not is_moving)

    # ==========================================================================
    # UPDATE LOOP
    # ==========================================================================

    def update(self):
        """Call periodically to handle timed operations.

        Should be called from main loop.
        """
        # Handle timed output expiry
        if self._timed_output_active:
            if time.ticks_diff(time.ticks_ms(), self._timed_output_end) >= 0:
                self.set_output(False)
                self._timed_output_active = False

    # ==========================================================================
    # STATUS
    # ==========================================================================

    def get_status(self):
        """Get current I/O status.

        Returns:
            dict: I/O status information
        """
        return {
            'input_active': self.get_input_state(),
            'input_raw': self.get_input_raw(),
            'output_active': self._output_active,
            'output_mode': self._output_mode,
            'input_trigger': self._input_trigger,
            'input_active_high': self._input_active_high
        }


class TamperDetector:
    """Tamper detection using switch or sensor.

    Monitors a tamper switch and generates alerts when triggered.
    """

    def __init__(self, config_manager, tamper_pin=21, active_low=True):
        """Initialize tamper detector.

        Args:
            config_manager: ConfigManager instance
            tamper_pin: GPIO pin for tamper switch
            active_low: True if switch pulls pin low when tampered
        """
        self.config = config_manager
        self._active_low = active_low
        self._tamper_detected = False
        self._alert_callback = None

        # Initialize tamper pin
        pull = Pin.PULL_UP if active_low else Pin.PULL_DOWN
        self._pin = Pin(tamper_pin, Pin.IN, pull)

        # Get initial state
        self._last_state = self._pin.value()

        # Setup interrupt
        self._pin.irq(
            trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
            handler=self._tamper_irq
        )

    def _tamper_irq(self, pin):
        """Handle tamper switch changes."""
        if not self.config.get("tamper_enabled", False):
            return

        new_state = pin.value()
        if new_state != self._last_state:
            self._last_state = new_state

            # Check if tampered
            if self._active_low:
                self._tamper_detected = (new_state == 0)
            else:
                self._tamper_detected = (new_state == 1)

            # Generate alert if enabled
            if self._tamper_detected and self.config.get("tamper_alert_enabled", True):
                if self._alert_callback:
                    self._alert_callback("tamper", True)

    def is_tampered(self):
        """Check if tamper has been detected.

        Returns:
            bool: True if tamper detected
        """
        return self._tamper_detected

    def clear_tamper(self):
        """Clear tamper flag."""
        self._tamper_detected = False

    def get_raw_state(self):
        """Get raw tamper switch state.

        Returns:
            int: 0 or 1
        """
        return self._pin.value()

    def set_alert_callback(self, callback):
        """Set callback for tamper alerts.

        Args:
            callback: Function(alert_type: str, value: any)
        """
        self._alert_callback = callback

    def is_enabled(self):
        """Check if tamper detection is enabled.

        Returns:
            bool: True if enabled
        """
        return self.config.get("tamper_enabled", False)
