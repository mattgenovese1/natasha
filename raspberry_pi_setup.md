# Natasha - Raspberry Pi Setup Guide

## Overview
This guide outlines the process for setting up the Raspberry Pi Zero 2 W as the foundation for the Natasha AI penetration testing tool. The setup includes installing the operating system, configuring necessary services, and preparing the environment for the Natasha software components.

## Hardware Requirements
- Raspberry Pi Zero 2 W
- 32GB+ microSD card (Class 10 or better)
- Waveshare 2.13-inch e-paper display V4
- External WiFi adapter with monitor mode support
- Buttons, LEDs, and other hardware components as specified in the hardware design document

## Operating System Installation

### 1. Base Image Preparation

#### Option A: Kali Linux ARM (Recommended)
1. Download the latest Kali Linux ARM image for Raspberry Pi:
   ```
   wget https://images.kali.org/arm-images/kali-linux-2023.1-raspberry-pi-zero-2-w-armhf.img.xz
   ```

2. Extract the image:
   ```
   xz -d kali-linux-2023.1-raspberry-pi-zero-2-w-armhf.img.xz
   ```

3. Write the image to the microSD card (replace `/dev/sdX` with your SD card device):
   ```
   sudo dd if=kali-linux-2023.1-raspberry-pi-zero-2-w-armhf.img of=/dev/sdX bs=4M status=progress
   ```

#### Option B: Raspberry Pi OS with Kali Tools
1. Download the latest Raspberry Pi OS Lite image:
   ```
   wget https://downloads.raspberrypi.org/raspios_lite_armhf_latest
   ```

2. Extract the image:
   ```
   unzip raspios_lite_armhf_latest
   ```

3. Write the image to the microSD card:
   ```
   sudo dd if=raspios_lite_armhf_*.img of=/dev/sdX bs=4M status=progress
   ```

4. Mount the boot partition and create an SSH file to enable SSH:
   ```
   sudo mkdir -p /mnt/boot
   sudo mount /dev/sdX1 /mnt/boot
   sudo touch /mnt/boot/ssh
   ```

5. Configure WiFi (optional, for headless setup):
   ```
   sudo nano /mnt/boot/wpa_supplicant.conf
   ```
   
   Add the following content:
   ```
   country=US
   ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
   update_config=1
   
   network={
       ssid="YOUR_WIFI_SSID"
       psk="YOUR_WIFI_PASSWORD"
       key_mgmt=WPA-PSK
   }
   ```

6. Unmount the boot partition:
   ```
   sudo umount /mnt/boot
   ```

### 2. First Boot and Basic Configuration

1. Insert the microSD card into the Raspberry Pi Zero 2 W and power it on

2. Connect to the Raspberry Pi via SSH:
   ```
   ssh pi@raspberrypi.local  # Default password: raspberry (for Raspberry Pi OS)
   # OR
   ssh kali@kali.local       # Default password: kali (for Kali Linux)
   ```

3. Update the system:
   ```
   sudo apt update
   sudo apt upgrade -y
   ```

4. Change the default password:
   ```
   passwd
   ```

5. Configure the hostname:
   ```
   sudo hostnamectl set-hostname natasha
   ```

6. Edit the hosts file:
   ```
   sudo nano /etc/hosts
   ```
   
   Update the localhost line to include the new hostname:
   ```
   127.0.1.1       natasha
   ```

7. Configure timezone and locale:
   ```
   sudo dpkg-reconfigure tzdata
   sudo dpkg-reconfigure locales
   ```

## System Configuration

### 1. Enable Required Interfaces

1. Enable SPI interface (required for e-paper display):
   ```
   sudo raspi-config nonint do_spi 0
   ```

2. Enable I2C interface (optional, for additional sensors):
   ```
   sudo raspi-config nonint do_i2c 0
   ```

3. Configure USB OTG for HID emulation:
   ```
   sudo nano /boot/config.txt
   ```
   
   Add the following line:
   ```
   dtoverlay=dwc2
   ```

4. Edit the modules file:
   ```
   sudo nano /etc/modules
   ```
   
   Add the following lines:
   ```
   dwc2
   libcomposite
   ```

### 2. Install Required Packages

#### Base Dependencies
```
sudo apt install -y git python3-pip python3-dev python3-pil python3-numpy libopenjp2-7 libtiff5 python3-venv
```

#### Networking Tools
```
sudo apt install -y aircrack-ng wireshark-cli tcpdump nmap hostapd dnsmasq iptables-persistent
```

#### Development Tools
```
sudo apt install -y build-essential python3-dev libssl-dev libffi-dev
```

#### E-Paper Display Dependencies
```
sudo apt install -y python3-spidev python3-rpi.gpio
```

#### AI and Machine Learning Libraries
```
sudo pip3 install tensorflow-lite scikit-learn joblib
```

### 3. Configure USB HID Gadget

1. Create a setup script:
   ```
   sudo nano /usr/local/bin/setup_usb_hid.sh
   ```

2. Add the following content:
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

3. Make the script executable:
   ```
   sudo chmod +x /usr/local/bin/setup_usb_hid.sh
   ```

4. Configure the script to run at boot:
   ```
   sudo nano /etc/rc.local
   ```
   
   Add before the `exit 0` line:
   ```
   /usr/local/bin/setup_usb_hid.sh &
   ```

### 4. Configure Wireless Interface

1. Install aircrack-ng suite:
   ```
   sudo apt install -y aircrack-ng
   ```

2. Create a script to configure the external wireless adapter:
   ```
   sudo nano /usr/local/bin/setup_wireless.sh
   ```

3. Add the following content:
   ```bash
   #!/bin/bash
   
   # Check if external adapter is connected
   if ip link | grep -q wlan1; then
       # Put adapter in monitor mode
       sudo ip link set wlan1 down
       sudo iw dev wlan1 set type monitor
       sudo ip link set wlan1 up
       echo "External wireless adapter configured in monitor mode"
   else
       echo "External wireless adapter not found"
   fi
   ```

4. Make the script executable:
   ```
   sudo chmod +x /usr/local/bin/setup_wireless.sh
   ```

### 5. Configure E-Paper Display

1. Clone the Waveshare e-Paper library:
   ```
   git clone https://github.com/waveshare/e-Paper.git
   ```

2. Install the Python library:
   ```
   cd e-Paper/RaspberryPi_JetsonNano/python
   sudo pip3 install ./
   ```

3. Test the display:
   ```
   cd examples
   python3 epd_2in13_V4_test.py
   ```

## Natasha Software Installation

### 1. Create Project Directory

```
mkdir -p ~/natasha
cd ~/natasha
```

### 2. Set Up Python Virtual Environment

```
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Required Python Packages

```
pip install RPi.GPIO spidev pillow numpy tensorflow-lite scikit-learn pycryptodome scapy netifaces
```

### 4. Clone Natasha Repository

```
git clone https://github.com/yourusername/natasha.git .
```

### 5. Configure Autostart

1. Create a systemd service file:
   ```
   sudo nano /etc/systemd/system/natasha.service
   ```

2. Add the following content:
   ```
   [Unit]
   Description=Natasha AI Penetration Testing Tool
   After=network.target
   
   [Service]
   ExecStart=/home/pi/natasha/venv/bin/python3 /home/pi/natasha/main.py
   WorkingDirectory=/home/pi/natasha
   StandardOutput=inherit
   StandardError=inherit
   Restart=always
   User=pi
   
   [Install]
   WantedBy=multi-user.target
   ```

3. Enable the service:
   ```
   sudo systemctl enable natasha.service
   ```

### 6. Configure Power Management

1. Install power management tools:
   ```
   sudo apt install -y powertop
   ```

2. Create a power optimization script:
   ```
   sudo nano /usr/local/bin/optimize_power.sh
   ```

3. Add the following content:
   ```bash
   #!/bin/bash
   
   # Disable HDMI (saves ~30mA)
   /usr/bin/tvservice -o
   
   # Set CPU governor to powersave
   echo "powersave" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
   
   # Disable unused USB controllers
   echo 0 | sudo tee /sys/devices/platform/soc/*/usb*/**/power/control
   
   # Disable Bluetooth if not needed
   sudo systemctl disable bluetooth.service
   sudo systemctl stop bluetooth.service
   ```

4. Make the script executable:
   ```
   sudo chmod +x /usr/local/bin/optimize_power.sh
   ```

5. Configure the script to run at boot:
   ```
   sudo nano /etc/rc.local
   ```
   
   Add before the `exit 0` line:
   ```
   /usr/local/bin/optimize_power.sh &
   ```

## Security Hardening

### 1. Disable Unnecessary Services

```
sudo systemctl disable avahi-daemon
sudo systemctl disable triggerhappy
sudo systemctl disable bluetooth
```

### 2. Configure Firewall

```
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
```

### 3. Secure SSH Access

1. Edit SSH configuration:
   ```
   sudo nano /etc/ssh/sshd_config
   ```

2. Make the following changes:
   ```
   PermitRootLogin no
   PasswordAuthentication no
   ```

3. Set up SSH key authentication:
   ```
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   nano ~/.ssh/authorized_keys
   # Add your public key here
   chmod 600 ~/.ssh/authorized_keys
   ```

4. Restart SSH service:
   ```
   sudo systemctl restart ssh
   ```

## Final Setup

### 1. Test Hardware Components

1. Test e-paper display:
   ```
   cd ~/natasha
   python3 tests/test_display.py
   ```

2. Test buttons and LEDs:
   ```
   python3 tests/test_gpio.py
   ```

3. Test USB HID functionality:
   ```
   python3 tests/test_hid.py
   ```

4. Test wireless capabilities:
   ```
   python3 tests/test_wireless.py
   ```

### 2. System Verification

1. Verify all services are running:
   ```
   sudo systemctl status natasha.service
   ```

2. Check for any errors in the logs:
   ```
   sudo journalctl -u natasha.service
   ```

3. Verify system boot time:
   ```
   systemd-analyze
   ```

### 3. Final Reboot

```
sudo reboot
```

## Troubleshooting

### Display Issues
- Check SPI interface is enabled: `ls -l /dev/spi*`
- Verify connections between Raspberry Pi and display
- Test with Waveshare example code

### USB HID Issues
- Check USB gadget configuration: `ls /sys/kernel/config/usb_gadget/`
- Verify USB OTG cable is connected correctly
- Test with simple HID script

### Wireless Issues
- Check adapter is recognized: `ip a`
- Verify driver supports monitor mode: `iw list`
- Test with airmon-ng: `sudo airmon-ng start wlan1`

### Power Issues
- Check power supply is adequate (2.5A recommended)
- Monitor voltage: `vcgencmd measure_volts`
- Check for undervoltage warnings: `dmesg | grep voltage`