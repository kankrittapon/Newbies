#playwright_ops.py
import asyncio
from playwright.async_api import async_playwright, Page
import json
import os

# URLs สำหรับแต่ละ Site
PMROCKET_URL = "https://pmrocketbotautoq.web.app/"
EZBOT_URL = "https://popmart.ithitec.com/"

# ตัวแปร global สำหรับเก็บ browser object เพื่อป้องกันการปิดอัตโนมัติ
# ใช้ dict เพื่อเก็บหลาย browsers ถ้าต้องการ (เช่น สำหรับแต่ละ profile)
active_browsers = {}

# ฟังก์ชันสำหรับดึงข้อมูลเฉพาะสำหรับแต่ละ Site (web_elements)
def get_site_elements_config(site_name, all_api_data):
    """
    ดึงข้อมูล web_elements สำหรับ site นั้นๆ
    """
    try:
        if site_name == "PMROCKET":
            if 'pmrocket' in all_api_data and isinstance(all_api_data['pmrocket'], dict):
                return all_api_data['pmrocket']
            print(f"Warning: 'pmrocket' data not found or not in expected format in API data.")
            return {}
        elif site_name == "EZBOT":
            if 'ithitec' in all_api_data and isinstance(all_api_data['ithitec'], dict):
                return all_api_data['ithitec']
            print(f"Warning: 'ithitec' data not found or not in expected format in API data.")
            return {}
        return {}
    except Exception as e:
        print(f"An unexpected error occurred in get_site_elements_config for {site_name}: {e}")
        return {}


async def launch_browser_and_perform_booking(browser_type: str, site_name: str, 
                                             all_api_data: dict, 
                                             selected_branch_name: str, selected_day: str, selected_time_value: str,
                                             *, # บังคับให้ progress_callback เป็น keyword argument
                                             progress_callback=None):
    """
    เปิดเบราว์เซอร์และดำเนินการ Booking Process
    :param browser_type: "Chrome" หรือ "Edge"
    :param site_name: "PMROCKET" หรือ "EZBOT"
    :param all_api_data: ข้อมูล API ทั้งหมดที่โหลดมา (รวมถึง branchs.json, times.json และ element info)
    :param selected_branch_name: ชื่อ Branch ที่เลือกจาก GUI
    :param selected_day: วันที่เลือกจาก GUI (ตัวเลข 1-31)
    :param selected_time_value: ค่าเวลาที่เลือกจาก GUI
    :param progress_callback: ฟังก์ชันสำหรับอัปเดตสถานะ (ถ้ามี)
    """
    # Key สำหรับเก็บ browser ใน active_browsers dict
    browser_key = f"{site_name}-{browser_type}-{selected_branch_name}-{selected_day}-{selected_time_value}"

    # ถ้า browser นี้ถูกเปิดอยู่แล้ว ให้กลับไปใช้งาน instance เดิม
    if browser_key in active_browsers:
        if progress_callback:
            progress_callback(f"ℹ️ Browser สำหรับการจองนี้เปิดอยู่แล้ว.")
        return # ไม่ต้องทำอะไรเพิ่ม

    web_elements = get_site_elements_config(site_name, all_api_data) 
    
    branches_data = all_api_data.get("branchs", [])
    times_data = all_api_data.get("times", [])

    browser_launch_options = {
        "headless": False,
        "args": ["--start-maximized"]
    }

    target_url = ""
    if site_name == "PMROCKET":
        try:
            target_url = (all_api_data.get("pmrocket", {}) or {}).get("url") or PMROCKET_URL
        except Exception:
            target_url = PMROCKET_URL
    elif site_name == "EZBOT":
        try:
            target_url = (all_api_data.get("ithitec", {}) or {}).get("url") or EZBOT_URL
        except Exception:
            target_url = EZBOT_URL
    else:
        print("Invalid site name specified.")
        return

    if not web_elements:
        print(f"No web elements found for {site_name}. Booking process cannot continue.")
        if progress_callback:
            progress_callback(f"❌ Error: No web elements found for {site_name}.")
        return

    try:
        # ไม่ใช้ async with เพื่อป้องกัน Playwright ปิด browser อัตโนมัติ
        p = await async_playwright().start() 
        
        print(f"Launching {browser_type} for {site_name} at {target_url}")
        if progress_callback:
            progress_callback(f"🚀 กำลังเปิด {browser_type} สำหรับ {site_name}...")

        browser = None
        if browser_type == "Chrome":
            # Use system-installed Google Chrome to avoid downloading Playwright's Chromium
            browser = await p.chromium.launch(channel="chrome", **browser_launch_options)
        elif browser_type == "Edge":
            browser = await p.chromium.launch(channel="msedge", **browser_launch_options)
        
        # เก็บ browser object ไว้ใน active_browsers
        active_browsers[browser_key] = browser

        page = await browser.new_page()
        await page.goto(target_url)

        if progress_callback:
            progress_callback(f"🌐 ไปยังหน้า {target_url}...")

        print("Starting booking process...")

        # 1. รอจนกว่าปุ่ม Register จะขึ้น
        register_button_selector = web_elements.get("register_button")
        if register_button_selector:
            if progress_callback:
                progress_callback("⏳ กำลังรอปุ่ม Register...")
            await page.wait_for_selector(register_button_selector, state="visible", timeout=30000)
            await page.click(register_button_selector)
            print("Clicked Register button.")
            if progress_callback:
                progress_callback("✅ คลิกปุ่ม Register แล้ว.")
        else:
            print("Register button selector not found in element data.")
            if progress_callback:
                progress_callback("❌ Error: ไม่พบ Selector ปุ่ม Register.")
            return 

        # 2. เลือก Branch
        branch_buttons_base_selector = web_elements.get("branch_buttons")
        selected_branch_value = None
        for b in branches_data:
            if isinstance(b, dict) and b.get("name") == selected_branch_name:
                selected_branch_value = b.get("value")
                break
            elif isinstance(b, str) and b == selected_branch_name:
                selected_branch_value = b 
                break
        
        if branch_buttons_base_selector and selected_branch_value:
            if progress_callback:
                progress_callback(f"⏳ กำลังเลือก Branch: {selected_branch_name}...")
            branch_to_click_selector = f"{branch_buttons_base_selector} >> text='{selected_branch_name}'" 
            try:
                await page.wait_for_selector(branch_to_click_selector, state="visible", timeout=10000)
                await page.click(branch_to_click_selector)
                print(f"Selected Branch: {selected_branch_name}.")
                if progress_callback:
                    progress_callback(f"✅ เลือก Branch {selected_branch_name} แล้ว.")
            except Exception as e:
                print(f"Could not click branch '{selected_branch_name}' with selector '{branch_to_click_selector}': {e}")
                if progress_callback:
                    progress_callback(f"❌ Error: ไม่สามารถคลิก Branch '{selected_branch_name}' ได้.")
        else:
            print(f"Branch buttons base selector or selected branch value not found. Base Selector: {branch_buttons_base_selector}, Value: {selected_branch_value}")
            if progress_callback:
                progress_callback("❌ Error: ไม่สามารถเลือก Branch ได้.")

        # 3. กดปุ่ม Next (หลังเลือก Branch)
        branch_next_button_selector = web_elements.get("branch_next_button")
        if branch_next_button_selector:
            if progress_callback:
                progress_callback("⏳ กำลังรอปุ่ม Next (Branch)...")
            await page.wait_for_selector(branch_next_button_selector, state="visible", timeout=10000)
            await page.click(branch_next_button_selector)
            print("Clicked Branch Next button.")
            if progress_callback:
                progress_callback("✅ คลิกปุ่ม Next (Branch) แล้ว.")
        else:
            print("Branch Next button selector not found in element data.")
            if progress_callback:
                progress_callback("❌ Error: ไม่พบ Selector ปุ่ม Next (Branch).")

        # 4. เลือกวัน (ใช้ selected_day ที่รับเข้ามา)
        final_date_selector = None
        if site_name == "PMROCKET":
            calendar_day_button_prefix = web_elements.get("calendar_day_button_prefix")
            if calendar_day_button_prefix:
                container_selector = calendar_day_button_prefix.split(' > button:nth-child(')[0]
                final_date_selector = f"{container_selector} button:has-text('{selected_day}')" 
            else:
                print("PMROCKET: Calendar container selector prefix not found.")
        elif site_name == "EZBOT":
            calendar_grid_selector_ezbot = "#calendar-grid"
            date_data_attribute_selector = web_elements.get("date_data_attribute_selector") 

            if calendar_grid_selector_ezbot:
                if date_data_attribute_selector and "{}" in date_data_attribute_selector:
                    final_date_selector = date_data_attribute_selector.format(selected_day)
                else:
                    final_date_selector = f"{calendar_grid_selector_ezbot} button:has-text('{selected_day}')"
            else:
                print("EZBOT: Calendar grid selector not found.")

        if final_date_selector:
            if progress_callback:
                progress_callback(f"⏳ กำลังเลือกวันที่ {selected_day}...")
            try:
                await page.wait_for_selector(final_date_selector, state="visible", timeout=10000)
                await page.click(final_date_selector)
                print(f"Selected date: {selected_day}")
                if progress_callback:
                    progress_callback(f"✅ เลือกวันที่ {selected_day} แล้ว.")
            except Exception as e:
                print(f"Could not click date '{selected_day}' with selector '{final_date_selector}': {e}")
                if progress_callback:
                    progress_callback(f"❌ Error: ไม่สามารถคลิกวันที่ '{selected_day}' ได้.")
        else:
            print(f"Date selector not found or invalid for {site_name}. Selected Day: {selected_day}")
            if progress_callback:
                progress_callback("❌ Error: ไม่พบ Selector สำหรับวัน.")

        # 5. เลือกเวลา (ใช้ config เวลาก็มี times จาก API)
        time_select_section_selector_ezbot = web_elements.get("time_select_section_selector")
        time_buttons_base_selector_ezbot = web_elements.get("time_buttons_base_selector")
        time_buttons_prefix_pmrocket = web_elements.get("time_buttons_prefix")

        actual_time_value_to_select = selected_time_value
        
        final_time_selector = None
        if site_name == "PMROCKET":
            if time_buttons_prefix_pmrocket:
                if progress_callback:
                    progress_callback(f"⏳ กำลังรอให้ตัวเลือกเวลาโหลด...")
                
                time_container_selector = time_buttons_prefix_pmrocket.split(' > button:nth-child(')[0]
                
                await page.wait_for_selector(time_container_selector, state="visible", timeout=15000) 
                
                final_time_selector = f"{time_container_selector} button:has-text('{actual_time_value_to_select}')"
            else:
                print("PMROCKET: Time buttons container selector not found.")
        elif site_name == "EZBOT":
            if time_buttons_base_selector_ezbot:
                final_time_selector = f"{time_buttons_base_selector_ezbot} >> text='{actual_time_value_to_select}'"
            else:
                print("EZBOT: Time buttons base selector not found.")

        if final_time_selector:
            if progress_callback:
                progress_callback(f"⏳ กำลังเลือกเวลา {selected_time_value}...")
            try:
                await page.wait_for_selector(final_time_selector, state="visible", timeout=10000)
                await page.click(final_time_selector)
                print(f"Selected time: {selected_time_value}")
                if progress_callback:
                    progress_callback(f"✅ เลือกเวลา {selected_time_value} แล้ว.")
            except Exception as e:
                print(f"Could not click time '{selected_time_value}' with selector '{final_time_selector}': {e}")
                if progress_callback:
                    progress_callback(f"❌ Error: ไม่สามารถคลิกเวลา '{selected_time_value}' ได้.")
        else:
            print(f"Time selector not found or invalid for {site_name}. Time: {selected_time_value}")
            if progress_callback:
                progress_callback("❌ Error: ไม่พบ Selector สำหรับเวลา.")

        # 6. กดปุ่ม Confirm (หลังเลือกวันและเวลา)
        datetime_next_button_selector = web_elements.get("datetime_next_button") 
        if datetime_next_button_selector:
            if progress_callback:
                progress_callback("⏳ กำลังรอปุ่ม Confirm (เลือกวัน/เวลา)...")
            
            try:
                await page.wait_for_selector(datetime_next_button_selector, state="visible", timeout=30000) 
                await page.click(datetime_next_button_selector)
                print("Clicked Confirm selection button.")
                if progress_callback:
                    progress_callback("✅ คลิกปุ่ม Confirm (เลือกวัน/เวลา) แล้ว.")
            except Exception as e:
                print(f"Could not click Datetime Next button: {e}")
                if progress_callback:
                    progress_callback(f"❌ Error: ไม่สามารถคลิกปุ่ม Confirm (เลือกวัน/เวลา) ได้: {e}")
        else:
            print("Datetime Next button selector not found.")
            if progress_callback:
                progress_callback("❌ Error: ไม่พบ Selector ปุ่ม Confirm (เลือกวัน/เวลา).")

        # 7. รอโหลด Check Box จากนั้นติ๊กเช็คบ็อค
        checkbox_selector = web_elements.get("checkbox")
        if checkbox_selector:
            if progress_callback:
                progress_callback("⏳ กำลังรอ Checkbox...")
            await page.wait_for_selector(checkbox_selector, state="visible", timeout=15000)
            await page.check(checkbox_selector)
            print("Checked checkbox.")
            if progress_callback:
                progress_callback("✅ ติ๊ก Checkbox แล้ว.")
        else:
            print("Checkbox selector not found in element data.")
            if progress_callback:
                progress_callback("❌ Error: ไม่พบ Selector Checkbox.")

        # 8. กด Confirm Booking เป็นอันจบกระบวนการ
        confirm_booking_button_selector = web_elements.get("confirm_button")
        if confirm_booking_button_selector:
            if progress_callback:
                progress_callback("⏳ กำลังรอปุ่ม Confirm Booking...")
            try:
                await page.wait_for_selector(confirm_booking_button_selector, state="visible", timeout=30000)
                await page.click(confirm_booking_button_selector)
                print("Clicked Confirm Booking button. Booking process finished.")
                if progress_callback:
                    progress_callback("✅ คลิกปุ่ม Confirm Booking แล้ว. กระบวนการจองเสร็จสิ้น!")
            except Exception as e:
                print(f"Could not click Confirm Booking button: {e}")
                if progress_callback:
                    progress_callback(f"❌ Error: ไม่สามารถคลิกปุ่ม Confirm Booking ได้: {e}")
        else:
            print("Confirm Booking button selector not found in element data.")
            if progress_callback:
                progress_callback("❌ Error: ไม่พบ Selector ปุ่ม Confirm Booking.")

        print("Booking process completed. Browser will remain open.")

    except Exception as e:
        print(f"An error occurred during Playwright operation: {e}")
        if progress_callback:
            progress_callback(f"❌ เกิดข้อผิดพลาด: {e}")
    finally:
        # ไม่ต้องปิด p (Playwright context) หรือ browser ที่นี่
        # เพื่อให้ browser เปิดอยู่ให้ user ปิดเอง
        pass
