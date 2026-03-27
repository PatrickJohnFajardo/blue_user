import pyautogui
import json
import os
import time
from utils import logger, find_resource

CONFIG_FILE = find_resource('config_cg.json')

def get_coordinate(label, wait_func=input):
    logger.log(f"Calibrating: {label}", "INFO")
    prompt = f"Please hover your mouse over {label} and press Space."
    logger.log(prompt, "WARNING")
    
    wait_func(prompt)
    
    x, y = pyautogui.position()
    logger.log(f"Recorded {label} at ({x}, {y})", "SUCCESS")
    return {"x": x, "y": y}

def get_region(label, wait_func=input):
    logger.log(f"Calibrating Region: {label}", "INFO")
    
    prompt1 = f"STEP 1: Hover over TOP-LEFT of {label} and press Space."
    logger.log(prompt1, "WARNING")
    wait_func(prompt1)
    tl_x, tl_y = pyautogui.position()
    
    prompt2 = f"STEP 2: Hover over BOTTOM-RIGHT of {label} and press Space."
    logger.log(prompt2, "WARNING")
    wait_func(prompt2)
    br_x, br_y = pyautogui.position()
    
    width = br_x - tl_x
    height = br_y - tl_y
    
    if width <= 0 or height <= 0:
        logger.log("Invalid region dimensions!", "ERROR")
        return None
        
    return {"x": tl_x, "y": tl_y, "width": width, "height": height}

def main(wait_func=input):
    logger.log(f"Starting Color Game Calibration Phase...", "INFO")
    
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except:
            pass

    # 1. Colors
    for color in ["YELLOW", "WHITE", "PINK", "BLUE", "RED", "GREEN"]:
        config[f'target_{color.lower()}'] = get_coordinate(color, wait_func)
    
    # 2. Regions
    config['status_region_balance'] = get_region("BALANCE", wait_func)
    
    if not config['status_region_balance']:
        logger.log("Region calibration failed.", "ERROR")
        return
        
    # 3. Chips
    logger.log("--- Calibrating Chips ---", "INFO")
    chips = config.get('chips', {})
    chip_values = [1, 5, 10, 20, 50, 100]
    
    for val in chip_values:
        chips[str(val)] = get_coordinate(f"CHIP {val}", wait_func)
        config['chips'] = chips
    
    # Save to JSON
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
        
    logger.log(f"Color Game Calibration complete. Configuration saved to config_cg.json.", "SUCCESS")

if __name__ == "__main__":
    main()
