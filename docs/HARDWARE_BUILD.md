# Natasha Hardware Build Guide

Comprehensive instructions to assemble the hardware platform for the Natasha AI Penetration Testing Tool. This guide consolidates recommended components, wiring, assembly, power, enclosure, and validation steps, matching the current software expectations (GPIO mappings, display, USB HID, and WiFi requirements).

---

## 1. Bill of Materials (BOM)

Core components:
- Raspberry Pi Zero 2 W
- Waveshare 2.13" e-Paper Display V4 (250×122, SPI)
- External USB WiFi adapter with monitor mode + injection
  - Recommended chipsets: Atheros AR9271 (2.4 GHz), Ralink RT3070 (2.4 GHz), Realtek RTL8812AU (dual-band; driver required)
- 5x momentary push buttons (Up, Down, Select, Back, Power)
- 2x 3 mm LEDs (Red, Green) + 2x 330Ω resistors
- Power:
  - 3000 mAh+ LiPo battery (protected)
  - 5V boost/charge board (or quality USB power bank)
  - Quality USB cable(s) and OTG adapter/hub (for WiFi adapter)
- microSD card (32 GB or larger, Class 10+)
- Wires, headers, standoffs, screws, heat-shrink
- Optional: 3D-printed enclosure

Tools:
- Soldering iron + solder
- Multimeter
- Wire stripper/cutter
- Small screwdrivers
- 3D printer (optional)

---

## 2. GPIO Mapping and Wiring

The software expects the following GPIOs.

Display (SPI):
- VCC → 3.3V (Pin 1)
- GND → GND (Pin 6)
- DIN → MOSI (Pin 19)
- CLK → SCLK (Pin 23)
- CS  → CE0 (Pin 24)
- DC  → GPIO 25 (Pin 22)
- RST → GPIO 17 (Pin 11)
- BUSY → GPIO 24 (Pin 18)

Buttons (momentary, to ground):
- Up → GPIO 5 (Pin 29)
- Down → GPIO 6 (Pin 31)
- Select → GPIO 13 (Pin 33)
- Back → GPIO 19 (Pin 35)
- Power → GPIO 26 (Pin 37)

Notes:
- The firmware enables internal pull-ups for buttons. Wire one side of the button to the GPIO pin and the other side to GND.
- Debounce is handled in software.

LEDs (active-high):
- Red: GPIO 12 (Pin 32) → 330Ω resistor → LED → GND
- Green: GPIO 16 (Pin 36) → 330Ω resistor → LED → GND

External WiFi Adapter:
- Connect via USB OTG adapter or a powered micro-USB hub. For high-draw adapters (e.g., 8812AU), a powered hub is recommended.

USB HID (target connection):
- Pi Zero 2 W USB data port (the middle/OTG port) connects to the target with an OTG cable. The other micro-USB port can be used for power if not battery-powered.

---

## 3. Power System

Options:
- Battery-driven: LiPo battery + boost/charge board → 5V output to Pi. Choose a board with overcurrent/undervoltage protection.
- USB-powered: Quality 5V, 2.5A+ supply.

Recommendations:
- Keep wiring short to minimize voltage drop.
- If using a WiFi adapter with high peak current, prefer a powered hub or a robust 5V regulator.
- Consider ventilation and small heat sinks if ambient temperature is high.

---

## 4. Assembly Steps

1) Prepare the Pi
- Flash OS (Kali ARM or Raspberry Pi OS + tools). See installation guides.
- Boot and update packages.

2) Solder Headers (if needed)
- Add 40-pin header to the Pi Zero 2 W (if not pre-soldered).

3) Mount the e-Paper Display
- Use standoffs and screws; route SPI pins to the mapped GPIOs.
- Double-check pin mapping (miswiring may damage the display).

4) Wire Buttons and LEDs
- Buttons: GPIO pin → button → GND
- LEDs: GPIO pin → 330Ω → LED → GND (observe LED polarity)

5) Connect External WiFi
- Plug the adapter into an OTG adapter/hub. Ensure adequate power.

6) Power Integration
- For battery builds, connect LiPo to boost/charge board, then 5V to the Pi.
- Ensure stable 5V under load (check with a multimeter).

7) Enclosure (Optional)
- Print and assemble an enclosure that provides airflow and access to ports and buttons.
- Keep the WiFi adapter/antenna clear of metal surfaces.

---

## 5. Enclosure and Layout Tips

- Place the display on the front face; align buttons beneath it for usability.
- Keep the WiFi antenna external or near plastic windows for better RF performance.
- Add ventilation slots near the CPU and under the adapter.
- Provide strain relief for cables.
- Consider threaded inserts for repeated opening.

Front layout (example):
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

---

## 6. Software Configuration Hooks

After assembly, ensure the following software configurations are complete (handled automatically by install.sh; see docs/USER_GUIDE.md for details):

- SPI enabled for the display:
```
sudo raspi-config nonint do_spi 0
```
- USB HID gadget configured (creates /dev/hidg0 via /usr/local/bin/setup_usb_hid.sh)
- Required tools installed (aircrack-ng, hostapd, dnsmasq, iptables, php; optional: hcxdumptool, kismet, reaver/wash, horst, tshark)
- Systemd service natasha.service enabled (runs main.py at boot)

---

## 7. Validation and Smoke Tests

Display:
```
ls -l /dev/spi*
# Run the app/service and observe splash/menu on the e-paper display
```

Buttons/LEDs (with app running):
- Press Up/Down and observe menu navigation.
- Verify LEDs: Green on when idle, Red on during attacks.

USB HID:
```
ls /dev/hidg0
# Connect OTG to a test machine; verify key events when running a simple DuckyScript
```

WiFi Adapter:
```
iw dev
iw list | grep -E "Supported interface modes|monitor" -A3
ip route show default  # verify outbound interface detection
```

Captive Portal flow (root):
- Start a captive portal from the app.
- Verify hostapd/dnsmasq processes start and that a client can see/connect to the SSID.
- Check that iptables rules were added and then cleaned on stop; verify IP forwarding restoration:
```
sysctl -n net.ipv4.ip_forward
sudo iptables -S
sudo iptables -t nat -S
```

Handshake/PMKID (optional tools):
- Confirm hcxdumptool installed and test channel capture.

---

## 8. RF, Power, and Safety Considerations

RF:
- Keep antenna areas unobstructed and away from metal.
- Dual-band adapters may need driver installation (e.g., RTL8812AU).

Power:
- Ensure 5V rail remains above ~4.8V under load.
- Prefer a powered hub for power-hungry adapters.

Safety:
- Observe ESD handling for electronics.
- Secure battery and avoid short circuits; don’t compress LiPo cells.

---

## 9. Troubleshooting

No display output:
- Verify SPI, wiring, and display driver. The app uses a mock display if the driver is missing; confirm environment logs.

Buttons unresponsive:
- Check GND continuity; confirm internal pull-ups and software debounce (0.2 s).

WiFi adapter not detected:
- Check dmesg; try a different OTG adapter/hub; ensure adequate power.

HID not working:
- Confirm /dev/hidg0 exists and setup script runs at boot; try re-running the setup script.

Captive portal NAT issues:
- Verify iptables rules and outbound interface; check dnsmasq/hostapd logs for port conflicts.

---

## 10. Ethics and Legal Use

This device is for educational use and authorized security testing only. Always operate within legal and contractual boundaries, obtain explicit permission, and preserve evidence/logs of tests.
