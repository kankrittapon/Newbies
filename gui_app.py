import tkinter as tk
from tkinter import ttk, messagebox
from chrome_op import launch_chrome_with_profile
from edge_op import launch_edge_with_profile
from utils import get_all_api_data, google_sheet_check_login
import threading
import asyncio

# Import Playwright operations
from playwright_ops import launch_browser_and_perform_booking, get_site_elements_config

profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"]
browsers = ["Chrome", "Edge"]
sites = ["PMROCKET", "EZBOT"]
days = [str(i) for i in range(1, 32)]

class ApiStatusPopup(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("สถานะ Config")
        self.geometry("400x300")
        self.resizable(False, False)

        self.text = tk.Text(self, wrap="word", font=("Arial", 12))
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        threading.Thread(target=self.load_api_status).start()

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

class TrialModeWindow(tk.Toplevel):
    def __init__(self, parent, all_api_data):
        super().__init__(parent)
        self.title("โหมดทดลอง")
        self.geometry("400x600")
        self.resizable(False, False)
        self.all_api_data = all_api_data
        self.parent = parent

        tk.Label(self, text="เลือก Site:", font=("Arial", 12)).pack(pady=(10, 3))
        self.site_var = tk.StringVar(value=sites[0])
        self.site_combo = ttk.Combobox(self, values=sites, textvariable=self.site_var, state="readonly", font=("Arial", 11))
        self.site_combo.pack(pady=5)
        self.site_combo.bind("<<ComboboxSelected>>", self.on_site_selected)

        tk.Label(self, text="เลือก Browser:", font=("Arial", 12)).pack(pady=(10, 3))
        self.browser_var = tk.StringVar(value=browsers[0])
        browser_combo = ttk.Combobox(self, values=browsers, textvariable=self.browser_var, state="readonly", font=("Arial", 11))
        browser_combo.pack(pady=5)

        tk.Label(self, text="เลือก Branch:", font=("Arial", 12)).pack(pady=(10, 3))
        self.branch_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(self, textvariable=self.branch_var, state="readonly", font=("Arial", 11))
        self.branch_combo.pack(pady=5)

        tk.Label(self, text="เลือกวัน:", font=("Arial", 12)).pack(pady=(10, 3))
        self.day_var = tk.StringVar(value=days[0])
        self.day_combo = ttk.Combobox(self, values=days, textvariable=self.day_var, state="readonly", font=("Arial", 11))
        self.day_combo.pack(pady=5)

        tk.Label(self, text="เลือก Time:", font=("Arial", 12)).pack(pady=(10, 3))
        self.time_var = tk.StringVar()
        self.time_combo = ttk.Combobox(self, textvariable=self.time_var, state="readonly", font=("Arial", 11))
        self.time_combo.pack(pady=5)

        self.status_frame = ttk.LabelFrame(self, text="สถานะ Playwright", padding=(10, 5))
        self.status_frame.pack(pady=10, padx=10, fill="x", expand=True)

        self.status_text = tk.Text(self.status_frame, wrap="word", font=("Arial", 10), height=5)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.insert(tk.END, "พร้อมเริ่มต้นโหมดทดลอง...\n")
        self.status_text.config(state=tk.DISABLED)

        start_btn = ttk.Button(self, text="เริ่มโหมดทดลอง", command=self.start_trial_booking)
        start_btn.pack(pady=20)

        self.on_site_selected()

    def update_status(self, message):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def on_site_selected(self, event=None):
        selected_site = self.site_var.get()
        
        branches = self.all_api_data.get("branchs", [])
        times = self.all_api_data.get("times", [])

        branch_names = [b.get("name", b) if isinstance(b, dict) else b for b in branches]
        self.branch_combo['values'] = branch_names
        if branch_names:
            self.branch_var.set(branch_names[0])
        else:
            self.branch_var.set("")

        time_values = [t.get("value", t) if isinstance(t, dict) else t for t in times]
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

        self.update_status(f"กำลังเริ่มโหมดทดลองสำหรับ Site: {selected_site}, Browser: {selected_browser}, Branch: {selected_branch}, วันที่: {selected_day}, เวลา: {selected_time}...")
        
        threading.Thread(target=self._run_async_booking, 
                         args=(selected_browser, selected_site, self.all_api_data, selected_branch, selected_day, selected_time)).start()

    def _run_async_booking(self, browser_type, site_name, all_api_data, selected_branch, selected_day, selected_time):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                launch_browser_and_perform_booking(
                    browser_type,
                    site_name,
                    all_api_data,
                    selected_branch,
                    selected_day,
                    selected_time,
                    progress_callback=self.update_status
                )
            )
        except Exception as e:
            self.update_status(f"❌ เกิดข้อผิดพลาดที่ไม่คาดคิดในการจอง: {e}")
        finally:
            # เพิ่ม pass เพื่อแก้ไข IndentationError
            pass 

class App(tk.Tk):
    def __init__(self, user_info):
        super().__init__()
        self.title("Browser Profile Launcher & API Loader")
        self.geometry("450x550")
        self.resizable(False, False)
        self.user_info = user_info

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

        check_btn = ttk.Button(menu_frame, text="ตรวจสอบสถานะ Config", command=self.open_api_status, width=25)
        check_btn.pack(pady=5)

        top_up_btn = ttk.Button(menu_frame, text="เติมเงิน", command=self.on_top_up, width=25)
        top_up_btn.pack(pady=5)

        trial_mode_btn = ttk.Button(menu_frame, text="โหมดทดลอง", command=self.open_trial_mode_window, width=25)
        trial_mode_btn.pack(pady=5)

        live_mode_btn = ttk.Button(menu_frame, text="โหมดใช้งานจริง", command=self.on_live_mode, width=25)
        live_mode_btn.pack(pady=5)

        logout_btn = ttk.Button(menu_frame, text="Logout", command=self.logout, width=25)
        logout_btn.pack(pady=5)

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
        ApiStatusPopup(self)

    def on_top_up(self):
        messagebox.showinfo("เติมเงิน", "ฟังก์ชันเติมเงินยังไม่เปิดใช้งาน")

    def on_live_mode(self):
        messagebox.showinfo("โหมดใช้งานจริง", "เข้าสู่โหมดใช้งานจริง")
    
    def open_trial_mode_window(self):
        messagebox.showinfo("ข้อมูล API", "กำลังโหลดข้อมูล API... โปรดรอสักครู่")
        threading.Thread(target=self._load_api_and_open_trial_window).start()

    def _load_api_and_open_trial_window(self):
        try:
            api_data = get_all_api_data()
            self.after(0, lambda: self._show_trial_mode_window_after_load(api_data))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการโหลดข้อมูล API:\n{e}"))

    def _show_trial_mode_window_after_load(self, api_data):
        if not hasattr(self, '_trial_mode_window') or not self._trial_mode_window.winfo_exists():
            self._trial_mode_window = TrialModeWindow(self, api_data)
            self._trial_mode_window.grab_set()
            self._trial_mode_window.focus_set()
            self._trial_mode_window.transient(self)

    def logout(self):
        confirm = messagebox.askyesno("Logout", "คุณต้องการออกจากระบบใช่หรือไม่?")
        if confirm:
            self.destroy()

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
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
    login_win = LoginWindow()
    login_win.mainloop()

if __name__ == "__main__":
    main()