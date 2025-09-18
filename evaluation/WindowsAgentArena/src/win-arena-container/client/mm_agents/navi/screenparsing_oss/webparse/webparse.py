import asyncio
from playwright.async_api import async_playwright
from mm_agents.navi.screenparsing_oss.webparse.extract_async import extract_locate


class WebParse:
    def __init__(self, cdp_url=None, launch_browser=False) -> None:
        self.pw_page = None
        self.launch_browser = launch_browser
        self.chromium_cdp_url = cdp_url
        self.pw = None
        assert not launch_browser, "launch_browser not supported"

    async def _attach_to_existing(self, chromium_cdp_url):
        try:
            browser = await self.pw.chromium.connect_over_cdp(chromium_cdp_url)
            default_context = browser.contexts[0]
            self.pw_page = default_context.pages[0]
            return True
        except Exception as e:
            print(
                f"[webparse] Could not attach to RDP session at the given URL ({chromium_cdp_url}). Make sure the browser is running in debug mode and the URL is correct."
            )
            print(f"[webparse] Error: {e}")
            return False

    async def _launch_and_attach(self):
        browser = await self.pw.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://google.com")
        await page.wait_for_load_state("networkidle")
        self.pw_page = page

    async def _attach_page(self):
        if not self.pw:
            self.pw = await async_playwright().start()
        if self.chromium_cdp_url:
            # To connect to an already running browser session, you can use connect_over_cdp
            await self._attach_to_existing(self.chromium_cdp_url)
        if not self.pw_page and self.launch_browser:
            # If cdp url is not provided or not found, we'll launch a new browser
            await self._launch_and_attach()

    # def propose_ents(self, image):
    #     return asyncio.run(self._propose_ents(image))

    def propose_ents(self, image):
        try:
            return asyncio.run(self._propose_ents(image))
        except Exception:
            return []

    async def _propose_ents(self, image):
        async with async_playwright() as playwright:
            self.pw = playwright
            if not (await self._attach_to_existing(self.chromium_cdp_url)):
                return []

            attempts = 0
            while attempts < 2:
                has_match, entities = await extract_locate(image, self.pw_page)
                if not has_match:
                    attempts += 1
                else:
                    break
            return [
                {
                    "from": "webparse",
                    "type": "text/html",
                    "shape": {
                        "x": int(entity["shape"][0]),
                        "y": int(entity["shape"][1]),
                        "width": int(entity["shape"][2]),
                        "height": int(entity["shape"][3]),
                    },
                    "text": entity.get("textContent"),
                }
                for entity in entities
            ]
