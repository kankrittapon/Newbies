# Scheduledreal_booking.py
import threading
import time
import json
import asyncio
from datetime import datetime, timedelta
import uuid
import traceback
import os
import sys
from pathlib import Path

# นำเข้าฟังก์ชันการจองจาก real_booking.py
from real_booking import perform_real_booking, attach_to_chrome

# นำเข้าฟังก์ชัน launch browser จาก chrome_op และ edge_op
from chrome_op import launch_chrome_instance
from edge_op import launch_edge_with_profile

# คลาสสำหรับจัดการการจองแต่ละรายการ
class BookingTask:
    def __init__(self, task_data):
        self.id = str(uuid.uuid4())
        self.task_data = task_data
        self.status = "waiting" # สถานะเริ่มต้น
        self.thread = None # เก็บ reference ของ thread ที่รัน booking
        self.cdp_port = None # เก็บ port ของ browser ที่เปิดไว้
        self.is_cancelled = False # Flag สำหรับการยกเลิก task

    def to_dict(self):
        # แปลงข้อมูล task ให้เป็น dictionary สำหรับการบันทึก
        data_to_save = self.task_data.copy()
        if 'line_password' in data_to_save:
            del data_to_save['line_password']
        return {
            "id": self.id,
            "task_data": data_to_save,
            "status": self.status,
            "cdp_port": self.cdp_port
        }
        
    def cancel_task(self):
        self.is_cancelled = True
        
    async def _run_async_booking_real(self, all_api_data, progress_callback):
        # เมธอดสำหรับการจองจริงโดยเฉพาะ
        playwright = None
        try:
            progress_callback(f"⏳ Task [{self.id[:4]}] - กำลังรอเชื่อมต่อกับเบราว์เซอร์...")
            playwright, browser, context, page = await attach_to_chrome(self.cdp_port)
            progress_callback(f"✅ Task [{self.id[:4]}] - เชื่อมต่อสำเร็จ!")

            # ตรวจสอบว่า task ถูกยกเลิกหรือไม่
            if self.is_cancelled:
                raise asyncio.CancelledError

            await perform_real_booking(
                page=page,
                all_api_data=all_api_data,
                site_name=self.task_data.get('site_name'),
                selected_branch=self.task_data.get('selected_branch'),
                selected_day=self.task_data.get('selected_day'),
                selected_time=self.task_data.get('selected_time'),
                register_by_user=False,
                confirm_by_user=False,
                progress_callback=progress_callback
            )
            progress_callback(f"✅ Task [{self.id[:4]}] - การจองเสร็จสิ้น!")
            self.status = "completed"

        except asyncio.CancelledError:
            progress_callback(f"🚨 Task [{self.id[:4]}] - ถูกยกเลิก")
            self.status = "cancelled"
        except Exception as e:
            progress_callback(f"❌ Task [{self.id[:4]}] - เกิดข้อผิดพลาดในการจอง: {e}")
            progress_callback(traceback.format_exc())
            self.status = "failed"
        finally:
            if playwright:
                await playwright.stop()
            progress_callback(f"🟢 Task [{self.id[:4]}] - กระบวนการสิ้นสุดแล้ว")
    
    def run_booking(self, all_api_data, progress_callback):
        # นี่คือเมธอดที่จะรันใน thread ย่อย
        try:
            progress_callback(f"🚀 Task [{self.id[:4]}] - กำลังเริ่มการจอง...")
            
            browser_type = self.task_data.get('browser_type')
            profile_name = self.task_data.get('profile')
            
            launched_port, _ = None
            if browser_type == "Chrome":
                launched_port, _ = launch_chrome_instance(profile_name)
            elif browser_type == "Edge":
                launched_port, _ = launch_edge_with_profile(profile_name)
            
            if not launched_port:
                raise Exception("ไม่สามารถเปิดเบราว์เซอร์ได้")

            self.cdp_port = launched_port
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_async_booking_real(all_api_data, progress_callback))
            
        except Exception as e:
            progress_callback(f"❌ Task [{self.id[:4]}] - เกิดข้อผิดพลาด: {e}")
            progress_callback(traceback.format_exc())
            self.status = "failed"
        finally:
            if self.cdp_port:
                pass
            pass

class ScheduledManager:
    def __init__(self, all_api_data, progress_callback):
        self.all_api_data = all_api_data
        self.progress_callback = progress_callback
        self.tasks = []
        self._scheduler_thread = None
        self._stop_event = threading.Event()

        self.appdata_path = self._get_app_data_path()
        
        # แก้ไขตรงนี้: ชี้ไปที่ไฟล์ line_data.json
        self.line_data_path = self.appdata_path / "line_data.json"
        self.tasks_path = self.appdata_path / "scheduled_tasks.json"

        self.load_tasks()
        # แก้ไขตรงนี้: โหลดข้อมูล Line ทั้งหมดมาเก็บไว้ในตัวแปรเดียว
        self.line_data = self.load_line_credentials() 

    @staticmethod
    def _get_app_data_path():
        # เมธอดนี้ไม่ต้องแก้ไข
        if sys.platform.startswith("win"):
            app_data = os.environ.get('APPDATA')
            if app_data:
                path = Path(app_data) / "BokkChoYCompany"
                print(f"APPDATA path (Windows): {path}")
                path.mkdir(parents=True, exist_ok=True)
                return path
        path = Path.home() / ".BokkChoYCompany"
        print(f"HOME path (Non-Windows): {path}") 
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_line_credentials(self, data):
        """บันทึกข้อมูล Line Credentials ทั้งหมดลงในไฟล์เดียว"""
        with open(self.line_data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        self.progress_callback("✅ บันทึก Line Credentials เรียบร้อยแล้ว")
        print("File saved successfully.")

    def remove_line_credentials_by_email(self, email):
        path = self.line_data_path  # ใช้ path เดียวกับตอน save/load
        if not os.path.exists(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if email in data:
            del data[email]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.progress_callback(f"🗑️ ลบบัญชี LINE: {email} สำเร็จแล้ว")
        else:
            self.progress_callback(f"⚠️ ไม่พบบัญชี LINE: {email} ที่จะลบ")
    
    def load_line_credentials(self):
        """โหลดข้อมูล Line Credentials ทั้งหมดจากไฟล์เดียว"""
        try:
            with open(self.line_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.progress_callback("✅ โหลด Line Credentials เรียบร้อยแล้ว")
            return data
        except FileNotFoundError:
            self.progress_callback("ℹ️ ไม่พบไฟล์ Line Credentials")
            return {}

    def is_line_credential_exist(self, email):
        return email in self.line_data

    def save_tasks(self):
        # ใช้ self.tasks_path ที่กำหนดไว้แล้ว
        with open(self.tasks_path, "w", encoding='utf-8') as f:
            json.dump([task.to_dict() for task in self.tasks], f, indent=4, ensure_ascii=False)

    def load_tasks(self):
        # ใช้ self.tasks_path ที่กำหนดไว้แล้ว
        try:
            with open(self.tasks_path, "r", encoding='utf-8') as f:
                saved_tasks = json.load(f)
                self.tasks = [BookingTask(t['task_data']) for t in saved_tasks]
            self.progress_callback("✅ โหลด tasks ที่บันทึกไว้เรียบร้อยแล้ว")
        except (FileNotFoundError, json.JSONDecodeError):
            self.progress_callback("ℹ️ ไม่พบไฟล์ scheduled_tasks.json เริ่มต้นใหม่")
            self.tasks = []
    def add_booking(self, task_data):
        new_task = BookingTask(task_data)
        self.tasks.append(new_task)
        self.save_tasks()
        self.progress_callback(f"✅ เพิ่ม Task ใหม่สำเร็จ: {task_data.get('profile')} ({task_data.get('selected_time')})")
        return new_task.id

    def remove_booking(self, task_id):
        self.tasks = [task for task in self.tasks if task.id != task_id]
        self.save_tasks()
        self.progress_callback(f"✅ ลบ Task [{task_id[:4]}] เรียบร้อยแล้ว")

    def edit_booking(self, task_id, new_data):
        for task in self.tasks:
            if task.id == task_id:
                task.task_data.update(new_data)
                self.save_tasks()
                self.progress_callback(f"✅ แก้ไข Task [{task_id[:4]}] เรียบร้อยแล้ว")
                return True
        return False
        
    def clear_all_tasks(self):
        self.tasks = []
        self.save_tasks()
        self.progress_callback("✅ ล้าง Tasks ทั้งหมดเรียบร้อยแล้ว")

    def start_scheduler(self):
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self.progress_callback("⚠️ Scheduler กำลังทำงานอยู่แล้ว")
            return
            
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._monitor_tasks, daemon=True)
        self._scheduler_thread.start()
        self.progress_callback("🟢 เริ่มต้น Scheduler เรียบร้อยแล้ว")

    def stop_scheduler(self):
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._stop_event.set()
            for task in self.tasks:
                if task.status == "running":
                    task.cancel_task()
            self._scheduler_thread.join(timeout=2)
            self.progress_callback("🔴 หยุด Scheduler แล้ว")

    def _monitor_tasks(self):
        self.progress_callback("⏳ Scheduler กำลังตรวจสอบ tasks ใน background...")
        while not self._stop_event.is_set():
            now = datetime.now()
            
            for task in self.tasks:
                if task.status == "waiting":
                    try:
                        scheduled_time_str = f"{now.year}-{now.month:02d}-{int(task.task_data.get('selected_day')):02d} {task.task_data.get('selected_time')}:00"
                        scheduled_time = datetime.strptime(scheduled_time_str, '%Y-%m-%d %H:%M:%S')
                        
                        start_run_time = scheduled_time - timedelta(seconds=10)
                        
                        if now >= start_run_time:
                            task.status = "running"
                            booking_thread = threading.Thread(target=task.run_booking, args=(self.all_api_data, self.progress_callback), daemon=True)
                            booking_thread.start()
                            task.thread = booking_thread
                            self.progress_callback(f"▶️ Task [{task.id[:4]}] - ถึงเวลาเริ่มจองแล้ว!")
                    except Exception as e:
                        self.progress_callback(f"❌ เกิดข้อผิดพลาดในการตรวจสอบเวลาสำหรับ Task [{task.id[:4]}]: {e}")
            
            time.sleep(1)
        self.progress_callback("✅ Scheduler Thread สิ้นสุดการทำงาน")