# minigame.py
from playwright.async_api import Page
import asyncio

PIXELS_PER_RADIAN = 500

async def solve_minigame(page: Page) -> bool:
    try:
        canvas = page.locator("#app canvas")
        box = await canvas.bounding_box()
        cx = box['x'] + box['width'] / 2
        cy = box['y'] + box['height'] / 2

        rotation_y = await page.evaluate("window.cardGroup.rotation.y")
        drag = -rotation_y * PIXELS_PER_RADIAN

        await page.mouse.move(cx, cy)
        await page.mouse.down()
        await page.mouse.move(cx + drag, cy)
        await page.mouse.up()
        await asyncio.sleep(0.5)

        for _ in range(30):
            text = await page.locator("#status-text").inner_text()
            if '✅ มุมตรง!' in text and 'กดเมาส์ค้างไว้' in text:
                await page.mouse.move(cx, cy)
                await page.mouse.down()
                await asyncio.sleep(3.1)
                await page.mouse.up()
                return True
            await asyncio.sleep(0.2)
        return False
    except Exception as e:
        print("[ERROR] solve_minigame:", e)
        return False
