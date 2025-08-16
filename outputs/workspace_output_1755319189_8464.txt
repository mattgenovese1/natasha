        self.state = AppState.MAIN_MENU
        self._update_display()
        
        # Set green LED to indicate ready
        self._set_led("green", True)
        
        # Main loop
        try:
            while True:
                # Process events
                time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received, shutting down")
            self._cleanup()
            sys.exit(0)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Natasha AI Penetration Testing Tool")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run the application
    app = NatashaApp()
    app.run()
