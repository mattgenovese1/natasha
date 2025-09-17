# Natasha Installation, Configuration, and Usage Guide

This document explains how to install dependencies, configure the environment, and run Natasha in a safe, stable way. It also maps each feature to the system tools it requires and documents how to customize network settings (e.g., captive portal) to avoid conflicts with your environment.

Important: Use only in environments where you have explicit authorization. Many operations require elevated privileges (root).

---

## Supported Platform (reference)

- Raspberry Pi OS (Debian-based) or other Debian-based Linux (Ubuntu/Debian/Kali)
- Python 3.9+
- Optional hardware:
  - Waveshare 2.13" e-paper display (V4)
  - Raspberry Pi Zero 2 W (or similar)
  - USB HID gadget capability (for keyboard emulation) on Pi Zero class devices

Natasha can run in "mock" display mode without hardware (the UI renders without an e-paper display if the driver is absent).

---

## System Dependencies (Debian/Ubuntu/Raspberry Pi OS)

The commands below install required packages for most features. Run as root (or prefix with sudo).

```bash
apt update
apt install -y \
  python3 python3-pip python3-pil \
  git iproute2 iw \
  aircrack-ng hostapd dnsmasq php php-cli \
  bettercap hcxdumptool \
  tcpdump tshark wireshark-common
```

Notes:
- python3-pil installs Pillow via system packages (you can also use `pip install pillow`).
- `aircrack-ng` provides `airmon-ng`, `airodump-ng`, and `aireplay-ng`.
- `wireshark-common` provides `capinfos`. `tshark` is also installed for CLI analysis.
- `bettercap` replaces deprecated sslstrip functionality for MITM lab demos (HSTS limits real HTTPS stripping on modern sites).
- On some distros, `bettercap` may not be in the default repo; consult official docs to install.

Optional Python libraries:

```bash
# Optional: waveshare e-paper driver (mock mode is automatic if missing)
pip3 install waveshare-epd

# Optional: in case system PIL is missing
pip3 install pillow
```

---

## Feature → Tools Mapping

- WiFi Scanning (Network/Passive):
  - Requires: `aircrack-ng` (`airodump-ng`), `iw`
- WiFi Deauthentication (client/network):
  - Requires: `aircrack-ng` (`aireplay-ng`), `iw`
- Evil Twin (AP creation):
  - Requires: `hostapd`, `iw`, `iproute2` (`ip`)
- Captive Portal (AP + DHCP/DNS + NAT + web):
  - Requires: `hostapd`, `dnsmasq`, `iptables`, `php`, `iproute2` (`ip`), `sysctl`
- Handshake Capture:
  - Requires: `aircrack-ng` (`airodump-ng`), `iw`
- PMKID Attack:
  - Requires: `hcxdumptool`, `iw`
- Packet Capture + Analysis:
  - Requires: `tcpdump`, `tshark`, `wireshark-common` (`capinfos`)
- MITM (replacement for sslstrip):
  - Requires: `bettercap`
- HID Keyboard Emulation (USB gadget, Pi Zero class):
  - Requires: USB gadget configuration (kernel configfs); see reference notes below.

---

## Running Natasha

From the project root:

```bash
cd /home/trm314/natasha
python3 main.py --debug
```

Tips:
- Most WiFi operations require root: run the app with `sudo` or as root.
- The UI can be driven with GPIO buttons on hardware; in dev mode, keyboard shortcuts are enabled (w/s = up/down, Enter = select, b = back, q = quit).
- If the Waveshare driver is not installed/connected, the UI runs in mock mode.

---

## Captive Portal Network Configuration

The captive portal uses a configurable subnet and NAT to route traffic. To avoid conflicts with your local network (e.g., 192.168.1.0/24), customize the subnet and outbound interface in the config file.

Config file path:

```
~/.natasha/config.json
```

Example:

```json
{
  "network": {
    "captive_portal": {
      "gateway_ip": "192.168.55.1",
      "subnet_cidr": "192.168.55.1/24",
      "netmask": "255.255.255.0",
      "dhcp_range_start": "192.168.55.10",
      "dhcp_range_end": "192.168.55.50",
      "dns": "1.1.1.1",
      "outbound_iface": "eth0"
    }
  }
}
```

- `gateway_ip`: IP assigned to the AP interface (Natasha device side).
- `subnet_cidr`: CIDR to assign to the interface (must match gateway_ip subnet).
- `netmask`: Netmask for DHCP pool config.
- `dhcp_range_start` / `dhcp_range_end`: Client DHCP range.
- `dns`: Upstream DNS server for dnsmasq.
- `outbound_iface`: (Optional) Override outbound interface used for NAT (defaults to system default route).

During captive portal start, Natasha will:
- Configure the AP interface with `subnet_cidr`.
- Start `hostapd` on the AP interface.
- Start `dnsmasq` bound to `gateway_ip`/AP interface.
- Setup iptables NAT rules toward `outbound_iface`.
- Redirect HTTP traffic (port 80) to the local portal web server.

Cleanup will revert iptables rules and IP forwarding state. If `airmon-ng` kills network services, Natasha attempts to restore them during cleanup.

---

## Permissions and Services

- Run as root for WiFi and iptables operations.
- `airmon-ng check kill` can stop services (NetworkManager, wpa_supplicant). Natasha snapshots and attempts to restore them during cleanup; if restoration fails, you may need to restart manually:

```bash
systemctl start NetworkManager
systemctl start wpa_supplicant
```

- If `hostapd` or `dnsmasq` are enabled as system services, stop/disable them before using Natasha’s captive portal to prevent conflicts:

```bash
systemctl stop hostapd dnsmasq
systemctl disable hostapd dnsmasq
```

---

## Display (Waveshare 2.13" V4)

- Optional. The app will run in mock display mode if the driver is not present.
- Install the Python driver:

```bash
pip3 install waveshare-epd
```

If using hardware:
- Ensure SPI/I2C are enabled and the display is wired correctly.
- Driver import is `from waveshare_epd import epd2in13_V4`.

---

## USB HID Gadget (Pi Zero class)

For Raspberry Pi Zero class devices, you can configure the USB gadget framework to expose a HID keyboard device to a target host. High-level steps only (refer to official documentation for details):

1. Enable dwc2 and configfs overlays (boot/config.txt):
   - `dtoverlay=dwc2`
2. Ensure modules load on boot (boot/cmdline.txt):
   - Insert `modules-load=dwc2` after `root=...` (consult official docs for syntax)
3. Use configfs to create a HID gadget (keyboard) and bind to `usb0`:
   - Create gadget under `/sys/kernel/config/usb_gadget/...`
   - Define device/vendor IDs and HID function
   - Bind to UDC
4. A device file (e.g., `/dev/hidg0`) should appear; Natasha’s HID emulator uses that path.

References:
- Raspberry Pi USB Gadget documentation
- Linux USB gadget/configfs guides

---

## Known Issues / Troubleshooting

- Not running as root:
  - Many WiFi operations will fail. Run with `sudo` or as root.
- Missing tools:
  - The app logs which tools are missing; install with apt.
- AP won’t start:
  - Ensure managed mode is active (Natasha enforces this for AP flows)
  - Stop/disable system `hostapd`/`dnsmasq` services to avoid port/bind conflicts
- No DNS/DHCP for clients:
  - Verify `dnsmasq` is bound to the AP IP (Natasha writes `listen-address=<gateway_ip>`)
- No internet for clients on captive portal:
  - Confirm NAT rules are added and `outbound_iface` points to the correct uplink
- airmon-ng kills networking:
  - Natasha attempts to restore; if not restored, manually start services (see above)

---

## Safe Operation and Ethics

- Use only in environments where you have explicit authorization.
- Default fallbacks are benign (e.g., printing system/network info, local demo files).
- Avoid enabling destructive or disruptive operations outside of lab environments.

---

## Project Layout Overview

- `main.py` — application entry point and UI state machine
- `display_interface.py` — e-paper display UI (mock-enabled)
- `ai_engine.py` — template loading and DuckyScript generation
- `hid_emulation.py` — USB HID (keyboard) emulator
- `wifi_attack.py` — WiFi scanning/attacks, captive portal, and cleanup/restoration logic
- `mitm_attack.py` — MITM functionality (bettercap-based for lab demos)
- `templates/` — DuckyScript templates and JSON definitions
- `docs/` — documentation (this file)

---

## Quick Start

```bash
# Install dependencies (Debian-based)
sudo apt update
sudo apt install -y python3 python3-pip python3-pil git iproute2 iw \
  aircrack-ng hostapd dnsmasq php php-cli bettercap hcxdumptool \
  tcpdump tshark wireshark-common

# Optional Python driver for display
pip3 install waveshare-epd

# Run the app
cd /home/trm314/natasha
sudo python3 main.py --debug
```

Configure `~/.natasha/config.json` to set captive portal network settings and avoid subnet conflicts.
