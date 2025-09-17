            self._handle_main_menu_button(button)
        elif self.state == AppState.USB_ATTACK_MENU:
            self._handle_usb_attack_menu_button(button)
        elif self.state == AppState.WIFI_ATTACK_MENU:
            self._handle_wifi_attack_menu_button(button)
        elif self.state == AppState.USB_ATTACK_CONFIG:
            self._handle_usb_attack_config_button(button)
        elif self.state == AppState.WIFI_ATTACK_CONFIG:
            self._handle_wifi_attack_config_button(button)
        elif self.state == AppState.USB_ATTACK_RUNNING:
            self._handle_usb_attack_running_button(button)
        elif self.state == AppState.WIFI_ATTACK_RUNNING:
            self._handle_wifi_attack_running_button(button)
        elif self.state == AppState.SYSTEM_STATUS:
            self._handle_system_status_button(button)
        elif self.state == AppState.SETTINGS:
            self._handle_settings_button(button)
    
    def _handle_power_button(self):
        """Handle power button press."""
        # For now, just go to shutdown state
        self.state = AppState.SHUTDOWN
        self._update_display()
    
    def _handle_main_menu_button(self, button):
        """Handle button press in main menu.
        
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
                if self.menu_index >= self.menu_start + 5:  # 5 items visible at once
                    self.menu_start += 1
        elif button == "select":
            selected_item = self.menu_items[self.menu_index]
            if selected_item == "USB Attacks":
                self.state = AppState.USB_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            elif selected_item == "WiFi Attacks":
                self.state = AppState.WIFI_ATTACK_MENU
                self.menu_index = 0
                self.menu_start = 0
            elif selected_item == "System Status":
                self.state = AppState.SYSTEM_STATUS
            elif selected_item == "Settings":
                self.state = AppState.SETTINGS
                self.menu_index = 0
