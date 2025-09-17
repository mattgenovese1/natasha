# Natasha AI Penetration Testing Tool

Comprehensive guide for hardware, installation, configuration, and usage. This document reflects the latest codebase improvements, including hardened WiFi/MITM flows, privilege/tool checks, and safer subprocess handling.

---

## 1. Hardware Overview

- Core: Raspberry Pi Zero 2 W
- Display: Waveshare 2.13-inch e-paper (V4, 250×122)
- WiFi: External USB WiFi adapter with monitor mode + injection
  - Recommended chipsets: Atheros AR9271, Ralink RT3070, Realtek RTL8812AU (with proper driver)
- Inputs: 5x tactile buttons (Up, Down, Select, Back, Power)
- Status: 2x LEDs (Red: attack/alert, Green: ready)
- Power: 3000mAh+ LiPo + charge/protection board, or USB supply (≥2.5A)
- Optional: 3D-printed enclosure

---

## 2. Wiring and GPIO Mapping

Display (SPI):
- VCC → 3.3V (Pin 1)
- GND → GND (Pin 6)
- DIN → MOSI (Pin 19)
- CLK → SCLK (Pin 23)
- CS  → CE0 (Pin 24)
- DC  → GPIO 25 (Pin 22)
- RST → GPIO 17 (Pin 11)
- BUSY → GPIO 24 (Pin 18)

Buttons:
- Up → GPIO 5 (Pin 29)
- Down → GPIO 6 (Pin 31)
- Select → GPIO 13 (Pin 33)
- Back → GPIO 19 (Pin 35)
- Power → GPIO 26 (Pin 37)

LEDs:
- Red → GPIO 12 (Pin 32) via resistor (~330Ω)
- Green → GPIO 16 (Pin 36) via resistor (~330Ω)

Use internal pull-ups for buttons or add appropriate resistors.

---

## 3. Software Requirements

System packages (Debian/Kali/RPi OS):
- Base: git, python3, python3-venv, python3-dev, build-essential
- PIL deps: python3-pil, libopenjp2-7, libtiff5
- SPI/GPIO: python3-spidev, python3-rpi.gpio
- Networking tools: aircrack-ng, wireshark-cli (capinfos), tshark, tcpdump, nmap
- AP and DHCP/DNS: hostapd, dnsmasq, iptables, iptables-persistent
- Web: php
- WiFi advanced (optional but recommended):
  - hcxdumptool (PMKID), kismet (logging/scans), reaver (wash for WPS), horst (channel usage)

Python packages:
- RPi.GPIO, spidev, pillow, numpy, scikit-learn, joblib, pycryptodome, scapy, netifaces, psutil
- Optional: tensorflow-lite (if available for platform)

---

## 4. USB HID Gadget (Rubber Ducky Emulation)

1) Enable USB OTG gadget:
- Add to /boot/config.txt: `dtoverlay=dwc2`
- Add to /etc/modules: `dwc2` and `libcomposite`

2) Setup HID gadget on boot:
- Install /usr/local/bin/setup_usb_hid.sh (provided by install.sh)
- Ensure /etc/rc.local invokes the script before `exit 0`

This creates /dev/hidg0 for the HID keyboard emulation.

---

## 5. Display Configuration (E-Paper)

- Enable SPI: `sudo raspi-config nonint do_spi 0`
- The display module auto-detects Waveshare driver; falls back to mock mode on dev systems.
- Fonts: installer fetches DejaVuSansMono.ttf; the display layer falls back to PIL default if not found.

---

## 6. Installation

Option A: Scripted install (recommended)
- Run as root: `sudo ./install.sh`
- The script:
  - Creates ~/natasha with standard directories (logs, scripts, captures, models, templates, portals, fonts)
  - Installs system and Python dependencies
  - Configures SPI and USB HID gadget
  - Creates a generic captive portal in ~/natasha/portals/generic
  - Creates a natasha.service systemd unit to run the app

Option B: Manual (advanced)
- Install packages listed in Sections 3–5
- Create directories under ~/natasha
- Copy project files into ~/natasha
- Create systemd service to run main.py on boot

---

## 7. Configuration and Files

Directories (under ~/natasha):
- logs/: runtime logs
- captures/: WiFi/MITM captures, artifacts (pcaps, logs)
- scripts/: generated DuckyScript files
- analysis/: generated analysis summaries/reports
- templates/: AI payload templates (user overrides)
- portals/: captive portal content (generic created by installer)
- fonts/: display fonts

Key files:
- main.py: application entrypoint and UI state machine
- display_interface.py: display abstraction (mock support for dev)
- ai_engine.py: payload/template generation, template overlay at ~/.natasha/templates
- hid_emulation.py: HID writing and DuckyScript support (STRING, REPEAT, KEYDOWN/UP)
- wifi_attack.py: WiFi scanning and attacks (monitor mode, deauth, evil twin, captive portal, PMKID/handshake)
- wifi_attack_additions.py: advanced scans/analysis/reporting (mixin for WiFiAttack)
- mitm_attack.py / mitm_attack_methods.py: MITM orchestration and UI integration

Permissions:
- Many WiFi/MITM operations require root. The modules verify root and tool presence and fail with clear logs if unmet.

---

## 8. Using the Device

Boot:
- After installation, enable and start natasha.service:
  - `sudo systemctl enable natasha.service`
  - `sudo systemctl start natasha.service`

UI Navigation (buttons):
- Up/Down: navigate menu
- Select: choose/confirm
- Back: previous menu/stop operation
- Power: long-press transitions to shutdown flow

Menus:
- USB Attacks: Credential Harvester, Keylogger, Backdoor, System Info, Custom Script
- WiFi Attacks: Network Scanner, Deauth, Evil Twin, Captive Portal, Handshake Capture, PMKID Attack
- MITM Attacks: Attack selection/config (ARP/DNS/SSL Strip/Capture/Session)
- System Status: CPU, memory, disk, battery, uptime, WiFi/HID status
- Settings: display/network/power/update/factory reset (placeholders unless implemented)

Indicators:
- Green LED on when ready
- Red LED on during active attack; turns off on completion or stop

---

## 9. USB Attacks (HID)

- Select a USB attack and press Select to start
- Connect Pi to target via USB OTG (HID device /dev/hidg0 must be ready)
- The AI engine generates DuckyScript tailored to target OS (auto-detected by HID layer when possible)
- Script lines execute with progress feedback on the display
- Press Back to stop

Notes:
- DuckyScript additions supported: DEFAULTDELAY/DEFAULTCHARDELAY, STRING/STRINGLN, REPEAT, hyphenated combos (ALT-F4), KEYDOWN/KEYUP

---

## 10. WiFi Attacks

General:
- Requires root and tools (aircrack-ng, hostapd, dnsmasq, iptables, php; optionally hcxdumptool, kismet, reaver/wash, horst)
- Monitor mode is enabled automatically; interface state is snapshotted/restored on disable
- Outbound interface for NAT is detected automatically; iptables rules are tracked for precise rollback; original IP forwarding state is restored

Network Scanner (continuous or timed):
- Scans nearby APs and clients; supports advanced scans via wifi_attack_additions

Deauthentication:
- Targeted (AP + client) or broadcast; sets monitor interface to AP channel before injection

Evil Twin:
- Spawns hostapd with chosen SSID/channel; optional encryption; clients may connect to rogue AP

Captive Portal:
- Creates AP + DHCP/DNS + HTTP portal
- NAT rules added are tracked and removed on stop; IP forwarding restored to previous state
- Credentials logged to portal directory (if using generic content)

Handshake/PMKID Capture:
- Handshake: passive or deauth-assisted capture; outputs pcap/csv
- PMKID: uses hcxdumptool on specified channel; outputs pcapng (size > 24 bytes suggests data captured)

Advanced Scans & Reports:
- wifi_attack_additions provides airodump/kismet/wps/channel-usage scans and report generation (HTML/Text/JSON)

---

## 11. MITM Attacks

- Components: ARP spoofing, DNS spoofing, SSL stripping, packet capture, session hijack
- Hardened process lifecycle: terminate → wait → kill; shared status guarded by locks
- Inputs validated (IPs/domains/ports)
- Artifacts (dnsmasq/sslstrip/pid files, captures) tracked and cleaned
- UI refresh loop shows live updates on the display

---

## 12. Troubleshooting

General:
- Run as root for WiFi/MITM flows; ensure required tools are installed (the app logs missing tools)
- Check service logs: `sudo journalctl -u natasha.service -f`

HID:
- Verify /dev/hidg0 exists and setup_usb_hid.sh runs on boot
- Cable orientation (OTG) matters; use a quality OTG adapter

WiFi:
- Confirm external adapter: `ip link`, `iw dev`
- Driver monitor mode/injection support: `iw list`
- Conflicts (NetworkManager/wpa_supplicant) can interfere; airmon-ng may stop them; restart after use if required

Captive Portal:
- Ensure dnsmasq/hostapd not already running; check logs if ports are in use
- NAT rules use detected outbound interface; verify with `ip route`

PMKID/Handshake:
- Ensure hcxdumptool present; verify channel tuning
- Confirm captures contain expected frames with `tshark`/`capinfos`

Display:
- SPI enabled; wiring correct; mock mode indicates development environment

---

## 13. Security and Ethics

- Use only in lab or with explicit authorization
- Comply with laws and organizational policies
- Maintain logs and document scope
- Avoid persistent changes on third-party networks

---

## 14. Build Checklist

- [ ] SPI enabled; display connected and tested
- [ ] USB HID gadget configured; /dev/hidg0 present
- [ ] External WiFi adapter supports monitor mode/injection
- [ ] System tools installed (aircrack-ng, hostapd, dnsmasq, iptables, php; optional: hcxdumptool, kismet, reaver/wash, horst, tshark)
- [ ] Python deps installed
- [ ] Directories (logs, captures, scripts, templates, portals, analysis, fonts) present under ~/natasha
- [ ] natasha.service enabled and running

---

## 15. Appendix: Manual Systemd Service

Example service (edit paths as needed):

```
[Unit]
Description=Natasha AI Penetration Testing Tool
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/natasha/main.py
WorkingDirectory=/home/pi/natasha
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Enable and start:

```
sudo systemctl daemon-reload
sudo systemctl enable natasha.service
sudo systemctl start natasha.service
```
