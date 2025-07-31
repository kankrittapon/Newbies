import tkinter as tk
from tkinter import messagebox
from utils import create_gsheet_client, open_google_sheet
from datetime import datetime

SPREADSHEET_KEY = "1rQnV_-30tmb8oYj7g9q6-YdyuWZZ2c8sZ2xH7pqszVk"
SHEET_NAME = "Sheet1"  # เปลี่ยนตามชื่อ sheet จริง

class LoginApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Login")
        self.geometry("300x200")
        self.resizable(False, False)

        tk.Label(self, text="Username:").pack(pady=5)
        self.username_entry = tk.Entry(self)
        self.username_entry.pack(pady=5)

        tk.Label(self, text="Password:").pack(pady=5)
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack(pady=5)

        login_btn = tk.Button(self, text="Login", command=self.check_login)
        login_btn.pack(pady=15)

        # เตรียม client และ sheet ไว้
        self.client = create_gsheet_client()
        self.sheet = open_google_sheet(self.client, SPREADSHEET_KEY).worksheet(SHEET_NAME)

    def check_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning("Warning", "กรุณากรอก username และ password")
            return

        # ดึงข้อมูลใน sheet ทั้งหมด (สมมติว่า header อยู่แถวแรก)
        records = self.sheet.get_all_records()
        user = None
        for row in records:
            if row["Username"] == username and row["Password"] == password:
                user = row
                break

        if user is None:
            messagebox.showerror("Error", "Username หรือ Password ไม่ถูกต้อง")
            return

        # เช็ควันหมดอายุ (format สมมติ yyyy-mm-dd)
        exp_date_str = user.get("Expiration date", "")
        if exp_date_str:
            try:
                exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
                if exp_date < datetime.now():
                    messagebox.showerror("Error", "บัญชีผู้ใช้หมดอายุแล้ว")
                    return
            except Exception:
                pass

        # login ผ่าน
        messagebox.showinfo(
            "Welcome",
            f"สวัสดี {username}!\nRole: {user.get('Role')}\n"
            f"สามารถจองล่วงหน้าได้ {user.get('สามาถตั้งจองล่วงหน้าได้กี่ site')} site\n"
            f"สิทธิ์การจองล่วงหน้า: {user.get('ตั้งจองล่วงหน้าได้ไหม')}"
        )
        self.destroy()  # ปิดหน้าต่าง login
        # ต่อด้วยหน้าหลัก หรือฟังก์ชันอื่นๆ ต่อได้

if __name__ == "__main__":
    app = LoginApp()
    app.mainloop()
