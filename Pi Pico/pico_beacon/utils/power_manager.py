# Power Manager for Pico Beacon
# Handles battery monitoring, sleep modes, and peripheral power control

from machine import Pin, ADC, lightsleep, deepsleep
import time


class PowerManager:
    """Manages power for the beacon device."""

    # ADC reference voltage
    ADC_VREF = 3.3

    # Voltage divider ratio (if using voltage divider for battery monitoring)
    # For 2:1 divider (two equal resistors), ratio = 2.0
    VOLTAGE_DIVIDER_RATIO = 2.0

    # Battery voltage thresholds (for single cell LiPo)
    BATTERY_FULL = 4.2
    BATTERY_EMPTY = 3.0
    BATTERY_LOW_THRESHOLD = 3.4

    def __init__(self, battery_adc_pin=26, gps_enable_pin=None, cell_enable_pin=None):
        """Initialize power manager.

        Args:
            battery_adc_pin: GPIO pin connected to battery voltage divider
            gps_enable_pin: GPIO pin to enable/disable GPS module power
            cell_enable_pin: GPIO pin to enable/disable cellular module power
        """
        # Battery ADC
        self.battery_adc = ADC(Pin(battery_adc_pin))

        # Power control pins
        self.gps_enable = Pin(gps_enable_pin, Pin.OUT) if gps_enable_pin else None
        self.cell_enable = Pin(cell_enable_pin, Pin.OUT) if cell_enable_pin else None

        # State
        self._gps_powered = True
        self._cell_powered = True

        # Enable peripherals by default
        if self.gps_enable:
            self.gps_enable.value(1)
        if self.cell_enable:
            self.cell_enable.value(1)

    def read_battery_voltage(self):
        """Read battery voltage.

        Returns:
            float: Battery voltage in volts
        """
        # Read ADC (16-bit value)
        raw = self.battery_adc.read_u16()

        # Convert to voltage
        adc_voltage = (raw / 65535.0) * self.ADC_VREF

        # Account for voltage divider
        battery_voltage = adc_voltage * self.VOLTAGE_DIVIDER_RATIO

        return battery_voltage

    def get_battery_percentage(self):
        """Get battery charge percentage.

        Returns:
            int: Battery percentage (0-100)
        """
        voltage = self.read_battery_voltage()

        if voltage >= self.BATTERY_FULL:
            return 100
        elif voltage <= self.BATTERY_EMPTY:
            return 0
        else:
            # Linear interpolation
            range_v = self.BATTERY_FULL - self.BATTERY_EMPTY
            percent = ((voltage - self.BATTERY_EMPTY) / range_v) * 100
            return int(percent)

    def is_battery_low(self):
        """Check if battery is below low threshold.

        Returns:
            bool: True if battery is low
        """
        return self.read_battery_voltage() < self.BATTERY_LOW_THRESHOLD

    def is_battery_critical(self):
        """Check if battery is critically low.

        Returns:
            bool: True if battery is at or below empty threshold
        """
        return self.read_battery_voltage() <= self.BATTERY_EMPTY

    def enable_gps(self):
        """Enable GPS module power."""
        if self.gps_enable:
            self.gps_enable.value(1)
            self._gps_powered = True
            time.sleep_ms(100)  # Allow power to stabilize

    def disable_gps(self):
        """Disable GPS module power."""
        if self.gps_enable:
            self.gps_enable.value(0)
            self._gps_powered = False

    def enable_cellular(self):
        """Enable cellular module power."""
        if self.cell_enable:
            self.cell_enable.value(1)
            self._cell_powered = True
            time.sleep_ms(100)

    def disable_cellular(self):
        """Disable cellular module power."""
        if self.cell_enable:
            self.cell_enable.value(0)
            self._cell_powered = False

    def enable_all_peripherals(self):
        """Enable all peripheral modules."""
        self.enable_gps()
        self.enable_cellular()

    def disable_all_peripherals(self):
        """Disable all peripheral modules to save power."""
        self.disable_gps()
        self.disable_cellular()

    def light_sleep(self, duration_ms):
        """Enter light sleep mode for specified duration.

        In light sleep, the CPU is paused but RAM is retained.
        WiFi/BLE connections may be maintained.

        Args:
            duration_ms: Sleep duration in milliseconds
        """
        lightsleep(duration_ms)

    def deep_sleep(self, duration_ms):
        """Enter deep sleep mode for specified duration.

        In deep sleep, everything is powered down except RTC.
        The device will reset when waking up.

        Args:
            duration_ms: Sleep duration in milliseconds
        """
        # Disable peripherals before deep sleep
        self.disable_all_peripherals()

        # Enter deep sleep
        deepsleep(duration_ms)
        # Note: Code after this won't execute - device resets on wake

    def sleep_until_next_report(self, interval_sec, allow_deep_sleep=False):
        """Sleep until next reporting interval.

        Args:
            interval_sec: Reporting interval in seconds
            allow_deep_sleep: If True, use deep sleep for long intervals

        Note:
            For intervals > 30 seconds with deep sleep enabled,
            the device will reset and lose state. Use light sleep
            for maintaining connections.
        """
        duration_ms = interval_sec * 1000

        if allow_deep_sleep and duration_ms > 30000:
            # Use deep sleep for long intervals
            # Disable peripherals first
            self.disable_all_peripherals()
            self.deep_sleep(duration_ms)
        else:
            # Use light sleep to maintain state
            self.light_sleep(duration_ms)

    @property
    def gps_powered(self):
        """Check if GPS is powered."""
        return self._gps_powered

    @property
    def cell_powered(self):
        """Check if cellular is powered."""
        return self._cell_powered

    def get_status(self):
        """Get power status summary.

        Returns:
            dict: Power status information
        """
        return {
            'battery_voltage': self.read_battery_voltage(),
            'battery_percent': self.get_battery_percentage(),
            'battery_low': self.is_battery_low(),
            'gps_powered': self._gps_powered,
            'cell_powered': self._cell_powered
        }
