# -*- coding: utf-8 -*-
"""美团商家后台房价采集器"""
import os, json, time, re
from app.db.database import db_transaction
from app.constants import IMPORT_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

def _get_config(key, default=""):
    try:
        with db_transaction() as conn:
            c = conn.cursor()
            c.execute("SELECT config_value FROM sys_config WHERE config_key=?", (key,))
            row = c.fetchone()
            return row["config_value"] if row else default
    except: return default

class MeituanCollector:
    def __init__(self):
        self.browser = self.context = self.page = self.playwright = None
        self._config_cache = {}
        self._load_config()

    def _load_config(self):
        for k in ["meituan_enabled","meituan_username","meituan_password","meituan_calendar_url"]:
            self._config_cache[k] = _get_config(k,"")

    @property
    def enabled(self):
        return self._config_cache.get("meituan_enabled","0") == "1"

    @property
    def _cookie_path(self):
        return os.path.join(IMPORT_DIR, "meituan_cookies.json")

    def _save_cookies(self):
        try:
            if self.context:
                c = self.context.cookies()
                os.makedirs(os.path.dirname(self._cookie_path), exist_ok=True)
                with open(self._cookie_path,"w",encoding="utf-8") as f:
                    json.dump(c, f, ensure_ascii=False, indent=2)
                logger.info("Cookie已保存: %d条", len(c))
        except Exception as e: logger.error("保存Cookie失败: %s", e)

    def _load_cookies(self):
        try:
            if os.path.exists(self._cookie_path):
                with open(self._cookie_path,"r",encoding="utf-8") as f: return json.load(f)
        except: pass
        return []

    def _ensure_browser(self):
        if self.browser: return
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        self.context = self.browser.new_context(viewport={"width":1280,"height":800})
        saved = self._load_cookies()
        if saved: self.context.add_cookies(saved)
        self.page = self.context.new_page()

    def _close_browser(self):
        try:
            if self.browser: self.browser.close()
            if self.playwright: self.playwright.stop()
        except: pass
        self.browser = self.context = self.page = self.playwright = None

    def login(self):
        self._ensure_browser()
        try:
            self.page.goto("https://me.meituan.com/ebooking/", wait_until="domcontentloaded", timeout=15000)
            time.sleep(4)
            if "login" not in self.page.url.lower():
                logger.info("Cookie登录成功")
                return True
            logger.warning("Cookie失效")
            return False
        except Exception as e:
            logger.error("登录失败: %s", e)
            return False

    def capture_cookie(self, wait_timeout=180):
        self._ensure_browser()
        self.page.goto("https://me.meituan.com/login/index.html", wait_until="domcontentloaded", timeout=15000)
        logger.info("请在浏览器中手动登录美团...")
        start = time.time()
        while time.time() - start < wait_timeout:
            time.sleep(3)
            try:
                for text in ["工作台","产品管理","订单管理"]:
                    el = self.page.query_selector(f"text={text}")
                    if el:
                        cookies = self.context.cookies()
                        self._save_cookies()
                        return {"success": True, "cookie_count": len(cookies)}
            except: pass
        return {"success": False, "message": "超时"}

    def extract_prices(self):
        if not self.page: return None
        try:
            all_texts = []
            for i in range(10):
                time.sleep(3)
                t = self.page.evaluate("()=>document.body?document.body.innerText:''")
                all_texts.append(t)
                for f in self.page.frames:
                    try:
                        ft = f.evaluate("()=>document.body?document.body.innerText:''")
                        all_texts.append(ft)
                    except: pass
                combined = ' '.join(all_texts)
                if re.search(r'\d{2,4}\.\d{2}', combined):
                    break

            combined = ' '.join(all_texts)
            logger.info("文本总量=%d字, frame数=%d", len(combined), len(self.page.frames))

            decimals = re.findall(r'\b(\d{2,4}\.\d{2})\b', combined)
            prices = sorted(set(float(p) for p in decimals if 50 < float(p) < 9999))
            if prices:
                logger.info("美团底价: %s (共%d个: %s)", prices[0], len(prices), prices[:15])
                return prices[0]

            ints = re.findall(r'\b(\d{2,4})\b', combined)
            int_prices = sorted(set(float(p) for p in ints if 100 < float(p) < 9999))
            logger.warning("未找到小数价格, 整数: %s", int_prices[:20])
            return None
        except Exception as e:
            logger.error("提取异常: %s", e)
            return None

    def get_daily_min_price(self, date):
        if not self.enabled: return None
        try:
            if not self.login(): return None
            self.page.goto("https://me.meituan.com/ebooking/merchant/product#/index", wait_until="load", timeout=20000)
            return self.extract_prices()
        except Exception as e:
            logger.error("采集异常: %s", e)
            return None
        finally:
            self._close_browser()

def fetch_meituan_min_price(date):
    try:
        c = MeituanCollector()
        if not c.enabled: return None
        return c.get_daily_min_price(date)
    except Exception as e:
        logger.error("获取异常: %s", e)
        return None
