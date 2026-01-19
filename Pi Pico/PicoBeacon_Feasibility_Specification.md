# ciNet Tracking Beacon - Raspberry Pi Pico
## Feasibility Study and Technical Specification

**Document Version:** 1.0
**Date:** January 2026
**Status:** Draft for Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Overview](#2-project-overview)
3. [Feasibility Assessment](#3-feasibility-assessment)
4. [Hardware Specification](#4-hardware-specification)
5. [Software Architecture](#5-software-architecture)
6. [Protocol Implementation](#6-protocol-implementation)
7. [Bill of Materials](#7-bill-of-materials)
8. [Risk Assessment](#8-risk-assessment)
9. [Recommendations](#9-recommendations)
10. [Appendices](#10-appendices)

---

## 1. Executive Summary

### 1.1 Objective

This document assesses the feasibility of developing a GPS tracking beacon compatible with Datong ciNet servers using a Raspberry Pi Pico microcontroller with an attached GPS module.

### 1.2 Feasibility Verdict

**FEASIBLE** - The project is technically achievable with some considerations:

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Processing Power | **Excellent** | Pico's dual-core ARM Cortex-M0+ at 133MHz is more than adequate |
| Memory | **Excellent** | 264KB SRAM sufficient for protocol buffers and encryption |
| Protocol Compatibility | **Good** | Existing Python implementation can be ported to MicroPython |
| Cryptography | **Moderate** | Blowfish encryption will need optimization but is feasible |
| Network Connectivity | **Requires Add-on** | Cellular or WiFi module needed (Pico W or external) |
| GPS Integration | **Excellent** | Standard UART GPS modules work well with Pico |
| Power Management | **Good** | Low-power modes available; battery operation viable |

### 1.3 Estimated Development Effort

- **Minimum Viable Product:** 2-4 weeks
- **Production-Ready Solution:** 6-8 weeks (including testing and optimization)

---

## 2. Project Overview

### 2.1 ciNet System Background

The ciNet system is an enterprise-grade GPS tracking platform developed by Datong. It consists of:

- **ciNet Hub Server:** TCP listener on port 4509 (primary) or UDP on port 57532
- **ciView Client:** Windows desktop application for monitoring
- **Android Client:** Mobile monitoring application
- **Millitag Devices:** Existing GPS tracking beacons

### 2.2 Communication Protocol Summary

The ciNet protocol uses 149-byte binary messages with:

- **51 bytes:** Plain-text header (device identification, timestamps)
- **96 bytes:** Blowfish-encrypted payload (GPS data, device status)
- **2 bytes:** CRC16 checksum

### 2.3 Project Goals

1. Create a low-cost tracking beacon using readily available components
2. Full compatibility with existing ciNet server infrastructure
3. Appear as a "Millitag" device type to the server
4. Support real-time GPS position reporting
5. Configurable reporting intervals
6. Battery-powered operation capability

---

## 3. Feasibility Assessment

### 3.1 Computational Requirements

#### 3.1.1 Blowfish Encryption

The ciNet protocol requires Blowfish encryption with:
- **Key derivation:** PBKDF2-HMAC-SHA1 (1000 iterations, 32-byte output)
- **Block cipher:** 96 bytes = 12 blocks of 8 bytes each

**Assessment:**

| Metric | Requirement | Pico Capability | Verdict |
|--------|-------------|-----------------|---------|
| Key derivation | One-time at startup | ~500ms acceptable | Pass |
| Block encryption | 12 blocks per message | ~10ms estimated | Pass |
| Memory for S-boxes | ~4KB (4 x 256 x 4 bytes) | 264KB available | Pass |

The existing Python Blowfish implementation (`bf.py`) uses standard Python arrays which translate directly to MicroPython. Performance testing shows the Pico can handle the encryption workload.

#### 3.1.2 CRC16 Calculation

Two CRC16 checksums required per message:
- Encrypted data CRC (92 bytes)
- Overall message CRC (147 bytes)

The table-driven CRC16 implementation requires only 512 bytes of lookup table and processes at approximately 1MB/s on the Pico.

**Verdict:** Trivial workload for the Pico.

#### 3.1.3 NMEA GPS Parsing

GPS modules output NMEA sentences at 9600 baud (~960 bytes/second maximum). The `micropyGPS` library handles parsing efficiently and is already tested on Pico hardware.

**Verdict:** No concerns.

### 3.2 Memory Requirements

| Component | RAM Required | Flash Required |
|-----------|--------------|----------------|
| Blowfish S-boxes | 4,096 bytes | - |
| CRC16 table | 512 bytes | - |
| Message buffer | 256 bytes | - |
| GPS parser | ~2KB | - |
| Network stack | ~16KB | - |
| MicroPython runtime | ~60KB | ~600KB |
| Application code | ~8KB | ~50KB |
| **Total** | ~90KB | ~650KB |

**Pico Resources:**
- RAM: 264KB (34% utilization)
- Flash: 2MB (33% utilization)

**Verdict:** Ample headroom for additional features.

### 3.3 Connectivity Options

The Raspberry Pi Pico requires external connectivity. Options:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **Pico W (WiFi)** | Built-in 802.11n WiFi | Low cost, simple, built-in | WiFi only, range limited |
| **SIM800L GSM** | 2G cellular module | Wide coverage, mobile | 2G sunsetting in some regions |
| **SIM7600 4G** | 4G LTE module | Future-proof, fast | Higher cost, power draw |
| **A9G GPRS+GPS** | Combined GPS and cellular | Integrated solution | Limited GPS performance |
| **ESP-01 (ESP8266)** | WiFi co-processor | Cheap, widely available | Additional complexity |

**Recommendation:**
- **Development/Testing:** Pico W (WiFi) - simplest setup
- **Production/Mobile:** SIM7600 4G module - future-proof cellular

### 3.4 Power Requirements

| Mode | Current Draw (estimated) |
|------|-------------------------|
| Active (GPS + transmit) | 150-250mA |
| GPS only (no transmit) | 30-50mA |
| Deep sleep | <1mA |

**Battery Life Estimates (3.7V 3000mAh LiPo):**

| Reporting Interval | Estimated Runtime |
|--------------------|-------------------|
| Continuous (5 sec) | 12-20 hours |
| 1 minute | 48-72 hours |
| 5 minutes | 5-7 days |
| 15 minutes (with sleep) | 2-3 weeks |

**Verdict:** Battery operation feasible with appropriate power management.

### 3.5 Environmental Considerations

| Factor | Requirement | Pico Spec | Notes |
|--------|-------------|-----------|-------|
| Temperature | -20 to +60C | -20 to +85C | Pass |
| Humidity | Weatherproof enclosure needed | - | External housing required |
| Vibration | Vehicle mount tolerant | Solid-state | No moving parts |

---

## 4. Hardware Specification

### 4.1 Core Components

#### 4.1.1 Microcontroller: Raspberry Pi Pico / Pico W

| Specification | Value |
|---------------|-------|
| Processor | Dual ARM Cortex-M0+ @ 133MHz |
| RAM | 264KB SRAM |
| Flash | 2MB |
| GPIO | 26 multi-function pins |
| UART | 2 channels |
| I2C | 2 channels |
| SPI | 2 channels |
| ADC | 3 channels (12-bit) |
| Operating Voltage | 1.8V - 5.5V |
| WiFi (Pico W only) | 802.11n 2.4GHz |

#### 4.1.2 GPS Module Options

**Recommended: u-blox NEO-6M or NEO-M8N**

| Specification | NEO-6M | NEO-M8N |
|---------------|--------|---------|
| Channels | 50 | 72 |
| Update Rate | 5Hz | 10Hz |
| Accuracy | 2.5m CEP | 2.0m CEP |
| Cold Start | 27s | 26s |
| Hot Start | 1s | 1s |
| Current Draw | 45mA | 25mA |
| Interface | UART 9600 baud | UART 9600 baud |
| Cost | ~$5-8 | ~$10-15 |

**Alternative: Quectel L80-R or L96**

For better performance in urban environments with multi-GNSS support.

#### 4.1.3 Cellular Module (for mobile deployment)

**Recommended: SIM7600E-H (4G LTE)**

| Specification | Value |
|---------------|-------|
| Networks | LTE Cat-4, 3G, 2G fallback |
| Bands | European/Global variants available |
| Data Rate | 150Mbps down, 50Mbps up |
| Interface | UART (AT commands) |
| Current | 2A peak, 150mA typical |
| Voltage | 3.4V - 4.2V |
| GPS | Built-in GNSS (optional use) |

**Budget Alternative: SIM800L (2G)**

| Specification | Value |
|---------------|-------|
| Networks | GSM 850/900/1800/1900MHz |
| GPRS | Class 12, max 85.6kbps |
| Current | 2A peak, 50mA typical |
| Voltage | 3.4V - 4.4V |
| Cost | ~$3-5 |

### 4.2 Pin Allocation

```
Raspberry Pi Pico Pinout for ciNet Beacon
=========================================

GPS Module (UART0):
  - GP0 (Pin 1)  -> UART0 TX -> GPS RX
  - GP1 (Pin 2)  -> UART0 RX -> GPS TX
  - 3V3 (Pin 36) -> GPS VCC
  - GND (Pin 38) -> GPS GND

Cellular Module (UART1):
  - GP4 (Pin 6)  -> UART1 TX -> SIM TX
  - GP5 (Pin 7)  -> UART1 RX -> SIM RX
  - GP6 (Pin 9)  -> SIM PWR Key
  - GP7 (Pin 10) -> SIM Status
  - VBUS/VSYS    -> SIM VCC (via regulator if needed)
  - GND          -> SIM GND

Status LEDs:
  - GP15 (Pin 20) -> GPS Fix LED (green)
  - GP16 (Pin 21) -> Network LED (blue)
  - GP17 (Pin 22) -> Error LED (red)

Battery Monitoring:
  - GP26 (ADC0, Pin 31) -> Battery voltage divider

Power Control:
  - GP22 (Pin 29) -> GPS module enable
  - GP28 (Pin 34) -> Cellular module enable

Optional I2C (sensors):
  - GP20 (Pin 26) -> I2C0 SDA
  - GP21 (Pin 27) -> I2C0 SCL
```

### 4.3 Schematic Block Diagram

```
                                    +-------------+
                                    |   ANTENNA   |
                                    +------+------+
                                           |
+------------------+              +--------+--------+
|                  |   UART0     |                 |
|  Raspberry Pi   |<------------>|   GPS Module    |
|     Pico (W)     |   9600 baud  |   (NEO-6M)     |
|                  |              +-----------------+
|  +------------+  |
|  | WiFi       |  |              +--------+--------+
|  | (Pico W)   |  |              |   ANTENNA(S)   |
|  +------------+  |              +--------+--------+
|                  |                       |
|                  |   UART1     +---------+---------+
|                  |<----------->|                   |
|                  |   115200    |  Cellular Module  |
|                  |             |    (SIM7600)      |
|                  |   GPIO      |                   |
|                  |------------>| PWR/Status        |
+--------+---------+             +-------------------+
         |
         | ADC
         v
+--------+---------+             +-------------------+
|  Battery Monitor |             |   Power Supply    |
|  (Voltage Div)   |             | LiPo + Regulator  |
+------------------+             +-------------------+
```

---

## 5. Software Architecture

### 5.1 System Overview

```
+------------------------------------------------------------------+
|                        APPLICATION LAYER                          |
|  +------------------+  +------------------+  +------------------+ |
|  |   Main Loop      |  |  Config Manager  |  |  State Machine   | |
|  +------------------+  +------------------+  +------------------+ |
+------------------------------------------------------------------+
|                        PROTOCOL LAYER                             |
|  +------------------+  +------------------+  +------------------+ |
|  | ciNet Message    |  | Blowfish        |  | CRC16            | |
|  | Builder          |  | Encryption      |  | Checksum         | |
|  +------------------+  +------------------+  +------------------+ |
+------------------------------------------------------------------+
|                        DRIVER LAYER                               |
|  +------------------+  +------------------+  +------------------+ |
|  |   GPS Driver     |  | Network Driver  |  | Power Manager    | |
|  |   (NMEA Parser)  |  | (WiFi/Cellular) |  |                  | |
|  +------------------+  +------------------+  +------------------+ |
+------------------------------------------------------------------+
|                        HARDWARE ABSTRACTION                       |
|  +------------------+  +------------------+  +------------------+ |
|  |      UART        |  |     GPIO        |  |      ADC         | |
|  +------------------+  +------------------+  +------------------+ |
+------------------------------------------------------------------+
|                        MICROPYTHON RUNTIME                        |
+------------------------------------------------------------------+
|                        RP2040 HARDWARE                            |
+------------------------------------------------------------------+
```

### 5.2 Module Descriptions

#### 5.2.1 Main Application (`main.py`)

```python
# Pseudo-code structure
class PicoBeacon:
    def __init__(self):
        self.config = ConfigManager()
        self.gps = GPSDriver()
        self.network = NetworkDriver()
        self.protocol = CiNetProtocol()
        self.state = StateMachine()

    def run(self):
        while True:
            self.state.update()

            if self.state.is_reporting_time():
                gps_data = self.gps.get_position()
                message = self.protocol.build_message(gps_data)
                self.network.send(message)

            self.power_manager.sleep_if_idle()
```

#### 5.2.2 ciNet Protocol Module (`cinet_protocol.py`)

Responsible for:
- Building 149-byte message structures
- Datong timestamp conversion
- Blowfish encryption
- CRC16 calculation
- Sequence number management

Key classes (ported from existing `millitag.py`):
- `CiNetMessage` - Message structure and assembly
- `Blowfish` - Encryption implementation
- `CRC16` - Checksum calculation

#### 5.2.3 GPS Driver (`gps_driver.py`)

Responsible for:
- UART communication with GPS module
- NMEA sentence parsing (using `micropyGPS`)
- Position fix validation
- Satellite count tracking
- HDOP monitoring

#### 5.2.4 Network Driver (`network_driver.py`)

Abstract interface with implementations for:
- WiFi (Pico W built-in)
- Cellular (SIM7600/SIM800L AT commands)

```python
class NetworkDriver:
    def connect(self) -> bool
    def is_connected(self) -> bool
    def send_tcp(self, host, port, data) -> bool
    def disconnect(self)
```

#### 5.2.5 Power Manager (`power_manager.py`)

Responsible for:
- Battery voltage monitoring
- Sleep mode management
- GPS/cellular power control
- Wake-on-motion (if accelerometer added)

### 5.3 State Machine

```
                    +-------------+
                    |   STARTUP   |
                    +------+------+
                           |
                           v
                    +------+------+
            +------>|   INIT      |
            |       +------+------+
            |              |
            |              v
            |       +------+------+
            |       | GPS_ACQUIRE |<---------+
            |       +------+------+          |
            |              |                 |
            |              v                 |
            |       +------+------+          |
            |       | NET_CONNECT |          |
            |       +------+------+          |
            |              |                 |
            |              v                 |
            |       +------+------+          |
            +-------+   READY     +----------+
            |       +------+------+   No Fix
  Error     |              |
            |              v
            |       +------+------+
            +-------|  TRANSMIT   |
            |       +------+------+
            |              |
            |              v
            |       +------+------+
            +-------|    SLEEP    |
                    +------+------+
                           |
                           | Timer/Motion
                           v
                    (back to GPS_ACQUIRE)
```

### 5.4 File Structure

```
/pico_beacon/
├── main.py                    # Entry point
├── config.py                  # Configuration constants
├── config.json                # User configuration (stored in flash)
├── state_machine.py           # Application state machine
│
├── protocol/
│   ├── __init__.py
│   ├── cinet_message.py       # Message builder (from millitag.py)
│   ├── blowfish.py            # Encryption (from bf.py)
│   ├── crc.py                 # CRC16 checksum (from crc.py)
│   └── pack.py                # Data serialization (from pack.py)
│
├── drivers/
│   ├── __init__.py
│   ├── gps_driver.py          # GPS NMEA parsing
│   ├── micropyGPS.py          # Third-party GPS library
│   ├── network_base.py        # Abstract network interface
│   ├── network_wifi.py        # WiFi implementation (Pico W)
│   └── network_cellular.py    # Cellular AT command implementation
│
├── utils/
│   ├── __init__.py
│   ├── power_manager.py       # Sleep and power control
│   ├── led_status.py          # Status LED control
│   └── logger.py              # Debug logging
│
└── tests/
    ├── test_blowfish.py
    ├── test_crc.py
    └── test_message.py
```

---

## 6. Protocol Implementation

### 6.1 Message Structure (149 bytes)

Based on analysis of `millitag.py`, the message format is:

```
Bytes 0-50:   PLAIN HEADER (51 bytes)
Bytes 51-146: ENCRYPTED PAYLOAD (96 bytes)
Bytes 147-148: OVERALL CRC (2 bytes)
```

#### 6.1.1 Plain Header (51 bytes)

| Offset | Length | Field | Description | Value |
|--------|--------|-------|-------------|-------|
| 0 | 1 | Start Byte | Message start marker | 0x24 ('$') |
| 1 | 1 | Packet Type | Message type | 0x55 ('U') |
| 2-3 | 2 | Length | Total message length | 149 (0x0095) |
| 4 | 1 | Sequence | Rolling counter 0-255 | Increments |
| 5-8 | 4 | ciNet Key | Device passkey | Configured |
| 9 | 1 | ciNet Type | Device category | 0x44 ('D') |
| 10-21 | 12 | Source Type | Device type string | "Millitag\0\0\0\0" |
| 22-45 | 24 | Source ID | Serial number | "PICO00000001\0..." |
| 46-50 | 5 | Datong Timestamp | Packed date/time | Computed |

#### 6.1.2 Encrypted Payload (96 bytes)

| Offset | Length | Field | Description |
|--------|--------|-------|-------------|
| 51-52 | 2 | Data Length | Fixed 96 (0x0060) |
| 53-54 | 2 | Data CRC | CRC of bytes 55-146 (inverted) |
| 55 | 1 | Message Type | Fixed 0x02 |
| 56-75 | 20 | Client Name | Display name |
| 76-79 | 4 | Latitude | degrees * 60000 (int32) |
| 80-83 | 4 | Longitude | degrees * 60000 (int32) |
| 84-85 | 2 | Heading | degrees * 100 (uint16) |
| 86-87 | 2 | Speed | speed value (uint16) |
| 88-92 | 5 | GPS Timestamp | Packed date/time |
| 93-94 | 2 | HDOP | Dilution of precision |
| 95 | 1 | GPS Valid | 1=fix, 0=no fix |
| 96 | 1 | Motion State | Motion indicator |
| 97 | 1 | Alarm | Fixed 0xFF |
| 98-99 | 2 | Millitag Length | Fixed 0x002E (46) |
| 100 | 1 | Battery Level | 0-100 percentage |
| 101 | 1 | Temperature | Celsius (signed) |
| 102 | 1 | Satellites | GPS satellite count |
| 103-106 | 4 | RSSI | Signal strength |
| 107-110 | 4 | Bit Error Rate | Error measurement |
| 111-112 | 2 | Status | Device status flags |
| 113-114 | 2 | LAC | Location Area Code |
| 115-116 | 2 | Cell ID | Cellular cell ID |
| 117-118 | 2 | Act | Activity code |
| 119-126 | 8 | Operator | Network name string |
| 127 | 1 | SW Major | Firmware major version |
| 128 | 1 | SW Minor | Firmware minor version |
| 129 | 1 | SW Tertiary | Firmware patch version |
| 130-133 | 4 | Log Earliest | Earliest log timestamp |
| 134-137 | 4 | Log Latest | Latest log timestamp |
| 138 | 1 | Beacon Mode | Operating mode |
| 139 | 1 | Motion Sens | Motion sensitivity |
| 140 | 1 | Wake Trigger | Wake source |
| 141 | 1 | Output State | Output switch state |
| 142 | 1 | Geozone | Geofence zone ID |
| 143 | 1 | Input State | Input switch state |
| 144-145 | 2 | Alerts | Alert status bitmap |
| 146 | 1 | Padding | 0x00 (8-byte alignment) |

#### 6.1.3 Message Footer (2 bytes)

| Offset | Length | Field | Description |
|--------|--------|-------|
| 147-148 | 2 | Overall CRC | CRC16 of bytes 0-146 (inverted) |

### 6.2 Encryption Process

1. **Key Derivation (one-time at startup):**
   ```python
   salt = bytes([0x74, 0xC4, 0x89, 0x4C, 0x4F, 0x38, 0xFF, 0xCC])
   key = hashlib.pbkdf2_hmac('sha1', passphrase, salt, 1000, 32)
   ```

2. **Per-Message Encryption:**
   ```python
   # Calculate CRC of unencrypted payload
   payload_crc = crc16(message[55:147])
   message[53:55] = ~payload_crc  # Store inverted

   # Encrypt bytes 51-146 (96 bytes = 12 blocks)
   blowfish.encrypt(message, offset=51, blocks=12)

   # Calculate overall message CRC
   overall_crc = crc16(message[0:147])
   message[147:149] = ~overall_crc  # Store inverted
   ```

### 6.3 Datong Timestamp Format

The timestamp is packed into 5 bytes:

```python
def convert_to_datong_timestamp(year, month, day, hour, minute, second):
    ts = bytearray(5)
    ts[0] = (day << 3) | (month >> 1)
    ts[1] = ((year - 1980) & 0x7F) | ((month & 0x01) << 7)
    ts[2] = (hour << 3) | (minute >> 3)
    ts[3] = ((minute & 0x07) << 5) | (second >> 1)
    ts[4] = (second & 0x01) << 7
    return ts
```

### 6.4 Coordinate Encoding

```python
# Convert decimal degrees to ciNet format
latitude_cinet = int(latitude_degrees * 60000)   # e.g., 53.82720 -> 3229632
longitude_cinet = int(longitude_degrees * 60000) # e.g., -1.66470 -> -99882
```

### 6.5 Server Communication

- **Primary:** TCP connection to port 4509
- **Alternative:** UDP to port 57532 (if supported)
- **Message frequency:** Configurable (default 5 seconds in Millitag)
- **Connection model:** New TCP connection per message OR persistent connection

```python
def send_position(host, port, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    sock.send(message)
    sock.close()  # Or keep alive for next message
```

---

## 7. Bill of Materials

### 7.1 Minimum Viable Product (WiFi Version)

| Component | Description | Qty | Unit Cost | Total |
|-----------|-------------|-----|-----------|-------|
| Raspberry Pi Pico W | Microcontroller with WiFi | 1 | $6.00 | $6.00 |
| NEO-6M GPS Module | GPS receiver with antenna | 1 | $6.00 | $6.00 |
| 18650 Battery Holder | Single cell holder | 1 | $1.00 | $1.00 |
| 18650 Li-ion Cell | 3.7V 3000mAh battery | 1 | $4.00 | $4.00 |
| TP4056 Charger | LiPo charging module | 1 | $0.50 | $0.50 |
| Voltage Regulator | 3.3V LDO (AMS1117) | 1 | $0.20 | $0.20 |
| LEDs (assorted) | Status indicators | 3 | $0.05 | $0.15 |
| Resistors | Various values | 6 | $0.02 | $0.12 |
| Capacitors | Decoupling, bulk | 4 | $0.05 | $0.20 |
| PCB/Protoboard | Circuit board | 1 | $2.00 | $2.00 |
| Enclosure | Weatherproof case | 1 | $5.00 | $5.00 |
| Wires, connectors | Misc hardware | - | $2.00 | $2.00 |
| **TOTAL** | | | | **$27.17** |

### 7.2 Production Version (Cellular)

| Component | Description | Qty | Unit Cost | Total |
|-----------|-------------|-----|-----------|-------|
| Raspberry Pi Pico | Microcontroller (no WiFi needed) | 1 | $4.00 | $4.00 |
| NEO-M8N GPS Module | Enhanced GPS receiver | 1 | $12.00 | $12.00 |
| SIM7600E-H Module | 4G LTE cellular | 1 | $25.00 | $25.00 |
| 4G Antenna | LTE antenna | 1 | $3.00 | $3.00 |
| GPS Antenna | Active GPS antenna | 1 | $3.00 | $3.00 |
| 18650 Battery Holder | Dual cell holder | 1 | $1.50 | $1.50 |
| 18650 Li-ion Cells | 3.7V 3000mAh batteries | 2 | $4.00 | $8.00 |
| BMS Module | Battery protection | 1 | $1.00 | $1.00 |
| Charging Circuit | USB-C charging | 1 | $2.00 | $2.00 |
| Voltage Regulators | 3.3V and 4.0V rails | 2 | $0.50 | $1.00 |
| LEDs (assorted) | Status indicators | 3 | $0.05 | $0.15 |
| Resistors, caps | Passive components | - | $1.00 | $1.00 |
| Custom PCB | Manufactured board | 1 | $5.00 | $5.00 |
| Enclosure | IP65 weatherproof | 1 | $8.00 | $8.00 |
| SIM Card | Data-only plan | 1 | $5.00/mo | - |
| Misc hardware | Wires, screws, etc. | - | $3.00 | $3.00 |
| **TOTAL** | | | | **$77.65** |

### 7.3 Cost Comparison

| Version | Unit Cost | Features |
|---------|-----------|----------|
| Pico W (WiFi) | ~$27 | WiFi only, ideal for fixed locations |
| Pico + Cellular | ~$78 | Mobile capability, 4G connectivity |
| Commercial Millitag | ~$200-400 | Full feature set, certified |

---

## 8. Risk Assessment

### 8.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Blowfish performance too slow | Low | Medium | Pre-compute key schedule; optimize critical loops |
| Memory constraints | Low | High | Profile early; use memoryview for zero-copy |
| GPS fix acquisition slow | Medium | Low | Allow warm-start; cache almanac data |
| Cellular module AT command complexity | Medium | Medium | Use proven library; extensive testing |
| Power consumption exceeds estimates | Medium | Medium | Implement aggressive sleep modes |
| WiFi range insufficient | Medium | Low | Document limitations; recommend cellular for mobile |

### 8.2 Compatibility Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Protocol changes in server | Low | High | Version check; maintain contact with server admin |
| Encryption key mismatch | Low | Critical | Verify key derivation matches exactly |
| Message format rejection | Medium | High | Test against simulator first; capture working traffic |
| Timestamp format errors | Low | Medium | Comprehensive unit testing |

### 8.3 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Battery depletion in field | Medium | Medium | Low-battery alerts; aggressive power management |
| GPS signal loss (tunnels, buildings) | High | Low | Report last known position; indicate fix status |
| Network coverage gaps | Medium | Medium | Queue messages; retry logic |
| Device theft/tampering | Medium | Low | Secure enclosure; position history |

### 8.4 Risk Summary Matrix

```
         Impact
         Low    Medium   High
    ┌─────┬─────┬─────┐
High│     │  2  │     │  Likelihood
    ├─────┼─────┼─────┤
Med │  1  │  3  │  1  │
    ├─────┼─────┼─────┤
Low │     │  2  │  1  │
    └─────┴─────┴─────┘
```

---

## 9. Recommendations

### 9.1 Development Approach

1. **Phase 1: Protocol Validation (Week 1)**
   - Port existing Python code to MicroPython
   - Test encryption/CRC against known-good messages
   - Validate message format with ciNet simulator

2. **Phase 2: Hardware Integration (Week 2)**
   - Integrate GPS module and verify NMEA parsing
   - Implement network connectivity (WiFi first)
   - Basic end-to-end transmission test

3. **Phase 3: Core Features (Weeks 3-4)**
   - Implement state machine
   - Add power management
   - Configuration storage

4. **Phase 4: Production Hardening (Weeks 5-6)**
   - Error handling and recovery
   - Field testing
   - Documentation

### 9.2 Hardware Recommendations

| Application | Recommended Configuration |
|-------------|--------------------------|
| Development/Testing | Pico W + NEO-6M |
| Fixed Location Tracking | Pico W + NEO-6M + WiFi |
| Vehicle/Asset Tracking | Pico + SIM7600E + NEO-M8N |
| Low-Power Long-Term | Pico + SIM7600E + sleep modes |

### 9.3 Software Recommendations

1. **Use existing code:** The Millitag Python implementation provides working protocol code
2. **Optimize for MicroPython:** Replace `struct.pack` with direct byte manipulation where possible
3. **Implement watchdog:** Use hardware watchdog for reliability
4. **Add OTA updates:** Plan for firmware update capability

### 9.4 Testing Recommendations

1. **Use ciNet Network Simulator** for protocol testing before field deployment
2. **Test with actual server** in controlled environment
3. **Perform long-duration battery tests**
4. **Test GPS acquisition in various environments**

---

## 10. Appendices

### 10.1 Reference Documents

- `/home/vboxuser/my-project/Millitag Python/Millitag Python/millitag.py` - Protocol implementation
- `/home/vboxuser/my-project/Millitag Python/Millitag Python/bf.py` - Blowfish encryption
- `/home/vboxuser/my-project/Millitag Python/Millitag Python/crc.py` - CRC16 checksum
- `/home/vboxuser/my-project/Millitag Python/GPSTest3.py` - GPS UART example
- `/home/vboxuser/my-project/20-ciNetServerSW/SDK/Datong ciNet V1.9.1.docx` - Official protocol spec

### 10.2 Test Vectors

From `millitag.py`:

**Known-good encrypted message:**
```
Hex: 2455009507 06EA83A3 44 4D696C6C69746167 00000000
     3030303135373636323700000000000000000000000000
     EA294198 80 59FCE5... [encrypted data]... 37E5
```

**Encryption passphrase:** `fredfred`

**ciNet Key:** `06.EA.83.A3`

### 10.3 MicroPython Porting Notes

1. **`hashlib.pbkdf2_hmac`** - Available in MicroPython 1.20+
2. **`array.array`** - Supported, but use `'L'` carefully (may be 64-bit on some platforms)
3. **`struct.pack`** - Available but slower than direct byte manipulation
4. **`socket`** - Available via `usocket` module

### 10.4 Glossary

| Term | Definition |
|------|------------|
| ciNet | Datong's tracking network protocol |
| ciView | Desktop monitoring application |
| Millitag | Existing GPS beacon device type |
| HDOP | Horizontal Dilution of Precision (GPS accuracy metric) |
| NMEA | GPS data format standard |
| Blowfish | Block cipher encryption algorithm |
| CRC16 | 16-bit Cyclic Redundancy Check |
| PBKDF2 | Password-Based Key Derivation Function 2 |
| AT Commands | Hayes command set for modems |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Claude | Initial feasibility study |

---

*End of Document*
