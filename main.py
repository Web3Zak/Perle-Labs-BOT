import asyncio
import json

import ads
from logic import run_all_quests
from logger import setup_logger


# LOAD CONFIG

def load_accounts(path="config.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    
    if isinstance(data, dict):
        return [data]
    return data


# MAIN WORKFLOW

async def main():
    accounts = load_accounts()

    from playwright.async_api import async_playwright

    for account in accounts:
        logger = setup_logger(account["name"])
        logger.info("Starting account workflow")

        browser = context = page = None
        playwright = None

        try:
            logger.info(f"Starting ADS profile: {account['ads_profile_id']}")

            profile = await ads.start_profile(account["ads_profile_id"])

            # CDP
            ws = profile.get("ws")

            if isinstance(ws, dict):
                ws_url = (
                    ws.get("playwright")
                    or ws.get("cdp")
                    or ws.get("puppeteer")
                    or ws.get("selenium")
                )
            else:
                ws_url = ws

            if not ws_url:
                raise Exception(f"Cannot find CDP websocket in ADS response: {profile}")

            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(ws_url)

            context = browser.contexts[0]
            page = context.pages[0]

            logger.info("ADS browser connected")

            # RUN ALL QUESTS
            await run_all_quests(page, context, account, logger)

            logger.info("Account workflow completed successfully")

        except Exception as e:
            logger.error(f"Account failed: {e}", exc_info=True)

        finally:
            logger.info("Shutting down account")

            try:
                if page:
                    await page.close()
            except Exception:
                pass

            try:
                if context:
                    await context.close()
            except Exception:
                pass

            try:
                if browser:
                    await browser.close()
            except Exception:
                pass

            try:
                if playwright:
                    await playwright.stop()
            except Exception:
                pass

            try:
                await ads.stop_profile(account["ads_profile_id"])
                logger.info("ADS profile stopped")
            except Exception:
                pass



if __name__ == "__main__":
    asyncio.run(main())
