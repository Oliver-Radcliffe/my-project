# Motion Sensor Driver for Pico Beacon
# Supports accelerometers (MPU6050, ADXL345, LIS3DH) and simple interrupt-based sensors

from machine import Pin, I2C
import time
import math


class MotionSensorBase:
    """Base class for motion sensors."""

    def __init__(self):
        self._motion_detected = False
        self._callback = None

    def is_motion_detected(self):
        """Check if motion was detected since last check.

        Returns:
            bool: True if motion detected
        """
        result = self._motion_detected
        self._motion_detected = False  # Clear flag
        return result

    def set_callback(self, callback):
        """Set callback function for motion interrupt.

        Args:
            callback: Function to call on motion (no arguments)
        """
        self._callback = callback

    def get_acceleration(self):
        """Get current acceleration values.

        Returns:
            tuple: (x, y, z) acceleration in g, or None if not supported
        """
        return None

    def configure_threshold(self, threshold_g):
        """Configure motion detection threshold.

        Args:
            threshold_g: Threshold in g (gravitational units)
        """
        pass


class InterruptMotionSensor(MotionSensorBase):
    """Simple interrupt-based motion sensor (PIR, vibration switch, tilt switch)."""

    def __init__(self, pin, trigger=Pin.IRQ_RISING, pull=Pin.PULL_DOWN):
        """Initialize interrupt-based motion sensor.

        Args:
            pin: GPIO pin number
            trigger: IRQ trigger (IRQ_RISING, IRQ_FALLING, or IRQ_RISING | IRQ_FALLING)
            pull: Pin pull mode (PULL_UP, PULL_DOWN, or None)
        """
        super().__init__()

        self.pin = Pin(pin, Pin.IN, pull)
        self.pin.irq(trigger=trigger, handler=self._irq_handler)

    def _irq_handler(self, pin):
        """Interrupt handler."""
        self._motion_detected = True
        if self._callback:
            self._callback()

    def read_state(self):
        """Read current sensor state.

        Returns:
            int: 0 or 1
        """
        return self.pin.value()


class MPU6050(MotionSensorBase):
    """Driver for MPU6050 accelerometer/gyroscope."""

    # Register addresses
    PWR_MGMT_1 = 0x6B
    ACCEL_CONFIG = 0x1C
    ACCEL_XOUT_H = 0x3B
    INT_ENABLE = 0x38
    INT_STATUS = 0x3A
    MOT_THR = 0x1F
    MOT_DUR = 0x20
    WHO_AM_I = 0x75

    # Default I2C address
    DEFAULT_ADDR = 0x68

    def __init__(self, i2c=None, addr=None, int_pin=None,
                 sda_pin=20, scl_pin=21, i2c_id=0):
        """Initialize MPU6050.

        Args:
            i2c: Existing I2C instance (or None to create new)
            addr: I2C address (default 0x68)
            int_pin: GPIO pin for interrupt (optional)
            sda_pin: SDA GPIO pin (if creating I2C)
            scl_pin: SCL GPIO pin (if creating I2C)
            i2c_id: I2C peripheral ID (if creating I2C)
        """
        super().__init__()

        self.addr = addr or self.DEFAULT_ADDR

        if i2c:
            self.i2c = i2c
        else:
            self.i2c = I2C(i2c_id, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=400000)

        # Interrupt pin (optional)
        if int_pin is not None:
            self.int_pin = Pin(int_pin, Pin.IN, Pin.PULL_UP)
            self.int_pin.irq(trigger=Pin.IRQ_FALLING, handler=self._irq_handler)
        else:
            self.int_pin = None

        # Sensitivity (default +/- 2g)
        self._accel_scale = 16384.0  # LSB/g for +/- 2g range

        # Initialize sensor
        self._init_sensor()

    def _init_sensor(self):
        """Initialize the MPU6050."""
        # Check WHO_AM_I
        who = self._read_byte(self.WHO_AM_I)
        if who != 0x68:
            raise RuntimeError(f"MPU6050 not found (WHO_AM_I={who:#x})")

        # Wake up (clear sleep bit)
        self._write_byte(self.PWR_MGMT_1, 0x00)
        time.sleep_ms(100)

        # Set accelerometer range (+/- 2g)
        self._write_byte(self.ACCEL_CONFIG, 0x00)

    def _write_byte(self, reg, value):
        """Write a byte to a register."""
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def _read_byte(self, reg):
        """Read a byte from a register."""
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _read_bytes(self, reg, length):
        """Read multiple bytes from a register."""
        return self.i2c.readfrom_mem(self.addr, reg, length)

    def _irq_handler(self, pin):
        """Interrupt handler."""
        self._motion_detected = True
        if self._callback:
            self._callback()

    def get_acceleration(self):
        """Get acceleration in g.

        Returns:
            tuple: (x, y, z) in g
        """
        data = self._read_bytes(self.ACCEL_XOUT_H, 6)

        # Convert to signed 16-bit values
        ax = self._to_signed((data[0] << 8) | data[1])
        ay = self._to_signed((data[2] << 8) | data[3])
        az = self._to_signed((data[4] << 8) | data[5])

        # Convert to g
        return (ax / self._accel_scale,
                ay / self._accel_scale,
                az / self._accel_scale)

    @staticmethod
    def _to_signed(val):
        """Convert unsigned 16-bit to signed."""
        if val > 32767:
            val -= 65536
        return val

    def configure_threshold(self, threshold_g):
        """Configure motion detection threshold.

        Args:
            threshold_g: Threshold in g (0.004 to 1.020)
        """
        # Motion threshold register: 1 LSB = 4mg
        threshold_raw = min(255, max(1, int(threshold_g / 0.004)))
        self._write_byte(self.MOT_THR, threshold_raw)

        # Motion duration: 1 LSB = 1ms
        self._write_byte(self.MOT_DUR, 1)

        # Enable motion interrupt
        self._write_byte(self.INT_ENABLE, 0x40)

    def get_motion_magnitude(self):
        """Get total motion magnitude.

        Returns:
            float: Magnitude in g
        """
        ax, ay, az = self.get_acceleration()
        return math.sqrt(ax * ax + ay * ay + az * az)

    def is_moving(self, threshold_g=0.1):
        """Check if device is moving based on acceleration deviation from 1g.

        Args:
            threshold_g: Movement threshold in g

        Returns:
            bool: True if moving
        """
        magnitude = self.get_motion_magnitude()
        # At rest, magnitude should be ~1g (gravity)
        # Movement causes deviation from 1g
        return abs(magnitude - 1.0) > threshold_g


class ADXL345(MotionSensorBase):
    """Driver for ADXL345 accelerometer."""

    # Register addresses
    DEVID = 0x00
    POWER_CTL = 0x2D
    DATA_FORMAT = 0x31
    DATAX0 = 0x32
    INT_ENABLE = 0x2E
    INT_MAP = 0x2F
    INT_SOURCE = 0x30
    THRESH_ACT = 0x24
    ACT_INACT_CTL = 0x27

    DEFAULT_ADDR = 0x53

    def __init__(self, i2c=None, addr=None, int_pin=None,
                 sda_pin=20, scl_pin=21, i2c_id=0):
        """Initialize ADXL345."""
        super().__init__()

        self.addr = addr or self.DEFAULT_ADDR

        if i2c:
            self.i2c = i2c
        else:
            self.i2c = I2C(i2c_id, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=400000)

        if int_pin is not None:
            self.int_pin = Pin(int_pin, Pin.IN, Pin.PULL_UP)
            self.int_pin.irq(trigger=Pin.IRQ_FALLING, handler=self._irq_handler)
        else:
            self.int_pin = None

        self._accel_scale = 256.0  # LSB/g for +/- 2g range

        self._init_sensor()

    def _init_sensor(self):
        """Initialize ADXL345."""
        # Check device ID
        devid = self._read_byte(self.DEVID)
        if devid != 0xE5:
            raise RuntimeError(f"ADXL345 not found (DEVID={devid:#x})")

        # Set data format (+/- 2g, full resolution)
        self._write_byte(self.DATA_FORMAT, 0x08)

        # Enable measurement mode
        self._write_byte(self.POWER_CTL, 0x08)

    def _write_byte(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def _read_byte(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _read_bytes(self, reg, length):
        return self.i2c.readfrom_mem(self.addr, reg, length)

    def _irq_handler(self, pin):
        self._motion_detected = True
        if self._callback:
            self._callback()

    def get_acceleration(self):
        """Get acceleration in g."""
        data = self._read_bytes(self.DATAX0, 6)

        # Convert to signed 16-bit (little-endian)
        ax = self._to_signed(data[0] | (data[1] << 8))
        ay = self._to_signed(data[2] | (data[3] << 8))
        az = self._to_signed(data[4] | (data[5] << 8))

        return (ax / self._accel_scale,
                ay / self._accel_scale,
                az / self._accel_scale)

    @staticmethod
    def _to_signed(val):
        if val > 32767:
            val -= 65536
        return val

    def configure_threshold(self, threshold_g):
        """Configure activity detection threshold."""
        # Activity threshold: 62.5mg/LSB
        threshold_raw = min(255, max(1, int(threshold_g / 0.0625)))
        self._write_byte(self.THRESH_ACT, threshold_raw)

        # Enable activity detection on all axes
        self._write_byte(self.ACT_INACT_CTL, 0x70)

        # Enable activity interrupt
        self._write_byte(self.INT_ENABLE, 0x10)


def create_motion_sensor(sensor_type, **kwargs):
    """Factory function to create motion sensor.

    Args:
        sensor_type: "interrupt", "mpu6050", "adxl345", or "none"
        **kwargs: Sensor-specific arguments

    Returns:
        MotionSensorBase instance or None
    """
    sensor_type = sensor_type.lower()

    if sensor_type == "none" or sensor_type == "disabled":
        return None

    elif sensor_type == "interrupt" or sensor_type == "pir":
        pin = kwargs.get('pin', 22)
        return InterruptMotionSensor(pin)

    elif sensor_type == "mpu6050":
        return MPU6050(**kwargs)

    elif sensor_type == "adxl345":
        return ADXL345(**kwargs)

    else:
        raise ValueError(f"Unknown sensor type: {sensor_type}")
