from __future__ import annotations

import os
import re
import json
import time
import logging
import threading
import subprocess
from typing import Dict, List, Any, Optional


# NOTE:
# These helpers are designed to be mixed into the WiFiAttack class at runtime.
# They rely on the instance providing the following attributes/methods:
# - self.lock (threading.Lock)
# - self.stop_event (threading.Event)
# - self.capture_dir, self.analysis_dir
# - self.monitor_interface, self._enable_monitor_mode()
# - self._require_root(op: str) -> bool
# - self._require_tools(tools: List[str]) -> bool
# - self._update_scan_statistics(results: Dict[str, Any], scan_type: str) -> None
# - self.access_points (Dict), self.clients (Dict), self.hidden_networks (Dict),
#   self.client_stats (Dict), self.wps_enabled_networks (Dict), self.channel_stats (Dict),
#   self.encryption_stats (Dict), self.scan_history (List)
#
# To avoid circular imports, we perform on-demand imports of AccessPoint/Client where needed.


def advanced_scan_networks(self, scan_type: str = "basic", duration: int = 60,
                           channel: Optional[int] = None, bssid: Optional[str] = None) -> Dict[str, Any]:
    """Perform an advanced scan of WiFi networks.

    Args:
        scan_type: Type of scan to perform (basic, airodump, kismet, hidden_ssid, client, channel_usage, wps)
        duration: Duration of scan in seconds
        channel: Specific channel to scan (optional)
        bssid: Specific BSSID to focus on (optional)

    Returns:
        Dictionary containing scan results
    """
    logging.info(f"Starting advanced network scan: {scan_type}")

    # Privilege and tool checks
    if not self._require_root("Advanced scan"):
        return {}

    tools: List[str] = []
    # Validate and include channel tool as needed
    if scan_type == "basic":
        tools += ["iw"]
    elif scan_type in ("airodump", "hidden_ssid", "client"):
        tools += ["airodump-ng"]
    elif scan_type == "kismet":
        tools += ["kismet"]
    elif scan_type == "channel_usage":
        tools += ["horst"]
    elif scan_type == "wps":
        tools += ["wash"]
    else:
        logging.error(f"Unknown scan type: {scan_type}")
        return {}

    # If we will set channel, ensure iw is present
    if channel is not None and "iw" not in tools:
        tools.append("iw")

    if not self._require_tools(tools):
        return {}

    # Enable monitor mode
    if not self._enable_monitor_mode():
        logging.error("Failed to enable monitor mode for advanced scan")
        return {}

    # Validate inputs
    ch_val: Optional[int] = None
    if channel is not None:
        try:
            ch_val = int(channel)
        except Exception:
            logging.error("Invalid channel value (not an integer)")
            return {}
        if ch_val <= 0:
            logging.error("Invalid channel value (must be positive)")
            return {}

    if bssid is not None:
        if not re.match(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$", bssid):
            logging.error("Invalid BSSID format. Expected MAC like AA:BB:CC:DD:EE:FF")
            return {}

    # Create output file base path
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_file = os.path.join(self.capture_dir, f"scan_{scan_type}_{timestamp}")

    # Helper: set monitor channel if requested
    if ch_val is not None:
        try:
            subprocess.run(["iw", "dev", self.monitor_interface.name, "set", "channel", str(ch_val)],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as cpe:
            logging.error(f"Failed to set channel {ch_val}: {cpe.stderr.decode('utf-8', errors='ignore')}")
            return {}
        except Exception as e:
            logging.error(f"Failed to set channel {ch_val}: {e}")
            return {}

    # Build command
    cmd: List[str]
    if scan_type == "basic":
        cmd = ["iw", "dev", self.monitor_interface.name, "scan"]
        if ch_val is not None:
            # iw scan can filter by frequency; convert channel to frequency
            freq = _channel_to_frequency(ch_val)
            if freq is None:
                logging.error(f"Unsupported channel for basic scan: {ch_val}")
                return {}
            cmd.extend(["freq", str(freq)])
    elif scan_type == "airodump":
        cmd = ["airodump-ng", self.monitor_interface.name, "--output-format", "csv",
               "-w", output_file, "--write-interval", "1"]
        if ch_val is not None:
            cmd.extend(["--channel", str(ch_val)])
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
        if ch_val is not None:
            cmd.extend(["--channel", str(ch_val)])
    elif scan_type == "channel_usage":
        cmd = ["horst", "-i", self.monitor_interface.name, "-o", f"{output_file}.csv", "-N"]
        if ch_val is not None:
            cmd.extend(["-c", str(ch_val)])
    elif scan_type == "wps":
        cmd = ["wash", "-i", self.monitor_interface.name, "-o", f"{output_file}.csv"]
    else:
        # Already guarded
        return {}

    try:
        logging.info(f"Running scan command: {' '.join(cmd)}")
        if scan_type != "basic":
            # Long-running tools: run detached and kill after duration or stop_event
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            start = time.time()
            # Stop-responsive wait
            while time.time() - start < duration:
                if self.stop_event.is_set():
                    break
                time.sleep(0.5)
            # Terminate and ensure exit
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            # Parse results from files
            results = self._parse_scan_results(scan_type, output_file)
            # Best-effort cleanup of temporary outputs
            try:
                if scan_type in ("airodump", "hidden_ssid", "client"):
                    csv_file = f"{output_file}-01.csv"
                    if os.path.exists(csv_file):
                        os.unlink(csv_file)
                elif scan_type in ("wps", "channel_usage"):
                    csv_file = f"{output_file}.csv"
                    if os.path.exists(csv_file):
                        os.unlink(csv_file)
            except Exception:
                pass
        else:
            # Basic scan: blocking command; use timeout for duration
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=duration)
            results = self._parse_iw_scan(process.stdout.decode('utf-8', errors='ignore'))

        # Store results and update stats under lock
        scan_entry = {
            "timestamp": timestamp,
            "type": scan_type,
            "duration": duration,
            "channel": ch_val,
            "bssid": bssid,
            "results": results,
        }
        with self.lock:
            self.scan_history.append(scan_entry)
            self._update_scan_statistics(results, scan_type)
        return results

    except subprocess.TimeoutExpired:
        logging.error(f"Scan timed out after {duration} seconds")
        return {}
    except FileNotFoundError as fnf:
        logging.error(f"Scan tool not found: {fnf}")
        return {}
    except Exception as e:
        logging.error(f"Error during advanced scan: {e}")
        return {}


def _channel_to_frequency(ch: int) -> Optional[int]:
    """Map WiFi channel to center frequency for iw scan filtering.
    Covers 2.4 GHz (1–14), typical 5 GHz channels, and a provisional 6 GHz mapping.
    """
    # 2.4 GHz
    if 1 <= ch <= 13:
        return 2412 + 5 * (ch - 1)
    if ch == 14:
        return 2484
    # 5 GHz common mapping (36..177, step 4 channels)
    if 36 <= ch <= 177:
        return 5000 + 5 * ch
    # 6 GHz (approximate mapping as placeholder)
    if 1 <= ch <= 233:
        return 5950 + 5 * ch
    return None


def _parse_scan_results(self, scan_type: str, output_file: str) -> Dict[str, Any]:
    """Parse scan results based on scan type.

    Args:
        scan_type: Type of scan performed
        output_file: Base path of output files

    Returns:
        Dictionary containing parsed results
    """
    results: Dict[str, Any] = {}

    try:
        if scan_type in ("airodump", "hidden_ssid", "client"):
            csv_file = f"{output_file}-01.csv"
            if os.path.exists(csv_file):
                with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # Normalize newlines
                content = content.replace('\r\n', '\n')
                sections = content.split('\n\n')
                if len(sections) >= 2:
                    ap_section = sections[0].strip()
                    client_section = sections[1].strip()
                    # APs
                    ap_lines = ap_section.split('\n')
                    if ap_lines and ap_lines[0].lower().startswith("bssid"):
                        ap_lines = ap_lines[1:]
                    aps: Dict[str, Any] = {}
                    for line in ap_lines:
                        if not line.strip():
                            continue
                        fields = [c.strip() for c in line.split(',')]
                        if len(fields) < 14:
                            continue
                        bssid = fields[0]
                        try:
                            aps[bssid] = {
                                "bssid": bssid,
                                "first_seen": fields[1],
                                "last_seen": fields[2],
                                "channel": fields[3],
                                "speed": fields[4],
                                "privacy": fields[5],
                                "cipher": fields[6],
                                "auth": fields[7],
                                "power": fields[8],
                                "beacons": fields[9],
                                "data": fields[10],
                                "lan_ip": fields[11],
                                "essid": fields[13].strip().strip('\x00'),
                                "hidden": fields[13].strip() == "",
                            }
                        except Exception:
                            continue
                    # Clients
                    cl_lines = client_section.split('\n')
                    if cl_lines and cl_lines[0].lower().startswith("station mac"):
                        cl_lines = cl_lines[1:]
                    clients: Dict[str, Any] = {}
                    for line in cl_lines:
                        if not line.strip():
                            continue
                        fields = [c.strip() for c in line.split(',')]
                        if len(fields) < 6:
                            continue
                        mac = fields[0]
                        try:
                            clients[mac] = {
                                "mac": mac,
                                "first_seen": fields[1],
                                "last_seen": fields[2],
                                "power": fields[3],
                                "packets": fields[4],
                                "bssid": fields[5],
                            }
                        except Exception:
                            continue
                    results["access_points"] = aps
                    results["clients"] = clients
        elif scan_type == "wps":
            csv_file = f"{output_file}.csv"
            if os.path.exists(csv_file):
                wps_networks: Dict[str, Any] = {}
                with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.strip() and not line.startswith("BSSID"):
                            fields = [c.strip() for c in line.split(',')]
                            if len(fields) >= 6:
                                bssid = fields[0]
                                wps_networks[bssid] = {
                                    "bssid": bssid,
                                    "channel": fields[1],
                                    "rssi": fields[2],
                                    "wps_version": fields[3],
                                    "wps_locked": fields[4] == "Yes",
                                    "essid": fields[5],
                                }
                results["wps_networks"] = wps_networks
        elif scan_type == "channel_usage":
            csv_file = f"{output_file}.csv"
            if os.path.exists(csv_file):
                channel_data: Dict[str, Any] = {}
                with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            fields = [c.strip() for c in line.split(',')]
                            if len(fields) >= 3:
                                try:
                                    channel_data[fields[0]] = {
                                        "channel": fields[0],
                                        "utilization": float(fields[1]) if fields[1] else 0.0,
                                        "max_utilization": float(fields[2]) if fields[2] else 0.0,
                                    }
                                except Exception:
                                    continue
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
    access_points: Dict[str, Dict[str, Any]] = {}
    lines = [ln.strip() for ln in scan_output.splitlines()]

    current_bssid: Optional[str] = None
    current_ap: Dict[str, Any] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("BSS "):
            # Save previous
            if current_bssid and current_ap:
                access_points[current_bssid] = current_ap
            # Start new
            m = re.search(r"BSS ([0-9a-fA-F:]{17})", line)
            current_bssid = m.group(1) if m else None
            current_ap = {"bssid": current_bssid} if current_bssid else {}
        elif "SSID:" in line:
            ssid = line.split("SSID:", 1)[1].strip()
            current_ap["essid"] = ssid
            current_ap["hidden"] = (ssid == "")
        elif "DS Parameter set: channel" in line:
            ch = line.split("channel", 1)[1].strip()
            current_ap["channel"] = ch
        elif line.startswith("freq:"):
            freq = line.split("freq:", 1)[1].strip()
            current_ap["frequency"] = freq
        elif line.startswith("signal:"):
            sig = line.split("signal:", 1)[1].strip().split()[0]
            current_ap["signal"] = sig
        elif line.startswith("capability:"):
            current_ap["privacy"] = "Y" if "Privacy" in line else "N"
        elif line.startswith("RSN:") or line.startswith("WPA:"):
            current_ap["security"] = "WPA2" if line.startswith("RSN:") else "WPA"
            # Look ahead a few lines for Cipher and Authentication suites
            for j in range(i + 1, min(i + 8, n)):
                nxt = lines[j]
                if "Cipher:" in nxt and "cipher" not in current_ap:
                    current_ap["cipher"] = nxt.split("Cipher:", 1)[1].strip()
                if "Authentication suites:" in nxt and "auth" not in current_ap:
                    current_ap["auth"] = nxt.split("Authentication suites:", 1)[1].strip()
        i += 1

    # Save last AP
    if current_bssid and current_ap:
        access_points[current_bssid] = current_ap

    return access_points


def _update_scan_statistics(self, results: Dict[str, Any], scan_type: str) -> None:
    """Update statistics based on scan results.

    Args:
        results: Scan results
        scan_type: Type of scan performed
    """
    # Import lazily to avoid circular dependency at module import time
    try:
        from wifi_attack import AccessPoint, Client  # type: ignore
    except Exception:
        AccessPoint = None  # type: ignore
        Client = None  # type: ignore

    with self.lock:
        # Update access points
        if "access_points" in results:
            for bssid, ap in results["access_points"].items():
                if AccessPoint is not None:
                    try:
                        channel_val = int(ap.get("channel", 0)) if str(ap.get("channel", "")).isdigit() else 0
                    except Exception:
                        channel_val = 0
                    try:
                        power_val = int(ap.get("power", 0)) if str(ap.get("power", "")).isdigit() else 0
                    except Exception:
                        power_val = 0
                    self.access_points[bssid] = AccessPoint(
                        ap.get("essid", ""),
                        bssid,
                        channel_val,
                        ap.get("privacy", ""),
                        power_val,
                    )
                else:
                    # Fallback to dict if class unavailable
                    self.access_points[bssid] = ap

                if ap.get("hidden", False):
                    self.hidden_networks[bssid] = ap

        # Update clients
        if "clients" in results:
            for mac, client in results["clients"].items():
                if Client is not None:
                    try:
                        pwr_val = int(client.get("power", 0)) if str(client.get("power", "")).isdigit() else 0
                    except Exception:
                        pwr_val = 0
                    self.clients[mac] = Client(
                        mac,
                        client.get("bssid", ""),
                        pwr_val,
                    )
                else:
                    self.clients[mac] = client

                bssid_key = client.get("bssid", "")
                if bssid_key in self.client_stats:
                    self.client_stats[bssid_key].append(mac)
                else:
                    self.client_stats[bssid_key] = [mac]

        # Update WPS enabled networks
        if "wps_networks" in results:
            for bssid, network in results["wps_networks"].items():
                self.wps_enabled_networks[bssid] = network

        # Update channel statistics
        if "channel_data" in results:
            self.channel_stats = results["channel_data"]

        # Update encryption statistics
        if "access_points" in results:
            encryption_counts: Dict[str, int] = {}
            for _, ap in results["access_points"].items():
                enc = ap.get("privacy", "Unknown")
                encryption_counts[enc] = encryption_counts.get(enc, 0) + 1
            self.encryption_stats = encryption_counts


def analyze_network_security(self) -> Dict[str, Any]:
    """Analyze security of discovered networks.

    Returns:
        Dictionary containing security analysis results
    """
    analysis: Dict[str, Any] = {
        "vulnerable_networks": [],
        "encryption_distribution": {},
        "open_networks": [],
        "wps_networks": [],
        "hidden_networks": [],
        "client_connections": {},
        "channel_utilization": {},
    }

    encryption_counts: Dict[str, int] = {}
    for _, ap in self.access_points.items():
        encryption_counts[ap.encryption] = encryption_counts.get(ap.encryption, 0) + 1
    analysis["encryption_distribution"] = encryption_counts

    for bssid, ap in self.access_points.items():
        network = {
            "bssid": bssid,
            "ssid": ap.ssid,
            "channel": ap.channel,
            "encryption": ap.encryption,
            "vulnerabilities": [],
        }
        if ap.encryption in ("OPN", ""):
            network["vulnerabilities"].append("Open Network")
            analysis["open_networks"].append({
                "bssid": bssid,
                "ssid": ap.ssid,
                "channel": ap.channel,
            })
        if "WEP" in ap.encryption:
            network["vulnerabilities"].append("WEP Encryption")
        if bssid in self.wps_enabled_networks:
            network["vulnerabilities"].append("WPS Enabled")
            wps = self.wps_enabled_networks[bssid]
            analysis["wps_networks"].append({
                "bssid": bssid,
                "ssid": ap.ssid,
                "channel": ap.channel,
                "wps_version": wps.get("wps_version", ""),
                "wps_locked": wps.get("wps_locked", False),
            })
        if network["vulnerabilities"]:
            analysis["vulnerable_networks"].append(network)

    for bssid, ap in self.hidden_networks.items():
        analysis["hidden_networks"].append({
            "bssid": bssid,
            "channel": ap.get("channel", 0),
            "signal": ap.get("power", 0),
        })

    analysis["client_connections"] = self.client_stats
    analysis["channel_utilization"] = self.channel_stats

    return analysis


def generate_network_report(self, output_format: str = "text") -> str:
    """Generate a comprehensive report of network analysis.

    Args:
        output_format: Format of the report (text, json, html)

    Returns:
        Report in the specified format
    """
    analysis = self.analyze_network_security()

    if output_format == "json":
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "access_points": {bssid: {
                "ssid": ap.ssid,
                "channel": ap.channel,
                "encryption": ap.encryption,
                "signal": ap.signal,
            } for bssid, ap in self.access_points.items()},
            "clients": {mac: {
                "ap_bssid": client.ap_bssid,
                "signal": client.signal,
            } for mac, client in self.clients.items()},
            "analysis": analysis,
        }
        return json.dumps(report_data, indent=2)

    if output_format == "html":
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
        for bssid, ap in self.access_points.items():
            security_class = "secure"
            security_text = "Secure"
            for v in analysis["vulnerable_networks"]:
                if v["bssid"] == bssid:
                    security_class = "vulnerable"
                    security_text = ", ".join(v["vulnerabilities"])
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
            <th>SSID</th>
            <th>Signal</th>
        </tr>
"""
        for mac, client in self.clients.items():
            ap_ssid = self.access_points.get(client.ap_bssid).ssid if client.ap_bssid in self.access_points else ""
            html += f"""
        <tr>
            <td>{mac}</td>
            <td>{client.ap_bssid}</td>
            <td>{ap_ssid}</td>
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
        for network in analysis["vulnerable_networks"]:
            html += f"""
        <tr>
            <td>{network['bssid']}</td>
            <td>{network['ssid'] if network['ssid'] else "<hidden>"}</td>
            <td class="vulnerable">{', '.join(network['vulnerabilities'])}</td>
        </tr>"""
        html += """
    </table>
</body>
</html>
"""
        return html

    # Text report
    report = "WiFi Network Analysis Report\n"
    report += f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report += "Network Overview\n"
    report += "---------------\n"
    report += f"Total Networks: {len(self.access_points)}\n"
    report += f"Total Clients: {len(self.clients)}\n"
    report += f"Vulnerable Networks: {len(analysis['vulnerable_networks'])}\n"
    report += f"Hidden Networks: {len(analysis['hidden_networks'])}\n\n"

    report += "Access Points\n"
    report += "------------\n"
    report += f"{'BSSID':<18} {'SSID':<32} {'Ch':<4} {'Encryption':<10} {'Signal':<8} {'Security':<20}\n"
    for bssid, ap in self.access_points.items():
        security_text = "Secure"
        for v in analysis["vulnerable_networks"]:
            if v["bssid"] == bssid:
                security_text = ", ".join(v["vulnerabilities"])
                break
        report += f"{bssid:<18} {ap.ssid if ap.ssid else '<hidden>':<32} {ap.channel:<4} {ap.encryption:<10} {ap.signal:<8} {security_text:<20}\n"

    report += "\nClients\n"
    report += "-------\n"
    report += f"{'MAC':<18} {'Connected To':<20} {'SSID':<32} {'Signal':<8}\n"
    for mac, client in self.clients.items():
        ap_ssid = self.access_points.get(client.ap_bssid).ssid if client.ap_bssid in self.access_points else ""
        report += f"{mac:<18} {client.ap_bssid:<20} {ap_ssid:<32} {client.signal:<8}\n"

    report += "\nSecurity Analysis\n"
    report += "----------------\n"
    report += "Encryption Distribution:\n"
    for enc_type, count in analysis["encryption_distribution"].items():
        report += f"  {enc_type}: {count}\n"

    report += "\nVulnerable Networks:\n"
    for network in analysis["vulnerable_networks"]:
        report += f"  {network['bssid']} ({network['ssid'] if network['ssid'] else '<hidden>'}): {', '.join(network['vulnerabilities'])}\n"

    report += "\nHidden Networks:\n"
    for network in analysis["hidden_networks"]:
        report += f"  {network['bssid']} (Ch {network['channel']}): Signal {network['signal']}\n"

    return report


def start_network_analysis(self, scan_types: Optional[List[str]] = None, duration: int = 300) -> None:
    """Start comprehensive network analysis.

    Args:
        scan_types: List of scan types to perform
        duration: Total duration for analysis in seconds
    """
    if scan_types is None:
        scan_types = ["basic", "airodump", "wps", "channel_usage"]

    # Prevent overlap
    if getattr(self, "attack_thread", None) and self.attack_thread.is_alive():
        logging.warning("Network analysis already running")
        return

    logging.info(f"Starting comprehensive network analysis: {', '.join(scan_types)}")

    # (Re)initialize stop_event for new analysis
    if getattr(self, "stop_event", None) is None:
        self.stop_event = threading.Event()
    else:
        self.stop_event.clear()

    self.attack_thread = threading.Thread(target=self._run_network_analysis, args=(scan_types, duration))
    self.attack_thread.daemon = True
    self.attack_thread.start()

    with self.lock:
        # Use string type to avoid circular import on enum here
        self.attack_status = {
            "type": "network_scan",
            "status": "running",
            "start_time": time.time(),
            "duration": duration,
            "scan_types": scan_types,
        }


def _run_network_analysis(self, scan_types: List[str], duration: int) -> None:
    """Run network analysis in a background thread.

    Args:
        scan_types: List of scan types to perform
        duration: Total duration for analysis in seconds
    """
    try:
        per_scan = max(1, int(duration / max(1, len(scan_types))))
        for scan_type in scan_types:
            if self.stop_event.is_set():
                break
            with self.lock:
                self.attack_status["current_scan"] = scan_type
                self.attack_status["status"] = f"Scanning with {scan_type}"
            _ = self.advanced_scan_networks(scan_type=scan_type, duration=per_scan)
        # Generate reports
        report = self.generate_network_report()
        ts = time.strftime('%Y%m%d-%H%M%S')
        report_path = os.path.join(self.analysis_dir, f"network_report_{ts}.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        html_report = self.generate_network_report(output_format="html")
        html_report_path = os.path.join(self.analysis_dir, f"network_report_{ts}.html")
        with open(html_report_path, 'w', encoding='utf-8') as f:
            f.write(html_report)
        with self.lock:
            self.attack_status["status"] = "completed"
            self.attack_status["end_time"] = time.time()
            self.attack_status["report_path"] = report_path
            self.attack_status["html_report_path"] = html_report_path
    except Exception as e:
        logging.error(f"Error during network analysis: {e}")
        with self.lock:
            self.attack_status["status"] = "failed"
            self.attack_status["error"] = str(e)
