# Natasha AI Penetration Testing Tool

![Natasha Logo](images/natasha_logo.png)

## Overview

Natasha is an AI-powered penetration testing tool designed for educational purposes. It combines the capabilities of a USB Rubber Ducky and WiFi Pineapple into a single, portable device powered by a Raspberry Pi Zero 2 W with a Waveshare 2.13-inch e-paper display.

Natasha features a sophisticated AI engine that can generate attack scripts tailored to different target operating systems, making it a versatile tool for security education and authorized penetration testing.

## Features

### USB Attack Capabilities (Rubber Ducky)
- **Credential Harvesting**: Extract stored credentials from browsers and other sources
- **Keylogging**: Capture keystrokes on target systems
- **Backdoor Deployment**: Create persistent access to target systems
- **System Reconnaissance**: Gather detailed information about target systems
- **Custom Script Generation**: AI-powered generation of attack scripts

### WiFi Attack Capabilities (WiFi Pineapple)
- **Network Scanning**: Discover and analyze nearby wireless networks
- **Deauthentication Attacks**: Disconnect clients from their associated access points
- **Evil Twin Attacks**: Create rogue access points mimicking legitimate networks
- **Captive Portal Attacks**: Deploy phishing captive portals for credential harvesting
- **Handshake Capture**: Capture WPA/WPA2 handshakes for offline password cracking
- **PMKID Attacks**: Capture PMKID hashes without client interaction

### AI-Powered Features
- **Target OS Detection**: Automatically detect and adapt to different operating systems
- **Script Generation**: Create sophisticated attack scripts based on target environment
- **Adaptive Strategies**: Modify attack approaches based on environmental feedback
- **Natural Language Processing**: Generate scripts from natural language descriptions

### User Interface
- **Character-Based Interface**: Featuring "Natasha" as your penetration testing assistant
- **E-Paper Display**: Low-power, high-visibility display for field operations
- **Button Navigation**: Simple, intuitive controls for menu navigation
- **Status Indicators**: Visual feedback on attack progress and system status

## Hardware Requirements

- Raspberry Pi Zero 2 W
- Waveshare 2.13-inch e-paper display V4
- External WiFi adapter with monitor mode support
- Buttons for navigation
- LEDs for status indication
- Battery pack for portable operation
- Optional: 3D-printed case

## Installation

### 1. Prepare the Raspberry Pi

1. Download and flash Kali Linux ARM image for Raspberry Pi:
   ```
   wget https://images.kali.org/arm-images/kali-linux-2023.1-raspberry-pi-zero-2-w-armhf.img.xz
   xz -d kali-linux-2023.1-raspberry-pi-zero-2-w-armhf.img.xz
   sudo dd if=kali-linux-2023.1-raspberry-pi-zero-2-w-armhf.img of=/dev/sdX bs=4M status=progress
   ```

2. Boot the Raspberry Pi and perform initial setup:
   ```
   sudo apt update
   sudo apt upgrade -y
   ```

### 2. Install Dependencies

```bash
# System dependencies
sudo apt install -y git python3-pip python3-dev python3-pil python3-numpy libopenjp2-7 libtiff5 python3-venv
sudo apt install -y aircrack-ng wireshark-cli tcpdump nmap hostapd dnsmasq iptables-persistent
sudo apt install -y build-essential python3-dev libssl-dev libffi-dev
sudo apt install -y python3-spidev python3-rpi.gpio

# Python dependencies
sudo pip3 install RPi.GPIO spidev pillow numpy tensorflow-lite scikit-learn pycryptodome scapy netifaces psutil
```

### 3. Configure Hardware

1. Enable SPI interface:
   ```
   sudo raspi-config nonint do_spi 0
   ```

2. Configure USB OTG for HID emulation:
   ```
   echo "dtoverlay=dwc2" | sudo tee -a /boot/config.txt
   echo "dwc2" | sudo tee -a /etc/modules
   echo "libcomposite" | sudo tee -a /etc/modules
   ```

3. Create USB HID setup script:
   ```bash
   sudo nano /usr/local/bin/setup_usb_hid.sh
   ```

   Add the following content:
   ```bash
   #!/bin/bash
   
   cd /sys/kernel/config/usb_gadget/
   mkdir -p natasha
   cd natasha
   
   # USB device configuration
   echo 0x1d6b > idVendor  # Linux Foundation
   echo 0x0104 > idProduct # Multifunction Composite Gadget
   echo 0x0100 > bcdDevice # v1.0.0
   echo 0x0200 > bcdUSB    # USB2
   
   # Device information
   mkdir -p strings/0x409
   echo "fedcba9876543210" > strings/0x409/serialnumber
   echo "Natasha Security" > strings/0x409/manufacturer
   echo "Penetration Testing Tool" > strings/0x409/product
   
   # HID keyboard configuration
   mkdir -p functions/hid.usb0
   echo 1 > functions/hid.usb0/protocol
   echo 1 > functions/hid.usb0/subclass
   echo 8 > functions/hid.usb0/report_length
   
   # HID report descriptor (keyboard)
   echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc
   
   # Create configuration
   mkdir -p configs/c.1/strings/0x409
   echo "HID Config" > configs/c.1/strings/0x409/configuration
   echo 250 > configs/c.1/MaxPower
   
   # Link HID function to configuration
   ln -s functions/hid.usb0 configs/c.1/
   
   # Enable the gadget
   ls /sys/class/udc > UDC
   ```

4. Make the script executable and configure it to run at boot:
   ```
   sudo chmod +x /usr/local/bin/setup_usb_hid.sh
   echo "/usr/local/bin/setup_usb_hid.sh" | sudo tee -a /etc/rc.local
   ```

### 4. Connect the E-Paper Display

Connect the Waveshare 2.13-inch e-paper display to the Raspberry Pi GPIO pins:

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

### 5. Connect Buttons and LEDs

Connect the navigation buttons and status LEDs to the Raspberry Pi GPIO pins:

| Component       | Raspberry Pi GPIO Pin |
|-----------------|------------------------|
| Up Button       | GPIO 5 (Pin 29)       |
| Down Button     | GPIO 6 (Pin 31)       |
| Select Button   | GPIO 13 (Pin 33)      |
| Back Button     | GPIO 19 (Pin 35)      |
| Power Button    | GPIO 26 (Pin 37)      |
| Red LED         | GPIO 12 (Pin 32)      |
| Green LED       | GPIO 16 (Pin 36)      |

### 6. Clone and Install Natasha

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/natasha.git ~/natasha
   cd ~/natasha
   ```

2. Create necessary directories:
   ```
   mkdir -p ~/natasha/logs
   mkdir -p ~/natasha/scripts
   mkdir -p ~/natasha/captures
   ```

3. Configure autostart:
   ```
   sudo nano /etc/systemd/system/natasha.service
   ```

   Add the following content:
   ```
   [Unit]
   Description=Natasha AI Penetration Testing Tool
   After=network.target
   
   [Service]
   ExecStart=/usr/bin/python3 /home/kali/natasha/main.py
   WorkingDirectory=/home/kali/natasha
   StandardOutput=inherit
   StandardError=inherit
   Restart=always
   User=kali
   
   [Install]
   WantedBy=multi-user.target
   ```

4. Enable the service:
   ```
   sudo systemctl enable natasha.service
   sudo systemctl start natasha.service
   ```

## Usage

### Navigation

- **Up/Down Buttons**: Navigate through menus
- **Select Button**: Choose the selected option
- **Back Button**: Return to the previous menu
- **Power Button**: Long press to shut down the device

### USB Attacks

1. From the main menu, select "USB Attacks"
2. Choose an attack type:
   - Credential Harvester
   - Keylogger
   - Backdoor
   - System Information
   - Custom Script
3. Configure attack parameters (if applicable)
4. Press Select to start the attack
5. Connect the device to the target system via USB
6. Monitor the attack progress on the display
7. Press Back to stop the attack and return to the menu

### WiFi Attacks

1. From the main menu, select "WiFi Attacks"
2. Choose an attack type:
   - Network Scanner
   - Deauthentication
   - Evil Twin
   - Captive Portal
   - Handshake Capture
   - PMKID Attack
3. Configure attack parameters (if applicable)
4. Press Select to start the attack
5. Monitor the attack progress on the display
6. Press Back to stop the attack and return to the menu

### System Status

1. From the main menu, select "System Status"
2. View information about:
   - CPU usage
   - Memory usage
   - Disk usage
   - Battery level
   - Uptime
   - WiFi status
   - USB HID status
3. Press Back to return to the main menu

### Settings

1. From the main menu, select "Settings"
2. Configure various settings:
   - Display Settings
   - Network Settings
   - Power Settings
   - Update Software
   - Factory Reset
3. Press Back to return to the main menu

## Ethical Considerations

This tool is designed for educational purposes and authorized penetration testing only. Unauthorized use of this tool against systems without explicit permission is illegal and unethical.

Always:
- Obtain proper authorization before testing any system
- Document your testing activities
- Report vulnerabilities responsibly
- Follow applicable laws and regulations
- Use this tool only in controlled environments

## Troubleshooting

### Display Issues
- Check SPI interface is enabled: `ls -l /dev/spi*`
- Verify connections between Raspberry Pi and display
- Test with Waveshare example code

### USB HID Issues
- Check USB gadget configuration: `ls /sys/kernel/config/usb_gadget/`
- Verify USB OTG cable is connected correctly
- Test with simple HID script

### WiFi Issues
- Check adapter is recognized: `ip a`
- Verify driver supports monitor mode: `iw list`
- Test with airmon-ng: `sudo airmon-ng start wlan1`

### Power Issues
- Check power supply is adequate (2.5A recommended)
- Monitor voltage: `vcgencmd measure_volts`
- Check for undervoltage warnings: `dmesg | grep voltage`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is provided for educational purposes only. The authors are not responsible for any misuse or damage caused by this tool. Use at your own risk.