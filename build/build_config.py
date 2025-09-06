# build_config.py - Nuitka Build Configuration
import os
import sys

def create_nuitka_config():
    """สร้าง config สำหรับ Nuitka"""
    
    # ตรวจสอบ Python 3.12
    if sys.version_info[:2] != (3, 12):
        print(f"ERROR: Need Python 3.12 but found Python {sys.version_info.major}.{sys.version_info.minor}")
        return False
    
    # Modules ที่ต้องรวม
    include_modules = [
        "tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog",
        "requests", "json", "os", "sys", "subprocess", "threading",
        "datetime", "time", "pathlib", "tempfile", "hashlib",
        "logging", "configparser", "webbrowser", "urllib",
        "playwright", "asyncio", "selenium", "webdriver_manager"
    ]
    
    # Packages ที่ต้องรวม
    include_packages = [
        "playwright", "selenium", "webdriver_manager", "requests"
    ]
    
    # Data files
    data_files = [
        "assets/",
        "*.json",
        "*.md"
    ]
    
    config = {
        "main_file": "gui_app.py",
        "output_name": "NewbiesBot",
        "icon": "assets/robot.ico",
        "include_modules": include_modules,
        "include_packages": include_packages,
        "data_files": data_files,
        "windows_console": False,
        "onefile": True
    }
    
    print("SUCCESS: Build config created")
    return config

if __name__ == "__main__":
    config = create_nuitka_config()
    if config:
        print("SUCCESS: Ready to build with Nuitka")