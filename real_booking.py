import asyncio
import time
from datetime import datetime
import requests
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError
from bot_check import solve_bot_challenge
from minigame import solve_minigame
from line_login import perform_line_login, set_ui_helpers

ROCKETBOOKING_URL = "https://popmartth.rocket-booking.app/booking"

# ---------- CDP attach helpers ----------
async def wait_for_cdp_endpoints(port: int = 9222, timeout: float = 20.0):
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout
    last_json = None
    while time.time() < deadline:
        try:
            resp = await asyncio.to_thread(requests.get, url, timeout=1)
            if resp.status_code == 200:
                try:
                    last_json = resp.json()
                except Exception:
                    last_json = None
                http_base = f"http://127.0.0.1:{port}"
                ws_url = None
                if isinstance(last_json, dict):
                    ws_url = last_json.get("webSocketDebuggerUrl") or last_json.get("websocketDebuggerUrl")
                if not ws_url:
                    ws_url = f"ws://127.0.0.1:{port}/devtools/browser"
                return http_base, ws_url
        except Exception:
            pass
        await asyncio.sleep(0.3)
    raise RuntimeError(f"CDP endpoint not available on port {port} after {timeout:.1f}s")

async def attach_to_chrome(port: int = 0, progress_callback=None):
    http_base, ws_url = await wait_for_cdp_endpoints(port)
    if progress_callback:
        progress_callback(f"🔌 พบ CDP endpoint บนพอร์ต {port} – กำลังเชื่อมต่อ...")
    playwright = await async_playwright().start()
    browser = None
    try:
        try:
            browser = await playwright.chromium.connect_over_cdp(http_base, timeout=8000)
        except Exception as e1:
            if progress_callback:
                progress_callback(f"⚠️ ต่อผ่าน HTTP endpoint ไม่สำเร็จ: {e1} – ลองผ่าน WS อีกครั้ง")
            browser = await playwright.chromium.connect_over_cdp(ws_url, timeout=8000)

        if browser.contexts:
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            context = await browser.new_context()
            page = await context.new_page()

        if progress_callback:
            progress_callback("✅ เชื่อมต่อ CDP สำเร็จ")
        return playwright, browser, context, page
    except Exception as e:
        try:
            await playwright.stop()
        except Exception:
            pass
        raise e

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
async def perform_real_booking(
    page: Page, all_api_data: dict,
    site_name: str, selected_branch: str, selected_day: str,
    selected_time: str, register_by_user: bool,
    confirm_by_user: bool, progress_callback=None,
    round_index: int | None = None,
    timer_seconds: float | None = None,
    delay_seconds: float | None = None,
    auto_line_login: bool | None = False,
    line_email: str | None = None,
    user_profile_name: str | None = None,
    enable_fallback: bool | None = False
):
    if site_name != "ROCKETBOOKING":
        if progress_callback:
            progress_callback(f"❌ โหมดใช้งานจริงรองรับแค่ ROCKETBOOKING แต่ได้รับ Site: {site_name}")
        return

    rb_data = all_api_data.get("rocketbooking", {}) or {}
    # mapping selectors (รองรับทั้งแบบ flat และ pmrocket)
    if isinstance(rb_data.get("pmrocket"), dict):
        web_elements = dict(rb_data.get("pmrocket") or {})
    else:
        web_elements = dict(rb_data)

    # ✅ ผูก ui_helpers ให้ line_login ใช้
    ui = (rb_data.get("ui_helpers") or {})
    try:
        set_ui_helpers(ui)
    except Exception:
        pass

    target_url = (rb_data.get("url") or web_elements.get("url") or ROCKETBOOKING_URL)

    if not web_elements:
        if progress_callback:
            progress_callback(f"❌ ไม่พบข้อมูลการตั้งค่าสำหรับ '{site_name}' กรุณาตรวจสอบไฟล์ config")
        return

    bot_elements = {}
    if isinstance(rb_data.get("bot_check"), dict):
        bot_elements = rb_data.get("bot_check")
    elif "bot_check" in rb_data:
        bot_elements = rb_data["bot_check"]

    if progress_callback:
        progress_callback(f"🚀 กำลังเข้าสู่เว็บไซต์ {site_name} และตรวจสอบบอท...")

    # ปรับ map คีย์ selector ให้ครอบคลุม payload เดิม
    try:
        if "date_button" not in web_elements and web_elements.get("calendar_day_button_prefix"):
            web_elements["date_button"] = web_elements["calendar_day_button_prefix"] + "{}" + ")"
        if "time_button" not in web_elements and web_elements.get("time_buttons_prefix"):
            web_elements["time_button"] = web_elements["time_buttons_prefix"] + "{}" + ")"
        if "branch_buttons_base" not in web_elements:
            if web_elements.get("branch_buttons"):
                web_elements["branch_buttons_base"] = web_elements["branch_buttons"]
            elif web_elements.get("branch_list"):
                web_elements["branch_buttons_base"] = web_elements["branch_list"]
        if "next_button_after_branch" not in web_elements and web_elements.get("branch_next_button"):
            web_elements["next_button_after_branch"] = web_elements["branch_next_button"]
        if "confirm_selection_button" not in web_elements and web_elements.get("datetime_next_button"):
            web_elements["confirm_selection_button"] = web_elements["datetime_next_button"]
        if "confirm_booking_button" not in web_elements and web_elements.get("confirm_button"):
            web_elements["confirm_booking_button"] = web_elements["confirm_button"]
    except Exception:
        pass

    await page.goto(target_url, wait_until="networkidle")

    # รีโหลดกรณีหน้าไม่สมบูรณ์
    try:
        logo_ok = await page.is_visible("img.logo", timeout=3000)
    except Exception:
        logo_ok = False
    if not logo_ok:
        try:
            await page.evaluate("() => setTimeout(() => window.location.reload(), 500)")
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass

    if not await solve_bot_challenge(page, bot_elements, progress_callback):
        return

    # --- auto LINE login (ถ้าเลือก) ---
    if auto_line_login:
        try:
            if progress_callback:
                progress_callback("👤 กำลังกดเมนูโปรไฟล์เพื่อเริ่มล็อกอิน LINE...")
            prof_selectors = [
                "button:has-text('Profile')",
                "a:has-text('Profile')",
                "button:has-text('โปรไฟล์')",
                "a:has-text('โปรไฟล์')",
                "button[aria-label*='profile' i]",
            ]
            clicked_profile = False
            for sel in prof_selectors:
                try:
                    if await page.is_visible(sel, timeout=1000):
                        await page.click(sel)
                        clicked_profile = True
                        break
                except Exception:
                    pass
            if not clicked_profile:
                try:
                    await page.click("button:has([class*='profile']), div:has-text('โปรไฟล์')", timeout=1000)
                except Exception:
                    pass

            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            try:
                connect_probe = ", ".join([
                    "button:has-text('Connect LINE')",
                    "button:has-text('Connect')",
                    "a:has-text('Connect LINE')",
                    "a:has-text('Connect')",
                    "button:has-text('เชื่อมต่อ LINE')",
                    "a:has-text('เชื่อมต่อ LINE')",
                ])
                for _ in range(10):
                    if await page.is_visible(connect_probe, timeout=1000):
                        break
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            ok = await perform_line_login(page, progress_callback, preferred_email=line_email)
            if ok and progress_callback:
                progress_callback("✅ ยืนยันสถานะ LINE: ล็อกอินแล้ว")
            if not ok:
                if progress_callback:
                    progress_callback("❌ ล็อกอิน LINE อัตโนมัติไม่สำเร็จ")
                return
        except Exception as _e:
            if progress_callback:
                progress_callback(f"❌ ล็อกอิน LINE ล้มเหลว: {_e}")
            return

    # แจ้งเตือนถ้าเห็น Connect LINE แต่ไม่ได้ติ๊ก auto
    try:
        connect_sel = ", ".join([
            "button:has-text('Connect LINE')",
            "button:has-text('Connect')",
            "a:has-text('Connect LINE')",
            "a:has-text('Connect')",
            "button:has-text('เชื่อมต่อ LINE')",
            "a:has-text('เชื่อมต่อ LINE')",
        ])
        need_login = await page.is_visible(connect_sel, timeout=2000)
    except Exception:
        need_login = False
    if (not auto_line_login) and need_login and progress_callback:
        progress_callback("ℹ️ ยังไม่ได้ล็อกอิน LINE (ติ๊ก 'ยืนยันการตรวจสอบ LINE' เพื่อให้ระบบล็อกอินให้อัตโนมัติ)")

    # --- ตรวจสอบปุ่ม Register และวันเวลาที่เปิด ---
    register_button_selector = web_elements.get("register_button")
    if not register_button_selector:
        if progress_callback:
            progress_callback("❌ ไม่พบ Selector ของปุ่ม Register")
        return

    if not await safe_wait_for_selector(page, register_button_selector, bot_elements, progress_callback):
        if progress_callback:
            progress_callback("❌ ไม่พบปุ่ม Register บนหน้าเว็บ อาจจะยังไม่ถึงเวลาจอง")
        return

    try:
        start = time.time()
        while True:
            style = await page.get_attribute(register_button_selector, "style")
            style = style or ""
            if "222, 222, 222" not in style.replace(" ", ""):
                break
            if timer_seconds and (time.time() - start) > float(timer_seconds):
                if progress_callback:
                    progress_callback("⏳ หมดเวลารอ Register Active ตาม Timer")
                break
            await asyncio.sleep(0.05)
    except Exception:
        pass

    if progress_callback:
        progress_callback("✅ พบปุ่ม Register แล้ว! กำลังตรวจสอบวันที่จอง...")

    # Optional: after Register becomes clickable, re-try opening branch container a few times
    if enable_fallback:
        try:
            branch_container = web_elements.get("branch_buttons_base") or web_elements.get("branch_list")
            if branch_container:
                for _ in range(4):
                    try:
                        await page.wait_for_selector(branch_container, state="visible", timeout=2000)
                        break
                    except Exception:
                        await safe_click(page, register_button_selector, bot_elements, progress_callback)
                        await asyncio.sleep(0.4)
        except Exception:
            pass

    try:
        open_date_selector = web_elements.get("open_date_container")
        open_date_text = await page.inner_text(open_date_selector, timeout=10000)
        booking_datetime_str = open_date_text.replace("Open: ", "").strip()
        booking_datetime = datetime.strptime(booking_datetime_str, "%Y-%m-%d %H:%M:%S")
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

    # --- ดำเนินการกด Register / หรือรอผู้ใช้ ---
    if register_by_user:
        if progress_callback:
            progress_callback("🚨 รอให้คุณกด Register เอง...")
    else:
        if not await safe_click(page, register_button_selector, bot_elements, progress_callback):
            return
        if progress_callback:
            progress_callback("✅ กดปุ่ม Register แล้ว!")

    # --- กรอกฟอร์มโปรไฟล์ (ถ้ามี) ---
    try:
        if await page.is_visible("input#firstname", timeout=3000):
            from utils import load_user_profile_by_name
            profile = load_user_profile_by_name(user_profile_name)
            if profile:
                if progress_callback:
                    progress_callback("⏳ กำลังกำหนดข้อมูลโปรไฟล์...")
                if profile.get("Firstname"):
                    await page.fill("input#firstname", str(profile.get("Firstname")))
                if profile.get("Lastname"):
                    await page.fill("input#lastname", str(profile.get("Lastname")))
                try:
                    if profile.get("Gender"):
                        await page.click("div.ant-select-selector")
                        await page.keyboard.press("Enter")
                except Exception:
                    pass
                if profile.get("ID"):
                    await page.fill("input#ID", str(profile.get("ID")))
                if profile.get("Phone"):
                    await page.fill("input#tel", str(profile.get("Phone")))
                try:
                    await page.dispatch_event("input[type='checkbox']", "click")
                except Exception:
                    pass
                try:
                    await page.get_by_text("Next", exact=True).click()
                except Exception:
                    pass
    except Exception:
        pass

    # --- เลือก Branch ---
    if progress_callback:
        progress_callback("⏳ กำลังเลือก Branch...")
    branch_buttons_base_selector = web_elements.get("branch_buttons_base")
    branch_found = False
    for _ in range(5):
        branch_selector = f"{branch_buttons_base_selector}:has-text('{selected_branch}')"
        if await page.is_visible(branch_selector):
            if delay_seconds:
                try:
                    await page.wait_for_timeout(int(float(delay_seconds) * 1000))
                except Exception:
                    pass
            if not await safe_click(page, branch_selector, bot_elements, progress_callback):
                # If cannot click target branch, try fallback to any clickable branch
                if enable_fallback:
                    try:
                        btns = page.locator(f"{branch_buttons_base_selector} button, {branch_buttons_base_selector} [role='button']")
                        cnt = await btns.count()
                        for i in range(cnt):
                            b = btns.nth(i)
                            try:
                                dis = await b.is_disabled()
                            except Exception:
                                dis = False
                            if not dis:
                                await b.click()
                                branch_found = True
                                if progress_callback:
                                    progress_callback("ℹ️ คลิกสาขาที่กำหนดไม่ได้ เลือกสาขาอื่นแทน")
                                break
                    except Exception:
                        pass
                    if branch_found:
                        break
                return
            if progress_callback:
                progress_callback(f"✅ เลือก Branch '{selected_branch}' แล้ว!")
            branch_found = True
            break
        else:
            if progress_callback:
                progress_callback("⚠️ Branch ยังไม่โหลด, กำลังลองใหม่...")
            await page.click("body")
            await asyncio.sleep(2)

    # Fallback: choose first clickable branch if enabled
    if (not branch_found) and enable_fallback:
        try:
            btns = page.locator(f"{branch_buttons_base_selector} button, {branch_buttons_base_selector} [role='button']")
            cnt = await btns.count()
            for i in range(cnt):
                b = btns.nth(i)
                try:
                    dis = await b.is_disabled()
                except Exception:
                    dis = False
                if not dis:
                    await b.click()
                    branch_found = True
                    if progress_callback:
                        progress_callback("ℹ️ เลือกสาขาแรกที่กดได้เป็นตัวแทน")
                    break
        except Exception:
            pass

    if not branch_found:
        if progress_callback:
            progress_callback("❌ ไม่สามารถเลือก Branch ได้! ยกเลิกการจอง...")
        return

    next_button_selector = web_elements.get("next_button_after_branch")
    if not await safe_click(page, next_button_selector, bot_elements, progress_callback):
        return

    # --- ตรวจ minigame/canvas ก่อนเลือกวัน ---
    try:
        if await page.is_visible("canvas", timeout=2000):
            if progress_callback:
                progress_callback("🎮 พบมินิเกม กำลังพยายามแก้...")
            await solve_minigame(page)
    except Exception:
        pass

    # --- เลือกวัน ---
    if progress_callback:
        progress_callback("⏳ กำลังเลือกวัน...")
    date_selector = web_elements.get("date_button").format(selected_day)
    if delay_seconds:
        try:
            await page.wait_for_timeout(int(float(delay_seconds) * 1000))
        except Exception:
            pass
    if not await safe_click(page, date_selector, bot_elements, progress_callback):
        if enable_fallback:
            try:
                container = web_elements.get("date_picker_container") or "#calendar-grid"
                await page.wait_for_selector(container, timeout=4000)
                loc = page.locator(f"{container} button:not([disabled])")
                if await loc.count() > 0:
                    await loc.first.click()
                    if progress_callback:
                        progress_callback("ℹ️ เลือกวันแรกที่กดได้เป็นตัวแทน")
                else:
                    return
            except Exception:
                return
    if progress_callback:
        progress_callback(f"✅ เลือกวันที่ {selected_day} แล้ว!")

    # --- เลือกเวลา ---
    if progress_callback:
        progress_callback("⏳ กำลังเลือกเวลา...")
    if round_index is not None:
        try:
            prefix = web_elements.get("time_buttons_prefix")
            if prefix and "> button:nth-child(" in prefix:
                container = prefix.split(" > button:nth-child(")[0]
            else:
                container = web_elements.get("time_buttons_base_selector") or web_elements.get("time_buttons_base")
            if container:
                await page.wait_for_selector(container, state="visible", timeout=15000)
                if delay_seconds:
                    try:
                        await page.wait_for_timeout(int(float(delay_seconds) * 1000))
                    except Exception:
                        pass
                buttons = page.locator(f"{container} button:not([class*='disabledTime'])")
                count = await buttons.count()
                idx = max(0, min(round_index, count - 1))
                await buttons.nth(idx).click()
                if progress_callback:
                    progress_callback(f"✅ เลือกเวลา (รอบที่ {idx+1}) แล้ว!")
            else:
                time_selector = web_elements.get("time_button").format(selected_time)
                if delay_seconds:
                    try:
                        await page.wait_for_timeout(int(float(delay_seconds) * 1000))
                    except Exception:
                        pass
                await page.click(time_selector)
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ เลือกเวลาแบบรอบไม่สำเร็จ: {e}")
            return
    else:
        time_selector = web_elements.get("time_button").format(selected_time)
        if delay_seconds:
            try:
                await page.wait_for_timeout(int(float(delay_seconds) * 1000))
            except Exception:
                pass
        if not await safe_click(page, time_selector, bot_elements, progress_callback):
            if enable_fallback:
                try:
                    container = web_elements.get("time_buttons_base_selector") or web_elements.get("time_buttons_base")
                    if container:
                        await page.wait_for_selector(container, state="visible", timeout=4000)
                        buttons = page.locator(f"{container} button:not([class*='disabledTime'])")
                        if await buttons.count() > 0:
                            await buttons.first.click()
                            if progress_callback:
                                progress_callback("ℹ️ เลือกเวลาที่กดได้รายการแรกเป็นตัวแทน")
                        else:
                            return
                    else:
                        return
                except Exception:
                    return
        if progress_callback:
            progress_callback(f"✅ เลือกเวลา {selected_time} แล้ว!")

    # --- ยืนยันช่วงวัน/เวลา ---
    datetime_next_button_selector = web_elements.get("confirm_selection_button")
    if not await safe_click(page, datetime_next_button_selector, bot_elements, progress_callback):
        return
    try:
        await page.evaluate("""
            () => {
              setTimeout(() => {
                const interval = setInterval(() => {
                  const container = document.querySelector('div.wholePage.datePicker');
                  if (!container) return;
                  const buttons = Array.from(container.querySelectorAll('button'))
                    .filter(b => /Confirm/i.test(b.textContent||''));
                  buttons.forEach(btn => btn.click());
                }, 80);
                setTimeout(() => clearInterval(interval), 2000);
              }, 180);
            }
        """)
    except Exception:
        pass

    # --- Checkbox + Confirm booking ---
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
        try:
            await page.evaluate("""
                () => {
                  setTimeout(() => {
                    const interval = setInterval(() => {
                      const container = document.querySelector('div.InfoPage') || document.body;
                      const buttons = Array.from(container.querySelectorAll('button'))
                        .filter(b => /Confirm/i.test(b.textContent||''));
                      buttons.forEach(btn => btn.click());
                    }, 120);
                    setTimeout(() => clearInterval(interval), 5000);
                  }, 300);
                }
            """)
        except Exception:
            pass
        if not await safe_click(page, confirm_booking_selector, bot_elements, progress_callback):
            return
        if progress_callback:
            progress_callback("✅ กด Confirm Booking แล้ว! เสร็จสิ้น")
