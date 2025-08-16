class NatashaApp:
    """Main application class for Natasha AI Penetration Testing Tool."""
    
    def __init__(self):
        """Initialize the application."""
        self.display = None
        self.ai_engine = None
        self.hid_emulator = None
        self.wifi_attack = None
        
        self.state = AppState.STARTUP
        self.previous_state = None
        self.menu_index = 0
        self.menu_start = 0
        self.menu_items = []
        self.config_params = {}
        self.attack_results = {}
        self.stop_event = threading.Event()
        
        # Button GPIO pins
        self.button_pins = {
            "up": 5,     # GPIO 5 (Pin 29)
            "down": 6,   # GPIO 6 (Pin 31)
            "select": 13, # GPIO 13 (Pin 33)
            "back": 19,  # GPIO 19 (Pin 35)
            "power": 26  # GPIO 26 (Pin 37)
        }
        
        # LED GPIO pins
        self.led_pins = {
            "red": 12,   # GPIO 12 (Pin 32)
            "green": 16  # GPIO 16 (Pin 36)
        }
        
        # Button states
        self.button_states = {pin: False for pin in self.button_pins.keys()}
        self.button_last_press = {pin: 0 for pin in self.button_pins.keys()}
        self.button_debounce_time = 0.2  # seconds
        
        # Initialize components
        self._init_components()
        
        # Set up signal handlers
