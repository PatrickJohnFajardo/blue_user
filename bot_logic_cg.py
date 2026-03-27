import time
import json
import os
import threading
import pyautogui
import pytesseract
import requests
from PIL import Image
from utils import logger, find_resource, get_hwid

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class CGBot:
    def __init__(self, on_settings_sync=None, user_auth_id=None):
        self.user_auth_id = user_auth_id
        self.bot_name = "Unit CG"
        self.config_file = find_resource('config_cg.json')
        self.config = self.load_config()
        self.running = False
        self.remote_command = False
        self.network_recovery_active = False
        self.humanization_active = False
        self.status = "Connected"
        self.credits = 100
        self.game_mode = "Color Game"
        
        self.colors = ["yellow", "white", "pink", "blue", "red", "green"]
        self.fib_sequence = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765, 10946, 17711, 28657, 46368, 75025, 121393, 196418, 317811, 514229, 832040]
        
        self.base_bet = 1
        self.strategy = "martingale" # 'martingale' or 'fibonacci'
        self.current_level = 0
        self.current_balance = None
        self.last_bet_amount = None
        
        self.on_settings_sync = on_settings_sync
        
        self.bot_id = None
        self.sb_config = self.config.get('supabase', {})
        self.user_db_id = None
        self.user_franchise_id = None
        self.can_restart = True 
        
        self.handle_bot_identity()
        
    def load_config(self):
        config_data = {}
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
                
        # Fallback to main config for Supabase credentials if missing in CG config
        if 'supabase' not in config_data or not config_data['supabase'].get('key'):
            main_config_path = find_resource('config.json')
            if os.path.exists(main_config_path):
                with open(main_config_path, 'r') as f:
                    main_config = json.load(f)
                    if 'supabase' in main_config:
                        config_data['supabase'] = main_config['supabase']
        return config_data

    def needs_calibration(self):
        if 'target_yellow' not in self.config or 'status_region_balance' not in self.config or 'chips' not in self.config:
            return True
        return False

    def push_monitoring_update(self, status=None):
        if self.status == "BURNED":
            effective_status = "BURNED"
        elif status:
            effective_status = status
            self.status = status
        elif self.needs_calibration():
            effective_status = "CALIBRATE"
        elif not self.remote_command:
            effective_status = "Stopped"
        else:
            effective_status = "Running" if self.running else "Connected"
            
        if not self.bot_id or 'url' not in self.sb_config or 'key' not in self.sb_config:
            return
            
        headers = {
            "apikey": self.sb_config['key'],
            "Authorization": f"Bearer {self.sb_config['key']}",
            "Content-Type": "application/json",
        }
        
        try:
            # 1. Fetch remote changes
            get_url = f"{self.sb_config['url']}/rest/v1/color_game_bot?id=eq.{self.bot_id}&select=*"
            get_resp = requests.get(get_url, headers=headers, timeout=5)
            if get_resp.status_code == 200 and get_resp.json():
                remote_data = get_resp.json()[0]
                self.sync_remote_settings(remote_data)
                
            # 2. Push status updates
            balance = self.get_current_balance()
            payload = {
                "status": effective_status,
                "balance": balance if balance is not None else 0,
            }
            patch_url = f"{self.sb_config['url']}/rest/v1/color_game_bot?id=eq.{self.bot_id}"
            requests.patch(patch_url, headers=headers, json=payload, timeout=5)
        except Exception as e:
            logger.log(f"CG DB Sync Error: {e}", "DEBUG")
            
    def sync_remote_settings(self, remote_data):
        # Sync Command
        remote_cmd = remote_data.get('command')
        if remote_cmd is not None:
            self.remote_command = str(remote_cmd).lower() in ['true', 'start', 'run', '1']
            if not self.remote_command and self.running:
                self.running = False
                self.status = "Stopped"
            elif self.remote_command and not self.running:
                if self.can_restart and self.status != "BURNED":
                    self.running = True
                    self.status = "Running"
                else:
                    # Sync back that we are still stopped if burned
                    self.stop_remotely(self.status)
                
        # Sync Bet, Strategy
        new_bet = remote_data.get('bet')
        if new_bet: self.base_bet = int(new_bet)
        
        new_strat = remote_data.get('strategy')
        if new_strat: self.strategy = str(new_strat).lower()
        
        # Call UI sync if needed
        if self.on_settings_sync:
            self.on_settings_sync(remote_data)

    def handle_bot_identity(self):
        self.sb_config = self.config.get('supabase', {})
        sb_url = self.sb_config.get('url')
        sb_key = self.sb_config.get('key')
        if not sb_url or not sb_key: return
        
        headers = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json",
        }
        
        # 1. Look up User / Franchise from Auth
        if self.user_auth_id:
            try:
                user_url = f"{sb_url}/rest/v1/user_account?auth_id=eq.{self.user_auth_id}&select=id,franchise_id"
                u_resp = requests.get(user_url, headers=headers, timeout=5)
                if u_resp.status_code == 200 and u_resp.json():
                    self.user_db_id = u_resp.json()[0].get('id')
                    self.user_franchise_id = u_resp.json()[0].get('franchise_id')
                if not self.user_franchise_id:
                    f_url = f"{sb_url}/rest/v1/franchise?auth_id=eq.{self.user_auth_id}&select=id"
                    f_resp = requests.get(f_url, headers=headers, timeout=5)
                    if f_resp.status_code == 200 and f_resp.json():
                        self.user_franchise_id = f_resp.json()[0].get('id')
            except: pass
            
        # --- AUTO-NAMING LOGIC ---
        suggested_unit_name = "CG-001"
        if self.user_franchise_id:
            try:
                f_url = f"{sb_url}/rest/v1/franchise?id=eq.{self.user_franchise_id}&select=code"
                f_resp = requests.get(f_url, headers=headers, timeout=5)
                f_code = "CG"
                if f_resp.status_code == 200 and f_resp.json():
                    f_code = f_resp.json()[0].get('code') or "CG"
                
                c_headers = {**headers, "Prefer": "count=exact"}
                c_url = f"{sb_url}/rest/v1/color_game_bot?franchise_id=eq.{self.user_franchise_id}&select=id"
                c_resp = requests.get(c_url, headers=c_headers, timeout=5)
                
                total_units = 0
                if c_resp.status_code in [200, 206]:
                    content_range = c_resp.headers.get("Content-Range", "0-0/0")
                    total_units = int(content_range.split("/")[-1])
                
                next_idx = min(total_units + 1, 999)
                suggested_unit_name = f"{f_code}-{next_idx:03d}"
            except Exception as e:
                pass
            
        current_hwid = get_hwid()
        
        # 2. Look for existing bot by HWID
        try:
            url = f"{sb_url}/rest/v1/color_game_bot?guid=eq.{current_hwid}&select=*"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200 and resp.json():
                idx = resp.json()[0]
                self.bot_id = idx['id']
                self.bot_name = idx.get('unit_name') or suggested_unit_name
                logger.log(f"Linked existing CG bot: {self.bot_id}", "SUCCESS")
                
                # Check if unit name was missing or uninitialized, patch it
                if not idx.get('unit_name') or idx.get('unit_name') == "CG-001":
                     patch_url = f"{sb_url}/rest/v1/color_game_bot?id=eq.{self.bot_id}"
                     requests.patch(patch_url, headers=headers, json={"unit_name": self.bot_name}, timeout=5)
                return
        except: pass
        
        # 3. Create new bot if none found
        try:
            payload = {
                "status": "Starting",
                "bet": self.base_bet,
                "strategy": self.strategy,
                "target_color": self.colors[0],
                "level": 10,
                "command": False,
                "guid": current_hwid,
                "user_id": self.user_db_id,
                "franchise_id": self.user_franchise_id,
                "unit_name": suggested_unit_name,
                "mode": "Color Game"
            }
            url = f"{sb_url}/rest/v1/color_game_bot"
            resp = requests.post(url, headers={**headers, "Prefer": "return=representation"}, json=payload, timeout=5)
            if resp.status_code in (200, 201) and resp.json():
                self.bot_id = resp.json()[0]['id']
                self.bot_name = resp.json()[0].get('unit_name', suggested_unit_name)
                logger.log(f"Created new CG bot record: {self.bot_id}", "SUCCESS")
        except Exception as e:
            logger.log(f"CG Bot creation error: {e}", "ERROR")
            
    def stop_remotely(self, final_status="Stopped"):
        """Stops the bot and updates the database status so it doesn't auto-restart."""
        self.remote_command = False
        self.running = False
        self.status = final_status
        
        if final_status == "BURNED":
            self.can_restart = False
            
        # Update command=false in DB so the website toggle flips to off
        if self.bot_id and 'url' in self.sb_config and 'key' in self.sb_config:
            headers = {
                "apikey": self.sb_config['key'],
                "Authorization": f"Bearer {self.sb_config['key']}",
                "Content-Type": "application/json",
            }
            try:
                url = f"{self.sb_config['url']}/rest/v1/color_game_bot?id=eq.{self.bot_id}"
                requests.patch(url, headers=headers, json={"command": False, "status": final_status}, timeout=5)
            except:
                pass

    def push_play_history(self, start_bal, end_bal, level, bet_size, target_color, result_color):
        """Logs the outcome to 'color_game_play_history' table."""
        if not self.bot_id or 'url' not in self.sb_config or 'key' not in self.sb_config:
            return

        headers = {
            "apikey": self.sb_config['key'],
            "Authorization": f"Bearer {self.sb_config['key']}",
            "Content-Type": "application/json"
        }

        s_bal = start_bal if start_bal is not None else 0
        e_bal = end_bal if end_bal is not None else 0
        pnl = e_bal - s_bal

        payload = {
            "franchise_id": self.user_franchise_id,
            "bot_id": self.bot_id,
            "start_balance": s_bal,
            "end_balance": e_bal,
            "level": str(level),
            "pnl": pnl,
            "bet_size": bet_size,
            "target_color": target_color,
            "result_color": result_color or "Unknown"
        }

        try:
            url = f"{self.sb_config['url']}/rest/v1/color_game_play_history"
            resp = requests.post(url, headers=headers, json=payload, timeout=5)
            if resp.status_code in [200, 201]:
                logger.log(f"History pushed to Supabase (P&L: {pnl})", "SUCCESS")
            else:
                logger.log(f"Supabase History Error: {resp.status_code} - {resp.text}", "ERROR")
        except Exception as e:
            logger.log(f"History log error: {e}", "DEBUG")

    def capture_status_region(self, region_key):
        region_config = self.config.get(region_key)
        if not region_config: return None
        region = (int(region_config['x']), int(region_config['y']), int(region_config['width']), int(region_config['height']))
        return pyautogui.screenshot(region=region)

    def get_current_balance(self):
        if 'status_region_balance' not in self.config: return None
        try:
            image = self.capture_status_region('status_region_balance')
            text = pytesseract.image_to_string(image.convert('L'), config='--psm 7 -c tessedit_char_whitelist=0123456789.').strip()
            clean_text = "".join(c for c in text if c.isdigit() or c == '.')
            if clean_text:
                return float(clean_text)
        except Exception as e:
            logger.log(f"OCR Error: {e}", "DEBUG")
        return None

    def calculate_bet_amount(self):
        if self.strategy == 'martingale':
            return self.base_bet * (2 ** self.current_level)
        elif self.strategy == 'fibonacci':
            index = min(self.current_level, len(self.fib_sequence) - 1)
            return self.base_bet * self.fib_sequence[index]
        return self.base_bet

    def select_chips(self, amount):
        if not self.config.get('chips'): return {}
        # Make sure chip values are treated as integers for correct sorting/math
        available_chips = sorted([int(k) for k in self.config['chips'].keys()], reverse=True)
        selected = {}
        remaining = amount
        for chip in available_chips:
            if remaining >= chip:
                count = remaining // chip
                remaining = remaining % chip
                selected[chip] = count
        return selected

    def place_bet(self, amount, color):
        target_coords = self.config.get(f'target_{color.lower()}')
        if not target_coords: return
        
        chips_to_click = self.select_chips(amount)
        for chip_val, count in chips_to_click.items():
            chip_coords = self.config['chips'].get(str(chip_val))
            if not chip_coords: continue
            
            # Click chip
            pyautogui.click(chip_coords['x'], chip_coords['y'])
            time.sleep(0.3)
            
            # Click color target
            for _ in range(count):
                if not self.running: return
                pyautogui.click(target_coords['x'], target_coords['y'])
                time.sleep(0.1)

    def run_cycle(self):
        # Color Game Loop
        logger.log("Waiting for betting window to open (detecting balance)...", "INFO")
        
        balance_start_time = None
        current_read_balance = None
        
        while self.running:
            bal = self.get_current_balance()
            if bal is not None:
                if balance_start_time is None:
                    balance_start_time = time.time()
                    logger.log(f"Balance detected ({bal}), waiting for stabilization (3s)...", "DEBUG")
                elif time.time() - balance_start_time >= 3:
                    current_read_balance = bal
                    logger.log(f"Stable balance confirmed: {bal}", "SUCCESS")
                    break
            else:
                if balance_start_time is not None:
                    logger.log("Balance lost during stabilization, resetting timer.", "DEBUG")
                    balance_start_time = None
            
            time.sleep(1)
            
        if not self.running: return
        
        # 2. Evaluate previous bet's result if this isn't the first run
        if self.current_balance is not None and self.last_bet_amount is not None:
            prev_level = self.current_level
            prev_bet = self.last_bet_amount
            # Use yellow as placeholder for result_color as result detection is still being tuned
            res_color = "Yellow" 
            
            if current_read_balance > (self.current_balance - self.last_bet_amount):
                logger.log(f"WIN! Balance: {self.current_balance} -> {current_read_balance}", "SUCCESS")
                
                # Standard Fibonacci rule: Move back two steps
                if self.strategy == 'fibonacci':
                     self.current_level = max(0, self.current_level - 2)
                else:
                     self.current_level = 0
                     
                self.push_play_history(self.current_balance, current_read_balance, prev_level, prev_bet, "yellow", res_color)
            elif current_read_balance < self.current_balance:
                logger.log(f"LOSS! Balance: {self.current_balance} -> {current_read_balance}", "ERROR")
                # Move forward one step regardless of strategy
                self.current_level += 1
                self.push_play_history(self.current_balance, current_read_balance, prev_level, prev_bet, "yellow", "Other")
            else:
                logger.log(f"TIE / NO CHANGE! Balance remained: {current_read_balance}", "WARNING")
                # Even for ties, we log history to keep the website updated
                self.push_play_history(self.current_balance, current_read_balance, prev_level, prev_bet, "yellow", "Tie")
        
        # 3. Update internal balance tracker
        self.current_balance = current_read_balance
        
        # 4. Calculate next bet
        bet_amount = self.calculate_bet_amount()
        target_color = self.colors[0] # Temporary fallback; update with pattern logic
        
        # --- BURNED CHECK ---
        available_balance = current_read_balance if current_read_balance is not None else 0
        if available_balance < bet_amount:
            logger.log(f"BURNED: Balance {available_balance} cannot cover next bet {bet_amount}.", "ERROR")
            self.stop_remotely("BURNED")
            return
            
        # --- LEVEL LIMIT CHECK ---
        if self.current_level > self.max_level:
            logger.log(f"LIMIT REACHED: Current Level {self.current_level} exceeds Max Level {self.max_level}.", "WARNING")
            self.stop_remotely("Limit reached")
            return
            
        self.last_bet_amount = bet_amount
        
        # 5. Place Bet
        logger.log(f"Betting Window Open! Placing {bet_amount} on {target_color}.", "WARNING")
        self.place_bet(bet_amount, target_color)
        
        # 6. Wait out the Betting Window
        logger.log("Waiting for Betting Window to Close (~22s)...", "INFO")
        for _ in range(22):
            if not self.running: return
            time.sleep(1)
            
        # 7. Wait out the Game Animation / Roll
        logger.log("Game rolling... waiting for outcome (~30s)", "INFO")
        for _ in range(30):
            if not self.running: return
            time.sleep(1)
            
        # The loop will naturally spin back up.
        # It will instantly loop to step 1 and wait for the balance to re-appear on screen!
        logger.log("Waiting for next betting phase delay/donations to pass...", "DEBUG")
