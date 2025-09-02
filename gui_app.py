import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import simpledialog
from chrome_op import launch_chrome_instance as launch_chrome_with_profile
from edge_op import launch_edge_with_profile
from utils import get_all_api_data, google_sheet_check_login
import threading
import asyncio
import time
import json
import traceback
from datetime import datetime
from real_booking import perform_real_booking, attach_to_chrome
from playwright_ops import launch_browser_and_perform_booking as trial_booking
from playwright.async_api import async_playwright
from Scheduledreal_booking import ScheduledManager
from utils import get_all_api_data, google_sheet_check_login, setup_config_files, start_license_session, is_today_booking_open, get_user_profile_names, register_user, load_line_credentials, load_user_profile
from Scroll_ import ScrollableFrame
from ultrafast_booking import run_ultrafast_booking
from topup import TopUpDialog

profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"]
browsers = ["Chrome", "Edge"]
LIVE_SITES = ["ROCKETBOOKING"]
TRIAL_SITES = ["EZBOT", "PMROCKET"]
days = [str(i) for i in range(1, 32)]

class BookingProcessWindow(tk.Tk):
    def __init__(self, parent_window_class, user_info, mode, site_name, browser_type, all_api_data, selected_branch, selected_day, selected_time, register_by_user, confirm_by_user, cdp_port=None, round_index=None, timer_seconds=None, delay_seconds=None, auto_line_login=False):
        print(f"DEBUG: Creating BookingProcessWindow for mode '{mode}'...")
        super().__init__()
        self.parent_window_class = parent_window_class
        self.user_info = user_info
        self.all_api_data = all_api_data
        
        self.title("สถานะการจอง")
        # ขยายหน้าต่างให้ใหญ่ขึ้นและอนุญาตปรับขนาดได้
        self.geometry("600x500")
        self.resizable(True, True)

        self.mode = mode 
        self.site_name = site_name
        self.browser_type = browser_type
        self.selected_branch = selected_branch
        self.selected_day = selected_day
        self.selected_time = selected_time
        self.register_by_user = register_by_user
        self.confirm_by_user = confirm_by_user
        self.cdp_port = cdp_port
        self.round_index = round_index
        self.timer_seconds = timer_seconds
        self.delay_seconds = delay_seconds
        self.auto_line_login = auto_line_login
        
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
            # ตรวจ todaybooking ก่อน ถ้าไม่เปิดจองวันนี้ ให้ยุติ
            try:
                if not is_today_booking_open():
                    self.update_status("ℹ️ วันนี้ไม่มีการจอง (อ้างอิง todaybooking)")
                    return
                else:
                    self.update_status("🗓️ วันนี้มีการจองตาม todaybooking")
            except Exception as e:
                self.update_status(f"⚠️ ตรวจสอบ todaybooking ไม่สำเร็จ: {e}")

            self.update_status("⏳ กำลังรอเชื่อมต่อกับเบราว์เซอร์ที่เปิดอยู่...")
            # เริ่ม License/Quota ผ่าน Google Sheet (ถ้ามีพอร์ต)
            license_session = None
            try:
                if self.cdp_port:
                    license_session = start_license_session(self.user_info, port=self.cdp_port, version="1.0")
                    if not license_session:
                        self.update_status("❌ โควต้าการใช้งานพร้อมกันเต็ม หรือเชื่อมต่อ Sheet ไม่ได้")
                        return
                    else:
                        self.update_status("🟢 จองสิทธิ์ใช้งานสำเร็จ")
            except Exception:
                pass

            self.update_status(f"🔌 กำลังเชื่อมต่อพอร์ต {self.cdp_port} ...")
            playwright, browser, context, page = await attach_to_chrome(self.cdp_port, self.update_status)
            self.update_status(f"🔌 เชื่อมต่อพอร์ต {self.cdp_port} เสร็จ")
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
                progress_callback=self.update_status,
                round_index=self.round_index,
                timer_seconds=self.timer_seconds,
                delay_seconds=self.delay_seconds,
                auto_line_login=self.auto_line_login
            )
        except asyncio.CancelledError:
            self.update_status("🚨 Task ถูกยกเลิก")
        except Exception as e:
            self.update_status(f"❌ เกิดข้อผิดพลาดในการจอง: {e}")
            traceback.print_exc()
        finally:
            try:
                if 'license_session' in locals() and license_session:
                    license_session.stop()
            except Exception:
                pass
            if playwright:
                await playwright.stop()
            if self._async_loop and not self._async_loop.is_closed():
                self._async_loop.create_task(asyncio.sleep(0)).cancel()

    async def _run_trial_booking(self):
        try:
            await run_ultrafast_booking(
                browser_type=self.browser_type,
                site_name=self.site_name,
                all_api_data=self.all_api_data,
                selected_branch_name=self.selected_branch,
                selected_day=self.selected_day,
                selected_time=self.selected_time,
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
        # ปิดเบราว์เซอร์ที่ต่อ CDP อยู่ (ถ้ามีพอร์ต)
        if self.cdp_port:
            def _close_browser():
                try:
                    asyncio.run(self._close_browser_async())
                except Exception:
                    pass
            threading.Thread(target=_close_browser, daemon=True).start()
        messagebox.showinfo("ยกเลิก", "การจองถูกยกเลิกแล้ว")
        self.destroy()
        self.parent_window_class(user_info=self.user_info, all_api_data=self.all_api_data).mainloop()

    async def _close_browser_async(self):
        try:
            from real_booking import attach_to_chrome
            playwright, browser, context, page = await attach_to_chrome(self.cdp_port)
            try:
                await browser.close()
            finally:
                await playwright.stop()
        except Exception:
            pass

class SingleBookingWindow(tk.Tk):
    def __init__(self, user_info, all_api_data):
        print("DEBUG: Creating SingleBookingWindow...")
        super().__init__()
        self.user_info = user_info
        self.all_api_data = all_api_data
        self.title("จองทีละครั้ง")
        # ขยายขนาดหน้าต่างและอนุญาตให้ปรับขนาด พร้อมเพิ่มสกอร์ลบาร์
        self.geometry("520x740")
        self.resizable(True, True)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        # ใช้ ScrollableFrame เพื่อให้เห็นปุ่มครบแม้หน้าจอเล็ก
        self.scrollable = ScrollableFrame(self)
        self.scrollable.pack(fill=tk.BOTH, expand=True)
        main_frame = self.scrollable.scrollable_frame

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
        
        # ตัวเลือก Round/Timer/Delay
        adv_frame = ttk.LabelFrame(main_frame, text="ตัวเลือกขั้นสูง", padding=(10, 5))
        adv_frame.pack(fill="x", pady=(10, 5))
        ttk.Label(adv_frame, text="Round (index):").grid(row=0, column=0, sticky="w")
        self.round_var = tk.StringVar(value="")
        self.round_entry = ttk.Entry(adv_frame, textvariable=self.round_var, width=8)
        self.round_entry.grid(row=0, column=1, padx=5)
        ttk.Label(adv_frame, text="Timer (sec):").grid(row=0, column=2, sticky="w")
        self.timer_var = tk.StringVar(value="")
        self.timer_entry = ttk.Entry(adv_frame, textvariable=self.timer_var, width=8)
        self.timer_entry.grid(row=0, column=3, padx=5)
        ttk.Label(adv_frame, text="Delay (sec):").grid(row=0, column=4, sticky="w")
        self.delay_var = tk.StringVar(value="")
        self.delay_entry = ttk.Entry(adv_frame, textvariable=self.delay_var, width=8)
        self.delay_entry.grid(row=0, column=5, padx=5)
        
        self.register_var = tk.BooleanVar()
        self.register_check = ttk.Checkbutton(main_frame, text="กดปุ่ม Register ด้วยตัวเอง", variable=self.register_var)
        self.register_check.pack(pady=(10, 5))

        self.confirm_var = tk.BooleanVar()
        self.confirm_check = ttk.Checkbutton(main_frame, text="กดปุ่ม Confirm Booking ด้วยตัวเอง", variable=self.confirm_var)
        self.confirm_check.pack(pady=5)

        # โหมดช้า
        self.slow_var = tk.BooleanVar()
        self.slow_check = ttk.Checkbutton(main_frame, text="โหมดช้า (เพิ่มดีเลย์อัตโนมัติ)", variable=self.slow_var)
        self.slow_check.pack(pady=5)
        
        line_frame = ttk.Frame(main_frame)
        line_frame.pack(pady=10)
        
        self.confirm_line_check_var = tk.BooleanVar()
        ttk.Checkbutton(line_frame, text="ยืนยันการตรวจสอบ LINE", variable=self.confirm_line_check_var).pack(side=tk.LEFT, padx=5)
        
        open_settings_btn = ttk.Button(line_frame, text="ตั้งค่า LINE/Profile", command=self.on_line_settings)
        open_settings_btn.pack(side=tk.LEFT, padx=5)

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
        # ค่าขั้นสูง
        round_index = None
        timer_seconds = None
        delay_seconds = None
        try:
            if self.round_var.get().strip():
                round_index = max(0, int(self.round_var.get().strip()) - 1)
        except Exception:
            round_index = None
        try:
            if self.timer_var.get().strip():
                timer_seconds = float(self.timer_var.get().strip())
        except Exception:
            timer_seconds = None
        try:
            if self.delay_var.get().strip():
                delay_seconds = float(self.delay_var.get().strip())
        except Exception:
            delay_seconds = None
        
        if not selected_site or not selected_browser or not selected_profile or not selected_branch or not selected_day or not selected_time:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Site, Browser, Profile, Branch, วัน และ เวลา ให้ครบถ้วน!")
            return
        
        # ถ้าติ๊กตรว�� LINE ให้ตรวจว่าตั้งค่า LINE และโปรไฟล์แล้วหรือยัง
        confirm_line_login = bool(self.confirm_line_check_var.get())
        if confirm_line_login:
            # ตรวจ LINE credentials
            try:
                creds = load_line_credentials()
            except Exception:
                creds = {}
            valid_line = False
            if isinstance(creds, dict):
                if any(k in creds for k in ("Email","email","username","Password","password")):
                    em = (creds.get("Email") or creds.get("email") or creds.get("username") or "").strip()
                    pw = (creds.get("Password") or creds.get("password") or "").strip()
                    valid_line = bool(em and pw)
                else:
                    for em, pw in creds.items():
                        if str(em).strip() and str(pw or "").strip():
                            valid_line = True
                            break
            if not valid_line:
                messagebox.showwarning("คำเตือน", "คุณติ๊กตรวจ LINE แต่ยังไม่ได้ตั้งค่า LINE Email/Password ในเมนูตั้งค่า")
                return
            # ตรวจโปรไฟล์ผู้ใช้พื้นฐาน
            try:
                prof = load_user_profile()
            except Exception:
                prof = {}
            has_profile = isinstance(prof, dict) and any(str(v).strip() for v in prof.values())
            if not has_profile:
                messagebox.showwarning("คำเตือน", "คุณติ๊กตรวจ LINE แต่ยังไม่ได้ตั้งค่าโปรไฟล์ผู้ใช้ในเมนูตั้งค่า")
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
            # ปรับ delay ตามโหมดช้า หากผู้ใช้ไม่ได้กำหนดไว้
            if self.slow_var.get() and delay_seconds is None:
                delay_seconds = 0.3
            confirm_line_login = bool(self.confirm_line_check_var.get())

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
                cdp_port=launched_port,
                round_index=round_index,
                timer_seconds=timer_seconds,
                delay_seconds=delay_seconds,
                auto_line_login=confirm_line_login
            ).mainloop()
        except Exception as e:
            messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการเปิดหน้าต่างจอง: {e}")
            App(user_info=self.user_info).mainloop()
    
    def on_cancel(self):
        try:
            self.destroy()
            LiveModeWindow(user_info=self.user_info, api_data=self.all_api_data).mainloop()
        except Exception:
            # เผื่อกรณีเปิดจาก App โดยตรง ให้ย้อนกลับไป App
            App(user_info=self.user_info).mainloop()

    def _on_line_check_toggle(self):
        try:
            if getattr(self, "confirm_line_check_var", None) and self.confirm_line_check_var.get():
                self.on_check_line_login()
        finally:
            try:
                self.after(0, lambda: self.confirm_line_check_var.set(False))
            except Exception:
                pass

    def on_check_line_login(self):
        # ต้องติ๊กยืนยันก่อนเริ่ม และจะเปิดเบราว์เซอร์/โปรไฟล์ที่เลือกโดยอัตโนมัติ
        selected_browser = self.browser_var.get()
        selected_profile = self.profile_var.get()
        def runner():
            async def run_check():
                try:
                    from real_booking import attach_to_chrome
                    from line_login import perform_line_login
                    port = None
                    try:
                        if selected_browser == "Chrome":
                            port, _ = launch_chrome_with_profile(selected_profile)
                        elif selected_browser == "Edge":
                            port, _ = launch_edge_with_profile(selected_profile)
                    except Exception as e:
                        self.after(0, lambda: messagebox.showerror("Error", f"เปิดเบราว์เซอร์ไม่สำเร็จ: {e}"))
                        return
                    self.after(0, lambda: messagebox.showinfo("กำลังทำงาน", f"กำลังเชื่อมต่อเบราว์เซอร์ (พอร์ต {port})..."))
                    playwright, browser, context, page = await attach_to_chrome(port)
                    ok = await perform_line_login(page, progress_callback=lambda m: None)
                    try:
                        await browser.close()
                    except Exception:
                        pass
                    await playwright.stop()
                    if ok:
                        self.after(0, lambda: messagebox.showinfo("สำเร็จ", "ตรวจสอบ/ล็อกอิน LINE สำเร็จหรือไม่จำเป็นต้องทำ"))
                    else:
                        self.after(0, lambda: messagebox.showerror("ล้มเหลว", "ไม่สามารถล็อกอิน LINE ได้ ตรวจสอบข้อมูลใน Settings"))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("ผิดพลาด", f"เชื่อมต่อหรือล็อกอินไม่สำเร็จ: {e}"))
            asyncio.run(run_check())
        threading.Thread(target=runner, daemon=True).start()

    def on_line_settings(self):
        try:
            SettingsDialog(self).wait_window()
        except Exception as e:
            messagebox.showerror("Error", f"ไม่สามารถเปิดหน้าตั้งค่าได้: {e}")

class SettingsDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("ตั้งค่า LINE & Profile")
        self.geometry("420x320")
        self.resizable(False, False)
        container = ttk.Notebook(self)

        # แท็บ LINE
        line_tab = ttk.Frame(container)
        ttk.Label(line_tab, text="Email:").grid(row=0, column=0, sticky="e", padx=5, pady=6)
        self.line_email = tk.StringVar()
        ttk.Entry(line_tab, textvariable=self.line_email, width=30).grid(row=0, column=1, padx=5)

        ttk.Label(line_tab, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=6)
        self.line_password = tk.StringVar()
        ttk.Entry(line_tab, textvariable=self.line_password, show="*", width=30).grid(row=1, column=1, padx=5)

        ttk.Button(line_tab, text="บันทึก LINE", command=self.save_line).grid(row=2, column=1, sticky="e", pady=8)

        # แท็บ Profile
        prof_tab = ttk.Frame(container)
        self.fn = tk.StringVar(); self.ln = tk.StringVar(); self.gender = tk.StringVar(); self.pid = tk.StringVar(); self.phone = tk.StringVar()
        row = 0
        for label, var in [("Firstname", self.fn),("Lastname", self.ln),("Gender", self.gender),("ID", self.pid),("Phone", self.phone)]:
            ttk.Label(prof_tab, text=f"{label}:").grid(row=row, column=0, sticky="e", padx=5, pady=6)
            ttk.Entry(prof_tab, textvariable=var, width=30).grid(row=row, column=1, padx=5)
            row += 1
        ttk.Button(prof_tab, text="บันทึก Profile", command=self.save_profile).grid(row=row, column=1, sticky="e", pady=8)

        container.add(line_tab, text="LINE")
        container.add(prof_tab, text="Profile")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        self.load_existing()

    def _company_dir(self):
        import os
        from pathlib import Path
        appdata = os.environ.get('APPDATA')
        return Path(appdata) / "BokkChoYCompany" if appdata else Path.cwd()

    def load_existing(self):
        import json
        try:
            p = self._company_dir() / "line_data.json"
            if p.exists():
                data = json.load(open(p, 'r', encoding='utf-8'))
                self.line_email.set(data.get('Email') or data.get('email') or "")
                self.line_password.set(data.get('Password') or data.get('password') or "")
        except Exception:
            pass
        try:
            p = self._company_dir() / "user_profile.json"
            if p.exists():
                data = json.load(open(p, 'r', encoding='utf-8'))
                self.fn.set(data.get('Firstname', ''))
                self.ln.set(data.get('Lastname', ''))
                self.gender.set(data.get('Gender', ''))
                self.pid.set(data.get('ID', ''))
                self.phone.set(data.get('Phone', ''))
        except Exception:
            pass

    def save_line(self):
        import json, os
        email = (self.line_email.get() or "").strip()
        password = (self.line_password.get() or "").strip()
        if not email or not password:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Email/Password ให้ครบ")
            return
        p = self._company_dir() / "line_data.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        # โ��ลดข้อมูลเดิม (รองรับทั้ง list และ dict เก่า) แล้วรวมเป็น mapping
        existing_map = {}
        existing_list = []
        try:
            raw = json.load(open(p, 'r', encoding='utf-8')) if p.exists() else []
            if isinstance(raw, list):
                existing_list = [x for x in raw if isinstance(x, dict)]
                for it in existing_list:
                    em = (it.get("Email") or it.get("email") or "").strip()
                    pw = (it.get("Password") or it.get("password") or "").strip()
                    if em:
                        existing_map[em] = {"id": it.get("id"), "Password": pw}
            elif isinstance(raw, dict):
                # รองรับไฟล์แบบเก่า
                em = (raw.get("Email") or raw.get("email") or "").strip()
                pw = (raw.get("Password") or raw.get("password") or "").strip()
                if em:
                    existing_map[em] = {"id": 1, "Password": pw}
        except Exception:
            existing_map = {}
            existing_list = []
        # กำหนด id ให้สอดคล้อง (คง id เดิมถ้ามี)
        max_id = 0
        for v in existing_map.values():
            try:
                max_id = max(max_id, int(v.get("id") or 0))
            except Exception:
                pass
        if email in existing_map and (existing_map[email].get("id") or 0):
            assigned_id = int(existing_map[email]["id"])
        else:
            assigned_id = max_id + 1
        existing_map[email] = {"id": assigned_id, "Password": password}
        # เขียนกลับเป็น list ของออบเจ็กต์ เรียงตาม id
        new_list = sorted(
            (
                {"id": int(v.get("id") or 0), "Email": em, "Password": v.get("Password") or ""}
                for em, v in existing_map.items()
            ),
            key=lambda x: int(x.get("id") or 0)
        )
        json.dump(new_list, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=4)
        messagebox.showinfo("สำเร็จ", "บันทึก LINE Credentials เรียบร้อยแล้ว")

    def save_profile(self):
        import json
        d = {
            "Firstname": self.fn.get().strip(),
            "Lastname": self.ln.get().strip(),
            "Gender": self.gender.get().strip(),
            "ID": self.pid.get().strip(),
            "Phone": self.phone.get().strip(),
        }
        p = self._company_dir() / "user_profile.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        messagebox.showinfo("สำเร็จ", "บันทึกโปรไฟล์เรียบร้อยแล้ว")

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

        # จำกัดสิทธิ์: บัญชี Role "normal" ใช้ได้เฉพาะโหมดทดลองเท่านั้น
        try:
            role = str(self.user_info.get('Role', '')).strip().lower()
            if role == 'normal':
                single_booking_btn.config(state=tk.DISABLED)
                scheduled_booking_btn.config(state=tk.DISABLED)
                ttk.Label(self, text="บัญชี Role 'normal' ใช้ได้เฉพาะโหมดทดลอง", foreground="red").pack(pady=(5, 0))
        except Exception:
            pass
        
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
        App(user_info=self.user_info).mainloop()

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
        self.browser_combo = ttk.Combobox(control_frame, values=browsers, textvariable=self.browser_var, state="readonly")
        self.browser_combo.grid(row=0, column=3, padx=5, pady=5)
        self.browser_combo.bind("<<ComboboxSelected>>", self.on_scheduled_browser_selected)

        ttk.Label(control_frame, text="Profile:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.profile_combo = ttk.Combobox(control_frame, values=profiles[:max_scheduled], textvariable=self.profile_var, state="readonly")
        self.profile_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="Branch:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.branch_combo = ttk.Combobox(control_frame, textvariable=self.branch_var, state="readonly")
        self.branch_combo.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(control_frame, text="Day:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(control_frame, values=days, textvariable=self.day_var, state="readonly").grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="Time:").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        self.time_combo = ttk.Combobox(control_frame, textvariable=self.time_var, state="readonly")
        self.time_combo.grid(row=2, column=3, padx=5, pady=5)

        # Advanced options for scheduled tasks
        ttk.Label(control_frame, text="Round (index):").grid(row=3, column=2, padx=5, pady=5, sticky="w")
        self.round_var = tk.StringVar()
        self.round_entry = ttk.Entry(control_frame, textvariable=self.round_var, width=10)
        self.round_entry.grid(row=3, column=3, padx=5, pady=5, sticky="w")

        ttk.Label(control_frame, text="Timer (sec):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.timer_var = tk.StringVar()
        self.timer_entry = ttk.Entry(control_frame, textvariable=self.timer_var, width=10)
        self.timer_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(control_frame, text="Delay (sec):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.delay_var = tk.StringVar()
        self.delay_entry = ttk.Entry(control_frame, textvariable=self.delay_var, width=10)
        self.delay_entry.grid(row=4, column=1, padx=5, pady=5, sticky="w")

        # โหมดเพิ่มเติม
        self.manual_confirm_var = tk.BooleanVar(value=False)
        self.slow_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="กด Confirm Booking เอง", variable=self.manual_confirm_var).grid(row=4, column=2, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(control_frame, text="โหมดช้า", variable=self.slow_mode_var).grid(row=4, column=3, padx=5, pady=5, sticky="w")

        # แก้ไข UI: เปลี่ยนจาก Entry เป็น Combobox สำหรับ LINE Email
        #ttk.Label(control_frame, text="LINE Email:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        #self.line_email_combo = ttk.Combobox(control_frame, textvariable=self.line_email_var, state="readonly")
        #self.line_email_combo.grid(row=3, column=1, padx=5, pady=5)
        # ลบ Label และ Entry สำหรับ LINE Password ออกไป
        ttk.Label(control_frame, text="LINE Email:").grid(row=4, column=2, padx=5, pady=5, sticky="w")
        self.line_email_combo = ttk.Combobox(control_frame, textvariable=self.line_email_var, state="readonly")
        self.line_email_combo.grid(row=4, column=3, padx=5, pady=5)

        # User Profile selection
        ttk.Label(control_frame, text="User Profile:").grid(row=5, column=2, padx=5, pady=5, sticky="w")
        self.user_profile_var = tk.StringVar()
        self.user_profile_combo = ttk.Combobox(control_frame, textvariable=self.user_profile_var, state="readonly")
        self.user_profile_combo.grid(row=5, column=3, padx=5, pady=5)
        
        add_btn = ttk.Button(control_frame, text="เพิ่ม Task", command=self.add_task)
        add_btn.grid(row=6, column=0, columnspan=4, padx=5, pady=5, sticky="we")

        # ส่วนแสดงรายการ Task ที่ตั้งไว้
        list_frame = ttk.LabelFrame(main_frame, text="รายการจองที่ตั้งเวลาไว้", padding=(10, 5))
        list_frame.pack(fill="both", expand=True, pady=10)

        self.task_tree = ttk.Treeview(list_frame, columns=("TaskID", "Site", "Branch", "Day", "Time", "Round", "Timer", "Delay", "Confirm", "Slow", "Profile", "LINE Email", "Status"), show="headings")
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
        self.task_tree.heading("Round", text="Round", anchor="w")
        self.task_tree.column("Round", width=60)
        self.task_tree.heading("Timer", text="Timer", anchor="w")
        self.task_tree.column("Timer", width=60)
        self.task_tree.heading("Delay", text="Delay", anchor="w")
        self.task_tree.column("Delay", width=60)
        self.task_tree.heading("Confirm", text="Confirm", anchor="w")
        self.task_tree.column("Confirm", width=70)
        self.task_tree.heading("Slow", text="Slow", anchor="w")
        self.task_tree.column("Slow", width=60)
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
        self.task_confirm_line_check_var = tk.BooleanVar()
        ttk.Checkbutton(task_control_frame, text="ยืนยันการตรวจสอบ LINE", variable=self.task_confirm_line_check_var, command=self._on_task_line_check_toggle).pack(side=tk.LEFT, padx=5)

        # ปุ่มควบคุม Line Credentials
        line_cred_frame = ttk.Frame(list_frame)
        line_cred_frame.pack(pady=5)
        ttk.Button(line_cred_frame, text="เพิ่ม/แก้ไข LINE Credentials", command=self.add_line_credentials).pack(side=tk.LEFT, padx=5)
        ttk.Button(line_cred_frame, text="เพิ่ม/แก้ไข Profile", command=self.manage_profiles).pack(side=tk.LEFT, padx=5)
        
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
        self.update_user_profile_choices()
        self.refresh_task_list()
        # sync โปรไฟล์ตาม Browser ที่เลือกตอนเริ่มต้น
        try:
            self.on_scheduled_browser_selected()
        except Exception:
            pass

    def update_combobox_data(self):
        branches = self.all_api_data.get("branchs", [])
        times = self.all_api_data.get("times", [])

        self.branch_combo['values'] = branches
        if branches:
            self.branch_var.set(branches[0])

        self.time_combo['values'] = times
        if times:
            self.time_var.set(times[0])

    def on_scheduled_browser_selected(self, event=None):
        try:
            if self.browser_var.get() == "Edge":
                vals = ["Default"]
            else:
                vals = profiles
            self.profile_combo['values'] = vals
            if self.profile_var.get() not in vals and vals:
                self.profile_var.set(vals[0])
        except Exception:
            pass

    def update_line_email_choices(self):
        try:
            line_data = self.manager.load_line_credentials()
            email_list = list(line_data.keys())
            if hasattr(self, 'line_email_combo') and self.line_email_combo.winfo_exists():
                self.line_email_combo['values'] = email_list
                if email_list:
                    self.line_email_var.set(email_list[0])
                else:
                    self.line_email_var.set("")
        except Exception:
            pass

    def update_user_profile_choices(self):
        try:
            names = get_user_profile_names()
            if hasattr(self, 'user_profile_combo') and self.user_profile_combo.winfo_exists():
                self.user_profile_combo['values'] = names
                if names:
                    # ถ้าเคยเลือกไว้แล้วให้คงไว้ มิฉะนั้นเลือกตัวแรก
                    cur = self.user_profile_var.get()
                    self.user_profile_var.set(cur if cur in names else names[0])
                else:
                    self.user_profile_var.set("")
        except Exception:
            pass

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
                                          ( (task_data.get('round_index') + 1) if isinstance(task_data.get('round_index'), int) else (task_data.get('round_index') or '-') ),
                                          task_data.get('timer_seconds', '-'),
                                          task_data.get('delay_seconds', '-'),
                                          ('Y' if task_data.get('confirm_by_user') else 'N'),
                                          ('Y' if task_data.get('slow_mode') else 'N'),
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

        # แปลงค่าขั้นสูง
        round_index = None
        timer_seconds = None
        delay_seconds = None
        try:
            if self.round_var.get().strip():
                round_index = max(0, int(self.round_var.get().strip()) - 1)
        except Exception:
            round_index = None
        try:
            if self.timer_var.get().strip():
                timer_seconds = float(self.timer_var.get().strip())
        except Exception:
            timer_seconds = None
        try:
            if self.delay_var.get().strip():
                delay_seconds = float(self.delay_var.get().strip())
        except Exception:
            delay_seconds = None

        # โหมดช้า: ตั้งค่า delay เริ่มต้นหากผู้ใช้ไม่กำหนดเอง
        if self.slow_mode_var.get() and delay_seconds is None:
            delay_seconds = 0.3

        # ป้องกันใช้ Profile ซ้ำใน Scheduler (แยกตาม Browser)
        used_pairs = [(t.task_data.get('browser_type'), t.task_data.get('profile')) for t in self.manager.tasks]
        if (self.browser_var.get(), self.profile_var.get()) in used_pairs:
            messagebox.showwarning("คำเตือน", f"Profile '{self.profile_var.get()}' ของ {self.browser_var.get()} ถูกใช้ใน Task อื่นแล้ว")
            return

        task_data = {
            "site_name": self.site_var.get(),
            "browser_type": self.browser_var.get(),
            "profile": self.profile_var.get(),
            "selected_branch": self.branch_var.get(),
            "selected_day": self.day_var.get(),
            "selected_time": self.time_var.get(),
            "round_index": round_index,
            "timer_seconds": timer_seconds,
            "delay_seconds": delay_seconds,
            "confirm_by_user": bool(self.manual_confirm_var.get()),
            "slow_mode": bool(self.slow_mode_var.get()),
            "line_email": selected_line_email,
            "line_password": line_password,
            "user_profile_name": self.user_profile_var.get()
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
        # โปรไฟล์ผู้ใช้
        try:
            self.user_profile_var.set(task.task_data.get('user_profile_name', ''))
        except Exception:
            pass
        # ฟื้นค่าขั้นสูง
        ri = task.task_data.get('round_index')
        self.round_var.set(str(ri + 1) if isinstance(ri, int) else (str(ri) if ri else ''))
        self.timer_var.set(str(task.task_data.get('timer_seconds') or ''))
        self.delay_var.set(str(task.task_data.get('delay_seconds') or ''))
        self.manual_confirm_var.set(bool(task.task_data.get('confirm_by_user', False)))
        self.slow_mode_var.set(bool(task.task_data.get('slow_mode', False)))

        self.manager.remove_booking(task_id)
        self.refresh_task_list()
        messagebox.showinfo("สถานะ", "ข้อมูลถูกย้ายไปที่ช่องกรอกด้านบนแล้ว กรุณากด 'เพิ่ม Task' เพื่อบันทึก")
    
    def _on_task_line_check_toggle(self):
        try:
            if getattr(self, "task_confirm_line_check_var", None) and self.task_confirm_line_check_var.get():
                self.check_line_login_selected_task()
        finally:
            try:
                self.after(0, lambda: self.task_confirm_line_check_var.set(False))
            except Exception:
                pass

    def check_line_login_selected_task(self):
        selected_item = self.task_tree.focus()
        if not selected_item:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Task ที่ต้องการตรวจสอบ")
            return
        task = next((t for t in self.manager.tasks if t.id == selected_item), None)
        if not task:
            messagebox.showwarning("คำเตือน", "ไม่พบ Task ที่เลือก")
            return
        browser = task.task_data.get('browser_type') or "Chrome"
        profile = task.task_data.get('profile') or "Default"
        email = task.task_data.get('line_email')
        try:
            launched_port = None
            if browser == "Chrome":
                launched_port, _ = launch_chrome_with_profile(profile)
            elif browser == "Edge":
                launched_port, _ = launch_edge_with_profile(profile)
            if not launched_port:
                messagebox.showerror("Error", "ไม่สามารถเปิดเบราว์เซอร์ได้")
                return
        except Exception as e:
            messagebox.showerror("Error", f"เปิดเบราว์เซอร์ไม่สำเร็จ: {e}")
            return
        def runner():
            async def run_check():
                try:
                    from real_booking import attach_to_chrome
                    from line_login import perform_line_login
                    playwright, browser_obj, context, page = await attach_to_chrome(launched_port)
                    ok = await perform_line_login(page, progress_callback=lambda m: None, preferred_email=email)
                    try:
                        await browser_obj.close()
                    except Exception:
                        pass
                    await playwright.stop()
                    if ok:
                        self.after(0, lambda: messagebox.showinfo("สำเร็จ", f"ตรวจสอบ/ล็อกอิน LINE ({email}) สำเร็จ"))
                    else:
                        self.after(0, lambda: messagebox.showerror("ล้มเหลว", f"ไม่สามารถล็อกอิน LINE ด้วย {email}"))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("ผิดพลาด", f"ตรวจสอบไม่สำเร็จ: {e}"))
            asyncio.run(run_check())
        threading.Thread(target=runner, daemon=True).start()

    def add_line_credentials(self):
        win = LineCredentialsWindow(manager=self.manager)
        self.wait_window(win)
        self.update_line_email_choices()

    def manage_profiles(self):
        win = ProfilesWindow(self)
        self.wait_window(win)
        self.update_user_profile_choices()

    def open_settings(self):
        try:
            SettingsDialog(self).wait_window()
        except Exception as e:
            messagebox.showerror("Error", f"ไม่สามารถเปิดหน้าตั้งค่าได้: {e}")
        # รีเฟรชรายชื่ออีเมลหลังผู้ใช้บันทึกจาก Settings
        self.update_line_email_choices()

    def remove_line_credentials(self):
        # ฟังก์ชันนี้เลิกใช้ (จัดการลบได้จากหน้าต่าง LINE Credentials โดยตรง)
        messagebox.showinfo("ข้อมูล", "โปรดจัดการลบบัญชีในหน้าต่าง LINE Credentials")
   
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
        LiveModeWindow(user_info=self.user_info, api_data=self.all_api_data).mainloop()
        # เรียก LiveModeWindow หรือหน้าหลักอื่น ๆ ต่อไป

class LineCredentialsWindow(tk.Tk):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.title("ตั้งค่า LINE Credentials")
        self.geometry("520x360")
        self.resizable(False, False)

        # โหลดข้อมูลจากไฟล์เดียว
        self.line_data = self.manager.load_line_credentials()

        main_frame = ttk.Frame(self, padding=(10, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.LabelFrame(main_frame, text="รายการบัญชี LINE", padding=(10, 5))
        list_frame.pack(fill="both", expand=True, pady=5)

        toolbar = ttk.Frame(list_frame)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="+ เพิ่ม", command=self.on_add).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="แก้ไข", command=self.on_edit).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="ลบ", command=self.on_delete_selected).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="รีเฟรช", command=self.on_load).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="เปิดโฟลเดอร์ไฟล์", command=self.open_config_folder).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="ย้อนกลับ", command=self.on_cancel).pack(side=tk.RIGHT, padx=3)
        ttk.Button(toolbar, text="เสร็จสิ้น", command=self.on_done).pack(side=tk.RIGHT, padx=3)

        # เพิ่มคอลัมน์เลือก (ติ๊ก) แบบง่ายด้วยสัญลักษณ์
        self._selected_emails = set()
        self.cred_tree = ttk.Treeview(list_frame, columns=("Sel","Email"), show="headings", selectmode='extended')
        self.cred_tree.heading("Sel", text="เลือก")
        self.cred_tree.column("Sel", width=50, anchor="center")
        self.cred_tree.heading("Email", text="LINE Email")
        self.cred_tree.column("Email", width=430)
        self.cred_tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.cred_tree.bind("<Double-1>", self.on_double_click)
        self.cred_tree.bind("<Button-1>", self._on_tree_click)

        self.refresh_cred_list()

    def refresh_cred_list(self):
        self.cred_tree.delete(*self.cred_tree.get_children())
        for email in sorted(self.line_data.keys(), key=str.lower):
            mark = "☑" if email in self._selected_emails else "☐"
            self.cred_tree.insert("", "end", iid=email, values=(mark, email))

    def on_add(self):
        email, password = self._prompt_line_cred()
        if not email or not password:
            return
        self.line_data[email] = password
        try:
            self.manager.write_full_line_credentials(self.line_data)
        except Exception as e:
            messagebox.showerror("Error", f"บันทึกไม่สำเร็จ: {e}")
            return
        # reload from disk to ensure consistency
        try:
            self.line_data = self.manager.load_line_credentials()
        except Exception:
            pass
        self.refresh_cred_list()
        try:
            self.cred_tree.selection_set(email)
            self.cred_tree.focus(email)
        except Exception:
            pass
        messagebox.showinfo("สำเร็จ", f"เพิ่ม/อัปเดตบัญชี {email} แล้ว")
        if hasattr(self.manager, "update_line_email_choices"):
            self.manager.update_line_email_choices()

    def on_edit(self):
        # หาอีเมลจากติ๊ก/selection/โฟกัส
        email_sel = None
        if self._selected_emails:
            email_sel = list(self._selected_emails)[0]
        elif self.cred_tree.selection():
            cand = self.cred_tree.selection()[0]
            if "@" in cand:
                email_sel = cand
            else:
                try:
                    vals = self.cred_tree.item(cand, "values")
                    email_sel = vals[1] if len(vals) > 1 else None
                except Exception:
                    email_sel = None
        else:
            focus = self.cred_tree.focus()
            if focus:
                if "@" in focus:
                    email_sel = focus
                else:
                    try:
                        vals = self.cred_tree.item(focus, "values")
                        email_sel = vals[1] if len(vals) > 1 else None
                    except Exception:
                        email_sel = None

        if not email_sel:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกบัญชีที่ต้องการแก้ไข")
            return
        # โหลดข้อมูลล่าสุดจากไฟล์เพื่อความชัวร์
        try:
            latest = self.manager.load_line_credentials()
        except Exception:
            latest = self.line_data
        old_pass = (latest or {}).get(email_sel, "")
        email, password = self._prompt_line_cred(email_sel, old_pass)
        if not email or not password:
            return
        if email != email_sel and email_sel in self.line_data:
            del self.line_data[email_sel]
        self.line_data[email] = password
        try:
            self.manager.write_full_line_credentials(self.line_data)
        except Exception as e:
            messagebox.showerror("Error", f"บันทึกไม่สำเร็จ: {e}")
            return
        try:
            self.line_data = self.manager.load_line_credentials()
        except Exception:
            pass
        self.refresh_cred_list()
        try:
            self.cred_tree.selection_set(email)
            self.cred_tree.focus(email)
        except Exception:
            pass
        if hasattr(self.manager, "update_line_email_choices"):
            self.manager.update_line_email_choices()
        messagebox.showinfo("สำเร็จ", f"แก้ไขบัญชี {email} แล้ว")

    def on_delete_selected(self):
        sels = list(self._selected_emails) or list(self.cred_tree.selection())
        if not sels:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกรายการที่จะลบ")
            return
        if not messagebox.askyesno("ยืนยันการลบ", f"ต้องการลบ {len(sels)} รายการใช่หรือไม่?"):
            return
        for iid in sels:
            if iid in self.line_data:
                del self.line_data[iid]
            if iid in self._selected_emails:
                self._selected_emails.discard(iid)
        self.manager.write_full_line_credentials(self.line_data)
        try:
            self.line_data = self.manager.load_line_credentials()
        except Exception:
            pass
        self.refresh_cred_list()
        if hasattr(self.manager, "update_line_email_choices"):
            self.manager.update_line_email_choices()
        messagebox.showinfo("สำเร็จ", f"ลบ {len(sels)} รายการแล้ว")

    def on_load(self):
        self.line_data = self.manager.load_line_credentials()
        self.refresh_cred_list()

    def on_double_click(self, event):
        self.on_edit()

    def _on_tree_click(self, event):
        # toggle tick on first column (Sel)
        region = self.cred_tree.identify("region", event.x, event.y)
        col = self.cred_tree.identify_column(event.x)
        row = self.cred_tree.identify_row(event.y)
        if region == "cell" and col == "#1" and row:
            email = row
            if email in self._selected_emails:
                self._selected_emails.discard(email)
            else:
                self._selected_emails.add(email)
            # update visual
            mark = "☑" if email in self._selected_emails else "☐"
            current = self.cred_tree.item(email, "values")
            self.cred_tree.item(email, values=(mark, current[1] if len(current)>1 else email))
            return "break"

    def open_config_folder(self):
        try:
            import os
            path = str(self.manager.line_data_path.parent)
            if os.name == 'nt':
                os.startfile(path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            messagebox.showerror("Error", f"เปิดโฟลเดอร์ไม่สำเร็จ: {e}")

    def on_cancel(self):
        self.destroy()
    def on_done(self):
        if hasattr(self.manager, "update_line_email_choices"):
            self.manager.update_line_email_choices()
        self.destroy()

    def _prompt_line_cred(self, email_init: str = "", pass_init: str = ""):
        dlg = tk.Toplevel(self)
        dlg.title("กรอก LINE Credentials")
        dlg.geometry("420x160")
        dlg.resizable(False, False)
        ttk.Label(dlg, text="LINE Email:").grid(row=0, column=0, sticky="e", padx=8, pady=8)
        e_var = tk.StringVar(value=email_init)
        e_entry = ttk.Entry(dlg, textvariable=e_var, width=30)
        e_entry.grid(row=0, column=1, padx=8, pady=8)
        ttk.Label(dlg, text="LINE Password:").grid(row=1, column=0, sticky="e", padx=8, pady=8)
        p_var = tk.StringVar(value=pass_init)
        p_entry = ttk.Entry(dlg, textvariable=p_var, width=30, show='*')
        p_entry.grid(row=1, column=1, padx=8, pady=8, sticky="w")
        # fallback กรณีบางเครื่อง textvariable ไม่ sync ให้บังคับ insert
        try:
            if not e_entry.get() and email_init:
                e_entry.insert(0, email_init)
            if not p_entry.get() and pass_init:
                p_entry.insert(0, pass_init)
        except Exception:
            pass
        # ปุ่มรูปตา กดค้างเพื่อดูรหัสผ่าน
        eye_btn = ttk.Button(dlg, text="👁")
        eye_btn.grid(row=1, column=2, padx=(4, 8), pady=8)
        def _reveal(_=None):
            try:
                p_entry.config(show='')
            except Exception:
                pass
        def _hide(_=None):
            try:
                p_entry.config(show='*')
            except Exception:
                pass
        eye_btn.bind('<ButtonPress-1>', _reveal)
        eye_btn.bind('<ButtonRelease-1>', _hide)
        result = {"ok": False}
        def on_ok():
            # อ่านค่าจาก Entry โดยตรงเพื่อกันเคส StringVar ไม่ sync ในบางระบบ
            email_in = (e_entry.get() or "").strip()
            pass_in = (p_entry.get() or "").strip()
            if not email_in or not pass_in:
                messagebox.showwarning("คำเตือน", "กรุณากรอก Email และ Password")
                return
            # ตรวจสอบฟอร์แมตอีเมลแบบง่าย
            if '@' not in email_in or ' ' in email_in:
                messagebox.showwarning("คำเตือน", "รูปแบบอีเมลไม่ถูกต้อง")
                return
            # sync StringVar to ensure return reads correctly
            try:
                e_var.set(email_in)
                p_var.set(pass_in)
            except Exception:
                pass
            result["ok"] = True
            dlg.destroy()
        def on_cancel():
            dlg.destroy()
        btn_frame = ttk.Frame(dlg)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="บันทึก", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="ยกเลิก", command=on_cancel).pack(side=tk.LEFT, padx=5)
        dlg.transient(self)
        dlg.grab_set()
        e_entry.focus_set()
        self.wait_window(dlg)
        if result["ok"]:
            try:
                email_val = e_entry.get().strip()
                pass_val = p_entry.get().strip()
            except Exception:
                email_val = e_var.get().strip()
                pass_val = p_var.get().strip()
            return email_val, pass_val
        return None, None

class ProfilesWindow(tk.Tk):
    def __init__(self, master):
        super().__init__()
        self.master = master
        self.title("จัดการ User Profiles")
        self.geometry("640x420")
        self.resizable(False, False)
        self._profiles = self._load_profiles()
        main = ttk.Frame(self, padding=(10,10))
        main.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="+ เพิ่ม", command=self.on_add).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="แก้ไข", command=self.on_edit).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="ลบ", command=self.on_delete).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="รีเฟรช", command=self.on_refresh).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="เปิดโฟลเดอร์ไฟล์", command=self.open_config_folder).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="ปิด", command=self.destroy).pack(side=tk.RIGHT, padx=3)

        self.tree = ttk.Treeview(main, columns=("Name","Firstname","Lastname","Gender","ID","Phone"), show="headings")
        for col, w in [("Name",160),("Firstname",110),("Lastname",110),("Gender",70),("ID",90),("Phone",100)]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, pady=6)

        self.refresh_tree()

    def _company_dir(self):
        import os
        from pathlib import Path
        appdata = os.environ.get('APPDATA')
        return Path(appdata) / "BokkChoYCompany" if appdata else Path.cwd()

    def _profiles_path(self):
        return self._company_dir() / "user_profiles.json"

    def _load_profiles(self):
        try:
            import json
            p = self._profiles_path()
            if not p.exists():
                return []
            data = json.load(open(p, 'r', encoding='utf-8'))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_profiles(self, profiles: list):
        import json, os
        # รักษา id เดิม ถ้า Name เดิม และจัด id ใหม่ให้รายการใหม่
        by_name = {}
        max_id = 0
        for it in (self._profiles or []):
            try:
                max_id = max(max_id, int(it.get("id") or 0))
            except Exception:
                pass
            nm = str(it.get("Name") or "").strip()
            if nm:
                by_name[nm] = it
        new_list = []
        for rec in profiles:
            nm = str(rec.get("Name") or "").strip()
            if not nm:
                continue
            base = by_name.get(nm)
            if base and (base.get("id") or 0):
                rec["id"] = int(base.get("id"))
            else:
                max_id += 1
                rec["id"] = max_id
            new_list.append({
                "id": rec.get("id"),
                "Name": nm,
                "Firstname": rec.get("Firstname", ""),
                "Lastname": rec.get("Lastname", ""),
                "Gender": rec.get("Gender", ""),
                "ID": rec.get("ID", ""),
                "Phone": rec.get("Phone", "")
            })
        # เรียงตาม id
        new_list = sorted(new_list, key=lambda x: int(x.get("id") or 0))
        # ให้แน่ใจว่าไดเรกทอรีปลายทางถูกสร้างก่อน
        try:
            p = self._profiles_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(new_list, f, ensure_ascii=False, indent=4)
        except Exception as e:
            try:
                from tkinter import messagebox
                messagebox.showerror("Error", f"บันทึกโปรไฟล์ไม่สำเร็จ: {e}")
            except Exception:
                pass
            return
        self._profiles = new_list

    def refresh_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for it in self._profiles:
            self.tree.insert("", "end", iid=str(it.get("id")), values=(
                it.get("Name",""), it.get("Firstname",""), it.get("Lastname",""), it.get("Gender",""), it.get("ID",""), it.get("Phone","")
            ))

    def on_refresh(self):
        self._profiles = self._load_profiles()
        self.refresh_tree()

    def _prompt_profile(self, init: dict | None = None):
        dlg = tk.Toplevel(self)
        dlg.title("โปรไฟล์ผู้ใช้")
        dlg.geometry("420x250")
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=(10,10))
        frm.pack(fill=tk.BOTH, expand=True)
        fields = [
            ("Name","ชื่อโปรไฟล์"),
            ("Firstname","Firstname"),
            ("Lastname","Lastname"),
            ("Gender","Gender"),
            ("ID","ID"),
            ("Phone","Phone"),
        ]
        vars = {}
        entries = {}
        for r,(key,label) in enumerate(fields):
            ttk.Label(frm, text=label+":").grid(row=r, column=0, sticky="e", padx=5, pady=4)
            v = tk.StringVar(value=(init.get(key, "") if init else ""))
            e = ttk.Entry(frm, textvariable=v, width=30)
            e.grid(row=r, column=1, padx=5, pady=4)
            vars[key] = v
            entries[key] = e
        btnbar = ttk.Frame(frm)
        btnbar.grid(row=len(fields), column=0, columnspan=2, pady=10)
        result = {"ok": False}
        def ok():
            try:
                name = entries["Name"].get().strip()
            except Exception:
                name = vars["Name"].get().strip()
            if not name:
                messagebox.showwarning("คำเตือน", "กรุณากรอกชื่อโปรไฟล์ (Name)")
                return
            # sync from entries to vars
            try:
                for k in vars:
                    if k in entries:
                        vars[k].set(entries[k].get())
            except Exception:
                pass
            result["ok"] = True
            dlg.destroy()
        ttk.Button(btnbar, text="บันทึก", command=ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btnbar, text="ยกเลิก", command=dlg.destroy).pack(side=tk.LEFT, padx=5)
        dlg.transient(self)
        dlg.grab_set()
        dlg.wait_window()
        if result["ok"]:
            try:
                data = {k: entries[k].get().strip() for k in vars.keys()}
            except Exception:
                data = {k: v.get().strip() for k,v in vars.items()}
            return data
        return None

    def on_add(self):
        data = self._prompt_profile()
        if not data:
            return
        cur = self._profiles[:]
        cur.append(data)
        self._save_profiles(cur)
        self.refresh_tree()
        try:
            self.master.update_user_profile_choices()
        except Exception:
            pass
        messagebox.showinfo("สำเร็จ", f"เพ���่มโปรไฟล์ {data.get('Name')} แล้ว")

    def on_edit(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกโปรไฟล์ที่ต้องการแก้ไข")
            return
        try:
            vals = self.tree.item(sel, 'values')
            init = next((x for x in self._profiles if str(x.get('id')) == str(sel)), None)
            if not init:
                init = {"Name": vals[0], "Firstname": vals[1], "Lastname": vals[2], "Gender": vals[3], "ID": vals[4], "Phone": vals[5]}
        except Exception:
            init = {}
        data = self._prompt_profile(init)
        if not data:
            return
        # อัปเดตตามชื่อ (หรือ id ที่เลือก)
        updated = []
        for it in self._profiles:
            if str(it.get('id')) == str(sel):
                it = {**it, **data}
            updated.append(it)
        self._save_profiles(updated)
        self.refresh_tree()
        try:
            self.master.update_user_profile_choices()
        except Exception:
            pass
        messagebox.showinfo("สำเร็จ", f"แก้ไขโปรไฟล์ {data.get('Name')} แล้ว")

    def on_delete(self):
        sels = self.tree.selection()
        if not sels:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกโปรไฟล์ที่จะลบ")
            return
        if not messagebox.askyesno("ยืนยัน", f"ต้องการลบ {len(sels)} รายการใช่หรือไม่?"):
            return
        left = [it for it in self._profiles if str(it.get('id')) not in set(sels)]
        self._save_profiles(left)
        self.refresh_tree()
        try:
            self.master.update_user_profile_choices()
        except Exception:
            pass
        messagebox.showinfo("สำเร็จ", f"ลบ {len(sels)} รายการแล้ว")

    def open_config_folder(self):
        try:
            import os
            path = str(self._company_dir())
            if os.name == 'nt':
                os.startfile(path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            messagebox.showerror("Error", f"เปิดโฟลเดอร์ไม่สำเร็จ: {e}")

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
        self.geometry("520x600")
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

        # สถานะ Today Booking
        today_frame = ttk.LabelFrame(self, text="สถานะการ Booking วันนี้", padding=(10, 5))
        today_frame.pack(pady=5, padx=10, fill="x")
        inner = ttk.Frame(today_frame)
        inner.pack(fill="x")
        self.today_canvas = tk.Canvas(inner, width=18, height=18, highlightthickness=0)
        self.today_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.today_status_var = tk.StringVar(value="กำลังตรวจสอบ...")
        ttk.Label(inner, textvariable=self.today_status_var, font=("Arial", 11)).pack(side=tk.LEFT)
        ttk.Button(inner, text="รีเฟรช", command=self.refresh_todaybooking_status).pack(side=tk.RIGHT)

        # ตรวจสอบสถานะครั้งแรก
        self.after(100, self.refresh_todaybooking_status)

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

    def refresh_todaybooking_status(self):
        try:
            from utils import is_today_booking_open
            ok = is_today_booking_open()
            today_str = datetime.now().strftime("%Y-%m-%d")
            self.today_canvas.delete("all")
            color = "#2ecc71" if ok else "#e74c3c"  # เขียว/แดง
            self.today_canvas.create_oval(2, 2, 16, 16, fill=color, outline=color)
            self.today_status_var.set(f"วันนี้ {today_str}: " + ("มีการ Booking" if ok else "ไม่มีการ Booking"))
        except Exception as e:
            self.today_canvas.delete("all")
            self.today_canvas.create_oval(2, 2, 16, 16, fill="#bdc3c7", outline="#bdc3c7")
            self.today_status_var.set(f"ตรวจสอบไม่ได้: {e}")
    
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
        try:
            TopUpDialog(self, self.user_info)
        except Exception as e:
            messagebox.showerror("เติมเงิน", f"ไม่สามารถเปิดหน้าต่างเติมเงินได้: {e}")
    
    def open_live_mode_window(self):
        allowed_roles = ["admin", "vipi", "vipii"]
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
            StartMenu().mainloop()

class MainMenuWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Welcome")
        self.geometry("360x240")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=(12, 12))
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="เลือกเมนู", font=("Arial", 13, "bold")).pack(pady=(6, 14))
        ttk.Button(frm, text="Login", command=self.open_login, width=24).pack(pady=6)
        ttk.Button(frm, text="Register", command=self.open_register, width=24).pack(pady=6)
        ttk.Button(frm, text="Contact", command=self.open_contact, width=24).pack(pady=6)
        ttk.Button(frm, text="Exit", command=self.destroy, width=24).pack(pady=(12, 0))

    def open_login(self):
        self.destroy()
        LoginWindow().mainloop()

    def open_register(self):
        self.destroy()
        RegisterWindow().mainloop()

    def open_contact(self):
        self.destroy()
        ContactWindow().mainloop()

class RegisterWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Register")
        self.geometry("400x260")
        self.resizable(False, False)
        frm = ttk.LabelFrame(self, text="สมัครผู้ใช้ใหม่", padding=(12, 12))
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Username
        ttk.Label(frm, text="Username:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.username_entry = ttk.Entry(frm, width=28)
        self.username_entry.grid(row=0, column=1, padx=6, pady=6)
        # Password
        ttk.Label(frm, text="Password:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.password_entry = ttk.Entry(frm, show="*", width=28)
        self.password_entry.grid(row=1, column=1, padx=6, pady=6)
        # Actions
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, pady=12)
        try:
            ttk.Button(btns, text="ย้อนกลับ", command=lambda: (self.destroy(), MainMenuWindow().mainloop())).pack(side=tk.LEFT, padx=6)
        except Exception:
            pass
        ttk.Button(btns, text="สมัคร", command=self.on_register).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="ยกเลิก", command=self.on_cancel).pack(side=tk.LEFT, padx=6)
        # หมายเหตุ: ค่าทั้งหมดจะถูกกำหนดโดยระบบเป็นค่าเริ่มต้น บน Google Sheet

    def on_register(self):
        username = (self.username_entry.get() or "").strip()
        password = (self.password_entry.get() or "").strip()
        if not username or not password:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Username/Password")
            return
        try:
            rec = register_user(username=username, password=password)
            messagebox.showinfo("สำเร็จ", f"สมัครผู้ใช้เรียบร้อย\nUsername: {rec['Username']}\nRole: {rec['Role']}")
            self.destroy()
            LoginWindow().mainloop()
        except Exception as e:
            messagebox.showerror("Error", f"สมัครไม่สำเร็จ: {e}")

    def on_cancel(self):
        self.destroy()
        MainMenuWindow().mainloop()

class ContactWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Contact")
        self.geometry("420x260")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=(12, 12))
        frm.pack(fill=tk.BOTH, expand=True)
        msg = (
            "ติดต่อผู้ดูแลระบบ\n\n"
            "LINE: your_line_id\n"
            "Email: support@example.com\n"
            "คู่มือการใช้งาน: https://example.com/docs\n"
        )
        txt = tk.Text(frm, wrap="word", height=8)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, msg)
        txt.config(state=tk.DISABLED)
        ttk.Button(frm, text="ย้อนกลับ", command=self.back).pack(pady=10)

    def back(self):
        self.destroy()
        MainMenuWindow().mainloop()

class LoginWindow(tk.Tk):
    def __init__(self, prev_user_info=None):
        super().__init__()
        self.user_info = None
        self.prev_user_info = prev_user_info
        self.title("Login")
        self.geometry("350x220")
        self.resizable(False, False)

        tk.Label(self, text="Username:", font=("Arial", 12)).pack(pady=(20,5))
        self.username_entry = ttk.Entry(self, font=("Arial", 11))
        self.username_entry.pack(pady=5)

        tk.Label(self, text="Password:", font=("Arial", 12)).pack(pady=(10,5))
        self.password_entry = tk.Entry(self, show="*", font=("Arial", 11))
        self.password_entry.pack(pady=5)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=20)
        login_btn = ttk.Button(btn_frame, text="Login", command=self.try_login)
        login_btn.pack(side=tk.LEFT, padx=6)
        back_btn = ttk.Button(btn_frame, text="ย้อนกลับ", command=self.on_back)
        back_btn.pack(side=tk.LEFT, padx=6)

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

    def on_back(self):
        try:
            self.destroy()
            StartMenu().mainloop()
        except Exception:
            pass

class StartMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Welcome")
        self.geometry("360x240")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=(20, 20))
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="ยินดีต้อนรับ", font=("Arial", 14, "bold")).pack(pady=(0, 12))
        ttk.Button(frm, text="Login", width=24, command=self.open_login).pack(pady=6)
        ttk.Button(frm, text="Register", width=24, command=self.open_register).pack(pady=6)
        ttk.Button(frm, text="Contact", width=24, command=self.open_contact).pack(pady=6)
        ttk.Button(frm, text="Exit", width=24, command=self.destroy).pack(pady=(10, 0))

    def open_login(self):
        self.destroy()
        LoginWindow().mainloop()

    def open_register(self):
        dlg = tk.Toplevel(self)
        dlg.title("Register")
        dlg.geometry("320x200")
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=(10,10))
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Username:").grid(row=0, column=0, sticky="e", padx=5, pady=6)
        user_var = tk.StringVar()
        ttk.Entry(frm, textvariable=user_var, width=24).grid(row=0, column=1, padx=5, pady=6)

        ttk.Label(frm, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=6)
        pass_var = tk.StringVar()
        ttk.Entry(frm, textvariable=pass_var, show="*", width=24).grid(row=1, column=1, padx=5, pady=6)

        btnbar = ttk.Frame(frm)
        btnbar.grid(row=2, column=0, columnspan=2, pady=10)
        reg_btn = ttk.Button(btnbar, text="Register")
        reg_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btnbar, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=5)

        def on_done(result):
            try:
                reg_btn.config(state=tk.NORMAL)
            except Exception:
                pass
            status, payload = result
            if status == "OK":
                try:
                    dlg.destroy()
                except Exception:
                    pass
                messagebox.showinfo("สำเร็จ", "ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบด้วยบัญชีของคุณ")
            else:
                messagebox.showerror("ล้มเหลว", f"ลงทะเบียนไม่สำเร็จ: {payload}")

        def do_register():
            username = (user_var.get() or "").strip()
            password = (pass_var.get() or "").strip()
            if not username or not password:
                messagebox.showwarning("คำเตือน", "กรุณากรอก Username/Password")
                return
            try:
                reg_btn.config(state=tk.DISABLED)
            except Exception:
                pass
            def worker():
                try:
                    info = register_user(username, password, role="normal", max_sites=1, can_schedule="ไม่")
                    self.after(0, lambda: on_done(("OK", info)))
                except Exception as e:
                    self.after(0, lambda: on_done(("ERR", str(e))))
            threading.Thread(target=worker, daemon=True).start()

        reg_btn.config(command=do_register)
        dlg.transient(self)
        dlg.grab_set()
        dlg.focus_set()

    def open_contact(self):
        messagebox.showinfo("Contact", "Contact us: LINE ID @lockonstatosx")

def main():
    setup_config_files()
    StartMenu().mainloop()

if __name__ == "__main__":
    main()
