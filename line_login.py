from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
import asyncio
import re
import time
from utils import load_line_credentials, load_user_profile_by_name

# =========================
# Small utils
# =========================
def _ts() -> str:
    try:
        return time.strftime('%H:%M:%S')
    except Exception:
        return ''

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

# Ultra-fast helpers for immediate reaction (no long waits)
async def _fast_first_locator(target, selectors, tries: int = 20, per_try_timeout: int = 100):
    """Return (selector, locator.first) preferring visible+enabled element.
    Scans quickly with tiny delays; returns None if not found within tries.
    """
    if not selectors:
        return None
    cand_list = selectors if isinstance(selectors, list) else [selectors]
    for _ in range(max(1, tries)):
        # pass 1: visible and enabled
        for sel in cand_list:
            try:
                loc = target.locator(sel)
                cnt = await loc.count()
                if cnt > 0:
                    item = loc.first
                    vis = False
                    en = True
                    try:
                        vis = await item.is_visible()
                    except Exception:
                        vis = False
                    try:
                        en = await item.is_enabled()
                    except Exception:
                        en = True
                    if vis and en:
                        return sel, item
            except Exception:
                continue
        # pass 2: any (fallback)
        for sel in cand_list:
            try:
                loc = target.locator(sel)
                if await loc.count() > 0:
                    return sel, loc.first
            except Exception:
                continue
        await asyncio.sleep(0.04)
    return None

async def _fast_click(target, selectors, scroll: bool = True) -> bool:
    found = await _fast_first_locator(target, selectors, tries=25, per_try_timeout=70)
    if not found:
        return False
    sel, loc = found
    try:
        if scroll:
            try:
                await loc.scroll_into_view_if_needed(timeout=250)
            except Exception:
                pass
        await loc.click(no_wait_after=True, timeout=650)
        return True
    except Exception:
        try:
            await loc.click(no_wait_after=True, timeout=650, force=True)
            return True
        except Exception:
            # JS fallback when DOM intercepts normal click
            try:
                await loc.evaluate("(el) => el.click()")
                return True
            except Exception:
                return False

async def _visible_selectors_quick(page: Page, selectors, each_timeout: int = 350, limit: int = 8) -> list[str]:
    """Return a short list of selectors that are visible right now (best-effort)."""
    out = []
    if not selectors:
        return out
    items = selectors if isinstance(selectors, list) else [selectors]
    for sel in items[: max(1, limit)]:
        try:
            if await _is_visible(page, sel, each_timeout):
                out.append(sel)
        except Exception:
            continue
    return out

async def _js_click_button_by_text(page: Page, exact_texts=None, contains_texts=None, tries: int = 16) -> bool:
    exact = exact_texts or []
    contains = contains_texts or []
    for _ in range(max(1, tries)):
        try:
            ok = await page.evaluate(
                "(exacts, contains) => {\n                  const btns = Array.from(document.querySelectorAll('button'));\n                  const norm = (s) => (s||'').trim();\n                  const findExact = () => {\n                    for (const t of (exacts||[])) {\n                      const b = btns.find(x => norm(x.innerText) === t);\n                      if (b) { b.click(); return true; }\n                    }\n                    return false;\n                  };\n                  const findContains = () => {\n                    for (const t of (contains||[])) {\n                      const b = btns.find(x => norm(x.innerText).includes(t));\n                      if (b) { b.click(); return true; }\n                    }\n                    return false;\n                  };\n                  return findExact() || findContains();\n                }",
                exact, contains
            )
            if ok:
                return True
        except Exception:
            pass
        await asyncio.sleep(0.05)
    return False

async def _await_line_login_target(base_page: Page, timeout_ms: int = 6000):
    """Wait briefly for any page/frame whose URL contains line.me/access.line.me.
    Returns (login_page, login_frame) where either may be None.
    """
    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    login_page = None
    login_frame = None
    while time.perf_counter() < deadline:
        try:
            for p in base_page.context.pages:
                u = (p.url or "").lower()
                if ("line.me" in u) or ("access.line.me" in u):
                    login_page = p
                    break
            if not login_page:
                u0 = (base_page.url or "").lower()
                if ("line.me" in u0) or ("access.line.me" in u0):
                    login_page = base_page
            if login_page:
                try:
                    for fr in login_page.frames:
                        u = (fr.url or "").lower()
                        if ("line.me" in u) or ("access.line.me" in u):
                            login_frame = fr
                            break
                except Exception:
                    login_frame = None
                break
        except Exception:
            pass
        await asyncio.sleep(0.1)
    return login_page, login_frame

async def _click_connect_on_profile(page: Page, progress_callback=None) -> bool:
    """Aggressively click the green Connect button in Profile area.
    Returns True if we believe click succeeded (overlay showed or LINE page/tab detected).
    """
    # 0) Fast path: use configured selectors directly (prioritize exact path)
    try:
        fast_list = UI_HELPERS.get("connect_line_buttons") or []
        for sel in fast_list[:4]:  # try first few deterministic selectors
            try:
                loc = page.locator(sel)
                if await loc.count() == 0:
                    continue
                btn = loc.first
                if progress_callback:
                    progress_callback(f"[{_ts()}] Click Connect via: {sel}")
                try:
                    await btn.scroll_into_view_if_needed(timeout=200)
                except Exception:
                    pass
                try:
                    await btn.click(timeout=700, no_wait_after=True)
                except Exception:
                    try:
                        await btn.click(timeout=700, force=True)
                    except Exception:
                        await btn.evaluate("(el)=>el.click()")
                # after first attempt, do not attempt second clicks; wait briefly for overlay
                try:
                    markers = (UI_HELPERS.get("connect_overlay_title_selectors") or []) + (UI_HELPERS.get("connect_overlay_candidates") or [])
                    if markers:
                        await page.wait_for_selector(", ".join(markers), timeout=1200)
                except Exception:
                    pass
                return True
            except Exception:
                continue
    except Exception:
        pass

    # 1) Try scoped exact-text within profile containers
    scopes = UI_HELPERS.get("profile_markers") or [
        "div.layout-header-profile",
        "div.wrapper-setting-profile",
        "div.layouts-profile",
    ]
    texts = UI_HELPERS.get("connect_line_texts") or ["Connect LINE", "Connect", "เชื่อมต่อ LINE", "เชื่อมต่อ"]
    overlay_list = UI_HELPERS.get("connect_overlay_candidates") or []

    # quick JS finder that prefers visible exact-text buttons
    try:
        ok = await page.evaluate(
            "(scopes, texts) => {\n"
            "  const isVisible = (el) => { if(!el) return false; const r=el.getBoundingClientRect(); const s=getComputedStyle(el); return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none'; };\n"
            "  const eq=(a,b)=> (a||'').trim()===(b||'').trim();\n"
            "  const roots=[]; for(const sel of (scopes||[])){ const c=document.querySelector(sel); if(c) roots.push(c);} if(!roots.length) roots.push(document);\n"
            "  for(const root of roots){ const nodes = Array.from(root.querySelectorAll('button,a'));\n"
            "    // pass 1: exact text\n"
            "    for(const n of nodes){ const t=(n.innerText||'').trim(); if(texts.some(tok=>eq(t,tok)) && isVisible(n)){ n.click(); return true; } }\n"
            "    // pass 2: green-ish button with 'Connect' substring\n"
            "    for(const n of nodes){ const t=(n.innerText||'').trim(); if(/connect/i.test(t)){ const s=getComputedStyle(n); if(isVisible(n) && (s.backgroundColor.includes('rgb(0, 174, 66)') || s.backgroundColor.includes('rgb(0,174,66)') || s.backgroundColor.includes('green'))){ n.click(); return true; } } }\n"
            "  }\n"
            "  return false;\n"
            "}",
            scopes,
            texts,
        )
        if ok:
            # quick post-click detection (overlay or line page) using Python-side checks
            for _ in range(20):
                try:
                    for p in page.context.pages:
                        u = (p.url or "").lower()
                        if ("line.me" in u) or ("access.line.me" in u):
                            return True
                    u0 = (page.url or "").lower()
                    if ("line.me" in u0) or ("access.line.me" in u0):
                        return True
                except Exception:
                    pass
                try:
                    if overlay_list:
                        for sel in overlay_list:
                            try:
                                if await page.is_visible(sel, timeout=150):
                                    return True
                            except Exception:
                                continue
                except Exception:
                    pass
                await asyncio.sleep(0.1)
            return True  # clicked but no indicator; still proceed
    except Exception:
        pass

    # 2) Fallback: Playwright locator ops with scroll/force
    try:
        loc = None
        for sel in [
            "button:has-text('Connect LINE')",
            "button:has-text('Connect')",
            "a:has-text('Connect LINE')",
            "a:has-text('Connect')",
        ]:
            try:
                tmp = page.locator(sel)
                if await tmp.count() > 0:
                    loc = tmp.first
                    break
            except Exception:
                continue
        if loc is not None:
            try:
                await loc.scroll_into_view_if_needed(timeout=400)
            except Exception:
                pass
            try:
                await loc.click(timeout=900, no_wait_after=True)
            except Exception:
                try:
                    await loc.click(timeout=900, force=True)
                except Exception:
                    try:
                        await loc.evaluate("(el)=>el.click()")
                    except Exception:
                        return False
            return True
    except Exception:
        pass
    return False

async def _click_overlay_connect_line_account(page: Page, progress_callback=None) -> bool:
    """When the bottom sheet 'Sign-in / Sign-up' appears, click 'Connect LINE Account*'.
    Returns True if a click was dispatched (best-effort)."""
    next_btns = UI_HELPERS.get("connect_line_next_buttons") or [
        "text=/\\bConnect\\s+LINE\\s+Account\\s*\\*?/i",
        "button:has-text('Connect LINE Account*')",
        "a:has-text('Connect LINE Account*')",
        "button:has-text('Connect LINE Account')",
        "a:has-text('Connect LINE Account')",
        "button:has-text('เชื่อมต่อบัญชี LINE')",
        "a:has-text('เชื่อมต่อบัญชี LINE')",
    ]
    overlays = UI_HELPERS.get("connect_overlay_candidates") or []
    titles = UI_HELPERS.get("connect_overlay_title_selectors") or []
    try:
        # Small wait for overlay markers
        for _ in range(20):  # ~2s
            visible_overlay = False
            for sel in (titles + overlays):
                try:
                    if await page.is_visible(sel, timeout=100):
                        visible_overlay = True
                        break
                except Exception:
                    continue
            if visible_overlay:
                break
            await asyncio.sleep(0.1)
        # Click next button within overlay scope if possible
        for _ in range(20):
            try:
                # Prefer scoping to the first visible overlay if provided
                scope = None
                for ov in overlays:
                    try:
                        loc = page.locator(ov)
                        if await loc.count() > 0 and await loc.first.is_visible():
                            scope = loc.first
                            break
                    except Exception:
                        continue
                for s in next_btns:
                    try:
                        loc = (scope.locator(s) if scope else page.locator(s))
                        if await loc.count() == 0:
                            continue
                        btn = loc.first
                        if progress_callback:
                            progress_callback(f"[{_ts()}] Click Overlay via: {s}")
                        try:
                            await btn.scroll_into_view_if_needed(timeout=200)
                        except Exception:
                            pass
                        try:
                            await btn.click(timeout=800, no_wait_after=True)
                        except Exception:
                            try:
                                await btn.click(timeout=800, force=True)
                            except Exception:
                                await btn.evaluate("(el)=>el.click()")
                        return True
                    except Exception:
                        continue
            except Exception:
                pass
            await asyncio.sleep(0.1)
    except Exception:
        pass
    return False

# =========================
# Booking navigation helpers (NEW)
# =========================
_BOOKING_URL = "https://popmartth.rocket-booking.app/booking"
_BOOKING_MARKER = "body > div > div.sc-715cd296-0.fYuIyy > div > div:nth-child(1) > a > p"
# API-provided UI helpers (rocketbooking.ui_helpers)
UI_HELPERS = {}

def set_ui_helpers(ui: dict | None):
    """Inject UI selectors from API (rocketbooking.ui_helpers)."""
    try:
        global UI_HELPERS, _BOOKING_URL, _BOOKING_MARKER
        if isinstance(ui, dict):
            UI_HELPERS = ui
            _BOOKING_URL = UI_HELPERS.get("booking_url") or _BOOKING_URL
            _BOOKING_MARKER = UI_HELPERS.get("booking_marker") or _BOOKING_MARKER
    except Exception:
        pass

async def _click_booking_tab(page: Page) -> bool:
    """
    พยายาม 'กด' ปุ่ม/แท็บ Booking เพื่อกลับหน้า Booking (มากกว่าแค่ goto)
    """
    candidates = UI_HELPERS.get("booking_tab_selectors") or [
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
        markers = UI_HELPERS.get("logged_in_markers") or [
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
        pf = UI_HELPERS.get("profile_form") or {}
        firstname_sel = pf.get("firstname") or "#firstname"
        lastname_sel = pf.get("lastname") or "#lastname"
        id_sel = pf.get("id") or "#ID"
        phone_sel = pf.get("phone") or "#tel"
        need = False
        for probe in (firstname_sel, lastname_sel, id_sel, phone_sel):
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
                await page.fill(firstname_sel, firstname)
            except Exception:
                try:
                    await page.click(firstname_sel)
                    await page.keyboard.type(firstname)
                except Exception:
                    pass
        if lastname:
            try:
                await page.fill(lastname_sel, lastname)
            except Exception:
                try:
                    await page.click(lastname_sel)
                    await page.keyboard.type(lastname)
                except Exception:
                    pass

        # ประเภทบัตร
        id_label = None
        digits = "".join(ch for ch in idnum if ch.isdigit())
        if idnum:
            id_label = "บัตรประชาชน" if len(digits) >= 12 else "หนังสือเดินทาง"

        dropdown_candidates = (pf.get("id_type_dropdown_candidates") if isinstance(pf.get("id_type_dropdown_candidates"), list) else None) or [
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
            opt_tpl = pf.get("id_type_options_template")
            option_sels = [opt_tpl.format(id_label)] if opt_tpl else [
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
                await page.fill(id_sel, idnum)
            except Exception:
                try:
                    await page.click(id_sel)
                    await page.keyboard.type(idnum)
                except Exception:
                    pass
        if phone:
            try:
                await page.fill(phone_sel, phone)
            except Exception:
                try:
                    await page.click(phone_sel)
                    await page.keyboard.type(phone)
                except Exception:
                    pass

        # checkbox
        checkbox_candidates = (pf.get("profile_checkbox_candidates") if isinstance(pf.get("profile_checkbox_candidates"), list) else None) or [
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
        next_candidates = (pf.get("profile_next_buttons") if isinstance(pf.get("profile_next_buttons"), list) else None) or [
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

async def _check_profile_completed(page: Page, progress_callback=None, fast: bool = False) -> bool:
    """
    ตรวจการล็อกอินตามเงื่อนไขใหม่:
    - ต้อง "กดเข้าโปรไฟล์" ก่อนเท่านั้น แล้วตรวจว่า
      1) เห็นรูปโปรไฟล์ (avatar)
      2) เห็นชื่อ-นามสกุล (fullname)
      3) มีปุ่มออกระบบ (Logout)
      4) "ไม่มี" ปุ่ม Connect/เชื่อมต่อ LINE
    ถ้าครบ → ถือว่า login แล้ว และจะกลับหน้า Booking ให้
    """
    try:
        # 1) เปิดหน้าโปรไฟล์เสมอ (JS-first แล้ว fallback เป็น trigger ที่ตั้งค่าไว้)
        # ปรับ timeout ตามโหมด
        base_vis = 300 if fast else 800
        base_prof = 400 if fast else 1000
        base_conn = 350 if fast else 600
        triggers = UI_HELPERS.get("profile_triggers") or [
            "a:has-text('โปรไฟล์')",
            "button:has-text('โปรไฟล์')",
            "a:has-text('Profile')",
            "button:has-text('Profile')",
        ]
        opened = False
        try:
            # Attempt to click profile image first
            ok = await page.evaluate("() => { const el = document.querySelector(\"img[alt='Profile']\"); if (el) { el.click(); return true; } return false; }")
            if ok:
                opened = True
        except Exception:
            pass
        if not opened:
            # Fallback to clicking profile text/button
            for sel in triggers:
                try:
                    if await _is_visible(page, sel, base_vis):
                        await page.click(sel, no_wait_after=True)
                        opened = True
                        break
                except Exception:
                    continue
        # If profile page is not opened after attempts, return False
        if not opened:
            return False

        # probes หน้าโปรไฟล์ (container หลัก)
        profile_markers = UI_HELPERS.get("profile_markers") or [
            "body > div > div.sc-396c748-0.fRdeIf > div.layouts-profile > div",
            "body > div > div.sc-396c748-0.fRdeIf > div.wrapper-setting-profile > div.content-setting-profile",
            "div.layout-header-profile",
        ]
        on_profile = False
        for pr in profile_markers:
            try:
                # Increased timeout for profile marker visibility
                if await _is_visible(page, pr, base_prof * 1.5):
                    on_profile = True
                    break
            except Exception:
                pass
        if not on_profile:
            return False
        # 2) ตรวจองค์ประกอบตามเงื่อนไข
        avatar_selectors = UI_HELPERS.get("profile_avatar") or [
            "img[alt='Profile']",
            "div.layout-header-profile img",
            "img.profile",
            "div.profile img",
        ]
        fullname_selectors = UI_HELPERS.get("profile_fullname") or [
            "div.profile-name",
            "div.layouts-profile h1",
            "div.wrapper-setting-profile h1",
            "span.profile-name",
        ]
        logout_buttons = UI_HELPERS.get("logout_buttons") or [
            "button:has-text('LOGOUT')",
            "button:has-text('Log out')",
            "button:has-text('Logout')",
            "a:has-text('Logout')",
            "button:has-text('ออกระบบ')",
            "a:has-text('ออกระบบ')",
            "button:has-text('ออกจากระบบ')",
            "a:has-text('ออกจากระบบ')",
        ]
        # NOTE: :has-text() ของ Playwright เป็นการ match แบบส่วนหนึ่งของสตริง
        # จึงอาจแมตช์ "Disconnect" ได้ถ้าใช้ 'Connect' เฉยๆ และยังอาจเจอ element ที่ hidden
        # เปลี่ยนมาเช็กด้วย JS แบบ exact-text + visible เท่านั้น (สอดคล้องกับ c_source)
        connect_exact_tokens = UI_HELPERS.get("connect_line_texts") or [
            "Connect LINE",
            "Connect",
            "เชื่อมต่อ LINE",
            "เชื่อมต่อ",
        ]
        # include visible prompts as "connect present" signals
        connect_prompt_selectors = UI_HELPERS.get("connect_prompt_selectors") or []
        async def any_visible(selectors, t=800):
            for s in selectors:
                try:
                    # Increased timeout for individual element visibility checks
                    if await _is_visible(page, s, t * 1.5):
                        return True
                except Exception:
                    continue
            return False
        has_avatar = await any_visible(avatar_selectors, base_prof)
        has_fullname = await any_visible(fullname_selectors, base_prof)
        has_logout = await any_visible(logout_buttons, base_prof)
        # ค้นหาเฉพาะปุ่ม/ลิงก์ที่ข้อความตรงกับ token และต้องมองเห็น (visible)
        try:
            has_connect = await page.evaluate(
                "(tokens, markerSelectors) => {\n"
                "  const isVisible = (el) => {\n"
                "    if (!el) return false;\n"
                "    const rect = el.getBoundingClientRect();\n"
                "    const style = window.getComputedStyle(el);\n"
                "    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';\n"
                "  };\n"
                "  const textEq = (a,b) => (a||'').trim() === (b||'').trim();\n"
                "  const containers = [];\n"
                "  for (const sel of (markerSelectors||[])) {\n"
                "    const c = document.querySelector(sel);\n"
                "    if (c) containers.push(c);\n"
                "  }\n"
                "  const roots = containers.length ? containers : [document];\n"
                "  for (const root of roots) {\n"
                "    const candidates = Array.from(root.querySelectorAll('button, a'));\n"
                "    for (const el of candidates) {\n"
                "      const t = (el.innerText || '').trim();\n"
                "      if (tokens.some(tok => textEq(t, tok)) && isVisible(el)) return true;\n"
                "    }\n"
                "  }\n"
                "  return false;\n"
                "}",
                connect_exact_tokens,
                UI_HELPERS.get("profile_markers") or [
                    "body > div > div.sc-396c748-0.fRdeIf > div.layouts-profile > div",
                    "body > div > div.sc-396c748-0.fRdeIf > div.wrapper-setting-profile > div.content-setting-profile",
                    "div.layout-header-profile",
                ],
            )
        except Exception:
            has_connect = False
        # treat prompts as connect present
        try:
            if not has_connect and connect_prompt_selectors:
                for ps in connect_prompt_selectors:
                    # Increased timeout for connect prompt visibility
                    if await _is_visible(page, ps, base_conn * 1.5):
                        has_connect = True
                        break
        except Exception:
            pass
        # Logged in if avatar, fullname, logout button are present AND connect button is NOT present
        if has_avatar and has_fullname and has_logout and not has_connect:
            if progress_callback:
                progress_callback("✅ ยืนยันการล็อกอินจากหน้าโปรไฟล์แล้ว")
            await _ensure_booking_page(page, 8000)
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
    # instrumentation timers
    _t = {"last": time.perf_counter(), "start": None}
    _t["start"] = _t["last"]
    _metrics: list[tuple[str, float]] = []
    open_marked = False

    def _mark(name: str):
        try:
            now = time.perf_counter()
            dt = now - _t["last"]
            _t["last"] = now
            _metrics.append((name, dt))
            if progress_callback:
                progress_callback(f"⏱️ {name}: {int(dt*1000)} ms")
        except Exception:
            pass

    def _summary():
        try:
            if not _metrics:
                return
            parts = [f"{k} {int(v*1000)}ms" for k,v in _metrics]
            if progress_callback:
                progress_callback("⏱️ Summary: " + ", ".join(parts))
        except Exception:
            pass

    # Fast-lane: ถ้าเห็นปุ่ม/ข้อความ Connect บนหน้าโปรไฟล์ ให้กดไป overlay ทันที
    try:
        prompt_sel = ", ".join(UI_HELPERS.get("connect_prompt_selectors") or [])
        has_prompt = False
        try:
            # Increase timeout for initial prompt visibility check
            has_prompt = bool(prompt_sel and await _is_visible(page, prompt_sel, 800))
        except Exception:
            has_prompt = False
        if has_prompt:
            if progress_callback:
                progress_callback(f"[{_ts()}] Fast-lane: Connect prompt visible -> clicking Connect")
            await _click_connect_on_profile(page, progress_callback)
            await _click_overlay_connect_line_account(page, progress_callback)
    except Exception:
        pass
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
        _mark("ProfileCheck")
        if already_ready:
            if progress_callback:
                progress_callback("✅ โปรไฟล์พร้อมใช้งาน (ไม่ต้องล็อกอินเพิ่ม)")
            # Ensure กลับ booking เสมอ
            await _ensure_booking_page(page, 10000)
            _mark("EnsureBooking")
            _summary()
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
                        vis = await _visible_selectors_quick(page, login_btns, 350)
                        progress_callback(f"[{_ts()}] Visible LOGIN buttons: {len(vis)} -> {vis}")
                    if progress_callback:
                        progress_callback("ℹ️ พบปุ่ม LOGIN บนหน้าโปรไฟล์ กำลังกด...")
                    await page.click(lb, no_wait_after=True)
                    try:
                        # Increased timeout for waiting for connect buttons/overlay after clicking login
                        await page.wait_for_selector(
                            ", ".join((UI_HELPERS.get("connect_line_buttons") or []) + (UI_HELPERS.get("connect_overlay_candidates") or [])),
                            timeout=3000
                        )
                    except Exception:
                        pass
                    clicked_profile_login = True
                    _mark("ProfileLoginButton")
                    break
            except Exception:
                continue

        # กรณีอยู่หน้า Booking และมีปุ่ม Connect LINE
        connect_selector = ", ".join(UI_HELPERS.get("connect_line_buttons") or [
            "button:has-text('Connect LINE')",
            "button:has-text('Connect')",
            "a:has-text('Connect LINE')",
            "a:has-text('Connect')",
            "button:has-text('เชื่อมต่อ LINE')",
            "a:has-text('เชื่อมต่อ LINE')",
        ])
        # Early exit: ถ้าตอนนี้โปรไฟล์พร้อมแล้ว ให้จบที่นี่เลย
        try:
            ok_now = await _check_profile_completed(page, fast=True)
            if ok_now:
                await _ensure_booking_page(page, 8000)
                return True
        except Exception:
            pass
        # ตรวจว่ามี Connect จริงไหม ด้วย exact-text + visible ก่อนจะ log/กด
        has_connect_btn = False
        pref = []
        try:
            has_connect_btn = await page.evaluate(
                "(tokens, markerSelectors) => {\n"
                "  const isVisible = (el) => {\n"
                "    if (!el) return false; const r=el.getBoundingClientRect(); const s=getComputedStyle(el);\n"
                "    return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none';\n"
                "  };\n"
                "  const eq=(a,b)=> (a||'').trim()===(b||'').trim();\n"
                "  const roots=[]; for(const sel of (markerSelectors||[])){ const c=document.querySelector(sel); if(c) roots.push(c);} if(!roots.length) roots.push(document);\n"
                "  for(const root of roots){ const nodes=Array.from(root.querySelectorAll('button,a')); for(const n of nodes){ const t=(n.innerText||'').trim(); if(tokens.some(tok=>eq(t,tok)) && isVisible(n)) return true; } }\n"
                "  return false;\n"
                "}",
                UI_HELPERS.get("connect_line_texts") or ["Connect LINE","Connect","เชื่อมต่อ LINE","เชื่อมต่อ"],
                UI_HELPERS.get("profile_markers") or [
                    "body > div > div.sc-396c748-0.fRdeIf > div.layouts-profile > div",
                    "body > div > div.sc-396c748-0.fRdeIf > div.wrapper-setting-profile > div.content-setting-profile",
                    "div.layout-header-profile",
                ],
            )
        except Exception:
            has_connect_btn = False
        if has_connect_btn:
            if progress_callback:
                vis = await _visible_selectors_quick(page, UI_HELPERS.get("connect_line_buttons") or [], 300)
                if vis:
                    progress_callback(f"[{_ts()}] Visible Connect buttons: {len(vis)} -> {vis}")
                progress_callback("ℹ️ พบปุ่ม Connect LINE กำลังกด...")
            # ทางลัดที่โฟกัส: พยายามคลิกปุ่ม Connect ในโปรไฟล์ทันทีแบบ aggressive
            clicked_connect = await _click_connect_on_profile(page, progress_callback)
            # หากยังไม่มั่นใจ เพิ่ม fallback ด้วยชุด selector เดิม (สั้นๆ)
            if not clicked_connect:
                pref = UI_HELPERS.get("connect_line_buttons") or [connect_selector]
                try:
                    pref = sorted(pref, key=lambda s: 0 if ("LINE" in s or "เชื่อมต่อ LINE" in s) else 1)
                except Exception:
                    pass
                if progress_callback:
                    progress_callback(f"[{_ts()}] Fallback fast-click: {pref[:3]}{'...' if len(pref)>3 else ''}")
                clicked_connect = await _fast_click(page, pref)
            # หลังคลิกพยายามจัดการ overlay ให้ไว
            if clicked_connect:
                # เสริม: รอ overlay โผล่ช่วงสั้น แล้วกด Connect LINE Account*
                for _ in range(25):  # ~2.5s window
                    ov_clicked = await _click_overlay_connect_line_account(page, progress_callback)
                    if ov_clicked:
                        break
                    # หากเจอ LINE ทันทีให้หลุดเลย
                    try:
                        for p in page.context.pages:
                            u = (p.url or "").lower()
                            if "line.me" in u or "access.line.me" in u:
                                raise StopIteration
                        u0 = (page.url or "").lower()
                        if "line.me" in u0 or "access.line.me" in u0:
                            raise StopIteration
                    except StopIteration:
                        break
                    await asyncio.sleep(0.1)
        if has_connect_btn and clicked_connect:
            # short wait for overlay to appear (do not block long)
            try:
                # Increased timeout for overlay appearance
                await page.wait_for_selector(
                    ", ".join(UI_HELPERS.get("connect_overlay_candidates") or []),
                    timeout=1500
                )
            except Exception:
                pass
            _mark("OpenConnect")

            # ปุ่ม Connect LINE Account ชั้นถัดไป: คลิกแบบ aggressive + รองรับตัวอักษร "*"
            try:
                # Candidates for the second-stage button and the overlay container
                second_sel_list = UI_HELPERS.get("connect_line_next_buttons") or [
                    "text=/Connect\\s+LINE\\s+Account\\s*\\*?/i",
                    "button:has-text('Connect LINE Account*')",
                    "a:has-text('Connect LINE Account*')",
                    "button:has-text('Connect LINE Account')",
                    "a:has-text('Connect LINE Account')",
                    "button:has-text('Connect Account')",
                    "a:has-text('Connect Account')",
                    "button:has-text('เชื่อมต่อบัญชี LINE')",
                    "a:has-text('เชื่อมต่อบัญชี LINE')",
                    "button:has-text('เชื่อมต่อบัญชี')",
                    "a:has-text('เชื่อมต่อบัญชี')",
                ]
                overlay_candidates = UI_HELPERS.get("connect_overlay_candidates") or [
                    "div.sc-7d3b8656-0.hPTdmW",
                    "div.sc-48e8cede-3.iNSrMp",
                    ".sc-48e8cede-5.goYoKf",
                    "body > div > div:nth-child(3) > div.sc-7d3b8656-0.hPTdmW"
                ]

                async def _detect_line_auth_fast() -> bool:
                    try:
                        # any page URL contains line.me
                        for p in page.context.pages:
                            u = (p.url or "").lower()
                            if "line.me" in u or "access.line.me" in u:
                                return True
                    except Exception:
                        pass
                    try:
                        target = page
                        # quick probes on same page/frame
                        probes = (UI_HELPERS.get("quick_login_buttons") or []) + (UI_HELPERS.get("email_probe") or [])
                        for sel in probes[:5]:
                            try:
                                await target.wait_for_selector(sel, state="visible", timeout=200)
                                return True
                            except Exception:
                                continue
                    except Exception:
                        pass
                    return False

                def _pick_overlay_sel() -> str | None:
                    for ov in overlay_candidates:
                        try:
                            # use short attached state before visible
                            if page.locator(ov).first:
                                # visibility check best effort
                                return ov if page.locator(ov).first else None
                        except Exception:
                            continue
                    return None

                # Ensure overlay is open; if it closes unintentionally, reopen by clicking Connect again
                for attempt in range(1, 9):
                    if await _detect_line_auth_fast():
                        break

                    overlay_sel = None
                    # wait for overlay with increased tries and timeout
                    for _ in range(15): # ~1.5s
                        try:
                            for cand in overlay_candidates:
                                try:
                                    if await page.is_visible(cand, timeout=150):
                                        overlay_sel = cand
                                        break
                                except Exception:
                                    continue
                            if overlay_sel:
                                break
                        except Exception:
                            pass
                        await asyncio.sleep(0.1)

                    # If overlay is not up, click Connect again to reopen
                    if not overlay_sel:
                        try:
                            if progress_callback:
                                progress_callback("ℹ️ กำลังเปิดหน้าต่างเชื่อมต่อ LINE อีกครั้ง...")
                            try:
                                await page.locator(connect_selector).first.scroll_into_view_if_needed(timeout=500)
                            except Exception:
                                pass
                            try:
                                await page.locator(connect_selector).first.click(timeout=1000)
                            except Exception:
                                await page.click(connect_selector, timeout=1200, force=True)
                            await _wait_for_page_ready(page, 2000)
                            continue
                        except Exception:
                            pass

                    # Click the Connect LINE Account button inside the overlay only
                    try:
                        ov = page.locator(overlay_sel)
                        clicked = False
                        for sel in second_sel_list:
                            try:
                                loc = ov.locator(sel)
                                cnt = await loc.count()
                            except Exception:
                                cnt = 0
                            if cnt == 0:
                                continue
                            for i in range(min(cnt, 2)):
                                try:
                                    btn = loc.nth(i)
                                    try:
                                        await btn.scroll_into_view_if_needed(timeout=400)
                                    except Exception:
                                        pass
                                    if progress_callback:
                                        progress_callback("ℹ️ พบปุ่ม Connect LINE Account กำลังกด...")
                                    try:
                                        await btn.click(timeout=1000)
                                    except Exception:
                                        await btn.click(timeout=1000, force=True)
                                    clicked = True
                                    break
                                except Exception:
                                    continue
                            if clicked:
                                break
                        # After clicking, check quickly for LINE auth
                        for _ in range(8):
                            if await _detect_line_auth_fast():
                                raise StopIteration
                            # If overlay vanished without auth, break to outer loop to reopen
                            try:
                                if not await page.is_visible(overlay_sel, timeout=200):
                                    break
                            except Exception:
                                break
                            await asyncio.sleep(0.15)
                    except Exception:
                        pass

                    # small backoff before re-attempt
                    await asyncio.sleep(0.2)
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
                    if not open_marked:
                        _mark("OpenLINELogin")
                        open_marked = True
                    break
        except Exception:
            login_page = None
        if not login_page:
            try:
                u0 = (page.url or "")
                if "line.me" in u0 or "access.line.me" in u0:
                    login_page = page
                    if not open_marked:
                        _mark("OpenLINELogin")
                        open_marked = True
            except Exception:
                pass
        login_frame = None
        try:
            target = login_page or page
            for fr in target.frames:
                u = (fr.url or "")
                if "line.me" in u or "access.line.me" in u:
                    login_frame = fr
                    if not open_marked:
                        _mark("OpenLINELogin")
                        open_marked = True
                    break
        except Exception:
            login_frame = None

        op = login_frame or login_page or page

        # Quick Login ปุ่มเดี่ยว (หน้า Continue as ... มีปุ่ม Log in สีเขียว)
        try:
            quick_login_selectors = UI_HELPERS.get("quick_login_buttons") or [
                "#app > div > div > div > div > div > div.LyContents01 > div > div.login-button > button",
                "div.login-button > button",
                "button:has-text('Log in')",
                "button:has-text('LOGIN')",
                "button:has-text('เข้าสู่ระบบ')",
            ]
            # เฉพาะเมื่ออยู่บนโดเมน line.me เท่านั้น
            u_now = (login_page.url if login_page else page.url) or ""
            if "line.me" in u_now or "access.line.me" in u_now:
                # ถ้าไม่เห็นช่อง email แต่เห็นปุ่ม Quick Login ให้กดเลย
                probe_quick = await _visible_selectors_quick(op, quick_login_selectors, 400) # Increased timeout
                if probe_quick and not (await _visible_selectors_quick(op, UI_HELPERS.get("email_probe") or [], 300)): # Increased timeout
                    if progress_callback:
                        progress_callback(f"[{_ts()}] QuickLogin: {probe_quick[:2]}{'...' if len(probe_quick)>2 else ''}")
                    clicked_q = await _fast_click(op, quick_login_selectors)
                    if clicked_q:
                        # brief wait for consent/redirect
                        try:
                            await (login_page or page).wait_for_selector(
                                ", ".join(UI_HELPERS.get("consent_buttons") or []),
                                timeout=2500 # Increased timeout
                            )
                        except Exception:
                            pass
                            # กดยอมรับถ้ามี
                            try:
                                consent_sel = ", ".join(UI_HELPERS.get("consent_buttons") or [])
                                for _ in range(18):
                                    if await _is_visible(login_page or page, consent_sel, 450):
                                        await (login_page or page).click(consent_sel)
                                        break
                                    await asyncio.sleep(0.25)
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
                            await _ensure_booking_page(page, 10000)
                            if progress_callback:
                                progress_callback("✅ ล็อกอิน LINE สำเร็จ (Quick Login)")
                            return True
        except Exception:
            pass

        # รองรับ "Login with different account" ก่อน (เช่นเคยล็อกอินไว้)
        try:
            await _fast_click(op, [
                "div.login-with-different-account a",
                "a:has-text('different account')",
                "a:has-text('บัญชีอื่น')",
                "button:has-text('different account')"
            ])
        except Exception:
            pass

        # ถ้าต้องกรอก email/password
        email_candidates = UI_HELPERS.get("email_fields") or [
            "#app > div > div > div > div.MdBox01 > div > form > fieldset > div:nth-child(2) > input[type=text]",
            "input[type='email']",
            "input[name='tid']",
            "input[name='username']",
            "input[placeholder*='Email' i]",
            "input[placeholder*='อีเมล']",
        ]
        pass_candidates = UI_HELPERS.get("password_fields") or [
            "#app > div > div > div > div.MdBox01 > div > form > fieldset > div:nth-child(3) > input[type=password]",
            "input[type='password']",
            "input[name='tpasswd']",
            "input[name='password']",
            "input[placeholder*='Password' i]",
            "input[placeholder*='รหัส']",
        ]
        login_btn_candidates = UI_HELPERS.get("submit_login_buttons") or [
            "#app > div > div > div > div.MdBox01 > div > form > fieldset > div.mdFormGroup01Btn > button",
            "button[type='submit']",
            "button:has-text('Log in')",
            "button:has-text('Login')",
            "button:has-text('Sign in')",
            "button:has-text('เข้าสู่ระบบ')",
        ]

        # toggle ไปหน้า email ถ้ายังไม่เห็นช่อง
        try:
            email_toggle_selectors = UI_HELPERS.get("email_toggle_selectors") or [
                "button:has-text('Log in with email')",
                "a:has-text('Log in with email')",
                "button:has-text('Email')",
                "a:has-text('Email')",
                "button:has-text('เข้าสู่ระบบด้วยอีเมล')",
                "a:has-text('เข้าสู่ระบบด้วยอีเมล')",
                "button:has-text('อีเมล')",
                "a:has-text('อีเมล')",
            ]
            probe_email = ", ".join(UI_HELPERS.get("email_probe") or [
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
        # Ultra-fast discovery of email field
        email_sel = None
        # Increased tries and per_try_timeout for initial email field discovery
        found_email = await _fast_first_locator(op, email_candidates, tries=20, per_try_timeout=150)
        if found_email:
            email_sel, _ = found_email
            if progress_callback:
                progress_callback(f"[{_ts()}] Using email selector: {email_sel}")
        else:
            # one more short probe for generic inputs
            generic = ["input[type='email']", "input[name='tid']", "input[name='username']"]
            found_email = await _fast_first_locator(op, generic, tries=15, per_try_timeout=120)
            if found_email:
                email_sel, _ = found_email
                if progress_callback:
                    progress_callback(f"[{_ts()}] Using email selector (generic): {email_sel}")

            if not email_sel:
                # ถ้าพบ login_page/เฟรมแล้ว รอช่อง email โผล่อีกนิดก่อนสรุป
                wait_reprobe = bool(login_page or login_frame)
            if wait_reprobe:
                for _ in range(20):  # ~2s
                    try:
                        vis = await _is_visible(op, ", ".join(UI_HELPERS.get("email_probe") or []), 150)
                        if vis:
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(0.1)
                # try find again
                found_email = await _fast_first_locator(op, email_candidates, tries=10, per_try_timeout=100)
                if found_email:
                    email_sel, _ = found_email
            if not email_sel:
                # ถ้าอยู่ที่โปรไฟล์และยังเห็น prompt/ปุ่ม Connect ให้พยายามเปิดใหม่อีกสั้นๆ
                try:
                    prompt_sel = ", ".join(UI_HELPERS.get("connect_prompt_selectors") or [])
                    if prompt_sel and await _is_visible(page, prompt_sel, 600): # Increased timeout
                        for _ in range(3): # Increased tries
                            await _click_connect_on_profile(page, progress_callback)
                            await asyncio.sleep(0.3) # Increased sleep
                            # re-detect line page quickly
                            try:
                                for p in page.context.pages:
                                    u = (p.url or "").lower()
                                    if "line.me" in u or "access.line.me" in u:
                                        login_page = p
                                        break
                                u0 = (page.url or "").lower()
                                if (not login_page) and ("line.me" in u0 or "access.line.me" in u0):
                                    login_page = page
                            except Exception:
                                pass
                            # try finding email again
                            found_email = await _fast_first_locator(op, email_candidates, tries=10, per_try_timeout=100) # Increased tries and timeout
                            if found_email:
                                email_sel, _ = found_email
                                break
                except Exception:
                    pass
            if not email_sel:
                # ก่อนสรุป ลอง Quick Login อีกรอบหากยังอยู่บน line.me
                try:
                    u_now = ((login_page.url if login_page else page.url) or "").lower()
                    if ("line.me" in u_now) or ("access.line.me" in u_now):
                        qsel = UI_HELPERS.get("quick_login_buttons") or [
                            "#app > div > div > div > div > div > div.LyContents01 > div > div.login-button > button",
                            "div.login-button > button",
                            "button:has-text('Log in')",
                        ]
                        visq = await _visible_selectors_quick(op, qsel, 400) # Increased timeout
                        if visq:
                            if progress_callback:
                                progress_callback(f"[{_ts()}] QuickLogin(late): {visq[:2]}{'...' if len(visq)>2 else ''}")
                            if await _fast_click(op, qsel):
                                await _wait_for_booking_page(page, 12000)
                                await _fill_profile_if_needed(page, progress_callback)
                                try:
                                    ok = await _check_profile_completed(page, progress_callback)
                                    if ok and progress_callback:
                                        progress_callback("✅ ยืนยันแล้ว: Login + โปรไฟล์พร้อมใช้งาน")
                                except Exception:
                                    pass
                                await _ensure_booking_page(page, 10000)
                                if progress_callback:
                                    progress_callback("✅ ล็อกอิน LINE สำเร็จ (Quick Login)")
                                return True
                except Exception:
                    pass
                # อาจล็อกอินอยู่แล้ว / ไม่ต้องกรอก
                # แต่ถ้ายังเห็น overlay/prompt อยู่ อย่าพึ่งสรุป กลับไปกด overlay อีกรอบสั้นๆ
                try:
                    prompt_sel = ", ".join((UI_HELPERS.get("connect_prompt_selectors") or []) + (UI_HELPERS.get("connect_overlay_candidates") or []) + (UI_HELPERS.get("connect_overlay_title_selectors") or []))
                    if prompt_sel and await _is_visible(page, prompt_sel, 600): # Increased timeout
                        if progress_callback:
                            progress_callback(f"[{_ts()}] Overlay still visible; trying Connect LINE Account again")
                        for _ in range(15): # Increased tries
                            ok2 = await _click_overlay_connect_line_account(page, progress_callback)
                            if ok2:
                                break
                            await asyncio.sleep(0.15) # Increased sleep
                        # re-check email field quickly
                        found_email = await _fast_first_locator(op, email_candidates, tries=10, per_try_timeout=100) # Increased tries and timeout
                        if found_email:
                            email_sel, _ = found_email
                except Exception:
                    pass
            if not email_sel:
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
                _mark("RedirectAndVerify")
                _summary()
                return True

        _mark("EmailFormReady")
        # หา input password
        # Ultra-fast discovery of password field
        pass_sel = None
        # Increased tries and per_try_timeout for password field discovery
        found_pass = await _fast_first_locator(op, pass_candidates, tries=18, per_try_timeout=150)
        if found_pass:
            pass_sel, _ = found_pass
            if progress_callback:
                progress_callback(f"[{_ts()}] Using password selector: {pass_sel}")

        if not (email and password):
            if progress_callback:
                progress_callback("❌ ไม่มี Email/Password ใน line_data.json")
            return False

        # กรอกข้อมูล + กระตุ้น change/input เพื่อให้ปุ่ม enable แน่ๆ
        try:
            await op.fill(email_sel, email)
        except Exception:
            await op.click(email_sel)
            await op.keyboard.type(email)
        # nudge events
        try:
            await op.locator(email_sel).press("Tab")
        except Exception:
            pass

        if pass_sel:
            try:
                await op.fill(pass_sel, password)
            except Exception:
                await op.click(pass_sel)
                await op.keyboard.type(password)
            # primary submit via Enter
            try:
                await op.locator(pass_sel).press("Enter")
                clicked_login = True
            except Exception:
                pass

        # กด Login (fallbacks หลายแบบ)
        clicked_login = False
        for sel in login_btn_candidates:
            try:
                if await _is_visible(op, sel, 1200): # Increased timeout
                    if progress_callback:
                        vis = await _visible_selectors_quick(op, login_btn_candidates, 400) # Increased timeout
                        progress_callback(f"[{_ts()}] Visible submit buttons: {len(vis)} -> {vis}")
                    await op.click(sel)
                    clicked_login = True
                    if progress_callback:
                        progress_callback(f"[{_ts()}] Click submit via: {sel}")
                    break
            except Exception:
                pass
        if not clicked_login:
            try:
                await op.click(", ".join(login_btn_candidates))
                clicked_login = True
                if progress_callback:
                    progress_callback(f"[{_ts()}] Click submit via join() candidates")
            except Exception:
                pass
        if not clicked_login:
            # JS requestSubmit ให้ฟอร์ม เพื่อข้ามกรณีปุ่มยัง disabled จากเหตุผลเล็กน้อย
            try:
                ok_submit = await op.evaluate("""
                    () => {
                      const f = document.querySelector('form');
                      if (f && typeof f.requestSubmit === 'function') { f.requestSubmit(); return true; }
                      const btns = Array.from(document.querySelectorAll('button[type=submit], button')).filter(b=>/log\s*in/i.test(b.innerText||''));
                      if (btns[0]) { btns[0].click(); return true; }
                    return false;
                    }
                """)
                clicked_login = bool(ok_submit)
                if progress_callback:
                    progress_callback(f"[{_ts()}] requestSubmit(): {clicked_login}")
            except Exception:
                pass
        # สุดท้าย: role-based exact text
        if not clicked_login:
            try:
                await op.get_by_role("button", name="Log in", exact=True).click(timeout=1200)
                clicked_login = True
                if progress_callback:
                    progress_callback(f"[{_ts()}] Click submit via role(button, 'Log in')")
            except Exception:
                pass
        _mark("SubmitLogin")

        base_page = login_page or page
        try:
            await base_page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass

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
                _mark("RedirectAndVerify")
                _summary()
                return True
        except Exception:
            pass

        # รอ OTP ถ้ามี แต่ยอมให้ออกได้เมื่อหายไป/รีไดเรกต์เสร็จ
        otp_box = UI_HELPERS.get("otp_box") or "#app > div > div > div > div > div > div.MdMN06DigitCode > div.mdMN06CodeBox"
        otp_seen = False
        otp_marked = False
        for _ in range(300):  # ~150s (Increased wait time for OTP)
            try:
                # ถ้ากลับ booking แล้ว หรือเห็น logged-in ก็พอ
                if await _is_booking_logged_in(page):
                    break

                if await _is_visible(op, otp_box, 750): # Increased timeout
                    otp_seen = True
                    if progress_callback:
                        progress_callback("⌛ รอยืนยันตัวตนในมือถือ (LINE) ...")
                    if not otp_marked:
                        _mark("OTPShown")
                        otp_marked = True

                if otp_seen:
                    try:
                        if not await _is_visible(op, otp_box, 750): # Increased timeout
                            break
                    except Exception:
                        break

                # Early exit: หากกดเข้าโปรไฟล์แล้วและตรงตามเงื่อนไข login ให้หยุดรอทันที
                try:
                    ok_profile = await _check_profile_completed(page, fast=True)
                    if ok_profile:
                        break
                except Exception:
                    pass
            except Exception:
                break
            await asyncio.sleep(0.5)

        # ยืนยัน consent ถ้ามี
        try:
            consent_sel = ", ".join(UI_HELPERS.get("consent_buttons") or [
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

        # หลังรีไดเรกต์ กลับ booking + ตรวจโปรไฟล์ก่อน แล้วค่อยกรอกถ้าจำเป็น (เพื่อลดเวลา)
        try:
            # light wait for booking/profile elements instead of full network idle
            try:
                await page.wait_for_selector(_BOOKING_MARKER, timeout=1500)
            except Exception:
                pass
            # กดเข้าโปรไฟล์แบบเร็วหลัง redirect (JS-first, 10 ครั้ง)
            try:
                for _ in range(10):
                    try:
                        clicked = await page.evaluate("() => { const a = document.querySelector(\"img[alt='Profile']\"); if(a){ a.click(); return true;} const b = Array.from(document.querySelectorAll('a,button')).find(x=>/^(โปรไฟล์|Profile)$/i.test((x.innerText||'').trim())); if(b){ b.click(); return true;} return false; }")
                        if clicked:
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(0.08)
            except Exception:
                pass
            ok = False
            try:
                ok = await _check_profile_completed(page, progress_callback, fast=True)
            except Exception:
                ok = False
            if not ok:
                await _fill_profile_if_needed(page, progress_callback)
                try:
                    ok = await _check_profile_completed(page, progress_callback, fast=True)
                except Exception:
                    ok = False
            if ok and progress_callback:
                progress_callback("✅ ยืนยันแล้ว: Login + โปรไฟล์พร้อมใช้งาน")
            _mark("RedirectAndVerify")
        except Exception:
            pass

        # สรุป: บังคับกลับหน้า Booking เสมอ ตามข้อกำหนดข้อ 4
        await _ensure_booking_page(page, 10000)

        if progress_callback:
            progress_callback("✅ ล็อกอิน LINE สำเร็จ (หรือไม่จำเป็น) และกลับหน้า Booking แล้ว")
        # verify again after redirect; if still show Connect, reopen overlay quickly
        try:
            for _ in range(10):
                ok2 = await _check_profile_completed(page, fast=True)
                if ok2:
                    break
                pr = ", ".join((UI_HELPERS.get("connect_prompt_selectors") or []) + (UI_HELPERS.get("connect_line_buttons") or []))
                try:
                    if pr and await _is_visible(page, pr, 400):
                        await _click_connect_on_profile(page, progress_callback)
                        await _click_overlay_connect_line_account(page, progress_callback)
                        # small give-back before next check
                        await asyncio.sleep(0.3)
                except Exception:
                    pass
        except Exception:
            pass
        _summary()
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
