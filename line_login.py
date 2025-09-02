from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
import asyncio
import re
from utils import load_line_credentials, load_user_profile_by_name

# =========================
# Small utils
# =========================
async def _is_visible(target, selector: str, timeout: int = 2000) -> bool:
    try:
        await target.wait_for_selector(selector, state="visible", timeout=timeout)
        return True
    except PlaywrightTimeoutError:
        return False
    except Exception:
        try:
            return await target.locator(selector).is_visible()
        except Exception:
            return False

async def _wait_for_page_ready(p: Page, timeout: int = 15000) -> None:
    # domcontentloaded + networkidle (best effort)
    try:
        await p.wait_for_load_state("domcontentloaded", timeout=timeout)
    except Exception:
        pass
    try:
        await p.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass

# =========================
# Booking navigation helpers (NEW)
# =========================
_BOOKING_URL = "https://popmartth.rocket-booking.app/booking"
_BOOKING_MARKER = "body > div > div.sc-715cd296-0.fYuIyy > div > div:nth-child(1) > a > p"

async def _click_booking_tab(page: Page) -> bool:
    """
    พยายาม 'กด' ปุ่ม/แท็บ Booking เพื่อกลับหน้า Booking (มากกว่าแค่ goto)
    """
    candidates = [
        "a[href*='/booking']",
        "a:has-text('Booking')",
        "a:has-text('จอง')",
        "a:has-text('จองคิว')",
        "button:has-text('Booking')",
        "button:has-text('จองคิว')",
        "a:has-text('หน้าจอง')",
    ]
    for sel in candidates:
        try:
            if await _is_visible(page, sel, 800):
                await page.click(sel)
                await _wait_for_page_ready(page, 10000)
                return True
        except Exception:
            continue
    return False

async def _ensure_booking_page(page: Page, timeout: int = 12000) -> bool:
    """
    พยายามให้กลับมา/อยู่ที่หน้า Booking โดย:
    1) รอ URL และ marker
    2) ถ้าไม่ใช่ ลองกดปุ่ม Booking
    3) ถ้ายังไม่ได้ ให้ goto() โดยตรง แล้วรอ marker
    """
    # 1) ถ้าอยู่หน้า booking อยู่แล้ว
    try:
        if ("rocket-booking.app" in (page.url or "")) and ("/booking" in (page.url or "")):
            try:
                await page.wait_for_selector(_BOOKING_MARKER, state="visible", timeout=min(3000, timeout))
            except Exception:
                pass
            return True
    except Exception:
        pass

    # 2) ลอง "กด" Booking tab ก่อน (user-like)
    try:
        clicked = await _click_booking_tab(page)
        if clicked:
            try:
                await page.wait_for_selector(_BOOKING_MARKER, state="visible", timeout=min(5000, timeout))
            except Exception:
                pass
            if ("rocket-booking.app" in (page.url or "")) and ("/booking" in (page.url or "")):
                return True
    except Exception:
        pass

    # 3) fallback goto
    try:
        await page.goto(_BOOKING_URL, wait_until="domcontentloaded")
        await _wait_for_page_ready(page, timeout)
        try:
            await page.wait_for_selector(_BOOKING_MARKER, state="visible", timeout=min(5000, timeout))
        except Exception:
            pass
        return ("rocket-booking.app" in (page.url or "")) and ("/booking" in (page.url or ""))
    except Exception:
        return False

async def _wait_for_booking_page(page: Page, timeout: int = 12000) -> bool:
    """
    (คงโครงเดิม) รอให้ redirect กลับ booking เร็วขึ้น
    ใช้ร่วมกับ _ensure_booking_page ได้
    """
    booking_sel = _BOOKING_MARKER
    try:
        # รอ URL
        try:
            pattern = re.compile(r".*rocket-booking\.app/booking.*")
            await page.wait_for_url(pattern, timeout=timeout)
            try:
                await page.wait_for_selector(booking_sel, state="visible", timeout=min(3000, timeout))
            except Exception:
                pass
            return True
        except Exception:
            pass

        # Polling
        deadline = asyncio.get_event_loop().time() + (timeout / 1000.0)
        while asyncio.get_event_loop().time() < deadline:
            try:
                try:
                    if await _is_visible(page, booking_sel, 600):
                        return True
                except Exception:
                    pass
                u = (page.url or "")
                if "rocket-booking.app" in u and "/booking" in u:
                    return True
                for p in page.context.pages:
                    uu = (p.url or "")
                    if "rocket-booking.app" in uu and "/booking" in uu:
                        return True
            except Exception:
                pass
            await asyncio.sleep(0.2)
    except Exception:
        pass
    return False

async def _is_booking_logged_in(page: Page) -> bool:
    try:
        markers = [
            "div.layout-header-profile",
        ]
        for sel in markers:
            try:
                if await _is_visible(page, sel, 800):
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False

# =========================
# Profile / form helpers
# =========================
async def _fill_profile_if_needed(page: Page, progress_callback=None) -> None:
    """
    กรอกฟอร์มโปรไฟล์ถ้าพบ แล้วกดต่อให้เข้า booking
    """
    try:
        # ตรวจว่ามีฟอร์มหรือไม่
        need = False
        for probe in ("#firstname", "#lastname", "#ID", "#tel"):
            try:
                if await _is_visible(page, probe, 1500):
                    need = True
                    break
            except Exception:
                continue
        if not need:
            return

        if progress_callback:
            progress_callback("ℹ️ พบฟอร์มโปรไฟล์ กำลังกรอกข้อมูล...")

        prof = load_user_profile_by_name(None) or {}
        firstname = str(prof.get("Firstname", "")).strip()
        lastname = str(prof.get("Lastname", "")).strip()
        idnum = str(prof.get("ID", "")).strip()
        phone = str(prof.get("Phone", "")).strip()

        # ชื่อ/นามสกุล
        if firstname:
            try:
                await page.fill("#firstname", firstname)
            except Exception:
                try:
                    await page.click("#firstname")
                    await page.keyboard.type(firstname)
                except Exception:
                    pass
        if lastname:
            try:
                await page.fill("#lastname", lastname)
            except Exception:
                try:
                    await page.click("#lastname")
                    await page.keyboard.type(lastname)
                except Exception:
                    pass

        # ประเภทบัตร
        id_label = None
        digits = "".join(ch for ch in idnum if ch.isdigit())
        if idnum:
            id_label = "บัตรประชาชน" if len(digits) >= 12 else "หนังสือเดินทาง"

        dropdown_candidates = [
            "body > div.sc-3d022901-0.kThiLE > div:nth-child(3) > div.sc-7d3b8656-0.hPTdmW > div.sc-48e8cede-3.iNSrMp > form > div > div:nth-child(5) > div",
            ".ant-select",
            "div[role='combobox']",
        ]
        opened = False
        for sel in dropdown_candidates:
            try:
                if await _is_visible(page, sel, 1000):
                    await page.click(sel)
                    await asyncio.sleep(0.2)
                    opened = True
                    break
            except Exception:
                continue

        if id_label and opened:
            option_sels = [
                f"div.ant-select-item-option:has-text('{id_label}')",
                f"div[role='option']:has-text('{id_label}')",
                f"span:has-text('{id_label}')",
            ]
            for osel in option_sels:
                try:
                    if await _is_visible(page, osel, 1000):
                        await page.click(osel)
                        break
                except Exception:
                    continue

        # ID / Phone
        if idnum:
            try:
                await page.fill("#ID", idnum)
            except Exception:
                try:
                    await page.click("#ID")
                    await page.keyboard.type(idnum)
                except Exception:
                    pass
        if phone:
            try:
                await page.fill("#tel", phone)
            except Exception:
                try:
                    await page.click("#tel")
                    await page.keyboard.type(phone)
                except Exception:
                    pass

        # checkbox
        checkbox_candidates = [
            "body > div.sc-3d022901-0.kThiLE > div:nth-child(3) > div.sc-7d3b8656-0.hPTdmW > div.sc-48e8cede-3.iNSrMp > form > div > div.sc-48e8cede-10.cRNIPZ > label > span.ant-checkbox.ant-wave-target.css-kghr11 > input",
            "form input[type='checkbox']",
            "input[type='checkbox']",
        ]
        for sel in checkbox_candidates:
            try:
                await page.check(sel)
                break
            except Exception:
                try:
                    await page.click(sel)
                    break
                except Exception:
                    continue

        # NEXT / ยืนยัน
        next_candidates = [
            "body > div.sc-3d022901-0.kThiLE > div:nth-child(3) > div.sc-7d3b8656-0.hPTdmW > div.sc-48e8cede-3.iNSrMp > form > button",
            "form button[type='submit']",
            "button:has-text('NEXT')",
            "button:has-text('Next')",
            "button:has-text('ถัดไป')",
            "button:has-text('ยืนยัน')",
        ]
        for sel in next_candidates:
            try:
                if await _is_visible(page, sel, 1200):
                    await page.click(sel)
                    await _wait_for_page_ready(page, 15000)
                    break
            except Exception:
                continue

        if progress_callback:
            progress_callback("✅ กรอกโปรไฟล์เรียบร้อย")
    except Exception:
        pass

async def _check_profile_completed(page: Page, progress_callback=None) -> bool:
    """
    แนวทางใหม่ตาม requirement:
    - คลิก 'โปรไฟล์' ถ้ากดได้
      - ถ้า 'ไม่มีปุ่ม LOGIN' → ถือว่าล็อกอินแล้ว → กลับหน้า Booking ทันที (click Booking tab)
      - ถ้า 'มีปุ่ม LOGIN' → return False (ปล่อยให้ perform_line_login จัดการต่อ)
    - ถ้าเจอองค์ประกอบโปรไฟล์ แปลว่าล็อกอินแล้ว → กลับหน้า Booking
    """
    try:
        # กดเปิดโปรไฟล์ถ้าทำได้
        triggers = [
            "a:has-text('โปรไฟล์')",
            "button:has-text('โปรไฟล์')",
            "a:has-text('Profile')",
            "button:has-text('Profile')",
        ]
        opened = False
        for sel in triggers:
            try:
                if await _is_visible(page, sel, 1200):
                    await page.click(sel)
                    await _wait_for_page_ready(page, 8000)
                    opened = True
                    break
            except Exception:
                continue

        # probes ที่บอกว่าอยู่หน้าโปรไฟล์
        probes = [
            "body > div > div.sc-396c748-0.fRdeIf > div.layouts-profile > div",
            "body > div > div.sc-396c748-0.fRdeIf > div.wrapper-setting-profile > div.content-setting-profile",
            "div.layout-header-profile",
        ]
        on_profile = False
        for pr in probes:
            try:
                if await _is_visible(page, pr, 800):
                    on_profile = True
                    break
            except Exception:
                pass

        # หา login button บนหน้าโปรไฟล์
        login_btns = [
            "button:has-text('LOGIN')",
            "button:has-text('Login')",
            "button:has-text('เข้าสู่ระบบ')",
        ]
        has_login_button = False
        for lb in login_btns:
            try:
                if await _is_visible(page, lb, 600):
                    has_login_button = True
                    break
            except Exception:
                pass

        # เงื่อนไขตาม requirement ข้อ 1
        if on_profile and not has_login_button:
            if progress_callback:
                progress_callback("ℹ️ อยู่หน้าโปรไฟล์และไม่มีปุ่ม LOGIN → กลับหน้า Booking")
            # กลับ Booking (กด tab ถ้าได้)
            await _ensure_booking_page(page, 10000)
            return True

        # ถ้าหน้าโปรไฟล์และ 'มี' ปุ่ม LOGIN → ยังไม่ล็อกอินเต็ม → ให้ perform_line_login จัดการ
        if on_profile and has_login_button:
            return False

        # ถ้าไม่ได้เปิดโปรไฟล์ได้ (เช่นไม่มีปุ่มให้กด) ให้พิจารณาว่าล็อกอินแล้วหรือยัง
        if await _is_booking_logged_in(page):
            # ล็อกอินอยู่แล้ว → ensure booking
            await _ensure_booking_page(page, 10000)
            return True

        return False
    except Exception:
        return False

# =========================
# LINE login main flow
# =========================
async def perform_line_login(page: Page, progress_callback=None, preferred_email: str | None = None) -> bool:
    """
    เดิน flow LINE login ตาม requirement ใหม่:
    - ถ้าโปรไฟล์ไม่มีปุ่ม LOGIN → กลับ Booking ทันที (ถือว่าพร้อมใช้งาน)
    - ถ้าโปรไฟล์มีปุ่ม LOGIN → คลิกให้ แล้วรองรับ Quick Login
    - หากต้องกรอก email/password และระบบ 'ไม่ต้องรอ OTP' ให้ไปต่อได้เลย
    - จบทุกกรณี บังคับกลับหน้า Booking
    """
    creds = load_line_credentials() or {}
    email = None
    password = None
    try:
        # รองรับ mapping หลายบัญชี
        if isinstance(creds, dict) and not any(k in creds for k in ("Email","email","username","Password","password")):
            if preferred_email and preferred_email in creds:
                email = preferred_email
                password = creds.get(preferred_email)
            elif len(creds) == 1:
                email, password = next(iter(creds.items()))
            elif len(creds) > 1:
                try:
                    first = sorted((k for k in creds.keys() if k), key=str.lower)[0]
                    email = first
                    password = creds.get(first)
                except Exception:
                    email = None
                    password = None
        # รองรับ single dict
        if (not email or not password) and isinstance(creds, dict):
            email = creds.get("Email") or creds.get("username") or creds.get("email")
            password = creds.get("Password") or creds.get("password")
    except Exception:
        pass

    try:
        # ขั้นแรก: เช็คหน้าโปรไฟล์ตาม requirement ข้อ 1
        already_ready = await _check_profile_completed(page, progress_callback)
        if already_ready:
            if progress_callback:
                progress_callback("✅ โปรไฟล์พร้อมใช้งาน (ไม่ต้องล็อกอินเพิ่ม)")
            # Ensure กลับ booking เสมอ
            await _ensure_booking_page(page, 10000)
            return True

        # ถ้าหน้าโปรไฟล์มีปุ่ม LOGIN → กดให้
        login_btns = [
            "button:has-text('LOGIN')",
            "button:has-text('Login')",
            "button:has-text('เข้าสู่ระบบ')",
        ]
        clicked_profile_login = False
        for lb in login_btns:
            try:
                if await _is_visible(page, lb, 1500):
                    if progress_callback:
                        progress_callback("ℹ️ พบปุ่ม LOGIN บนหน้าโปรไฟล์ กำลังกด...")
                    await page.click(lb)
                    await _wait_for_page_ready(page, 10000)
                    clicked_profile_login = True
                    break
            except Exception:
                continue

        # กรณีอยู่หน้า Booking และมีปุ่ม Connect LINE
        connect_selector = "button:has-text('Connect LINE'), button:has-text('Connect')"
        if await _is_visible(page, connect_selector, 3000):
            if progress_callback:
                progress_callback("ℹ️ พบปุ่ม Connect LINE กำลังกด...")
            await page.click(connect_selector)
            await _wait_for_page_ready(page, 15000)
            # ปุ่ม Connect LINE Account ชั้นถัดไป
            try:
                second_sel_list = [
                    "button:has-text('Connect LINE Account')",
                    "a:has-text('Connect LINE Account')",
                    "button:has-text('Connect Account')",
                    "a:has-text('Connect Account')",
                    "button:has-text('เชื่อมต่อบัญชี LINE')",
                    "a:has-text('เชื่อมต่อบัญชี LINE')",
                    "button:has-text('เชื่อมต่อบัญชี')",
                    "a:has-text('เชื่อมต่อบัญชี')",
                ]
                for _ in range(10):
                    for second_sel in second_sel_list:
                        if await _is_visible(page, second_sel, 600):
                            if progress_callback:
                                progress_callback("ℹ️ พบปุ่ม Connect LINE Account กำลังกด...")
                            await page.click(second_sel)
                            await _wait_for_page_ready(page, 10000)
                            raise StopIteration  # break both loops
                    await asyncio.sleep(0.3)
            except StopIteration:
                pass
            except Exception:
                pass

        # หาแท็บ/เฟรม line login
        login_page = None
        try:
            for p in page.context.pages:
                u = (p.url or "")
                if "line.me" in u or "access.line.me" in u:
                    login_page = p
                    break
        except Exception:
            login_page = None
        if not login_page:
            try:
                u0 = (page.url or "")
                if "line.me" in u0 or "access.line.me" in u0:
                    login_page = page
            except Exception:
                pass
        login_frame = None
        try:
            target = login_page or page
            for fr in target.frames:
                u = (fr.url or "")
                if "line.me" in u or "access.line.me" in u:
                    login_frame = fr
                    break
        except Exception:
            login_frame = None

        op = login_frame or login_page or page

        # Quick Login ปุ่มเดี่ยว (ไม่ต้องกรอก)
        try:
            quick_login_selectors = [
                "#app > div > div > div > div > div > div.LyContents01 > div > div.login-button > button",
                "div.login-button > button",
                "button:has-text('LOGIN')",
                "button:has-text('Login')",
                "button:has-text('เข้าสู่ระบบ')",
            ]
            for qsel in quick_login_selectors:
                try:
                    if await _is_visible(op, qsel, 1500):
                        if progress_callback:
                            progress_callback("ℹ️ พบปุ่ม Login แบบ Quick Login กำลังกด...")
                        await op.click(qsel)
                        await _wait_for_page_ready(login_page or page, 20000)
                        # รอรีไดเรกต์กลับ booking/กดยอมรับ consent
                        try:
                            consent_sel = ", ".join([
                                "button:has-text('Agree')",
                                "button:has-text('Allow')",
                                "button:has-text('ยอมรับ')",
                                "button:has-text('อนุญาต')",
                            ])
                            for _ in range(20):
                                if await _is_visible(login_page or page, consent_sel, 500):
                                    await (login_page or page).click(consent_sel)
                                    break
                                await asyncio.sleep(0.3)
                        except Exception:
                            pass
                        # กลับ booking + ตรวจโปรไฟล์
                        await _wait_for_booking_page(page, 12000)
                        await _fill_profile_if_needed(page, progress_callback)
                        try:
                            ok = await _check_profile_completed(page, progress_callback)
                            if ok and progress_callback:
                                progress_callback("✅ ยืนยันแล้ว: Login + โปรไฟล์พร้อมใช้งาน")
                        except Exception:
                            pass
                        # บังคับกลับ booking เสมอ
                        await _ensure_booking_page(page, 10000)
                        if progress_callback:
                            progress_callback("✅ ล็อกอิน LINE สำเร็จ (Quick Login)")
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        # ถ้าต้องกรอก email/password
        email_candidates = [
            "#app > div > div > div > div.MdBox01 > div > form > fieldset > div:nth-child(2) > input[type=text]",
            "input[type='email']",
            "input[name='tid']",
            "input[name='username']",
            "input[placeholder*='Email' i]",
            "input[placeholder*='อีเมล']",
        ]
        pass_candidates = [
            "#app > div > div > div > div.MdBox01 > div > form > fieldset > div:nth-child(3) > input[type=password]",
            "input[type='password']",
            "input[name='tpassword']",
            "input[name='password']",
            "input[placeholder*='Password' i]",
            "input[placeholder*='รหัส']",
        ]
        login_btn_candidates = [
            "#app > div > div > div > div.MdBox01 > div > form > fieldset > div.mdFormGroup01Btn > button",
            "button[type='submit']",
            "button:has-text('Log in')",
            "button:has-text('Login')",
            "button:has-text('Sign in')",
            "button:has-text('เข้าสู่ระบบ')",
        ]

        # toggle ไปหน้า email ถ้ายังไม่เห็นช่อง
        try:
            email_toggle_selectors = [
                "button:has-text('Log in with email')",
                "a:has-text('Log in with email')",
                "button:has-text('Email')",
                "a:has-text('Email')",
                "button:has-text('เข้าสู่ระบบด้วยอีเมล')",
                "a:has-text('เข้าสู่ระบบด้วยอีเมล')",
                "button:has-text('อีเมล')",
                "a:has-text('อีเมล')",
            ]
            probe_email = ", ".join([
                "input[type='email']",
                "input[name='tid']",
                "input[name='username']",
                "input[placeholder*='Email' i]",
                "input[placeholder*='อีเมล']",
            ])
            vis = False
            try:
                vis = await _is_visible(op, probe_email, 1500)
            except Exception:
                vis = False
            if not vis:
                for sel in email_toggle_selectors:
                    try:
                        if await _is_visible(op, sel, 800):
                            await op.click(sel)
                            break
                    except Exception:
                        pass
        except Exception:
            pass

        # หา input email
        email_sel = None
        for sel in email_candidates:
            try:
                if await _is_visible(op, sel, 2000):
                    email_sel = sel
                    break
            except Exception:
                pass
        if not email_sel:
            try:
                await op.wait_for_selector("input[type='email'], input[name='tid'], input[name='username']", timeout=15000)
                for sel in email_candidates:
                    if await _is_visible(op, sel, 1000):
                        email_sel = sel
                        break
            except Exception:
                email_sel = None

        if not email_sel:
            # อาจล็อกอินอยู่แล้ว / ไม่ต้องกรอก
            if progress_callback:
                progress_callback("ℹ️ ไม่พบหน้าเข้าสู่ระบบ LINE อาจล็อกอินอยู่แล้ว")
            try:
                await _check_profile_completed(page, progress_callback)
            except Exception:
                pass
            try:
                await _fill_profile_if_needed(page, progress_callback)
            except Exception:
                pass
            await _ensure_booking_page(page, 10000)
            return True

        # หา input password
        pass_sel = None
        for sel in pass_candidates:
            try:
                if await _is_visible(op, sel, 2000):
                    pass_sel = sel
                    break
            except Exception:
                pass

        if not (email and password):
            if progress_callback:
                progress_callback("❌ ไม่มี Email/Password ใน line_data.json")
            return False

        # กรอกข้อมูล
        try:
            await op.fill(email_sel, email)
        except Exception:
            await op.click(email_sel)
            await op.keyboard.type(email)

        if pass_sel:
            try:
                await op.fill(pass_sel, password)
            except Exception:
                await op.click(pass_sel)
                await op.keyboard.type(password)

        # กด Login
        clicked_login = False
        for sel in login_btn_candidates:
            try:
                if await _is_visible(op, sel, 800):
                    await op.click(sel)
                    clicked_login = True
                    break
            except Exception:
                pass
        if not clicked_login:
            try:
                await op.click(", ".join(login_btn_candidates))
            except Exception:
                pass

        base_page = login_page or page
        await _wait_for_page_ready(base_page, 20000)

        # กรณี "ไม่ต้องรอ OTP" → บางทีจะรีไดเรกต์กลับ booking เลย
        try:
            if await _is_booking_logged_in(page):
                await _fill_profile_if_needed(page, progress_callback)
                ok = await _check_profile_completed(page, progress_callback)
                if ok and progress_callback:
                    progress_callback("✅ ยืนยันแล้ว: Login + โปรไฟล์พร้อมใช้งาน")
                await _ensure_booking_page(page, 10000)
                if progress_callback:
                    progress_callback("✅ ล็อกอิน LINE สำเร็จ (redirect สำเร็จ/ไม่ต้อง OTP)")
                return True
        except Exception:
            pass

        # รอ OTP ถ้ามี แต่ยอมให้ออกได้เมื่อหายไป/รีไดเรกต์เสร็จ
        otp_box = "#app > div > div > div > div > div > div.MdMN06DigitCode > div.mdMN06CodeBox"
        otp_seen = False
        for _ in range(240):  # ~120s
            try:
                # ถ้ากลับ booking แล้ว หรือเห็น logged-in ก็พอ
                if await _is_booking_logged_in(page):
                    break

                if await _is_visible(op, otp_box, 500):
                    otp_seen = True
                    if progress_callback:
                        progress_callback("⌛ รอยืนยันตัวตนในมือถือ (LINE) ...")

                if otp_seen:
                    try:
                        if not await _is_visible(op, otp_box, 500):
                            break
                    except Exception:
                        break
            except Exception:
                break
            await asyncio.sleep(0.5)

        # ยืนยัน consent ถ้ามี
        try:
            consent_sel = ", ".join([
                "button:has-text('Agree')",
                "button:has-text('Allow')",
                "button:has-text('ยอมรับ')",
                "button:has-text('อนุญาต')",
            ])
            for _ in range(20):
                target = login_page or page
                try:
                    if await _is_visible(target, consent_sel, 500):
                        await target.click(consent_sel)
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.3)
        except Exception:
            pass

        # หลังรีไดเรกต์ กลับ booking + กรอกโปรไฟล์ถ้ามี
        try:
            await _wait_for_page_ready(page, 15000)
            await _fill_profile_if_needed(page, progress_callback)
            ok = await _check_profile_completed(page, progress_callback)
            if ok and progress_callback:
                progress_callback("✅ ยืนยันแล้ว: Login + โปรไฟล์พร้อมใช้งาน")
        except Exception:
            pass

        # สรุป: บังคับกลับหน้า Booking เสมอ ตามข้อกำหนดข้อ 4
        await _ensure_booking_page(page, 10000)

        if progress_callback:
            progress_callback("✅ ล็อกอิน LINE สำเร็จ (หรือไม่จำเป็น) และกลับหน้า Booking แล้ว")
        return True

    except Exception as e:
        if progress_callback:
            progress_callback(f"❌ เกิดข้อผิดพลาด LINE Login: {e}")
        # พยายามกลับหน้า Booking ให้ด้วยแม้พลาด
        try:
            await _ensure_booking_page(page, 8000)
        except Exception:
            pass
        return False
