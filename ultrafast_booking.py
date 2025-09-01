# ultrafast_booking.py
import asyncio
from playwright.async_api import async_playwright, Page
from minigame import solve_minigame

URLS = {
    "EZBOT": "https://popmart.ithitec.com/",
    "PMROCKET": "https://pmrocketbotautoq.web.app/"
}

def _normalize_trial_elements(raw: dict) -> dict:
    """
    ทำ normalize selectors ให้เหมือนแนวทางใน real_booking.py
    รองรับทั้ง payload แบบ flat และแบบมีชั้น pmrocket/ithitec
    """
    if not isinstance(raw, dict):
        return {}
    # เลือกชั้นในกรณีส่งมาหลายชั้น
    if isinstance(raw.get("pmrocket"), dict):
        web = dict(raw.get("pmrocket") or {})
    elif isinstance(raw.get("ithitec"), dict):
        web = dict(raw.get("ithitec") or {})
    else:
        web = dict(raw)

    try:
        if "date_button" not in web and web.get("calendar_day_button_prefix"):
            web["date_button"] = web["calendar_day_button_prefix"] + "{}" + ")"
        if "time_button" not in web and web.get("time_buttons_prefix"):
            web["time_button"] = web["time_buttons_prefix"] + "{}" + ")"
        if "branch_buttons_base" not in web:
            if web.get("branch_buttons"):
                web["branch_buttons_base"] = web["branch_buttons"]
            elif web.get("branch_list"):
                web["branch_buttons_base"] = web["branch_list"]
        if "next_button_after_branch" not in web and web.get("branch_next_button"):
            web["next_button_after_branch"] = web["branch_next_button"]
        if "confirm_selection_button" not in web and web.get("datetime_next_button"):
            web["confirm_selection_button"] = web["datetime_next_button"]
        if "confirm_booking_button" not in web and web.get("confirm_button"):
            web["confirm_booking_button"] = web["confirm_button"]
    except Exception:
        pass
    return web

async def solve_ezbot_spin(page: Page, log):
    try:
        # Prefer viewport element for pointer interactions
        vp_selector = "#captcha-viewport"
        spin_selector = "#captcha-spin"
        try:
            await page.wait_for_selector(vp_selector, timeout=5000)
            log("✅ พบ selector [ezbot_captcha_viewport]")
        except Exception:
            # fallback try spin
            await page.wait_for_selector(spin_selector, timeout=5000)
            vp_selector = spin_selector
            log("✅ พบ selector [ezbot_captcha_spin]")
        box = await page.locator(vp_selector).bounding_box()
        if not box:
            return False
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        # Try a few horizontal drags to align yaw near 0 degrees
        for dx in (360, 480, 540):
            try:
                await page.mouse.move(cx, cy)
                await page.mouse.down()
                await page.mouse.move(cx + dx, cy)
                await page.mouse.up()
                # Allow internal timer to trigger
                await page.wait_for_timeout(2300)
                # Check status/bar indicating success
                ok = await page.evaluate("""
                    () => {
                        const st = document.getElementById('captcha-status');
                        if (st && /ผ่าน|ถูกต้อง/i.test(st.textContent||'')) return true;
                        const bar = document.getElementById('captcha-bar');
                        if (bar){
                            const w = parseFloat((getComputedStyle(bar).width||'').replace('px',''));
                            const p = bar.style.width || '';
                            if (/^\\s*9\\d%/.test(p) || /100%/.test(p)) return true;
                        }
                        return false;
                    }
                """)
                if ok:
                    log("✅ มินิเกม (EZBOT) ผ่านแล้ว")
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False

async def inject_and_book_fast(page: Page, site_data: dict, site_name: str, branch: str, day: str, time: str, progress_callback=None):
    # ใช้ normalize ให้เหมือนโหมดจริง
    raw = next(iter(site_data.values()), {})
    web = _normalize_trial_elements(raw)
        
    def log(msg):
        if progress_callback:
            progress_callback(msg)

    async def wait_for_selector_logged(selector: str, name: str, timeout: int = 15000):
        def friendly(ok: bool):
            base = (name or "").split(":")[0]
            ok_map = {
                "register_button": "✅ Found Register",
                "branch_button": "✅ Found Branch",
                "branch_buttons_base": "✅ Found Branch",
                "next_button_after_branch": "✅ Found Next",
                "date_button": "✅ Found Date",
                "time_button": "✅ Found Time",
                "confirm_selection_button": "✅ Found Confirm",
                "checkbox": "✅ Found Checkbox",
                "confirm_booking_button": "✅ Found Confirm Booking",
            }
            fail_map = {
                "register_button": "❌ Not Found Register",
                "branch_button": "❌ Not Found Branch",
                "branch_buttons_base": "❌ Not Found Branch",
                "next_button_after_branch": "❌ Not Found Next",
                "date_button": "❌ Not Found Date",
                "time_button": "❌ Not Found Time",
                "confirm_selection_button": "❌ Not Found Confirm",
                "checkbox": "❌ Not Found Checkbox",
                "confirm_booking_button": "❌ Not Found Confirm Booking",
            }
            return ok_map.get(base) if ok else fail_map.get(base)
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            msg = friendly(True)
            if msg:
                log(msg)
            return True
        except Exception:
            msg = friendly(False)
            if msg:
                log(msg)
            raise

    log("🌐 เข้าสู่เว็บไซต์...")
    await page.goto(URLS[site_name], wait_until="networkidle")
    log("✅ เข้าหน้าเว็บไซต์เรียบร้อยแล้ว")

    await wait_for_selector_logged(web["register_button"], "register_button", 15000)
    await page.click(web["register_button"])
    log("✅ คลิกปุ่ม Register แล้ว")

    await wait_for_selector_logged(web["branch_buttons_base"], "branch_buttons_base", 10000)
    branch_container = web["branch_buttons_base"]
    branch_clicked = False
    # Try direct locator on buttons inside the container
    try:
        locator_selector = f"{branch_container} button:has-text('{branch}')"
        await wait_for_selector_logged(locator_selector, f"branch_button:{branch}", 8000)
        await page.click(locator_selector)
        branch_clicked = True
    except Exception:
        # Fallback to JS: search all buttons within the container(s)
        branch_clicked = await page.evaluate(f"""
            () => {{
                const containers = Array.from(document.querySelectorAll("{branch_container}"));
                for (const c of containers) {{
                    const buttons = Array.from(c.querySelectorAll("button, [role='button']"));
                    for (const btn of buttons) {{
                        const txt = (btn.innerText || btn.textContent || "").trim();
                        if (txt.includes("{branch}")) {{
                            btn.click();
                            return true;
                        }}
                    }}
                }}
                return false;
            }}
        """)
    if not branch_clicked:
        raise Exception(f"❌ ไม่พบสาขา '{branch}' บนหน้าเว็บ")
    log(f"✅ เลือกสาขา {branch} แล้ว")

    await wait_for_selector_logged(web["next_button_after_branch"], "next_button_after_branch", 8000)
    await page.click(web["next_button_after_branch"])
    log("✅ คลิก Next หลังเลือกสาขาแล้ว")

    # Handle potential minigame like in live booking
    try:
        log("🔎 กำลังตรวจสอบมินิเกม...")
        async def check_in_frame(fr):
            try:
                return await fr.evaluate("""
                    () => {
                        const isVisible = (el) => {
                            const style = getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity||'1') === 0) return false;
                            const r = el.getBoundingClientRect();
                            return r.width >= 40 && r.height >= 40;
                        };
                        const inViewportCenter = (r) => {
                            const cx = (window.innerWidth || 0) / 2;
                            const cy = (window.innerHeight || 0) / 2;
                            return (cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom);
                        };
                        // Known PMROCKET pattern
                        const pm = document.querySelector('#app canvas');
                        if (pm && isVisible(pm)) return true;
                        // EZBOT specific checks
                        try {
                            const step = document.getElementById('step-verify');
                            if (step && getComputedStyle(step).display !== 'none') return true;
                            const vpEl = document.querySelector('#captcha-viewport') || document.querySelector('#captcha-spin');
                            if (vpEl && isVisible(vpEl)) return true;
                        } catch (e) {}
                        // General canvas/WebGL (including shadow DOM)
                        const canvases = [];
                        const walk = (root) => {
                            try {
                                if (root && root.querySelectorAll) {
                                    root.querySelectorAll('canvas').forEach(c => canvases.push(c));
                                    root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) walk(el.shadowRoot); });
                                }
                            } catch(e) {}
                        };
                        walk(document);
                        for (const c of canvases) {
                            if (isVisible(c)) return true;
                            try {
                                if (c.getContext && (c.getContext('webgl') || c.getContext('webgl2') || c.getContext('experimental-webgl'))) return true;
                            } catch(e) {}
                        }
                        // Heuristic: visible iframe covering viewport center (common for EZBOT overlays)
                        try {
                            const iframes = Array.from(document.querySelectorAll('iframe'));
                            for (const f of iframes) {
                                const r = f.getBoundingClientRect();
                                if (isVisible(f) && r.width >= 100 && r.height >= 100 && inViewportCenter(r)) return true;
                            }
                        } catch (e) {}
                        // Heuristic: large modal/overlay elements
                        try {
                            const elems = Array.from(document.querySelectorAll('div,section,article'));
                            for (const el of elems) {
                                const r = el.getBoundingClientRect();
                                if (!r || r.width < 200 || r.height < 200) continue;
                                const txt = (el.id + ' ' + el.className).toLowerCase();
                                if (/captcha|overlay|modal|puzzle|game|challenge/.test(txt)) {
                                    if (isVisible(el) && inViewportCenter(r)) return true;
                                }
                            }
                        } catch (e) {}
                        // Status text hint
                        const st = document.querySelector('#status-text');
                        if (st && /มุมตรง|กดเมาส์ค้างไว้|angle|minigame|captcha/i.test(st.textContent||'')) return true;
                        return false;
                    }
                """)
            except Exception:
                return False
        found = await check_in_frame(page)
        if not found:
            for fr in page.frames:
                if fr == page.main_frame:
                    continue
                if await check_in_frame(fr):
                    found = True
                    break
        if not found:
            await page.wait_for_timeout(600)
            found = await check_in_frame(page)
        if found:
            log("✅ Found Mini-game")
            try:
                if site_name == "EZBOT":
                    solved = await solve_ezbot_spin(page, log)
                    if not solved:
                        log("⚠️ Mini-game solve did not succeed, continuing")
                else:
                    await solve_minigame(page)
            except Exception:
                pass
            # Wait for overlay/minigame to disappear before proceeding
            for _ in range(12):  # ~6-8 seconds total
                try:
                    still = await check_in_frame(page)
                except Exception:
                    still = False
                if not still:
                    break
                await page.wait_for_timeout(600)
            else:
                log("⚠️ มินิเกมอาจยังคงอยู่ แต่จะพยายามดำเนินการต่อ")
            await page.wait_for_timeout(300)
        else:
            log("ℹ️ No Mini-game")
    except Exception:
        pass

    # Build/select date selector with fallback (prefer text under container for PMROCKET)
    date_selector = None
    prefix = web.get("calendar_day_button_prefix")
    if prefix and "> button:nth-child(" in prefix:
        container = prefix.split(' > button:nth-child(')[0]
        date_selector = f"{container} button:has-text('{day}')"
    elif "date_button" in web and web["date_button"]:
        date_selector = web["date_button"].format(day)
    else:
        # Generic fallback used by EZBOT/ithitec
        date_selector = f"#calendar-grid button:has-text('{day}')"
    await wait_for_selector_logged(date_selector, "date_button", 20000)
    await page.click(date_selector)
    log(f"✅ เลือกวันที่ {day} แล้ว")

    # Build/select time selector with robust handling (prefer text under container for PMROCKET)
    time_selector = None
    tprefix = web.get("time_buttons_prefix")
    if tprefix and "> button:nth-child(" in tprefix:
        tcontainer = tprefix.split(' > button:nth-child(')[0]
        time_selector = f"{tcontainer} button:has-text('{time}')"
    elif "time_buttons_base_selector" in web and web["time_buttons_base_selector"]:
        time_selector = f"{web['time_buttons_base_selector']} >> text='{time}'"
    elif "time_button" in web and web["time_button"]:
        # Only use as last resort; attempt int index if applicable
        try:
            time_selector = web["time_button"].format(int(time))
        except Exception:
            time_selector = f"button:has-text('{time}')"
    else:
        # Fallback: any button with matching text
        time_selector = f"button:has-text('{time}')"
    await wait_for_selector_logged(time_selector, "time_button", 20000)
    await page.click(time_selector)
    log(f"✅ เลือกเวลา {time} แล้ว")

    await wait_for_selector_logged(web["confirm_selection_button"], "confirm_selection_button", 8000)
    await page.click(web["confirm_selection_button"])
    log("✅ ยืนยันวันและเวลาแล้ว")

    await wait_for_selector_logged(web["checkbox"], "checkbox", 8000)
    await page.check(web["checkbox"])
    log("✅ ติ๊ก Checkbox เรียบร้อย")

    await wait_for_selector_logged(web["confirm_booking_button"], "confirm_booking_button", 8000)
    await page.click(web["confirm_booking_button"])
    log("🎉 เสร็จสิ้นการจองเรียบร้อยแล้ว")

async def run_ultrafast_booking(browser_type, site_name, all_api_data, selected_branch_name, selected_day, selected_time, progress_callback=None):
    if site_name == "ROCKETBOOKING":
        site_data = all_api_data.get("rocketbooking", {})
    elif site_name == "EZBOT":
        site_data = {"ezbot": all_api_data.get("ithitec", {})}
    elif site_name == "PMROCKET":
        site_data = {"pmrocket": all_api_data.get("pmrocket", {})}
    else:
        raise Exception(f"❌ ยังไม่รองรับเว็บไซต์ {site_name} ในโหมด ultrafast")

    if not site_data or not next(iter(site_data.values()), {}):
        raise Exception(f"❌ ไม่พบข้อมูล config สำหรับ {site_name}")

    target_url = URLS.get(site_name)
    if not target_url:
        raise Exception(f"❌ ไม่มี URL สำหรับเว็บไซต์ {site_name}")

    async with async_playwright() as p:
        if browser_type == "Chrome":
            browser = await p.chromium.launch(channel="chrome", headless=False)
        elif browser_type == "Edge":
            browser = await p.chromium.launch(channel="msedge", headless=False)
        else:
            raise Exception(f"❌ ไม่รองรับเบราว์เซอร์ {browser_type}")

        context = await browser.new_context()
        page = await context.new_page()

        try:
            await inject_and_book_fast(
                page=page,
                site_data=site_data,
                site_name=site_name,
                branch=selected_branch_name,
                day=selected_day,
                time=selected_time,
                progress_callback=progress_callback
            )
        finally:
            await page.wait_for_timeout(5000)
            await browser.close()
