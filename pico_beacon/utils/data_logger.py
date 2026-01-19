# Data Logger for Pico Beacon
# Logs GPS positions to flash storage or SD card for offline tracking

import os
import time
import json


class DataLogger:
    """Logs GPS data to storage for offline tracking and backup."""

    # Log file settings
    DEFAULT_LOG_DIR = "/logs"
    MAX_LOG_SIZE = 100000  # Max bytes per log file (100KB)
    MAX_LOG_FILES = 10     # Max number of log files to keep

    def __init__(self, log_dir=None, enable_csv=True, enable_json=False):
        """Initialize data logger.

        Args:
            log_dir: Directory for log files (default: /logs)
            enable_csv: Log in CSV format (compact, easy to import)
            enable_json: Log in JSON format (more data, human readable)
        """
        self.log_dir = log_dir or self.DEFAULT_LOG_DIR
        self.enable_csv = enable_csv
        self.enable_json = enable_json

        self._csv_file = None
        self._json_file = None
        self._csv_path = None
        self._json_path = None
        self._record_count = 0

        # Ensure log directory exists
        self._ensure_dir()

        # Open log files
        self._open_logs()

    def _ensure_dir(self):
        """Ensure log directory exists."""
        try:
            os.stat(self.log_dir)
        except OSError:
            try:
                os.mkdir(self.log_dir)
            except OSError:
                # Directory might already exist or can't be created
                pass

    def _open_logs(self):
        """Open new log files."""
        # Generate timestamp for filename
        try:
            t = time.localtime()
            timestamp = f"{t[0]:04d}{t[1]:02d}{t[2]:02d}_{t[3]:02d}{t[4]:02d}{t[5]:02d}"
        except Exception:
            # Fallback if RTC not set
            timestamp = f"{time.ticks_ms()}"

        if self.enable_csv:
            self._csv_path = f"{self.log_dir}/gps_{timestamp}.csv"
            try:
                self._csv_file = open(self._csv_path, 'w')
                # Write CSV header
                self._csv_file.write("timestamp,latitude,longitude,altitude,speed,heading,satellites,hdop,valid,battery\n")
                self._csv_file.flush()
            except OSError as e:
                print(f"Failed to open CSV log: {e}")
                self._csv_file = None

        if self.enable_json:
            self._json_path = f"{self.log_dir}/gps_{timestamp}.jsonl"
            try:
                self._json_file = open(self._json_path, 'w')
            except OSError as e:
                print(f"Failed to open JSON log: {e}")
                self._json_file = None

    def log(self, gps_data, device_status=None):
        """Log a GPS position record.

        Args:
            gps_data: dict with GPS data from GPSDriver.get_position()
            device_status: dict with device status (optional)

        Returns:
            bool: True if logged successfully
        """
        success = True

        # Build timestamp string
        ts = gps_data.get('timestamp')
        if ts:
            ts_str = f"{ts[0]:04d}-{ts[1]:02d}-{ts[2]:02d}T{ts[3]:02d}:{ts[4]:02d}:{ts[5]:02d}"
        else:
            ts_str = str(time.ticks_ms())

        # Get battery level
        battery = device_status.get('battery', -1) if device_status else -1

        # Log to CSV
        if self._csv_file:
            try:
                lat = gps_data.get('latitude', 0.0)
                lon = gps_data.get('longitude', 0.0)
                alt = gps_data.get('altitude', 0.0)
                speed = gps_data.get('speed', 0.0)
                heading = gps_data.get('heading')
                heading_str = f"{heading:.1f}" if heading is not None else ""
                sats = gps_data.get('satellites', 0)
                hdop = gps_data.get('hdop', 99.9)
                valid = 1 if gps_data.get('valid', False) else 0

                line = f"{ts_str},{lat:.6f},{lon:.6f},{alt:.1f},{speed:.1f},{heading_str},{sats},{hdop:.1f},{valid},{battery}\n"
                self._csv_file.write(line)
                self._csv_file.flush()
            except Exception as e:
                print(f"CSV log error: {e}")
                success = False

        # Log to JSON Lines
        if self._json_file:
            try:
                record = {
                    'ts': ts_str,
                    'lat': gps_data.get('latitude', 0.0),
                    'lon': gps_data.get('longitude', 0.0),
                    'alt': gps_data.get('altitude', 0.0),
                    'spd': gps_data.get('speed', 0.0),
                    'hdg': gps_data.get('heading'),
                    'sat': gps_data.get('satellites', 0),
                    'hdop': gps_data.get('hdop', 99.9),
                    'fix': gps_data.get('valid', False),
                    'bat': battery
                }
                self._json_file.write(json.dumps(record) + '\n')
                self._json_file.flush()
            except Exception as e:
                print(f"JSON log error: {e}")
                success = False

        self._record_count += 1

        # Check if rotation needed
        self._check_rotation()

        return success

    def _check_rotation(self):
        """Check if log files need rotation."""
        needs_rotation = False

        if self._csv_file and self._csv_path:
            try:
                size = os.stat(self._csv_path)[6]
                if size > self.MAX_LOG_SIZE:
                    needs_rotation = True
            except OSError:
                pass

        if needs_rotation:
            self.close()
            self._cleanup_old_logs()
            self._open_logs()

    def _cleanup_old_logs(self):
        """Remove old log files if too many exist."""
        try:
            files = os.listdir(self.log_dir)
            csv_files = sorted([f for f in files if f.endswith('.csv')])
            json_files = sorted([f for f in files if f.endswith('.jsonl')])

            # Remove oldest files if over limit
            while len(csv_files) > self.MAX_LOG_FILES:
                oldest = csv_files.pop(0)
                try:
                    os.remove(f"{self.log_dir}/{oldest}")
                except OSError:
                    pass

            while len(json_files) > self.MAX_LOG_FILES:
                oldest = json_files.pop(0)
                try:
                    os.remove(f"{self.log_dir}/{oldest}")
                except OSError:
                    pass

        except OSError:
            pass

    def close(self):
        """Close log files."""
        if self._csv_file:
            try:
                self._csv_file.close()
            except Exception:
                pass
            self._csv_file = None

        if self._json_file:
            try:
                self._json_file.close()
            except Exception:
                pass
            self._json_file = None

    def get_log_files(self):
        """Get list of log files.

        Returns:
            list: Paths to log files
        """
        try:
            files = os.listdir(self.log_dir)
            return [f"{self.log_dir}/{f}" for f in files
                    if f.endswith('.csv') or f.endswith('.jsonl')]
        except OSError:
            return []

    def get_record_count(self):
        """Get number of records logged in current session."""
        return self._record_count

    def read_log(self, filepath, max_records=100):
        """Read records from a log file.

        Args:
            filepath: Path to log file
            max_records: Maximum records to return

        Returns:
            list: List of record dicts (for JSON) or strings (for CSV)
        """
        records = []
        try:
            with open(filepath, 'r') as f:
                for i, line in enumerate(f):
                    if i == 0 and filepath.endswith('.csv'):
                        continue  # Skip CSV header
                    if i >= max_records:
                        break
                    if filepath.endswith('.jsonl'):
                        try:
                            records.append(json.loads(line))
                        except ValueError:
                            pass
                    else:
                        records.append(line.strip())
        except OSError as e:
            print(f"Error reading log: {e}")

        return records

    def get_storage_info(self):
        """Get storage usage information.

        Returns:
            dict: Storage info (total, used, free bytes if available)
        """
        try:
            stat = os.statvfs('/')
            block_size = stat[0]
            total_blocks = stat[2]
            free_blocks = stat[3]

            return {
                'total': total_blocks * block_size,
                'free': free_blocks * block_size,
                'used': (total_blocks - free_blocks) * block_size
            }
        except Exception:
            return {'total': 0, 'free': 0, 'used': 0}

    def __del__(self):
        """Destructor - ensure files are closed."""
        self.close()


class SDCardLogger(DataLogger):
    """Extended logger with SD card support.

    Requires an SD card module connected via SPI.
    """

    def __init__(self, spi_id=0, cs_pin=17, log_dir="/sd/logs", **kwargs):
        """Initialize SD card logger.

        Args:
            spi_id: SPI peripheral ID
            cs_pin: Chip select GPIO pin
            log_dir: Directory on SD card for logs
            **kwargs: Additional args passed to DataLogger
        """
        self._sd = None
        self._mounted = False

        # Try to mount SD card
        self._mount_sd(spi_id, cs_pin)

        if self._mounted:
            super().__init__(log_dir=log_dir, **kwargs)
        else:
            # Fall back to internal flash
            print("SD card not available, using internal flash")
            super().__init__(log_dir="/logs", **kwargs)

    def _mount_sd(self, spi_id, cs_pin):
        """Mount SD card."""
        try:
            from machine import SPI, Pin
            import sdcard

            spi = SPI(spi_id, baudrate=1000000,
                      polarity=0, phase=0,
                      sck=Pin(18), mosi=Pin(19), miso=Pin(16))
            cs = Pin(cs_pin, Pin.OUT)

            self._sd = sdcard.SDCard(spi, cs)

            # Mount filesystem
            os.mount(self._sd, '/sd')
            self._mounted = True
            print("SD card mounted successfully")

        except ImportError:
            print("sdcard module not available")
        except Exception as e:
            print(f"Failed to mount SD card: {e}")

    def unmount(self):
        """Unmount SD card."""
        self.close()
        if self._mounted:
            try:
                os.umount('/sd')
                self._mounted = False
            except Exception:
                pass

    @property
    def is_sd_mounted(self):
        """Check if SD card is mounted."""
        return self._mounted
