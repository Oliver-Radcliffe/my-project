# LED Status Indicators for Pico Beacon
# Provides visual feedback for device state
#
# RAPID 2 LED Patterns:
#   Power-on: Green 1s -> Red 1s -> Blue constant
#   GPS acquiring: Cyan (Green + Blue)
#   GPS has fix: Purple (Red + Blue)
#   Connected: Blue solid
#   Transmitting: Blue flash
#   Error: Red solid/flash

from machine import Pin, Timer
import time


class StatusLED:
    """Controls status LEDs for visual feedback.

    RAPID 2 LED color combinations:
    - Green (GP15): GPS indicator
    - Blue (GP16): Network indicator
    - Red (GP17): Error indicator
    - Cyan: Green + Blue (GPS acquiring)
    - Purple: Red + Blue (GPS fix)
    """

    def __init__(self, gps_pin=15, network_pin=16, error_pin=17, onboard_pin=25):
        """Initialize status LEDs.

        Args:
            gps_pin: GPIO pin for GPS status LED (green)
            network_pin: GPIO pin for network status LED (blue)
            error_pin: GPIO pin for error LED (red)
            onboard_pin: GPIO pin for onboard LED (Pico = 25, Pico W = "LED")
        """
        self.led_gps = Pin(gps_pin, Pin.OUT) if gps_pin else None      # Green
        self.led_network = Pin(network_pin, Pin.OUT) if network_pin else None  # Blue
        self.led_error = Pin(error_pin, Pin.OUT) if error_pin else None  # Red

        # Handle Pico W's different LED setup
        try:
            if onboard_pin == "LED":
                self.led_onboard = Pin("LED", Pin.OUT)
            else:
                self.led_onboard = Pin(onboard_pin, Pin.OUT)
        except Exception:
            self.led_onboard = None

        # Blink timers
        self._blink_timer = None
        self._blink_led = None
        self._blink_state = False
        self._multi_blink_leds = []

        # Turn all LEDs off initially
        self.all_off()

    def _set_led(self, led, state):
        """Set LED state safely."""
        if led:
            led.value(1 if state else 0)

    def gps_on(self):
        """Turn GPS LED on (indicates fix)."""
        self._set_led(self.led_gps, True)

    def gps_off(self):
        """Turn GPS LED off (no fix)."""
        self._set_led(self.led_gps, False)

    def gps_blink(self):
        """Blink GPS LED (acquiring)."""
        self._start_blink(self.led_gps)

    def network_on(self):
        """Turn network LED on (connected)."""
        self._set_led(self.led_network, True)

    def network_off(self):
        """Turn network LED off (disconnected)."""
        self._set_led(self.led_network, False)

    def network_blink(self):
        """Blink network LED (connecting)."""
        self._start_blink(self.led_network)

    def error_on(self):
        """Turn error LED on."""
        self._set_led(self.led_error, True)

    def error_off(self):
        """Turn error LED off."""
        self._set_led(self.led_error, False)

    def error_blink(self):
        """Blink error LED."""
        self._start_blink(self.led_error)

    def onboard_on(self):
        """Turn onboard LED on."""
        self._set_led(self.led_onboard, True)

    def onboard_off(self):
        """Turn onboard LED off."""
        self._set_led(self.led_onboard, False)

    def onboard_toggle(self):
        """Toggle onboard LED."""
        if self.led_onboard:
            self.led_onboard.toggle()

    def all_off(self):
        """Turn all LEDs off."""
        self._stop_blink()
        self._set_led(self.led_gps, False)
        self._set_led(self.led_network, False)
        self._set_led(self.led_error, False)
        self._set_led(self.led_onboard, False)

    def all_on(self):
        """Turn all LEDs on (for testing)."""
        self._stop_blink()
        self._set_led(self.led_gps, True)
        self._set_led(self.led_network, True)
        self._set_led(self.led_error, True)
        self._set_led(self.led_onboard, True)

    def _blink_callback(self, timer):
        """Timer callback for blinking."""
        if self._blink_led:
            self._blink_state = not self._blink_state
            self._blink_led.value(1 if self._blink_state else 0)

    def _start_blink(self, led, period_ms=500):
        """Start blinking an LED.

        Args:
            led: Pin object to blink
            period_ms: Blink period in milliseconds
        """
        self._stop_blink()

        if led:
            self._blink_led = led
            self._blink_state = False
            self._blink_timer = Timer()
            self._blink_timer.init(period=period_ms // 2,
                                   mode=Timer.PERIODIC,
                                   callback=self._blink_callback)

    def _stop_blink(self):
        """Stop any blinking LED."""
        if self._blink_timer:
            self._blink_timer.deinit()
            self._blink_timer = None
        if self._blink_led:
            self._blink_led.value(0)
            self._blink_led = None
        self._blink_state = False

    def indicate_startup(self):
        """Show startup sequence (all LEDs blink)."""
        for _ in range(3):
            self.all_on()
            time.sleep_ms(200)
            self.all_off()
            time.sleep_ms(200)

    def rapid2_startup_sequence(self):
        """RAPID 2 power-on LED sequence.

        Sequence: Green 1s -> Red 1s -> Blue constant
        This indicates normal power-up and system initialization.
        """
        self.all_off()

        # Green for 1 second
        self._set_led(self.led_gps, True)
        time.sleep(1)
        self._set_led(self.led_gps, False)

        # Red for 1 second
        self._set_led(self.led_error, True)
        time.sleep(1)
        self._set_led(self.led_error, False)

        # Blue constant (indicates system ready)
        self._set_led(self.led_network, True)

    def set_cyan(self):
        """Set LEDs to cyan (green + blue).

        RAPID 2: Indicates GPS acquiring satellites.
        """
        self._stop_blink()
        self._set_led(self.led_gps, True)      # Green
        self._set_led(self.led_network, True)  # Blue
        self._set_led(self.led_error, False)   # Red off

    def set_purple(self):
        """Set LEDs to purple (red + blue).

        RAPID 2: Indicates GPS has fix.
        """
        self._stop_blink()
        self._set_led(self.led_gps, False)     # Green off
        self._set_led(self.led_network, True)  # Blue
        self._set_led(self.led_error, True)    # Red

    def blink_cyan(self, period_ms=500):
        """Blink cyan (green + blue together).

        RAPID 2: Indicates GPS acquiring with periodic flash.
        """
        self._multi_blink_leds = [self.led_gps, self.led_network]
        self._start_multi_blink(period_ms)

    def _start_multi_blink(self, period_ms=500):
        """Start blinking multiple LEDs together."""
        self._stop_blink()
        if self._multi_blink_leds:
            self._blink_state = False
            self._blink_timer = Timer()
            self._blink_timer.init(
                period=period_ms // 2,
                mode=Timer.PERIODIC,
                callback=self._multi_blink_callback
            )

    def _multi_blink_callback(self, timer):
        """Timer callback for blinking multiple LEDs."""
        self._blink_state = not self._blink_state
        for led in self._multi_blink_leds:
            if led:
                led.value(1 if self._blink_state else 0)

    def indicate_transmit(self):
        """Flash to indicate transmission."""
        if self.led_network:
            for _ in range(2):
                self.led_network.value(1)
                time.sleep_ms(50)
                self.led_network.value(0)
                time.sleep_ms(50)

    def indicate_error(self, count=3):
        """Flash error LED.

        Args:
            count: Number of flashes
        """
        if self.led_error:
            for _ in range(count):
                self.led_error.value(1)
                time.sleep_ms(100)
                self.led_error.value(0)
                time.sleep_ms(100)

    def update_gps_status(self, has_fix, acquiring=False):
        """Update GPS LED based on status.

        RAPID 2 patterns:
        - Acquiring: Cyan (green + blue)
        - Has fix: Purple (red + blue)
        - No GPS: All off

        Args:
            has_fix: True if GPS has a fix
            acquiring: True if currently acquiring satellites
        """
        self._stop_blink()
        self._multi_blink_leds = []

        if has_fix:
            # Purple = GPS has fix
            self.set_purple()
        elif acquiring:
            # Cyan = GPS acquiring
            self.set_cyan()
        else:
            # No GPS activity
            self._set_led(self.led_gps, False)
            self._set_led(self.led_error, False)

    def update_network_status(self, connected, connecting=False):
        """Update network LED based on status.

        RAPID 2 patterns:
        - Connected: Blue solid
        - Connecting: Blue blink
        - Disconnected: Blue off

        Args:
            connected: True if connected to network
            connecting: True if currently connecting
        """
        # Don't stop GPS-related LED states
        if self._blink_timer and self._multi_blink_leds:
            return  # GPS is using the LEDs

        if connected:
            self._set_led(self.led_network, True)
        elif connecting:
            self._start_blink(self.led_network)
        else:
            self._set_led(self.led_network, False)

    def indicate_standby(self):
        """Indicate standby mode - all LEDs off except brief flash."""
        self.all_off()

    def indicate_hibernate(self):
        """Indicate hibernate mode - all LEDs off."""
        self.all_off()

    def indicate_deployment(self):
        """Indicate deployment mode - rapid blue flash."""
        self._start_blink(self.led_network, period_ms=200)
