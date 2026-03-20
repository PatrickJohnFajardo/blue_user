import tkinter as tk
import sys
import json
from gui_app import BaccaratGUI
from login_gui import LoginScreen
from bot_logic import Bot
from utils import logger, find_resource
from startup import initialize_environment
from dependency_check import check_and_install_dependencies

class AppController:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw() # Hide initially
        
        # Run startup registration
        logger.log("Running startup registration...", "INFO")
        initialize_environment()
        
        # Check for Remembered Session
        auth_id = self.check_remembered_session()
        if auth_id:
            logger.log("Resuming remembered session...", "SUCCESS")
            self.start_main_app(auth_id)
        else:
            self.show_login()
            
        self.root.mainloop()

    def check_remembered_session(self):
        try:
            config_path = find_resource("config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    return config.get("supabase", {}).get("remembered_auth_id")
        except:
            pass
        return None

    def show_login(self):
        self.login_window = tk.Toplevel(self.root)
        self.login_window.title("BLUE LOG IN")
        self.login_screen = LoginScreen(self.login_window, self.start_main_app)
        
        # Ensure closing login closes entire app
        self.login_window.protocol("WM_DELETE_WINDOW", sys.exit)

    def start_main_app(self, auth_id=None):
        # Destroy login window if it exists
        if hasattr(self, 'login_window') and self.login_window:
            self.login_window.destroy()
        
        # Show Main GUI
        self.root.deiconify()
        self.app = BaccaratGUI(self.root, user_auth_id=auth_id, on_logout=self.handle_logout)

    def handle_logout(self):
        # Hide main app components if necessary (BaccaratGUI packs into root)
        # To be safe, we can clear the root or just withdraw it and show login
        self.root.withdraw()
        
        # Clear existing children from root to prevent overlapping on next login
        for widget in self.root.winfo_children():
            # Don't destroy the root itself!
            widget.destroy()
            
        self.show_login()

def main():
    if "--headless" in sys.argv:
        logger.log("Starting in HEADLESS mode...", "INFO")
        check_and_install_dependencies()
        initialize_environment()
        try:
            bot = Bot(base_bet=10, pattern_string="PPPB", reset_on_cycle=True)
            bot.start()
        except Exception as e:
            logger.log(f"Headless Mode Error: {e}", "ERROR")
            sys.exit(1)
    else:
        check_and_install_dependencies()
        AppController()

if __name__ == "__main__":
    main()
