# simple_mode.py - Simple UI for beginners
import tkinter as tk
from tkinter import ttk, messagebox
from window_manager import window_manager
from error_handler import safe_execute
from logger_config import get_logger

logger = get_logger()

class SimpleModeWindow(tk.Tk):
    def __init__(self, user_info, api_data):
        super().__init__()
        self.user_info = user_info
        self.api_data = api_data
        self.title("โหมดง่าย - จองแบบเรียบง่าย")
        self.geometry("450x650")
        self.resizable(False, False)
        
        # Main container
        main = ttk.Frame(self, padding=(20, 20))
        main.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = tk.Label(main, text="🎯 จองง่ายๆ ใน 3 ขั้นตอน", 
                        font=("Arial", 16, "bold"), fg="#2c3e50")
        title.pack(pady=(0, 20))
        
        # Step 1: Branch
        self._create_step(main, "1️⃣ เลือกสาขา", self._create_branch_section)
        
        # Step 2: Date & Time  
        self._create_step(main, "2️⃣ เลือกวันและเวลา", self._create_datetime_section)
        
        # Step 3: Start
        self._create_step(main, "3️⃣ เริ่มจอง", self._create_action_section)
        
        # Additional info section
        info_section = ttk.LabelFrame(main, text="📝 ข้อมูลเพิ่มเติม", padding=(15, 10))
        info_section.pack(fill=tk.X, pady=(0, 15))
        
        info_text = (
            "• โหมดนี้จะใช้ Chrome Profile Default\n"
            "• จะกด Register และ Confirm อัตโนมัติ\n"
            "• หากต้องการตั้งค่าเพิ่มเติม ใช้โหมดขั้นสูง"
        )
        tk.Label(info_section, text=info_text, font=("Arial", 9), 
                fg="#34495e", justify=tk.LEFT).pack(anchor="w")
        
        # Bottom buttons
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.X, pady=(20, 0))
        
        # Center the buttons
        button_frame = ttk.Frame(bottom)
        button_frame.pack(expand=True)
        
        ttk.Button(button_frame, text="โหมดขั้นสูง", 
                  command=self.switch_to_advanced, width=20).pack(side=tk.LEFT, padx=10, pady=5)
        ttk.Button(button_frame, text="ย้อนกลับ", 
                  command=self.on_back, width=20).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Info text below buttons
        info_text = tk.Label(bottom, text="📝 โหมดนี้เหมาะสำหรับผู้ใช้ที่เพิ่งเริ่มต้น", 
                         font=("Arial", 9), fg="#7f8c8d")
        info_text.pack(pady=(10, 0))
    
    def _create_step(self, parent, title, content_func):
        """สร้าง step container"""
        frame = ttk.LabelFrame(parent, text=title, padding=(15, 10))
        frame.pack(fill=tk.X, pady=(0, 15))
        content_func(frame)
        return frame
    
    def _create_branch_section(self, parent):
        """Step 1: Branch selection"""
        branches = self.api_data.get("branchs", [])
        
        self.branch_var = tk.StringVar()
        branch_combo = ttk.Combobox(parent, textvariable=self.branch_var, 
                                   values=branches, state="readonly", 
                                   font=("Arial", 12), width=25)
        branch_combo.pack(pady=5)
        
        if branches:
            self.branch_var.set(branches[0])
        
        # Hint
        hint = tk.Label(parent, text="💡 เลือกสาขาที่ต้องการจอง", 
                       font=("Arial", 9), fg="#7f8c8d")
        hint.pack()
    
    def _create_datetime_section(self, parent):
        """Step 2: Date & Time selection"""
        # Date
        date_frame = ttk.Frame(parent)
        date_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(date_frame, text="วันที่:", font=("Arial", 11)).pack(side=tk.LEFT)
        self.day_var = tk.StringVar(value="1")
        day_combo = ttk.Combobox(date_frame, textvariable=self.day_var,
                                values=[str(i) for i in range(1, 32)], 
                                state="readonly", width=8)
        day_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        # Time
        time_frame = ttk.Frame(parent)
        time_frame.pack(fill=tk.X)
        
        tk.Label(time_frame, text="เวลา:", font=("Arial", 11)).pack(side=tk.LEFT)
        times = self.api_data.get("times", [])
        self.time_var = tk.StringVar()
        time_combo = ttk.Combobox(time_frame, textvariable=self.time_var,
                                 values=times, state="readonly", width=15)
        time_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        if times:
            self.time_var.set(times[0])
    
    def _create_action_section(self, parent):
        """Step 3: Action buttons"""
        # Big start button
        start_btn = tk.Button(parent, text="🚀 เริ่มจอง", 
                             font=("Arial", 14, "bold"),
                             bg="#27ae60", fg="white",
                             command=self.start_simple_booking,
                             height=2, width=25)
        start_btn.pack(pady=15)
        
        # Status
        self.status_var = tk.StringVar(value="พร้อมเริ่มจอง")
        status_label = tk.Label(parent, textvariable=self.status_var,
                               font=("Arial", 11, "bold"), fg="#2c3e50")
        status_label.pack(pady=5)
    
    @safe_execute()
    def start_simple_booking(self):
        """เริ่มจองแบบง่าย"""
        branch = self.branch_var.get()
        day = self.day_var.get()
        time = self.time_var.get()
        
        if not all([branch, day, time]):
            messagebox.showwarning("ข้อมูลไม่ครบ", "กรุณาเลือกสาขา วัน และเวลา")
            return
        
        self.status_var.set("กำลังเริ่มจอง...")
        
        # Import และเรียกใช้ booking process
        from gui_app import BookingProcessWindow
        from chrome_op import launch_chrome_instance
        
        try:
            # เปิด Chrome profile default
            port, _ = launch_chrome_instance("Default")
            if not port:
                messagebox.showerror("ข้อผิดพลาด", "เปิด Chrome ไม่ได้")
                return
            
            # เริ่ม booking process
            self.destroy()  # ปิด Simple Mode window
            BookingProcessWindow(
                parent_window_class=SimpleModeWindow,
                user_info=self.user_info,
                mode="live",
                site_name="ROCKETBOOKING", 
                browser_type="Chrome",
                all_api_data=self.api_data,
                selected_branch=branch,
                selected_day=day,
                selected_time=time,
                register_by_user=False,  # Auto register
                confirm_by_user=False,   # Auto confirm
                cdp_port=port
            ).mainloop()
            
        except Exception as e:
            logger.error(f"Simple booking failed: {e}")
            messagebox.showerror("ข้อผิดพลาด", f"เริ่มจองไม่ได้: {e}")
            self.status_var.set("พร้อมเริ่มจอง")
    
    @safe_execute()
    def switch_to_advanced(self):
        """เปลี่ยนไปโหมดขั้นสูง"""
        from gui_app import LiveModeWindow
        self.destroy()
        LiveModeWindow(user_info=self.user_info, api_data=self.api_data).mainloop()
    
    @safe_execute()
    def on_back(self):
        """ย้อนกลับหน้าหลัก"""
        from gui_app import App
        self.destroy()
        App(self.user_info).mainloop()