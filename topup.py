import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

# Utilities to record and update top-up requests in Google Sheet
try:
    from utils import record_topup_request, update_topup_proof
except Exception:
    # Fallback stubs if utils not ready; UI will show an error
    def record_topup_request(user_info: dict, amount: float, method: str, note: str | None = None) -> dict:
        raise RuntimeError("record_topup_request is unavailable")
    def update_topup_proof(txid: str, proof_link: str) -> bool:
        raise RuntimeError("update_topup_proof is unavailable")


class TopUpDialog(tk.Toplevel):
    """
    Simple top-up window with:
      - amount input (THB)
      - payment method selector
      - note/reference (optional)
      - submit -> creates a top-up request in Google Sheet (Status: Pending)
      - after creation, shows TxID and allows submitting a proof link to update the request
    """
    METHODS = [
        "PromptPay (QR)",
        "TrueMoney",
        "LINE Pay",
        "Bank Transfer",
        "Other",
    ]

    def __init__(self, master, user_info: dict):
        super().__init__(master)
        self.title("เติม��งิน (Top-up)")
        self.geometry("460x360")
        self.resizable(False, False)
        self.user_info = user_info or {}
        self.txid: Optional[str] = None

        container = ttk.Frame(self, padding=(12, 10))
        container.pack(fill=tk.BOTH, expand=True)

        # Amount
        ttk.Label(container, text="จำนวนเงิน (THB):").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.amount_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.amount_var, width=18).grid(row=0, column=1, sticky="w", padx=6, pady=6)

        # Method
        ttk.Label(container, text="วิธีชำระเงิน:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.method_var = tk.StringVar(value=self.METHODS[0])
        ttk.Combobox(container, values=self.METHODS, textvariable=self.method_var, state="readonly", width=16).grid(row=1, column=1, sticky="w", padx=6, pady=6)

        # Note
        ttk.Label(container, text="หมายเหตุ/อ้างอิง (ถ้ามี):").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        self.note_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.note_var, width=26).grid(row=2, column=1, sticky="w", padx=6, pady=6)

        # Submit section
        submit_row = ttk.Frame(container)
        submit_row.grid(row=3, column=0, columnspan=2, pady=(10, 6))
        ttk.Button(submit_row, text="สร้างคำขอเติมเงิน", command=self.on_submit).pack(side=tk.LEFT, padx=4)
        ttk.Button(submit_row, text="ปิด", command=self.destroy).pack(side=tk.LEFT, padx=4)

        # Separator
        ttk.Separator(container, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 8))

        # Result area (TxID + Proof submission)
        self.result_frame = ttk.LabelFrame(container, text="ผลการสร้างคำขอ / อัปโหลดหลักฐาน", padding=(10, 8))
        self.result_frame.grid(row=5, column=0, columnspan=2, sticky="ew")
        self.result_frame.grid_remove()

        self.txid_var = tk.StringVar()
        ttk.Label(self.result_frame, text="รหัสรายการ (TxID):").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(self.result_frame, textvariable=self.txid_var, width=28, state="readonly").grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(self.result_frame, text="ลิงก์หลักฐานชำระเงิน:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.proof_var = tk.StringVar()
        ttk.Entry(self.result_frame, textvariable=self.proof_var, width=28).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Button(self.result_frame, text="ส่งหลักฐาน", command=self.on_submit_proof).grid(row=2, column=1, sticky="w", padx=4, pady=8)

        # Tips
        tips = (
            "คำแนะนำ:\n"
            "- สร้างคำขอก่อน จากนั้นจะได้ TxID สำหรับอ้างอิง\n"
            "- โอน/ชำระตามวิธีที่เลือก แล้วอัปโหลดหลักฐาน (เช่น ลิงก์รูปภาพ)\n"
            "- ระบบจะปรับยอดหลังจากตรวจสอบแล้ว"
        )
        ttk.Label(container, text=tips, foreground="#555").grid(row=6, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 0))

        self.grab_set()
        self.focus_set()

    def on_submit(self):
        # Validate
        try:
            amt = float((self.amount_var.get() or "").strip())
        except Exception:
            messagebox.showwarning("คำเตือน", "จำนวนเงินไม่ถูกต้อง")
            return
        if amt <= 0:
            messagebox.showwarning("คำเตือน", "จำนวนเงินต้องมากกว่า 0")
            return
        method = (self.method_var.get() or "").strip()
        note = (self.note_var.get() or "").strip() or None
        try:
            result = record_topup_request(self.user_info, amt, method, note)
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถสร้างคำขอเติมเงินได้: {e}")
            return
        self.txid = str(result.get("TxID") or "")
        self.txid_var.set(self.txid)
        self.result_frame.grid()
        messagebox.showinfo("สำเร็จ", f"สร้างคำขอเติมเงินเรียบร้อย\nTxID: {self.txid}\nสถานะ: Pending")

    def on_submit_proof(self):
        if not self.txid:
            messagebox.showwarning("คำเตือน", "กรุณาสร้างคำขอเติมเงินก่อน (ต้องมี TxID)")
            return
        proof_link = (self.proof_var.get() or "").strip()
        if not proof_link:
            messagebox.showwarning("คำเตือน", "กรุณากรอกลิงก์หลักฐานการชำระเงิน")
            return
        try:
            ok = update_topup_proof(self.txid, proof_link)
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"ส่งหลักฐานไม่สำเร็จ: {e}")
            return
        if ok:
            messagebox.showinfo("สำเร็จ", "ส่งหลักฐานเรียบร้อย สถานะจะถูกอัปเดตหลังการตรวจสอบ")
        else:
            messagebox.showwarning("คำเตือน", "ไม่พบรายการที่ตรงกับ TxID หรืออัปเดตไม่สำเร็จ")
