import os
import subprocess
import sys
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def create_desktop_shortcut(app_path):
    """Creates a desktop shortcut for the given app path using PowerShell."""
    desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
    shortcut_path = os.path.join(desktop, "Baccarat Bot.lnk")
    
    if os.path.exists(shortcut_path):
        return True

    powershell_script = f"""
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut_path}')
    $s.TargetPath = '{app_path}'
    $s.WorkingDirectory = '{os.path.dirname(app_path)}'
    $s.Save()
    """
    try:
        subprocess.run(["powershell", "-Command", powershell_script], capture_output=True, check=True)
        return True
    except Exception as e:
        print(f"Failed to create shortcut: {e}")
        return False

def install_tesseract(installer_path):
    """Runs the Tesseract installer silently."""
    try:
        print(f"Installing Tesseract from {installer_path}...")
        # /S for silent install
        subprocess.run([installer_path, "/S"], check=True)
        return True
    except Exception as e:
        print(f"Tesseract installation failed: {e}")
        return False

def check_and_install_dependencies():
    """Main dependency check logic."""
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    # 1. Check Tesseract
    if not os.path.exists(tesseract_path):
        print("Tesseract OCR not found.")
        installer_name = "tesseract-ocr-w64-setup.exe"
        # Search for any tesseract setup exe in the current directory and 'data' subfolder
        cwd = os.getcwd()
        search_dirs = [cwd, os.path.join(cwd, "data")]
        
        # Also check alongside executable if frozen
        if getattr(sys, 'frozen', False):
            search_dirs.append(os.path.dirname(sys.executable))
            search_dirs.append(os.path.join(os.path.dirname(sys.executable), "data"))

        setup_exe = None
        for d in search_dirs:
            if not os.path.exists(d): continue
            for file in os.listdir(d):
                if "tesseract-ocr-w64-setup" in file.lower() and file.endswith(".exe"):
                    setup_exe = os.path.join(d, file)
                    break
            if setup_exe: break
        
        if setup_exe:
            print(f"Found installer: {setup_exe}")
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            if messagebox.askyesno("Setup", "Tesseract OCR is required but not installed.\nWould you like to install it now?"):
                if install_tesseract(setup_exe):
                    messagebox.showinfo("Success", "Tesseract installed! Please restart the app if OCR fails.")
                else:
                    messagebox.showerror("Error", "Tesseract installation failed. Please install it manually.")
            root.destroy()
        else:
            print("No Tesseract installer found in current directory.")

    # 2. Check/Create Shortcut
    # Determine the executable path
    if getattr(sys, 'frozen', False):
        app_path = sys.executable
        create_desktop_shortcut(app_path)

if __name__ == "__main__":
    check_and_install_dependencies()
