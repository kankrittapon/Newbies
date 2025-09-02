import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from uuid import uuid4
from typing import Optional

# ใช้ Payment Backend ผ่าน payments_client
try:
    from payments_client import create_payment_by_tier, create_payment
except Exception:
    def create_payment_by_tier(*args, **kwargs):  # type: ignore
        raise RuntimeError("payments_client.create_payment_by_tier unavailable")
    def create_payment(*args, **kwargs):  # type: ignore
        raise RuntimeError("payments_client.create_payment unavailable")


class TopUpDialog(tk.Toplevel):
    """
    หน้าต่างเติมเงิน (Stripe via Payment Backend)
    - ถ้า role = admin: ป้อนจำนวนเงินเองได้ (> 0, ทศนิยมไม่เกิน 2)
    - ถ้า role อื่น: เลือก VIPI/VIPII/VIPIII จาก Dropdown (1500/2500/3500)
    - กดไปหน้าชำระเงิน -> เปิด Stripe Checkout URL ในเว็บเบราว์เซอร์ แล้วปิดหน้าต่าง

    หมายเหตุ: ต���ด Truemoney Wallet ออกแล้ว (ไม่แสดงใน UI)
    """

    TIERS = ["VIPI", "VIPII", "VIPIII"]

    def __init__(self, master, user_info: dict):
        super().__init__(master)
        self.title("เติมเงิน (Top-up)")
        self.geometry("460x240")
        self.resizable(False, False)
        self.user_info = user_info or {}
        # Guard flags to prevent double submit/redirect
        self._redirected = False
        self._submitting = False
        self.submit_btn: Optional[ttk.Button] = None
        self.close_btn: Optional[ttk.Button] = None

        # ตรวจสอบ role ของผู้ใช้
        role = str(self.user_info.get("Role", "")).strip().lower()
        self.is_admin = (role == "admin")

        container = ttk.Frame(self, padding=(12, 10))
        container.pack(fill=tk.BOTH, expand=True)

        if self.is_admin:
            # โหมด admin: กรอกจำนวนเงินได้เอง
            ttk.Label(container, text="จำนวนเงิน (THB):").grid(row=0, column=0, sticky="e", padx=6, pady=6)
            self.amount_var = tk.StringVar()
            ttk.Entry(container, textvariable=self.amount_var, width=20).grid(row=0, column=1, sticky="w", padx=6, pady=6)
            self.submit_btn = ttk.Button(container, text="ไปหน้าชำระเงิน", command=self._submit_admin)
            self.submit_btn.grid(row=1, column=0, columnspan=2, pady=(10, 6))
        else:
            # โหมดผู้ใช้ทั่วไป: เลือกแพ็��เกจ VIP
            ttk.Label(container, text="แพ็กเกจ (VIP):").grid(row=0, column=0, sticky="e", padx=6, pady=6)
            self.tier_var = tk.StringVar(value=self.TIERS[0])
            ttk.Combobox(container, values=self.TIERS, textvariable=self.tier_var, state="readonly", width=18).grid(row=0, column=1, sticky="w", padx=6, pady=6)
            self.submit_btn = ttk.Button(container, text="ไปหน้าชำระเงิน", command=self._submit_tier)
            self.submit_btn.grid(row=1, column=0, columnspan=2, pady=(10, 6))

        self.close_btn = ttk.Button(container, text="ปิด", command=self.destroy)
        self.close_btn.grid(row=3, column=0, columnspan=2, pady=(4, 0))

        tips = (
            "คำแนะนำ:\n"
            "- ระบบจะพาไป Stripe Checkout เพื่อชำระเงิน\n"
            "- ไม่ต้องส่งหลักฐาน ระบบจะอัปเดตอัตโนมัติเมื่อชำระสำเร็จ"
        )
        ttk.Label(container, text=tips, foreground="#555").grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 0))

        self.grab_set()
        self.focus_set()

    def _open_checkout(self, url: str):
        if not url:
            messagebox.showerror("ผิดพลาด", "ไม่พบ URL สำหรับชำระเงิน")
            return
        if self._redirected:
            return
        self._redirected = True
        try:
            if self.submit_btn:
                self.submit_btn.config(state="disabled")
            if self.close_btn:
                self.close_btn.config(state="disabled")
        except Exception:
            pass
        webbrowser.open_new_tab(url)
        self.after(100, self.destroy)

    def _submit_admin(self):
        if self._submitting or self._redirected:
            return
        self._submitting = True
        # ตรวจสอบจำนวนเงินที่กรอก
        try:
            amt = float((self.amount_var.get() or "").strip())
            if amt <= 0 or (round(amt, 2) != float(f"{amt:.2f}")):
                raise ValueError
        except Exception:
            self._submitting = False
            messagebox.showwarning("คำเตือน", "จำนวนเงินต้องมากกว่า 0 และทศนิยมไม่เกิน 2 ตำแหน่ง")
            return

        username = str(self.user_info.get("Username") or "-")
        client_txid = uuid4().hex[:8].upper()

        try:
            result = create_payment(
                txid=client_txid,
                amount=amt,
                channel="promptpay",                 # label เฉยๆ
                description="Top-up (ADMIN)",
                username=username,
                role="admin",                        # สำคัญเพื่อ bypass allowlist ฝั่ง client
            )
            url = str(result.get("deeplink") or result.get("url") or "")
            if not url:
                self._submitting = False
                messagebox.showerror("ผิดพลาด", "ไม่พบ URL สำหรับชำระเงิน")
                return
            self._open_checkout(url)
        except Exception as e:
            self._submitting = False
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถสร้างการชำระเงินได้: {e}")

    def _submit_tier(self):
        if self._submitting or self._redirected:
            return
        self._submitting = True
        tier = (self.tier_var.get() or "").strip().upper()
        if tier not in self.TIERS:
            self._submitting = False
            messagebox.showwarning("คำเตือน", "กรุณาเลือกแพ็กเกจ VIP ให้ถูกต้อง")
            return

        username = str(self.user_info.get("Username") or "-")
        client_txid = uuid4().hex[:8].upper()

        try:
            result = create_payment_by_tier(
                tier=tier,
                username=username,
                client_txid=client_txid,
            )
            url = str(result.get("deeplink") or result.get("url") or "")
            if not url:
                self._submitting = False
                messagebox.showerror("ผิดพลาด", "ไม่พบ URL สำหรับชำระเงิน")
                return
            self._open_checkout(url)
        except Exception as e:
            self._submitting = False
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถสร้างการชำระเงินได้: {e}")
