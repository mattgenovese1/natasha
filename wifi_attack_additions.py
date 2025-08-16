def advanced_scan_networks(self, scan_type: str = "basic", duration: int = 60, 
                              channel: int = None, bssid: str = None) -> Dict[str, Any]:
        """Perform an advanced scan of WiFi networks.
        
        Args:
            scan_type: Type of scan to perform (basic, airodump, kismet, hidden_ssid, client, channel_usage, wps)
            duration: Duration of scan in seconds
            channel: Specific channel to scan (optional)
            bssid: Specific BSSID to focus on (optional)
            
        Returns:
            Dictionary containing scan results
        """
        with self.lock:
            logging.info(f"Starting advanced network scan: {scan_type}")
            
            # Enable monitor mode
            if not self._enable_monitor_mode():
                logging.error("Failed to enable monitor mode for advanced scan")
                return {}
            
            # Create output file path
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            output_file = os.path.join(self.capture_dir, f"scan_{scan_type}_{timestamp}")
            
            # Set channel if specified
            if channel is not None:
                subprocess.run(["iw", "dev", self.monitor_interface.name, "set", "channel", str(channel)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Prepare scan command based on scan type
            if scan_type == "basic":
                cmd = ["iw", "dev", self.monitor_interface.name, "scan"]
                if channel:
                    cmd.extend(["freq", str(2412 + (channel - 1) * 5)])
            elif scan_type == "airodump":
                cmd = ["airodump-ng", self.monitor_interface.name, "--output-format", "csv", 
                      "-w", output_file, "--write-interval", "1"]
                if channel:
                    cmd.extend(["--channel", str(channel)])
                if bssid:
                    cmd.extend(["--bssid", bssid])
            elif scan_type == "kismet":
                cmd = ["kismet", "-c", self.monitor_interface.name, "--no-ncurses", 
                      "--log-types=csv", f"--log-prefix={output_file}"]
            elif scan_type == "hidden_ssid":
                cmd = ["airodump-ng", self.monitor_interface.name, "--output-format", "csv", 
                      "-w", output_file, "--write-interval", "1"]
            elif scan_type == "client":
                if not bssid:
                    logging.error("BSSID required for client scan")
                    return {}
                cmd = ["airodump-ng", self.monitor_interface.name, "--output-format", "csv", 
                      "-w", output_file, "--write-interval", "1", "--bssid", bssid]
                if channel:
                    cmd.extend(["--channel", str(channel)])
            elif scan_type == "channel_usage":
                cmd = ["horst", "-i", self.monitor_interface.name, "-o", f"{output_file}.csv", "-N"]
                if channel:
                    cmd.extend(["-c", str(channel)])
            elif scan_type == "wps":
                cmd = ["wash", "-i", self.monitor_interface.name, "-o", f"{output_file}.csv"]
            else:
                logging.error(f"Unknown scan type: {scan_type}")
                return {}
            
            try:
                # Start scan process
                logging.info(f"Running scan command: {' '.join(cmd)}")
                
                # For non-blocking scans (airodump, kismet, etc.)
                if scan_type != "basic":
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    # Wait for specified duration
                    time.sleep(duration)
                    
                    # Terminate scan process
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    
                    # Parse results based on scan type
                    results = self._parse_scan_results(scan_type, output_file)
                else:
                    # For basic scan (blocking)
                    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=duration)
                    results = self._parse_iw_scan(process.stdout.decode('utf-8', errors='ignore'))
                
                # Store results in scan history
                scan_entry = {
                    "timestamp": timestamp,
                    "type": scan_type,
                    "duration": duration,
                    "channel": channel,
                    "bssid": bssid,
                    "results": results
                }
                self.scan_history.append(scan_entry)
                
                # Update statistics
                self._update_scan_statistics(results, scan_type)
                
                return results
                
            except subprocess.TimeoutExpired:
                logging.error(f"Scan timed out after {duration} seconds")
                return {}
            except Exception as e:
                logging.error(f"Error during advanced scan: {e}")
                return {}
    
    def _parse_scan_results(self, scan_type: str, output_file: str) -> Dict[str, Any]:
        """Parse scan results based on scan type.
        
        Args:
            scan_type: Type of scan performed
            output_file: Base path of output files
            
        Returns:
            Dictionary containing parsed results
        """
        results = {}
        
        try:
            if scan_type == "airodump" or scan_type == "hidden_ssid" or scan_type == "client":
                # Parse airodump CSV output
                csv_file = f"{output_file}-01.csv"
                if os.path.exists(csv_file):
                    with open(csv_file, 'r') as f:
                        content = f.read()
                    
                    # Split into AP and client sections
                    sections = content.split("\r\n\r\n")
                    if len(sections) >= 2:
                        ap_section = sections[0].strip()
                        client_section = sections[1].strip()
                        
                        # Parse APs
                        ap_lines = ap_section.split("\r\n")[1:]  # Skip header
                        aps = {}
                        for line in ap_lines:
                            if line.strip():
                                fields = [f.strip() for f in line.split(",")]
                                if len(fields) >= 14:
                                    bssid = fields[0].strip()
                                    first_seen = fields[1].strip()
                                    last_seen = fields[2].strip()
                                    channel = fields[3].strip()
                                    speed = fields[4].strip()
                                    privacy = fields[5].strip()
                                    cipher = fields[6].strip()
                                    auth = fields[7].strip()
                                    power = fields[8].strip()
                                    beacons = fields[9].strip()
                                    data = fields[10].strip()
                                    lan_ip = fields[11].strip()
                                    essid = fields[13].strip().strip('\x00')
                                    
                                    aps[bssid] = {
                                        "bssid": bssid,
                                        "first_seen": first_seen,
                                        "last_seen": last_seen,
                                        "channel": channel,
                                        "speed": speed,
                                        "privacy": privacy,
                                        "cipher": cipher,
                                        "auth": auth,
                                        "power": power,
                                        "beacons": beacons,
                                        "data": data,
                                        "lan_ip": lan_ip,
                                        "essid": essid,
                                        "hidden": essid == ""
                                    }
                        
                        # Parse clients
                        client_lines = client_section.split("\r\n")[1:]  # Skip header
                        clients = {}
                        for line in client_lines:
                            if line.strip():
                                fields = [f.strip() for f in line.split(",")]
                                if len(fields) >= 6:
                                    mac = fields[0].strip()
                                    first_seen = fields[1].strip()
                                    last_seen = fields[2].strip()
                                    power = fields[3].strip()
                                    packets = fields[4].strip()
                                    bssid = fields[5].strip()
                                    
                                    clients[mac] = {
                                        "mac": mac,
                                        "first_seen": first_seen,
                                        "last_seen": last_seen,
                                        "power": power,
                                        "packets": packets,
                                        "bssid": bssid
                                    }
                        
                        results["access_points"] = aps
                        results["clients"] = clients
            
            elif scan_type == "wps":
                # Parse wash output
                csv_file = f"{output_file}.csv"
                if os.path.exists(csv_file):
                    wps_networks = {}
                    with open(csv_file, 'r') as f:
                        for line in f:
                            if line.strip() and not line.startswith("BSSID"):
                                fields = [f.strip() for f in line.split(",")]
                                if len(fields) >= 6:
                                    bssid = fields[0].strip()
                                    channel = fields[1].strip()
                                    rssi = fields[2].strip()
                                    wps_version = fields[3].strip()
                                    wps_locked = fields[4].strip()
                                    essid = fields[5].strip()
                                    
                                    wps_networks[bssid] = {
                                        "bssid": bssid,
                                        "channel": channel,
                                        "rssi": rssi,
                                        "wps_version": wps_version,
                                        "wps_locked": wps_locked == "Yes",
                                        "essid": essid
                                    }
                    
                    results["wps_networks"] = wps_networks
            
            elif scan_type == "channel_usage":
                # Parse horst output
                csv_file = f"{output_file}.csv"
                if os.path.exists(csv_file):
                    channel_data = {}
                    with open(csv_file, 'r') as f:
                        for line in f:
                            if line.strip() and not line.startswith("#"):
                                fields = [f.strip() for f in line.split(",")]
                                if len(fields) >= 3:
                                    channel = fields[0].strip()
                                    utilization = fields[1].strip()
                                    max_utilization = fields[2].strip()
                                    
                                    channel_data[channel] = {
                                        "channel": channel,
                                        "utilization": float(utilization) if utilization else 0,
                                        "max_utilization": float(max_utilization) if max_utilization else 0
                                    }
                    
                    results["channel_data"] = channel_data
        
        except Exception as e:
            logging.error(f"Error parsing scan results: {e}")
        
        return results
    
    def _parse_iw_scan(self, scan_output: str) -> Dict[str, Dict[str, Any]]:
        """Parse output from iw scan command.
        
        Args:
            scan_output: Output from iw scan command
            
        Returns:
            Dictionary of access points
        """
        access_points = {}
        current_bssid = None
        current_ap = {}
        
        for line in scan_output.splitlines():
            line = line.strip()
            
            # New BSS section
            if line.startswith("BSS "):
                # Save previous AP if exists
                if current_bssid and current_ap:
                    access_points[current_bssid] = current_ap
                
                # Extract new BSSID
                bssid_match = re.search(r"BSS ([0-9a-fA-F:]{17})", line)
                if bssid_match:
                    current_bssid = bssid_match.group(1)
                    current_ap = {"bssid": current_bssid}
            
            # Extract SSID
            elif "SSID: " in line:
                ssid = line.split("SSID: ")[1].strip()
                current_ap["essid"] = ssid
                current_ap["hidden"] = ssid == ""
            
            # Extract channel
            elif "DS Parameter set: channel" in line:
                channel = line.split("channel")[1].strip()
                current_ap["channel"] = channel
            
            # Extract frequency
            elif "freq: " in line:
                freq = line.split("freq: ")[1].strip()
                current_ap["frequency"] = freq
            
            # Extract signal strength
            elif "signal: " in line:
                signal = line.split("signal: ")[1].split(" ")[0].strip()
                current_ap["signal"] = signal
            
            # Extract security info
            elif "capability: " in line:
                if "Privacy" in line:
                    current_ap["privacy"] = "Y"
                else:
                    current_ap["privacy"] = "N"
            
            # Extract encryption info
            elif "RSN:" in line or "WPA:" in line:
                if "RSN:" in line:
                    current_ap["security"] = "WPA2"
                else:
                    current_ap["security"] = "WPA"
                
                # Look for cipher and authentication details in next lines
                cipher_line = scan_output.splitlines()[scan_output.splitlines().index(line) + 2]
                auth_line = scan_output.splitlines()[scan_output.splitlines().index(line) + 4]
                
                if "Cipher: " in cipher_line:
                    current_ap["cipher"] = cipher_line.split("Cipher: ")[1].strip()
                
                if "Authentication suites: " in auth_line:
                    current_ap["auth"] = auth_line.split("Authentication suites: ")[1].strip()
        
        # Add the last AP
        if current_bssid and current_ap:
            access_points[current_bssid] = current_ap
        
        return access_points
    
    def _update_scan_statistics(self, results: Dict[str, Any], scan_type: str) -> None:
        """Update statistics based on scan results.
        
        Args:
            results: Scan results
            scan_type: Type of scan performed
        """
        # Update access points
        if "access_points" in results:
            for bssid, ap in results["access_points"].items():
                self.access_points[bssid] = AccessPoint(
                    ap.get("essid", ""),
                    bssid,
                    int(ap.get("channel", 0)) if ap.get("channel", "").isdigit() else 0,
                    ap.get("privacy", ""),
                    int(ap.get("power", 0)) if ap.get("power", "").isdigit() else 0
                )
                
                # Update hidden networks
                if ap.get("hidden", False):
                    self.hidden_networks[bssid] = ap
        
        # Update clients
        if "clients" in results:
            for mac, client in results["clients"].items():
                self.clients[mac] = Client(
                    mac,
                    client.get("bssid", ""),
                    int(client.get("power", 0)) if client.get("power", "").isdigit() else 0
                )
                
                # Update client statistics
                if client.get("bssid", "") in self.client_stats:
                    self.client_stats[client.get("bssid", "")].append(mac)
                else:
                    self.client_stats[client.get("bssid", "")] = [mac]
        
        # Update WPS enabled networks
        if "wps_networks" in results:
            for bssid, network in results["wps_networks"].items():
                self.wps_enabled_networks[bssid] = network
        
        # Update channel statistics
        if "channel_data" in results:
            self.channel_stats = results["channel_data"]
        
        # Update encryption statistics
        if "access_points" in results:
            encryption_counts = {}
            for bssid, ap in results["access_points"].items():
                encryption = ap.get("privacy", "Unknown")
                if encryption in encryption_counts:
                    encryption_counts[encryption] += 1
                else:
                    encryption_counts[encryption] = 1
            
            self.encryption_stats = encryption_counts
    
    def analyze_network_security(self) -> Dict[str, Any]:
        """Analyze security of discovered networks.
        
        Returns:
            Dictionary containing security analysis results
        """
        analysis = {
            "vulnerable_networks": [],
            "encryption_distribution": {},
            "open_networks": [],
            "wps_networks": [],
            "hidden_networks": [],
            "client_connections": {},
            "channel_utilization": {}
        }
        
        # Analyze encryption distribution
        encryption_counts = {}
        for bssid, ap in self.access_points.items():
            if ap.encryption in encryption_counts:
                encryption_counts[ap.encryption] += 1
            else:
                encryption_counts[ap.encryption] = 1
        
        analysis["encryption_distribution"] = encryption_counts
        
        # Identify vulnerable networks
        for bssid, ap in self.access_points.items():
            network = {
                "bssid": bssid,
                "ssid": ap.ssid,
                "channel": ap.channel,
                "encryption": ap.encryption,
                "vulnerabilities": []
            }
            
            # Check for open networks
            if ap.encryption == "OPN" or ap.encryption == "":
                network["vulnerabilities"].append("Open Network")
                analysis["open_networks"].append({
                    "bssid": bssid,
                    "ssid": ap.ssid,
                    "channel": ap.channel
                })
            
            # Check for WEP encryption
            if "WEP" in ap.encryption:
                network["vulnerabilities"].append("WEP Encryption")
            
            # Check for WPS
            if bssid in self.wps_enabled_networks:
                network["vulnerabilities"].append("WPS Enabled")
                analysis["wps_networks"].append({
                    "bssid": bssid,
                    "ssid": ap.ssid,
                    "channel": ap.channel,
                    "wps_version": self.wps_enabled_networks[bssid].get("wps_version", ""),
                    "wps_locked": self.wps_enabled_networks[bssid].get("wps_locked", False)
                })
            
            # Add to vulnerable networks if any vulnerabilities found
            if network["vulnerabilities"]:
                analysis["vulnerable_networks"].append(network)
        
        # Add hidden networks
        for bssid, ap in self.hidden_networks.items():
            analysis["hidden_networks"].append({
                "bssid": bssid,
                "channel": ap.get("channel", 0),
                "signal": ap.get("power", 0)
            })
        
        # Add client connections
        analysis["client_connections"] = self.client_stats
        
        # Add channel utilization
        analysis["channel_utilization"] = self.channel_stats
        
        return analysis
    
    def generate_network_report(self, output_format: str = "text") -> str:
        """Generate a comprehensive report of network analysis.
        
        Args:
            output_format: Format of the report (text, json, html)
            
        Returns:
            Report in the specified format
        """
        # Perform security analysis
        analysis = self.analyze_network_security()
        
        if output_format == "json":
            # Generate JSON report
            report_data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "access_points": {bssid: {
                    "ssid": ap.ssid,
                    "channel": ap.channel,
                    "encryption": ap.encryption,
                    "signal": ap.signal
                } for bssid, ap in self.access_points.items()},
                "clients": {mac: {
                    "ap_bssid": client.ap_bssid,
                    "signal": client.signal
                } for mac, client in self.clients.items()},
                "analysis": analysis
            }
            
            return json.dumps(report_data, indent=2)
            
        elif output_format == "html":
            # Generate HTML report
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>WiFi Network Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .vulnerable {{ color: red; }}
        .warning {{ color: orange; }}
        .secure {{ color: green; }}
    </style>
</head>
<body>
    <h1>WiFi Network Analysis Report</h1>
    <p>Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <h2>Network Overview</h2>
    <p>Total Networks: {len(self.access_points)}</p>
    <p>Total Clients: {len(self.clients)}</p>
    <p>Vulnerable Networks: {len(analysis["vulnerable_networks"])}</p>
    <p>Hidden Networks: {len(analysis["hidden_networks"])}</p>
    
    <h2>Access Points</h2>
    <table>
        <tr>
            <th>BSSID</th>
            <th>SSID</th>
            <th>Channel</th>
            <th>Encryption</th>
            <th>Signal</th>
            <th>Security</th>
        </tr>
"""
            
            # Add rows for each access point
            for bssid, ap in self.access_points.items():
                # Determine security class
                security_class = "secure"
                security_text = "Secure"
                
                for vuln_network in analysis["vulnerable_networks"]:
                    if vuln_network["bssid"] == bssid:
                        security_class = "vulnerable"
                        security_text = ", ".join(vuln_network["vulnerabilities"])
                        break
                
                html += f"""
        <tr>
            <td>{bssid}</td>
            <td>{ap.ssid if ap.ssid else "<hidden>"}</td>
            <td>{ap.channel}</td>
            <td>{ap.encryption}</td>
            <td>{ap.signal}</td>
            <td class="{security_class}">{security_text}</td>
        </tr>"""
            
            html += """
    </table>
    
    <h2>Clients</h2>
    <table>
        <tr>
            <th>MAC</th>
            <th>Connected To</th>
            <th>Signal</th>
        </tr>
"""
            
            # Add rows for each client
            for mac, client in self.clients.items():
                ap_ssid = ""
                if client.ap_bssid in self.access_points:
                    ap_ssid = self.access_points[client.ap_bssid].ssid
                
                html += f"""
        <tr>
            <td>{mac}</td>
            <td>{client.ap_bssid} ({ap_ssid})</td>
            <td>{client.signal}</td>
        </tr>"""
            
            html += """
    </table>
    
    <h2>Security Analysis</h2>
    <h3>Encryption Distribution</h3>
    <table>
        <tr>
            <th>Encryption Type</th>
            <th>Count</th>
        </tr>
"""
            
            # Add rows for encryption distribution
            for enc_type, count in analysis["encryption_distribution"].items():
                html += f"""
        <tr>
            <td>{enc_type}</td>
            <td>{count}</td>
        </tr>"""
            
            html += """
    </table>
    
    <h3>Vulnerable Networks</h3>
    <table>
        <tr>
            <th>BSSID</th>
            <th>SSID</th>
            <th>Vulnerabilities</th>
        </tr>
"""
            
            # Add rows for vulnerable networks
            for network in analysis["vulnerable_networks"]:
                html += f"""
        <tr>
            <td>{network["bssid"]}</td>
            <td>{network["ssid"] if network["ssid"] else "<hidden>"}</td>
            <td class="vulnerable">{", ".join(network["vulnerabilities"])}</td>
        </tr>"""
            
            html += """
    </table>
</body>
</html>
"""
            return html
            
        else:  # Default to text format
            # Generate text report
            report = f"WiFi Network Analysis Report\n"
            report += f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            report += f"Network Overview\n"
            report += f"---------------\n"
            report += f"Total Networks: {len(self.access_points)}\n"
            report += f"Total Clients: {len(self.clients)}\n"
            report += f"Vulnerable Networks: {len(analysis['vulnerable_networks'])}\n"
            report += f"Hidden Networks: {len(analysis['hidden_networks'])}\n\n"
            
            report += f"Access Points\n"
            report += f"------------\n"
            report += f"{'BSSID':<18} {'SSID':<32} {'Ch':<4} {'Encryption':<10} {'Signal':<8} {'Security':<20}\n"
            
            for bssid, ap in self.access_points.items():
                security_text = "Secure"
                
                for vuln_network in analysis["vulnerable_networks"]:
                    if vuln_network["bssid"] == bssid:
                        security_text = ", ".join(vuln_network["vulnerabilities"])
                        break
                
                report += f"{bssid:<18} {ap.ssid if ap.ssid else '<hidden>':<32} {ap.channel:<4} {ap.encryption:<10} {ap.signal:<8} {security_text:<20}\n"
            
            report += f"\nClients\n"
            report += f"-------\n"
            report += f"{'MAC':<18} {'Connected To':<50} {'Signal':<8}\n"
            
            for mac, client in self.clients.items():
                ap_ssid = ""
                if client.ap_bssid in self.access_points:
                    ap_ssid = self.access_points[client.ap_bssid].ssid
                
                report += f"{mac:<18} {client.ap_bssid} ({ap_ssid}):{' ':<30} {client.signal:<8}\n"
            
            report += f"\nSecurity Analysis\n"
            report += f"----------------\n"
            report += f"Encryption Distribution:\n"
            
            for enc_type, count in analysis["encryption_distribution"].items():
                report += f"  {enc_type}: {count}\n"
            
            report += f"\nVulnerable Networks:\n"
            for network in analysis["vulnerable_networks"]:
                report += f"  {network['bssid']} ({network['ssid'] if network['ssid'] else '<hidden>'}): {', '.join(network['vulnerabilities'])}\n"
            
            report += f"\nHidden Networks:\n"
            for network in analysis["hidden_networks"]:
                report += f"  {network['bssid']} (Ch {network['channel']}): Signal {network['signal']}\n"
            
            return report
    
    def start_network_analysis(self, scan_types: List[str] = None, duration: int = 300) -> None:
        """Start comprehensive network analysis.
        
        Args:
            scan_types: List of scan types to perform
            duration: Total duration for analysis in seconds
        """
        if scan_types is None:
            scan_types = ["basic", "airodump", "wps", "channel_usage"]
        
        logging.info(f"Starting comprehensive network analysis: {', '.join(scan_types)}")
        
        # Create a thread for the analysis
        self.attack_thread = threading.Thread(target=self._run_network_analysis, 
                                             args=(scan_types, duration))
        self.attack_thread.daemon = True
        self.attack_thread.start()
        
        # Update attack status
        self.attack_status = {
            "type": AttackType.NETWORK_SCAN,
            "status": "running",
            "start_time": time.time(),
            "duration": duration,
            "scan_types": scan_types
        }
    
    def _run_network_analysis(self, scan_types: List[str], duration: int) -> None:
        """Run network analysis in a background thread.
        
        Args:
            scan_types: List of scan types to perform
            duration: Total duration for analysis in seconds
        """
        try:
            # Calculate time per scan type
            time_per_scan = duration / len(scan_types)
            
            # Perform each scan type
            for scan_type in scan_types:
                if self.stop_event.is_set():
                    break
                
                # Update status
                self.attack_status["current_scan"] = scan_type
                self.attack_status["status"] = f"Scanning with {scan_type}"
                
                # Perform scan
                results = self.advanced_scan_networks(scan_type=scan_type, duration=time_per_scan)
                
                # Save results
                self.scan_results[scan_type] = results
            
            # Generate report
            report = self.generate_network_report()
            report_path = os.path.join(self.analysis_dir, f"network_report_{time.strftime('%Y%m%d-%H%M%S')}.txt")
            
            with open(report_path, 'w') as f:
                f.write(report)
            
            # Generate HTML report
            html_report = self.generate_network_report(output_format="html")
            html_report_path = os.path.join(self.analysis_dir, f"network_report_{time.strftime('%Y%m%d-%H%M%S')}.html")
            
            with open(html_report_path, 'w') as f:
                f.write(html_report)
            
            # Update status
            self.attack_status["status"] = "completed"
            self.attack_status["end_time"] = time.time()
            self.attack_status["report_path"] = report_path
            self.attack_status["html_report_path"] = html_report_path
            
        except Exception as e:
            logging.error(f"Error during network analysis: {e}")
            self.attack_status["status"] = "failed"
            self.attack_status["error"] = str(e)