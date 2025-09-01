from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from utils import load_line_credentials


async def perform_line_login(page: Page, progress_callback=None, preferred_email: str | None = None) -> bool:
    """
    เดิน flow การล็อกอิน LINE บนหน้า Rocket Booking หากจำเป็น
    - คลิกปุ่ม Connect LINE ถ้ามี
    - คลิก "login with different account" ถ้ามี
    - กรอก email/password จาก line_data.json
    - รอจนฟ��ร์มหายหรือกลับสู่หน้าหลัก
    """
    creds = load_line_credentials() or {}
    email = None
    password = None
    try:
        # 1) รองรับรูปแบบ mapping หลายบัญชี {email: password}
        if isinstance(creds, dict) and not any(k in creds for k in ("Email","email","username","Password","password")):
            if preferred_email and preferred_email in creds:
                email = preferred_email
                password = creds.get(preferred_email)
            elif len(creds) == 1:
                email, password = next(iter(creds.items()))
        # 2) รองรับรูปแบบเก่าแบบ single dict ที่มี key Email/Password
        if not email or not password:
            email = creds.get("Email") or creds.get("username") or creds.get("email")
            password = creds.get("Password") or creds.get("password")
    except Exception:
        pass

    try:
        # ตรวจปุ่ม Connect LINE
        connect_selector = "button:has-text('Connect LINE'), button:has-text('Connect')"
        if await page.is_visible(connect_selector, timeout=3000):
            if progress_callback:
                progress_callback("ℹ️ พบปุ่ม Connect LINE กำลังคลิก...")
            await page.click(connect_selector)

        # กรณีมีปุ่มเข้าสู่ระบบด้วยบัญชีอื่น
        try:
            diff_selector = "div.login-with-different-account > a"
            if await page.is_visible(diff_selector, timeout=3000):
                await page.click(diff_selector)
        except PlaywrightTimeoutError:
            pass

        # หา input email/password
        email_selector = "input[placeholder*='Email' i], input[placeholder*='อีเมล']"
        pass_selector = "input[placeholder*='Password' i], input[placeholder*='รหัส']"

        if not await page.is_visible(email_selector, timeout=5000):
            if progress_callback:
                progress_callback("ℹ️ ไม่พบหน้าเข้าสู่ระบบ LINE อาจล็อกอินอยู่แล้ว")
            return True

        if not email or not password:
            if progress_callback:
                progress_callback("❌ ไม่มีข้อมูล Email/Password ใน line_data.json")
            return False

        await page.fill(email_selector, email)
        await page.fill(pass_selector, password)
        await page.click("button[type='submit'], button:has-text('Log in'), button:has-text('เข้าสู่ระบบ')")

        # รอจนฟอร์มหลุด/รีไดเรกต์กลับ
        try:
            await page.wait_for_selector("form", state="detached", timeout=30000)
        except PlaywrightTimeoutError:
            # บางครั้ง form ยังอยู่แต่มีการ redirect แล้ว ให้ผ่อนปรน
            pass

        if progress_callback:
            progress_callback("✅ ล็อกอิน LINE สำเร็จ (หรือไม่จำเป็น)")
        return True
    except Exception as e:
        if progress_callback:
            progress_callback(f"❌ เกิดข้อผิดพลาด LINE Login: {e}")
        return False
