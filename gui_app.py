# gui_app.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading, asyncio, json, traceback, re
from datetime import datetime
from typing import Any, Dict, Optional
import time

# Import ระบบใหม่
from window_manager import window_manager
from error_handler import safe_execute, handle_async_error, ErrorReporter
from logger_config import setup_logging, get_logger, log_performance, cleanup_old_logs

# Setup logging
logger = setup_logging()
cleanup_old_logs()

# ---- internal modules (มีอยู่ในโปรเจ็กต์) ----
from chrome_op import launch_chrome_instance as launch_chrome_with_profile
from edge_op import launch_edge_with_profile
from real_booking import perform_real_booking, attach_to_chrome
from playwright_ops import launch_browser_and_perform_booking as trial_booking  # (ยังคงใช้ในโหมดทดลอง)
from Scheduledreal_booking import ScheduledManager
from ultrafast_booking import run_ultrafast_booking
from topup import TopUpDialog
from Scroll_ import ScrollableFrame

# ---- utils หลัก (ต่อ backend + ไฟล์ตั้งค่า) ----
from utils import (
    get_all_api_data, google_sheet_check_login, setup_config_files,
    start_license_session, is_today_booking_open, get_user_profile_names,
    register_user, load_line_credentials, load_user_profile,
    BACKEND_URL
)

# ---- optional admin helpers (มีหรือไม่มีก็ได้) ----
try:
    # ถ้าผู้ใช้มีไฟล์ utils_admin.py เราจะใช้ class ข้างใน
    from utils_admin import AdminClient as _UtilsAdminClient  # type: ignore
except Exception:
    _UtilsAdminClient = None  # noqa

try:
    # ถ้ามี admin_console_handlers.py จะพยายามใช้
    import admin_console_handlers as _ACH  # type: ignore
except Exception:
    _ACH = None  # noqa

import requests

# ----------------------------- Style / Theme helpers -----------------------------
def _get_app_icon_image():
    try:
        import base64, os
        from tkinter import PhotoImage
        # try load from assets folder (first png)
        assets = os.path.join(os.getcwd(), 'assets')
        if os.path.isdir(assets):
            for name in os.listdir(assets):
                if name.lower().endswith('.png'):
                    try:
                        return PhotoImage(file=os.path.join(assets, name))
                    except Exception:
                        pass
        # fallback: 16x16 simple dot icon (base64 PNG)
        _PNG = (
            b"iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAQAAAC1+jfqAAAAPUlEQVQoz2NgoBvgw4AFYGBg/0cZQwZgMBlG\n"
            b"kA0QZBqDgYGB4T8ZyJgYGBZCwGQYFQ8wEJg1gYGBgYJkAwEAAKQ1G7mP0b2fAAAAAElFTkSuQmCC"
        )
        return PhotoImage(data=base64.b64decode(_PNG))
    except Exception:
        return None

def apply_app_style(root: tk.Tk):
    """Apply only app icon from assets; do not change theme/colors."""
    try:
        icon = _get_app_icon_image()
        if icon is not None:
            root.iconphoto(True, icon)
    except Exception:
        pass

def _friendly_expiration(s: str) -> str:
    try:
        txt = (s or '').strip()
        if not txt:
            return '-'
        # handle Z suffix
        if txt.endswith('Z'):
            txt = txt[:-1]
        # try parse with microseconds or not
        from datetime import datetime
        for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
            try:
                dt = datetime.strptime(txt, fmt)
                break
            except Exception:
                dt = None
        if not dt:
            return s
        # to local string
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return s

# ----------------------------- ค่าตายตัวของ GUI -----------------------------
profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"]
edge_profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"]
browsers = ["Chrome", "Edge"]
LIVE_SITES = ["ROCKETBOOKING"]
TRIAL_SITES = ["EZBOT", "PMROCKET"]
days = [str(i) for i in range(1, 32)]


# ----------------------------- Admin API Wrapper -----------------------------
class AdminApi:
    """ตัวห่อ (wrapper) ให้ Admin Console ใช้งาน — พยายามใช้ utils_admin/admin_console_handlers ก่อน
    ถ้าไม่มี จะ fallback เรียก REST API ตรงไปที่ BACKEND_URL
    """
    def __init__(self, token: str):
        self._token = token
        self._headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
        self._client = None
        if _UtilsAdminClient:
            try:
                self._client = _UtilsAdminClient(base_url=BACKEND_URL, token=token)  # type: ignore
            except Exception:
                self._client = None

    # ------------------ Users ------------------
    def list_users(self) -> list[dict]:
        # 1) utils_admin
        if self._client and hasattr(self._client, "list_users"):
            try:
                return list(self._client.list_users())  # type: ignore
            except Exception:
                pass
        # 2) admin_console_handlers
        if _ACH and hasattr(_ACH, "list_users"):
            try:
                return list(_ACH.list_users(self._token))  # type: ignore
            except Exception:
                pass
        # 3) Fallback REST
        try:
            r = requests.get(f"{BACKEND_URL}/admin/users", headers=self._headers, timeout=10)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, dict):
                items = j.get("items") or j.get("users") or []
                if isinstance(items, list):
                    # normalize exp_date -> expires_at for GUI
                    out = []
                    for it in items:
                        if isinstance(it, dict) and ("exp_date" in it) and ("expires_at" not in it):
                            it = {**it, "expires_at": it.get("exp_date")}
                        out.append(it)
                    return out
            if isinstance(j, list):
                return j
        except Exception:
            pass
        return []

    def update_user(self, username: str, fields: dict) -> bool:
        # utils_admin
        if self._client and hasattr(self._client, "update_user"):
            try:
                return bool(self._client.update_user(username, fields))  # type: ignore
            except Exception:
                pass
        # admin_console_handlers
        if _ACH and hasattr(_ACH, "update_user"):
            try:
                return bool(_ACH.update_user(self._token, username, fields))  # type: ignore
            except Exception:
                pass
        # REST
        try:
            r = requests.put(
                f"{BACKEND_URL}/admin/users/{username}",
                headers=self._headers, json=fields, timeout=10
            )
            if r.status_code in (200, 204):
                return True
        except Exception:
            pass
        return False

    def delete_user(self, username: str) -> bool:
        if self._client and hasattr(self._client, "delete_user"):
            try:
                return bool(self._client.delete_user(username))  # type: ignore
            except Exception:
                pass
        if _ACH and hasattr(_ACH, "delete_user"):
            try:
                return bool(_ACH.delete_user(self._token, username))  # type: ignore
            except Exception:
                pass
        try:
            r = requests.delete(
                f"{BACKEND_URL}/admin/users/{username}",
                headers=self._headers, timeout=10
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    def reset_password(self, username: str, new_password: str) -> bool:
        # Prefer utils_admin/admin_console_handlers if available, else REST
        if self._client and hasattr(self._client, "reset_password"):
            try:
                return bool(self._client.reset_password(username, new_password))  # type: ignore
            except Exception:
                pass
        if _ACH and hasattr(_ACH, "reset_password"):
            try:
                return bool(_ACH.reset_password(self._token, username, new_password))  # type: ignore
            except Exception:
                pass
        try:
            r = requests.post(
                f"{BACKEND_URL}/admin/users/reset-password",
                headers=self._headers, json={"username": username, "new_password": new_password}, timeout=10
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    # ------------------ TodayBooking ------------------
    def get_todaybooking_open(self) -> Optional[bool]:
        # utils_admin
        if self._client and hasattr(self._client, "get_todaybooking_open"):
            try:
                return bool(self._client.get_todaybooking_open())  # type: ignore
            except Exception:
                pass
        # admin_console_handlers
        if _ACH and hasattr(_ACH, "get_todaybooking_open"):
            try:
                return bool(_ACH.get_todaybooking_open(self._token))  # type: ignore
            except Exception:
                pass
        # REST
        try:
            r = requests.get(f"{BACKEND_URL}/todaybooking/open", headers=self._headers, timeout=10)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            j = r.json()
            return bool(j.get("open", False))
        except Exception:
            return None

    def set_todaybooking_open(self, open_flag: bool) -> bool:
        # utils_admin
        if self._client and hasattr(self._client, "set_todaybooking_open"):
            try:
                return bool(self._client.set_todaybooking_open(open_flag))  # type: ignore
            except Exception:
                pass
        # admin_console_handlers
        if _ACH and hasattr(_ACH, "set_todaybooking_open"):
            try:
                return bool(_ACH.set_todaybooking_open(self._token, open_flag))  # type: ignore
            except Exception:
                pass
        # REST
        try:
            r = requests.post(
                f"{BACKEND_URL}/todaybooking/open",
                headers=self._headers, json={"open": bool(open_flag)}, timeout=10
            )
            return r.status_code in (200, 204)
        except Exception:
            return False


# ----------------------------- Booking Process Window -----------------------------
class BookingProcessWindow(tk.Tk):
    def __init__(self, parent_window_class, user_info, mode, site_name, browser_type,
                 all_api_data, selected_branch, selected_day, selected_time,
                 register_by_user, confirm_by_user, cdp_port=None, round_index=None,
                 timer_seconds=None, delay_seconds=None, auto_line_login=False,
                 user_profile_name=None, enable_fallback: bool=False):
        super().__init__()
        apply_app_style(self)
        self.parent_window_class = parent_window_class
        self.user_info = user_info
        self.all_api_data = all_api_data

        self.title("สถานะการจอง")
        self.geometry("640x520")
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
        self.user_profile_name = user_profile_name
        self.enable_fallback = bool(enable_fallback)

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

    def update_status(self, message):
        def inner():
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)
        self.after(0, inner)

    @safe_execute()
    def on_ok(self):
        self.destroy()
        # ตรวจว่ามาจาก Simple Mode หรือไม่
        if hasattr(self, 'parent_window_class') and self.parent_window_class.__name__ == 'SimpleModeWindow':
            from simple_mode import SimpleModeWindow
            SimpleModeWindow(user_info=self.user_info, api_data=self.all_api_data).mainloop()
        else:
            from gui_app import App
            App(self.user_info).mainloop()

    @safe_execute()
    def on_cancel(self):
        if self._async_loop and self._async_loop.is_running():
            self.update_status("🚨 กำลังยกเลิกการทำงาน...")
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
            self.thread.join(timeout=2)
        messagebox.showinfo("ยกเลิก", "การจองถูกยกเลิกแล้ว")
        self.destroy()
        # ตรวจว่ามาจาก Simple Mode หรือไม่
        if hasattr(self, 'parent_window_class') and self.parent_window_class.__name__ == 'SimpleModeWindow':
            from simple_mode import SimpleModeWindow
            SimpleModeWindow(user_info=self.user_info, api_data=self.all_api_data).mainloop()
        else:
            from gui_app import App
            App(self.user_info).mainloop()

    @safe_execute()
    def start_booking_process(self):
        start_time = time.time()
        self.thread = threading.Thread(target=self._run_async_booking, daemon=True)
        self.thread.start()
        log_performance("start_booking_process", time.time() - start_time)

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
            ErrorReporter.report_critical(e, "Booking process failed")
            self.update_status(f"❌ เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")
        finally:
            self.update_status("🟢 กระบวนการสิ้นสุดแล้ว")
            self.after(0, lambda: self.ok_btn.config(state=tk.NORMAL))
            if self._async_loop and not self._async_loop.is_closed():
                self._async_loop.close()

    async def _run_live_booking(self):
        playwright = None
        license_session = None
        try:
            # todaybooking guard
            try:
                if not is_today_booking_open():
                    self.update_status("ℹ️ วันนี้ไม่มีการจอง (อ้างอิง todaybooking)")
                    return
                else:
                    self.update_status("🗓️ วันนี้มีการจองตาม todaybooking")
            except Exception as e:
                self.update_status(f"⚠️ ตรวจสอบ todaybooking ไม่สำเร็จ: {e}")

            self.update_status("⏳ กำลังรอเชื่อมต่อกับเบราว์เซอร์ที่เปิดอยู่...")

            # license moved below attach_to_chrome with retry; do not block early

            self.update_status(f"🔌 กำลั��เชื่อมต่อพอร์ต {self.cdp_port} ...")
            playwright, browser, context, page = await attach_to_chrome(self.cdp_port, self.update_status)
            self.update_status("✅ เชื่อมต่อกับเบราว์เซอร์สำเร็จ!")

            # License acquisition (non-blocking with short retries)
            try:
                if self.cdp_port and (license_session is None):
                    for i in range(3):
                        try:
                            license_session = start_license_session(self.user_info, port=self.cdp_port, version="1.0")
                        except Exception:
                            license_session = None
                        if license_session:
                            break
                        self.update_status(f"⚠️ จองสิทธิ์ไม่สำเร็จ กำลังลองใหม่ ({i+1}/3)...")
                        await asyncio.sleep(1.2)
                    if license_session:
                        self.update_status("🟢 จองสิทธิ์ใช้งานสำเร็จ")
                    else:
                        self.update_status("⚠️ ไม่สามารถจองสิทธิ์ได้ จะดำเนินการต่อ (โ��รดตรวจสอบว่าไม่มีอินสแตนซ์อื่นใช้งานอยู่)")
            except Exception:
                pass

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
                auto_line_login=self.auto_line_login,
                user_profile_name=self.user_profile_name,
                enable_fallback=bool(getattr(self, 'enable_fallback', False))
            )
        except asyncio.CancelledError:
            self.update_status("🚨 Task ถูกยกเลิก")
        except Exception as e:
            self.update_status(f"❌ เกิดข้อผิดพลาดในการจอง: {e}")
            traceback.print_exc()
        finally:
            try:
                if license_session:
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
            self.update_status(f"❌ โหมดทดลองผิดพลาด: {e}")
            traceback.print_exc()
        finally:
            if self._async_loop and not self._async_loop.is_closed():
                self._async_loop.create_task(asyncio.sleep(0)).cancel()




# ----------------------------- Profile Login Window -----------------------------
class ProfileLoginWindow(tk.Tk):
    def __init__(self, user_info, browser_type, profile_name, line_email):
        super().__init__()
        apply_app_style(self)
        self.user_info = user_info
        self.browser_type = browser_type
        self.profile_name = profile_name
        self.line_email = line_email
        self.browser_to_close = None
        self.playwright_to_close = None
        
        self.title("Profile Login")
        self.geometry("640x520")
        self.resizable(True, True)
        
        main_frame = ttk.Frame(self, padding=(10, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.status_text = tk.Text(main_frame, wrap="word", font=("Arial", 10), height=15)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.config(state=tk.DISABLED)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        self.ok_btn = ttk.Button(button_frame, text="ตกลง", command=self.on_ok, state=tk.DISABLED)
        self.ok_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = ttk.Button(button_frame, text="ยกเลิก", command=self.on_cancel)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.start_profile_login()
    
    def update_status(self, message):
        def inner():
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)
        self.after(0, inner)
    
    def start_profile_login(self):
        threading.Thread(target=self._run_profile_login, daemon=True).start()
    
    def _run_profile_login(self):
        try:
            self.update_status(f"⏳ เริ่มต้น Profile Login...")
            self.update_status(f"🔧 Browser: {self.browser_type}")
            self.update_status(f"📁 Profile: {self.profile_name}")
            self.update_status(f"📧 LINE Email: {self.line_email}")
            
            self.update_status(f"🚀 กำลังเปิด {self.browser_type} ด้วย Profile {self.profile_name}...")
            
            launched_port = None
            if self.browser_type == "Chrome":
                launched_port, _ = launch_chrome_with_profile(self.profile_name)
            else:
                launched_port, _ = launch_edge_with_profile(self.profile_name)
            
            if not launched_port:
                self.update_status("❌ ไม่สามารถเปิดเบราว์เซอร์ได้")
                return
            
            self.update_status(f"✅ เปิดเบราว์เซอร์สำเร็จ! Port: {launched_port}")
            
            # Auto login to LINE
            self.update_status("🔐 กำลังเชื่อมต่อกับเบราว์เซอร์เพื่อ Login LINE...")
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                from real_booking import attach_to_chrome
                playwright, browser, context, page = loop.run_until_complete(
                    attach_to_chrome(launched_port, self.update_status)
                )
                
                self.update_status("🌐 เข้าสู่หน้า Booking...")
                loop.run_until_complete(page.goto("https://popmartth.rocket-booking.app/booking"))
                
                self.update_status("⏳ รอหน้าเว็บโหลดเสร็จ...")
                
                # Wait for page to fully load
                try:
                    # Wait for navigation and dynamic content
                    loop.run_until_complete(page.wait_for_load_state("networkidle", timeout=15000))
                    loop.run_until_complete(asyncio.sleep(3))
                    self.update_status("✅ หน้าเว็บโหลดเสร็จแล้ว")
                except Exception as e:
                    self.update_status(f"⚠️ รอหน้าโหลด: {e}")
                    loop.run_until_complete(asyncio.sleep(5))  # Fallback wait
                
                # Check if we're on booking page and click profile
                self.update_status("🔍 ตรวจสอบหน้า Booking...")
                
                try:
                    current_url = page.url.lower()
                    if "booking" in current_url:
                        self.update_status("✅ อยู่หน้า Booking แล้ว")
                        
                        # Click profile button
                        self.update_status("👤 กดปุ่มโปรไฟล์...")
                        
                        profile_selectors = [
                            "a[href='/profile']",
                            "a:has-text('โปรไฟล์')",
                            "button:has-text('โปรไฟล์')",
                            "a:has-text('Profile')",
                            "button:has-text('Profile')",
                            ".profile-link",
                            "[data-testid='profile']"
                        ]
                        
                        profile_clicked = False
                        for selector in profile_selectors:
                            try:
                                if loop.run_until_complete(page.is_visible(selector, timeout=3000)):
                                    loop.run_until_complete(page.click(selector, timeout=3000))
                                    self.update_status(f"✅ กดโปรไฟล์สำเร็จ: {selector}")
                                    profile_clicked = True
                                    break
                            except Exception:
                                continue
                        
                        if not profile_clicked:
                            self.update_status("⚠️ ไม่พบปุ่มโปรไฟล์ - กรุณาคลิกด้วยตัวเอง แล้วกด OK")
                            # Wait for manual click and continue
                            loop.run_until_complete(asyncio.sleep(10))
                            self.update_status("⏳ รอให้คลิกโปรไฟล์ด้วยตัวเอง...")
                        
                        # Wait for profile page to load
                        loop.run_until_complete(asyncio.sleep(3))
                        self.update_status("✅ อยู่หน้า Profile แล้ว")
                        
                        # Check login status with multiple selectors
                        logout_selectors = [
                            "p.textred:has-text('ออกจากระบบ')",
                            ":has-text('ออกจากระบบ')",
                            "button:has-text('ออกจากระบบ')",
                            "a:has-text('ออกจากระบบ')"
                        ]
                        
                        connect_selectors = [
                            "button:has-text('Connect LINE Account')",
                            ":has-text('Connect LINE Account')",
                            "button:has-text('Connect')",
                            ":has-text('Connect')",
                            "a:has-text('Connect')",
                            ".connect-button",
                            "[data-testid*='connect']"
                        ]
                        
                        logout_found = False
                        for selector in logout_selectors:
                            try:
                                if loop.run_until_complete(page.is_visible(selector, timeout=2000)):
                                    logout_found = True
                                    self.update_status(f"✅ เจอปุ่ม 'ออกจากระบบ' - Login แล้ว! ({selector})")
                                    break
                            except Exception:
                                continue
                        
                        if logout_found:
                            success = True
                        else:
                            success = False  # Initialize success variable
                            connect_found = False
                            for selector in connect_selectors:
                                try:
                                    if loop.run_until_complete(page.is_visible(selector, timeout=2000)):
                                        connect_found = True
                                        self.update_status(f"🔗 เจอปุ่ม Connect - ต้อง Login LINE ({selector})")
                                        break
                                except Exception:
                                    continue
                            
                            if connect_found:
                                # Click Connect button first
                                self.update_status("🔗 กำลังคลิกปุ่ม Connect...")
                                connect_clicked = False
                                for selector in connect_selectors:
                                    try:
                                        self.update_status(f"🔍 ลองหา: {selector}")
                                        if loop.run_until_complete(page.is_visible(selector, timeout=3000)):
                                            self.update_status(f"✅ เจอแล้ว กำลังคลิก: {selector}")
                                            loop.run_until_complete(page.click(selector, timeout=5000))
                                            self.update_status(f"✅ กดปุ่ม Connect สำเร็จ: {selector}")
                                            connect_clicked = True
                                            break
                                        else:
                                            self.update_status(f"❌ ไม่เจอ: {selector}")
                                    except Exception as e:
                                        self.update_status(f"⚠️ ผิดพลาดกับ {selector}: {e}")
                                        continue
                                
                                if connect_clicked:
                                    # Wait for second Connect button to appear
                                    loop.run_until_complete(asyncio.sleep(2))
                                    
                                    # Look for and click "Connect LINE Account*" button
                                    second_connect_selectors = [
                                        "button:has-text('Connect LINE Account')",
                                        ":has-text('Connect LINE Account')",
                                        "button:contains('Connect LINE Account')",
                                        "button[class*='connect']"
                                    ]
                                    
                                    second_clicked = False
                                    for selector in second_connect_selectors:
                                        try:
                                            if loop.run_until_complete(page.is_visible(selector, timeout=3000)):
                                                loop.run_until_complete(page.click(selector, timeout=5000))
                                                self.update_status(f"✅ กดปุ่ม Connect LINE Account สำเร็จ: {selector}")
                                                second_clicked = True
                                                break
                                        except Exception:
                                            continue
                                    
                                    # Wait for LINE login page to load
                                    loop.run_until_complete(asyncio.sleep(3))
                                    
                                    # Check if we're on LINE OAuth page
                                    current_url = loop.run_until_complete(page.evaluate("window.location.href"))
                                    if "access.line.me" in current_url:
                                        # Check for Quick Login first
                                        quick_login_btn = "#app > div > div > div > div > div > div.LyContents01 > div > div.login-button > button"
                                        different_account_link = "#app > div > div > div > div > div > div.LyContents01 > div > div.login-with-different-account > a"
                                        
                                        try:
                                            if loop.run_until_complete(page.is_visible(quick_login_btn, timeout=3000)):
                                                self.update_status("🔑 เจอ Quick Login - กำลังกดปุ่ม Log in")
                                                try:
                                                    loop.run_until_complete(page.click(quick_login_btn))
                                                    self.update_status("✅ Quick Login สำเร็จ - กดปุ่มได้")
                                                    success = True
                                                except Exception:
                                                    self.update_status("⚠️ Quick Login ไม่สำเร็จ - ปุ่ม disabled")
                                                    success = False
                                            elif loop.run_until_complete(page.is_visible(different_account_link, timeout=2000)):
                                                self.update_status("🔑 เจอ 'Log in to another account' - กำลังคลิก")
                                                loop.run_until_complete(page.click(different_account_link))
                                                loop.run_until_complete(asyncio.sleep(2))
                                                # Continue to normal login below
                                                self.update_status("🔑 อยู่หน้า LINE OAuth - ใช้โหมด Normal Login")
                                            else:
                                                self.update_status("🔑 อยู่หน้า LINE OAuth - ใช้โหมด Normal Login")
                                        except Exception:
                                            self.update_status("🔑 อยู่หน้า LINE OAuth - ใช้โหมด Normal Login")
                                        # Fill email and password directly (only if Quick Login failed)
                                        if not success:
                                            try:
                                                # Get password from credentials first
                                                from utils import load_line_credentials
                                                creds = load_line_credentials()
                                                password = None
                                                if isinstance(creds, dict):
                                                    password = creds.get(self.line_email)
                                                elif isinstance(creds, list):
                                                    for item in creds:
                                                        if item.get('Email') == self.line_email:
                                                            password = item.get('Password')
                                                            break
                                                
                                                if not password:
                                                    self.update_status("⚠️ ไม่พบ Password สำหรับ Email นี้")
                                                    success = False
                                                else:
                                                    # Use selectors from line_login.py
                                                    email_selectors = [
                                                        "#app > div > div > div > div.MdBox01 > div > form > fieldset > div:nth-child(2) > input[type=text]",
                                                        "input[type='email']",
                                                        "input[name='tid']",
                                                        "input[name='username']",
                                                        "input[placeholder*='Email' i]",
                                                        "input[placeholder*='อีเมล']"
                                                    ]
                                                    
                                                    password_selectors = [
                                                        "#app > div > div > div > div.MdBox01 > div > form > fieldset > div:nth-child(3) > input[type=password]",
                                                        "input[type='password']",
                                                        "input[name='tpasswd']",
                                                        "input[name='password']",
                                                        "input[placeholder*='Password' i]",
                                                        "input[placeholder*='รหัส']"
                                                    ]
                                                    
                                                    login_selectors = [
                                                        "#app > div > div > div > div.MdBox01 > div > form > fieldset > div.mdFormGroup01Btn > button",
                                                        "#app > div > div > div > div > div > div.LyContents01 > div > div.login-button > button",
                                                        "button[type='submit']",
                                                        "button:has-text('Log in')",
                                                        "button:has-text('Login')",
                                                        "button:has-text('เข้าสู่ระบบ')"
                                                    ]
                                                    
                                                    # Fill email
                                                    email_filled = False
                                                    for selector in email_selectors:
                                                        try:
                                                            if loop.run_until_complete(page.is_visible(selector, timeout=2000)):
                                                                loop.run_until_complete(page.fill(selector, self.line_email))
                                                                self.update_status(f"✅ ใส่ Email: {self.line_email}")
                                                                email_filled = True
                                                                break
                                                        except Exception:
                                                            continue
                                                    
                                                    # Fill password
                                                    password_filled = False
                                                    if email_filled:
                                                        for selector in password_selectors:
                                                            try:
                                                                if loop.run_until_complete(page.is_visible(selector, timeout=2000)):
                                                                    loop.run_until_complete(page.fill(selector, password))
                                                                    self.update_status("✅ ใส่ Password")
                                                                    password_filled = True
                                                                    break
                                                            except Exception:
                                                                continue
                                                    
                                                    # Click login button
                                                    if email_filled and password_filled:
                                                        for selector in login_selectors:
                                                            try:
                                                                if loop.run_until_complete(page.is_visible(selector, timeout=2000)):
                                                                    loop.run_until_complete(page.click(selector))
                                                                    self.update_status("✅ กดปุ่ม Login")
                                                                    break
                                                            except Exception:
                                                                continue
                                                        
                                                        # Wait for OTP or redirect completion
                                                        otp_selector = "#app > div > div > div > div > div > div.MdMN06DigitCode > div.mdMN06CodeBox"
                                                        booking_marker = "body > div > div.sc-715cd296-0.fYuIyy > div > div:nth-child(1) > a > p"
                                                        otp_shown = False
                                                        
                                                        for wait_attempt in range(40):  # Wait up to 40 seconds
                                                            try:
                                                                # Check if back to booking page
                                                                if loop.run_until_complete(page.is_visible(booking_marker, timeout=1000)):
                                                                    success = True
                                                                    break
                                                                
                                                                # Check if OTP page is visible
                                                                if loop.run_until_complete(page.is_visible(otp_selector, timeout=1000)):
                                                                    if not otp_shown:
                                                                        self.update_status("⌛ รอยืนยันตัวตนในมือถือ (LINE) ...")
                                                                        otp_shown = True
                                                            except Exception:
                                                                pass
                                                            loop.run_until_complete(asyncio.sleep(1))
                                                        else:
                                                            success = False
                                                    else:
                                                        success = False
                                            except Exception as e:
                                                self.update_status(f"⚠️ ผิดพลาดในการใส่ข้อมูล: {e}")
                                                success = False
                                    else:
                                        # Use normal line_login for other cases
                                        from line_login import perform_line_login, set_ui_helpers
                                        
                                        ui_helpers = {
                                            "booking_marker": "body > div > div.sc-715cd296-0.fYuIyy > div > div:nth-child(1) > a > p"
                                        }
                                        set_ui_helpers(ui_helpers)
                                    
                                        success = loop.run_until_complete(
                                            perform_line_login(
                                                page=page,
                                                progress_callback=self.update_status,
                                                preferred_email=self.line_email
                                            )
                                        )
                                    
                                    # Verify login success by checking for logout button
                                    if success:
                                        loop.run_until_complete(asyncio.sleep(3))
                                        # Navigate back to profile to verify
                                        loop.run_until_complete(page.goto("https://popmartth.rocket-booking.app/profile"))
                                        loop.run_until_complete(asyncio.sleep(2))
                                        
                                        # Check if logout button exists now
                                        final_check = False
                                        for selector in logout_selectors:
                                            try:
                                                if loop.run_until_complete(page.is_visible(selector, timeout=3000)):
                                                    final_check = True
                                                    self.update_status(f"✅ ยืนยัน Login สำเร็จ - เจอปุ่มออกจากระบบ")
                                                    break
                                            except Exception:
                                                continue
                                        
                                        if not final_check:
                                            self.update_status("⚠️ Login อาจไม่สำเร็จ - ไม่เจอปุ่มออกจากระบบ")
                                            success = False
                                else:
                                    self.update_status("⚠️ ไม่สามารถคลิกปุ่ม Connect ได้")
                                    success = False
                            else:
                                self.update_status("⚠️ ไม่เจอปุ่ม Connect หรือ ออกจากระบบ - ลองดูหน้าเว็บด้วยตัวเอง")
                                success = False
                    else:
                        self.update_status(f"⚠️ ไม่ได้อยู่หน้า Booking: {current_url}")
                        success = False
                except Exception as e:
                    self.update_status(f"⚠️ เกิดข้อผิดพลาดในการตรวจสอบหน้า: {e}")
                    success = False
                
                if success:
                    self.update_status("✅ Login LINE สำเร็จ!")
                    self.update_status("✅ ตรวจสอบโปรไฟล์เสร็จสิ้น!")
                    self.update_status("🎉 เสร็จสิ้นทุกขั้ตอน!")
                    
                    # Close browser immediately and show success
                    try:
                        loop.run_until_complete(browser.close())
                        loop.run_until_complete(playwright.stop())
                        # Kill Chrome/Edge processes
                        import subprocess
                        try:
                            if self.browser_type == "Chrome":
                                subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], capture_output=True)
                            else:
                                subprocess.run(["taskkill", "/f", "/im", "msedge.exe"], capture_output=True)
                        except Exception:
                            pass
                        self.update_status("🚫 ปิด Browser แล้ว")
                    except Exception as e:
                        self.update_status(f"⚠️ ปิด Browser ไม่ได้: {e}")
                    
                    self.after(0, self.show_success_popup)
                    return
                else:
                    self.update_status("⚠️ Login LINE ไม่สำเร็จ - กรุณา Login ด้วยตัวเอง")
                
                # Close browser for failed case
                try:
                    loop.run_until_complete(browser.close())
                    loop.run_until_complete(playwright.stop())
                    # Kill Chrome/Edge processes
                    import subprocess
                    try:
                        if self.browser_type == "Chrome":
                            subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], capture_output=True)
                        else:
                            subprocess.run(["taskkill", "/f", "/im", "msedge.exe"], capture_output=True)
                    except Exception:
                        pass
                    self.update_status("🚫 ปิด Browser แล้ว")
                except Exception as e:
                    self.update_status(f"⚠️ ปิด Browser ไม่ได้: {e}")
                
            except Exception as e:
                self.update_status(f"⚠️ Auto login ล้มเหลว: {e}")
                self.update_status("📝 กรุณา Login LINE ด้วยตัวเองในเบราว์เซอร์")
            finally:
                loop.close()
            
        except Exception as e:
            self.update_status(f"❌ เกิดข้อผิดพลาด: {e}")
        finally:
            if not hasattr(self, 'browser_to_close') or not self.browser_to_close:
                self.after(0, lambda: self.ok_btn.config(state=tk.NORMAL))
    

    
    def show_success_popup(self):
        """Show success popup after browser is closed"""
        messagebox.showinfo(
            "LOGIN สำเร็จ", 
            "LOGIN LINE เรียบร้อยแล้ว\nกรุณากดปุ่มเริ่มการจองได้เลย"
        )
        
        # Return to main app
        self.on_ok()
    
    def close_browser_and_exit(self):
        """Close browser and return to main app"""
        def _close():
            try:
                if self.browser_to_close:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.browser_to_close.close())
                    loop.close()
                    self.update_status("🚫 ปิด Browser แล้ว")
            except Exception as e:
                self.update_status(f"⚠️ ปิด Browser ไม่ได้: {e}")
            finally:
                self.after(1000, self.on_ok)  # Return to main app after 1 second
        
        threading.Thread(target=_close, daemon=True).start()
    
    def on_ok(self):
        self.destroy()
        App(self.user_info).mainloop()
    
    def on_cancel(self):
        self.destroy()
        App(self.user_info).mainloop()


# ----------------------------- Single Booking Window -----------------------------
class SingleBookingWindow(tk.Tk):
    def __init__(self, user_info, all_api_data):
        super().__init__()
        self.user_info = user_info
        self.all_api_data = all_api_data
        self.title("จองทีละครั้ง")
        self.geometry("560x760")
        self.resizable(True, True)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.scrollable = ScrollableFrame(self)
        self.scrollable.pack(fill=tk.BOTH, expand=True)
        main_frame = self.scrollable.scrollable_frame

        tk.Label(main_frame, text="เลือก Site:", font=("Arial", 12)).pack(pady=(10, 3))
        self.site_var = tk.StringVar(value=LIVE_SITES[0])
        self.site_combo = ttk.Combobox(main_frame, values=LIVE_SITES, textvariable=self.site_var, state="readonly", font=("Arial", 11))
        self.site_combo.pack(pady=5)

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

        # ตัวเลือกขั้นสูง
        adv = ttk.LabelFrame(main_frame, text="ตัวเลือกขั้นสูง", padding=(10, 6))
        adv.pack(fill="x", pady=(10, 6))
        ttk.Label(adv, text="Round (index):").grid(row=0, column=0, sticky="w")
        self.round_var = tk.StringVar(value="")
        ttk.Entry(adv, textvariable=self.round_var, width=8).grid(row=0, column=1, padx=5)
        ttk.Label(adv, text="Timer (sec):").grid(row=0, column=2, sticky="w")
        self.timer_var = tk.StringVar(value="")
        ttk.Entry(adv, textvariable=self.timer_var, width=8).grid(row=0, column=3, padx=5)
        ttk.Label(adv, text="Delay (sec):").grid(row=0, column=4, sticky="w")
        self.delay_var = tk.StringVar(value="")
        ttk.Entry(adv, textvariable=self.delay_var, width=8).grid(row=0, column=5, padx=5)

        # Smart fallback option
        self.fallback_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="ใช้ Smart Fallback (สาขา/วัน/เวลาตัวแทน)", variable=self.fallback_var).pack(pady=(6,2), anchor="w")

        self.register_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="กดปุ่ม Register ด้วยตัวเอง", variable=self.register_var).pack(pady=(10, 4))

        self.confirm_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="กด Confirm Booking เอง", variable=self.confirm_var).pack(pady=4)

        # LINE
        line = ttk.Frame(main_frame)
        line.pack(pady=10)
        self.confirm_line_check_var = tk.BooleanVar()
        ttk.Checkbutton(line, text="ยืนยันการตรวจสอบ LINE (auto login)", variable=self.confirm_line_check_var).pack(side=tk.LEFT, padx=5)
        ttk.Button(line, text="ตั้งค่า LINE/Profile", command=self.on_line_settings).pack(side=tk.LEFT, padx=5)

        ctrl = ttk.Frame(main_frame)
        ctrl.pack(pady=12)
        ttk.Button(ctrl, text="เริ่มการจอง", command=self.on_start_booking).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Profile Login", command=self.on_profile_login).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="ย้อนกลับ", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

        self.on_site_selected()

    def on_browser_selected(self, _=None):
        if self.browser_var.get() == "Edge":
            self.profile_combo['values'] = edge_profiles
            self.profile_var.set(edge_profiles[0])
        else:
            self.profile_combo['values'] = profiles
            self.profile_var.set(profiles[0])

    def on_site_selected(self, _=None):
        branches = self.all_api_data.get("branchs", []) or []
        times = self.all_api_data.get("times", []) or []
        self.branch_combo['values'] = branches
        self.branch_var.set(branches[0] if branches else "")
        self.time_combo['values'] = times
        self.time_var.set(times[0] if times else "")
        self.day_combo['values'] = days
        self.day_var.set(days[0])

    def on_start_booking(self):
        # Check booking time and wait if needed
        booking_time = self._get_booking_time()
        if booking_time:
            from datetime import datetime
            import time
            current_time = datetime.now().time()
            time_diff = self._time_difference(current_time, booking_time)
            
            if time_diff > 60:  # More than 1 minute before booking
                wait_time = time_diff - 45  # Enter site 45 seconds before
                result = messagebox.askyesno(
                    "รอเวลาจอง", 
                    f"เวลาจอง: {booking_time.strftime('%H:%M')}\n"
                    f"จะเข้าไซต์อีก {wait_time:.0f} วินาที\n\n"
                    f"ต้องการรอหรือเริ่มเลย?"
                )
                if result:  # Yes = รอ
                    messagebox.showinfo("กำลังรอ", f"รอ {wait_time:.0f} วินาที ก่อนเข้าไซต์...")
                    time.sleep(wait_time)
        
        selected_browser = self.browser_var.get()
        selected_profile = self.profile_var.get()
        selected_branch = self.branch_var.get()
        selected_day = self.day_var.get()
        selected_time = self.time_var.get()
        register_by_user = self.register_var.get()
        confirm_by_user = self.confirm_var.get()

        # ขั้นสูง
        round_index = None
        timer_seconds = None
        delay_seconds = None
        try:
            v = self.round_var.get().strip()
            if v:
                round_index = max(0, int(v) - 1)
        except Exception:
            pass
        try:
            v = self.timer_var.get().strip()
            if v:
                timer_seconds = float(v)
        except Exception:
            pass
        try:
            v = self.delay_var.get().strip()
            if v:
                delay_seconds = float(v)
        except Exception:
            pass

        if not all([selected_browser, selected_profile, selected_branch, selected_day, selected_time]):
            messagebox.showwarning("คำเตือน", "กรุณาเลือกข้อมูลให้ครบถ้วน!")
            return

        confirm_line_login = bool(self.confirm_line_check_var.get())
        if confirm_line_login:
            # ตรวจว่ามี LINE และ Profile ตั้งค่าไว้
            creds = {}
            try:
                creds = load_line_credentials()
            except Exception:
                pass
            has_line = False
            if isinstance(creds, dict):
                if any(k in creds for k in ("Email","email","username","Password","password")):
                    has_line = bool((creds.get("Email") or creds.get("email") or creds.get("username")) and (creds.get("Password") or creds.get("password")))
                else:
                    has_line = any(str(v or "").strip() for v in creds.values())
            if not has_line:
                messagebox.showwarning("คำเตือน", "ยังไม่ได้ตั้งค่า LINE Email/Password ในเมนูตั้งค่า")
                return
            prof = {}
            try:
                prof = load_user_profile()
            except Exception:
                pass
            if not (isinstance(prof, dict) and any(str(v).strip() for v in prof.values())):
                messagebox.showwarning("คำเตือน", "ยังไม่ได้ตั้งค่าโปรไฟล์ผู้ใช้ในเมนูตั้งค่า")
                return

        try:
            launched_port = None
            if selected_browser == "Chrome":
                launched_port, _ = launch_chrome_with_profile(selected_profile)
            else:
                launched_port, _ = launch_edge_with_profile(selected_profile)
            if not launched_port:
                messagebox.showerror("Error", "ไม่สามารถเปิดเบราว์เซอร์ได้")
                return
        except Exception as e:
            messagebox.showerror("Error", f"เปิดเบราว์เซอร์ไม่สำเร็จ: {e}")
            return

        self.destroy()
        BookingProcessWindow(
            parent_window_class=SingleBookingWindow,
            user_info=self.user_info,
            mode="live",
            site_name="ROCKETBOOKING",
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
            auto_line_login=confirm_line_login,
            enable_fallback=bool(self.fallback_var.get())
        ).mainloop()

    def on_line_settings(self):
        try:
            SettingsDialog(self).wait_window()
        except Exception as e:
            messagebox.showerror("Error", f"เปิดหน้าตั้งค่าไม่ได้: {e}")
    
    def on_profile_login(self):
        """Launch Profile-based Login mode - เปิด Browser และ Login LINE ล่วงหน้า"""
        try:
            # Get selections
            browser_type = self.browser_var.get()
            profile_name = self.profile_var.get()
            
            # Get LINE credentials
            creds = load_line_credentials()
            if not creds:
                messagebox.showwarning("คำเตือน", "No LINE credentials found. Please configure LINE settings first.")
                return
            
            # Show LINE email selection dialog
            line_email = self._select_line_email(list(creds.keys()))
            if not line_email:
                return
            
            # Launch with log window
            self.destroy()
            ProfileLoginWindow(
                user_info=self.user_info,
                browser_type=browser_type,
                profile_name=profile_name,
                line_email=line_email
            ).mainloop()
            
        except Exception as e:
            messagebox.showerror("Error", f"Profile login failed: {e}")
    
    def _select_line_email(self, emails):
        """Dropdown dialog to select LINE email"""
        if len(emails) == 1:
            return emails[0]
        
        dialog = tk.Toplevel(self)
        dialog.title("Select LINE Email")
        dialog.geometry("350x150")
        dialog.resizable(False, False)
        
        main_frame = ttk.Frame(dialog, padding=(20, 20))
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Select LINE Email:").pack(pady=(0, 10))
        
        selected = tk.StringVar(value=emails[0])
        email_combo = ttk.Combobox(main_frame, textvariable=selected, values=emails, state="readonly", width=30)
        email_combo.pack(pady=(0, 15))
        
        result = {"email": None}
        
        def on_ok():
            result["email"] = selected.get()
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        dialog.transient(self)
        dialog.grab_set()
        dialog.wait_window()
        
        return result["email"]
    
    def _select_user_profile(self, profiles):
        """Simple dialog to select user profile"""
        if not profiles:
            return None
        if len(profiles) == 1:
            return profiles[0]
        
        dialog = tk.Toplevel(self)
        dialog.title("Select User Profile")
        dialog.geometry("300x200")
        dialog.resizable(False, False)
        
        selected = tk.StringVar(value=profiles[0])
        
        ttk.Label(dialog, text="Select User Profile:").pack(pady=10)
        
        for profile in profiles:
            ttk.Radiobutton(dialog, text=profile, variable=selected, value=profile).pack(pady=2)
        
        result = {"profile": None}
        
        def on_ok():
            result["profile"] = selected.get()
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(dialog, text="OK", command=on_ok).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(dialog, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=10, pady=10)
        
        dialog.transient(self)
        dialog.grab_set()
        dialog.wait_window()
        
        return result["profile"]
    
    def _get_booking_time(self):
        """Get today's booking time from API"""
        try:
            import requests
            from utils import BACKEND_URL
            r = requests.get(f"{BACKEND_URL}/todaybooking/open", timeout=5)
            if r.status_code == 200:
                data = r.json()
                time_str = data.get("booking_time")
                if time_str:
                    from datetime import datetime
                    return datetime.strptime(time_str, "%H:%M").time()
        except Exception:
            pass
        return None
    
    def _time_difference(self, current_time, target_time):
        """Calculate seconds difference between current and target time"""
        from datetime import datetime, timedelta
        today = datetime.now().date()
        current_dt = datetime.combine(today, current_time)
        target_dt = datetime.combine(today, target_time)
        
        # If target time is tomorrow
        if target_dt < current_dt:
            target_dt += timedelta(days=1)
        
        return (target_dt - current_dt).total_seconds()

    def on_cancel(self):
        self.destroy()
        App(self.user_info).mainloop()


# ----------------------------- Settings Dialog -----------------------------
class SettingsDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        apply_app_style(self)
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

        # Extra: bulk editor for LINE credentials
        try:
            ttk.Button(line_tab, text="แก้หลายรายการ", command=self.open_bulk_line_editor).grid(row=3, column=1, sticky="e", pady=4)
        except Exception:
            pass

        self.load_existing()

    # โฟลเดอร์เก็บไฟล์ตั้งค่า (ใช้ร่วมกับ utils)
    def _company_dir(self):
        import os
        from pathlib import Path
        appdata = os.environ.get('APPDATA')
        return Path(appdata) / "BokkChoYCompany" if appdata else Path.cwd()

    def load_existing(self):
        try:
            p = self._company_dir() / "line_data.json"
            if p.exists():
                data = json.load(open(p, 'r', encoding='utf-8'))
                if isinstance(data, dict):
                    self.line_email.set(data.get('Email') or data.get('email') or "")
                    self.line_password.set(data.get('Password') or data.get('password') or "")
                elif isinstance(data, list) and data:
                    it = data[0]
                    self.line_email.set(it.get("Email") or "")
                    self.line_password.set(it.get("Password") or "")
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
        import os
        email = (self.line_email.get() or "").strip()
        password = (self.line_password.get() or "").strip()
        if not email or not password:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Email/Password")
            return
        p = self._company_dir() / "line_data.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        # เก็บเป็น list ของ {id, Email, Password}
        old = []
        try:
            raw = json.load(open(p, 'r', encoding='utf-8')) if p.exists() else []
            if isinstance(raw, list):
                old = [x for x in raw if isinstance(x, dict)]
            elif isinstance(raw, dict):
                em = (raw.get("Email") or raw.get("email") or "").strip()
                pw = (raw.get("Password") or raw.get("password") or "").strip()
                if em:
                    old = [{"id": 1, "Email": em, "Password": pw}]
        except Exception:
            pass
        by_email = { (it.get("Email") or "").strip(): it for it in old }
        if email in by_email and (by_email[email].get("id") or 0):
            assigned = int(by_email[email]["id"])
        else:
            assigned = max([int(x.get("id") or 0) for x in old] + [0]) + 1
        by_email[email] = {"id": assigned, "Email": email, "Password": password}
        out = sorted(by_email.values(), key=lambda x: int(x.get("id") or 0))
        json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=4)
        messagebox.showinfo("สำเร็จ", "บันทึก LINE Credentials แล้ว")

    def save_profile(self):
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
        messagebox.showinfo("สำเร็จ", "บันทึกโปรไฟล์แล้ว")

    def open_bulk_line_editor(self):
        try:
            p = self._company_dir() / "line_data.json"
            def _validate_and_normalize(obj):
                if isinstance(obj, dict):
                    out = []
                    i = 1
                    for em, pw in obj.items():
                        ems = str(em).strip(); pws = str(pw).strip()
                        if not ems or not pws: continue
                        out.append({"id": i, "Email": ems, "Password": pws}); i += 1
                    return out
                if isinstance(obj, list):
                    out = []
                    i = 1
                    for it in obj:
                        if not isinstance(it, dict):
                            continue
                        em = (it.get("Email") or it.get("email") or "").strip()
                        pw = (it.get("Password") or it.get("password") or "").strip()
                        if not em or not pw:
                            continue
                        out.append({"id": i, "Email": em, "Password": pw}); i += 1
                    return out
                raise ValueError("ต้องเป็น list ของออบเจ็กต์ หรือ mapping {email: password}")
            BulkJsonEditorDialog(self, p,
                                 title="แก้หลายรายการ - LINE Credentials",
                                 note="ใส่เป็น list ของ {Email, Password} หรือ mapping {email: password}",
                                 normalizer=_validate_and_normalize).wait_window()
        except Exception:
            pass


class ProfilesManagerDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        apply_app_style(self)
        self.title("จัดการ User Profiles")
        self.geometry("520x360")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=(10,10)); frm.pack(fill=tk.BOTH, expand=True)
        self.lb = tk.Listbox(frm, height=10)
        self.lb.pack(fill=tk.BOTH, expand=True)
        bar = ttk.Frame(frm); bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="เพิ่ม", command=self.on_add).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="แก้ไข", command=self.on_edit).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="ลบ", command=self.on_delete).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="รีเฟรช", command=self.refresh).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="ปิด", command=self.destroy).pack(side=tk.RIGHT, padx=3)
        self.refresh()

    def _company_dir(self):
        import os
        from pathlib import Path
        appdata = os.environ.get('APPDATA')
        return Path(appdata) / "BokkChoYCompany" if appdata else Path.cwd()

    def _profiles_path(self):
        return self._company_dir() / "user_profiles.json"

    def _load(self):
        import json
        p = self._profiles_path()
        if not p.exists():
            return []
        try:
            data = json.load(open(p, 'r', encoding='utf-8'))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, items: list):
        import json
        p = self._profiles_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        json.dump(items, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=4)

    def refresh(self):
        # พยายามอ่านไฟล์เต็มก่อน ถ้าไม่มีแต่ combobox มีชื่อ ให้ seed ตามชื่อ
        from utils import get_user_profile_names
        self.lb.delete(0, tk.END)
        items = self._load()
        if not items:
            try:
                names = get_user_profile_names() or []
            except Exception:
                names = []
            if names:
                items = [{"Name": n} for n in names if str(n).strip()]
                if items:
                    self._save(items)
        for it in (items or []):
            nm = str(it.get('Name') or '').strip()
            if nm:
                self.lb.insert(tk.END, nm)

    def _prompt(self, init=None):
        d = tk.Toplevel(self); d.title("โปรไฟล์"); d.geometry("420x250"); d.resizable(False, False)
        frm = ttk.Frame(d, padding=(10,10)); frm.pack(fill=tk.BOTH, expand=True)
        fields = ["Name","Firstname","Lastname","Gender","ID","Phone"]
        vars = {}
        for i,k in enumerate(fields):
            ttk.Label(frm, text=k+":").grid(row=i, column=0, sticky="e", padx=5, pady=4)
            v = tk.StringVar(value=(init.get(k, "") if init else ""))
            ttk.Entry(frm, textvariable=v, width=28).grid(row=i, column=1, padx=5, pady=4)
            vars[k] = v
        bar = ttk.Frame(frm); bar.grid(row=len(fields), column=0, columnspan=2, pady=8)
        out = {"ok": False}
        def ok(): out.update(ok=True); d.destroy()
        ttk.Button(bar, text="บันทึก", command=ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="ยกเลิก", command=d.destroy).pack(side=tk.LEFT, padx=4)
        d.transient(self); d.grab_set(); d.wait_window()
        if out.get("ok"):
            return {k: v.get().strip() for k,v in vars.items()}
        return None

    def on_add(self):
        data = self._prompt()
        if not data or not data.get('Name'): return
        items = self._load()
        left = [it for it in items if str(it.get('Name') or '').strip() != data['Name']]
        left.append(data)
        self._save(left)
        self.refresh()

    def on_edit(self):
        sel = self.lb.curselection()
        if not sel: return
        name = self.lb.get(sel[0])
        items = self._load()
        cur = next((it for it in items if str(it.get('Name') or '').strip()==name), {})
        data = self._prompt(cur)
        if not data or not data.get('Name'): return
        left = [it for it in items if str(it.get('Name') or '').strip() != name]
        left.append(data)
        self._save(left)
        self.refresh()

    def on_delete(self):
        sel = self.lb.curselection()
        if not sel: return
        name = self.lb.get(sel[0])
        items = self._load()
        left = [it for it in items if str(it.get('Name') or '').strip() != name]
        self._save(left)
        self.refresh()

class LineManagerDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        apply_app_style(self)
        self.title("จัดการ LINE Credentials")
        self.geometry("520x360")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=(10,10)); frm.pack(fill=tk.BOTH, expand=True)
        self.lb = tk.Listbox(frm, height=10)
        self.lb.pack(fill=tk.BOTH, expand=True)
        bar = ttk.Frame(frm); bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="เพิ่ม", command=self.on_add).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="แก้ไข", command=self.on_edit).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="ลบ", command=self.on_delete).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="แก้หลายรายการ", command=self.open_bulk_editor).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="รีเฟรช", command=self.refresh).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="ปิด", command=self.destroy).pack(side=tk.RIGHT, padx=3)
        self.refresh()

    def _company_dir(self):
        import os
        from pathlib import Path
        appdata = os.environ.get('APPDATA')
        return Path(appdata) / "BokkChoYCompany" if appdata else Path.cwd()

    def _line_path(self):
        return self._company_dir() / "line_data.json"

    def _load_list(self):
        import json
        p = self._line_path()
        if not p.exists():
            return []
        try:
            raw = json.load(open(p, 'r', encoding='utf-8'))
        except Exception:
            return []
        out = []
        if isinstance(raw, list):
            for it in raw:
                if not isinstance(it, dict):
                    continue
                em = (it.get('Email') or it.get('email') or '').strip()
                pw = (it.get('Password') or it.get('password') or '').strip()
                if em and pw:
                    out.append({'id': int(it.get('id') or 0), 'Email': em, 'Password': pw})
        elif isinstance(raw, dict):
            i = 1
            for em, pw in raw.items():
                ems = str(em).strip(); pws = str(pw).strip()
                if ems and pws:
                    out.append({'id': i, 'Email': ems, 'Password': pws}); i += 1
        i = 1
        for it in out:
            it['id'] = i; i += 1
        return out

    def _save_list(self, items):
        import json
        p = self._line_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        out = []
        i = 1
        for it in items:
            em = (it.get('Email') or '').strip()
            pw = (it.get('Password') or '').strip()
            if em and pw:
                out.append({'id': i, 'Email': em, 'Password': pw}); i += 1
        json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    def refresh(self):
        self.lb.delete(0, tk.END)
        for it in self._load_list():
            self.lb.insert(tk.END, it.get('Email',''))

    def _prompt(self, init=None):
        d = tk.Toplevel(self); d.title("LINE"); d.geometry("400x160"); d.resizable(False, False)
        frm = ttk.Frame(d, padding=(10,10)); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Email:").grid(row=0, column=0, sticky="e", padx=5, pady=6)
        v_em = tk.StringVar(value=(init.get('Email','') if init else ''))
        ttk.Entry(frm, textvariable=v_em, width=26).grid(row=0, column=1, padx=5, pady=6)
        ttk.Label(frm, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=6)
        v_pw = tk.StringVar(value=(init.get('Password','') if init else ''))
        ttk.Entry(frm, textvariable=v_pw, width=26, show='*').grid(row=1, column=1, padx=5, pady=6)
        bar = ttk.Frame(frm); bar.grid(row=2, column=0, columnspan=2, pady=8)
        out = {"ok": False}
        def ok(): out.update(ok=True); d.destroy()
        ttk.Button(bar, text="บันทึก", command=ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="ยกเลิก", command=d.destroy).pack(side=tk.LEFT, padx=4)
        d.transient(self); d.grab_set(); d.wait_window()
        if out.get('ok'):
            return {'Email': v_em.get().strip(), 'Password': v_pw.get().strip()}
        return None

    def on_add(self):
        it = self._prompt()
        if not it or not it.get('Email') or not it.get('Password'):
            return
        lst = self._load_list()
        lst = [x for x in lst if (x.get('Email') or '').strip().lower() != it['Email'].lower()]
        lst.append(it)
        self._save_list(lst)
        self.refresh()

    def on_edit(self):
        sel = self.lb.curselection()
        if not sel: return
        email = self.lb.get(sel[0])
        lst = self._load_list()
        cur = next((x for x in lst if (x.get('Email') or '').strip().lower() == email.lower()), {})
        it = self._prompt(cur)
        if not it or not it.get('Email') or not it.get('Password'):
            return
        left = [x for x in lst if (x.get('Email') or '').strip().lower() != email.lower()]
        left.append(it)
        self._save_list(left)
        self.refresh()

    def on_delete(self):
        sel = self.lb.curselection()
        if not sel: return
        email = self.lb.get(sel[0])
        lst = self._load_list()
        left = [x for x in lst if (x.get('Email') or '').strip().lower() != email.lower()]
        self._save_list(left)
        self.refresh()

    def open_bulk_editor(self):
        p = self._line_path()
        def _normalize(obj):
            if isinstance(obj, dict):
                out = []
                i = 1
                for em, pw in obj.items():
                    ems = str(em).strip(); pws = str(pw).strip()
                    if not ems or not pws: continue
                    out.append({"id": i, "Email": ems, "Password": pws}); i += 1
                return out
            if isinstance(obj, list):
                out = []
                i = 1
                for it in obj:
                    if not isinstance(it, dict):
                        continue
                    em = (it.get('Email') or it.get('email') or '').strip()
                    pw = (it.get('Password') or it.get('password') or '').strip()
                    if not em or not pw:
                        continue
                    out.append({"id": i, "Email": em, "Password": pw}); i += 1
                return out
            raise ValueError('ต้องเป็น list ของออบเจ็กต์ หรือ mapping {email: password}')
        BulkJsonEditorDialog(self, p,
                             title="แก้หลายรายการ - LINE Credentials",
                             note="ใส่เป็น list ของ {Email, Password} หรือ mapping {email: password}",
                             normalizer=_normalize).wait_window()
        self.refresh()

class BulkJsonEditorDialog(tk.Toplevel):
    def __init__(self, master, path, title: str, note: str, normalizer):
        super().__init__(master)
        self.title(title)
        self.geometry("680x480")
        self.resizable(True, True)
        self.path = path
        self.normalizer = normalizer
        frm = ttk.Frame(self, padding=(10,10)); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text=note).pack(anchor="w", pady=(0,6))
        self.text = tk.Text(frm, wrap="word")
        self.text.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(frm); btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="บันทึก", command=self.on_save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="ยกเลิก", command=self.destroy).pack(side=tk.LEFT, padx=4)
        self._load()

    def _load(self):
        import json
        try:
            if self.path.exists():
                data = json.load(open(self.path, 'r', encoding='utf-8'))
            else:
                data = []
        except Exception:
            data = []
        try:
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            pretty = "[]"
        self.text.delete('1.0', tk.END)
        self.text.insert(tk.END, pretty)

    def on_save(self):
        import json
        raw = self.text.get('1.0', tk.END).strip()
        try:
            obj = json.loads(raw) if raw else []
        except Exception as e:
            messagebox.showerror("Error", f"JSON ไม่ถูกต้อง: {e}")
            return
        try:
            out = self.normalizer(obj)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            json.dump(out, open(self.path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"บันทึกไฟล์ไม่สำเร็จ: {e}")
            return
        messagebox.showinfo("สำเร็จ", "บันทึกข้อมูลเรียบร้อยแล้ว")
        self.destroy()

    def on_edit(self):
        sel = self.lb.curselection()
        if not sel: return
        name = self.lb.get(sel[0])
        items = self._load()
        cur = next((it for it in items if str(it.get('Name') or '').strip()==name), {})
        data = self._prompt(cur)
        if not data or not data.get('Name'): return
        left = [it for it in items if str(it.get('Name') or '').strip() != name]
        left.append(data)
        self._save(left)
        self.refresh()

    def on_delete(self):
        sel = self.lb.curselection()
        if not sel: return
        name = self.lb.get(sel[0])
        items = self._load()
        left = [it for it in items if str(it.get('Name') or '').strip() != name]
        self._save(left)
        self.refresh()


# ----------------------------- Scheduled Booking Window -----------------------------
class ScheduledBookingWindow(tk.Tk):
    def __init__(self, user_info, all_api_data):
        super().__init__()
        apply_app_style(self)
        self.user_info = user_info
        self.all_api_data = all_api_data
        self.title("จองล่วงหน้า (schedule)")
        self.geometry("1000x750")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        max_scheduled = int(self.user_info.get('สามาถตั้งจองล่วงหน้าได้กี่ site', 0))

        self.manager = ScheduledManager(all_api_data=self.all_api_data, progress_callback=self.update_status)

        self.scrollable = ScrollableFrame(self)
        self.scrollable.pack(fill="both", expand=True)
        main = self.scrollable.scrollable_frame

        tk.Label(main, text=f"ตั้งค่าการจองล่วงหน้า (สูงสุด {max_scheduled} รายการ)", font=("Arial", 16, "bold")).pack(pady=(0, 8))

        control = ttk.LabelFrame(main, text="เพิ่มการจองใหม่", padding=(10, 6))
        control.pack(fill="x", pady=8)

        self.site_var = tk.StringVar(value=LIVE_SITES[0])
        self.browser_var = tk.StringVar(value=browsers[0])
        self.profile_var = tk.StringVar(value=profiles[0])
        self.branch_var = tk.StringVar()
        self.day_var = tk.StringVar(value=days[0])
        self.time_var = tk.StringVar()
        self.line_email_var = tk.StringVar()
        self.user_profile_var = tk.StringVar()

        ttk.Label(control, text="Site:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Combobox(control, values=LIVE_SITES, textvariable=self.site_var, state="readonly").grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(control, text="Browser:").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.browser_combo = ttk.Combobox(control, values=browsers, textvariable=self.browser_var, state="readonly")
        self.browser_combo.grid(row=0, column=3, padx=4, pady=4)
        self.browser_combo.bind("<<ComboboxSelected>>", self.on_browser_selected)

        ttk.Label(control, text="Profile:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.profile_combo = ttk.Combobox(control, values=profiles[:max_scheduled], textvariable=self.profile_var, state="readonly")
        self.profile_combo.grid(row=1, column=1, padx=4, pady=4)

        ttk.Label(control, text="Branch:").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.branch_combo = ttk.Combobox(control, textvariable=self.branch_var, state="readonly")
        self.branch_combo.grid(row=1, column=3, padx=4, pady=4)

        ttk.Label(control, text="Day:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Combobox(control, values=days, textvariable=self.day_var, state="readonly").grid(row=2, column=1, padx=4, pady=4)

        ttk.Label(control, text="Time:").grid(row=2, column=2, sticky="w", padx=4, pady=4)
        self.time_combo = ttk.Combobox(control, textvariable=self.time_var, state="readonly")
        self.time_combo.grid(row=2, column=3, padx=4, pady=4)

        ttk.Label(control, text="Round (index):").grid(row=3, column=2, sticky="w")
        self.round_var = tk.StringVar()
        ttk.Entry(control, textvariable=self.round_var, width=10).grid(row=3, column=3, sticky="w", padx=4)

        ttk.Label(control, text="Timer (sec):").grid(row=3, column=0, sticky="w")
        self.timer_var = tk.StringVar()
        ttk.Entry(control, textvariable=self.timer_var, width=10).grid(row=3, column=1, sticky="w", padx=4)

        ttk.Label(control, text="Delay (sec):").grid(row=4, column=0, sticky="w")
        self.delay_var = tk.StringVar()
        ttk.Entry(control, textvariable=self.delay_var, width=10).grid(row=4, column=1, sticky="w", padx=4)

        self.manual_confirm_var = tk.BooleanVar(value=False)
        self.slow_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control, text="กด Confirm เอง", variable=self.manual_confirm_var).grid(row=4, column=2, sticky="w")
        ttk.Checkbutton(control, text="โหมดช้า", variable=self.slow_mode_var).grid(row=4, column=3, sticky="w")

        ttk.Label(control, text="LINE Email:").grid(row=5, column=2, sticky="w", padx=4, pady=4)
        self.line_email_combo = ttk.Combobox(control, textvariable=self.line_email_var, state="readonly")
        self.line_email_combo.grid(row=5, column=3, padx=60, pady=4, sticky="we")
        ttk.Button(control, text="จัดการ LINE", command=self.manage_line).grid(row=5, column=3, sticky="e", padx=4)

        ttk.Label(control, text="User Profile:").grid(row=5, column=0, sticky="w", padx=4, pady=4)
        self.user_profile_combo = ttk.Combobox(control, textvariable=self.user_profile_var, state="readonly")
        self.user_profile_combo.grid(row=5, column=1, padx=60, pady=4, sticky="we")
        ttk.Button(control, text="จัดการ Profiles", command=self.manage_profiles).grid(row=5, column=1, sticky="e", padx=4)

        ttk.Button(control, text="เพิ่ม Task", command=self.add_task).grid(row=6, column=0, columnspan=4, sticky="we", pady=6)

        # ตารางงาน
        list_frame = ttk.LabelFrame(main, text="รายการจองที่ตั้งเวลาไว้", padding=(10, 5))
        list_frame.pack(fill="both", expand=True, pady=10)
        self.task_tree = ttk.Treeview(list_frame, columns=("TaskID","Site","Branch","Day","Time","Round","Timer","Delay","Confirm","Slow","Profile","LINE","Status"), show="headings")
        for c, w in [("TaskID",70),("Site",100),("Branch",160),("Day",60),("Time",80),
                     ("Round",60),("Timer",60),("Delay",60),("Confirm",70),("Slow",60),
                     ("Profile",100),("LINE",220),("Status",110)]:
            self.task_tree.heading(c, text=c); self.task_tree.column(c, width=w, anchor="w")
        self.task_tree.pack(fill="both", expand=True)

        task_control = ttk.Frame(list_frame); task_control.pack(pady=5)
        ttk.Button(task_control, text="ลบ", command=self.remove_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(task_control, text="แก้ไข", command=self.edit_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(task_control, text="ล้างทั้งหมด", command=self.clear_all_tasks).pack(side=tk.LEFT, padx=5)

        status_frame = ttk.LabelFrame(main, text="สถานะการทำงาน", padding=(10, 5))
        status_frame.pack(fill="x", pady=10)
        self.status_text = tk.Text(status_frame, wrap="word", font=("Arial", 11), height=5)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.config(state=tk.DISABLED)

        overall = ttk.Frame(main); overall.pack(pady=10)
        self.start_btn = ttk.Button(overall, text="เริ่ม Scheduler", command=self.start_scheduler)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(overall, text="หยุด Scheduler ทั้งหมด", command=self.stop_scheduler, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(overall, text="ย้อนกลับ", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

        self.update_combobox_data()
        self.update_line_email_choices()
        self.update_user_profile_choices()
        self.refresh_task_list()
        try:
            self.on_browser_selected()
        except Exception:
            pass

    def on_browser_selected(self, _=None):
        vals = ["Default"] if self.browser_var.get() == "Edge" else profiles
        self.profile_combo['values'] = vals
        if self.profile_var.get() not in vals and vals:
            self.profile_var.set(vals[0])

    def update_combobox_data(self):
        branches = self.all_api_data.get("branchs", []) or []
        times = self.all_api_data.get("times", []) or []
        self.branch_combo['values'] = branches
        if branches: self.branch_var.set(branches[0])
        self.time_combo['values'] = times
        if times: self.time_var.set(times[0])

    def start_trial_booking(self):
        selected_site = self.site_var.get()
        selected_browser = self.browser_var.get()
        selected_branch = self.branch_var.get()
        selected_day = self.day_var.get()
        selected_time = self.time_var.get()
        if not all([selected_site, selected_browser, selected_branch, selected_day, selected_time]):
            messagebox.showwarning("คำเตือน", "กรุณากรอก Site/Browser/Branch/Day/Time ให้ครบ")
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
            messagebox.showerror("Error", f"เริ่มโหมดทดลองไม่สำเร็จ: {e}")
            App(self.user_info).mainloop()

    def update_line_email_choices(self):
        try:
            line_data = self.manager.load_line_credentials()
            emails = list(line_data.keys())
            self.line_email_combo['values'] = emails
            if emails: self.line_email_var.set(emails[0])
        except Exception:
            pass

    def update_user_profile_choices(self):
        try:
            names = get_user_profile_names()
            self.user_profile_combo['values'] = names
            if names and self.user_profile_var.get() not in names:
                self.user_profile_var.set(names[0])
        except Exception:
            pass

    def manage_line(self):
        try:
            LineManagerDialog(self).wait_window()
        except Exception:
            pass
        self.update_line_email_choices()

    def manage_profiles(self):
        try:
            ProfilesManagerDialog(self).wait_window()
        except Exception:
            pass
        self.update_user_profile_choices()

    def update_status(self, message):
        def inner():
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)
            self.refresh_task_list()
        self.after(0, inner)

    def refresh_task_list(self):
        self.task_tree.delete(*self.task_tree.get_children())
        for task in self.manager.tasks:
            d = task.task_data
            self.task_tree.insert("", "end", iid=task.id, values=(
                task.id[:4], d.get('site_name','-'), d.get('selected_branch','-'),
                d.get('selected_day','-'), d.get('selected_time','-'),
                ((d.get('round_index')+1) if isinstance(d.get('round_index'), int) else (d.get('round_index') or '-')),
                d.get('timer_seconds','-'), d.get('delay_seconds','-'),
                ('Y' if d.get('confirm_by_user') else 'N'),
                ('Y' if d.get('slow_mode') else 'N'),
                d.get('profile','-'), d.get('line_email','-'), task.status
            ))

    def add_task(self):
        # ตรวจข้อมูลจำเป็น
        if not all([self.site_var.get(), self.browser_var.get(), self.profile_var.get(),
                    self.branch_var.get(), self.day_var.get(), self.time_var.get()]):
            messagebox.showwarning("คำเตือน", "กรอกข้อมูลให้ครบก่อนเพิ่ม Task")
            return
        # แปลงตัวเลือกขั้นสูง
        def _float_or_none(s): 
            s = (s or "").strip()
            try: return float(s) if s else None
            except: return None
        def _round_index(s):
            s = (s or "").strip()
            try:
                v = int(s); return max(0, v-1)
            except: return None

        line_map = self.manager.load_line_credentials()
        selected_email = self.line_email_var.get()
        if selected_email and not line_map.get(selected_email):
            messagebox.showwarning("คำเตือน", "LINE Email ไม่มีในรายการ credentials")
            return

        d = {
            "site_name": self.site_var.get(),
            "browser_type": self.browser_var.get(),
            "profile": self.profile_var.get(),
            "selected_branch": self.branch_var.get(),
            "selected_day": self.day_var.get(),
            "selected_time": self.time_var.get(),
            "round_index": _round_index(self.round_var.get()),
            "timer_seconds": _float_or_none(self.timer_var.get()),
            "delay_seconds": _float_or_none(self.delay_var.get()),
            "confirm_by_user": bool(self.manual_confirm_var.get()),
            "slow_mode": bool(self.slow_mode_var.get()),
            "line_email": selected_email,
            "line_password": line_map.get(selected_email),
            "user_profile_name": self.user_profile_var.get(),
        }
        self.manager.add_booking(d)
        self.refresh_task_list()

    def remove_task(self):
        sel = self.task_tree.focus()
        if not sel:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Task")
            return
        self.manager.remove_booking(sel)
        self.refresh_task_list()

    def edit_task(self):
        sel = self.task_tree.focus()
        if not sel:
            messagebox.showwarning("คำเตือน", "กรุณาเลือก Task")
            return
        task = next((t for t in self.manager.tasks if t.id == sel), None)
        if not task:
            return
        d = task.task_data
        self.site_var.set(d.get('site_name','')); self.browser_var.set(d.get('browser_type',''))
        self.profile_var.set(d.get('profile','')); self.branch_var.set(d.get('selected_branch',''))
        self.day_var.set(d.get('selected_day','')); self.time_var.set(d.get('selected_time',''))
        ri = d.get('round_index'); self.round_var.set(str(ri+1) if isinstance(ri,int) else '')
        self.timer_var.set(str(d.get('timer_seconds') or '')); self.delay_var.set(str(d.get('delay_seconds') or ''))
        self.manual_confirm_var.set(bool(d.get('confirm_by_user', False))); self.slow_mode_var.set(bool(d.get('slow_mode', False)))
        self.line_email_var.set(d.get('line_email','')); self.user_profile_var.set(d.get('user_profile_name',''))
        self.manager.remove_booking(sel)
        self.refresh_task_list()
        messagebox.showinfo("สถานะ", "ย้ายข้อมูลขึ้นฟอร์มด้านบนแล้ว กด 'เพิ่ม Task' เพื่อบันทึกใหม่")

    def clear_all_tasks(self):
        if messagebox.askyesno("ยืนยัน", "ล้าง Task ทั้งหมดใช่ไหม?"):
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
        App(self.user_info).mainloop()


# ----------------------------- Trial Mode Window -----------------------------
class TrialModeWindow(tk.Tk):
    def __init__(self, all_api_data, user_info):
        super().__init__()
        apply_app_style(self)
        self.user_info = user_info
        self.all_api_data = all_api_data
        self.title("โหมดทดลอง")
        self.geometry("400x600")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        main = ttk.Frame(self, padding=(10, 10)); main.pack(fill=tk.BOTH, expand=True)
        tk.Label(main, text="เลือก Site:", font=("Arial", 12)).pack(pady=(10, 3))
        self.site_var = tk.StringVar(value=TRIAL_SITES[0])
        ttk.Combobox(main, values=TRIAL_SITES, textvariable=self.site_var, state="readonly", font=("Arial", 11)).pack(pady=5)

        tk.Label(main, text="เลือก Browser:", font=("Arial", 12)).pack(pady=(10, 3))
        self.browser_var = tk.StringVar(value=browsers[0])
        ttk.Combobox(main, values=browsers, textvariable=self.browser_var, state="readonly", font=("Arial", 11)).pack(pady=5)

        tk.Label(main, text="เลือก Branch:", font=("Arial", 12)).pack(pady=(10, 3))
        self.branch_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(main, textvariable=self.branch_var, state="readonly", font=("Arial", 11))
        self.branch_combo.pack(pady=5)

        tk.Label(main, text="เลือกวัน:", font=("Arial", 12)).pack(pady=(10, 3))
        self.day_var = tk.StringVar(value=days[0])
        ttk.Combobox(main, values=days, textvariable=self.day_var, state="readonly", font=("Arial", 11)).pack(pady=5)

        tk.Label(main, text="เลือก Time:", font=("Arial", 12)).pack(pady=(10, 3))
        self.time_var = tk.StringVar()
        self.time_combo = ttk.Combobox(main, textvariable=self.time_var, state="readonly", font=("Arial", 11))
        self.time_combo.pack(pady=5)

        status_frame = ttk.LabelFrame(main, text="สถานะ", padding=(10, 5))
        status_frame.pack(pady=10, padx=10, fill="x", expand=True)
        self.status_text = tk.Text(status_frame, wrap="word", font=("Arial", 10), height=5)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.insert(tk.END, "พร้อมเริ่มโหมดทดลอง...\n")
        self.status_text.config(state=tk.DISABLED)

        ctrl = ttk.Frame(main); ctrl.pack(pady=20)
        ttk.Button(ctrl, text="เริ่มโหมดทดลอง", command=self.start_trial_booking).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="ย้อนกลับ", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

        # init combos
        branches = self.all_api_data.get("branchs", []) or []
        times = self.all_api_data.get("times", []) or []
        self.branch_combo['values'] = branches
        if branches: self.branch_var.set(branches[0])
        self.time_combo['values'] = times
        if times: self.time_var.set(times[0])

    def start_trial_booking(self):
        selected_site = self.site_var.get()
        selected_browser = self.browser_var.get()
        selected_branch = self.branch_var.get()
        selected_day = self.day_var.get()
        selected_time = self.time_var.get()
        if not all([selected_site, selected_browser, selected_branch, selected_day, selected_time]):
            messagebox.showwarning("คำเตือน", "กรุณากรอก Site/Browser/Branch/Day/Time ให้ครบ")
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
            messagebox.showerror("Error", f"เริ่มโหมดทดลองไม่สำเร็จ: {e}")
            App(self.user_info).mainloop()

    def on_cancel(self):
        self.destroy()
        App(self.user_info).mainloop()


# ----------------------------- Live Mode Window -----------------------------
class LiveModeWindow(tk.Tk):
    def __init__(self, user_info, api_data):
        super().__init__()
        apply_app_style(self)
        self.user_info = user_info
        self.api_data = api_data or {}
        self.title("Live Mode")
        self.geometry("360x260")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_back)

        frm = ttk.Frame(self, padding=(12, 12))
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="โหมดการใช้งานจริง", font=("Arial", 13, "bold")).pack(pady=(6, 10))

        ttk.Button(frm, text="Single Booking", width=28, command=self.open_single).pack(pady=6)
        self.sch_btn = ttk.Button(frm, text="Scheduler", width=28, command=self.open_scheduler)
        self.sch_btn.pack(pady=6)
        ttk.Button(frm, text="Help (Timer/Delay/Round)", width=28, command=self.open_help).pack(pady=6)
        ttk.Button(frm, text="Back", width=28, command=self.on_back).pack(pady=(16,6))

        # enable/disable scheduler by role or flag
        role = str(self.user_info.get('Role', '')).strip().lower()
        can_pre = bool(self.user_info.get('can_prebook') or self.user_info.get('ตั้งจองล่วงหน้าได้ไหม') in ['ใช่', True, 'true'])
        if role in {"admin", "vipi", "vipii", "vipiii"} or can_pre:
            self.sch_btn.config(state=tk.NORMAL)
        else:
            self.sch_btn.config(state=tk.DISABLED)

    def open_single(self):
        try:
            self.destroy()
            SingleBookingWindow(user_info=self.user_info, all_api_data=self.api_data).mainloop()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            App(self.user_info).mainloop()

    def open_scheduler(self):
        try:
            self.destroy()
            ScheduledBookingWindow(user_info=self.user_info, all_api_data=self.api_data).mainloop()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            App(self.user_info).mainloop()

    def on_back(self):
        self.destroy()
        App(self.user_info).mainloop()

    def open_help(self):
        txt = (
            "คำอธิบายแบบย่อ:\n\n"
            "- Round(Index): ลำดับปุ่มเวลา ‘ที่กดได้’ ในหน้าจอ (1 = รายการแรก).\n"
            "  ใช้เมื่อต้องการกดตามลำดับ ไม่ยึดติดกับข้อความเวลา.\n\n"
            "- Timer(sec): เวลาสูงสุดที่รอให้ปุ่ม Register เปลี่ยนเป็น Active.\n"
            "  ครบเวลาแล้วยังไม่ Active จะหยุดรอและเดินหน้าต่อ.\n\n"
            "- Delay(sec): เวลาหน่วงก่อนคลิกองค์ประกอบสำคัญ (Branch/Date/Time)\n"
            "  เพื่อให้เพจโหลดเสถียรก่อนคลิก.\n\n"
            "- ข้อแนะนำ: หากเวลาที่ต้องการ ‘เต็ม/ไม่ขึ้น’ ให้ใช้ Round(Index)\n"
            "  เพื่อเลือกเวลาลำดับที่ต้องการแทนการจับข้อความเวลา."
        )
        top = tk.Toplevel(self)
        top.title("Help")
        top.geometry("520x360")
        top.resizable(False, False)
        frame = ttk.Frame(top, padding=(12, 12))
        frame.pack(fill=tk.BOTH, expand=True)
        t = tk.Text(frame, wrap="word", height=16)
        t.pack(fill=tk.BOTH, expand=True)
        t.insert(tk.END, txt)
        t.config(state=tk.DISABLED)
        ttk.Button(frame, text="ปิด", command=top.destroy).pack(pady=6)

    def start_trial_booking(self):
        selected_site = self.site_var.get()
        selected_browser = self.browser_var.get()
        selected_branch = self.branch_var.get()
        selected_day = self.day_var.get()
        selected_time = self.time_var.get()
        if not all([selected_site, selected_browser, selected_branch, selected_day, selected_time]):
            messagebox.showwarning("คำเตือน", "กรุณาเลือกข้อมูลให้ครบถ้วน!")
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
            messagebox.showerror("Error", f"เปิดหน้าต่างจองไม่สำเร็จ: {e}")
            App(self.user_info).mainloop()


# ----------------------------- Admin Config Window -----------------------------
class AdminConfigWindow(tk.Tk):
    def __init__(self, user_info):
        super().__init__()
        apply_app_style(self)
        self.user_info = user_info
        self.title("Admin Config Inspector")
        self.geometry("1200x800")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_back)
        
        # Admin check
        role = (user_info.get("Role") or "").lower()
        if role != "admin":
            ttk.Label(self, text="Admin access required", foreground="red").pack(pady=20)
            ttk.Button(self, text="Back", command=self.on_back).pack()
            return
        
        self.schema_cache = None
        self.loading = False
        
        # Main layout
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top controls
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(top_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 5))
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(top_frame, textvariable=self.category_var, state="readonly", width=20)
        self.category_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.category_combo.bind("<<ComboboxSelected>>", self.on_category_selected)
        
        ttk.Button(top_frame, text="Refresh", command=self.refresh_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Save", command=self.save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Reset to Base", command=self.reset_to_base).pack(side=tk.LEFT, padx=5)
        
        # Config panels
        panels_frame = ttk.Frame(main_frame)
        panels_frame.pack(fill=tk.BOTH, expand=True)
        
        # Base KV panel
        base_frame = ttk.LabelFrame(panels_frame, text="Base KV (Read-only)")
        base_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.base_text = tk.Text(base_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED)
        self.base_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Override panel
        override_frame = ttk.LabelFrame(panels_frame, text="Override (Editable)")
        override_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.override_text = tk.Text(override_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.override_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Effective panel
        effective_frame = ttk.LabelFrame(panels_frame, text="Effective Config (Merged)")
        effective_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        self.effective_text = tk.Text(effective_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED)
        self.effective_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, pady=(10, 0))
        
        # Load initial data
        self.load_categories()
    
    def load_categories(self):
        """Load available categories"""
        def _load():
            try:
                from admin_config_inspector import admin_get_config_categories
                categories = admin_get_config_categories(self.user_info)
                self.after(0, lambda: self._on_categories_loaded(categories))
            except Exception as e:
                self.after(0, lambda: self._on_error(f"Failed to load categories: {e}"))
        
        self.status_var.set("Loading categories...")
        threading.Thread(target=_load, daemon=True).start()
    
    def _on_categories_loaded(self, categories):
        self.category_combo['values'] = categories
        if categories:
            self.category_var.set(categories[0])
            self.on_category_selected()
        self.status_var.set("Categories loaded")
    
    def _on_error(self, message):
        self.status_var.set(f"Error: {message}")
        messagebox.showerror("Error", message)
    
    def on_category_selected(self, event=None):
        """Handle category selection"""
        category = self.category_var.get()
        if not category or self.loading:
            return
        
        def _load():
            try:
                from admin_config_inspector import admin_get_category_config
                config_data = admin_get_category_config(self.user_info, category)
                self.after(0, lambda: self._on_config_loaded(config_data))
            except Exception as e:
                self.after(0, lambda: self._on_error(f"Failed to load config: {e}"))
        
        self.loading = True
        self.status_var.set(f"Loading {category}...")
        threading.Thread(target=_load, daemon=True).start()
    
    def _on_config_loaded(self, config_data):
        """Update UI with loaded config data"""
        try:
            # Update base panel
            self.base_text.config(state=tk.NORMAL)
            self.base_text.delete(1.0, tk.END)
            self.base_text.insert(tk.END, json.dumps(config_data.get("base", {}), indent=2, ensure_ascii=False))
            self.base_text.config(state=tk.DISABLED)
            
            # Update override panel
            self.override_text.delete(1.0, tk.END)
            self.override_text.insert(tk.END, json.dumps(config_data.get("override", {}), indent=2, ensure_ascii=False))
            
            # Update effective panel
            self.effective_text.config(state=tk.NORMAL)
            self.effective_text.delete(1.0, tk.END)
            self.effective_text.insert(tk.END, json.dumps(config_data.get("effective", {}), indent=2, ensure_ascii=False))
            self.effective_text.config(state=tk.DISABLED)
            
            self.status_var.set(f"Loaded {config_data.get('category', 'config')}")
        except Exception as e:
            self._on_error(f"Failed to display config: {e}")
        finally:
            self.loading = False
    
    def refresh_data(self):
        """Refresh current category data"""
        self.on_category_selected()
    
    def save_changes(self):
        """Save override changes"""
        category = self.category_var.get()
        if not category:
            messagebox.showwarning("Warning", "No category selected")
            return
        
        try:
            # Parse override text
            override_text = self.override_text.get(1.0, tk.END).strip()
            if not override_text:
                updates = {}
            else:
                updates = json.loads(override_text)
            
            def _save():
                try:
                    from admin_config_inspector import admin_update_category_config
                    success, errors = admin_update_category_config(self.user_info, category, updates)
                    if success:
                        self.after(0, lambda: self._on_save_success())
                    else:
                        self.after(0, lambda: self._on_save_error(errors))
                except Exception as e:
                    self.after(0, lambda: self._on_error(f"Save failed: {e}"))
            
            self.status_var.set("Saving...")
            threading.Thread(target=_save, daemon=True).start()
            
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON in override panel: {e}")
        except Exception as e:
            self._on_error(f"Save preparation failed: {e}")
    
    def _on_save_success(self):
        self.status_var.set("Saved successfully")
        messagebox.showinfo("Success", "Config saved successfully")
        self.refresh_data()  # Refresh to show updated effective config
    
    def _on_save_error(self, errors):
        error_msg = "\n".join(errors)
        self.status_var.set("Save failed")
        messagebox.showerror("Validation Error", f"Save failed:\n{error_msg}")
    
    def reset_to_base(self):
        """Reset category to base (clear override)"""
        category = self.category_var.get()
        if not category:
            messagebox.showwarning("Warning", "No category selected")
            return
        
        if not messagebox.askyesno("Confirm Reset", f"Reset {category} to base config?\nThis will clear all overrides."):
            return
        
        def _reset():
            try:
                from admin_config_inspector import admin_reset_category_config
                success = admin_reset_category_config(self.user_info, category)
                if success:
                    self.after(0, lambda: self._on_reset_success())
                else:
                    self.after(0, lambda: self._on_error("Reset failed"))
            except Exception as e:
                self.after(0, lambda: self._on_error(f"Reset failed: {e}"))
        
        self.status_var.set("Resetting...")
        threading.Thread(target=_reset, daemon=True).start()
    
    def _on_reset_success(self):
        self.status_var.set("Reset successful")
        messagebox.showinfo("Success", "Config reset to base successfully")
        self.refresh_data()
    
    def on_back(self):
        self.destroy()
        AdminConsoleWindow(self.user_info).mainloop()


# ----------------------------- Admin Console -----------------------------
class AdminConsoleWindow(tk.Tk):
    def __init__(self, user_info):
        super().__init__()
        apply_app_style(self)
        self.user_info = user_info
        self.token = (user_info or {}).get("token")
        self.api = AdminApi(self.token) if self.token else None

        self.title("Admin Console")
        self.geometry("980x680")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_back)

        if not self.token or not self.api:
            ttk.Label(self, text="ไม่พบ token สำหรับ Admin API", foreground="red").pack(pady=12)
            ttk.Button(self, text="ย้อนกลับ", command=self.on_back).pack()
            return

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=10)
        self._users_tab = ttk.Frame(nb); nb.add(self._users_tab, text="Users")
        self._today_tab = ttk.Frame(nb); nb.add(self._today_tab, text="TodayBooking")
        self._config_tab = ttk.Frame(nb); nb.add(self._config_tab, text="Config")

        # --- Users tab ---
        top = ttk.Frame(self._users_tab); top.pack(fill="x", pady=6)
        ttk.Button(top, text="รีเฟรช", command=self.load_users).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="บันทึกการแก้ไข", command=self.save_selected_user).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="ลบ", command=self.delete_selected_user).pack(side=tk.LEFT, padx=4)

        self.tree = ttk.Treeview(self._users_tab,
                                 columns=("username","role","sites_limit","can_prebook","expires_at","email"),
                                 show="headings", selectmode="browse")
        for c,w in [("username",200), ("role",120), ("sites_limit",110), ("can_prebook",120), ("expires_at",160), ("email",200)]:
            self.tree.heading(c, text=c); self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        editor = ttk.LabelFrame(self._users_tab, text="แก้ไขผู้ใช้", padding=(10,8))
        editor.pack(fill="x", padx=8, pady=6)
        ttk.Label(editor, text="Username:").grid(row=0, column=0, sticky="e"); self.e_user = ttk.Entry(editor, width=26); self.e_user.grid(row=0, column=1, padx=6, pady=4, sticky="w")
        ttk.Label(editor, text="Role:").grid(row=0, column=2, sticky="e"); self.role_var = tk.StringVar(); self.e_role = ttk.Combobox(editor, textvariable=self.role_var, values=["normal","vipi","vipii","vipiii","admin"], state="readonly", width=16); self.e_role.grid(row=0, column=3, padx=6, pady=4, sticky="w")
        ttk.Label(editor, text="Expires at (YYYY-MM-DD):").grid(row=1, column=0, sticky="e"); self.exp_var = tk.StringVar(); self.e_exp = ttk.Entry(editor, textvariable=self.exp_var, width=26); self.e_exp.grid(row=1, column=1, padx=6, pady=4, sticky="w")
        ttk.Label(editor, text="Status:").grid(row=1, column=2, sticky="e"); self.status_var = tk.StringVar(); self.e_status = ttk.Entry(editor, textvariable=self.status_var, width=16); self.e_status.grid(row=1, column=3, padx=6, pady=4, sticky="w")

        # --- Today tab ---
        ttop = ttk.Frame(self._today_tab); ttop.pack(fill="x", pady=12)
        ttk.Label(ttop, text="สถานะวันนี้: ").pack(side=tk.LEFT, padx=6)
        self.today_status_lbl = ttk.Label(ttop, text="กำลังโหลด...", width=50)
        self.today_status_lbl.pack(side=tk.LEFT)
        ttk.Button(ttop, text="รีเฟรช", command=self.refresh_today).pack(side=tk.LEFT, padx=6)
        ttk.Button(ttop, text="เปิดวันนี้", command=lambda: self.set_today(True)).pack(side=tk.LEFT, padx=3)
        ttk.Button(ttop, text="ปิดวันนี้", command=lambda: self.set_today(False)).pack(side=tk.LEFT, padx=3)
        ttk.Button(ttop, text="ตั้งเวลาจอง", command=self.set_booking_time).pack(side=tk.LEFT, padx=3)
        
        # --- Config tab ---
        config_frame = ttk.Frame(self._config_tab)
        config_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Config Inspector section
        inspector_frame = ttk.LabelFrame(config_frame, text="Config Inspector", padding=(10, 10))
        inspector_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(inspector_frame, text="Manage application configuration with KV override support").pack()
        ttk.Button(inspector_frame, text="Open Config Inspector", command=self.open_config_inspector).pack(pady=5)
        
        # API Status section
        status_frame = ttk.LabelFrame(config_frame, text="API Status Checker", padding=(10, 10))
        status_frame.pack(fill=tk.BOTH, expand=True)
        
        # Dropdown for API selection
        api_select_frame = ttk.Frame(status_frame)
        api_select_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(api_select_frame, text="Select API:").pack(side=tk.LEFT, padx=(0, 5))
        self.api_var = tk.StringVar()
        self.api_combo = ttk.Combobox(api_select_frame, textvariable=self.api_var, state="readonly", width=20)
        self.api_combo.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(api_select_frame, text="Check Status", command=self.check_api_status).pack(side=tk.LEFT)
        
        # Status display
        self.api_status_text = tk.Text(status_frame, wrap=tk.WORD, font=("Arial", 10), height=8)
        self.api_status_text.pack(fill=tk.BOTH, expand=True)
        
        # Load API list
        self.load_api_list()

        self.load_users()
        self.refresh_today()
    
    def open_config_inspector(self):
        """Open dedicated config inspector window"""
        self.destroy()
        AdminConfigWindow(self.user_info).mainloop()
    
    def load_api_list(self):
        """Load available APIs for status checking"""
        apis = ["All APIs", "branchs", "times", "urls", "sites"]
        self.api_combo['values'] = apis
        self.api_var.set("All APIs")
    
    def check_api_status(self):
        """Check status of selected API"""
        selected = self.api_var.get()
        if not selected:
            return
        
        def _check():
            try:
                from utils import get_all_api_data
                self.api_status_text.delete(1.0, tk.END)
                self.api_status_text.insert(tk.END, f"Checking {selected}...\n")
                
                results = get_all_api_data()
                
                if selected == "All APIs":
                    for name, data in results.items():
                        ok = not (isinstance(data, str) and data.startswith("Error"))
                        self.api_status_text.insert(tk.END, f"{name}: {'✅' if ok else '❌'}\n")
                else:
                    data = results.get(selected, "Not found")
                    ok = not (isinstance(data, str) and data.startswith("Error"))
                    self.api_status_text.insert(tk.END, f"{selected}: {'✅' if ok else '❌'}\n")
                    if not ok:
                        self.api_status_text.insert(tk.END, f"Error: {data}\n")
                    else:
                        self.api_status_text.insert(tk.END, f"Data: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...\n")
            except Exception as e:
                self.api_status_text.delete(1.0, tk.END)
                self.api_status_text.insert(tk.END, f"Failed to check API status: {e}\n")
        
        threading.Thread(target=_check, daemon=True).start()

    def on_back(self):
        self.destroy()
        App(self.user_info).mainloop()

    # ---- users tab helpers ----
    def load_users(self):
        if not self.api:
            return
        self.tree.delete(*self.tree.get_children())
        try:
            users = self.api.list_users() or []
        except Exception as e:
            messagebox.showerror("Error", f"โหลดรายชื่อผู้ใช้ล้มเหลว: {e}")
            return
        for u in users:
            uname = u.get("username") or u.get("user") or ""
            role = u.get("role") or "normal"
            sites = u.get("sites_limit")
            pre = u.get("can_prebook")
            exp = u.get("expires_at") or u.get("expire_at") or u.get("exp_date") or ""
            email = u.get("email") or ""
            self.tree.insert("", "end", iid=uname, values=(uname, role, sites, bool(pre), exp, email))

    def on_tree_select(self, _=None):
        sel = self.tree.focus()
        if not sel: return
        vals = self.tree.item(sel, "values")
        self.e_user.delete(0, tk.END); self.e_user.insert(0, vals[0])
        self.role_var.set(vals[1]);
        # vals: username, role, sites_limit, can_prebook, expires_at, email
        try:
            self.exp_var.set(vals[4])
        except Exception:
            pass

    def save_selected_user(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกรายการ")
            return
        username = self.e_user.get().strip()
        role = self.role_var.get().strip().lower() or "normal"
        exp = self.exp_var.get().strip()
        payload = {"role": role}
        if exp:
            payload["expires_at"] = exp
        # ขอข้อมูลเพิ่มเติมผ่าน dialog เพื่อแก้ไขโควต้า/อีเมล
        try:
            from tkinter import simpledialog
            sites = simpledialog.askinteger("Sites limit", "จำนวน site ที่จองล่วงหน้าได้:", minvalue=0, maxvalue=999)
            if sites is not None:
                payload["sites_limit"] = int(sites)
            yn = messagebox.askyesno("ตั้งค่า Prebook", "อนุญาตให้ตั้งจองล่วงหน้าได้ไหม? (Yes/No)")
            payload["can_prebook"] = bool(yn)
            email = simpledialog.askstring("Email", "อีเมล (เว้นว่างได้):")
            if email is not None:
                payload["email"] = email.strip()
        except Exception:
            pass
        try:
            ok = self.api.update_user(username, payload)
            if ok:
                messagebox.showinfo("สำเร็จ", "อัปเดตผู้ใช้เรียบร้อย")
                self.load_users()
            else:
                messagebox.showerror("ล้มเหลว", "อัปเดตไม่สำเร็จ")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_selected_user(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showwarning("คำเตือน", "กรุณาเลือกรายการ")
            return
        if not messagebox.askyesno("ยืนยัน", f"ลบผู้ใช้ '{sel}' ใช่ไหม?"):
            return
        try:
            ok = self.api.delete_user(sel)
            if ok:
                self.tree.delete(sel)
                messagebox.showinfo("สำเร็จ", "ลบแล้ว")
            else:
                messagebox.showerror("ล้มเหลว", "ลบไม่สำเร็จ")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- todaybooking tab helpers ----
    def refresh_today(self):
        if not self.api:
            return
        try:
            result = self.api.get_todaybooking_open()
            if result is None:
                self.today_status_lbl.config(text="(ไม่มี endpoint) — ถือว่า 'ปิด'")
            else:
                is_open = result.get("open", False) if isinstance(result, dict) else bool(result)
                booking_time = result.get("booking_time", "") if isinstance(result, dict) else ""
                
                status_text = "เปิด (มี booking)" if is_open else "ปิด (ไม่มี booking)"
                if booking_time:
                    status_text += f" | เวลาจอง: {booking_time}"
                
                self.today_status_lbl.config(text=status_text)
        except Exception as e:
            self.today_status_lbl.config(text=f"โหลดไม่ได้: {e}")

    def set_today(self, open_flag: bool):
        if not self.api:
            return
        try:
            ok = self.api.set_todaybooking_open(open_flag)
            if ok:
                messagebox.showinfo("สำเร็จ", "อัปเดตสถานะแล้ว")
                self.refresh_today()
            else:
                messagebox.showerror("ล้มเหลว", "อัปเดตไม่สำเร็จ")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def set_booking_time(self):
        from tkinter import simpledialog
        time_str = simpledialog.askstring(
            "ตั้งเวลาจอง", 
            "ใส่เวลาจอง (HH:MM เช่น 10:00):"
        )
        if time_str:
            try:
                from datetime import datetime
                datetime.strptime(time_str, "%H:%M")
                
                payload = {"booking_time": time_str}
                r = requests.post(
                    f"{BACKEND_URL}/todaybooking/time",
                    headers=self.api._headers, json=payload, timeout=10
                )
                if r.status_code in (200, 204):
                    messagebox.showinfo("สำเร็จ", f"ตั้งเวลาจอง {time_str} แล้ว")
                    self.refresh_today()
                else:
                    messagebox.showerror("ล้มเหลว", "ตั้งเวลาไม่สำเร็จ")
            except ValueError:
                messagebox.showerror("ผิดพลาด", "รูปแบบเวลาไม่ถูกต้อง (ใช้ HH:MM)")
            except Exception as e:
                messagebox.showerror("Error", str(e))


# ----------------------------- App (Main) -----------------------------
class App(tk.Tk):
    def __init__(self, user_info):
        super().__init__()
        apply_app_style(self)
        self.user_info = user_info
        self.title("Browser Profile Launcher & API Loader")
        self.geometry("540x620")
        self.resizable(False, False)

        self.api_data = {}
        threading.Thread(target=self._load_api_data_in_background, daemon=True).start()

        user_frame = ttk.LabelFrame(self, text="สถานะผู้ใช้งาน", padding=(10, 5))
        user_frame.pack(pady=10, padx=10, fill="x")
        txt = (
            f"User: {self.user_info['Username']}\n"
            f"Role: {self.user_info.get('Role', '-')}\n"
            f"Max Profiles: {self.user_info.get('สามาถตั้งจองล่วงหน้าได้กี่ site', '-')}\n"
            f"Can Use Scheduler: {self.user_info.get('ตั้งจองล่วงหน้าได้ไหม', '-')}\n"
            f"Expiration date: {self.user_info.get('Expiration date', '-')}"
        )
        tk.Label(user_frame, text=txt, font=("Arial", 11), justify=tk.LEFT).pack(pady=5, padx=5)

        # TodayBooking status
        today_frame = ttk.LabelFrame(self, text="สถานะการ Booking วันนี้", padding=(10, 5))
        today_frame.pack(pady=5, padx=10, fill="x")
        inner = ttk.Frame(today_frame); inner.pack(fill="x")
        self.today_canvas = tk.Canvas(inner, width=18, height=18, highlightthickness=0)
        self.today_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.today_status_var = tk.StringVar(value="กำลังตรวจสอบ...")
        ttk.Label(inner, textvariable=self.today_status_var, font=("Arial", 11), width=60).pack(side=tk.LEFT)
        ttk.Button(inner, text="รีเฟรช", command=self.refresh_todaybooking_status).pack(side=tk.RIGHT)
        self.after(100, self.refresh_todaybooking_status)

        menu = ttk.Frame(self); menu.pack(pady=10)
        ttk.Button(menu, text="เติมเงิน", width=25, command=self.on_top_up).pack(pady=5)
        
        # Simple Mode button (prominent)
        self.simple_mode_btn = ttk.Button(menu, text="🎯 โหมดง่าย (แนะนำ)", width=25, command=self.open_simple_mode, state='disabled')
        self.simple_mode_btn.pack(pady=5)
        
        self.trial_mode_btn = ttk.Button(menu, text="โหมดทดลอง", width=25, command=self.open_trial_mode_window, state='disabled')
        self.trial_mode_btn.pack(pady=5)
        self.live_mode_btn = ttk.Button(menu, text="โหมดขั้นสูง", width=25, command=self.open_live_mode_window, state='disabled')
        self.live_mode_btn.pack(pady=5)

        # ปุ่ม Admin Console เฉพาะ admin
        role = str(self.user_info.get('Role','')).lower().strip()
        if role == "admin":
            ttk.Button(menu, text="Admin Console", width=25, command=self.open_admin_console).pack(pady=5)

        ttk.Button(menu, text="ตรวจสอบอัปเดต", width=25, command=self.check_updates).pack(pady=5)
        ttk.Button(menu, text="Logout", width=25, command=self.logout).pack(pady=5)

    def _load_api_data_in_background(self):
        try:
            self.api_data = get_all_api_data()
            self.after(0, self._on_api_data_loaded_successfully)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"โหลด API ไม่ได้:\n{e}"))

    def _on_api_data_loaded_successfully(self):
        self.simple_mode_btn.config(state='normal')
        self.trial_mode_btn.config(state='normal')
        self.live_mode_btn.config(state='normal')

    def refresh_todaybooking_status(self):
        try:
            # Get booking status and time
            import requests
            from utils import BACKEND_URL
            try:
                r = requests.get(f"{BACKEND_URL}/todaybooking/open", timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    ok = data.get("open", False)
                    booking_time = data.get("booking_time", "")
                else:
                    ok = is_today_booking_open(True)
                    booking_time = ""
            except Exception:
                ok = is_today_booking_open(True)
                booking_time = ""
            
            today_str = datetime.now().strftime("%Y-%m-%d")
            self.today_canvas.delete("all")
            color = "#2ecc71" if ok else "#e74c3c"
            self.today_canvas.create_oval(2, 2, 16, 16, fill=color, outline=color)
            
            status_text = f"วันนี้ {today_str}: " + ("มีการ Booking" if ok else "ไม่มีการ Booking")
            if booking_time:
                status_text += f" | รอบ: {booking_time}"
            
            self.today_status_var.set(status_text)
        except Exception as e:
            self.today_canvas.delete("all")
            self.today_canvas.create_oval(2, 2, 16, 16, fill="#bdc3c7", outline="#bdc3c7")
            self.today_status_var.set(f"ตรวจสอบไม่ได้: {e}")



    def on_top_up(self):
        try:
            TopUpDialog(self, self.user_info)
        except Exception as e:
            messagebox.showerror("เติมเงิน", f"เปิดหน้าต่างเติมเงินไม่ได้: {e}")

    def open_live_mode_window(self):
        allowed_roles = ["admin", "vipi", "vipii", "premium", "staff"]
        role = self.user_info.get('Role', '')
        if role not in allowed_roles:
            messagebox.showerror("Error", f"คุณไม่มีสิทธิ์ใช้งานโหมดนี้ (role: {role})")
            return
        try:
            self.destroy()
            LiveModeWindow(user_info=self.user_info, api_data=self.api_data).mainloop()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {e}")
            App(self.user_info).mainloop()

    def open_trial_mode_window(self):
        if not self.api_data:
            messagebox.showwarning("คำเตือน", "API ยังไม่พร้อม โปรดลองใหม่")
            return
        try:
            self.destroy()
            TrialModeWindow(all_api_data=self.api_data, user_info=self.user_info).mainloop()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {e}")
            App(self.user_info).mainloop()

    @safe_execute()
    def open_simple_mode(self):
        """เปิด Simple Mode"""
        # ตรวจสอบ role
        role = self.user_info.get('Role', '').lower()
        if role == 'normal':
            messagebox.showerror("ไม่มีสิทธิ์", "โหมดนี้สำหรับสมาชิก VIP ขึ้นไป")
            return
        
        if not self.api_data:
            messagebox.showwarning("คำเตือน", "API ยังไม่พร้อม โปรดลองใหม่")
            return
        try:
            from simple_mode import SimpleModeWindow
            self.destroy()  # ปิด window ปัจจุบัน
            SimpleModeWindow(user_info=self.user_info, api_data=self.api_data).mainloop()
        except Exception as e:
            ErrorReporter.report_critical(e, "Failed to open simple mode")
    
    def open_admin_console(self):
        self.destroy()
        AdminConsoleWindow(self.user_info).mainloop()
    
    @safe_execute()
    def check_updates(self):
        """ตรวจสอบอัปเดต"""
        try:
            from updater import manual_update_check
            manual_update_check()
        except Exception as e:
            ErrorReporter.report_critical(e, "Failed to check updates")

    def logout(self):
        if messagebox.askyesno("Logout", "ออกจากระบบใช่ไหม?"):
            self.destroy()
            StartMenu().mainloop()





# ----------------------------- Login/Register/Start -----------------------------
class MainMenuWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_app_style(self)
        self.title("Welcome")
        self.geometry("360x240")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=(12, 12)); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="เลือกเมนู", font=("Arial", 13, "bold")).pack(pady=(6, 14))
        ttk.Button(frm, text="Login", command=self.open_login, width=24).pack(pady=6)
        ttk.Button(frm, text="Register", command=self.open_register, width=24).pack(pady=6)
        ttk.Button(frm, text="Contact", command=self.open_contact, width=24).pack(pady=6)
        ttk.Button(frm, text="Exit", command=self.destroy, width=24).pack(pady=(12, 0))

    def open_login(self):
        self.destroy(); LoginWindow().mainloop()

    def open_register(self):
        self.destroy(); RegisterWindow().mainloop()

    def open_contact(self):
        self.destroy(); ContactWindow().mainloop()


class RegisterWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_app_style(self)
        self.title("Register")
        self.geometry("400x260")
        self.resizable(False, False)
        frm = ttk.LabelFrame(self, text="สมัครผู้ใช้ใหม่", padding=(12, 12)); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frm, text="Username:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.username_entry = ttk.Entry(frm, width=28); self.username_entry.grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(frm, text="Password:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.password_entry = ttk.Entry(frm, show="*", width=28); self.password_entry.grid(row=1, column=1, padx=6, pady=6)
        btns = ttk.Frame(frm); btns.grid(row=2, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="ย้อนกลับ", command=lambda: (self.destroy(), MainMenuWindow().mainloop())).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="สมัคร", command=self.on_register).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="ยกเลิก", command=self.on_cancel).pack(side=tk.LEFT, padx=6)

    def on_register(self):
        username = (self.username_entry.get() or "").strip()
        password = (self.password_entry.get() or "").strip()
        if not username or not password:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Username/Password"); return
        try:
            rec = register_user(username=username, password=password)
            messagebox.showinfo("สำเร็จ", f"สมัครผู้ใช้เรียบร้อย\nUsername: {rec['Username']}\nRole: {rec['Role']}")
            self.destroy(); LoginWindow().mainloop()
        except Exception as e:
            messagebox.showerror("Error", f"สมัครไม่สำเร็จ: {e}")

    def on_cancel(self):
        self.destroy(); MainMenuWindow().mainloop()


class ContactWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_app_style(self)
        self.title("Contact")
        self.geometry("420x260"); self.resizable(False, False)
        frm = ttk.Frame(self, padding=(12, 12)); frm.pack(fill=tk.BOTH, expand=True)
        msg = ("ติดต่อผู้ดูแลระบบ\n\nLINE: your_line_id\nEmail: support@example.com\nคู่มือการใช้งาน: https://example.com/docs\n")
        txt = tk.Text(frm, wrap="word", height=8); txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, msg); txt.config(state=tk.DISABLED)
        ttk.Button(frm, text="ย้อนกลับ", command=self.back).pack(pady=10)

    def back(self):
        self.destroy(); MainMenuWindow().mainloop()


class LoginWindow(tk.Tk):
    def __init__(self, prev_user_info=None):
        super().__init__()
        apply_app_style(self)
        self.user_info = None
        self.prev_user_info = prev_user_info
        self.title("Login")
        self.geometry("350x220"); self.resizable(False, False)
        tk.Label(self, text="Username:", font=("Arial", 12)).pack(pady=(20,5))
        self.username_entry = ttk.Entry(self, font=("Arial", 11)); self.username_entry.pack(pady=5)
        tk.Label(self, text="Password:", font=("Arial", 12)).pack(pady=(10,5))
        self.password_entry = tk.Entry(self, show="*", font=("Arial", 11)); self.password_entry.pack(pady=5)
        btn_frame = ttk.Frame(self); btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Login", command=self.try_login).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="ย้อนกลับ", command=self.on_back).pack(side=tk.LEFT, padx=6)
        
        # Load saved credentials if available
        self._load_saved_credentials()

    def try_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Username และ Password"); return
        try:
            user_info = google_sheet_check_login(username, password)
        except Exception as e:
            messagebox.showerror("Error", f"เชื่อมต่อไม่ได้:\n{e}"); return
        if user_info == "expired":
            messagebox.showerror("Error", "บัญชีหมดอายุแล้ว"); return
        if not user_info:
            messagebox.showerror("Error", "Username หรือ Password ไม่ถูกต้อง"); return
        self.destroy(); App(user_info).mainloop()

    def _load_saved_credentials(self):
        """Load saved credentials from config wizard"""
        try:
            from config_loader import get_saved_credentials
            saved_creds = get_saved_credentials()
            if saved_creds:
                self.username_entry.insert(0, saved_creds.get('username', ''))
                self.password_entry.insert(0, saved_creds.get('password', ''))
        except Exception:
            pass
    
    def on_back(self):
        self.destroy(); StartMenu().mainloop()


class StartMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_app_style(self)
        self.title("Welcome"); self.geometry("360x240"); self.resizable(False, False)
        frm = ttk.Frame(self, padding=(20, 20)); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="ยินดีต้อนรับ", font=("Arial", 14, "bold")).pack(pady=(0, 12))
        ttk.Button(frm, text="Login", width=24, command=self.open_login).pack(pady=6)
        ttk.Button(frm, text="Register", width=24, command=self.open_register).pack(pady=6)
        ttk.Button(frm, text="Contact", width=24, command=self.open_contact).pack(pady=6)
        ttk.Button(frm, text="Exit", width=24, command=self.destroy).pack(pady=(10, 0))

    def open_login(self):
        self.destroy(); LoginWindow().mainloop()

    def open_register(self):
        self.destroy(); RegisterWindow().mainloop()

    def open_contact(self):
        messagebox.showinfo("Contact", "Contact us: LINE ID @lockonstatosx")


# ----------------------------- main -----------------------------
def main():
    setup_config_files()
    
    # Check for updates on startup (silent)
    try:
        from updater import check_updates_on_startup
        check_updates_on_startup()
    except Exception:
        pass
    
    # Check if first-time setup is needed
    try:
        from config_wizard import should_show_wizard, ConfigWizard
        from config_loader import get_saved_credentials
        
        if should_show_wizard():
            ConfigWizard().mainloop()
        else:
            # Check for saved credentials
            saved_creds = get_saved_credentials()
            if saved_creds and saved_creds['username'] and saved_creds['password']:
                # Auto login with saved credentials
                try:
                    user_info = google_sheet_check_login(saved_creds['username'], saved_creds['password'])
                    if user_info and user_info != "expired":
                        App(user_info).mainloop()
                        return
                except Exception:
                    pass
            
            # Fallback to login screen
            StartMenu().mainloop()
    except ImportError:
        # Fallback if wizard not available
        StartMenu().mainloop()

if __name__ == "__main__":
    main()
