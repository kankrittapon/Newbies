# config_wizard.py - First-time setup wizard
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from pathlib import Path
from error_handler import safe_execute
from logger_config import get_logger

logger = get_logger()

class ConfigWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🧙‍♂️ ตัวช่วยตั้งค่าเริ่มต้น")
        self.geometry("500x600")
        self.resizable(False, False)
        
        # Center window
        self.eval('tk::PlaceWindow . center')
        
        self.current_step = 0
        self.config_data = {}
        
        self._setup_ui()
        self._show_step(0)
    
    def _setup_ui(self):
        """Setup main UI"""
        # Header
        header = tk.Frame(self, bg="#3498db", height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(header, text="🧙‍♂️ ตัวช่วยตั้งค่าเริ่มต้น", 
                        font=("Arial", 16, "bold"), 
                        bg="#3498db", fg="white")
        title.pack(expand=True)
        
        # Content area
        self.content = tk.Frame(self, bg="white")
        self.content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Navigation
        nav = tk.Frame(self, bg="#ecf0f1", height=60)
        nav.pack(fill=tk.X)
        nav.pack_propagate(False)
        
        self.prev_btn = ttk.Button(nav, text="← ย้อนกลับ", command=self.prev_step)
        self.prev_btn.pack(side=tk.LEFT, padx=20, pady=15)
        
        self.next_btn = ttk.Button(nav, text="ถัดไป →", command=self.next_step)
        self.next_btn.pack(side=tk.RIGHT, padx=20, pady=15)
        
        self.step_label = tk.Label(nav, text="", font=("Arial", 10), bg="#ecf0f1")
        self.step_label.pack(expand=True)
    
    def _clear_content(self):
        """Clear content area"""
        for widget in self.content.winfo_children():
            widget.destroy()
    
    def _show_step(self, step):
        """Show specific step"""
        self.current_step = step
        self._clear_content()
        
        steps = [
            ("ยินดีต้อนรับ", self._step_welcome),
            ("ข้อมูลผู้ใช้", self._step_user_info),
            ("ตั้งค่า LINE", self._step_line_config),
            ("ตั้งค่าโปรไฟล์", self._step_profile_config),
            ("ตั้งค่าเบราว์เซอร์", self._step_browser_config),
            ("เสร็จสิ้น", self._step_complete)
        ]
        
        if 0 <= step < len(steps):
            title, func = steps[step]
            self.step_label.config(text=f"ขั้นตอน {step + 1}/{len(steps)}: {title}")
            func()
            
            # Update navigation buttons
            self.prev_btn.config(state=tk.NORMAL if step > 0 else tk.DISABLED)
            self.next_btn.config(text="เสร็จสิ้น" if step == len(steps) - 1 else "ถัดไป →")
    
    def _step_welcome(self):
        """Welcome step"""
        tk.Label(self.content, text="🎉 ยินดีต้อนรับสู่ Newbies Bot!", 
                font=("Arial", 18, "bold")).pack(pady=20)
        
        welcome_text = (
            "ตัวช่วยนี้จะแนะนำคุณในการตั้งค่าเริ่มต้น\n"
            "เพื่อให้คุณสามารถใช้งานโปรแกรมได้อย่างสมบูรณ์\n\n"
            "ขั้นตอนที่จะทำ:\n"
            "• ตั้งค่าข้อมูลผู้ใช้\n"
            "• ตั้งค่า LINE สำหรับ Auto Login\n"
            "• ตั้งค่าโปรไฟล์ส่วนตัว\n"
            "• ตั้งค่าเบราว์เซอร์\n\n"
            "⏱️ ใช้เวลาประมาณ 3-5 นาที"
        )
        
        tk.Label(self.content, text=welcome_text, font=("Arial", 11), 
                justify=tk.LEFT).pack(pady=20)
        
        # Tips
        tips_frame = tk.LabelFrame(self.content, text="💡 เคล็ดลับ", font=("Arial", 10, "bold"))
        tips_frame.pack(fill=tk.X, pady=20)
        
        tips_text = (
            "• คุณสามารถข้ามขั้นตอนใดก็ได้ และกลับมาตั้งค่าทีหลัง\n"
            "• ข้อมูลทั้งหมดจะถูกเก็บไว้ในเครื่องของคุณเท่านั้น\n"
            "• หากมีปัญหา สามารถรีเซ็ตการตั้งค่าได้ในเมนูหลัก"
        )
        
        tk.Label(tips_frame, text=tips_text, font=("Arial", 9), 
                justify=tk.LEFT).pack(padx=10, pady=10)
    
    def _step_user_info(self):
        """User info step"""
        tk.Label(self.content, text="👤 ข้อมูลผู้ใช้", 
                font=("Arial", 16, "bold")).pack(pady=(0, 20))
        
        # Form
        form = tk.Frame(self.content)
        form.pack(fill=tk.X)
        
        # Username
        tk.Label(form, text="Username:", font=("Arial", 11)).grid(row=0, column=0, sticky="e", padx=5, pady=10)
        self.username_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.username_var, width=25).grid(row=0, column=1, padx=10, pady=10)
        
        # Password
        tk.Label(form, text="Password:", font=("Arial", 11)).grid(row=1, column=0, sticky="e", padx=5, pady=10)
        self.password_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.password_var, show="*", width=25).grid(row=1, column=1, padx=10, pady=10)
        
        # Auto login
        self.auto_login_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="จำรหัสผ่าน (Auto Login)", 
                       variable=self.auto_login_var).grid(row=2, column=1, sticky="w", padx=10, pady=5)
        
        # Info
        info_text = "ℹ️ ข้อมูลนี้จะใช้สำหรับเข้าสู่ระบบอัตโนมัติ"
        tk.Label(self.content, text=info_text, font=("Arial", 9), 
                fg="#7f8c8d").pack(pady=20)
    
    def _step_line_config(self):
        """LINE configuration step"""
        tk.Label(self.content, text="📱 ตั้งค่า LINE", 
                font=("Arial", 16, "bold")).pack(pady=(0, 20))
        
        # Form
        form = tk.Frame(self.content)
        form.pack(fill=tk.X)
        
        # LINE Email
        tk.Label(form, text="LINE Email:", font=("Arial", 11)).grid(row=0, column=0, sticky="e", padx=5, pady=10)
        self.line_email_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.line_email_var, width=30).grid(row=0, column=1, padx=10, pady=10)
        
        # LINE Password
        tk.Label(form, text="LINE Password:", font=("Arial", 11)).grid(row=1, column=0, sticky="e", padx=5, pady=10)
        self.line_password_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.line_password_var, show="*", width=30).grid(row=1, column=1, padx=10, pady=10)
        
        # Enable auto login
        self.line_auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="เปิดใช้ LINE Auto Login", 
                       variable=self.line_auto_var).grid(row=2, column=1, sticky="w", padx=10, pady=5)
        
        # Info
        info_frame = tk.LabelFrame(self.content, text="ℹ️ ข้อมูล", font=("Arial", 10, "bold"))
        info_frame.pack(fill=tk.X, pady=20)
        
        info_text = (
            "• LINE Auto Login จะช่วยให้คุณไม่ต้องใส่รหัส OTP ทุกครั้ง\n"
            "• ข้อมูล LINE จะถูกเข้ารหัสและเก็บไว้ในเครื่องเท่านั้น\n"
            "• คุณสามารถข้ามขั้นตอนนี้และตั้งค่าทีหลังได้"
        )
        
        tk.Label(info_frame, text=info_text, font=("Arial", 9), 
                justify=tk.LEFT).pack(padx=10, pady=10)
    
    def _step_profile_config(self):
        """Profile configuration step"""
        tk.Label(self.content, text="📋 ตั้งค่าโปรไฟล์", 
                font=("Arial", 16, "bold")).pack(pady=(0, 20))
        
        # Form
        form = tk.Frame(self.content)
        form.pack(fill=tk.X)
        
        # Personal info
        fields = [
            ("ชื่อ:", "firstname"),
            ("นามสกุล:", "lastname"),
            ("เพศ:", "gender"),
            ("เลขบัตรประชาชน:", "id_number"),
            ("เบอร์โทร:", "phone")
        ]
        
        self.profile_vars = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(form, text=label, font=("Arial", 11)).grid(row=i, column=0, sticky="e", padx=5, pady=8)
            var = tk.StringVar()
            self.profile_vars[key] = var
            
            if key == "gender":
                combo = ttk.Combobox(form, textvariable=var, values=["ชาย", "หญิง"], 
                                   state="readonly", width=27)
                combo.grid(row=i, column=1, padx=10, pady=8)
            else:
                ttk.Entry(form, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=8)
        
        # Info
        info_text = "ℹ️ ข้อมูลนี้จะใช้สำหรับกรอกฟอร์มจองอัตโนมัติ"
        tk.Label(self.content, text=info_text, font=("Arial", 9), 
                fg="#7f8c8d").pack(pady=15)
    
    def _step_browser_config(self):
        """Browser configuration step"""
        tk.Label(self.content, text="🌐 ตั้งค่าเบราว์เซอร์", 
                font=("Arial", 16, "bold")).pack(pady=(0, 20))
        
        # Browser selection
        browser_frame = tk.LabelFrame(self.content, text="เลือกเบราว์เซอร์หลัก", font=("Arial", 10, "bold"))
        browser_frame.pack(fill=tk.X, pady=10)
        
        self.browser_var = tk.StringVar(value="Chrome")
        ttk.Radiobutton(browser_frame, text="🔵 Google Chrome (แนะนำ)", 
                       variable=self.browser_var, value="Chrome").pack(anchor="w", padx=10, pady=5)
        ttk.Radiobutton(browser_frame, text="🔷 Microsoft Edge", 
                       variable=self.browser_var, value="Edge").pack(anchor="w", padx=10, pady=5)
        
        # Profile selection
        profile_frame = tk.LabelFrame(self.content, text="เลือก Profile", font=("Arial", 10, "bold"))
        profile_frame.pack(fill=tk.X, pady=10)
        
        self.profile_var = tk.StringVar(value="Default")
        profiles = ["Default", "Profile 1", "Profile 2", "Profile 3"]
        
        for profile in profiles:
            ttk.Radiobutton(profile_frame, text=f"📁 {profile}", 
                           variable=self.profile_var, value=profile).pack(anchor="w", padx=10, pady=2)
        
        # Auto close browser
        self.auto_close_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.content, text="ปิดเบราว์เซอร์อัตโนมัติหลังจองเสร็จ", 
                       variable=self.auto_close_var).pack(pady=10)
    
    def _step_complete(self):
        """Complete step"""
        tk.Label(self.content, text="🎉 ตั้งค่าเสร็จสิ้น!", 
                font=("Arial", 18, "bold"), fg="#27ae60").pack(pady=20)
        
        # Summary
        summary_frame = tk.LabelFrame(self.content, text="📋 สรุปการตั้งค่า", font=("Arial", 10, "bold"))
        summary_frame.pack(fill=tk.X, pady=20)
        
        summary_text = f"""
✅ ข้อมูลผู้ใช้: {self.username_var.get() if hasattr(self, 'username_var') else 'ไม่ได้ตั้งค่า'}
✅ LINE Auto Login: {'เปิดใช้งาน' if hasattr(self, 'line_auto_var') and self.line_auto_var.get() else 'ปิดใช้งาน'}
✅ โปรไฟล์ส่วนตัว: {'ตั้งค่าแล้ว' if hasattr(self, 'profile_vars') and any(v.get() for v in self.profile_vars.values()) else 'ไม่ได้ตั้งค่า'}
✅ เบราว์เซอร์: {self.browser_var.get() if hasattr(self, 'browser_var') else 'Chrome'} ({self.profile_var.get() if hasattr(self, 'profile_var') else 'Default'})
        """
        
        tk.Label(summary_frame, text=summary_text.strip(), font=("Arial", 10), 
                justify=tk.LEFT).pack(padx=10, pady=10)
        
        # Next steps
        next_frame = tk.LabelFrame(self.content, text="🚀 ขั้นตอนต่อไป", font=("Arial", 10, "bold"))
        next_frame.pack(fill=tk.X, pady=10)
        
        next_text = (
            "• คุณสามารถเริ่มใช้งานโปรแกรมได้ทันที\n"
            "• ลองใช้ 'โหมดง่าย' สำหรับการจองครั้งแรก\n"
            "• สามารถแก้ไขการตั้งค่าได้ในเมนูหลัก"
        )
        
        tk.Label(next_frame, text=next_text, font=("Arial", 9), 
                justify=tk.LEFT).pack(padx=10, pady=10)
    
    @safe_execute()
    def prev_step(self):
        """Go to previous step"""
        if self.current_step > 0:
            self._show_step(self.current_step - 1)
    
    @safe_execute()
    def next_step(self):
        """Go to next step or finish"""
        if self.current_step == 5:  # Last step
            self._save_config()
            self._finish_wizard()
        else:
            self._show_step(self.current_step + 1)
    
    def _save_config(self):
        """Save configuration"""
        try:
            config = {}
            
            # User info
            if hasattr(self, 'username_var') and self.username_var.get():
                config['user'] = {
                    'username': self.username_var.get(),
                    'password': self.password_var.get() if self.auto_login_var.get() else '',
                    'auto_login': self.auto_login_var.get()
                }
            
            # LINE config
            if hasattr(self, 'line_email_var') and self.line_email_var.get():
                config['line'] = {
                    'email': self.line_email_var.get(),
                    'password': self.line_password_var.get(),
                    'auto_login': self.line_auto_var.get()
                }
            
            # Profile config
            if hasattr(self, 'profile_vars'):
                profile_data = {k: v.get() for k, v in self.profile_vars.items() if v.get()}
                if profile_data:
                    config['profile'] = profile_data
            
            # Browser config
            if hasattr(self, 'browser_var'):
                config['browser'] = {
                    'type': self.browser_var.get(),
                    'profile': self.profile_var.get(),
                    'auto_close': self.auto_close_var.get()
                }
            
            # Save to file
            config_dir = Path.home() / ".newbies_bot"
            config_dir.mkdir(exist_ok=True)
            
            config_file = config_dir / "wizard_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # Mark wizard as completed
            (config_dir / "wizard_completed").touch()
            
            logger.info("Configuration wizard completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            messagebox.showerror("ข้อผิดพลาด", f"บันทึกการตั้งค่าไม่สำเร็จ: {e}")
    
    def _finish_wizard(self):
        """Finish wizard and start main app"""
        messagebox.showinfo("เสร็จสิ้น", 
                           "🎉 ตั้งค่าเสร็จสิ้น!\n\n"
                           "โปรแกรมจะเริ่มทำงานในอีกสักครู่...")
        
        self.destroy()
        
        # Start main app
        from gui_app import StartMenu
        StartMenu().mainloop()

def should_show_wizard():
    """Check if wizard should be shown"""
    config_dir = Path.home() / ".newbies_bot"
    return not (config_dir / "wizard_completed").exists()

def main():
    """Main function"""
    if should_show_wizard():
        ConfigWizard().mainloop()
    else:
        from gui_app import StartMenu
        StartMenu().mainloop()

if __name__ == "__main__":
    main()