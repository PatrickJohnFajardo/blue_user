import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import os
import sys
from bot_logic import Bot
from utils import logger
import calibration
from PIL import Image, ImageTk


class BaccaratGUI:
    def __init__(self, root, user_auth_id=None, on_logout=None):
        self.root = root
        self.user_auth_id = user_auth_id
        self.on_logout = on_logout
        self.root.title("BLUE")
        self.root.geometry("325x150") # Reduced height for compact view
        self.root.configure(bg="#1a1a1a")
        self.root.resizable(False, False)
        
        # Colors
        self.dark_blue = "#1e3a8a" # Deep dark blue for headers
        self.bg_dark = "#1a1a1a"
        self.text_blue = "#3498db"
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        self.is_running = False
        self.is_calibrating = False
        self.calib_event = threading.Event()
        
        # Initialize bot on startup
        self.initialize_bot_instance()
        
        self.setup_custom_menu()
        self.setup_ui()
        self.bind_keys()
        
        # Handle window closing to stop bot on website
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Connect logger to GUI
        logger.set_callback(self.log_to_gui)
        
        # Automatically Start Bot Thread after login
        self.start_bot_thread()
        self.update_info_loop()
        self.update_ui_fast_loop() # Start the 1s UI clock

    def configure_styles(self):
        self.style.configure("TLabel", background=self.bg_dark, foreground="#ecf0f1", font=("Helvetica", 10))
        self.style.configure("TFrame", background=self.bg_dark)
        self.style.configure("Header.TLabel", background=self.bg_dark, foreground=self.text_blue, font=("Helvetica", 18, "bold"))
        self.style.configure("Status.TLabel", background=self.bg_dark, foreground=self.text_blue, font=("Helvetica", 12, "bold"))

    def setup_custom_menu(self):
        # Replacing native menu with a dark blue custom menu bar
        self.menu_bar = tk.Frame(self.root, bg=self.dark_blue, height=30)
        self.menu_bar.pack(side=tk.TOP, fill=tk.X)
        self.menu_bar.pack_propagate(False)
        
        # Dropdown logic
        self.menu_btn = tk.Menubutton(
            self.menu_bar, text="≡ Menu", 
            bg=self.dark_blue, fg="white", 
            activebackground=self.text_blue, 
            activeforeground="white",
            relief="flat", font=("Helvetica", 10, "bold"),
            padx=10
        )
        self.menu_btn.pack(side=tk.LEFT)
        
        self.bot_menu = tk.Menu(self.menu_btn, tearoff=0, bg=self.bg_dark, fg="white", activebackground=self.text_blue)
        self.menu_btn.config(menu=self.bot_menu)
        
        self.bot_menu.add_command(label="Run Calibration", command=self.start_calibration)
        self.bot_menu.add_command(label="Logs", command=self.toggle_logs)
        self.bot_menu.add_separator()
        self.bot_menu.add_command(label="Logout", command=self.handle_logout)
        self.bot_menu.add_separator()
        self.bot_menu.add_command(label="Exit", command=self.on_closing)

    def bind_keys(self):
        self.root.bind("<space>", self.on_space_pressed)

    def on_space_pressed(self, event):
        if self.is_calibrating:
            self.trigger_next_step()

    def setup_ui(self):
        # Main Container
        self.main_frame = tk.Frame(self.root, bg=self.bg_dark)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        # Header Row
        header_frame = tk.Frame(self.main_frame, bg=self.bg_dark)
        header_frame.pack(fill=tk.X)
        
        self.unit_name_label = ttk.Label(header_frame, text=self.bot.bot_name if self.bot else "Unit", style="Header.TLabel")
        self.unit_name_label.pack(side=tk.LEFT)
        
        # Transparent Status Bar (just text)
        self.status_frame = tk.Frame(self.main_frame, bg=self.bg_dark)
        self.status_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.status_label = ttk.Label(self.status_frame, text="INITIALIZING...", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT)
        
        # Calibration Progress Button (Hidden by default)
        self.calib_frame = tk.Frame(self.main_frame, bg=self.bg_dark)
        self.next_btn = ttk.Button(self.calib_frame, text="NEXT CALIBRATION STEP", command=self.trigger_next_step, state=tk.DISABLED)
        self.next_btn.pack(pady=10)
        
        # Log Section
        self.log_frame = tk.Frame(self.main_frame, bg=self.bg_dark)
        # Hidden by default
        
        self.log_display = scrolledtext.ScrolledText(
            self.log_frame, 
            bg="#111111", 
            fg="#cccccc", 
            font=("Consolas", 8),
            borderwidth=0,
            highlightthickness=0,
            padx=5,
            pady=5,
            height=10
        )
        self.log_display.pack(fill=tk.BOTH, expand=True)
        self.log_display.config(state=tk.DISABLED)
        
        # Load last few lines from log file
        self.load_past_logs()
        
        # Initial log entry
        self.log_to_gui("--- Session Started ---")

        # Control buttons removed as requested - bot runs on login

    def get_help_image_path(self, msg):
        # When running as a frozen .exe, PyInstaller extracts data to sys._MEIPASS
        if getattr(sys, 'frozen', False):
            base_dir = os.path.join(sys._MEIPASS, "taraccabai")
        else:
            base_dir = "taraccabai"
        if "betting window is open" in msg: return os.path.join(base_dir, "clickable button.png")
        if "hover your mouse over BANKER" in msg: return os.path.join(base_dir, "banker.png")
        if "PLAYER" in msg: return os.path.join(base_dir, "player.png")
        if "TIE and press" in msg or "over TIE " in msg: return os.path.join(base_dir, "tie.png")
        if "MAIN STATUS REGION" in msg:
            return os.path.join(base_dir, "status region 1.png" if "STEP 1" in msg else "status region 2.png")
        if "TIE STATUS REGION" in msg:
            return os.path.join(base_dir, "tie status region 1.png" if "STEP 1" in msg else "tie status region 2.png")
        if "BALANCE" in msg:
            return os.path.join(base_dir, "balance status 1.png" if "STEP 1" in msg else "balance status 2.png")
        if "CHIP " in msg:
            try:
                # Extracts the value from e.g. "CHIP 10 and press Space"
                val = msg.split("CHIP ")[1].split(" ")[0]
                return os.path.join(base_dir, f"chip {val}.png")
            except: pass
        return None

    def update_info_loop(self):
        if self.bot:
            threading.Thread(target=self._perform_bg_sync, daemon=True).start()
        # Network sync remains every 5 seconds to avoid over-requesting
        self.root.after(5000, self.update_info_loop)

    def update_ui_fast_loop(self):
        """Higher frequency loop for UI timer and status smoothness (1s)."""
        if self.bot:
            self._update_ui_state()
        self.root.after(1000, self.update_ui_fast_loop)

    def _perform_bg_sync(self):
        try:
            # Let the bot's internal push_monitoring_update handle all status decisions
            self.bot.push_monitoring_update()
            self.root.after(0, self._update_ui_state)
        except Exception:
            pass

    def _update_ui_state(self):
        if not self.bot: return
        
        # Use NIG-01 as the ultimate fallback if everything else is generic
        display_name = self.bot.bot_name
        if not display_name or display_name == "Unit":
            display_name = "NIG-001"
            
        self.unit_name_label.config(text=display_name)
        
        credits_val = self.bot.credits if self.bot.credits is not None else 0
        cmd_active = self.bot.remote_command
        
        # 1. Critical Errors / Blocking conditions
        if self.bot.network_recovery_active:
            # Show the dynamic countdown timer
            self.status_label.config(text=f"RECOVERY REST ({self.bot.recovery_remaining}s)", foreground="#f39c12") # Orange
        elif self.bot.humanization_active:
            # Show Humanization warning and countdown
            mins = self.bot.humanization_remaining // 60
            secs = self.bot.humanization_remaining % 60
            warning = f"HUMANIZING ({mins}m {secs}s)\nDO NOT TOUCH!"
            self.status_label.config(text=warning, foreground="#d35400") # Dark Orange / Brownish
        elif self.bot.needs_calibration():
            self.status_label.config(text="NEEDS CALIBRATION", foreground="#f39c12")
        elif credits_val < 1:
            self.status_label.config(text="NO CREDITS", foreground="#f39c12")
        elif self.bot.status == "BURNED":
            self.status_label.config(text="NO BALANCE (PLEASE RESTART APP)", foreground="#c0392b") # Red

            
        # 2. Operational States
        elif cmd_active and self.is_running and self.bot.running:
            # Both thread is alive AND website says RUN AND bot engine is active
            self.status_label.config(text="RUNNING", foreground="#2ecc71") # Green
        elif self.bot.status == "Stopped":
            # Bot was manually stopped from website
            self.status_label.config(text="STOPPED", foreground="#c0392b") # Red
        else:
            # Default standby state
            self.status_label.config(text="CONNECTED", foreground="#1abc9c") # Blue Green

    def start_calibration(self):
        from tkinter import simpledialog
        pwd = simpledialog.askstring("Password", "Enter calibration password:", show='*')
        if pwd is None:
            return
        if pwd != "akhlys11":
            messagebox.showerror("Error", "Incorrect password")
            return

        if messagebox.askyesno("Calibration", "Calibration started.\nUse SPACE or the NEXT STEP button to capture points.\nContinue?"):
            self.root.geometry("325x500") # Expand window for calibration
            self.is_calibrating = True
            
            # --- POPUP UI ---
            self.calib_popup = tk.Toplevel(self.root)
            self.calib_popup.title("BT - CALIBRATION INSTRUCTION")
            self.calib_popup.geometry("400x150")
            self.calib_popup.attributes("-topmost", True)
            self.calib_popup.configure(bg="#2c3e50")
            
            self.pop_header = tk.Label(self.calib_popup, text="CALIBRATION STEP", font=("Helvetica", 14, "bold"), fg="#3498db", bg="#2c3e50")
            self.pop_header.pack(pady=(10, 5))
            
            self.pop_instr = tk.Label(self.calib_popup, text="Initializing...", font=("Helvetica", 12), fg="white", bg="#2c3e50", wraplength=350, justify=tk.CENTER)
            self.pop_instr.pack(pady=5, padx=10)
            
            self.pop_hint = tk.Label(self.calib_popup, text="Press SPACE/NEXT when ready.", font=("Helvetica", 10, "italic"), fg="#95a5a6", bg="#2c3e50")
            self.pop_hint.pack(pady=5)
            
            self.pop_image_lbl = tk.Label(self.calib_popup, bg="#2c3e50")
            self.pop_image_lbl.pack(pady=5)
            
            # --- ACTION BUTTONS ---
            btn_frame = tk.Frame(self.calib_popup, bg="#2c3e50")
            btn_frame.pack(side=tk.BOTTOM, pady=10)
            
            self.next_btn_pop = tk.Button(btn_frame, text="NEXT STEP", command=self.trigger_next_step, bg="#27ae60", fg="white", font=("Helvetica", 10, "bold"), width=15)
            self.next_btn_pop.pack(side=tk.LEFT, padx=5)
            
            self.cancel_btn = tk.Button(btn_frame, text="EXIT / CANCEL", command=self.cancel_calibration, bg="#c0392b", fg="white", font=("Helvetica", 10, "bold"), width=15)
            self.cancel_btn.pack(side=tk.LEFT, padx=5)

            self.calib_frame.pack(pady=10)
            self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            self.next_btn.config(state=tk.NORMAL)
            self.calib_event.clear()
            self.calibration_cancelled = False
            threading.Thread(target=self.run_calibration, daemon=True).start()


    def trigger_next_step(self):
        if self.is_calibrating:
            self.calib_event.set()

    def cancel_calibration(self):
        if self.is_calibrating:
            if messagebox.askyesno("Cancel", "Are you sure you want to exit calibration?"):
                self.calibration_cancelled = True
                self.calib_event.set() # Unblock waiter

    def run_calibration(self):
        def gui_waiter(msg):
            # Check if cancelled before waiting
            if self.calibration_cancelled:
                raise ValueError("CANCELLED")

            # Update labels with the full instruction
            self.root.after(0, lambda: self.status_label.config(text=msg.upper(), foreground="#f1c40f"))
            
            # Update the Floating Popup
            if self.calib_popup and self.calib_popup.winfo_exists():
                self.root.after(0, lambda: self.pop_instr.config(text=msg))

                # Update Image
                img_path = self.get_help_image_path(msg)
                if img_path and os.path.exists(img_path):
                    try:
                        img = Image.open(img_path)
                        img.thumbnail((350, 200)) # Resize for popup
                        photo = ImageTk.PhotoImage(img)
                        def update_img(p):
                            self.pop_image_lbl.config(image=p)
                            self.pop_image_lbl.image = p # Keep reference
                            # Adjust popup size based on image
                            if self.calib_popup and self.calib_popup.winfo_exists():
                                self.calib_popup.geometry("400x450")
                        self.root.after(0, lambda: update_img(photo))
                    except Exception as e:
                        logger.log(f"Image load error: {e}", "DEBUG")
                else:
                    self.root.after(0, lambda: self.pop_image_lbl.config(image=""))
            
            self.calib_event.clear()
            self.calib_event.wait()
            
            if self.calibration_cancelled:
                raise ValueError("CANCELLED")

            self.calib_event.clear()


        try:
            game_mode = self.bot.game_mode if self.bot else "Classic Baccarat"
            min_chip = 50 if game_mode == "Always 8 Baccarat" else 10
            calibration.main(wait_func=gui_waiter, min_chip=min_chip)
            
            # Restore status label after success
            self.root.after(0, lambda: self.status_label.config(text="CALIBRATION SUCCESS", foreground="#27ae60"))
            
            # Close Popup
            if self.calib_popup and self.calib_popup.winfo_exists():
                self.root.after(0, self.calib_popup.destroy)
            
            # Refresh configuration without restart
            if self.bot:
                self.bot.config = self.bot.load_config()
                self.bot.sb_config = self.bot.config.get('supabase', {})
                
            self.root.after(0, lambda: messagebox.showinfo("Success", "Calibration complete! No need to restart."))
        except ValueError as ve:
            if str(ve) == "CANCELLED":
                logger.log("Calibration exited by user.", "WARNING")
                self.root.after(0, lambda: self.status_label.config(text="CALIBRATION CANCELLED", foreground="#e67e22"))
                if self.calib_popup and self.calib_popup.winfo_exists():
                    self.root.after(0, self.calib_popup.destroy)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Calibration failed: {ve}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Calibration failed: {e}"))

        finally:
            self.is_calibrating = False
            self.root.after(0, lambda: self.next_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.calib_frame.pack_forget())
            self.root.after(0, lambda: self.log_frame.pack_forget())
            self.root.after(0, lambda: self.root.geometry("325x150")) # Shrink window back

    def initialize_bot_instance(self):
        try:
            self.bot = Bot(on_settings_sync=self.update_remote_settings_display, user_auth_id=self.user_auth_id)
        except Exception as e:
            logger.log(f"Startup Error: {e}", "DEBUG")
            self.bot = None

    def update_remote_settings_display(self, remote_data):
        # Engine handles sync; UI can use this for specific notifications if needed
        pass

    def start_bot_thread(self):
        if self.is_running: return 
        if not self.bot:
            self.initialize_bot_instance()
        if self.bot:
            # Persistent Memory: We no longer wipe stats on every click!
            self.bot.last_result = None
            self.bot.first_run = True
            self.bot.starting_balance = None
            self.bot.target_balance = None
            self.bot.start_time = time.time()
            self.bot.can_restart = True # Manual start clears burned block
            logger.log(f"Auto-Start initialized. Syncing with remote command...", "INFO")

        
        self.is_running = True
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

    def run_bot(self):
        try:
            self.bot.running = True
            while self.is_running:
                if self.bot.credits < 1:
                    self.bot.push_monitoring_update(status="No Credits")
                    time.sleep(5)
                    continue
                if not self.bot.remote_command:
                    # In standby (Connected), update monitoring periodically
                    self.bot.push_monitoring_update()
                    time.sleep(5)
                    continue
                self.bot.run_cycle()
        except Exception as e:
            logger.log(f"Bot Internal Error: {e}", "ERROR")
            self.is_running = False
        finally:
            self.root.after(0, self.on_bot_stopped)

    def stop_bot(self):
        self.is_running = False
        if self.bot:
            self.bot.stop_remotely("Stopped")

    def handle_logout(self):
        """Clears the session and returns to login."""
        if messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            self.stop_bot()
            
            # Clear remembered session from config
            try:
                from utils import find_resource
                import json
                config_path = find_resource("config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        config = json.load(f)
                    
                    if "supabase" in config:
                        config["supabase"]["remembered_auth_id"] = None
                        
                        with open(config_path, "w") as f:
                            json.dump(config, f, indent=2)
            except Exception as e:
                print(f"Failed to clear session during logout: {e}")

            if self.on_logout:
                self.on_logout()

    def on_closing(self):
        """Called when the window is closed or Exit is clicked."""
        if self.bot:
            # If we are BURNED, don't overwrite with "Inactive" to keep it persistent on website
            if self.bot.status == "BURNED":
                 self.root.destroy()
                 return
            
            # For normal exit, show "Inactive" on the website
            self.is_running = False
            self.bot.push_monitoring_update(status="Inactive")

        # Small delay to allow final network request to finish
        self.root.after(1000, self.root.destroy)

    def toggle_logs(self):
        """Show or hide the log output and resize the window."""
        if self.log_frame.winfo_ismapped():
            self.log_frame.pack_forget()
            self.root.geometry("325x150") # Snap back to compact height
        else:
            self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            self.root.geometry("325x450") # Expand to show logs
            self.root.update_idletasks() # Ensure UI refresh

    def on_bot_stopped(self):
        # Auto-restart logic or notifications can go here
        pass

    def log_to_gui(self, message):
        """Append a message to the log display in a thread-safe way."""
        if hasattr(self, 'log_display'):
            self.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.log_display.config(state=tk.NORMAL)
        self.log_display.insert(tk.END, f"{message}\n")
        self.log_display.see(tk.END)
        self.log_display.config(state=tk.DISABLED)

    def load_past_logs(self, lines=20):
        """Loads the last N lines from the automation_log.txt file."""
        log_file = "automation_log.txt"
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                    last_lines = all_lines[-lines:]
                    self.log_display.config(state=tk.NORMAL)
                    for line in last_lines:
                        self.log_display.insert(tk.END, line)
                    self.log_display.see(tk.END)
                    self.log_display.config(state=tk.DISABLED)
            except Exception as e:
                self.log_to_gui(f"Error loading past logs: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = BaccaratGUI(root)
    root.mainloop()
