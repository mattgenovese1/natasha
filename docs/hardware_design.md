# Natasha Hardware Design and Connections

## Overview
This document outlines the hardware components, connections, and requirements for the Natasha AI penetration testing tool. The system is built around a Raspberry Pi Zero 2 W with a Waveshare 2.13-inch e-paper display, configured to function as both a USB Rubber Ducky and WiFi attack platform.

## Core Hardware Components

### 1. Raspberry Pi Zero 2 W
- **Processor**: Quad-core 64-bit ARM Cortex-A53 @ 1GHz
- **Memory**: 512MB LPDDR2 RAM
- **Storage**: 32GB+ microSD card (Class 10 or better)
- **Connectivity**: 
  - Built-in 2.4GHz 802.11 b/g/n wireless LAN
  - Bluetooth 4.2
  - USB OTG port
- **Power**: 5V via micro USB port
- **GPIO**: 40-pin GPIO header

### 2. Waveshare 2.13-inch E-Paper Display V4
- **Resolution**: 250×122 pixels
- **Colors**: Black and white
- **Interface**: SPI
- **Dimensions**: 65.0mm × 30.2mm (display area: 48.55mm × 23.71mm)
- **Power**: 3.3V (compatible with Raspberry Pi GPIO)

### 3. Additional Hardware Components
- **External WiFi Adapter**: For dedicated wireless attacks (while maintaining connectivity)
  - Recommended: USB WiFi adapter with monitor mode and packet injection support
  - Compatible chipsets: Realtek RTL8812AU, Atheros AR9271, or Ralink RT3070
- **Input Controls**:
  - 4× tactile push buttons for UI navigation
  - 1× emergency stop/power button
- **Status Indicators**:
  - 2× LEDs (red and green) for status indication
- **Power Supply**:
  - 3000mAh+ LiPo battery with protection circuit
  - Power management board with charging capability
  - USB power input for charging/tethered operation
- **Enclosure**:
  - Custom 3D-printed case with access to all ports
  - Dimensions: approximately 80mm × 45mm × 20mm

## Connection Diagram

### Raspberry Pi to E-Paper Display
| E-Paper Pin | Raspberry Pi GPIO Pin | Function |
|-------------|------------------------|----------|
| VCC         | 3.3V (Pin 1)          | Power    |
| GND         | GND (Pin 6)           | Ground   |
| DIN         | MOSI (Pin 19)         | Data In  |
| CLK         | SCLK (Pin 23)         | Clock    |
| CS          | CE0 (Pin 24)          | Chip Select |
| DC          | GPIO 25 (Pin 22)      | Data/Command |
| RST         | GPIO 17 (Pin 11)      | Reset    |
| BUSY        | GPIO 24 (Pin 18)      | Busy Status |

### Navigation Buttons
| Button Function | Raspberry Pi GPIO Pin |
|-----------------|------------------------|
| Up              | GPIO 5 (Pin 29)       |
| Down            | GPIO 6 (Pin 31)       |
| Select          | GPIO 13 (Pin 33)      |
| Back            | GPIO 19 (Pin 35)      |
| Power/Emergency | GPIO 26 (Pin 37)      |

### Status LEDs
| LED Color | Raspberry Pi GPIO Pin | Function |
|-----------|------------------------|----------|
| Red       | GPIO 12 (Pin 32)      | Attack/Warning Status |
| Green     | GPIO 16 (Pin 36)      | Power/Ready Status |

### External WiFi Adapter
- Connected to Raspberry Pi via USB OTG adapter or USB hub
- May require powered USB hub depending on power requirements

### Power Management
- Battery connected to Raspberry Pi via power management board
- Power management board connected to Raspberry Pi GPIO for monitoring:
  - Battery level monitoring: GPIO 4 (Pin 7) - ADC input
  - Charging status: GPIO 27 (Pin 13) - Digital input

## Physical Layout

### Front View
```
┌──────────────────────────────┐
│ ┌────────────────────────┐   │
│ │                        │   │
│ │     E-Paper Display    │   │
│ │                        │   │
│ └────────────────────────┘   │
│                              │
│ [UP] [DOWN] [SEL] [BACK]     │
│                              │
│ [PWR]        [RED] [GREEN]   │
└──────────────────────────────┘
```

### Side View
```
┌─────────────────────────┐
│                         │
│  ┌─────┐                │
│  │     │ <-- USB Port   │
│  └─────┘                │
│                         │
│  ┌─────┐                │
│  │     │ <-- microSD    │
│  └─────┘                │
│                         │
└─────────────────────────┘
```

## Power Requirements

### Power Consumption Estimates
- Raspberry Pi Zero 2 W: 100-240mA @ 5V (0.5-1.2W)
- E-Paper Display: ~20mA during refresh, <1μA standby
- External WiFi Adapter: 100-250mA @ 5V (0.5-1.25W)
- LEDs and other components: ~20mA @ 3.3V (0.066W)

### Total Power Requirements
- Operating (active attack): ~400mA @ 5V (2W)
- Idle/Standby: ~120mA @ 5V (0.6W)
- Expected battery life with 3000mAh battery:
  - Active usage: ~7-8 hours
  - Standby: ~25 hours

## Assembly Instructions

### 1. Prepare the Raspberry Pi
- Flash microSD card with custom Kali Linux image
- Configure system for headless operation
- Enable required interfaces (SPI, GPIO)

### 2. Connect the E-Paper Display
- Connect display to Raspberry Pi GPIO header according to pin mapping
- Secure with standoffs if necessary

### 3. Add Input Controls and Status Indicators
- Connect buttons to GPIO pins with appropriate pull-up/down resistors
- Connect LEDs with current-limiting resistors (330Ω recommended)

### 4. Power Management Setup
- Connect battery to power management board
- Connect power management board to Raspberry Pi
- Configure GPIO pins for battery monitoring

### 5. External WiFi Setup
- Connect external WiFi adapter via USB
- Configure for monitor mode operation

### 6. Final Assembly
- Arrange components in enclosure
- Secure all connections
- Perform power-on test

## Special Considerations

### Heat Management
- Include ventilation holes in enclosure design
- Consider thermal pads for processor if operating in high-temperature environments
- Monitor CPU temperature via software

### EMI/RFI Considerations
- Keep antenna areas clear of metal components
- Separate digital and analog circuits where possible
- Consider internal shielding for sensitive components

### Durability
- Secure all connections with hot glue or conformal coating
- Use strain relief for external connections
- Consider adding rubber bumpers to protect from drops

### Portability
- Keep weight under 150g for easy carrying
- Include lanyard attachment point
- Design for one-handed operation when possible

## Bill of Materials (BOM)

| Component | Quantity | Estimated Cost (USD) |
|-----------|----------|----------------------|
| Raspberry Pi Zero 2 W | 1 | $15 |
| Waveshare 2.13" E-Paper Display V4 | 1 | $25 |
| External WiFi Adapter | 1 | $10-30 |
| Tactile Push Buttons | 5 | $2 |
| LEDs | 2 | $1 |
| Resistors Pack | 1 | $2 |
| LiPo Battery (3000mAh+) | 1 | $15 |
| Power Management Board | 1 | $5 |
| microSD Card (32GB+) | 1 | $10 |
| Custom 3D-Printed Enclosure | 1 | $5-15 |
| Miscellaneous (wires, connectors, etc.) | - | $5 |
| **Total** | | **$95-125** |