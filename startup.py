# startup.py - Baccarat Bot Startup & Registration
# Handles: Machine GUID detection, ngrok tunnel, Supabase unit registration

import subprocess
import time
import requests
import winreg
import os
import json

CONFIG_FILE = "config.json"
ngrok_process = None


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


def start_ngrok(port=8000):
    """Start ngrok tunnel and return the public HTTPS URL."""
    global ngrok_process

    print("[startup] Starting ngrok...")
    try:
        ngrok_process = subprocess.Popen(
            ["ngrok", "http", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print("[startup] ngrok not found. Skipping tunnel setup.")
        return ""

    time.sleep(3)

    try:
        response = requests.get("http://localhost:4040/api/tunnels")
        if response.status_code == 200:
            for tunnel in response.json().get("tunnels", []):
                if tunnel.get("proto") == "https":
                    return tunnel.get("public_url")
    except Exception as e:
        print(f"[startup] ngrok tunnel error: {e}")

    return ""


def stop_ngrok():
    """Terminate the ngrok process."""
    global ngrok_process
    if ngrok_process:
        ngrok_process.terminate()
        print("[startup] ngrok stopped.")


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


def register_unit(guid, ngrok_url=""):
    """Register or update this machine in the Supabase 'units' table."""
    config = load_config()
    sb = config.get("supabase", {})
    supabase_url = sb.get("url")
    supabase_key = sb.get("key")

    if not supabase_url or not supabase_key:
        print("[startup] Supabase credentials not set — skipping unit registration.")
        return

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }

    # 1. Check if a unit with this GUID already exists
    try:
        resp = requests.get(
            f"{supabase_url}/rest/v1/units",
            params={"guid": f"eq.{guid}", "select": "id,unit_name"},
            headers=headers,
            timeout=5,
        )
        existing = resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"[startup] Error checking existing unit: {e}")
        return

    payload = {}
    if ngrok_url:
        payload["api_base_url"] = ngrok_url
    payload["status"] = "connected"

    # 2a. PATCH if existing row found
    if existing:
        unit_id = existing[0]["id"]
        unit_name = existing[0].get("unit_name", "Unknown")
        try:
            resp = requests.patch(
                f"{supabase_url}/rest/v1/units",
                params={"id": f"eq.{unit_id}"},
                json=payload,
                headers={**headers, "Prefer": "return=representation"},
                timeout=5,
            )
            if resp.status_code in (200, 204):
                print(f"[startup] Unit updated: {unit_name} (id={unit_id})")
            else:
                print(f"[startup] Unit update failed [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"[startup] Error updating unit: {e}")

    # 2b. POST if no existing row
    else:
        try:
            resp = requests.post(
                f"{supabase_url}/rest/v1/units",
                json={**payload, "guid": guid},
                headers={**headers, "Prefer": "return=representation"},
                timeout=5,
            )
            if resp.status_code in (200, 201):
                new_unit = resp.json()[0] if resp.json() else {}
                print(f"[startup] New unit registered (id={new_unit.get('id', '?')})")
            else:
                print(f"[startup] Unit registration failed [{resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"[startup] Error registering unit: {e}")


def initialize_environment():
    """
    Main startup routine:
    1. Detect machine GUID and store in config.json
    2. Start ngrok tunnel (if available)
    3. Register this machine in Supabase 'units' table
    """
    config = load_config()
    sb = config.get("supabase", {})

    # 1. Detect and store Machine GUID
    guid = get_machine_guid()
    if guid:
        print(f"[startup] Machine GUID: {guid}")
        if sb.get("hardware_id") != guid:
            sb["hardware_id"] = guid
            config["supabase"] = sb
            save_config(config)
            print("[startup] Updated hardware_id in config.json")

    # 2. Start ngrok (optional)
    ngrok_url = start_ngrok()
    if ngrok_url:
        print(f"[startup] ngrok URL: {ngrok_url}")

    # 3. Register the unit in Supabase
    if guid:
        register_unit(guid, ngrok_url)

    return ngrok_url


if __name__ == "__main__":
    print("=" * 50)
    print("  Baccarat Bot - Startup & Registration")
    print("=" * 50)
    url = initialize_environment()
    if url:
        print(f"\nBot is accessible at: {url}")
    else:
        print("\nBot registered (no ngrok tunnel).")
    print("=" * 50)
