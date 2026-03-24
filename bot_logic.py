import pyautogui
import pytesseract
import json
import time
import os
import random
import numpy as np
from PIL import Image, ImageOps
import requests
import math
from utils import logger, get_hwid, find_resource

# Configuration for Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Global PyAutoGUI speed settings
pyautogui.PAUSE = 0.02 # Minimal delay between actions
pyautogui.FAILSAFE = True

# Strategy name mapping: DB uses lowercase enums, bot uses capitalized internally
STRATEGY_DB_TO_BOT = {"standard": "Standard", "tank": "Tank", "sweeper": "Sweeper", "burst": "Burst"}
STRATEGY_BOT_TO_DB = {v: k for k, v in STRATEGY_DB_TO_BOT.items()}

# Game Mode mapping
MODE_DB_TO_BOT = {"Classic": "Classic Baccarat", "classic": "Classic Baccarat", "Always 8 Baccarat": "Always 8 Baccarat", "Always 8": "Always 8 Baccarat", "always 8": "Always 8 Baccarat"}
MODE_BOT_TO_DB = {"Classic Baccarat": "Classic", "Always 8 Baccarat": "Always 8"}

class Bot:
    def __init__(self, config_file='config.json', pattern_string='PPPB', base_bet=10, reset_on_cycle=True, target_percentage=0.0, max_level=12, strategy="Standard", on_settings_sync=None, user_auth_id=None):
        self.user_auth_id = user_auth_id
        self.user_db_id = None
        self.user_franchise_id = None
        self.config_file = find_resource(config_file)
        self.config = self.load_config()
        self.on_settings_sync = on_settings_sync
        self.running = False
        self.base_bet = base_bet
        self.current_bet = self.base_bet
        self.last_result = None 
        self.target_percentage = target_percentage
        self.starting_balance = None
        self.target_balance = None
        self.max_level = max_level
        self.strategy = strategy
        self.first_run = True 
        self.start_time = time.time()
        self.last_sync_time = 0
        self.local_mode = False
        self.game_mode = "Classic Baccarat"
        self._network_failures = 0  # Track consecutive network failures
        self._total_hands_played = 0 # Track hands since start
        self.betting_mode = "Sequence"
        self.session_lost_amount = 0 # Track accumulated loss for specific recovery modes
        self.franchise_name = "Baccarat Bot"
        self.bot_name = "Unit"
        self.credits = 0
        self.remote_command = False
        self.connection_status = "OK" # "OK" or "FAIL"
        self.bot_id = None
        self.state_file = find_resource('bot_state.json')
        self.status = "Connected"
        self.can_restart = True
        self.last_sync_success_time = time.time() # Tracker for internet loss recovery
        self.network_recovery_active = False
        self.recovery_remaining = 0 # Countdown for UI
        
        # --- HUMANIZATION SETTINGS ---
        self.humanization_active = False
        self.humanization_remaining = 0
        self.last_humanization_bet_time = 0
        self.daily_runtime_limit = random.randint(7*3600, 12*3600)
        self.accumulated_daily_runtime = 0
        self.day_of_last_reset = time.strftime("%d")
        self.has_done_lunch = False
        self.has_done_dinner = False
        self.session_start_time = time.time()
        self.next_humanization_bet_interval = random.randint(180, 330) # Random 3 to 5.5 mins
        
        
        # Strategy Multipliers (Transitions from Level 1 up to Level 10)
        self.strategies = {
            "Standard": [2] * 20,
            "Tank":    [2, 2, 2, 2, 2, 3, 2, 3, 2],
            "Sweeper": [3, 3, 3, 2, 2, 2, 2, 2, 2, 2],
            "Burst":   [1.6667, 1.8, 1.926]
        }
        self.strategy = strategy
        self.banker_density = self.calculate_banker_density(pattern_string)
        self.target_duration = 0 # Target seconds from DB
        
        self.pattern = pattern_string.upper().replace("-", "").replace(" ", "")
        if not self.pattern or any(c not in 'PBT' for c in self.pattern):
            logger.log(f"Invalid Pattern '{self.pattern}'! Defaulting to 'B'.", "WARNING")
            self.pattern = 'B'
            
        self.pattern_index = 0
        self.reset_on_cycle = reset_on_cycle
        self.last_end_balance = None  # Tracks balance for continuity
        self.current_bet_start_balance = None # Balance captured right before placing a bet
        
        logger.log(f"Bot Initialized. Pattern: {self.pattern} | Strategy: {self.strategy}", "INFO")

        # Monitoring Settings
        self.sb_config = self.config.get('supabase', {})
        self.martingale_level = 0
        self.bet_placed_this_round = False
        self.last_outcome_time = time.time()
        
        # Handle Bot Identity (find or create bot row in DB)
        self.handle_bot_identity()
        
        # PERSISTENCE: Re-load last session level/lost amount if it exists
        self.load_state()

        if self.sb_url and self.sb_key and self.bot_id:
            self.push_monitoring_update(status="Starting")

            
    def load_config(self):
        if not os.path.exists(self.config_file):
            logger.log("Config file not found!", "ERROR")
            raise FileNotFoundError("Config file not found.")
        with open(self.config_file, 'r') as f:
            return json.load(f)

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.log("Configuration saved.", "DEBUG")
        except Exception as e:
            logger.log(f"Failed to save config: {e}", "ERROR")

    def save_state(self):
        """Persists play state for recovery after network/power loss."""
        if not self.bot_id: return
        state = {
            "bot_id": self.bot_id,
            "pattern_index": self.pattern_index,
            "martingale_level": self.martingale_level,
            "current_bet": self.current_bet,
            "last_result": self.last_result,
            "total_hands_played": self._total_hands_played,
            "session_lost_amount": self.session_lost_amount,
            "bet_placed": self.bet_placed_this_round,
            "last_outcome_time": self.last_outcome_time,
            "timestamp": time.time()
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except:
            pass

    def load_state(self):
        """Loads persistent play state if it exists and matches current bot_id."""
        if not os.path.exists(self.state_file): return
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Only resume if it's for the same bot
            if state.get("bot_id") == self.bot_id:
                self.pattern_index = state.get("pattern_index", 0)
                self.martingale_level = state.get("martingale_level", 0)
                self.current_bet = state.get("current_bet", self.base_bet)
                self.last_result = state.get("last_result")
                self._total_hands_played = state.get("total_hands_played", 0)
                self.session_lost_amount = state.get("session_lost_amount", 0)
                self.bet_placed_this_round = state.get("bet_placed", False)
                self.last_outcome_time = state.get("last_outcome_time", time.time())
                self.first_run = False # Resume skip logic
                logger.log(f"RECOVERY: Resuming from Level {self.martingale_level}, Bet {self.current_bet}.", "SUCCESS")
        except:
            pass

    def clear_state(self):
        """Removes the state file when a session is cleanly finished or stopped manually."""
        if os.path.exists(self.state_file):
            try: os.remove(self.state_file)
            except: pass

    def handle_bot_identity(self):
        """Finds or creates a bot row in the Supabase 'bot' table using deterministic HWID."""
        self.sb_config = self.config.get('supabase', {})
        self.bot_id = self.sb_config.get('bot_id', '')
        self.sb_url = self.sb_config.get('url')
        self.sb_key = self.sb_config.get('key')
        
        if not self.sb_url or not self.sb_key:
            logger.log("Supabase credentials missing.", "DEBUG")
            return

        headers = {
            "apikey": self.sb_key,
            "Authorization": f"Bearer {self.sb_key}",
            "Content-Type": "application/json",
        }
        
        # --- NEW: Get user_db_id from public.user_account if logged in ---
        if self.user_auth_id:
            try:
                # 1. Check user_account table
                user_url = f"{self.sb_url}/rest/v1/user_account?auth_id=eq.{self.user_auth_id}&select=id,franchise_id"
                u_resp = requests.get(user_url, headers=headers, timeout=5)
                if u_resp.status_code == 200 and u_resp.json():
                    u_data = u_resp.json()[0]
                    self.user_db_id = u_data.get('id')
                    self.user_franchise_id = u_data.get('franchise_id')
                    logger.log(f"Linked to User Account: {self.user_db_id} (Franchise: {self.user_franchise_id})", "DEBUG")
                
                # 2. If not found, check franchise table (Franchise owner case)
                if not self.user_franchise_id:
                    f_owner_url = f"{self.sb_url}/rest/v1/franchise?auth_id=eq.{self.user_auth_id}&select=id"
                    f_resp = requests.get(f_owner_url, headers=headers, timeout=5)
                    if f_resp.status_code == 200 and f_resp.json():
                        self.user_franchise_id = f_resp.json()[0].get('id')
                        logger.log(f"Linked as Franchise Owner (Franchise: {self.user_franchise_id})", "DEBUG")

            except Exception as e:
                logger.log(f"Account lookup error: {e}", "DEBUG")

        # --- AUTO-NAMING LOGIC ---
        suggested_unit_name = "NIG-001"
        if self.user_franchise_id:
            try:
                # 1. Get Franchise Code
                f_url = f"{self.sb_url}/rest/v1/franchise?id=eq.{self.user_franchise_id}&select=code"
                f_resp = requests.get(f_url, headers=headers, timeout=5)
                f_code = "NIG"
                if f_resp.status_code == 200 and f_resp.json():
                    f_code = f_resp.json()[0].get('code') or "NIG"
                
                # 2. Count existing units in this franchise
                # Use count=exact header to get the total number of bots for this franchise
                c_headers = {**headers, "Prefer": "count=exact"}
                c_url = f"{self.sb_url}/rest/v1/bot?franchise_id=eq.{self.user_franchise_id}&select=id"
                c_resp = requests.get(c_url, headers=c_headers, timeout=5)
                
                total_units = 0
                if c_resp.status_code in [200, 206]:
                    content_range = c_resp.headers.get("Content-Range", "0-0/0")
                    total_units = int(content_range.split("/")[-1])
                
                # 3. Determine next index (Limit to 999)
                next_idx = min(total_units + 1, 999)
                suggested_unit_name = f"{f_code}-{next_idx:03d}"
                logger.log(f"Auto-naming: Suggested Name {suggested_unit_name} (Units: {total_units})", "DEBUG")
            except Exception as e:
                logger.log(f"Auto-naming error: {e}", "DEBUG")

        current_hwid = get_hwid()
        
        # --- PHASE 1: Try to find bot by current_hwid (GUID) AND franchise_id ---
        if self.user_franchise_id:
            try:
                # Search for a bot record that matches this machine AND this franchise
                url = f"{self.sb_url}/rest/v1/bot?guid=eq.{current_hwid}&franchise_id=eq.{self.user_franchise_id}&select=*,franchise:franchise_id(investor_name,credits,code)"
                resp = requests.get(url, headers=headers, timeout=5)
                
                if resp.status_code == 400:
                    url_simple = f"{self.sb_url}/rest/v1/bot?guid=eq.{current_hwid}&franchise_id=eq.{self.user_franchise_id}&select=*"
                    resp = requests.get(url_simple, headers=headers, timeout=5)
                
                logger.log(f"Phase 1 Lookup (GUID {current_hwid}, Franchise {self.user_franchise_id}): {resp.status_code}", "DEBUG")

                if resp.status_code == 200 and resp.json():
                    data = resp.json()[0]
                    self.bot_id = data['id']
                    self.bot_name = data.get('unit_name') or "Unit"
                    
                    # Robust Update: Ensure bot is pinned to current user
                    updates = {}
                    if self.user_db_id and data.get('user_id') != self.user_db_id:
                        updates["user_id"] = self.user_db_id
                    
                    # If the name is generic "Unit", try to suggest a better one
                    if self.bot_name == "Unit":
                        self.bot_name = suggested_unit_name
                        updates["unit_name"] = self.bot_name
                        logger.log(f"Assigned Auto-name to Bot {self.bot_id}: {self.bot_name}", "INFO")

                    if updates:
                        patch_url = f"{self.sb_url}/rest/v1/bot?id=eq.{self.bot_id}"
                        requests.patch(patch_url, headers=headers, json=updates, timeout=5)

                    franchise = data.get('franchise') if isinstance(data.get('franchise'), dict) else None
                    self.franchise_name = franchise.get('investor_name') if franchise else "Baccarat Bot"
                    self.credits = franchise.get('credits') if franchise and franchise.get('credits') is not None else 0

                    logger.log(f"Bot linked by machine and franchise: {self.bot_id} ({self.bot_name})", "SUCCESS")
                    self._save_bot_id()
                    self.load_state() 
                    return
            except Exception as e:
                logger.log(f"GUID/Franchise lookup error: {e}", "DEBUG")

        # --- PHASE 2: Fallback — Try to find bot by legacy bot_id from config ---
        if self.bot_id:
            try:
                url = f"{self.sb_url}/rest/v1/bot?id=eq.{self.bot_id}&select=*,franchise:franchise_id(investor_name,credits,code)"
                resp = requests.get(url, headers=headers, timeout=5)
                
                if resp.status_code == 400:
                    url_simple = f"{self.sb_url}/rest/v1/bot?id=eq.{self.bot_id}&select=*"
                    resp = requests.get(url_simple, headers=headers, timeout=5)

                logger.log(f"Phase 2 Lookup (ID {self.bot_id}): {resp.status_code}", "DEBUG")
                if resp.status_code == 200 and resp.json():
                    data = resp.json()[0]
                    
                    # Only reuse this bot_id if it belongs to the same franchise
                    # OR if we don't have a franchise yet (legacy/anonymous)
                    if not self.user_franchise_id or data.get('franchise_id') == self.user_franchise_id:
                        if not data.get('guid') or data.get('guid') != current_hwid:
                            patch_url = f"{self.sb_url}/rest/v1/bot?id=eq.{self.bot_id}"
                            requests.patch(patch_url, headers=headers, json={"guid": current_hwid}, timeout=5)
                        
                        self.bot_name = data.get('unit_name') or suggested_unit_name
                        
                        updates = {}
                        if self.user_db_id and data.get('user_id') != self.user_db_id:
                            updates["user_id"] = self.user_db_id
                        if not data.get('unit_name') or data.get('unit_name') == "Unit":
                            updates["unit_name"] = self.bot_name
                        
                        if updates:
                            patch_url = f"{self.sb_url}/rest/v1/bot?id=eq.{self.bot_id}"
                            requests.patch(patch_url, headers=headers, json=updates, timeout=5)

                        franchise = data.get('franchise')
                        if isinstance(franchise, dict):
                            self.franchise_name = franchise.get('investor_name') or "Baccarat Bot"
                            self.credits = franchise.get('credits') if franchise.get('credits') is not None else 0
                        
                        logger.log(f"Bot identity confirmed: {self.bot_id} ({self.bot_name})", "INFO")
                        self.load_state()
                        return
                    else:
                        logger.log(f"Cached Bot ID {self.bot_id} belongs to a different franchise. Ignoring.", "WARNING")
                        self.bot_id = None # Clear it so we create a new one for this franchise
            except Exception as e:
                logger.log(f"Bot ID verification error: {e}", "DEBUG")

        # --- PHASE 3: Not found — Create a new bot record ---
        try:
            logger.log("No existing bot found for this hardware/ID. Creating new entry...", "WARNING")
            payload = {
                "status": "CALIBRATE" if self.needs_calibration() else "Starting",
                "bet": self.base_bet,
                "pattern": self.pattern if self.pattern in ['P', 'B', 'PB', 'BP', 'PPPB', 'BBBP'] else 'B',
                "level": self.max_level,
                "target_profit": self.target_percentage if self.target_percentage is not None else 0.0,
                "command": False,
                "duration": 0,
                "strategy": STRATEGY_BOT_TO_DB.get(self.strategy, "standard"),
                "balance": 0,
                "mode": MODE_BOT_TO_DB.get(self.game_mode, "Classic"),
                "guid": current_hwid,
                "user_id": self.user_db_id,
                "franchise_id": self.user_franchise_id,
                "unit_name": suggested_unit_name
            }
                
            url = f"{self.sb_url}/rest/v1/bot"
            resp = requests.post(
                url,
                headers={**headers, "Prefer": "return=representation"},
                json=payload,
                timeout=5
            )
            if resp.status_code in (200, 201) and resp.json():
                data = resp.json()[0]
                self.bot_id = data['id']
                self.bot_name = data.get('unit_name') or "NIG-001"
                logger.log(f"Created new bot record: {self.bot_id}", "SUCCESS")
                self._save_bot_id()
            else:
                logger.log(f"Failed to create bot: {resp.status_code} {resp.text}", "ERROR")
        except Exception as e:
            logger.log(f"Bot creation error: {e}", "ERROR")

    def _save_bot_id(self):
        """Persist bot_id to config.json."""
        if 'supabase' not in self.config:
            self.config['supabase'] = {}
        self.config['supabase']['bot_id'] = self.bot_id
        self.config['supabase']['hardware_id'] = get_hwid()
        self.save_config()

    def needs_calibration(self):
        if 'target_a' not in self.config or 'status_region_main' not in self.config or 'chips' not in self.config:
            return True
        return False

    def push_monitoring_update(self, status=None):
        if not self.sb_url or not self.sb_key or not self.bot_id:
            return

        headers = {
            "apikey": self.sb_key,
            "Authorization": f"Bearer {self.sb_key}",
            "Content-Type": "application/json",
        }
        
        try:
            # 1. GET fresh settings first (Flicker Fix)
            get_url = f"{self.sb_url}/rest/v1/bot?id=eq.{self.bot_id}&select=*,franchise:franchise_id(investor_name,credits)"
            get_resp = requests.get(get_url, headers=headers, timeout=5)
            
            if get_resp.status_code == 200:
                self.connection_status = "OK"
                data = get_resp.json()
                if data:
                    bot_data = data[0]
                    # Update Identity & Credits
                    self.bot_name = bot_data.get('unit_name') or self.bot_name
                    franchise = bot_data.get('franchise')
                    if isinstance(franchise, dict):
                        self.franchise_name = franchise.get('investor_name') or self.franchise_name
                        self.credits = franchise.get('credits') if franchise.get('credits') is not None else 0
                    
                    # Sync Martingale & Command
                    self.sync_remote_settings(bot_data)
            
            # 2. Calculate what to push back
            balance = self.get_current_balance()
            
            # --- STATUS CALCULATION ---
            # We only show BURNED if the bot itself has set that status.
            # We don't 'predict' it here anymore to avoid desync with the main loop.
            if self.status == "BURNED":
                effective_status = "BURNED"
            elif status:
                effective_status = status
            elif self.needs_calibration():
                effective_status = "CALIBRATE"
            elif not self.remote_command:
                # If command is OFF, status is Stopped
                effective_status = "Stopped"
            elif self.humanization_active:
                effective_status = "HUMANIZING"
            elif self.network_recovery_active:
                effective_status = f"RESTING ({self.recovery_remaining}s)"
            else:
                # RUNNING status only if threads are active and command is ON
                effective_status = "Running" if self.running else "Connected"


            # 3. PATCH status back
            payload = {
                "status": effective_status,
                "balance": balance if balance is not None else 0,
            }
            patch_url = f"{self.sb_url}/rest/v1/bot?id=eq.{self.bot_id}"
            requests.patch(
                patch_url,
                headers={**headers, "Prefer": "return=minimal"},
                json=payload,
                timeout=5
            )
            
            self.last_sync_time = time.time()
            self.last_sync_success_time = time.time() # Mark a successful exchange
            self._network_failures = 0
            
        except Exception as e:
            self.connection_status = "FAIL"
            self._network_failures += 1
            if self._network_failures <= 2:
                logger.log(f"Sync error (network): {type(e).__name__}", "DEBUG")

    def calculate_banker_density(self, pattern):
        if not pattern: return 0
        pattern = pattern.upper()
        return pattern.count('B') / len(pattern)

    def push_play_history(self, start_bal, end_bal, level, bet_size):
        """Logs the outcome to 'play_history' table."""
        if not self.sb_url or not self.sb_key or not self.bot_id:
            return

        headers = {
            "apikey": self.sb_key,
            "Authorization": f"Bearer {self.sb_key}",
            "Content-Type": "application/json"
        }

        s_bal = start_bal if start_bal is not None else 0
        e_bal = end_bal if end_bal is not None else 0
        pnl = e_bal - s_bal

        payload = {
            "bot_id": self.bot_id,
            "start_balance": s_bal,
            "end_balance": e_bal,
            "level": str(level),
            "pnl": pnl,
        }

        try:
            url = f"{self.sb_url}/rest/v1/play_history"
            requests.post(url, headers=headers, json=payload, timeout=5)
        except Exception as e:
            logger.log(f"History log error: {e}", "DEBUG")

    def apply_constraints(self):
        """Enforces safety rules defined by the system/UI."""
        # 1. Bet Size vs Max Level Mapping
        bet_limits = {200: 10, 100: 11, 50: 12, 10: 14}
        
        strict_limit = 14
        for trigger_bet, limit in sorted(bet_limits.items(), reverse=True):
            if self.base_bet >= trigger_bet:
                strict_limit = limit
                break
        
        if self.max_level > strict_limit:
            logger.log(f"Max Level {self.max_level} exceeds safety limit for Bet {self.base_bet}. Clamping to {strict_limit}.", "WARNING")
            self.max_level = strict_limit

        # 2. Level vs Strategy Constraints
        if self.max_level >= 4 and self.strategy in ["Sweeper", "Burst"]:
            logger.log(f"Strategy {self.strategy} is not allowed for Level {self.max_level}. Reverting to Standard.", "WARNING")
            self.strategy = "Standard"

    def sync_remote_settings(self, remote_data):
        if self.local_mode:
            # Still update status/balance to DB, but don't accept changes FROM DB
            return

        # 1. Pattern Sync
        new_pattern = remote_data.get('pattern')
        if new_pattern and new_pattern.upper() != self.pattern:
            self.pattern = new_pattern.upper().replace("-", "").replace(" ", "")
            self.pattern_index = 0
            self.banker_density = self.calculate_banker_density(self.pattern)

        # 2. Bet (Base Bet) Sync
        new_bet = remote_data.get('bet')
        if new_bet is not None:
            new_bet = int(new_bet)
            if new_bet < 10:
                new_bet = 10
            
            if new_bet != self.base_bet:
                self.base_bet = new_bet
                self.current_bet = self.base_bet
                self.martingale_level = 1

        # 3. Strategy Sync (DB stores lowercase: standard, sweeper, etc.)
        new_strategy_db = remote_data.get('strategy')
        if new_strategy_db:
            new_strategy = STRATEGY_DB_TO_BOT.get(new_strategy_db, new_strategy_db)
            if new_strategy in self.strategies and new_strategy != self.strategy:
                self.strategy = new_strategy

        # 4. Max Level Sync
        new_max_level = remote_data.get('level')
        if new_max_level is not None:
            try:
                new_max_level = int(new_max_level)
                if new_max_level != self.max_level:
                    if self.martingale_level == 0:
                        logger.log(f"Max Level changed to {new_max_level}. Syncing.", "INFO")
                        self.max_level = new_max_level
                    else:
                        # Queue the update for after the current recovery
                        logger.log(f"Max Level changed to {new_max_level}, but we are at Level {self.martingale_level}. Will update after next Win.", "INFO")
                        # For now, we update it but don't reset the current bet/level
                        self.max_level = new_max_level
            except ValueError:
                pass


        # 5. Command Sync (Safe Type Conversion)
        remote_cmd_val = remote_data.get('command')
        if remote_cmd_val is not None:
            if isinstance(remote_cmd_val, bool):
                self.remote_command = remote_cmd_val
            else:
                self.remote_command = str(remote_cmd_val).lower() in ['true', 'start', 'run', '1']
        else:
            self.remote_command = False

        # 5. Target Profit Sync
        new_profit_pct = remote_data.get('target_profit')
        if new_profit_pct is not None:
            try:
                pct = float(new_profit_pct)
                if pct != self.target_percentage:
                    self.target_percentage = pct
                    if self.starting_balance:
                        self.target_balance = self.starting_balance + (self.target_percentage / 100 * self.starting_balance)
            except (ValueError, TypeError):
                pass

        # 6. Duration Limit Sync (minutes from DB)
        raw_duration = remote_data.get('duration')
        if raw_duration in [None, "", 0, "0"]:
            self.target_duration = 0
        else:
            try:
                self.target_duration = int(raw_duration) * 60
            except ValueError:
                self.target_duration = 0

        # 7. Game Mode Sync
        raw_mode = remote_data.get('mode')
        if raw_mode:
            new_game_mode = MODE_DB_TO_BOT.get(raw_mode, raw_mode)
            if new_game_mode in ["Classic Baccarat", "Always 8 Baccarat"]:
                if new_game_mode != self.game_mode:
                    self.game_mode = new_game_mode
                    logger.log(f"Synced Game Mode: {self.game_mode}", "INFO")

        # 8. Bot Status Sync — driven by command field (true = run, false = stop)
        remote_cmd = remote_data.get('command')

        if remote_cmd is not None:
            if isinstance(remote_cmd, bool):
                should_run = remote_cmd
            else:
                should_run = str(remote_cmd).lower() in ['true', 'start', 'run', '1']
        else:
            should_run = self.running  # No info — keep current state

        if not should_run:
            if self.running:
                self.running = False
                self.status = "Stopped" # Explicitly transition to Stopped only on delta
                logger.log("Stopping bot (Remote Command)...", "INFO")
            # Clear burned block when website command is toggled OFF
            self.can_restart = True 
        elif should_run and not self.running:
            if self.can_restart and self.status != "BURNED":
                self.start_time = time.time()
                self.running = True
                self.status = "Running"
                logger.log("Starting bot (Remote Command)...", "INFO")
            else:
                # Force command back to false if it tries to auto-restart while burned
                self.status = "BURNED" # Ensure we don't flip to Stopped if burned
                self.stop_remotely(self.status)

        # 10. Final validation
        self.apply_constraints()

        # Notify UI if callback exists
        if self.on_settings_sync:
            self.on_settings_sync(remote_data)

    def capture_status_region(self, region_key):
        region_config = self.config.get(region_key)
        if not region_config: raise ValueError(f"Region {region_key} missing")
        region = (int(region_config['x']), int(region_config['y']), int(region_config['width']), int(region_config['height']))
        return pyautogui.screenshot(region=region)

    def check_tie_region(self):
        try:
            img = self.capture_status_region('status_region_tie')
            np_img = np.array(img)
            avg_color = np_img.mean(axis=(0, 1))
            r, g, b = avg_color
            
            is_green = (g > r + 15) and (g > b + 15) and (g > 70)
            
            text = pytesseract.image_to_string(img.convert('L').point(lambda p: p > 150 and 255)).strip().lower()
            if "tie" in text or "t1e" in text or is_green: 
                return True
        except: pass
        return False

    def analyze_state(self):
        if self.check_tie_region(): return "TIE"
        image = self.capture_status_region('status_region_main')
        text = pytesseract.image_to_string(image.convert('L')).strip().lower()
        if "banker" in text: return "BANKER"
        if "player" in text: return "PLAYER"
        if "win" in text or "nanalo" in text: return "GENERIC_WIN"
        return None

    def get_current_balance(self):
        if 'status_region_balance' not in self.config: return None
        try:
            image = self.capture_status_region('status_region_balance')
            text = pytesseract.image_to_string(image.convert('L')).strip()
            clean_text = "".join(c for c in text if c.isdigit() or c == '.')
            if clean_text:
                new_val = float(clean_text)
                # Sanity check: If we have a previous balance, don't allow impossible jumps (e.g. +5k in one go)
                if self.last_end_balance is not None:
                    diff = abs(new_val - self.last_end_balance)
                    if diff > 5000: # Adjust threshold if needed
                        logger.log(f"Balance OCR Glitch suspected: {self.last_end_balance} -> {new_val}. Ignoring.", "DEBUG")
                        return self.last_end_balance
                return new_val
        except: pass
        return None

    def wait_for_result_to_clear(self):
        logger.log("Waiting for result banner to clear...", "DEBUG")
        start_wait = time.time()
        
        # Actively wait for the banner to disappear
        while self.analyze_state() is not None:
            time.sleep(0.5)
            if time.time() - start_wait > 15: # Safety timeout
                break
                
        logger.log("Waiting for betting window to open...", "DEBUG")
        start_wait = time.time()
        while True:
            # Check 1: Button color (Reliable shortcut)
            if self.is_button_clickable():
                logger.log("Betting window detected via Button Color!", "INFO")
                break

            # Check 2: OCR (Fallback)
            try:
                image = self.capture_status_region('status_region_main')
                text = pytesseract.image_to_string(image.convert('L')).strip().lower()
                keywords = ["place", "bet", "please", "start", "your"]
                if any(k in text for k in keywords):
                    logger.log(f"Betting window detected via OCR! ('{text}')", "INFO")
                    break
            except:
                pass
                
            if time.time() - start_wait > 30: # Longer timeout for shuffles
                # If we've waited 30s and button is still not clickable, it's likely a shuffle
                return False
                
            time.sleep(0.5)
            
        # Additional buffer to ensure chips are clickable
        time.sleep(random.uniform(1.0, 2.0))
        return True
                
    def is_button_clickable(self):
        """Checks if the Banker button matches its 'clickable' color baseline."""
        if 'target_a' not in self.config or 'color' not in self.config['target_a']:
            return False
            
        target = self.config['target_a']
        try:
            current_color = pyautogui.pixel(int(target['x']), int(target['y']))
            baseline = target['color']
            
            # Simple Manhattan distance for color matching
            diff = sum(abs(c - b) for c, b in zip(current_color, baseline))
            # Status buttons are usually very distinct when clickable vs dimmed
            return diff < 60 
        except:
            return False

    def drift_detection(self):
        target = self.config['target_a']
        current_color = pyautogui.pixel(int(target['x']), int(target['y']))
        baseline = target.get('color')
        if baseline:
            diff = sum(abs(c - b) for c, b in zip(current_color, baseline))
            return diff < 100
        return True

    def select_chips(self, amount):
        if not self.config.get('chips'): return {}
        available_chips = sorted([int(k) for k in self.config['chips'].keys()], reverse=True)
        selected = {}
        remaining = amount
        for chip in available_chips:
            if remaining >= chip:
                count = remaining // chip
                remaining = remaining % chip
                selected[chip] = count
        return selected

    def execute_bet(self, target_char):
        if not self.running: return

        # Budget Check
        current_bal = self.get_current_balance()
        if current_bal is not None:
            min_chip = min([int(k) for k in self.config.get('chips', {'10':0}).keys()])
            if current_bal < min_chip or current_bal < self.current_bet:
                logger.log(f"BURNED: Balance {current_bal} cannot cover next bet {self.current_bet}.", "ERROR")
                self.stop_remotely("BURNED")
                return
            self.current_bet_start_balance = current_bal
        elif self.last_end_balance is not None:
            self.current_bet_start_balance = self.last_end_balance

        if target_char == 'T':
            lookup = self.pattern_index - 1
            resolved_side = None
            while lookup >= 0:
                if self.pattern[lookup] in 'PB':
                    resolved_side = self.pattern[lookup]
                    break
                lookup -= 1
            target_char = resolved_side if resolved_side else 'B'
            
        # Humanized pre-bet delay
        time.sleep(random.uniform(0.3, 0.6))
        
        target_key = 'target_a' if target_char == 'B' else 'target_b'
        target = self.config[target_key]
        chips_to_click = self.select_chips(self.current_bet)
        
        for chip_val, count in chips_to_click.items():
            chip_config = self.config['chips'].get(str(chip_val))
            if chip_config:
                chip_x = chip_config['x'] + random.randint(-3, 3)
                chip_y = chip_config['y'] + random.randint(-3, 3)
                move_dur = random.uniform(0.05, 0.1)
                
                pyautogui.click(chip_x, chip_y, duration=move_dur)
                time.sleep(random.uniform(0.02, 0.05))
                
                target_x = target['x'] + random.randint(-5, 5)
                target_y = target['y'] + random.randint(-5, 5)
                
                for _ in range(count):
                    pyautogui.click(x=target_x, y=target_y, duration=random.uniform(0.02, 0.05))
                    time.sleep(random.uniform(0.01, 0.03))
                
                time.sleep(random.uniform(0.02, 0.05))

        self.bet_placed_this_round = True
        self.push_monitoring_update()

    def execute_test_bet(self):
        """Standard $10 bet on Banker for physical testing."""
        target = self.config['target_a']
        chip_10 = self.config['chips'].get('10')
        if not chip_10:
            logger.log("Cannot test clicks: Chip 10 not calibrated.", "ERROR")
            return
            
        logger.log("Testing humanized clicks: Chip 10 -> Banker", "INFO")
        
        cx = chip_10['x'] + random.randint(-3, 3)
        cy = chip_10['y'] + random.randint(-3, 3)
        pyautogui.click(cx, cy, duration=random.uniform(0.15, 0.35))
        
        time.sleep(random.uniform(0.1, 0.3))
        
        tx = target['x'] + random.randint(-5, 5)
        ty = target['y'] + random.randint(-5, 5)
        pyautogui.click(tx, ty, duration=random.uniform(0.15, 0.35))
        
        logger.log(f"Click test complete. Offset applied: ({tx-target['x']}, {ty-target['y']})", "SUCCESS")

    def check_humanization(self):
        """Checks and triggers humanization breaks and daily limits."""
        now = time.localtime()
        current_hour = now.tm_hour
        current_day = time.strftime("%d")
        
        # 1. Midnight Reset
        if current_day != self.day_of_last_reset:
            self.daily_runtime_limit = random.randint(7*3600, 12*3600)
            self.accumulated_daily_runtime = 0
            self.day_of_last_reset = current_day
            self.has_done_lunch = False
            self.has_done_dinner = False
            logger.log(f"Daily Reset: New total limit is {self.daily_runtime_limit // 3600} hours.", "INFO")

        # 2. Trigger Lunch (11 AM)
        if current_hour == 11 and not self.has_done_lunch:
            self.humanization_active = True
            self.humanization_remaining = random.randint(15*60, 60*60)
            self.has_done_lunch = True
            logger.log(f"Entering LUNCH Humanization ({self.humanization_remaining // 60} mins)...", "WARNING")

        # 3. Trigger Dinner (6 PM / 18)
        if current_hour == 18 and not self.has_done_dinner:
            self.humanization_active = True
            self.humanization_remaining = random.randint(15*60, 60*60)
            self.has_done_dinner = True
            logger.log(f"Entering DINNER Humanization ({self.humanization_remaining // 60} mins)...", "WARNING")

        # 4. Check Daily Limit
        if self.accumulated_daily_runtime >= self.daily_runtime_limit:
            logger.log("DAILY LIMIT REACHED: Humanizing shutdown...", "WARNING")
            self.stop_remotely("Daily Limit")
            return True
            
        return False

    def run_cycle(self):
        # Update running stats
        if self.running:
            self.accumulated_daily_runtime += 1 # Rough approximation per cycle
            
        if self.check_humanization():
            return

        if self.humanization_active:
            # --- HUMANIZATION (RESTING MODE) ---
            # Random keep-alive bet to appear more human
            time_since_last_bet = time.time() - self.last_humanization_bet_time
            
            if time_since_last_bet > self.next_humanization_bet_interval:
                mins = self.next_humanization_bet_interval // 60
                secs = self.next_humanization_bet_interval % 60
                logger.log(f"Humanization Heartbeat: Placing keep-alive bet after {mins}m {secs}s.", "DEBUG")
                # We place the regular bet according to strategy but just slowly
                self.last_humanization_bet_time = time.time()
                # Create a new random interval for the next bet (3 to 5.5 mins)
                self.next_humanization_bet_interval = random.randint(180, 330)
                # Continue with the rest of run_cycle logic for ONE HAND
            else:
                self.humanization_remaining -= 1
                if self.humanization_remaining <= 0:
                    self.humanization_active = False
                    logger.log("Humanization break complete. Resuming normal pace.", "SUCCESS")
                time.sleep(1)
                return

        if self.needs_calibration():
            if time.time() - self.last_sync_time > 5:
                self.push_monitoring_update()
            time.sleep(1)
            return

        self.push_monitoring_update()
        
        # --- NEW: INTERNET LOSS RECOVERY (2-MINUTE REST) ---
        sync_gap = time.time() - self.last_sync_success_time
        if sync_gap > 45: # If no successful sync for 45 seconds
            logger.log(f"RECOVERY: No internet sync for {int(sync_gap)}s. Entering 2-minute REST...", "WARNING")
            self.network_recovery_active = True
            self.recovery_remaining = 120
            
            # Countdown loop instead of static sleep
            while self.recovery_remaining > 0:
                time.sleep(1) 
                self.recovery_remaining -= 1
            
            # Wait for internet to be actually back before proceeding
            logger.log("Rest over. Waiting for internet restoration...", "INFO")
            while True:
                self.push_monitoring_update()
                if self.connection_status == "OK":
                    logger.log("Internet restored! Syncing balance for missed results...", "SUCCESS")
                    break
                time.sleep(5)

            # Wait for next banner to calculate the "blind" result
            logger.log("Waiting for next outcome banner to resolve missed hands...", "INFO")
            while True:
                outcome = self.analyze_state()
                if outcome:
                    current_bal = self.get_current_balance()
                    if current_bal is not None and self.last_end_balance is not None:
                        # Compare balance to see what happened during the outage
                        diff = current_bal - self.last_end_balance
                        
                        # Use a small epsilon to ignore tiny fluctuations if any
                        if abs(diff) < 1:
                            logger.log(f"Recovery: No balance change detected ({diff}). Assuming no hands played during outage.", "INFO")
                        elif diff > 0:
                            logger.log(f"Recovery: Detected GAIN of {diff}. Assuming WIN. Resetting Martingale.", "SUCCESS")
                            self.martingale_level = 0
                            self.current_bet = self.base_bet
                            self.pattern_index = (self.pattern_index + 1) % len(self.pattern)
                        else:
                            logger.log(f"Recovery: Detected LOSS of {diff}. Assuming LOSS. Adjusting Martingale.", "ERROR")
                            # If we bet recently, we know the size. Otherwise use previous bet.
                            self.martingale_level += 1
                            multipliers = self.strategies.get(self.strategy, self.strategies["Standard"])
                            if self.martingale_level < len(multipliers):
                                self.current_bet = int(self.current_bet * multipliers[self.martingale_level-1])
                            else:
                                self.current_bet *= 2
                            self.pattern_index = (self.pattern_index + 1) % len(self.pattern)
                        
                        self.last_end_balance = current_bal
                        self.bet_placed_this_round = False
                        self.last_result = "RECOVERED"
                        self._total_hands_played += 1
                        self.save_state()
                        
                        # Wait for this banner to clear before starting a new round
                        self.wait_for_result_to_clear()
                    break
                time.sleep(1)
            
            self.network_recovery_active = False # NOW it is safe to show 'Running' again
        
        self.drift_detection()
        
        current_bal = self.get_current_balance()

        if self.starting_balance is None and current_bal is not None:
            self.starting_balance = current_bal
            self.last_end_balance = current_bal
            if self.target_percentage:
                self.target_balance = self.starting_balance + (self.target_percentage / 100 * self.starting_balance)
                logger.log(f"Session Start Balance: {self.starting_balance} | Goal: {self.target_balance}", "INFO")

        # 1. Listen for outcome banner
        if not self.analyze_state():
            # Simply wait for the next banner to appear
            time.sleep(0.5)
            
            # Pulse for debugging (every 20s)
            now = time.time()
            if not hasattr(self, '_last_pulse'): self._last_pulse = 0
            if now - self._last_pulse > 20:
                logger.log("Listening for next hand outcome...", "DEBUG")
                self._last_pulse = now

            # Check limits even while waiting
            elapsed_seconds = time.time() - self.start_time
            if self.target_duration > 0 and elapsed_seconds >= self.target_duration:
                logger.log(f"SESSION STOP: Time limit reached.", "WARNING")
                self.stop_remotely("Time Limit")
                return
            return

        
        current_target_char = self.pattern[self.pattern_index] 
        if current_target_char == 'T':
            lookup = self.pattern_index - 1
            resolved_side = None
            while lookup >= 0:
                if self.pattern[lookup] in 'PB':
                    resolved_side = self.pattern[lookup]
                    break
                lookup -= 1
            current_target_char = resolved_side if resolved_side else 'B'
        
        outcome = self.analyze_state()
        if outcome:
            self.last_outcome_time = time.time() # Update timer when banner is found
            
            if not self.bet_placed_this_round:
                logger.log(f"Outcome {outcome} detected but NO BET was placed (e.g. Shuffle). Syncing for next round.", "WARNING")
                if self.wait_for_result_to_clear():
                    self.execute_bet(self.pattern[self.pattern_index])
                else:
                    # If betting window never opened, we reset last_result so the NEXT hand seen
                    # is treated as a Baseline Sighting again (Safety).
                    logger.log("Betting window never opened. Resetting sighting for next hand.", "DEBUG")
                    self.last_result = None
                return

            start_bal = self.get_current_balance()
            logger.log(f"Outcome: {outcome}", "SUCCESS")
            self.bet_placed_this_round = False # Reset for next round
            
            if not self.wait_for_result_to_clear():
                # If betting window never opened after we bet (rare), we still treat first hand after shuffle as baseline
                logger.log("Betting window never opened after result. Resetting sighting.", "DEBUG")
                self.last_result = None
                return
            
            current_target_name = "BANKER" if current_target_char == 'B' else "PLAYER"
            actual_result = "LOSS"
            if outcome == "TIE": actual_result = "PUSH"
            elif outcome == current_target_name or outcome == "GENERIC_WIN": actual_result = "WIN"
            
            # --- BALANCE CROSS-CHECK (Catches skipped hands & OCR misreads) ---
            end_bal = self.get_current_balance()
            if end_bal is not None and self.last_end_balance is not None and actual_result != "PUSH":
                balance_diff = end_bal - self.last_end_balance
                
                if actual_result == "WIN" and balance_diff < -1:
                    # Banner said WIN, but balance went DOWN → likely a skipped hand loss
                    logger.log(f"CROSS-CHECK: Banner={actual_result} but Balance dropped by {balance_diff}. Overriding → LOSS.", "WARNING")
                    actual_result = "LOSS"
                elif actual_result == "LOSS" and balance_diff > 1:
                    # Banner said LOSS, but balance went UP → likely a skipped hand win
                    logger.log(f"CROSS-CHECK: Banner={actual_result} but Balance gained {balance_diff}. Overriding → WIN.", "WARNING")
                    actual_result = "WIN"

            logger.log(f"Result determined: {actual_result}", "INFO")
            prev_bet = self.current_bet
            prev_level = self.martingale_level
            # --- SESSION START HANDLING ---
            if self.last_result is None:
                logger.log("First hand detected (Baseline). Ignoring result for stats/betting.", "WARNING")
                if self.martingale_level == 0:
                    # Only reset to base if we weren't in a persistent recovery
                    self.current_bet = self.base_bet
                else:
                    logger.log(f"Resuming Persistent Martingale Level {self.martingale_level} (Bet: {self.current_bet})", "SUCCESS")

                self.last_result = "SIGHTED"
                self.last_end_balance = self.get_current_balance()
                self._total_hands_played = 0
                self.execute_bet(self.pattern[self.pattern_index])
                return

            # --- STANDARD LOGIC ---
            if actual_result == "WIN":
                is_half_win = False
                # Super 6 Detection: Banker win on 6 pays only 50%
                if end_bal is not None and self.last_end_balance is not None and prev_bet > 0:
                    profit = end_bal - self.last_end_balance
                    # Using a threshold around 50% (e.g. 30% to 70% of stake)
                    if 0.3 <= (profit / prev_bet) <= 0.7:
                        is_half_win = True
                
                if is_half_win and self.martingale_level > 0:
                    logger.log(f"SUPER 6 DETECTED: Profit {profit} is only ~50% of bet {prev_bet}. Dropping 1 Martingale level.", "WARNING")
                    self.martingale_level -= 1
                    
                    # Recalculate bet size for the NEW (lowered) level
                    if self.martingale_level == 0:
                        self.current_bet = self.base_bet
                    else:
                        # Re-derive the bet for this specific level
                        temp_bet = self.base_bet
                        multipliers = self.strategies.get(self.strategy, self.strategies["Standard"])
                        for i in range(self.martingale_level):
                            if i < len(multipliers):
                                temp_bet = int(temp_bet * multipliers[i])
                            else:
                                temp_bet *= 2
                        self.current_bet = temp_bet
                        
                    logger.log(f"Recovery adjustment: Returning to Level {self.martingale_level} (Bet: {self.current_bet})", "INFO")
                    # In a half-win, we keep the pattern index moving or stay? 
                    # Usually move forward since the round is resolved.
                    self.pattern_index = (self.pattern_index + 1) % len(self.pattern)
                else:
                    # Regular Full Win
                    self.current_bet = self.base_bet
                    self.martingale_level = 0
                    self.session_lost_amount = 0 # Reset recovery tracking
                    self.pattern_index = (self.pattern_index + 1) % len(self.pattern)

            elif actual_result == "PUSH":
                logger.log(f"Tie detected: Preserving Bet {self.current_bet} (Level {self.martingale_level})", "INFO")
                # Do not modify current_bet, martingale_level, or pattern_index

            elif actual_result == "LOSS":
                if self.game_mode == "Always 8 Baccarat":
                    self.session_lost_amount += prev_bet
                    # Formula: ((total lost) / 0.62) + 50
                    raw_bet = (self.session_lost_amount / 0.62) + 50
                    self.current_bet = math.ceil(raw_bet / 10) * 10
                    logger.log(f"Always 8 Logic: Total Lost={self.session_lost_amount}, Next Bet={self.current_bet}", "INFO")
                else:
                    # Smart Banker Multiplier Override (2.11x)
                    current_target_char = self.pattern[self.pattern_index]
                    has_consecutive_bankers = "BB" in self.pattern
                    
                    if current_target_char == 'B' and has_consecutive_bankers:
                        self.current_bet = math.ceil(self.current_bet * 2.11 / 10) * 10
                        logger.log(f"Banker Multiplier (2.11x) applied (Pattern contains 'BB'). Rounding up to nearest 10.", "INFO")
                    else:
                        multipliers = self.strategies.get(self.strategy, self.strategies["Standard"])
                        if self.martingale_level < len(multipliers):
                            multiplier = multipliers[self.martingale_level]
                            self.current_bet = int(self.current_bet * multiplier)
                        else:
                            self.current_bet *= 2

                self.martingale_level += 1
                self.pattern_index = (self.pattern_index + 1) % len(self.pattern)

                if self.martingale_level > self.max_level:
                    logger.log(f"SESSION STOP: Max Level ({self.max_level}) reached.", "WARNING")
                    self.stop_remotely("BURNED")
                    return

            self.last_result = actual_result
            self._total_hands_played += 1
            
            history_start = self.current_bet_start_balance if self.current_bet_start_balance is not None else self.last_end_balance



            # Log result to Supabase (including PUSH/TIE as requested)
            self.push_play_history(history_start, end_bal, prev_level, prev_bet)
            
            # Save state after processing result
            self.save_state()
                
            self.last_end_balance = end_bal
            self.current_bet_start_balance = None 

            # --- AFTER LOGGING: CHECK LIMITS ---
            elapsed_seconds = time.time() - self.start_time
            if self.target_duration > 0 and elapsed_seconds >= self.target_duration:
                logger.log(f"SESSION STOP: Time limit reached.", "WARNING")
                self.stop_remotely("Time Limit")
                return

            if self.target_percentage is not None and self._total_hands_played > 0:
                current_bal = self.get_current_balance()
                # Ensure we have a valid balance and target, and that we aren't at $0 (which triggers false wins)
                if current_bal is not None and self.target_balance is not None and current_bal > 1:
                    if current_bal >= self.target_balance:
                        logger.log(f"GOAL REACHED! Profit target (>{self.target_percentage}%) hit.", "SUCCESS")
                        self.stop_remotely("Goal Reached")
                        return

            # --- PLACING NEXT BET ---
            self.execute_bet(self.pattern[self.pattern_index])
            self.save_state() # Save state again after placing bet (updates pattern_index/bet)
            time.sleep(random.uniform(0.5, 1.0))
        else:
            time.sleep(0.1)

    def stop_remotely(self, reason_status):
        """Stops the bot and updates the database status so it doesn't auto-restart."""
        self.running = False
        if reason_status == "BURNED":
            self.can_restart = False
        self.clear_state() # Manual/Remote stop clears recovery data
        self.push_monitoring_update(status=reason_status)

        # Set command=false in DB so the website toggle flips to off
        if self.sb_url and self.sb_key and self.bot_id:
            headers = {
                "apikey": self.sb_key,
                "Authorization": f"Bearer {self.sb_key}",
                "Content-Type": "application/json",
            }
            try:
                url = f"{self.sb_url}/rest/v1/bot?id=eq.{self.bot_id}"
                requests.patch(url, headers=headers, json={"command": False}, timeout=5)
            except:
                pass


    def start(self):
        self.running = True
        self.start_time = time.time()
        
        self.last_end_balance = self.get_current_balance()
        
        logger.log("Bot session active. Listening for commands...", "INFO")
        try:
            while True:
                if self.running:
                    self.run_cycle()
                else:
                    if time.time() - self.last_sync_time > 5:
                        self.push_monitoring_update()
                    time.sleep(1)
        except KeyboardInterrupt:
            logger.log("Bot stopped manually.", "INFO")
