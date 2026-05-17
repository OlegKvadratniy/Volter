from __future__ import annotations

import json
import logging
import pickle
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

# Allow running this file directly for testing
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Playwright,
    sync_playwright,
)

from volter.models.product import Product, SkuOption

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHORT_URL_DOMAINS = ("m.tb.cn", "e.tb.cn", "t.cn")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]

COOKIES_DIR = Path.home() / ".volter"
COOKIES_FILE = COOKIES_DIR / "cookies.pkl"

MAX_RETRIES = 3
PAGE_TIMEOUT_MS = 30_000
NAVIGATION_TIMEOUT_MS = 25_000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_delay(lo: float = 0.5, hi: float = 2.0) -> None:
    time.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------------------
# TaobaoParser
# ---------------------------------------------------------------------------

class TaobaoParser:
    """Чёрный ящик: URL внутрь → Product наружу."""

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # -- public API ----------------------------------------------------------

    def parse(self, url: str) -> Product:
        """Раскрыть короткую ссылку, зайти на страницу, собрать данные."""
        last_error = ""

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("Attempt %d/%d for %s", attempt, MAX_RETRIES, url)
            try:
                full_url = self._resolve_short_url(url)
                item_id = self._extract_item_id(full_url)
                if not item_id:
                    raise ValueError(f"Cannot extract item_id from {full_url}")

                self._setup_browser()
                page = self._context.new_page()
                try:
                    self._goto_page(page, full_url)
                    self._scroll_page(page)

                    if self._check_captcha(page):
                        logger.warning("Captcha detected — switching to visible mode")
                        self._handle_captcha(page)

                    # Extract data from HTML source
                    product = self._extract_from_html(page, item_id, full_url)
                    return product
                finally:
                    page.close()
            except Exception as exc:
                last_error = str(exc)
                logger.error("Attempt %d failed: %s", attempt, exc)
                self._safe_close()

        return Product(error=f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")

    def close(self) -> None:
        self._safe_close()

    # -- HTML extraction -----------------------------------------------------

    def _extract_from_html(self, page: Any, item_id: str, full_url: str) -> Product:
        """Extract product data by evaluating JS in the page context."""
        try:
            data = page.evaluate("""
                () => {
                    // Primary: __ICE_APP_CONTEXT__
                    if (window.__ICE_APP_CONTEXT__) {
                        return { source: 'ICE_APP_CONTEXT', data: window.__ICE_APP_CONTEXT__ };
                    }
                    // Fallback: g_config
                    if (window.g_config) {
                        return { source: 'g_config', data: window.g_config };
                    }
                    return null;
                }
            """)

            if not data:
                logger.warning("No embedded data found in page")
                return Product(item_id=item_id, full_url=full_url, error="No embedded data found")

            logger.info("Found data source: %s", data.get("source"))
            res = self._navigate_to_res(data.get("data", {}))

            if not res:
                logger.warning("Could not navigate to product data (res)")
                return Product(item_id=item_id, full_url=full_url, error="No product data in res")

            return self._build_product(res, item_id, full_url)

        except Exception as exc:
            logger.error("Failed to extract from HTML: %s", exc)
            return Product(item_id=item_id, full_url=full_url, error=str(exc))

    @staticmethod
    def _navigate_to_res(raw: dict) -> dict | None:
        """Navigate through various wrapper structures to find the 'res' dict."""
        # Direct: { loaderData: { home: { data: { res: {...} } } } }
        res = (
            raw.get("loaderData", {})
            .get("home", {})
            .get("data", {})
            .get("res")
        )
        if res:
            return res

        # Try: { data: { res: {...} } }
        res = raw.get("data", {}).get("res")
        if res:
            return res

        # Try: { res: {...} }
        res = raw.get("res")
        if res:
            return res

        # Try: { data: { data: { res: {...} } } }
        res = raw.get("data", {}).get("data", {}).get("res")
        if res:
            return res

        return None

    def _build_product(self, res: dict, item_id: str, full_url: str) -> Product:
        """Build Product from the 'res' data object."""
        item = res.get("item", {})
        seller = res.get("seller", {})
        sku_core = res.get("skuCore", {})

        # Title
        title = item.get("title", "")

        # Main image
        images = item.get("images", [])
        image_url = images[0] if images else ""

        # Shop name
        shop = seller.get("shopName", "") or seller.get("sellerNick", "")

        # Price from skuCore.sku2info["0"] (default/starting price)
        sku2info = sku_core.get("sku2info", {})
        default_sku = sku2info.get("0", {})

        price_yuan = 0.0
        if default_sku:
            # Try subPrice (after discount) first, then regular price
            sub_price = default_sku.get("subPrice", {})
            price_obj = default_sku.get("price", {})

            price_text = (
                sub_price.get("priceText", "")
                or price_obj.get("priceText", "")
            )
            price_money = (
                sub_price.get("priceMoney")
                or price_obj.get("priceMoney")
            )

            if price_money:
                price_yuan = float(price_money) / 100
            elif price_text:
                match = re.search(r"(\d+\.?\d*)", str(price_text))
                if match:
                    price_yuan = float(match.group(1))

        # SKU options from skuCore or from DOM
        sku_options = self._extract_sku_options(res, sku_core)

        return Product(
            item_id=item_id,
            title_zh=title,
            price_yuan=price_yuan,
            shop=shop,
            image_url=image_url,
            sku_options=sku_options,
            full_url=full_url,
        )

    def _extract_sku_options(self, res: dict, sku_core: dict) -> list[SkuOption]:
        """Extract SKU options from data or DOM."""
        sku_options: list[SkuOption] = []

        # Try skuBase from res
        sku_base = res.get("skuBase", {})
        if sku_base:
            props = sku_base.get("props", [])
            if isinstance(props, list):
                for prop in props:
                    name = prop.get("name", "")
                    values = prop.get("values", [])
                    if isinstance(values, list):
                        val_names = [v.get("name", "") for v in values if v.get("name")]
                    else:
                        val_names = []
                    if name and val_names:
                        sku_options.append(SkuOption(name=name, values=val_names))

        # If no skuBase, try to extract from industryParamVO color classification
        if not sku_options:
            plus_view = res.get("plusViewVO", {})
            industry = plus_view.get("industryParamVO", {})
            basic_params = industry.get("basicParamList", [])
            for param in basic_params:
                if param.get("propertyName") == "颜色分类":
                    raw_values = param.get("valueName", "")
                    if raw_values:
                        values = [v.strip() for v in raw_values.split(",") if v.strip()]
                        if values:
                            sku_options.append(SkuOption(name="颜色分类", values=values))
                    break

        return sku_options

    # -- URL helpers ---------------------------------------------------------

    def _resolve_short_url(self, url: str) -> str:
        """Follow redirects for short URLs (m.tb.cn, e.tb.cn, t.cn)."""
        if any(domain in url for domain in SHORT_URL_DOMAINS):
            logger.info("Short URL detected, resolving: %s", url)
            self._pw = sync_playwright().start()
            browser = self._pw.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
                resolved = page.url
                return resolved
            finally:
                page.close()
                ctx.close()
                browser.close()
                self._pw.stop()
                self._pw = None
        return url

    @staticmethod
    def _extract_item_id(url: str) -> str:
        """Extract numeric item_id from Taobao URL."""
        match = re.search(r"(?:id|item_id)=(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"/item/(\d+)", url)
        if match:
            return match.group(1)
        return ""

    # -- browser setup -------------------------------------------------------

    def _setup_browser(self) -> None:
        if self._browser is not None:
            return

        self._pw = sync_playwright().start()
        launch_args = {
            "headless": self._headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
            ],
        }
        self._browser = self._pw.chromium.launch(**launch_args)

        viewport = random.choice(VIEWPORTS)
        context_args: dict[str, Any] = {
            "user_agent": random.choice(USER_AGENTS),
            "viewport": viewport,
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
        }

        self._context = self._browser.new_context(**context_args)

        # Inject stealth script
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)

        # Load saved cookies
        self._load_cookies()

    # -- cookies -------------------------------------------------------------

    def _load_cookies(self) -> None:
        if not COOKIES_FILE.exists():
            return
        try:
            with open(COOKIES_FILE, "rb") as f:
                cookies = pickle.load(f)
            if cookies:
                self._context.add_cookies(cookies)
                logger.info("Loaded %d cookies from %s", len(cookies), COOKIES_FILE)
        except Exception as exc:
            logger.warning("Failed to load cookies: %s", exc)

    def _save_cookies(self) -> None:
        if self._context is None:
            return
        try:
            COOKIES_DIR.mkdir(parents=True, exist_ok=True)
            cookies = self._context.cookies()
            with open(COOKIES_FILE, "wb") as f:
                pickle.dump(cookies, f)
            logger.info("Saved %d cookies to %s", len(cookies), COOKIES_FILE)
        except Exception as exc:
            logger.warning("Failed to save cookies: %s", exc)

    # -- page actions --------------------------------------------------------

    def _goto_page(self, page: Any, url: str) -> None:
        page.set_default_timeout(PAGE_TIMEOUT_MS)
        page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        _random_delay(1.0, 3.0)

    def _scroll_page(self, page: Any) -> None:
        """Scroll to trigger lazy-loaded content."""
        try:
            page.evaluate("""
                () => {
                    return new Promise(resolve => {
                        let totalHeight = 0;
                        const distance = 300;
                        const timer = setInterval(() => {
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= document.body.scrollHeight) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)
            _random_delay(0.5, 1.5)
        except Exception as exc:
            logger.warning("Scroll failed: %s", exc)

    def _check_captcha(self, page: Any) -> bool:
        """Detect captcha / anti-bot page."""
        url = page.url
        captcha_url_patterns = [
            "login.taobao.com",
            "sec.taobao.com",
            "verify.taobao.com",
            "check.taobao.com",
        ]
        if any(p in url for p in captcha_url_patterns):
            return True

        try:
            title = page.title()
            if any(w in title.lower() for w in ["verify", "captcha", "安全验证", "滑块"]):
                return True
        except Exception:
            pass

        return False

    def _handle_captcha(self, page: Any) -> None:
        """Switch to visible browser so user can solve captcha manually."""
        if not self._headless:
            logger.info("Waiting for user to solve captcha (60s timeout)...")
            try:
                page.wait_for_timeout(60_000)
            except Exception:
                pass
            self._save_cookies()
            return

        logger.info("Restarting in visible mode to solve captcha...")
        self._save_cookies()
        self._safe_close()

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=False)
        self._context = self._browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=random.choice(VIEWPORTS),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        self._load_cookies()

        new_page = self._context.new_page()
        new_page.goto(page.url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        logger.info("Solve captcha in the visible browser, then press Enter in terminal...")
        try:
            input("Press Enter when captcha is solved...")
        except KeyboardInterrupt:
            pass
        self._save_cookies()
        new_page.close()

    # -- cleanup -------------------------------------------------------------

    def _safe_close(self) -> None:
        """Close browser resources without raising."""
        try:
            if self._context:
                self._save_cookies()
                self._context.close()
        except Exception as exc:
            logger.debug("Context close error: %s", exc)
        try:
            if self._browser:
                self._browser.close()
        except Exception as exc:
            logger.debug("Browser close error: %s", exc)
        try:
            if self._pw:
                self._pw.stop()
        except Exception as exc:
            logger.debug("Playwright stop error: %s", exc)
        self._context = None
        self._browser = None
        self._pw = None


if __name__ == "__main__":
    import json as _json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter Taobao URL: ").strip()

    if not url:
        print("No URL provided.")
        sys.exit(1)

    parser = TaobaoParser(headless=False)
    try:
        product = parser.parse(url)
        print("\n--- Result ---")
        print(_json.dumps({
            "item_id": product.item_id,
            "title_zh": product.title_zh,
            "price_yuan": product.price_yuan,
            "shop": product.shop,
            "image_url": product.image_url,
            "sku_options": [
                {"name": s.name, "values": s.values}
                for s in product.sku_options
            ],
            "full_url": product.full_url,
            "error": product.error,
        }, ensure_ascii=False, indent=2))
    finally:
        parser.close()
