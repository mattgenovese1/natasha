#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natasha AI Penetration Testing Tool
AI Engine for DuckyScript Generation

This module implements the AI engine responsible for generating DuckyScript payloads
based on target OS detection and attack parameters. It uses a lightweight model
to generate effective attack scripts tailored to different environments.
"""

import os
import time
import json
import random
import logging
import threading
from enum import Enum
from typing import Dict, List, Tuple, Optional, Union, Any

# Optional imports for machine learning components
try:
    import joblib
    from sklearn.feature_extraction.text import CountVectorizer
    ML_AVAILABLE = True
except ImportError:
    logging.info("Machine learning libraries not available. Some features will be limited.")
    ML_AVAILABLE = False

# Import learning component
try:
    from ai_learning import AILearning
    LEARNING_AVAILABLE = True
except ImportError:
    logging.info("AI Learning component not available. Learning features will be disabled.")
    LEARNING_AVAILABLE = False


class TargetOS(Enum):
    """Enumeration of target operating systems."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    ANDROID = "android"
    UNKNOWN = "unknown"


class AttackType(Enum):
    """Enumeration of attack types."""
    CREDENTIAL_HARVEST = "credential_harvest"
    KEYLOGGER = "keylogger"
    BACKDOOR = "backdoor"
    RECON = "recon"
    EXFILTRATION = "exfiltration"
    NETWORK_CONFIG = "network_config"
    CUSTOM = "custom"


class AIEngine:
    """AI Engine for generating DuckyScript payloads."""

    def __init__(self, model_dir: str = "models"):
        """Initialize the AI Engine.

        Args:
            model_dir: Directory containing model files
        """
        self.model_dir = model_dir
        self.templates: Dict[str, Dict[str, Any]] = {}
        self.models: Dict[str, Any] = {}
        self.vectorizers: Dict[str, Any] = {}
        self.lock = threading.Lock()
        self.os_detection_rules: Dict[TargetOS, Dict[str, Any]] = {}
        
        # Initialize learning component if available
        if LEARNING_AVAILABLE:
            self.learning_component = AILearning(model_dir=model_dir)
        else:
            self.learning_component = None

        # Load resources
        self._load_resources()

    def _load_resources(self):
        """Load templates, models, and other resources."""
        try:
            # Ensure model directory exists
            os.makedirs(self.model_dir, exist_ok=True)

            # Load templates (package defaults + user overrides)
            pkg_template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
            self._load_templates(pkg_template_path)

            # Load OS detection rules
            self._load_os_detection_rules()

            # Load ML models if available
            if ML_AVAILABLE:
                self._load_ml_models()

            logging.info("AI Engine resources loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load AI Engine resources: {e}")

    def _atomic_write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON atomically to avoid partial writes."""
        dir_path = os.path.dirname(path)
        os.makedirs(dir_path, exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)

    def _atomic_joblib_dump(self, obj: Any, path: str) -> None:
        """Atomically write joblib artifacts."""
        dir_path = os.path.dirname(path)
        os.makedirs(dir_path, exist_ok=True)
        tmp_path = path + ".tmp"
        try:
            joblib.dump(obj, tmp_path)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _load_templates(self, pkg_template_path: str):
        """Load DuckyScript templates from package dir (read-only) and user overlay (~/.natasha/templates).
        Writes and new files go to the user path. UNKNOWN OS is skipped.
        """
        try:
            user_base = os.path.join(os.path.expanduser("~"), "natasha", "templates")
            os.makedirs(user_base, exist_ok=True)

            for os_type in TargetOS:
                if os_type == TargetOS.UNKNOWN:
                    continue
                self.templates[os_type.value] = {}

                pkg_dir = os.path.join(pkg_template_path, os_type.value)
                user_dir = os.path.join(user_base, os_type.value)
                os.makedirs(user_dir, exist_ok=True)

                for attack_type in AttackType:
                    name = f"{attack_type.value}.json"
                    user_file = os.path.join(user_dir, name)
                    pkg_file = os.path.join(pkg_dir, name)

                    data: Dict[str, Any]
                    if os.path.exists(user_file):
                        with open(user_file, 'r') as f:
                            data = json.load(f)
                    elif os.path.exists(pkg_file):
                        with open(pkg_file, 'r') as f:
                            data = json.load(f)
                    else:
                        data = {
                            "metadata": {
                                "name": f"{attack_type.value.replace('_', ' ').title()} for {os_type.value.title()}",
                                "description": f"Template for {attack_type.value.replace('_', ' ')} attacks on {os_type.value}",
                                "version": "1.0",
                                "author": "Natasha AI"
                            },
                            "templates": []
                        }
                        self._atomic_write_json(user_file, data)

                    self.templates[os_type.value][attack_type.value] = data

            # Fallback templates: prefer user, then package, else generate and save to user
            user_fallback = os.path.join(user_base, "fallback.json")
            pkg_fallback = os.path.join(pkg_template_path, "fallback.json")
            if os.path.exists(user_fallback):
                with open(user_fallback, 'r') as f:
                    self.templates["fallback"] = json.load(f)
            elif os.path.exists(pkg_fallback):
                with open(pkg_fallback, 'r') as f:
                    self.templates["fallback"] = json.load(f)
            else:
                self.templates["fallback"] = {
                    "metadata": {
                        "name": "Fallback Templates",
                        "description": "Generic templates for when OS-specific ones are not available",
                        "version": "1.0",
                        "author": "Natasha AI"
                    },
                    "templates": self._generate_fallback_templates()
                }
                self._atomic_write_json(user_fallback, self.templates["fallback"])

            logging.info(f"Loaded templates for {len(self.templates)} operating systems")
        except Exception as e:
            logging.error(f"Failed to load templates: {e}")
            self.templates = {"fallback": {"templates": self._generate_fallback_templates()}}

    def _generate_fallback_templates(self) -> List[Dict[str, Any]]:
        """Generate basic fallback templates for common attacks.

        Returns:
            List of template dictionaries
        """
        return [
            {
                "name": "Basic Reconnaissance",
                "description": "Gather basic system information",
                "attack_type": "recon",
                "script": [
                    "REM Basic Reconnaissance Script",
                    "REM Generated by Natasha AI",
                    "DELAY 1000",
                    "GUI r",
                    "DELAY 500",
                    "STRING cmd",
                    "ENTER",
                    "DELAY 1000",
                    "STRING whoami & hostname & ipconfig /all",
                    "ENTER"
                ],
                "parameters": {}
            },
            {
                "name": "Simple Exfiltration",
                "description": "Exfiltrate system information to a file",
                "attack_type": "exfiltration",
                "script": [
                    "REM Simple Exfiltration Script",
                    "REM Generated by Natasha AI",
                    "DELAY 1000",
                    "GUI r",
                    "DELAY 500",
                    "STRING cmd",
                    "ENTER",
                    "DELAY 1000",
                    "STRING whoami > %TEMP%\\info.txt & hostname >> %TEMP%\\info.txt & ipconfig /all >> %TEMP%\\info.txt",
                    "ENTER"
                ],
                "parameters": {}
            }
        ]

    def _load_os_detection_rules(self):
        """Load rules for OS detection from USB enumeration responses."""
        # These are simplified rules for demonstration
        self.os_detection_rules = {
            TargetOS.WINDOWS: {
                "usb_ids": ["VID_045E&PID_0291", "VID_045E&PID_0750"],  # Microsoft USB IDs
                "descriptors": ["Windows", "Microsoft"],
                "enumeration_speed": (50, 200)  # ms range
            },
            TargetOS.MACOS: {
                "usb_ids": ["VID_05AC&PID_024F", "VID_05AC&PID_0290"],  # Apple USB IDs
                "descriptors": ["Apple", "Mac"],
                "enumeration_speed": (20, 100)  # ms range
            },
            TargetOS.LINUX: {
                "usb_ids": [],  # Various Linux distributions
                "descriptors": ["Linux", "Ubuntu", "Debian", "Fedora"],
                "enumeration_speed": (30, 150)  # ms range
            },
            TargetOS.ANDROID: {
                "usb_ids": ["VID_18D1"],  # Google USB IDs
                "descriptors": ["Android", "Google"],
                "enumeration_speed": (40, 180)  # ms range
            }
        }

    def _load_ml_models(self):
        """Load machine learning models for script generation and OS detection."""
        if not ML_AVAILABLE:
            return

        try:
            model_files = {
                "os_detector": os.path.join(self.model_dir, "os_detector.joblib"),
                "script_generator": os.path.join(self.model_dir, "script_generator.joblib"),
                "vectorizer": os.path.join(self.model_dir, "vectorizer.joblib"),
            }

            # Load existing models or create placeholders
            for model_name, model_path in model_files.items():
                if os.path.exists(model_path):
                    if model_name == "vectorizer":
                        self.vectorizers["vectorizer"] = joblib.load(model_path)
                        logging.info("Loaded vectorizer")
                    else:
                        self.models[model_name] = joblib.load(model_path)
                        logging.info(f"Loaded model: {model_name}")
                else:
                    logging.info(f"Model not found (optional): {model_path}")
                    if model_name == "vectorizer":
                        self.vectorizers["vectorizer"] = CountVectorizer()

            logging.info("Machine learning components loaded")
        except Exception as e:
            logging.error(f"Failed to load ML models: {e}")

    def detect_target_os(self, usb_enumeration_data: Dict[str, Any] = None) -> TargetOS:
        """Detect the target operating system based on USB enumeration data.

        Args:
            usb_enumeration_data: USB enumeration data (if available)

        Returns:
            Detected target OS
        """
        if usb_enumeration_data is None:
            # If no data provided, return UNKNOWN
            return TargetOS.UNKNOWN

        # Extract relevant features from USB enumeration data
        usb_id = usb_enumeration_data.get("usb_id", "")
        descriptor = usb_enumeration_data.get("descriptor", "")
        enumeration_speed = usb_enumeration_data.get("enumeration_speed", 0)

        # Check against rules for each OS
        for os_type, rules in self.os_detection_rules.items():
            # Check USB ID
            for id_pattern in rules["usb_ids"]:
                if id_pattern in usb_id:
                    return os_type

            # Check descriptor strings
            for desc_pattern in rules["descriptors"]:
                if desc_pattern.lower() in descriptor.lower():
                    return os_type

            # Check enumeration speed range
            speed_range = rules["enumeration_speed"]
            if speed_range[0] <= enumeration_speed <= speed_range[1]:
                # This is a weak signal, so we'll just consider it a hint
                logging.debug(f"Enumeration speed {enumeration_speed}ms suggests {os_type.value}")

        # If no match found, try ML-based detection if available
        if ML_AVAILABLE and "os_detector" in self.models:
            try:
                # Prepare features for ML model
                features = [
                    usb_id,
                    descriptor,
                    str(enumeration_speed)
                ]

                # Make prediction
                prediction = self.models["os_detector"].predict([" ".join(features)])
                predicted_os = prediction[0]

                # Convert prediction to TargetOS enum
                for os_type in TargetOS:
                    if os_type.value == predicted_os:
                        return os_type
            except Exception as e:
                logging.error(f"ML-based OS detection failed: {e}")

        # Default to UNKNOWN if no match found
        return TargetOS.UNKNOWN

    def generate_duckyscript(
        self,
        attack_type: AttackType,
        target_os: TargetOS = TargetOS.UNKNOWN,
        parameters: Dict[str, Any] = None,
    ) -> str:
        """Generate a DuckyScript payload for the specified attack type and target OS.

        Args:
            attack_type: Type of attack to generate
            target_os: Target operating system
            parameters: Additional parameters for script generation

        Returns:
            Generated DuckyScript as a string
        """
        if parameters is None:
            parameters = {}

        with self.lock:
            # Select appropriate template
            template = self._select_template(attack_type, target_os, parameters)

            if template is None:
                logging.warning(f"No template found for {attack_type.value} on {target_os.value}")
                return self._generate_fallback_script(attack_type, target_os, parameters)

            # Generate script from template
            script = self._generate_from_template(template, parameters)

            # Add metadata and comments
            script = self._add_metadata(script, attack_type, target_os, parameters)

            # Optimize script (optionally merge STRING commands)
            script = self._optimize_script(script, merge_strings=parameters.get('merge_strings', False))

            return script

    def _select_template(
        self,
        attack_type: AttackType,
        target_os: TargetOS,
        parameters: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Select the most appropriate template for the attack.

        Args:
            attack_type: Type of attack
            target_os: Target operating system
            parameters: Additional parameters

        Returns:
            Selected template dictionary or None if no suitable template found
        """
        # Try to find a specific template for the target OS and attack type
        if target_os.value in self.templates and attack_type.value in self.templates[target_os.value]:
            templates = self.templates[target_os.value][attack_type.value].get("templates", [])
            if templates:
                # Find the best matching template based on parameters
                best_template = self._find_best_template(templates, parameters)
                if best_template:
                    return best_template

        # Fall back to generic template for the attack type
        if "fallback" in self.templates:
            fallback_templates = self.templates["fallback"].get("templates", [])
            matching_templates = [t for t in fallback_templates if t.get("attack_type") == attack_type.value]
            # Only use fallback JSON templates for Windows; otherwise rely on OS-aware fallback generator
            if target_os == TargetOS.WINDOWS and matching_templates:
                return self._find_best_template(matching_templates, parameters)

        return None

    def _find_best_template(
        self,
        templates: List[Dict[str, Any]],
        parameters: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Find the best matching template based on parameters.

        Args:
            templates: List of template dictionaries
            parameters: Parameters to match against

        Returns:
            Best matching template or random template if no good match
        """
        if not templates:
            return None

        # If only one template, return it
        if len(templates) == 1:
            return templates[0]

        # Score templates based on parameter match
        scored_templates: List[Tuple[Dict[str, Any], int]] = []
        for template in templates:
            score = 0
            template_params = template.get("parameters", {})

            # Score based on parameter match
            for param_name, param_value in parameters.items():
                if param_name in template_params:
                    template_value = template_params[param_name]

                    # Exact match
                    if template_value == param_value:
                        score += 10
                    # Partial match for strings
                    elif isinstance(param_value, str) and isinstance(template_value, str):
                        if param_value.lower() in template_value.lower() or template_value.lower() in param_value.lower():
                            score += 5
                    # Range match for numbers
                    elif isinstance(param_value, (int, float)) and isinstance(template_value, (int, float)):
                        if abs(param_value - template_value) / max(1, abs(template_value)) < 0.2:  # Within 20%
                            score += 5

            scored_templates.append((template, score))

        # Sort by score (descending)
        scored_templates.sort(key=lambda x: x[1], reverse=True)

        # Return the highest scoring template, or a random one if all scores are 0
        if scored_templates[0][1] > 0:
            return scored_templates[0][0]
        else:
            return random.choice(templates)

    def _generate_from_template(
        self,
        template: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> str:
        """Generate a DuckyScript from a template.

        Args:
            template: Template dictionary
            parameters: Parameters for script generation

        Returns:
            Generated DuckyScript as a string
        """
        # Get the base script from the template
        script_lines = template.get("script", [])

        # Process each line for parameter substitution
        processed_lines: List[str] = []
        for line in script_lines:
            # Handle parameter substitution for both {$name} and {name}
            for param_name, param_value in parameters.items():
                ph1 = f"{{$" + str(param_name) + "}}"
                ph2 = f"{{{param_name}}}"
                val = str(param_value)
                if ph1 in line:
                    line = line.replace(ph1, val)
                if ph2 in line:
                    line = line.replace(ph2, val)

            processed_lines.append(line)

        # Join lines into a single script
        return "\n".join(processed_lines)

    def _add_metadata(
        self,
        script: str,
        attack_type: AttackType,
        target_os: TargetOS,
        parameters: Dict[str, Any],
    ) -> str:
        """Add metadata and comments to the script.

        Args:
            script: Generated script
            attack_type: Type of attack
            target_os: Target operating system
            parameters: Script parameters

        Returns:
            Script with added metadata
        """
        # Create metadata header
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        metadata_lines = [
            "REM ==============================================",
            "REM Natasha AI Penetration Testing Tool",
            f"REM Attack Type: {attack_type.value.replace('_', ' ').title()}",
            f"REM Target OS: {target_os.value.title()}",
            f"REM Generated: {timestamp}",
            "REM ==============================================",
        ]

        # Add parameter information
        if parameters:
            metadata_lines.append("REM Parameters:")
            for param_name, param_value in parameters.items():
                metadata_lines.append(f"REM   - {param_name}: {param_value}")
            metadata_lines.append("REM ==============================================")

        # Add educational note
        metadata_lines.extend([
            "REM NOTE: This script is generated for educational purposes",
            "REM and authorized penetration testing only.",
            "REM ==============================================",
            "",
        ])

        # Combine metadata with script
        return "\n".join(metadata_lines) + "\n" + script

    def _optimize_script(self, script: str, merge_strings: bool = False) -> str:
        """Optimize the generated script for better performance.

        Args:
            script: Generated script
            merge_strings: If True, merge consecutive STRING commands

        Returns:
            Optimized script
        """
        lines = script.split("\n")
        optimized_lines: List[str] = []

        # Process lines
        i = 0
        while i < len(lines):
            current_line = lines[i].strip()

            # Skip empty lines
            if not current_line:
                i += 1
                continue

            # Combine consecutive STRING commands (optional)
            if merge_strings and current_line.startswith("STRING ") and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith("STRING "):
                    current_text = current_line[7:]
                    next_text = next_line[7:]
                    combined_line = f"STRING {current_text} {next_text}"
                    lines[i + 1] = combined_line
                    i += 1
                    continue

            # Optimize DELAY commands
            if current_line.startswith("DELAY "):
                try:
                    delay_value = int(current_line[6:])
                    # Minimum delay of 20ms
                    if delay_value < 20:
                        optimized_lines.append("DELAY 20")
                    else:
                        optimized_lines.append(current_line)
                except ValueError:
                    optimized_lines.append(current_line)
            else:
                optimized_lines.append(current_line)

            i += 1

        return "\n".join(optimized_lines)

    def _generate_fallback_script(
        self,
        attack_type: AttackType,
        target_os: TargetOS,
        parameters: Dict[str, Any],
    ) -> str:
        """Generate a fallback script when no suitable template is found.

        Args:
            attack_type: Type of attack
            target_os: Target operating system
            parameters: Script parameters

        Returns:
            Fallback script as a string
        """
        # Basic script structure
        script_lines: List[str] = [
            "REM Fallback script generated by Natasha AI",
            f"REM Attack Type: {attack_type.value}",
            f"REM Target OS: {target_os.value}",
            "DELAY 1000",
        ]

        # Add OS-specific shell/launcher commands
        if target_os == TargetOS.WINDOWS:
            script_lines.extend([
                "GUI r",
                "DELAY 500",
                "STRING cmd",
                "ENTER",
                "DELAY 800",
            ])
        elif target_os == TargetOS.MACOS:
            script_lines.extend([
                "GUI SPACE",
                "DELAY 400",
                "STRING terminal",
                "DELAY 400",
                "ENTER",
                "DELAY 800",
            ])
        elif target_os == TargetOS.LINUX:
            script_lines.extend([
                "CTRL ALT t",
                "DELAY 800",
            ])
        else:
            # Generic minimal
            script_lines.extend([
                "REM Generic environment",
            ])

        # Add attack-specific commands (benign/demo only)
        if attack_type == AttackType.RECON:
            if target_os == TargetOS.WINDOWS:
                script_lines.extend([
                    "STRING echo === System Info ===",
                    "ENTER",
                    "STRING systeminfo",
                    "ENTER",
                ])
            elif target_os == TargetOS.MACOS:
                script_lines.extend([
                    "STRING echo '=== System Info ==='",
                    "ENTER",
                    "STRING system_profiler SPHardwareDataType",
                    "ENTER",
                ])
            elif target_os == TargetOS.LINUX:
                script_lines.extend([
                    "STRING echo '=== System Info ==='",
                    "ENTER",
                    "STRING uname -a && lsb_release -a",
                    "ENTER",
                ])
        elif attack_type == AttackType.EXFILTRATION:
            # Safe demo: save basic info locally only (no transmission)
            if target_os == TargetOS.WINDOWS:
                script_lines.extend([
                    "STRING set OUT=%TEMP%\\natasha_demo.txt",
                    "ENTER",
                    "STRING echo Natasha Demo > %OUT%",
                    "ENTER",
                    "STRING echo User: %USERNAME% >> %OUT%",
                    "ENTER",
                    "STRING echo Host: %COMPUTERNAME% >> %OUT%",
                    "ENTER",
                    "STRING ipconfig /all >> %OUT%",
                    "ENTER",
                ])
            elif target_os == TargetOS.MACOS:
                script_lines.extend([
                    "STRING OUT=~/natasha_demo.txt; echo 'Natasha Demo' > \"$OUT\"",
                    "ENTER",
                    "STRING echo \"User: $(whoami)\" >> \"$OUT\"",
                    "ENTER",
                    "STRING echo \"Host: $(hostname)\" >> \"$OUT\"",
                    "ENTER",
                    "STRING ifconfig >> \"$OUT\"",
                    "ENTER",
                ])
            elif target_os == TargetOS.LINUX:
                script_lines.extend([
                    "STRING OUT=~/natasha_demo.txt; echo 'Natasha Demo' > \"$OUT\"",
                    "ENTER",
                    "STRING echo \"User: $(whoami)\" >> \"$OUT\"",
                    "ENTER",
                    "STRING echo \"Host: $(hostname)\" >> \"$OUT\"",
                    "ENTER",
                    "STRING ip addr >> \"$OUT\"",
                    "ENTER",
                ])
        elif attack_type == AttackType.NETWORK_CONFIG:
            # Show local network configuration
            if target_os == TargetOS.WINDOWS:
                script_lines.extend([
                    "STRING ipconfig /all",
                    "ENTER",
                ])
            elif target_os == TargetOS.MACOS:
                script_lines.extend([
                    "STRING ifconfig",
                    "ENTER",
                ])
            elif target_os == TargetOS.LINUX:
                script_lines.extend([
                    "STRING ip addr",
                    "ENTER",
                ])
        elif attack_type == AttackType.CUSTOM:
            # Generic custom demo action
            if target_os == TargetOS.WINDOWS:
                script_lines.extend([
                    "STRING echo Custom demo executed",
                    "ENTER",
                ])
            else:
                script_lines.extend([
                    "STRING echo 'Custom demo executed'",
                    "ENTER",
                ])
        else:
            # For other attack types without safe fallback, just print a banner
            if target_os == TargetOS.WINDOWS:
                script_lines.extend(["STRING echo Natasha fallback script", "ENTER"])
            else:
                script_lines.extend(["STRING echo 'Natasha fallback script'", "ENTER"])

        return "\n".join(script_lines)

    def learn_from_feedback(
        self,
        script: str,
        success: bool,
        attack_type: AttackType,
        target_os: TargetOS,
        parameters: Dict[str, Any] = None,
        user_feedback: Dict[str, Any] = None,
        execution_time: float = None,
    ) -> None:
        """Learn from feedback on generated scripts.

        Args:
            script: The script that was executed
            success: Whether the script was successful
            attack_type: Type of attack attempted
            target_os: Target operating system
            parameters: Parameters used for script generation
            user_feedback: Additional user feedback
            execution_time: Time taken to execute the script
        """
        if not LEARNING_AVAILABLE or self.learning_component is None:
            logging.warning("Learning component not available. Cannot learn from feedback.")
            return

        try:
            self.learning_component.record_feedback(
                script=script,
                success=success,
                attack_type=attack_type.value,
                target_os=target_os.value,
                parameters=parameters or {},
                user_feedback=user_feedback,
                execution_time=execution_time
            )
            logging.info(f"Feedback recorded for {attack_type.value} on {target_os.value} - Success: {success}")
        except Exception as e:
            logging.error(f"Failed to record feedback: {e}")

    def process_feedback(self) -> None:
        """Process collected feedback to improve script generation."""
        if not LEARNING_AVAILABLE or self.learning_component is None:
            logging.warning("Learning component not available. Cannot process feedback.")
            return
        
        try:
            self.learning_component.process_feedback()
            logging.info("Feedback processing completed")
        except Exception as e:
            logging.error(f"Failed to process feedback: {e}")

    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning statistics.
        
        Returns:
            Dictionary with learning statistics
        """
        if not LEARNING_AVAILABLE or self.learning_component is None:
            return {
                "learning_available": False,
                "message": "Learning component not available"
            }
        
        try:
            return self.learning_component.get_learning_stats()
        except Exception as e:
            logging.error(f"Failed to get learning stats: {e}")
            return {
                "learning_available": True,
                "error": str(e)
            }

    def save_models(self) -> None:
        """Save trained models to disk."""
        if not ML_AVAILABLE:
            return

        try:
            # Ensure model directory exists
            os.makedirs(self.model_dir, exist_ok=True)

            # Save models (atomic)
            for model_name, model in self.models.items():
                model_path = os.path.join(self.model_dir, f"{model_name}.joblib")
                self._atomic_joblib_dump(model, model_path)
                logging.info(f"Saved model: {model_name}")

            # Save vectorizers (atomic)
            for vec_name, vec in self.vectorizers.items():
                vec_path = os.path.join(self.model_dir, f"{vec_name}.joblib")
                self._atomic_joblib_dump(vec, vec_path)
                logging.info(f"Saved vectorizer: {vec_name}")
        except Exception as e:
            logging.error(f"Failed to save models: {e}")

    def generate_custom_script(
        self,
        script_description: str,
        target_os: TargetOS = TargetOS.UNKNOWN,
    ) -> str:
        """Generate a custom script based on a natural language description.

        Args:
            script_description: Natural language description of the desired script
            target_os: Target operating system

        Returns:
            Generated DuckyScript as a string
        """
        # This is a placeholder for a more sophisticated implementation
        # In a real implementation, this would use NLP to understand the description
        # and generate an appropriate script

        logging.info(f"Generating custom script for: {script_description}")

        # Extract key information from description
        keywords = {
            "password": AttackType.CREDENTIAL_HARVEST,
            "credential": AttackType.CREDENTIAL_HARVEST,
            "keylog": AttackType.KEYLOGGER,
            "backdoor": AttackType.BACKDOOR,
            "information": AttackType.RECON,
            "recon": AttackType.RECON,
            "exfil": AttackType.EXFILTRATION,
            "network": AttackType.NETWORK_CONFIG,
        }

        # Determine attack type based on keywords
        attack_type = AttackType.CUSTOM
        for keyword, att_type in keywords.items():
            if keyword.lower() in script_description.lower():
                attack_type = att_type
                break

        # Extract parameters from description (placeholder)
        parameters: Dict[str, Any] = {}

        # Generate script using the determined attack type
        return self.generate_duckyscript(attack_type, target_os, parameters)


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize the AI Engine
    ai_engine = AIEngine()

    # Test OS detection
    test_data = {
        "usb_id": "VID_045E&PID_0291",
        "descriptor": "Microsoft Keyboard",
        "enumeration_speed": 120,
    }
    detected_os = ai_engine.detect_target_os(test_data)
    print(f"Detected OS: {detected_os.value}")

    # Generate a script for credential harvesting on Windows
    script = ai_engine.generate_duckyscript(
        AttackType.CREDENTIAL_HARVEST,
        TargetOS.WINDOWS,
        {"browser": "chrome", "exfil_method": "file"},
    )
    print("\nGenerated Script:")
    print(script)

    # Generate a custom script
    custom_script = ai_engine.generate_custom_script(
        "Extract saved passwords from Chrome and save to a file",
        TargetOS.WINDOWS,
    )
    print("\nCustom Script:")
    print(custom_script)
