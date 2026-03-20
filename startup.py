# startup.py - Baccarat Bot Startup & Registration
# Handles: Machine GUID detection

import time
import requests
import winreg
import os
import json

from utils import find_resource
CONFIG_FILE = find_resource("config.json")


def get_machine_guid():
    """Get unique Machine GUID from the Windows registry."""
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return guid
    except Exception as e:
        print(f"[startup] Failed to get Machine GUID: {e}")
        return ""


def load_config():
    """Load config.json."""
    if not os.path.exists(CONFIG_FILE):
        print(f"[startup] {CONFIG_FILE} not found!")
        return {}
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def save_config(config):
    """Save config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def initialize_environment():
    """
    Main startup routine:
    1. Detect machine GUID and store in config.json
    """
    config = load_config()
    sb = config.get("supabase", {})

    # 1. Detect and store Machine GUID
    guid = get_machine_guid()
    if guid:
        print(f"[startup] Machine GUID: {guid}")
        if sb.get("hardware_id") != guid:
            sb["hardware_id"] = guid
            # Do NOT reset bot_id here; let bot_logic.py handle identifying/linking based on bot_id fallback
            config["supabase"] = sb
            save_config(config)
            print("[startup] New hardware detected. Local config updated.")

    return True


if __name__ == "__main__":
    print("=" * 50)
    print("  Baccarat Bot - Startup")
    print("=" * 50)
    initialize_environment()
    print("\nStartup check complete.")
    print("=" * 50)
