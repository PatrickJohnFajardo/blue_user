import tkinter as tk
import requests
import json
from tkinter import messagebox
import os
from utils import find_resource

class LoginScreen:
    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.root.title("BLUE LOG IN")
        self.root.geometry("500x500")
        
        # Colors
        self.dark_blue = "#1e3a8a" # Matches main app top bar
        self.accent_blue = "#3498db"
        self.text_white = "#ffffff"
        self.input_bg = "#f0f0f0"

        self.root.configure(bg=self.dark_blue)
        self.root.resizable(False, False)

        # Center Window
        self.center_window(500, 500)
        self.load_supabase_config()
        self.setup_layout()
        self.bind_keys()

    def center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def load_supabase_config(self):
        try:
            config_path = find_resource("config.json")
            with open(config_path, "r") as f:
                config = json.load(f)
                self.sb_url = config.get("supabase", {}).get("url")
                self.sb_key = config.get("supabase", {}).get("key")
        except Exception:
            self.sb_url = None
            self.sb_key = None

    def bind_keys(self):
        self.root.bind("<Return>", lambda e: self.handle_login())

    def setup_layout(self):
        # Centered Form Container
        self.form_frame = tk.Frame(self.root, bg=self.dark_blue)
        self.form_frame.place(relx=0.5, rely=0.5, anchor="center", width=350)

        # Fields
        self.email_ent = self.create_input("Email", "Enter your email")
        self.pass_ent = self.create_input("Password", "Enter your password", show="*")

        # Remember Me Checkbox (Now above button, aligned left)
        self.remember_var = tk.BooleanVar(value=True)
        self.remember_cb = tk.Checkbutton(
            self.form_frame, text="Remember Me", 
            variable=self.remember_var,
            bg=self.dark_blue, fg="white", 
            selectcolor=self.dark_blue,
            activebackground=self.dark_blue,
            activeforeground="white",
            font=("Helvetica", 10),
            padx=0 # Ensure it touches the left edge
        )
        self.remember_cb.pack(anchor="w", pady=(10, 0))

        # Login Button (White with dark blue text)
        self.login_btn = tk.Button(
            self.form_frame, text="Log in", 
            bg="white", fg=self.dark_blue, font=("Helvetica", 12, "bold"),
            relief="flat", height=2, cursor="hand2",
            command=self.handle_login
        )
        self.login_btn.pack(fill=tk.X, pady=(30, 0))

    def create_input(self, label_text, placeholder, show=None):
        tk.Label(
            self.form_frame, text=label_text, 
            bg=self.dark_blue, font=("Helvetica", 10, "bold"), fg=self.text_white
        ).pack(anchor="w", pady=(20, 5))
        
        ent = tk.Entry(
            self.form_frame, font=("Helvetica", 11), 
            relief="flat", highlightthickness=0,
            bg=self.input_bg, fg="#333333"
        )
        ent.pack(fill=tk.X, ipady=10)
        ent.insert(0, placeholder)
        
        ent.bind("<FocusIn>", lambda e: (ent.delete(0, tk.END), ent.config(show=show if show else "")) if ent.get() == placeholder else None)
        return ent

    def handle_login(self):
        email = self.email_ent.get()
        password = self.pass_ent.get()

        if not self.sb_url or not self.sb_key:
            messagebox.showerror("Error", "Supabase configuration missing.")
            return

        # Attempt Login via Supabase Auth
        try:
            headers = {
                "apikey": self.sb_key,
                "Content-Type": "application/json"
            }
            payload = {
                "email": email,
                "password": password
            }
            
            # Supabase GoTrue endpoint for password login
            auth_url = f"{self.sb_url}/auth/v1/token?grant_type=password"
            resp = requests.post(auth_url, headers=headers, json=payload, timeout=10)
            
            if resp.status_code == 200:
                auth_data = resp.json()
                user_data = auth_data.get("user", {})
                auth_id = user_data.get("id") # The UUID
                
                # Success! Save auth_id if remember is checked
                if self.remember_var.get():
                    self.save_remembered_id(auth_id)
                else:
                    self.save_remembered_id(None) # Clear it if unchecked

                # Pass auth_id to the main app
                self.on_success(auth_id=auth_id)
            else:
                error_msg = resp.json().get("error_description") or resp.json().get("error") or "Invalid credentials."
                messagebox.showerror("Login Failed", error_msg)
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to authentication server: {e}")

    def save_remembered_id(self, auth_id):
        try:
            config_path = find_resource("config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
            else:
                config = {}
            
            if "supabase" not in config:
                config["supabase"] = {}
            
            config["supabase"]["remembered_auth_id"] = auth_id
            
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Failed to save remember me setting: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = LoginScreen(root, lambda: print("Login Successful"))
    root.mainloop()
