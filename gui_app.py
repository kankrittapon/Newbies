import tkinter as tk
from tkinter import ttk, messagebox
from chrome_op import launch_chrome_instance as launch_chrome_with_profile
from edge_op import launch_edge_with_profile
from utils import get_all_api_data, google_sheet_check_login
import threading
import asyncio
import time
import json
import traceback
from real_booking import perform_real_booking, attach_to_chrome
from playwright_ops import launch_browser_and_perform_booking as trial_booking
from playwright.async_api import async_playwright
from Scheduledreal_booking import ScheduledManager
from utils import get_all_api_data, google_sheet_check_login, setup_config_files
from Scroll_ import ScrollableFrame

profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"]
browsers = ["Chrome", "Edge"]
LIVE_SITES = ["ROCKETBOOKING"]
TRIAL_SITES = ["EZBOT", "PMROCKET"]
days = [str(i) for i in range(1, 32)]

class BookingProcessWindow(tk.Tk):
    def __init__(self, parent_window_class, user_info, mode, site_name, browser_type, all_api_data, selected_branch, selected_day, selected_time, register_by_user, confirm_by_user, cdp_port=None):
        print(f"DEBUG: Creating BookingProcessWindow for mode '{mode}'...")
        super().__init__()
        self.parent_window_class = parent_window_class
        self.user_info = user_info
        self.all_api_data = all_api_data
        
        self.title("สถานะการจอง")
        self.geometry("450x450")
        self.resizable(False, False)

        self.mode = mode 
        self.site_name = site_name
        self.browser_type = browser_type
        self.selected_branch = selected_branch
        self.selected_day = selected_day
        self.selected_time = selected_time
        self.register_by_user = register_by_user
        self.confirm_by_user = confirm_by_user
        self.cdp_port = cdp_port
        
        self.thread = None
        self._async_loop = None

        main_frame = ttk.Frame(self, padding=(10, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.status_text = tk.Text(main_frame, wrap="word", font=("Arial", 10), height=15)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        self.ok_btn = ttk.Button(button_frame, text="ตกลง", command=self.on_ok, state=tk.DISABLED)
        self.ok_btn.pack(side=tk.LEFT, padx=5)

        self.cancel_btn = ttk.Button(button_frame, text="ยกเลิก", command=self.on_cancel, state=tk.NORMAL)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.start_booking_process()
        print("DEBUG: BookingProcessWindow created successfully.")

    def update_status(self, message):
        def inner():
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)
        self.after(0, inner)

    def start_booking_process(self):
        self.thread = threading.Thread(target=self._run_async_booking, daemon=True)
        self.thread.start()

    def _run_async_booking(self):
        self._async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._async_loop)
        
        try:
            main_task = self._async_loop.create_task(
                self._run_live_booking() if self.mode == "live" else self._run_trial_booking()
            )
            self._async_loop.run_until_complete(asyncio.wait_for(main_task, timeout=300))
        except asyncio.TimeoutError:
            self.update_status("❌ การจองหมดเวลา! อาจมีปัญหาเกิดขึ้น")
        except Exception as e:
            self.update_status(f"❌ เกิดข้อผิดพลาดที่ไม่คาดคิดใน Thread: {e}")
            traceback.print_exc()
        finally:
            self.update_status("🟢 กระบวนการสิ้นสุดแล้ว")
            self.after(0, lambda: self.ok_btn.config(state=tk.NORMAL))
            if self._async_loop and not self._async_loop.is_closed():
                self._async_loop.close()

    async def _run_live_booking(self):
        playwright = None
        try:
            self.update_status("⏳ กำลังรอเชื่อมต่อกับเบราว์เซอร์ที่เปิดอยู่...")
            playwright, browser, context, page = await attach_to_chrome(self.cdp_port)
            self.update_status("✅ เชื่อมต่อกับเบราว์เซอร์สำเร็จ!")

            await perform_real_booking(
                page=page,
                all_api_data=self.all_api_data,
                site_name=self.site_name,
                selected_branch=self.selected_branch,
                selected_day=self.selected_day,
                selected_time=self.selected_time,
                register_by_user=self.register_by_user,
                confirm_by_user=self.confirm_by_user,
                progress_callback=self.update_status
            )
        except asyncio.CancelledError:
            self.update_status("🚨 Task ถูกยกเลิก")
        except Exception as e:
            self.update_status(f"❌ เกิดข้อผิดพลาดในการจอง: {e}")
            traceback.print_exc()
        finally:
            if playwright:
                await playwright.stop()
            if self._async_loop and not self._async_loop.is_closed():
                self._async_loop.create_task(asyncio.sleep(0)).cancel()

    async def _run_trial_booking(self):
        try:
            await trial_booking(
                browser_type=self.browser_type,
                site_name=self.site_name,
                all_api_data=self.all_api_data,
                selected_branch_name=self.selected_branch,
                selected_day=self.selected_day,
                selected_time_value=self.selected_time,
                progress_callback=self.update_status
            )
        except asyncio.CancelledError:
            self.update_status("🚨 Task ถูกยกเลิก")
        except Exception as e:
            self.update_status(f"❌ เกิดข้อผิดพลาดในการทดลองจอง: {e}")
            traceback.print_exc()
        finally:
            if self._async_loop and not self._async_loop.is_closed():
                self._async_loop.create_task(asyncio.sleep(0)).cancel()

    def on_ok(self):
        self.destroy()
        self.parent_window_class(user_info=self.user_info, all_api_data=self.all_api_data).mainloop()

    def on_cancel(self):
        if self._async_loop and self._async_loop.is_running():
            self.update_status("🚨 กำลังยกเลิกการทำงาน...")
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
            self.thread.join(timeout=2)
        messagebox.showinfo("ยกเลิก", "การจองถูกยกเลิกแล้ว")
        self.destroy()
        self.parent_window_class(user_info=self.user_info, all_api_data=self.all_api_data).mainloop()

class SingleBookingWindow(tk.Tk):
    def __init__(self, user_info, all_api_data):
        print("DEBUG: Creating SingleBookingWindow...")
        super().__init__()
        self.user_info = user_info
        self.all_api_data = all_api_data
        self.title("จองทีละครั้ง")
        self.geometry("400x650")
        self.resizable(False, False)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        main_frame = ttk.Frame(self, padding=(10, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text="เลือก Site:", font=("Arial", 12)).pack(pady=(10, 3))
        self.site_var = tk.StringVar(value=LIVE_SITES[0])
        self.site_combo = ttk.Combobox(main_frame, values=LIVE_SITES, textvariable=self.site_var, state="readonly", font=("Arial", 11))
        self.site_combo.pack(pady=5)
        self.site_combo.bind("<<ComboboxSelected>>", self.on_site_selected)

        tk.Label(main_frame, text="เลือก Browser:", font=("Arial", 12)).pack(pady=(10, 3))
        self.browser_var = tk.StringVar(value=browsers[0])
        self.browser_combo = ttk.Combobox(main_frame, values=browsers, textvariable=self.browser_var, state="readonly", font=("Arial", 11))
        self.browser_combo.pack(pady=5)
        self.browser_combo.bind("<<ComboboxSelected>>", self.on_browser_selected)

        tk.Label(main_frame, text="เลือก Profile:", font=("Arial", 12)).pack(pady=(10, 3))
        self.profile_var = tk.StringVar(value=profiles[0])
        self.profile_combo = ttk.Combobox(main_frame, values=profiles, textvariable=self.profile_var, state="readonly", font=("Arial", 11))
        self.profile_combo.pack(pady=5)

        tk.Label(main_frame, text="เลือก Branch:", font=("Arial", 12)).pack(pady=(10, 3))
        self.branch_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(main_frame, textvariable=self.branch_var, state="readonly", font=("Arial", 11))
        self.branch_combo.pack(pady=5)

        tk.Label(main_frame, text="เลือกวัน:", font=("Arial", 12)).pack(pady=(10, 3))
        self.day_var = tk.StringVar(value=days[0])
        self.day_combo = ttk.Combobox(main_frame, values=days, textvariable=self.day_var, state="readonly", font=("Arial", 11))
        self.day_combo.pack(pady=5)

        tk.Label(main_frame, text="เลือก Time:", font=("Arial", 12)).pack(pady=(10, 3))
        self.time_var = tk.StringVar()
        self.time_combo = ttk.Combobox(main_frame, textvariable=self.time_var, state="readonly", font=("Arial", 11))
        self.time_combo.pack(pady=5)
        
        self.register_var = tk.BooleanVar()
        self.register_check = ttk.Checkbutton(main_frame, text="กดปุ่ม Register ด้วยตัวเอง", variable=self.register_var)
        self.register_check.pack(pady=(10, 5))

        self.confirm_var = tk.BooleanVar()
        self.confirm_check = ttk.Checkbutton(main_frame, text="กดปุ่ม Confirm Booking ด้วยตัวเอง", variable=self.confirm_var)
        self.confirm_check.pack(pady=5)
        
        line_frame = ttk.Frame(main_frame)
        line_frame.pack(pady=10)
        
        check_line_login_btn = ttk.Button(line_frame, text="ตรวจสอบการ Login LINE", command=self.on_check_line_login)
        check_line_login_btn.pack(side=tk.LEFT, padx=5)

        line_settings_btn = ttk.Button(line_frame, text="ตั้งค่า Login LINE", command=self.on_line_settings)
        line_settings_btn.pack(side=tk.LEFT, padx=5)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(pady=20)
        
        self.start_booking_btn = ttk.Button(control_frame, text="เริ่มการจอง", command=self.on_start_booking)
        self.start_booking_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(control_frame, text="ย้อนกลับ", command=self.on_cancel)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        self.on_site_selected()
        print("DEBUG: SingleBookingWindow created successfully.")

    def enable_start_button(self):
        self.start_booking_btn.config(state=tk.NORMAL)

    def on_browser_selected(self, event=None):
        selected_browser = self.browser_var.get()
        if selected_browser == "Edge":
            self.profile_combo['values'] = ["Default"]
            self.profile_var.set("Default")
            self.profile_combo.config(state="readonly")
        else:
            self.profile_combo['values'] = profiles
            self.profile_var.set(profiles[0])
            self.profile_combo.config(state="readonly")

    def on_site_selected(self, event=None):
        branches = self.all_api_data.get("branchs", [])
        times = self.all_api_data.get("times", [])
        
        branch_names = branches
        self.branch_combo['values'] = branch_names
        if branch_names:
            self.branch_var.set(branch_names[0])
        else:
            self.branch_var.set("")

        time_values = times
        self.time_combo['values'] = time_values
        if time_values:
            self.time_var.set(time_values[0])
        else:
            self.time_var.set("")
        
        self.day_combo['values'] = days
        self.day_var.set(days[0])

    def on_start_booking(self):
        selected_site = self.site_var.get()
        selected_browser = self.browser_var.get()
        selected_profile = self.profile_var.get()
        selected_branch = self.branch_var.get()
        selected_day = self.day_var.get()
        selected_time = self.time_var.get()
        register_by_user = self.register_var.get()
        confirm_by_user = self.confirm_var.get()
        
        if not selected_site or not selected_browser or not selected_profile or not selected_branch or not selected_day or not selected_time:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Site, Browser, Profile, Branch, วัน และ เวลา ให้ครบถ้วน!")
            return
        
        try:
            launched_port = None
            if selected_browser == "Chrome":
                launched_port, _ = launch_chrome_with_profile(selected_profile)
            elif selected_browser == "Edge":
                launched_port, _ = launch_edge_with_profile(selected_profile)
        
            if not launched_port:
                messagebox.showerror("Error", "ไม่สามารถเปิดเบราว์เซอร์ได้")
                return
        
            self.destroy()
            BookingProcessWindow(
                parent_window_class=SingleBookingWindow, 
                user_info=self.user_info,
                mode="live", 
                site_name=selected_site, 
                browser_type=selected_browser, 
                all_api_data=self.all_api_data, 
                selected_branch=selected_branch, 
                selected_day=selected_day, 
                selected_time=selected_time, 
                register_by_user=register_by_user, 
                confirm_by_user=confirm_by_user, 
                cdp_port=launched_port
            ).mainloop()
        except Exception as e:
            messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการเปิดหน้าต่างจอง: {e}")
            App(user_info=self.user_info).mainloop()
    
    def on_cancel(self):
        self.destroy()
        LiveModeWindow(user_info=self.user_info, api_data=self.api_data).mainloop()

    def on_check_line_login(self):
        messagebox.showinfo("ตรวจสอบการ Login LINE", "ฟังก์ชันตรวจสอบสถานะการ Login LINE")

    def on_line_settings(self):
        messagebox.showinfo("ตั้งค่า Login LINE", "ฟังก์ชันตั้งค่า Login LINE")

class ApiStatusPopup(tk.Tk):
    def __init__(self, user_info):
        print("DEBUG: Creating ApiStatusPopup...")
        super().__init__()
        self.user_info = user_info
        self.title("สถานะ Config")
        self.geometry("400x300")
        self.resizable(False, False)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.text = tk.Text(self, wrap="word", font=("Arial", 12))
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        back_btn = ttk.Button(self, text="ย้อนกลับ", command=self.on_close)
        back_btn.pack(pady=5)

        threading.Thread(target=self.load_api_status, daemon=True).start()
        print("DEBUG: ApiStatusPopup created successfully.")

    def load_api_status(self):
        self.text.insert(tk.END, "กำลังโหลดข้อมูล ......\n")
        try:
            results = get_all_api_data()
        except Exception as e:
            self.text.insert(tk.END, f"❌ เกิดข้อผิดพลาดในการโหลด ...:\n{e}\n")
            return

        self.text.delete("1.0", tk.END)
        for api_name, data in results.items():
            if isinstance(data, str) and data.startswith("Error"):
                status = "❌ โหลดไม่สำเร็จ"
            else:
                status = "✅ โหลดสำเร็จ"
            self.text.insert(tk.END, f"{api_name} : {status}\n")

    def on_close(self):
        self.destroy()
        App(user_info=self.user_info).mainloop()

class LiveModeWindow(tk.Tk):
    def __init__(self, user_info, api_data):  # เพิ่ม api_data เป็นพารามิเตอร์
        print("DEBUG: Creating LiveModeWindow...")
        super().__init__()
        self.user_info = user_info
        self.api_data = api_data
        self.title("โหมดใช้งานจริง")
        self.geometry("300x200")
        self.resizable(False, False)
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        tk.Label(self, text="เลือกประเภทการจอง:", font=("Arial", 12)).pack(pady=(20, 10))

        single_booking_btn = ttk.Button(self, text="จองทีละครั้ง", command=self.on_single_booking)
        single_booking_btn.pack(pady=5)

        scheduled_booking_btn = ttk.Button(self, text="จองล่วงหน้า (schedule)", command=self.on_scheduled_booking)
        scheduled_booking_btn.pack(pady=5)
        
        back_btn = ttk.Button(self, text="ย้อนกลับ", command=self.on_cancel)
        back_btn.pack(pady=5)
        print("DEBUG: LiveModeWindow created successfully.")

    def on_single_booking(self):
        if not self.api_data:
            messagebox.showerror("Error", "ข้อมูล API ยังไม่พร้อมใช้งาน")
            return
        self.destroy()
        SingleBookingWindow(user_info=self.user_info, all_api_data=self.api_data).mainloop()

    def on_scheduled_booking(self):
        can_use_scheduler = self.user_info.get('ตั้งจองล่วงหน้าได้ไหม', 'ไม่') == 'ใช่'
        if not can_use_scheduler:
            messagebox.showerror("ข้อผิดพลาด", "คุณไม่มีสิทธิ์ในการเข้าใช้งานโหมดจองล่วงหน้า")
            return

        if not self.api_data:
            messagebox.showerror("Error", "ข้อมูล API ยังไม่พร้อมใช้งาน")
            return

        self.destroy()
        ScheduledBookingWindow(user_info=self.user_info, all_api_data=self.api_data).mainloop()
    def on_cancel(self):
        self.destroy()
        App(user_info=self.user_info, api_data=self.api_data).mainloop()

class ScheduledBookingWindow(tk.Tk):
    def __init__(self, user_info, all_api_data):
        super().__init__()
        self.user_info = user_info
        self.all_api_data = all_api_data
        self.title("จองล่วงหน้า (schedule)")
        self.geometry("1000x750")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        max_scheduled = int(self.user_info.get('สามาถตั้งจองล่วงหน้าได้กี่ site', 0))
        # ตัวจัดการ Task จองล่วงหน้า
        self.manager = ScheduledManager(all_api_data=self.all_api_data, progress_callback=self.update_status)
            # สร้าง ScrollableFrame และแพ็คเต็มหน้าต่าง
        self.scrollable = ScrollableFrame(self)
        self.scrollable.pack(fill="both", expand=True)
        main_frame = self.scrollable.scrollable_frame
        tk.Label(main_frame, text=f"ตั้งค่าการจองล่วงหน้า (สูงสุด {max_scheduled} รายการ)", font=("Arial", 16, "bold")).pack(pady=(0, 10))

        # เฟรมสำหรับเพิ่ม Task ใหม่
        control_frame = ttk.LabelFrame(main_frame, text="เพิ่มการจองใหม่", padding=(10, 5))
        control_frame.pack(fill="x", pady=10)

        # ตัวแปรเก็บค่าจาก input ต่างๆ
        self.site_var = tk.StringVar(value=LIVE_SITES[0])
        self.browser_var = tk.StringVar(value=browsers[0])
        self.profile_var = tk.StringVar(value=profiles[0])
        self.branch_var = tk.StringVar()
        self.day_var = tk.StringVar(value=days[0])
        self.time_var = tk.StringVar()
        self.line_email_var = tk.StringVar()
        # ลบ self.line_password_var ออก

        # ส่วน dropdown และ label
        ttk.Label(control_frame, text="Site:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(control_frame, values=LIVE_SITES, textvariable=self.site_var, state="readonly").grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="Browser:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Combobox(control_frame, values=browsers, textvariable=self.browser_var, state="readonly").grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(control_frame, text="Profile:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(control_frame, values=profiles[:max_scheduled], textvariable=self.profile_var, state="readonly").grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="Branch:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.branch_combo = ttk.Combobox(control_frame, textvariable=self.branch_var, state="readonly")
        self.branch_combo.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(control_frame, text="Day:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(control_frame, values=days, textvariable=self.day_var, state="readonly").grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="Time:").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        self.time_combo = ttk.Combobox(control_frame, textvariable=self.time_var, state="readonly")
        self.time_combo.grid(row=2, column=3, padx=5, pady=5)

        # แก้ไข UI: เปลี่ยนจาก Entry เป็น Combobox สำหรับ LINE Email
        #ttk.Label(control_frame, text="LINE Email:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        #self.line_email_combo = ttk.Combobox(control_frame, textvariable=self.line_email_var, state="readonly")
        #self.line_email_combo.grid(row=3, column=1, padx=5, pady=5)
        # ลบ Label และ Entry สำหรับ LINE Password ออกไป
        ttk.Label(control_frame, text="LINE Email:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.line_email_combo = ttk.Combobox(control_frame, textvariable=self.line_email_var, state="readonly")
        self.line_email_combo.grid(row=3, column=1, padx=5, pady=5)
        
        add_btn = ttk.Button(control_frame, text="เพิ่ม Task", command=self.add_task)
        add_btn.grid(row=4, column=0, columnspan=4, padx=5, pady=5, sticky="we")

        # ส่วนแสดงรายการ Task ที่ตั้งไว้
        list_frame = ttk.LabelFrame(main_frame, text="รายการจองที่ตั้งเวลาไว้", padding=(10, 5))
        list_frame.pack(fill="both", expand=True, pady=10)

        self.task_tree = ttk.Treeview(list_frame, columns=("TaskID", "Site", "Branch", "Day", "Time", "Profile", "LINE Email", "Status"), show="headings")
        self.task_tree.heading("TaskID", text="ID", anchor="w")
        self.task_tree.column("TaskID", width=80)
        self.task_tree.heading("Site", text="Site", anchor="w")
        self.task_tree.column("Site", width=100)
        self.task_tree.heading("Branch", text="Branch", anchor="w")
        self.task_tree.column("Branch", width=150)
        self.task_tree.heading("Day", text="Day", anchor="w")
        self.task_tree.column("Day", width=50)
        self.task_tree.heading("Time", text="Time", anchor="w")
        self.task_tree.column("Time", width=80)
        self.task_tree.heading("Profile", text="Profile", anchor="w")
        self.task_tree.column("Profile", width=100)
        self.task_tree.heading("LINE Email", text="LINE Email", anchor="w")
        self.task_tree.column("LINE Email", width=200)
        self.task_tree.heading("Status", text="Status", anchor="w")
        self.task_tree.column("Status", width=100)
        self.task_tree.pack(fill="both", expand=True)

        # ปุ่มควบคุม Task
        task_control_frame = ttk.Frame(list_frame)
        task_control_frame.pack(pady=5)
        ttk.Button(task_control_frame, text="ลบ", command=self.remove_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(task_control_frame, text="แก้ไข", command=self.edit_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(task_control_frame, text="ล้างทั้งหมด", command=self.clear_all_tasks).pack(side=tk.LEFT, padx=5)

        # ปุ่มควบคุม Line Credentials
        line_cred_frame = ttk.Frame(list_frame)
        line_cred_frame.pack(pady=5)
        ttk.Button(line_cred_frame, text="เพิ่ม/แก้ไข LINE Credentials", command=self.add_line_credentials).pack(side=tk.LEFT, padx=5)
    
        # เพิ่ม Label และ Combobox สำหรับเลือก LINE Email ที่จะลบ
        ttk.Label(line_cred_frame, text="เลือก LINE Email ที่จะลบ:").pack(side=tk.LEFT, padx=5)
        self.line_email_remove_var = tk.StringVar()
        self.line_email_remove_combo = ttk.Combobox(line_cred_frame, textvariable=self.line_email_remove_var, state="readonly")
        self.line_email_remove_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(line_cred_frame, text="ลบ (LINE)", command=self.remove_line_credentials).pack(side=tk.LEFT, padx=5)
        
        # ส่วนแสดงสถานะการทำงาน
        status_frame = ttk.LabelFrame(main_frame, text="สถานะการทำงาน", padding=(10, 5))
        status_frame.pack(fill="x", pady=10)

        self.status_text = tk.Text(status_frame, wrap="word", font=("Arial", 11), height=5)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.config(state=tk.DISABLED)

        # ปุ่มควบคุม Scheduler
        overall_control_frame = ttk.Frame(main_frame)
        overall_control_frame.pack(pady=10)

        self.start_btn = ttk.Button(overall_control_frame, text="เริ่ม Scheduler", command=self.start_scheduler)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(overall_control_frame, text="หยุด Scheduler ทั้งหมด", command=self.stop_scheduler, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(overall_control_frame, text="ย้อนกลับ", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

        self.update_combobox_data()
        self.update_line_email_choices()
        self.update_line_email_remove_choices()
        self.refresh_task_list()

    def update_combobox_data(self):
        branches = self.all_api_data.get("branchs", [])
        times = self.all_api_data.get("times", [])

        self.branch_combo['values'] = branches
        if branches:
            self.branch_var.set(branches[0])

        self.time_combo['values'] = times
        if times:
            self.time_var.set(times[0])

    def update_line_email_choices(self):
        line_data = self.manager.load_line_credentials()
        email_list = list(line_data.keys())
        self.line_email_combo['values'] = email_list
        if email_list:
            self.line_email_var.set(email_list[0])
        else:
            self.line_email_var.set("")

    def update_line_email_remove_choices(self):
        line_data = self.manager.load_line_credentials()
        email_list = list(line_data.keys())
        self.line_email_remove_combo['values'] = email_list
        if email_list:
            self.line_email_remove_var.set(email_list[0])
        else:
            self.line_email_remove_var.set("")

    def update_status(self, message):
        def inner():
            if not self.winfo_exists():
            # ถ้าหน้าต่างถูกปิดไปแล้ว ไม่ต้องทำอะไร
                return
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)
            self.refresh_task_list()
        self.after(0, inner)

    def refresh_task_list(self):
        self.task_tree.delete(*self.task_tree.get_children())
        for task in self.manager.tasks:
            task_data = task.task_data
            self.task_tree.insert("", "end", iid=task.id,
                                  values=(task.id[:4], task_data.get('site_name', '-'), task_data.get('selected_branch', '-'),
                                          task_data.get('selected_day', '-'), task_data.get('selected_time', '-'),
                                          task_data.get('profile', '-'), task_data.get('line_email', '-'), task.status))

    def add_task(self):
        max_scheduled = int(self.user_info.get('สามาถตั้งจองล่วงหน้าได้กี่ site', 0))
        if len(self.manager.tasks) >= max_scheduled:
            messagebox.showwarning("คำเตือน", f"คุณเพิ่ม Task ได้สูงสุดเพียง {max_scheduled} รายการเท่านั้น")
            return

        # แก้ไข: ตรวจสอบว่าเลือก LINE Email แล้วหรือไม่
        selected_line_email = self.line_email_var.get()

        if not selected_line_email:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก LINE Email")
            return
        used_emails = [t.task_data.get('line_email') for t in self.manager.tasks]
        if selected_line_email in used_emails:
            messagebox.showwarning("คำเตือน", "LINE Email นี้ถูกใช้ใน Task อื่นแล้ว")
            return
            
        line_data = self.manager.load_line_credentials()
        line_password = line_data.get(selected_line_email)
        if not line_password:
            messagebox.showwarning("คำเตือน", "ไม่พบ Password สำหรับ LINE Email ที่เลือก")
            return

        task_data = {
            "site_name": self.site_var.get(),
            "browser_type": self.browser_var.get(),
            "profile": self.profile_var.get(),
            "selected_branch": self.branch_var.get(),
            "selected_day": self.day_var.get(),
            "selected_time": self.time_var.get(),
            "line_email": selected_line_email,
            "line_password": line_password
        }

        # แก้ไข: ตรวจสอบเฉพาะข้อมูลที่จำเป็น
        if not all([task_data.get('site_name'), task_data.get('browser_type'), task_data.get('profile'),
                    task_data.get('selected_branch'), task_data.get('selected_day'),
                    task_data.get('selected_time')]):
            messagebox.showwarning("คำเตือน", "กรุณากรอกข้อมูลให้ครบถ้วน")
            return

        self.manager.add_booking(task_data)
        self.refresh_task_list()

    def remove_task(self):
        selected_item = self.task_tree.focus()
        print(f"DEBUG: Selected item is '{selected_item}'")
        if not selected_item:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Task ที่ต้องการลบ")
            return

        task_id = selected_item
        print(f"DEBUG: Task ID is '{task_id}'")
        self.manager.remove_booking(task_id)
        self.refresh_task_list()

    def edit_task(self):
        selected_item = self.task_tree.focus()
        if not selected_item:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Task ที่ต้องการแก้ไข")
            return

        task_id = selected_item
        task = next((t for t in self.manager.tasks if t.id == task_id), None)
        if not task:
            messagebox.showwarning("คำเตือน", "ไม่พบ Task ที่เลือก")
            return

        self.site_var.set(task.task_data.get('site_name', ''))
        self.browser_var.set(task.task_data.get('browser_type', ''))
        self.profile_var.set(task.task_data.get('profile', ''))
        self.branch_var.set(task.task_data.get('selected_branch', ''))
        self.day_var.set(task.task_data.get('selected_day', ''))
        self.time_var.set(task.task_data.get('selected_time', ''))
        self.line_email_var.set(task.task_data.get('line_email', ''))

        self.manager.remove_booking(task_id)
        self.refresh_task_list()
        messagebox.showinfo("สถานะ", "ข้อมูลถูกย้ายไปที่ช่องกรอกด้านบนแล้ว กรุณากด 'เพิ่ม Task' เพื่อบันทึก")
    
    def add_line_credentials(self):
        win = LineCredentialsWindow(manager=self.manager)
        self.wait_window(win)
        self.update_line_email_choices()

    def remove_line_credentials(self):
        selected_email = self.line_email_remove_var.get()
        if not selected_email:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกบัญชี LINE ที่ต้องการลบ")
            return
    
        confirm = messagebox.askyesno("ยืนยันการลบ", f"คุณต้องการลบบัญชี LINE '{selected_email}' ใช่หรือไม่?")
        if confirm:
            self.manager.remove_line_credentials_by_email(selected_email)
            self.refresh_task_list()
            self.update_line_email_choices()
            self.line_email_remove_var.set("")  # เคลียร์ selection
            messagebox.showinfo("สถานะ", f"ลบบัญชี LINE '{selected_email}' เรียบร้อยแล้ว")   
   
    def clear_all_tasks(self):
        confirm = messagebox.askyesno("ยืนยัน", "คุณต้องการล้าง Task ทั้งหมดใช่หรือไม่?")
        if confirm:
            self.manager.clear_all_tasks()
            self.refresh_task_list()

    def start_scheduler(self):
        self.manager.start_scheduler()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

    def stop_scheduler(self):
        self.manager.stop_scheduler()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def on_cancel(self):
        self.manager.stop_scheduler()
        self.destroy()
        LiveModeWindow(user_info=self.user_info, api_data=self.api_data).mainloop()
        # เรียก LiveModeWindow หรือหน้าหลักอื่น ๆ ต่อไป

class LineCredentialsWindow(tk.Tk):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.title("ตั้งค่า LINE Credentials")
        self.geometry("500x350")
        self.resizable(False, False)

        # โหลดข้อมูลจากไฟล์เดียว
        self.line_data = self.manager.load_line_credentials()

        main_frame = ttk.Frame(self, padding=(10, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="เพิ่ม/แก้ไขบัญชี LINE", padding=(10, 5))
        input_frame.pack(fill="x", pady=5)

        ttk.Label(input_frame, text="LINE Email:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.email_var = tk.StringVar()
        self.email_entry = ttk.Entry(input_frame, textvariable=self.email_var, width=30)
        self.email_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(input_frame, text="LINE Password:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(input_frame, textvariable=self.password_var, show="*", width=30)
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        save_btn = ttk.Button(button_frame, text="บันทึก", command=self.on_save)
        save_btn.pack(side=tk.LEFT, padx=5)

        clear_btn = ttk.Button(button_frame, text="ล้างข้อมูล", command=self.on_clear_input)
        clear_btn.pack(side=tk.LEFT, padx=5)

        list_frame = ttk.LabelFrame(main_frame, text="รายการบัญชีที่บันทึกไว้", padding=(10, 5))
        list_frame.pack(fill="both", expand=True, pady=5)

        self.cred_tree = ttk.Treeview(list_frame, columns=("Email",), show="headings")
        self.cred_tree.heading("Email", text="LINE Email")
        self.cred_tree.column("Email", width=400)
        self.cred_tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.cred_tree.bind("<Double-1>", self.on_double_click)

        self.refresh_cred_list()

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(pady=10)

        load_btn = ttk.Button(control_frame, text="โหลดข้อมูล", command=self.on_load)
        load_btn.pack(side=tk.LEFT, padx=5)

        delete_btn = ttk.Button(control_frame, text="ลบที่เลือก", command=self.on_delete)
        delete_btn.pack(side=tk.LEFT, padx=5)

        back_btn = ttk.Button(control_frame, text="ย้อนกลับ", command=self.on_cancel)
        back_btn.pack(side=tk.LEFT, padx=5)
        done_btn = ttk.Button(control_frame, text="เสร็จสิ้น", command=self.on_done)
        done_btn.pack(side=tk.LEFT, padx=5)

    def refresh_cred_list(self):
        self.cred_tree.delete(*self.cred_tree.get_children())
        for email in self.line_data.keys():
            self.cred_tree.insert("", "end", iid=email, values=(email,))
    
    def on_save(self):
        # แก้ไข: ดึงค่าจาก Entry widget โดยตรงแทน StringVar
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()

        # แก้ไขโค้ดส่วนนี้ให้รัดกุมขึ้นอีกนิด
        if not email:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Email ให้ครบถ้วน")
            return
        
        if not password:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Password ให้ครบถ้วน")
            return
            
        self.line_data[email] = password
        self.manager.save_line_credentials(self.line_data)
        messagebox.showinfo("สถานะ", "บันทึก LINE Credentials เรียบร้อยแล้ว")
        self.refresh_cred_list()
        self.on_clear_input()
        if hasattr(self.manager, "update_line_email_choices"):
            self.manager.update_line_email_choices()

    def on_clear_input(self):
        self.email_var.set("")
        self.password_var.set("")

    def on_delete(self):
        selected = self.cred_tree.focus()
        if not selected:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกบัญชีที่ต้องการลบ")
            return

        confirm = messagebox.askyesno("ยืนยันการลบ", f"คุณต้องการลบบัญชี {selected} ใช่หรือไม่?")
        if confirm:
            if selected in self.line_data:
                del self.line_data[selected]
            self.manager.save_line_credentials(self.line_data)
            self.refresh_cred_list()
            messagebox.showinfo("สถานะ", "ลบ LINE Credentials เรียบร้อยแล้ว")
            
            if hasattr(self.manager, "update_line_email_choices"):
                self.manager.update_line_email_choices()

    def on_load(self):
        self.line_data = self.manager.load_line_credentials()
        self.refresh_cred_list()
        messagebox.showinfo("สถานะ", "โหลดข้อมูลใหม่เรียบร้อยแล้ว")

    def on_double_click(self, event):
        selected = self.cred_tree.focus()
        if not selected:
            return
        # แก้ไข: ใช้ set() ของ StringVar เพื่ออัปเดตค่าใน Entry
        self.email_var.set(selected)
        self.password_var.set(self.line_data.get(selected, ""))

    def on_cancel(self):
        self.destroy()
    def on_done(self):
        if hasattr(self.manager, "update_line_email_choices"):
            self.manager.update_line_email_choices()
        self.destroy()

class TrialModeWindow(tk.Tk):
    def __init__(self, all_api_data, user_info):
        print("DEBUG: Creating TrialModeWindow...")
        super().__init__()
        self.user_info = user_info
        self.all_api_data = all_api_data
        self.title("โหมดทดลอง")
        self.geometry("400x600")
        self.resizable(False, False)
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        main_frame = ttk.Frame(self, padding=(10, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text="เลือก Site:", font=("Arial", 12)).pack(pady=(10, 3))
        self.site_var = tk.StringVar(value=TRIAL_SITES[0])
        self.site_combo = ttk.Combobox(main_frame, values=TRIAL_SITES, textvariable=self.site_var, state="readonly", font=("Arial", 11))
        self.site_combo.pack(pady=5)
        self.site_combo.bind("<<ComboboxSelected>>", self.on_site_selected)

        tk.Label(main_frame, text="เลือก Browser:", font=("Arial", 12)).pack(pady=(10, 3))
        self.browser_var = tk.StringVar(value=browsers[0])
        self.browser_combo = ttk.Combobox(main_frame, values=browsers, textvariable=self.browser_var, state="readonly", font=("Arial", 11))
        self.browser_combo.pack(pady=5)
        
        tk.Label(main_frame, text="เลือก Branch:", font=("Arial", 12)).pack(pady=(10, 3))
        self.branch_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(main_frame, textvariable=self.branch_var, state="readonly", font=("Arial", 11))
        self.branch_combo.pack(pady=5)

        tk.Label(main_frame, text="เลือกวัน:", font=("Arial", 12)).pack(pady=(10, 3))
        self.day_var = tk.StringVar(value=days[0])
        self.day_combo = ttk.Combobox(main_frame, values=days, textvariable=self.day_var, state="readonly", font=("Arial", 11))
        self.day_combo.pack(pady=5)

        tk.Label(main_frame, text="เลือก Time:", font=("Arial", 12)).pack(pady=(10, 3))
        self.time_var = tk.StringVar()
        self.time_combo = ttk.Combobox(main_frame, textvariable=self.time_var, state="readonly", font=("Arial", 11))
        self.time_combo.pack(pady=5)

        self.status_frame = ttk.LabelFrame(main_frame, text="สถานะ Playwright", padding=(10, 5))
        self.status_frame.pack(pady=10, padx=10, fill="x", expand=True)

        self.status_text = tk.Text(self.status_frame, wrap="word", font=("Arial", 10), height=5)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.insert(tk.END, "พร้อมเริ่มต้นโหมดทดลอง...\n")
        self.status_text.config(state=tk.DISABLED)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(pady=20)
        
        self.start_btn = ttk.Button(control_frame, text="เริ่มโหมดทดลอง", command=self.start_trial_booking)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        back_btn = ttk.Button(control_frame, text="ย้อนกลับ", command=self.on_cancel)
        back_btn.pack(side=tk.LEFT, padx=5)

        self.on_site_selected()
        print("DEBUG: TrialModeWindow created successfully.")

    def enable_start_button(self):
        self.start_btn.config(state=tk.NORMAL)

    def update_status(self, message):
        def inner():
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)
        self.after(0, inner)

    def on_site_selected(self, event=None):
        selected_site = self.site_var.get()
        
        branches = self.all_api_data.get("branchs", [])
        times = self.all_api_data.get("times", [])

        branch_names = branches
        self.branch_combo['values'] = branch_names
        if branch_names:
            self.branch_var.set(branch_names[0])
        else:
            self.branch_var.set("")

        time_values = times
        self.time_combo['values'] = time_values
        if time_values:
            self.time_var.set(time_values[0])
        else:
            self.time_var.set("")
        
        self.day_combo['values'] = days
        self.day_var.set(days[0])

    def start_trial_booking(self):
        selected_site = self.site_var.get()
        selected_browser = self.browser_var.get()
        selected_branch = self.branch_var.get()
        selected_day = self.day_var.get()
        selected_time = self.time_var.get()

        if not selected_site or not selected_browser or not selected_branch or not selected_day or not selected_time:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Site, Browser, Branch, วัน และ เวลา ให้ครบถ้วน!")
            return

        try:
            self.destroy()
            BookingProcessWindow(
                parent_window_class=TrialModeWindow,
                user_info=self.user_info,
                mode="trial", 
                site_name=selected_site, 
                browser_type=selected_browser, 
                all_api_data=self.all_api_data, 
                selected_branch=selected_branch, 
                selected_day=selected_day, 
                selected_time=selected_time, 
                register_by_user=False, 
                confirm_by_user=False
            ).mainloop()
        except Exception as e:
            messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการเปิดหน้าต่างจอง: {e}")
            App(user_info=self.user_info).mainloop()
    
    def on_cancel(self):
        self.destroy()
        App(user_info=self.user_info).mainloop()

class App(tk.Tk):
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info
        self.title("Browser Profile Launcher & API Loader")
        self.geometry("450x550")
        self.resizable(False, False)
        
        self.api_data = {}
        threading.Thread(target=self._load_api_data_in_background, daemon=True).start()

        user_frame = ttk.LabelFrame(self, text="สถานะผู้ใช้งาน", padding=(10, 5))
        user_frame.pack(pady=10, padx=10, fill="x")

        user_summary = (
            f"User: {self.user_info['Username']}\n"
            f"Role: {self.user_info.get('Role', '-')}\n"
            f"Max Profiles: {self.user_info.get('สามาถตั้งจองล่วงหน้าได้กี่ site', '-')}\n"
            f"Can Use Scheduler: {self.user_info.get('ตั้งจองล่วงหน้าได้ไหม', '-')}\n"
            f"Expiration date: {self.user_info.get('Expiration date', '-')}"
        )
        tk.Label(user_frame, text=user_summary, font=("Arial", 11), justify=tk.LEFT).pack(pady=5, padx=5)

        menu_frame = ttk.Frame(self)
        menu_frame.pack(pady=10)
        
        self.check_btn = ttk.Button(menu_frame, text="ตรวจสอบสถานะ Config", command=self.open_api_status, width=25)
        self.check_btn.pack(pady=5)

        self.top_up_btn = ttk.Button(menu_frame, text="เติมเงิน", command=self.on_top_up, width=25)
        self.top_up_btn.pack(pady=5)

        self.trial_mode_btn = ttk.Button(menu_frame, text="โหมดทดลอง", command=self.open_trial_mode_window, width=25, state='disabled')
        self.trial_mode_btn.pack(pady=5)
        
        self.live_mode_btn = ttk.Button(menu_frame, text="โหมดใช้งานจริง", command=self.open_live_mode_window, width=25, state='disabled')
        self.live_mode_btn.pack(pady=5)

        logout_btn = ttk.Button(menu_frame, text="Logout", command=self.logout, width=25)
        logout_btn.pack(pady=5)

    def _load_api_data_in_background(self):
        try:
            # โหลดข้อมูลหนัก ๆ ใน thread นี้
            self.api_data = get_all_api_data()
            # อัพเดต UI โดยเรียก self.after ใน main thread
            self.after(0, self._on_api_data_loaded_successfully)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"ไม่สามารถโหลดข้อมูล API ได้:\n{e}"))

    def _on_api_data_loaded_successfully(self):
        print("API data loaded successfully.")
        print(f"API Data: {json.dumps(self.api_data, indent=2)}")
        
        self.trial_mode_btn.config(state='normal')
        self.live_mode_btn.config(state='normal')
    
    def on_launch(self):
        selected_browser = "Chrome"
        selected_profile = "Default"

        if not selected_browser or not selected_profile:
            messagebox.showwarning("คำเตือน", "กรุณาระบุ Browser และ Profile ที่ต้องการเรียกใช้!")
            return

        if selected_browser == "Chrome":
            launch_chrome_with_profile(selected_profile)
        elif selected_browser == "Edge":
            launch_edge_with_profile(selected_profile)

        messagebox.showinfo("Success", f"Launched {selected_browser} with profile '{selected_profile}'")

    def open_api_status(self):
        try:
            self.destroy()
            ApiStatusPopup(user_info=self.user_info).mainloop()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการเปิดหน้าต่าง: {e}")
            App(user_info=self.user_info).mainloop()

    def on_top_up(self):
        messagebox.showinfo("เติมเงิน", "ฟังก์ชันเติมเงินยังไม่เปิดใช้งาน")
    
    def open_live_mode_window(self):
        allowed_roles = ["admin", "normal", "vipi", "vipii"]
        user_role = self.user_info.get('Role', '')
        if user_role not in allowed_roles:
            messagebox.showerror("Error", f"คุณไม่มีสิทธิ์ในการเข้าใช้งานโหมดนี้! บทบาทปัจจุบัน: {user_role}")
            return
        
        try:
            self.destroy()
            LiveModeWindow(user_info=self.user_info, api_data=self.api_data).mainloop()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการเปิดหน้าต่าง: {e}")
            App(user_info=self.user_info).mainloop()

    def open_trial_mode_window(self):
        if not self.api_data:
            messagebox.showwarning("คำเตือน", "ข้อมูล API ยังไม่พร้อม โปรดรอสักครู่")
            return
        
        try:
            self.destroy()
            TrialModeWindow(all_api_data=self.api_data, user_info=self.user_info).mainloop()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการเปิดหน้าต่าง: {e}")
            App(user_info=self.user_info).mainloop()
    
    def logout(self):
        confirm = messagebox.askyesno("Logout", "คุณต้องการออกจากระบบใช่หรือไม่?")
        if confirm:
            self.destroy()
            LoginWindow().mainloop()

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.user_info = None
        self.title("Login")
        self.geometry("350x220")
        self.resizable(False, False)

        tk.Label(self, text="Username:", font=("Arial", 12)).pack(pady=(20,5))
        self.username_entry = ttk.Entry(self, font=("Arial", 11))
        self.username_entry.pack(pady=5)

        tk.Label(self, text="Password:", font=("Arial", 12)).pack(pady=(10,5))
        self.password_entry = tk.Entry(self, show="*", font=("Arial", 11))
        self.password_entry.pack(pady=5)

        login_btn = ttk.Button(self, text="Login", command=self.try_login)
        login_btn.pack(pady=20)

    def try_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Username และ Password")
            return

        try:
            user_info = google_sheet_check_login(username, password)
        except Exception as e:
            messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการเชื่อมต่อ:\n{e}")
            return

        if user_info == "expired":
            messagebox.showerror("Error", "บัญชีผู้ใช้หมดอายุแล้ว")
            return
        elif not user_info:
            messagebox.showerror("Error", "Username หรือ Password ไม่ถูกต้อง")
            return

        self.destroy()
        app = App(user_info)
        app.mainloop()

def main():
    setup_config_files() 
    login_win = LoginWindow()
    login_win.mainloop()

if __name__ == "__main__":
    main()