"""MITM UI helper methods bound to NatashaApp at runtime.
These functions are imported and attached to NatashaApp in main.py.
"""
import logging
import time
import threading


def _mitm_ui_refresh_loop(self):
    """Periodically refresh the MITM running screen while the state is RUNNING."""
    try:
        while True:
            try:
                if hasattr(self, "state_lock"):
                    with self.state_lock:
                        running = self.state == AppState.MITM_ATTACK_RUNNING
                else:
                    running = self.state == AppState.MITM_ATTACK_RUNNING
            except Exception:
                running = False
            if not running:
                break
            # Prefer thread-safe updater if available
            if hasattr(self, "_update_display_threadsafe"):
                self._update_display_threadsafe()
            else:
                self._update_display()
            time.sleep(1)
    except Exception as e:
        logging.debug(f"MITM UI refresh loop error: {e}")


def _start_mitm_ui_refresher(self):
    """Start a background thread to keep the MITM running UI updated."""
    try:
        t = getattr(self, "_mitm_ui_thread", None)
        if t and getattr(t, "is_alive", lambda: False)():
            return
        t = threading.Thread(target=_mitm_ui_refresh_loop, args=(self,))
        t.daemon = True
        self._mitm_ui_thread = t
        t.start()
    except Exception as e:
        logging.debug(f"MITM UI refresher start error: {e}")


def show_mitm_attack_menu(self):
        """Show the MITM attack menu."""
        self.menu_items = [
            "ARP Spoofing",
            "DNS Spoofing",
            "SSL Strip",
            "Packet Capture",
            "Session Hijacking",
            "Back"
        ]
        
        self.display.clear()
        self.display.draw_menu("MITM Attack Menu", self.menu_items, 
                             selected_index=self.menu_index, 
                             start_index=self.menu_start)
        self.display.draw_natasha_avatar(200, 30, expression="thinking")
        self.display.update()
    
def _handle_mitm_attack_menu_button(self, button):
        """Handle button press in MITM attack menu.
        
        Args:
            button: Button that was pressed
        """
        if button == "up":
            if self.menu_index > 0:
                self.menu_index -= 1
                if self.menu_index < self.menu_start:
                    self.menu_start = self.menu_index
        elif button == "down":
            if self.menu_index < len(self.menu_items) - 1:
                self.menu_index += 1
                if self.menu_index >= self.menu_start + 5:
                    self.menu_start += 1
        elif button == "select":
            selected_item = self.menu_items[self.menu_index]
            if selected_item == "Back":
                self.state = AppState.MAIN_MENU
                self.menu_index = 0
                self.menu_start = 0
            else:
                # Configure selected MITM attack
                self.config_params = {"attack_name": selected_item}
                self.state = AppState.MITM_ATTACK_CONFIG
                self.menu_index = 0
                self.menu_start = 0
        elif button == "back":
            self.state = AppState.MAIN_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()
    
def show_mitm_attack_config(self):
        """Show the MITM attack configuration screen."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        self.display.clear()
        self.display.draw_header(f"Configure {attack_name}")
        
        if attack_name == "ARP Spoofing":
            target_ip = self.config_params.get("target_ip", "192.168.1.100")
            gateway_ip = self.config_params.get("gateway_ip", "192.168.1.1")
            
            self.display.draw_text(10, 30, f"Target IP: {target_ip}", font=self.display.font_normal)
            self.display.draw_text(10, 50, f"Gateway IP: {gateway_ip}", font=self.display.font_normal)
            self.display.draw_text(10, 80, "Press SELECT to start attack", font=self.display.font_normal)
            self.display.draw_text(10, 100, "Press BACK to cancel", font=self.display.font_normal)
            
        elif attack_name == "DNS Spoofing":
            domain = self.config_params.get("domain", "example.com")
            redirect_ip = self.config_params.get("redirect_ip", "192.168.1.100")
            
            self.display.draw_text(10, 30, f"Domain: {domain}", font=self.display.font_normal)
            self.display.draw_text(10, 50, f"Redirect IP: {redirect_ip}", font=self.display.font_normal)
            self.display.draw_text(10, 80, "Press SELECT to start attack", font=self.display.font_normal)
            self.display.draw_text(10, 100, "Press BACK to cancel", font=self.display.font_normal)
            
        elif attack_name == "SSL Strip":
            port = self.config_params.get("port", "10000")
            
            self.display.draw_text(10, 30, f"Port: {port}", font=self.display.font_normal)
            self.display.draw_text(10, 80, "Press SELECT to start attack", font=self.display.font_normal)
            self.display.draw_text(10, 100, "Press BACK to cancel", font=self.display.font_normal)
            
        elif attack_name == "Packet Capture":
            filter_expr = self.config_params.get("filter_expr", "")
            duration = self.config_params.get("duration", "300")
            
            self.display.draw_text(10, 30, f"Filter: {filter_expr}", font=self.display.font_normal)
            self.display.draw_text(10, 50, f"Duration: {duration}s", font=self.display.font_normal)
            self.display.draw_text(10, 80, "Press SELECT to start capture", font=self.display.font_normal)
            self.display.draw_text(10, 100, "Press BACK to cancel", font=self.display.font_normal)
            
        elif attack_name == "Session Hijacking":
            target_ip = self.config_params.get("target_ip", "192.168.1.100")
            
            self.display.draw_text(10, 30, f"Target IP: {target_ip}", font=self.display.font_normal)
            self.display.draw_text(10, 80, "Press SELECT to start attack", font=self.display.font_normal)
            self.display.draw_text(10, 100, "Press BACK to cancel", font=self.display.font_normal)
        
        self.display.draw_natasha_avatar(200, 30, expression="thinking")
        self.display.update()
    
def handle_mitm_attack_config_button(self, button):
        """Handle button press in MITM attack configuration.
        
        Args:
            button: Button that was pressed
        """
        # Basic in-screen editing for common parameters using up/down
        attack_name = self.config_params.get("attack_name", "Unknown")

        if button == "up" or button == "down":
            try:
                if attack_name == "ARP Spoofing":
                    # Toggle simple presets
                    if button == "up":
                        self.config_params["target_ip"] = (
                            "192.168.1.100" if self.config_params.get("target_ip") != "192.168.1.100" else "192.168.1.50"
                        )
                    else:
                        self.config_params["gateway_ip"] = (
                            "192.168.1.1" if self.config_params.get("gateway_ip") != "192.168.1.1" else "192.168.0.1"
                        )
                elif attack_name == "DNS Spoofing":
                    if button == "up":
                        self.config_params["domain"] = (
                            "example.com" if self.config_params.get("domain") != "example.com" else "test.local"
                        )
                    else:
                        self.config_params["redirect_ip"] = (
                            "192.168.1.100" if self.config_params.get("redirect_ip") != "192.168.1.100" else "192.168.1.1"
                        )
                elif attack_name == "SSL Strip":
                    # Toggle port between 10000 and 8080
                    current = str(self.config_params.get("port", "10000"))
                    self.config_params["port"] = "8080" if current == "10000" else "10000"
                elif attack_name == "Packet Capture":
                    if button == "up":
                        cycle = ["", "tcp port 80", "udp port 53"]
                        cur = self.config_params.get("filter_expr", "")
                        self.config_params["filter_expr"] = cycle[(cycle.index(cur) + 1) % len(cycle)] if cur in cycle else cycle[0]
                    else:
                        cycle = ["60", "120", "300"]
                        cur = str(self.config_params.get("duration", "300"))
                        self.config_params["duration"] = cycle[(cycle.index(cur) + 1) % len(cycle)] if cur in cycle else cycle[0]
                elif attack_name == "Session Hijacking":
                    # Toggle target between two examples
                    self.config_params["target_ip"] = (
                        "192.168.1.100" if self.config_params.get("target_ip") != "192.168.1.100" else "192.168.1.50"
                    )
            except Exception as e:
                logging.debug(f"Config toggle error: {e}")
        elif button == "select":
            # Start the attack
            self.state = AppState.MITM_ATTACK_RUNNING
            self._start_mitm_attack()
        elif button == "back":
            self.state = AppState.MITM_ATTACK_MENU
            self.menu_index = 0
            self.menu_start = 0
        
        self._update_display()
    
def show_mitm_attack_running(self):
        """Show the MITM attack running screen."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        
        self.display.clear()
        self.display.draw_header(f"{attack_name} Running")
        
        # Show attack status
        status = self.attack_results.get("status", "Running")
        start_time = self.attack_results.get("start_time", time.time())
        elapsed = int(time.time() - start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        
        self.display.draw_text(10, 30, f"Status: {status}", font=self.display.font_normal)
        self.display.draw_text(10, 50, f"Time: {minutes:02d}:{seconds:02d}", font=self.display.font_normal)
        
        # Show attack-specific information
        if attack_name == "ARP Spoofing":
            target_ip = self.config_params.get("target_ip", "")
            gateway_ip = self.config_params.get("gateway_ip", "")
            self.display.draw_text(10, 70, f"Target: {target_ip}", font=self.display.font_normal)
            self.display.draw_text(10, 90, f"Gateway: {gateway_ip}", font=self.display.font_normal)
            
        elif attack_name == "DNS Spoofing":
            domain = self.config_params.get("domain", "")
            redirect_ip = self.config_params.get("redirect_ip", "")
            self.display.draw_text(10, 70, f"Domain: {domain}", font=self.display.font_normal)
            self.display.draw_text(10, 90, f"Redirect: {redirect_ip}", font=self.display.font_normal)
            
        elif attack_name == "Packet Capture":
            filter_expr = self.config_params.get("filter_expr", "")
            duration = self.config_params.get("duration", "")
            remaining = max(0, int(duration) - elapsed)
            self.display.draw_text(10, 70, f"Filter: {filter_expr}", font=self.display.font_normal)
            self.display.draw_text(10, 90, f"Remaining: {remaining}s", font=self.display.font_normal)
        
        self.display.draw_text(10, 110, "Press BACK to stop", font=self.display.font_normal)
        self.display.draw_natasha_avatar(200, 30, expression="success")
        self.display.update()
    
def handle_mitm_attack_running_button(self, button):
        """Handle button press while MITM attack is running.
        
        Args:
            button: Button that was pressed
        """
        if button == "back" or button == "select":
            # Stop the attack
            self._stop_mitm_attack()
            self.state = AppState.MITM_ATTACK_MENU
            self.menu_index = 0
            self.menu_start = 0
            self._update_display()
    
def start_mitm_attack(self):
        """Start the configured MITM attack."""
        attack_name = self.config_params.get("attack_name", "Unknown")
        logging.info(f"Starting MITM attack: {attack_name}")
        
        # Set red LED to indicate attack is running
        self._set_led("red", True)
        
        # Reset attack results
        self.attack_results = {}
        # Start periodic UI refresher
        _start_mitm_ui_refresher(self)
        
        # Start attack based on type
        if attack_name == "ARP Spoofing":
            target_ip = self.config_params.get("target_ip", "192.168.1.100")
            gateway_ip = self.config_params.get("gateway_ip", "192.168.1.1")
            
            if self.mitm_attack:
                success = self.mitm_attack.start_arp_spoof(target_ip, gateway_ip)
                if success:
                    self.attack_results = dict(self.mitm_attack.attack_status)
                else:
                    self.attack_results["status"] = "Failed"
                    self.attack_results["error"] = "Failed to start ARP spoofing attack"
            else:
                self.attack_results["status"] = "Failed"
                self.attack_results["error"] = "MITM attack module not available"
        
        elif attack_name == "DNS Spoofing":
            domain = self.config_params.get("domain", "example.com")
            redirect_ip = self.config_params.get("redirect_ip", "192.168.1.100")
            
            if self.mitm_attack:
                success = self.mitm_attack.start_dns_spoof(domain, redirect_ip)
                if success:
                    self.attack_results = dict(self.mitm_attack.attack_status)
                else:
                    self.attack_results["status"] = "Failed"
                    self.attack_results["error"] = "Failed to start DNS spoofing attack"
            else:
                self.attack_results["status"] = "Failed"
                self.attack_results["error"] = "MITM attack module not available"
        
        elif attack_name == "SSL Strip":
            port = int(self.config_params.get("port", "10000"))
            
            if self.mitm_attack:
                success = self.mitm_attack.start_ssl_strip(port)
                if success:
                    self.attack_results = dict(self.mitm_attack.attack_status)
                else:
                    self.attack_results["status"] = "Failed"
                    self.attack_results["error"] = "Failed to start SSL stripping attack"
            else:
                self.attack_results["status"] = "Failed"
                self.attack_results["error"] = "MITM attack module not available"
        
        elif attack_name == "Packet Capture":
            filter_expr = self.config_params.get("filter_expr", "")
            duration = int(self.config_params.get("duration", "300"))
            
            if self.mitm_attack:
                success = self.mitm_attack.start_packet_capture(filter_expr, duration)
                if success:
                    self.attack_results = dict(self.mitm_attack.attack_status)
                else:
                    self.attack_results["status"] = "Failed"
                    self.attack_results["error"] = "Failed to start packet capture"
            else:
                self.attack_results["status"] = "Failed"
                self.attack_results["error"] = "MITM attack module not available"
        
        elif attack_name == "Session Hijacking":
            target_ip = self.config_params.get("target_ip", "192.168.1.100")
            
            if self.mitm_attack:
                success = self.mitm_attack.start_session_hijack(target_ip)
                if success:
                    self.attack_results = dict(self.mitm_attack.attack_status)
                else:
                    self.attack_results["status"] = "Failed"
                    self.attack_results["error"] = "Failed to start session hijacking attack"
            else:
                self.attack_results["status"] = "Failed"
                self.attack_results["error"] = "MITM attack module not available"
    
def stop_mitm_attack(self):
        """Stop the running MITM attack."""
        logging.info("Stopping MITM attack")
        
        if self.mitm_attack:
            self.mitm_attack.stop_attack()
        
        # Turn off red LED
        self._set_led("red", False)