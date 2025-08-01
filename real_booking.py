import asyncio
import time
from datetime import datetime
import requests
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError
from bot_check import solve_bot_challenge

# URLs สำหรับโหมดใช้งานจริง
ROCKETBOOKING_URL = "https://popmartth.rocket-booking.app/booking"

# ---------- CDP attach helpers ----------
async def wait_for_cdp_endpoint(port: int = 9222, timeout: float = 20.0) -> str:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = await asyncio.to_thread(requests.get, url, timeout=1)
            if resp.status_code == 200:
                return f"http://127.0.0.1:{port}"
        except Exception:
            pass
        await asyncio.sleep(0.3)
    raise RuntimeError(f"CDP endpoint not available on port {port} after {timeout:.1f}s")


async def attach_to_chrome(port: int = 0):
    cdp_base = await wait_for_cdp_endpoint(port)
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(cdp_base)
        
        if browser.contexts:
            context = browser.contexts[0]
            if context.pages:
                page = context.pages[0]
            else:
                page = await context.new_page()
        else:
            context = await browser.new_context()
            page = await context.new_page()

        return playwright, browser, context, page
    except Exception:
        await playwright.stop()
        raise


# ---------- resilient interaction helpers ----------
async def safe_click(page: Page, selector: str, bot_elements: dict, progress_callback=None, retries=3):
    for attempt in range(1, retries + 1):
        try:
            await page.click(selector, timeout=10000)
            return True
        except PlaywrightTimeoutError:
            if progress_callback:
                progress_callback(f"⚠️ (Attempt {attempt}) ไม่พบ element '{selector}' – กำลังตรวจสอบบอท...")
            if not await solve_bot_challenge(page, bot_elements, progress_callback):
                return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"⚠️ (Attempt {attempt}) error คลิก '{selector}': {e} – ตรวจสอบบอท...")
            if not await solve_bot_challenge(page, bot_elements, progress_callback):
                return False
        await asyncio.sleep(0.5)
    if progress_callback:
        progress_callback(f"❌ ไม่สามารถคลิก '{selector}' ได้หลังลอง {retries} ครั้ง")
    return False


async def safe_wait_for_selector(page: Page, selector: str, bot_elements: dict, progress_callback=None, timeout=30000, retries=3):
    for attempt in range(1, retries + 1):
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            if progress_callback:
                progress_callback(f"⚠️ (Attempt {attempt}) Element '{selector}' ยังไม่แสดง – ตรวจสอบบอท...")
            if not await solve_bot_challenge(page, bot_elements, progress_callback):
                return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"⚠️ (Attempt {attempt}) error รอ '{selector}': {e} – ตรวจสอบบอท...")
            if not await solve_bot_challenge(page, bot_elements, progress_callback):
                return False
        await asyncio.sleep(0.5)
    if progress_callback:
        progress_callback(f"❌ ไม่สามารถรอ selector '{selector}' ได้หลังลอง {retries} ครั้ง")
    return False


# ---------- booking logic ----------
async def perform_real_booking(page: Page, all_api_data: dict,
                               site_name: str, selected_branch: str, selected_day: str,
                               selected_time: str, register_by_user: bool,
                               confirm_by_user: bool, progress_callback=None):
    
    if site_name != "ROCKETBOOKING":
        if progress_callback:
            progress_callback(f"❌ โหมดใช้งานจริงรองรับแค่ ROCKETBOOKING แต่ได้รับ Site: {site_name}")
        return
        
    web_elements = all_api_data.get("rocketbooking", {}).get("pmrocket", {})
    target_url = ROCKETBOOKING_URL
    
    if not web_elements:
        if progress_callback:
            progress_callback(f"❌ ไม่พบข้อมูลการตั้งค่าสำหรับ '{site_name}' กรุณาตรวจสอบไฟล์ config")
        return
    
    bot_elements = all_api_data.get("rocketbooking", {}).get("bot_check", {})

    if progress_callback:
        progress_callback(f"🚀 กำลังเข้าสู่เว็บไซต์ {site_name} และตรวจสอบบอท...")
    
    await page.goto(target_url, wait_until="networkidle")

    if not await solve_bot_challenge(page, bot_elements, progress_callback):
        return

    # --- โค้ดที่ถูกแก้ไขเพื่อย้ายการตรวจสอบปุ่ม Register มาไว้ด้านหน้า ---
    register_button_selector = web_elements.get("register_button")
    if not register_button_selector:
        if progress_callback:
            progress_callback("❌ ไม่พบ Selector ของปุ่ม Register")
        return

    # ตรวจสอบว่าปุ่ม Register ปรากฏขึ้นหรือไม่
    if not await safe_wait_for_selector(page, register_button_selector, bot_elements, progress_callback):
        if progress_callback:
            progress_callback("❌ ไม่พบปุ่ม Register บนหน้าเว็บ อาจจะยังไม่ถึงเวลาจอง")
        return
        
    # เมื่อเจอปุ่ม Register แล้วจึงตรวจสอบวันที่จอง
    if progress_callback:
        progress_callback("✅ พบปุ่ม Register แล้ว! กำลังตรวจสอบวันที่จอง...")

    try:
        open_date_selector = web_elements.get("open_date_container")
        open_date_text = await page.inner_text(open_date_selector, timeout=10000)
        booking_datetime_str = open_date_text.replace("Open: ", "").strip()
        booking_datetime = datetime.strptime(booking_datetime_str, '%Y-%m-%d %H:%M:%S')

        if booking_datetime < datetime.now():
            if progress_callback:
                progress_callback(f"เจอปุ่ม Register นะ แต่วันนี้ไม่ใช่วัน Booking ({booking_datetime_str})!")
            return

        if progress_callback:
            progress_callback(f"✅ วันที่จองถูกต้อง: {booking_datetime_str}")
    except Exception as e:
        if progress_callback:
            progress_callback(f"เจอปุ่ม Register นะ แต่วันนี้ไม่ใช่วัน Booking! (ข้อผิดพลาดในการตรวจสอบวันที่: {e})")
        return
    # --- สิ้นสุดส่วนที่แก้ไข ---


    # ... (ส่วนที่เหลือของกระบวนการจองยังคงเหมือนเดิม) ...

    if register_by_user:
        if progress_callback:
            progress_callback("🚨 รอให้คุณกด Register เอง...")
    else:
        if not await safe_click(page, register_button_selector, bot_elements, progress_callback):
            return
        if progress_callback:
            progress_callback("✅ กดปุ่ม Register แล้ว!")

    if progress_callback:
        progress_callback("⏳ กำลังเลือก Branch...")
    branch_buttons_base_selector = web_elements.get("branch_buttons_base")
    branch_found = False
    for _ in range(5):
        branch_selector = f"{branch_buttons_base_selector}:has-text('{selected_branch}')"
        if await page.is_visible(branch_selector):
            if not await safe_click(page, branch_selector, bot_elements, progress_callback):
                return
            if progress_callback:
                progress_callback(f"✅ เลือก Branch '{selected_branch}' แล้ว!")
            branch_found = True
            break
        else:
            if progress_callback:
                progress_callback("⚠️ Branch ยังไม่โหลด, กำลังลองใหม่...")
            await page.click('body')
            await asyncio.sleep(2)

    if not branch_found:
        if progress_callback:
            progress_callback("❌ ไม่สามารถเลือก Branch ได้! ยกเลิกการจอง...")
        return

    next_button_selector = web_elements.get("next_button_after_branch")
    if not await safe_click(page, next_button_selector, bot_elements, progress_callback):
        return

    if progress_callback:
        progress_callback("⏳ กำลังเลือกวัน...")
    date_selector = web_elements.get("date_button").format(selected_day)
    if not await safe_click(page, date_selector, bot_elements, progress_callback):
        return
    if progress_callback:
        progress_callback(f"✅ เลือกวันที่ {selected_day} แล้ว!")

    if progress_callback:
        progress_callback("⏳ กำลังเลือกเวลา...")
    time_selector = web_elements.get("time_button").format(selected_time)
    if not await safe_click(page, time_selector, bot_elements, progress_callback):
        return
    if progress_callback:
        progress_callback(f"✅ เลือกเวลา {selected_time} แล้ว!")

    datetime_next_button_selector = web_elements.get("confirm_selection_button")
    if not await safe_click(page, datetime_next_button_selector, bot_elements, progress_callback):
        return

    if progress_callback:
        progress_callback("⏳ กำลังติ๊ก Checkbox...")
    checkbox_selector = web_elements.get("checkbox")
    if not await safe_wait_for_selector(page, checkbox_selector, bot_elements, progress_callback):
        return
    await page.check(checkbox_selector)
    if progress_callback:
        progress_callback("✅ ติ๊ก Checkbox แล้ว!")

    confirm_booking_selector = web_elements.get("confirm_booking_button")
    if confirm_by_user:
        if progress_callback:
            progress_callback("🚨 รอให้คุณกด Confirm Booking ด้วยตัวเอง...")
    else:
        if not await safe_click(page, confirm_booking_selector, bot_elements, progress_callback):
            return
        if progress_callback:
            progress_callback("✅ กด Confirm Booking แล้ว! เสร็จสิ้น")