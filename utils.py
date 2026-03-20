import logging
import time
import os
import subprocess
import uuid
import sys
from datetime import datetime, timedelta
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

class Logger:
    def __init__(self, log_file='automation_log.txt'):
        self.log_file = log_file
        self.callback = None
        # Create log file if it doesn't exist
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                f.write(f"Log started at {time.ctime()}\n")
        else:
            # Clean old logs on startup
            self.cleanup_old_logs(days_to_keep=3)
    
    def set_callback(self, callback):
        """Sets a callback function for the logger."""
        self.callback = callback

    def log(self, message, level="INFO"):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] [{level}] {message}"
        
        # Print to console with color
        if level == "INFO":
            print(f"{Fore.CYAN}{formatted_message}{Style.RESET_ALL}")
        elif level == "WARNING":
            print(f"{Fore.YELLOW}{formatted_message}{Style.RESET_ALL}")
        elif level == "ERROR":
            print(f"{Fore.RED}{formatted_message}{Style.RESET_ALL}")
        elif level == "SUCCESS":
            print(f"{Fore.GREEN}{formatted_message}{Style.RESET_ALL}")
        else:
            print(formatted_message)
            
        # Write to file
        try:
            with open(self.log_file, 'a') as f:
                f.write(formatted_message + "\n")
        except:
            pass

        # Send to callback if exists
        if self.callback:
            try:
                self.callback(formatted_message)
            except:
                pass

    def cleanup_old_logs(self, days_to_keep=3):
        """Removes log entries older than the specified number of days."""
        if not os.path.exists(self.log_file):
            return

        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        new_lines = []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('[') and len(line) > 20:
                        try:
                            timestamp_str = line[1:20]
                            log_date = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            if log_date >= cutoff_date:
                                new_lines.append(line)
                        except ValueError:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
            
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        except Exception as e:
            # We don't want to fail the main app if cleanup fails
            print(f"Log cleanup failed: {e}")

import winreg

def get_hwid():
    """Generates a unique hardware ID (MachineGUID) for the current machine."""
    try:
        # Get unique Machine GUID from the Windows registry (consistent with startup.py)
        if os.name == 'nt':
            registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
            key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if guid:
                return guid
    except Exception:
        pass
    
    # Fallback to MAC address
    return str(uuid.getnode())

def find_resource(filename):
    """
    Finds a file in the current directory or the 'data' subdirectory.
    Returns the absolute path.
    """
    # 1. Check root directory
    if os.path.exists(filename):
        return os.path.abspath(filename)
    
    # 2. Check 'data' directory
    data_path = os.path.join("data", filename)
    if os.path.exists(data_path):
        return os.path.abspath(data_path)
    
    # 3. Check alongside executable if frozen
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        path1 = os.path.join(base_dir, filename)
        if os.path.exists(path1):
            return path1
        path2 = os.path.join(base_dir, "data", filename)
        if os.path.exists(path2):
            return path2

    return os.path.abspath(filename)

# Global logger instance
logger = Logger()
