# Baccarat Automation Bot v2.0

Comprehensive automation bot for Baccarat with Supabase remote management, OCR recognition, and advanced Martingale strategies.

## 🚀 Quick Start (New PC Setup)

To move this bot to a new computer, simply **Double-click `START_BOT.bat`**.

This script will:
1.  **Check Python**: Ensure you have Python installed.
2.  **Auto-Install**: Create a virtual environment and install dependencies automatically.
3.  **Register PC**: Detect your hardware and register this PC on your Supabase dashboard.
4.  **Start Bot**: Launch the application.

### 📝 Prerequisites
- **Python 3.10+**: Must be installed on the PC.
- **Tesseract OCR**: Needs to be installed to `C:\Program Files\Tesseract-OCR\`.
  - Installer is in the `Baccarat-Bot-v2` folder.

### 2. Physical Setup (Screen Calibration)

The bot needs to know where to click and where to read balance.

1.  Run `setup.bat` to install all dependencies.
2.  Run `run_gui.bat`.
3.  Click **"Run Calibration"**.
4.  Follow the instructions in the bot logs:
    - Hover over the **Banker** area -> Press **Space**.
    - Hover over the **Player** area -> Press **Space**.
    - Hover over the **Balance** area -> Use **1** and **2** to select the box.
    - Hover over the **Chips** -> Press **Space** for each chip (10, 50, 100, etc.).

### 3. Configure Supabase (Remote Website)

Open `config.json` and ensure your Supabase credentials match your dashboard:

```json
"supabase": {
  "url": "https://your-project.supabase.co",
  "key": "your-anon-key",
  "pc_name": "PC-NAME-HERE"
}
```

---

## 📂 File Structure

- `main.py`: The entry point for the application.
- `gui_app.py`: The primary user interface.
- `bot_logic.py`: Core betting engine and pattern logic.
- `utils.py`: Logging and helper functions (includes auto-log cleanup).
- `clean_logs.py`: Manual script to purge logs older than 3 days.
- `setup.bat`: One-click installer for new environments.
- `run_gui.bat`: Launches the bot with the graphical interface.
- `start_headless.bat`: Launches the bot in the background (remote control only).

---

## ⚠️ Important Rules

- **Display Scaling**: Ensure your Windows Display Scaling is set to **100%**. Other values (125%, 150%) will cause the bot to click the wrong spots.
- **Game Resolution**: Keep the game window at the same size it was during calibration.
- **Martingale Safety**: The bot has built-in limits based on your Base Bet to prevent "Busts".

## 🛠 Troubleshooting

- **"Python not found"**: Run `setup.bat`. If it fails, reinstall Python and check "Add to PATH".
- **"Tesseract not found"**: Ensure Tesseract is installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- **Bot clicks wrong spot**: Re-run the Calibration process.
