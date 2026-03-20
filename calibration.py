import pyautogui
import json
import time
import os
import sys
from utils import logger, find_resource
from PIL import Image

CONFIG_FILE = find_resource('config.json')

def get_coordinate(label, wait_func=input):
    """
    Prompts the user to hover over a target and records coordinates.
    Uses wait_func to wait for user confirmation.
    """
    logger.log(f"Calibrating: {label}", "INFO")
    prompt = f"Please hover your mouse over {label} and press Space."
    logger.log(prompt, "WARNING")
    
    wait_func(prompt)
    
    x, y = pyautogui.position()
    logger.log(f"Recorded {label} at ({x}, {y})", "SUCCESS")
    return {"x": x, "y": y}

def get_region(label, wait_func=input):
    """
    Prompts user to define a region (Top-Left and Bottom-Right).
    """
    logger.log(f"Calibrating Region: {label}", "INFO")
    
    prompt1 = f"STEP 1: Hover over TOP-LEFT of {label} and press Space."
    logger.log(prompt1, "WARNING")
    wait_func(prompt1)
    tl_x, tl_y = pyautogui.position()
    logger.log(f"Top-Left recorded at ({tl_x}, {tl_y})", "SUCCESS")
    
    prompt2 = f"STEP 2: Hover over BOTTOM-RIGHT of {label} and press Space."
    logger.log(prompt2, "WARNING")
    wait_func(prompt2)
    br_x, br_y = pyautogui.position()
    logger.log(f"Bottom-Right recorded at ({br_x}, {br_y})", "SUCCESS")
    
    width = br_x - tl_x
    height = br_y - tl_y
    
    if width <= 0 or height <= 0:
        logger.log("Invalid region dimensions!", "ERROR")
        return None
        
    return {"x": tl_x, "y": tl_y, "width": width, "height": height}

def capture_color_baseline(coords, label):
    """
    Captures a small screenshot at the coordinate to establish baseline color.
    For buttons, we might want to capture a small 5x5 region around the center.
    """
    # Capture a small region around the click point
    region = (coords['x'] - 2, coords['y'] - 2, 5, 5)
    try:
        img = pyautogui.screenshot(region=region)
        # Get the center pixel color
        pixel = img.getpixel((2, 2))
        logger.log(f"Baseline color for {label}: {pixel}", "INFO")
        return pixel
    except Exception as e:
        logger.log(f"Failed to capture color for {label}: {e}", "ERROR")
        return (0, 0, 0)

def main(wait_func=input, min_chip=10):
    logger.log(f"Starting Calibration Phase (Min Chip: {min_chip})...", "INFO")
    logger.log("HINT: You can use the GUI 'Next' button or SPACE key (if bound).", "DEBUG")
    
    # Load existing config if it exists to avoid wiping everything
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except:
            pass

    # 1. Capture Targets
    config['target_a'] = get_coordinate("BANKER", wait_func)
    config['target_b'] = get_coordinate("PLAYER", wait_func)
    config['target_c'] = get_coordinate("TIE", wait_func)
    
    # 2. Capture Regions
    config['status_region_main'] = get_region("MAIN STATUS REGION", wait_func)
    config['status_region_tie'] = get_region("TIE STATUS REGION", wait_func)
    config['status_region_balance'] = get_region("BALANCE", wait_func)
    
    if not config['status_region_main'] or not config['status_region_tie'] or not config['status_region_balance']:
        logger.log("Region calibration failed.", "ERROR")
        return
        
    # 3. Chip Calibration
    logger.log("--- Calibrating Chips ---", "INFO")
    chips = config.get('chips', {})
    all_possible_chips = [10, 50, 100, 250, 500, 1000, 5000, 10000]
    chip_values = [v for v in all_possible_chips if v >= min_chip]
    
    for val in chip_values:
        config['chips'] = chips # Update mid-loop for partial saves if needed
        chips[str(val)] = get_coordinate(f"CHIP {val}", wait_func)
    
    config['chips'] = chips

    # 4. Color Baselines
    logger.log("--- Capturing Color Baselines ---", "INFO")
    prompt_color = "Please hover over BANKER while the betting window is open, then press Space."
    logger.log(prompt_color, "WARNING")
    wait_func(prompt_color)
    
    config['target_a']['color'] = capture_color_baseline(config['target_a'], "Target A")
    config['target_b']['color'] = capture_color_baseline(config['target_b'], "Target B")
    config['target_c']['color'] = capture_color_baseline(config['target_c'], "Target C")

    # 5. Save to JSON
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
        
    logger.log(f"Calibration complete. Configuration saved.", "SUCCESS")

if __name__ == "__main__":
    main()
