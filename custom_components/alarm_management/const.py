"""Alarm Management constants."""

DOMAIN = "alarm_management"
VERSION = "0.7.0"
STORAGE_VERSION = 5
SIGNAL_UPDATED = f"{DOMAIN}_updated"
SERVICES = ("trigger_test", "acknowledge", "reset")
STATES = ("idle", "active", "acknowledged")
INPUT_CONFIG_KEY = "input_config"
INPUT_CONFIG_VERSION = 1
MAX_INPUTS = 10
ALARM_TYPES = ("house", "fire", "intrusion")
SIGNAL_INPUTS_UPDATED = f"{DOMAIN}_inputs_updated"
HISTORY_LIMIT = 100
RULE_CONFIG_KEY = "rule_config"
RULE_CONFIG_VERSION = 1
MAX_RULES = 30
OUTPUT_CONFIG_KEY = "output_config"
OUTPUT_CONFIG_VERSION = 1
MAX_OUTPUTS = 20
MAX_LONG_TEXT = 4096
