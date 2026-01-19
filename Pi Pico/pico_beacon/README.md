# Pico Beacon

A ciNet-compatible GPS tracking beacon for Raspberry Pi Pico / Pico W.

## Features

- Full compatibility with Datong ciNet servers
- Appears as a "Millitag" device type
- GPS position tracking with NMEA parsing
- WiFi (Pico W) or Cellular (SIM7600/SIM800L) connectivity
- Blowfish encryption with PBKDF2 key derivation
- Battery monitoring and power management
- Status LED indicators
- Configurable reporting intervals

## Hardware Requirements

### Minimum (WiFi Version)
- Raspberry Pi Pico W
- GPS Module (NEO-6M, NEO-M8N, or similar NMEA)
- Power supply (USB or LiPo battery)

### Mobile Version (Cellular)
- Raspberry Pi Pico (standard)
- GPS Module
- SIM7600 or SIM800L cellular module
- LiPo battery + charging circuit

## Wiring

### GPS Module (UART0)
| Pico Pin | GPS Pin |
|----------|---------|
| GP0 (TX) | RX      |
| GP1 (RX) | TX      |
| 3V3      | VCC     |
| GND      | GND     |

### Cellular Module (UART1) - Optional
| Pico Pin | SIM Pin |
|----------|---------|
| GP4 (TX) | RX      |
| GP5 (RX) | TX      |
| GP6      | PWRKEY  |
| GP7      | STATUS  |

### Status LEDs (Optional)
| Pico Pin | LED Color | Function |
|----------|-----------|----------|
| GP15     | Green     | GPS Fix  |
| GP16     | Blue      | Network  |
| GP17     | Red       | Error    |

## Installation

1. Install MicroPython on your Pico:
   - Download from https://micropython.org/download/rp2-pico-w/
   - Hold BOOTSEL button and connect USB
   - Copy the .uf2 file to the RPI-RP2 drive

2. Copy all files to the Pico:
   ```bash
   # Using mpremote (install with: pip install mpremote)
   mpremote cp -r . :
   ```

   Or use Thonny IDE to copy files manually.

3. Edit configuration:
   - Open `config.py` and modify `DEFAULT_CONFIG`
   - Or create `/config.json` on the Pico with your settings

4. Reset the Pico to start the beacon.

## Configuration

Edit `DEFAULT_CONFIG` in `config.py` or create a `config.json` file:

```json
{
    "server_host": "your.server.ip",
    "server_port": 4509,
    "passphrase": "your_passphrase",
    "cinet_key": "06.EA.83.A3",
    "serial_number": "PICO00000001",
    "client_name": "My Pico Beacon",
    "wifi_ssid": "YourNetwork",
    "wifi_password": "YourPassword",
    "report_interval_sec": 10
}
```

## Testing

Run protocol tests on desktop Python:

```bash
cd pico_beacon
python -m pytest tests/test_protocol.py -v
```

Or on the Pico:

```python
import tests.test_protocol
tests.test_protocol.run_all_tests()
```

## File Structure

```
pico_beacon/
├── main.py                 # Main application entry point
├── boot.py                 # Boot configuration
├── config.py               # Configuration and constants
├── protocol/
│   ├── __init__.py
│   ├── blowfish.py         # Blowfish encryption
│   ├── crc.py              # CRC16 checksum
│   ├── pack.py             # Data packing utilities
│   └── cinet_message.py    # ciNet protocol message builder
├── drivers/
│   ├── __init__.py
│   ├── gps_driver.py       # GPS NMEA parser
│   ├── network_base.py     # Network driver interface
│   ├── network_wifi.py     # WiFi driver (Pico W)
│   └── network_cellular.py # Cellular driver (SIM7600/800)
├── utils/
│   ├── __init__.py
│   ├── power_manager.py    # Battery and sleep management
│   ├── led_status.py       # Status LED control
│   └── logger.py           # Debug logging
└── tests/
    └── test_protocol.py    # Protocol tests
```

## LED Status Indicators

| LED | Solid | Blinking | Off |
|-----|-------|----------|-----|
| Green (GPS) | Has fix | Acquiring | No GPS |
| Blue (Network) | Connected | Connecting | Disconnected |
| Red (Error) | Error state | - | Normal |

## Troubleshooting

### No GPS Fix
- Ensure GPS antenna has clear sky view
- Check wiring (TX/RX crossed correctly)
- Wait up to 60 seconds for cold start

### Network Connection Failed
- Verify WiFi credentials in config
- Check signal strength
- For cellular, verify APN settings and SIM card

### Message Not Received by Server
- Verify server IP and port
- Check passphrase matches server configuration
- Verify ciNet key matches registered device

## Protocol Details

The beacon uses the ciNet/Millitag protocol:
- 149-byte binary messages
- Blowfish encryption (ECB mode)
- PBKDF2-HMAC-SHA1 key derivation
- CRC16 checksums
- TCP port 4509 (primary)

See `PicoBeacon_Feasibility_Specification.md` for full protocol documentation.

## License

This project is provided for educational and development purposes.
The ciNet protocol is proprietary to Datong.
