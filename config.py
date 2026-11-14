import json
import os
import sys

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".claude_widget_config.json")

DEFAULT_CONFIG = {
    "x": 100,
    "y": 100,
    "theme": "jarvis_cyan",  # Options: jarvis_cyan, jarvis_gold, dark_glass, light_glass
    "opacity": 0.85,
    "click_through": False,
    "startup": False,
    "shortcut": "Ctrl+Shift+C",
    "refresh_interval": 60
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass