# updater.py - Auto-updater for Newbies Bot
import os
import sys
import json
import requests
import subprocess
import tempfile
import hashlib
from pathlib import Path
from tkinter import messagebox
from logger_config import get_logger

logger = get_logger()

class AutoUpdater:
    def __init__(self, current_version=None):
        if current_version is None:
            try:
                from version import __version__
                self.current_version = __version__
            except ImportError:
                self.current_version = "1.0.0"
        else:
            self.current_version = current_version
        self.update_server = "https://api.github.com/repos/kankrittapon/Newbies/releases/latest"
        self.download_url = None
        self.new_version = None
    
    def check_for_updates(self, silent=True):
        """ตรวจสอบอัปเดต"""
        try:
            response = requests.get(self.update_server, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.new_version = data.get("tag_name", "").replace("v", "")
                
                if self._is_newer_version(self.new_version):
                    # หา download URL
                    for asset in data.get("assets", []):
                        if asset["name"].endswith(".exe"):
                            self.download_url = asset["browser_download_url"]
                            break
                    
                    if not silent:
                        self._show_update_dialog()
                    return True
                else:
                    if not silent:
                        messagebox.showinfo("อัปเดต", "คุณใช้เวอร์ชันล่าสุดอยู่แล้ว")
                    return False
            else:
                if not silent:
                    messagebox.showerror("ข้อผิดพลาด", "ตรวจสอบอัปเดตไม่ได้")
                return False
                
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            if not silent:
                messagebox.showerror("ข้อผิดพลาด", f"ตรวจสอบอัปเดตไม่ได้: {e}")
            return False
    
    def _is_newer_version(self, new_version):
        """เปรียบเทียบเวอร์ชัน"""
        try:
            current_parts = [int(x) for x in self.current_version.split(".")]
            new_parts = [int(x) for x in new_version.split(".")]
            
            # Pad shorter version with zeros
            max_len = max(len(current_parts), len(new_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            new_parts.extend([0] * (max_len - len(new_parts)))
            
            return new_parts > current_parts
        except Exception:
            return False
    
    def _show_update_dialog(self):
        """แสดง dialog อัปเดต"""
        result = messagebox.askyesno(
            "อัปเดตใหม่", 
            f"มีเวอร์ชันใหม่ v{self.new_version}\n"
            f"เวอร์ชันปัจจุบัน: v{self.current_version}\n\n"
            f"ต้องการอัปเดตตอนนี้ไหม?"
        )
        
        if result:
            self.download_and_install()
    
    def download_and_install(self):
        """ดาวน์โหลดและติดตั้งอัปเดต"""
        if not self.download_url:
            messagebox.showerror("ข้อผิดพลาด", "ไม่พบลิงก์ดาวน์โหลด")
            return
        
        try:
            # สร้าง temp directory
            temp_dir = tempfile.mkdtemp()
            temp_file = os.path.join(temp_dir, "NewbiesBot_new.exe")
            
            # ดาวน์โหลด
            messagebox.showinfo("กำลังดาวน์โหลด", "กำลังดาวน์โหลดอัปเดต...")
            
            response = requests.get(self.download_url, stream=True)
            response.raise_for_status()
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # ตรวจสอบไฟล์
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 1000000:  # > 1MB
                self._install_update(temp_file)
            else:
                messagebox.showerror("ข้อผิดพลาด", "ไฟล์ที่ดาวน์โหลดไม่ถูกต้อง")
                
        except Exception as e:
            logger.error(f"Update download failed: {e}")
            messagebox.showerror("ข้อผิดพลาด", f"ดาวน์โหลดอัปเดตไม่สำเร็จ: {e}")
    
    def _install_update(self, new_file):
        """ติดตั้งอัปเดต"""
        try:
            current_exe = sys.executable
            backup_exe = current_exe + ".backup"
            
            # สร้าง batch script สำหรับอัปเดต
            batch_script = f'''@echo off
echo กำลังติดตั้งอัปเดต...
timeout /t 2 /nobreak > nul
move "{current_exe}" "{backup_exe}"
move "{new_file}" "{current_exe}"
echo อัปเดตเสร็จสิ้น!
start "" "{current_exe}"
del "%~f0"
'''
            
            batch_file = os.path.join(tempfile.gettempdir(), "update_newbies.bat")
            with open(batch_file, 'w', encoding='utf-8') as f:
                f.write(batch_script)
            
            # รัน batch script และปิดโปรแกรม
            messagebox.showinfo("อัปเดต", "กำลังติดตั้งอัปเดต...\nโปรแกรมจะรีสตาร์ทอัตโนมัติ")
            
            subprocess.Popen([batch_file], shell=True)
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Update installation failed: {e}")
            messagebox.showerror("ข้อผิดพลาด", f"ติดตั้งอัปเดตไม่สำเร็จ: {e}")

def check_updates_on_startup():
    """ตรวจสอบอัปเดตตอนเปิดโปรแกรม"""
    try:
        updater = AutoUpdater()
        return updater.check_for_updates(silent=True)
    except Exception as e:
        logger.error(f"Startup update check failed: {e}")
        return False

def manual_update_check():
    """ตรวจสอบอัปเดตด้วยตนเอง"""
    try:
        updater = AutoUpdater()
        updater.check_for_updates(silent=False)
    except Exception as e:
        logger.error(f"Manual update check failed: {e}")
        messagebox.showerror("ข้อผิดพลาด", f"ตรวจสอบอัปเดตไม่ได้: {e}")

if __name__ == "__main__":
    manual_update_check()