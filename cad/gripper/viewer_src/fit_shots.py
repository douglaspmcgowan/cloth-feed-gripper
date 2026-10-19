"""Capture the current fit review at the three supported viewport sizes."""
import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[3]
SIZES = ((1440, 900, "light"), (768, 1024, "dark"), (375, 812, "dark"))


async def finding_shot(page, folder, name, finding):
    await page.evaluate("id => selectFinding(id,{instant:true})", finding)
    await page.evaluate("document.getElementById('fit-3d').scrollIntoView({block:'start'})")
    await page.wait_for_timeout(500)
    await page.screenshot(path=str(folder / name))


async def capture(folder):
    folder.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        for width, height, scheme in SIZES:
            context = await browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
            context.set_default_timeout(600000)
            page = await context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto((ROOT / "cad/gripper/viewer.html").as_uri() + "#fit-3d")
            await page.wait_for_function("V3.ready&&V3.mode==='fit'")
            await finding_shot(page, folder, f"fit3d_{width}_{scheme}.png", "horn-housing")
            if width == 375:
                await page.locator("#fitCard").screenshot(path=str(folder / "fit3d_horn_card_375_dark.png"))
            if width == 1440:
                await page.evaluate("location.hash='#fit-findings'")
                await page.wait_for_timeout(500)
                await page.screenshot(path=str(folder / "fit_findings_1440_light.png"))
                await page.evaluate("location.hash='#fit-3d'")
                await finding_shot(page, folder, "fit3d_boss_bore_1440_light.png", "boss-bore-finish")
                await finding_shot(page, folder, "fit3d_b19_finger_a_1440_light.png", "finger-a-knuckle-b")
                await finding_shot(page, folder, "fit3d_b19_finger_b_1440_light.png", "knuckle-a-finger-b")
            if width == 375:
                await finding_shot(page, folder, "fit3d_roll_375_dark.png", "roll-wrist")
            assert not errors, errors
            await context.close()
        await browser.close()
    print("Nine current fit screenshots captured; zero page errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", required=True, type=Path)
    asyncio.run(capture(parser.parse_args().shots.resolve()))
