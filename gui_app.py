import tkinter as tk
from tkinter import ttk, messagebox
from chrome_op import launch_chrome_with_profile
from edge_op import launch_edge_with_profile
from utils import get_all_api_data, google_sheet_check_login  # สมมติมีฟังก์ชันตรวจ login
import threading

profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"]
browsers = ["Chrome", "Edge"]

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

class App(tk.Tk):
    def __init__(self, user_info):
        super().__init__()
        self.title("Browser Profile Launcher & API Loader")
        self.geometry("450x350")
        self.resizable(False, False)
        self.user_info = user_info

        user_summary = (
            f"User: {self.user_info['Username']}\n"
            f"Role: {self.user_info.get('Role', '-')}\n"
            f"Max Profiles: {self.user_info.get('Max Profiles', '-')}\n"
            f"Can Use Scheduler: {self.user_info.get('Can Use Scheduler', '-')}\n"
            f"Expiration date: {self.user_info.get('Expiration date', '-')}"
        )
        tk.Label(self, text=user_summary, font=("Arial", 11), justify=tk.LEFT).pack(pady=10)

        tk.Label(self, text="Select Browser:", font=("Arial", 12)).pack(pady=(5, 3))
        self.browser_var = tk.StringVar(value=browsers[0])
        browser_combo = ttk.Combobox(self, values=browsers, textvariable=self.browser_var, state="readonly", font=("Arial", 11))
        browser_combo.pack(pady=5)

        tk.Label(self, text="Select Profile:", font=("Arial", 12)).pack(pady=(5, 3))
        self.profile_var = tk.StringVar(value=profiles[0])
        profile_combo = ttk.Combobox(self, values=profiles, textvariable=self.profile_var, state="readonly", font=("Arial", 11))
        profile_combo.pack(pady=5)

        launch_btn = ttk.Button(self, text="Launch Browser", command=self.on_launch)
        launch_btn.pack(pady=10)

        check_btn = ttk.Button(self, text="สถานะ Config", command=self.open_api_status)
        check_btn.pack(pady=5)

        logout_btn = ttk.Button(self, text="Logout", command=self.logout)
        logout_btn.pack(pady=15)

    def on_launch(self):
        selected_browser = self.browser_var.get()
        selected_profile = self.profile_var.get()
        if not selected_browser or not selected_profile:
            messagebox.showwarning("คำเตือน", "Please select both browser and profile!")
            return

        if selected_browser == "Chrome":
            launch_chrome_with_profile(selected_profile)
        elif selected_browser == "Edge":
            launch_edge_with_profile(selected_profile)

        messagebox.showinfo("Success", f"Launched {selected_browser} with profile '{selected_profile}'")

    def open_api_status(self):
        ApiStatusPopup(self)

    def logout(self):
        confirm = messagebox.askyesno("Logout", "คุณต้องการออกจากระบบใช่หรือไม่?")
        if confirm:
            self.destroy()
            main()  # เรียกกลับไปหน้า login

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
        self.password_entry = ttk.Entry(self, show="*", font=("Arial", 11))
        self.password_entry.pack(pady=5)

        login_btn = ttk.Button(self, text="Login", command=self.try_login)
        login_btn.pack(pady=20)

    def try_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning("คำเตือน", "กรุณากรอก Username และ Password")
            return

        # ตรวจสอบข้อมูลจาก google sheet ใน utils.py
        try:
            user_info = google_sheet_check_login(username, password)
        except Exception as e:
            messagebox.showerror("Error", f"เกิดข้อผิดพลาดในการเชื่อมต่อ:\n{e}")
            return

        if not user_info:
            messagebox.showerror("Error", "Username หรือ Password ไม่ถูกต้อง")
            return

        # ถ้า login สำเร็จ ปิด login หน้าต่าง แล้วเปิด app หลัก
        self.destroy()
        app = App(user_info)
        app.mainloop()

def main():
    login_win = LoginWindow()
    login_win.mainloop()

if __name__ == "__main__":
    main()
