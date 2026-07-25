# -*- coding: utf-8 -*-
"""
去呼呼客栈管家 自动数据采集引擎
通过浏览器自动化登录去呼呼PMS系统，自动导出日报并清洗入库
"""
import os
import json
import time
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional

from app.db.database import db_transaction
from app.core.data_cleaner import DataCleaner
from app.core.calculator import calc_hourly
from app.core.scheduler import daily_aggregate, monthly_aggregate_for_month
from app.core.meituan_collector import fetch_meituan_min_price
from app.constants import IMPORT_DIR, MAX_HOUR, DataSource, DEFAULT_TIMEZONE
from app.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(DEFAULT_TIMEZONE)
except ImportError:
    import pytz
    TZ = pytz.timezone(DEFAULT_TIMEZONE)


def check_browser_available() -> dict:
    """
    检测系统是否有可用的 Chromium 浏览器
    供系统状态API调用，返回 {available: bool, name: str, path: str, message: str}
    """
    import os
    import winreg
    from pathlib import Path

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")

    # 检查列表：(路径, 显示名称)
    check_list = [
        # Edge
        (os.path.join(program_files_x86, "Microsoft\\Edge\\Application\\msedge.exe"), "Microsoft Edge"),
        (os.path.join(program_files, "Microsoft\\Edge\\Application\\msedge.exe"), "Microsoft Edge"),
        # Chrome
        (os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"), "Google Chrome"),
        (os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"), "Google Chrome"),
        (os.path.join(local_appdata, "Google\\Chrome\\Application\\chrome.exe"), "Google Chrome"),
        # 360
        (os.path.join(local_appdata, "360Chrome\\Chrome\\Application\\360chrome.exe"), "360极速浏览器"),
        (os.path.join(program_files_x86, "360\\360se6\\Application\\360se.exe"), "360安全浏览器"),
        # QQ
        (os.path.join(program_files_x86, "Tencent\\QQBrowser\\QQBrowser.exe"), "QQ浏览器"),
        # 搜狗
        (os.path.join(program_files_x86, "SogouExplorer\\SogouExplorer.exe"), "搜狗浏览器"),
    ]

    for path, name in check_list:
        if os.path.exists(path):
            return {"available": True, "name": name, "path": path, "message": f"检测到 {name}"}

    # 检查注册表中的默认浏览器
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice") as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\shell\open\command") as cmd_key:
            cmd, _ = winreg.QueryValueEx(cmd_key, "")
            exe = cmd.strip().strip('"').split('"')[0]
            exe = os.path.normpath(exe)
            if os.path.exists(exe):
                return {"available": True, "name": f"默认浏览器({prog_id})", "path": exe, "message": f"检测到 {prog_id}"}
    except Exception:
        pass

    return {"available": False, "name": "", "path": "", "message": "未检测到Chromium内核浏览器，自动采集功能不可用。请安装Edge或Chrome浏览器。"}


class QuhuhuCollector:
    """去呼呼数据采集器"""

    LOGIN_URL = "https://i.quhuhu.com/action/loginIndex?bizType=srm&retUrl=http%3A%2F%2Fkz.quhuhu.com%2Frooms%2Ftable.htm"
    ROOMS_URL = "http://kz.quhuhu.com/rooms/table.htm"
    # 去呼呼三个产品
    PRODUCT_KZ = "去呼呼客栈管家"   # kz.quhuhu.com
    PRODUCT_JD = "去呼呼酒店管家"   # jd.quhuhu.com
    PRODUCT_JT = "去呼呼集团管家"   # jt.quhuhu.com

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self._cleaner = DataCleaner()
        # 预加载的配置（避免 Playwright greenlet 线程冲突）
        self._config = {}

    def _preload_config(self):
        """在启动浏览器前预加载所有需要的配置到内存（不使用 context manager，避免 greenlet 冲突）"""
        try:
            import sqlite3
            from app.constants import DB_FILE
            conn = sqlite3.connect(
                DB_FILE,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT config_key, config_value FROM sys_config")
            for row in c.fetchall():
                self._config[row["config_key"]] = row["config_value"]
            conn.close()
            logger.info(f"已预加载 {len(self._config)} 项配置")
        except Exception as e:
            logger.error(f"预加载配置失败: {e}")

    def _save_config_after(self, updates: dict):
        """采集结束后保存配置（在浏览器关闭后调用，避免 greenlet 冲突）"""
        if not updates:
            return
        try:
            import sqlite3
            from app.constants import DB_FILE
            conn = sqlite3.connect(
                DB_FILE
            )
            c = conn.cursor()
            for key, value in updates.items():
                c.execute(
                    "INSERT OR REPLACE INTO sys_config(config_key,config_value,config_desc) VALUES(?,?,?)",
                    (key, str(value), "自动采集配置")
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def _cfg(self, key: str, default: str = "") -> str:
        """从预加载配置中读取（线程安全）"""
        return self._config.get(key, default)

    def _ensure_browser(self, headed: bool = True):
        if self.browser is not None:
            return
        
        # Playwright 已在 EXE 中捆绑，此处不应失败
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()

        # 自动探测系统可用的 Chromium 内核浏览器
        browser_path = self._find_system_browser()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=ChromeWhatsNewUI",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        if browser_path:
            logger.info(f"使用系统浏览器: {browser_path}")
            self.browser = self.playwright.chromium.launch(
                headless=not headed,
                executable_path=browser_path,
                args=launch_args,
            )
        else:
            # 最终兜底：Playwright 内置 Chromium
            logger.info("未找到系统浏览器，使用 Playwright 内置 Chromium")
            self.browser = self.playwright.chromium.launch(
                headless=not headed,
                args=launch_args,
            )

        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        )
        self.page = self.context.new_page()
        logger.info("Playwright 浏览器已启动")

    def _find_system_browser(self) -> Optional[str]:
        """
        自动查找系统可用的 Chromium 内核浏览器
        优先级：系统默认浏览器 > Edge > Chrome > 360浏览器 > QQ浏览器
        :return: 浏览器可执行文件路径，未找到返回 None
        """
        import winreg

        candidates = []  # [(路径, 名称), ...]

        # 1. 从注册表读取系统默认浏览器
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice") as key:
                prog_id, _ = winreg.QueryValueEx(key, "ProgId")
                # 从 ProgId 查找对应程序路径
                try:
                    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                                        rf"{prog_id}\shell\open\command") as cmd_key:
                        cmd, _ = winreg.QueryValueEx(cmd_key, "")
                        # 提取 exe 路径（去掉参数和引号）
                        exe = cmd.strip().strip('"').split('"')[0]
                        exe = os.path.normpath(exe)
                        if os.path.exists(exe):
                            candidates.append((exe, f"系统默认({prog_id})"))
                except Exception:
                    pass
        except Exception:
            pass

        # 2. 常见浏览器路径列表
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")

        known_browsers = [
            # Edge（稳定版 + Beta + Dev）
            (os.path.join(program_files_x86, "Microsoft\\Edge\\Application\\msedge.exe"), "Edge (x86)"),
            (os.path.join(program_files, "Microsoft\\Edge\\Application\\msedge.exe"), "Edge"),
            # Chrome
            (os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"), "Chrome"),
            (os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"), "Chrome (x86)"),
            (os.path.join(local_appdata, "Google\\Chrome\\Application\\chrome.exe"), "Chrome (Local)"),
            # 360安全浏览器
            (os.path.join(local_appdata, "360Chrome\\Chrome\\Application\\360chrome.exe"), "360极速浏览器"),
            (os.path.join(program_files, "360\\360se6\\Application\\360se.exe"), "360安全浏览器"),
            (os.path.join(program_files_x86, "360\\360se6\\Application\\360se.exe"), "360安全浏览器(x86)"),
            (os.path.join(program_files, "360\\360Chrome\\Chrome\\Application\\360chrome.exe"), "360极速"),
            # QQ浏览器
            (os.path.join(program_files, "Tencent\\QQBrowser\\QQBrowser.exe"), "QQ浏览器"),
            (os.path.join(program_files_x86, "Tencent\\QQBrowser\\QQBrowser.exe"), "QQ浏览器(x86)"),
            (os.path.join(local_appdata, "Tencent\\QQBrowser\\QQBrowser.exe"), "QQ浏览器(Local)"),
            # 搜狗浏览器
            (os.path.join(program_files, "SogouExplorer\\SogouExplorer.exe"), "搜狗浏览器"),
            (os.path.join(program_files_x86, "SogouExplorer\\SogouExplorer.exe"), "搜狗浏览器(x86)"),
            # Brave
            (os.path.join(program_files, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"), "Brave"),
            # Opera
            (os.path.join(program_files, "Opera\\launcher.exe"), "Opera"),
            (os.path.join(local_appdata, "Programs\\Opera\\launcher.exe"), "Opera (Local)"),
        ]

        for path, name in known_browsers:
            if os.path.exists(path):
                candidates.append((path, name))

        # 3. 尝试 Playwright 的 channel 方式（Edge/Chrome 官方支持）
        for channel, ch_name in [("msedge", "Edge"), ("chrome", "Chrome")]:
            try:
                from playwright.sync_api import sync_playwright
                pw = sync_playwright().start()
                try:
                    # 尝试用 channel 启动来验证可用，然后关闭
                    b = pw.chromium.launch(channel=channel, headless=True,
                                           args=["--no-sandbox"])
                    b.close()
                    # channel 可用，但不直接用 channel，只是加入候选
                    if not any("Edge" in n or "Chrome" in n for _, n in candidates):
                        candidates.append((f"__channel__{channel}", ch_name))
                except Exception:
                    pass
                finally:
                    try:
                        pw.stop()
                    except Exception:
                        pass
            except Exception:
                pass

        # 返回第一个可用的（默认浏览器优先）
        if candidates:
            path, name = candidates[0]
            logger.info(f"检测到浏览器: {name} ({path})")
            if path.startswith("__channel__"):
                # 这是 Playwright channel，不能用于 executable_path
                return None  # 让上层用 channel 方式
            return path

        return None

    def _close_browser(self):
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    def _ensure_debug_dir(self) -> str:
        """确保调试截图目录存在"""
        debug_dir = os.path.join(os.path.dirname(IMPORT_DIR), "logs")
        os.makedirs(debug_dir, exist_ok=True)
        return debug_dir

    def _save_debug_screenshot(self, name: str) -> None:
        """保存调试截图"""
        try:
            path = os.path.join(self._ensure_debug_dir(), name)
            self.page.screenshot(path=path, full_page=True)
            logger.info(f"调试截图已保存: {name}")
        except Exception as e:
            logger.warning(f"截图失败: {e}")

    def _login(self) -> bool:
        """登录去呼呼 — 先用cookie，失败则JS直接POST登录API"""
        username = self._cfg("quhuhu_username", "")
        password_enc = self._cfg("quhuhu_password", "")

        if not username or not password_enc:
            logger.error("未配置去呼呼账号密码")
            return False

        try:
            password = base64.b64decode(password_enc).decode("utf-8")
        except Exception:
            password = password_enc

        self._ensure_browser(headed=True)
        page = self.page

        # 策略1: 尝试cookie
        saved_cookies = self._cfg("collect_cookie", "")
        if saved_cookies:
            logger.info("尝试cookie免登录...")
            if self._login_with_cookie(saved_cookies):
                return True

        # 策略2: JS直接POST登录API（绕过Vue表单的一切问题）
        logger.info("尝试JS直接POST登录API...")
        if self._login_via_api(username, password):
            self._save_cookies_if_new()  # ★ 登录成功后持久化Cookie
            return True

        # 策略3: 传统表单兜底
        logger.info("回退传统表单登录...")
        if self._login_via_fallback(username, password):
            self._save_cookies_if_new()  # ★ 登录成功后持久化Cookie
            return True
        
        return False

    def _save_cookies_if_new(self):
        """新登录成功后将Cookie持久化到数据库，下次免登录"""
        if self._pending_cookies:
            try:
                self._save_config_after({"collect_cookie": self._pending_cookies})
                logger.info("Cookie已持久化到数据库")
            except Exception as e:
                logger.warning(f"Cookie持久化失败: {e}")

    def _login_via_api(self, username: str, password: str) -> bool:
        """
        方案A：用JS直接POST到去呼呼登录API，完全绕过Vue表单
        """
        page = self.page
        # 先访问登录页获取必要的token/csrf
        page.goto("https://i.quhuhu.com/action/loginIndex?bizType=srm",
                  wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        # 用JS拦截并捕获登录请求，直接fetch
        result = page.evaluate("""
            async (params) => {
                const username = params.username;
                const password = params.password;
                
                // 尝试找到登录API端点
                // 去呼呼通常使用 /action/login 或 /api/login
                const endpoints = [
                    '/action/login',
                    '/action/loginIndex',
                    '/api/login', 
                    '/api/v1/login',
                    '/sso/login',
                ];
                
                for (const endpoint of endpoints) {
                    try {
                        const resp = await fetch(endpoint, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded',
                            },
                            body: new URLSearchParams({
                                username: username,
                                password: password,
                                mobile: username,
                                bizType: 'srm',
                            }).toString(),
                            redirect: 'follow',
                        });
                        
                        if (resp.url && !resp.url.includes('login')) {
                            // 登录成功，跳转
                            window.location.href = resp.url;
                            return 'redirect:' + resp.url;
                        }
                        
                        const text = await resp.text();
                        if (text.includes('成功') || text.includes('token')) {
                            return 'ok:' + endpoint;
                        }
                    } catch(e) {
                        // 尝试下一个端点
                    }
                }
                
                // 兜底：找form的action
                const form = document.querySelector('form');
                if (form && form.action) {
                    const action = form.action || window.location.href;
                    try {
                        const fd = new FormData();
                        fd.append('username', username);
                        fd.append('password', password);
                        fd.append('mobile', username);
                        const resp = await fetch(action, {
                            method: 'POST',
                            body: fd,
                            redirect: 'follow',
                        });
                        window.location.href = resp.url || '/';
                        return 'form-post';
                    } catch(e) {
                        return 'form-error:' + e.message;
                    }
                }
                
                return 'no-endpoint';
            }
        """, {"username": username, "password": password})

        logger.info(f"API登录结果: {result}")

        # 等待跳转
        time.sleep(5)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(3)

        current_url = page.url
        logger.info(f"API登录后URL: {current_url}")

        if "kz.quhuhu.com" in current_url and "login" not in current_url.lower():
            self._pending_cookies = json.dumps(self.context.cookies())
            return True

        return False

    def _login_via_fallback(self, username: str, password: str) -> bool:
        """方案B：传统表单填写（兜底）"""
        page = self.page
        page.goto("http://kz.quhuhu.com/v2/report/guestRoom.htm",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(2)

        if "kz.quhuhu.com" in page.url and "login" not in page.url.lower():
            self._pending_cookies = json.dumps(self.context.cookies())
            return True

        self._dismiss_browser_prompt()
        time.sleep(1)
        self._switch_to_account_login()
        time.sleep(2)

        # 填表
        phone = page.get_by_placeholder("请输入用户名或手机号")
        if phone.count() == 0:
            phone = page.locator("input.ivu-input[type='text']").first
        phone.click()
        time.sleep(0.3)
        phone.fill(username)
        time.sleep(0.5)

        pwd = page.locator("input[type='password']").first
        pwd.click()
        time.sleep(0.3)
        pwd.fill(password)
        time.sleep(0.5)

        # 勾选协议 - 强制
        try:
            page.locator(".ivu-checkbox-input").first.click(force=True)
        except Exception:
            try:
                page.locator("span:has-text('我已阅读')").first.click()
            except Exception:
                pass
        time.sleep(0.5)

        # 点登录
        page.locator("button:has-text('登录')").first.click(force=True)
        time.sleep(2)

        # 协议弹窗
        self._agree_protocol_popup()
        time.sleep(1)

        # ★ 关键：弹窗关闭后，用 JS 直接提交表单（不点按钮了）
        page.evaluate("""
            () => {
                const form = document.querySelector('form');
                if (form) {
                    form.submit();
                    return 'form-submitted';
                }
                // 找登录按钮用 JS 点击
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.textContent.includes('登录') && b.offsetParent !== null) {
                        b.click();
                        return 'btn-clicked';
                    }
                }
                return 'nothing';
            }
        """)
        time.sleep(5)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        time.sleep(3)

        if "kz.quhuhu.com" in page.url and "login" not in page.url.lower():
            self._pending_cookies = json.dumps(self.context.cookies())
            return True
        return False

    def _login_with_cookie(self, cookies_json: str) -> bool:
        """用已保存的 cookie 尝试免登录"""
        page = self.page
        try:
            cookies = json.loads(cookies_json)
            self.context.add_cookies(cookies)
            logger.info(f"已加载 {len(cookies)} 个 cookie")
        except Exception as e:
            logger.warning(f"Cookie 解析失败: {e}")
            return False

        # 直接访问 PMS 页面看是否需要登录
        page.goto("http://kz.quhuhu.com/v2/report/guestRoom.htm",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        if "login" not in page.url.lower():
            logger.info("✅ Cookie 有效，已免登录进入 PMS")
            self._pending_cookies = json.dumps(self.context.cookies())
            return True

        logger.info("Cookie 已失效，需要重新登录")
        return False

    def capture_cookie(self, wait_timeout: int = 180) -> Dict:
        """
        打开浏览器让用户手动登录，登录成功后自动抓取 Cookie 并保存
        会持续等待直到用户登录成功或超时
        :param wait_timeout: 等待用户登录的超时秒数（默认3分钟）
        """
        self._ensure_browser(headed=True)
        page = self.page

        # 打开 PMS 登录页
        page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        result = {
            "success": False,
            "message": "",
            "current_url": page.url,
        }

        # 先检查是否已登录（有有效cookie）
        page.goto("http://kz.quhuhu.com/v2/report/guestRoom.htm",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        if "login" not in page.url.lower():
            # 已经登录了，直接抓取
            cookies = self.context.cookies()
            cookies_json = json.dumps(cookies)
            self._pending_cookies = cookies_json
            self._save_config_after({"collect_cookie": cookies_json})
            result["success"] = True
            result["message"] = f"已登录状态，成功读取 {len(cookies)} 个 Cookie 并保存！"
            result["cookie_count"] = len(cookies)
            logger.info(f"✅ 免登录：已保存 {len(cookies)} 个 cookie")
            self._close_browser()
            return result

        # 需要手动登录：等待用户操作
        logger.info("⏳ 等待用户手动登录（最多等待 {} 秒）...".format(wait_timeout))
        logger.info("   浏览器已打开登录页面，请手动输入账号密码登录")

        start_time = time.time()
        check_interval = 2  # 每2秒检查一次

        while time.time() - start_time < wait_timeout:
            time.sleep(check_interval)
            try:
                current_url = page.url
                # 检查是否登录成功（URL不再包含login）
                if "login" not in current_url.lower() and "kz.quhuhu.com" in current_url:
                    logger.info(f"✅ 检测到登录成功！URL: {current_url}")
                    time.sleep(2)  # 等页面完全加载

                    # 抓取 cookie
                    cookies = self.context.cookies()
                    cookies_json = json.dumps(cookies)

                    # 保存到数据库
                    self._pending_cookies = cookies_json
                    self._save_config_after({"collect_cookie": cookies_json})

                    result["success"] = True
                    result["message"] = f"登录成功！已保存 {len(cookies)} 个 Cookie，后续采集将自动免登录。"
                    result["cookie_count"] = len(cookies)
                    logger.info(f"✅ 已保存 {len(cookies)} 个 cookie")

                    self._close_browser()
                    return result

                # 检测登录错误
                body_text = page.evaluate("() => document.body.innerText.substring(0, 500)").lower()
                if any(err in body_text for err in ["密码错误", "账号不存在", "账号或密码错误"]):
                    elapsed = int(time.time() - start_time)
                    logger.info(f"   等待中... ({elapsed}s) 页面仍显示登录表单")

            except Exception as e:
                logger.debug(f"检测登录状态异常: {e}")

        # 超时
        elapsed = int(time.time() - start_time)
        result["message"] = f"等待超时（{elapsed}秒），未检测到登录成功。请确认账号密码正确后重试。"
        logger.warning(f"⏰ 等待用户登录超时 ({elapsed}s)")
        self._close_browser()
        return result

    def _login_via_vue(self, username: str, password: str) -> bool:
        """方案A：通过JS找到Vue组件实例，直接设置数据并调用登录方法"""
        page = self.page
        try:
            result = page.evaluate("""
                (params) => {
                    const username = params.username;
                    const password = params.password;
                    // 遍历DOM树找Vue组件
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        const vm = el.__vue__;
                        if (!vm) continue;

                        // 递归查找含登录表单数据的组件
                        const finder = (comp, d) => {
                            if (d > 15) return null;
                            const keys = ['loginForm','formData','form','ruleForm','formModel'];
                            for (const k of keys) {
                                if (comp[k] && typeof comp[k] === 'object') {
                                    const f = comp[k];
                                    if (f.mobile !== undefined || f.phone !== undefined
                                        || f.username !== undefined) {
                                        return { comp, key: k, form: f };
                                    }
                                }
                            }
                            if (comp.$children) {
                                for (const c of comp.$children) {
                                    const r = finder(c, d+1);
                                    if (r) return r;
                                }
                            }
                            return null;
                        };
                        const found = finder(vm, 0);
                        if (!found) continue;

                        const f = found.form;
                        if (f.mobile !== undefined) f.mobile = username;
                        if (f.phone !== undefined) f.phone = username;
                        if (f.username !== undefined) f.username = username;
                        if (f.account !== undefined) f.account = username;
                        if (f.password !== undefined) f.password = password;
                        if (f.pwd !== undefined) f.pwd = password;
                        if (f.agreed !== undefined) f.agreed = true;
                        if (f.agree !== undefined) f.agree = true;
                        if (f.checked !== undefined) f.checked = true;

                        const methods = ['handleLogin','login','submit','handleSubmit',
                            'onSubmit','doLogin','onLogin','loginSubmit','postLogin'];
                        for (const m of methods) {
                            if (typeof found.comp[m] === 'function') {
                                found.comp[m]();
                                return 'vue-ok:' + m + ':' + found.key;
                            }
                        }
                        return 'vue-no-method:' + found.key;
                    }
                    return 'vue-not-found';
                }
            """, {"username": username, "password": password})

            logger.info(f"Vue方案: {result}")

            if result and 'vue-ok' in str(result):
                logger.info("✓ Vue组件登录方法已调用，等待跳转...")
                time.sleep(5)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                time.sleep(3)
                current_url = page.url
                if "login" not in current_url.lower() or "kz.quhuhu.com" in current_url:
                    self._pending_cookies = json.dumps(self.context.cookies())
                    return True

            # 方案A-补充：处理可能的协议弹窗
            time.sleep(1)
            self._agree_protocol_popup()
            time.sleep(1)
            self._click_login_button(None)
            time.sleep(5)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            time.sleep(3)
            return "login" not in page.url.lower() or "kz.quhuhu.com" in page.url

        except Exception as e:
            logger.warning(f"Vue方案异常: {e}")
            return False

    def _login_via_form(self, username: str, password: str) -> bool:
        """方案B：传统表单填写登录（兜底）"""
        page = self.page

        # 填手机号
        phone_input = self._find_and_fill_phone(username)
        if not phone_input:
            return False

        # 填密码
        pwd_input = self._find_and_fill_password(password)
        if not pwd_input:
            return False

        self._save_debug_screenshot("03_form_filled.png")

        # 勾选协议
        self._check_agreement_checkbox()
        self._save_debug_screenshot("03_agreement_checked.png")

        # 点击登录
        if not self._click_login_button(pwd_input):
            return False

        # 处理协议弹窗
        time.sleep(2)
        if self._agree_protocol_popup():
            time.sleep(1)
            self._click_login_button(None)

        # 等待结果
        time.sleep(5)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        time.sleep(3)

        self._save_debug_screenshot("04_after_login.png")
        self._select_product()
        self._save_debug_screenshot("05_after_product_select.png")

        return self._check_login_result()

    # ==================== 登录步骤分解方法 ====================

    def _dismiss_browser_prompt(self) -> None:
        """
        关闭"请使用谷歌浏览器"弹窗及可能的其他遮罩层
        点击"取消"、关闭按钮或遮罩层
        """
        page = self.page
        dismiss_selectors = [
            # "取消"文字按钮
            "button:has-text('取消')",
            "span:has-text('取消')",
            "a:has-text('取消')",
            "div:has-text('取消')",
            "text=取消",
            # 关闭按钮（X图标） - iView modal
            ".ivu-modal-close",
            ".ivu-modal .ivu-icon-ios-close",
            ".ivu-modal-header .ivu-icon",
            ".modal-close",
            ".dialog-close",
            "[class*='close']",
            # 弹窗中的取消按钮
            ".ivu-modal-footer button:has-text('取消')",
            ".ivu-modal-footer button.ivu-btn-default",
            ".dialog-footer button:has-text('取消')",
            "button.ivu-btn-default:has-text('取消')",
            # 遮罩层（点击遮罩也可关闭）
            ".ivu-modal-mask",
            ".modal-mask",
        ]
        for sel in dismiss_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    logger.info(f"✓ 已关闭浏览器提示弹窗: {sel}")
                    time.sleep(1)
                    return
            except Exception:
                continue

        # JS 兜底：查找并点击"取消"或关闭弹窗
        try:
            found = page.evaluate("""
                () => {
                    // 策略1: 找"取消"按钮
                    const els = document.querySelectorAll('button, a, span, div');
                    for (const el of els) {
                        const t = el.textContent.trim();
                        if ((t === '取消' || t === '知道了' || t === '确定')
                            && el.offsetParent !== null) {
                            el.click();
                            return t;
                        }
                    }
                    // 策略2: 关闭 modal（点击关闭图标）
                    const closeIcons = document.querySelectorAll('.ivu-icon-ios-close, .ivu-modal-close, [class*="close"]');
                    for (const icon of closeIcons) {
                        if (icon.offsetParent !== null) {
                            icon.click();
                            return 'close-icon';
                        }
                    }
                    // 策略3: 点击遮罩层
                    const masks = document.querySelectorAll('.ivu-modal-mask, .ivu-modal-wrapper');
                    for (const mask of masks) {
                        if (mask.offsetParent !== null && mask.style.display !== 'none') {
                            mask.click();
                            return 'mask';
                        }
                    }
                    return null;
                }
            """)
            if found:
                logger.info(f"✓ JS兜底关闭弹窗: '{found}'")
                time.sleep(1)
                return
        except Exception:
            pass

        logger.info("未检测到浏览器提示弹窗（可能未弹出），继续登录")

    def _switch_to_account_login(self) -> bool:
        """
        从"微信扫码登录"切换到"账号登录"
        页面有两个Tab：微信扫码登录 | 账号登录
        """
        page = self.page

        # 先检查当前是否已经是"账号登录"模式（看密码框是否可见）
        try:
            pwd = page.query_selector("input[type='password']")
            if pwd and pwd.is_visible():
                logger.info("✓ 已在账号登录模式（密码框已可见）")
                return True
        except Exception:
            pass

        # 需要切换：点击"账号登录"Tab
        switch_selectors = [
            # iView Tabs 结构
            ".ivu-tabs-tab:has-text('账号登录')",
            ".ivu-tabs-nav-item:has-text('账号登录')",
            "div.ivu-tabs-tab:has-text('账号')",
            # 文本匹配
            "text=账号登录",
            "div:has-text('账号登录')",
            "span:has-text('账号登录')",
            "a:has-text('账号登录')",
            "[role='tab']:has-text('账号')",
            "li:has-text('账号登录')",
        ]

        for sel in switch_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    logger.info(f"✓ 已切换到账号登录: {sel}")
                    time.sleep(2)
                    return True
            except Exception:
                continue

        # JS 策略1: 精确查找Tab元素
        logger.warning("选择器未找到账号登录Tab，尝试 JS 策略")
        try:
            found = page.evaluate("""
                () => {
                    // 查找文字为"账号登录"的可点击元素（排除大的容器）
                    const allEls = document.querySelectorAll('*');
                    for (const el of allEls) {
                        const t = el.textContent.trim();
                        if (t === '账号登录' && el.offsetParent !== null
                            && el.offsetWidth < 200 && el.offsetWidth > 15) {
                            el.click();
                            return 'found:' + el.tagName;
                        }
                    }
                    // 尝试 ivu-tabs-tab
                    const tabs = document.querySelectorAll('.ivu-tabs-tab');
                    for (const tab of tabs) {
                        if (tab.textContent.includes('账号') && tab.offsetParent !== null) {
                            tab.click();
                            return 'tab:' + tab.textContent.trim();
                        }
                    }
                    return null;
                }
            """)
            if found:
                logger.info(f"✓ JS切换成功: '{found}'")
                time.sleep(2)
                return True
        except Exception:
            pass

        return False

    def _find_and_fill_phone(self, username: str):
        """查找手机号输入框并填写（模拟真实输入+Tab触发Vue验证）"""
        page = self.page

        # 策略1: CSS 选择器（优先找可见的）
        phone_selectors = [
            "input.ivu-input[placeholder*='手机']",
            "input.ivu-input[placeholder*='用户名']",
            "input.ivu-input[placeholder*='账号']",
            ".ivu-input-wrapper input[type='text']",
            "input.ivu-input[type='text']",
            "input[name='mobile']",
            "input[name='phone']",
            "input[name='username']",
            "input[type='tel']",
        ]
        phone_input = None
        for sel in phone_selectors:
            try:
                el = page.query_selector(sel)
                if el:
                    try:
                        is_vis = el.is_visible()
                    except Exception:
                        is_vis = False
                    if is_vis and el.is_enabled():
                        phone_input = el
                        logger.info(f"✓ 找到可见手机号输入框: {sel}")
                        break
            except Exception:
                continue

        # 策略2: Playwright get_by_placeholder
        if not phone_input:
            for ph in ["请输入用户名或手机号", "手机号", "手机", "请输入手机号", "账号", "用户名"]:
                try:
                    loc = page.get_by_placeholder(ph)
                    if loc.count() > 0:
                        el = loc.first
                        if el.is_visible():
                            phone_input = el
                            logger.info(f"✓ get_by_placeholder 找到可见输入框: '{ph}'")
                            break
                except Exception:
                    continue

        if not phone_input:
            logger.error("❌ 所有策略均未找到可见的手机号输入框")
            return None

        # ★ 模拟真实输入：click → clear → type(慢速) → Tab（触发Vue blur/change）
        phone_input.click()
        time.sleep(0.3)
        # 三击选中全部，然后删除
        phone_input.click(click_count=3)
        time.sleep(0.2)
        phone_input.press("Backspace")
        time.sleep(0.2)
        # 使用 type() 慢速逐个输入（模拟真实键盘，触发Vue input事件）
        phone_input.type(username, delay=80)
        logger.info(f"已填写账号: {username}")
        time.sleep(0.3)
        # ★ Tab 切换焦点 → 触发 Vue blur/change 验证
        phone_input.press("Tab")
        time.sleep(0.5)
        return phone_input

    def _find_and_fill_password(self, password: str):
        """查找密码输入框并填写（模拟真实输入+Tab触发Vue验证）"""
        page = self.page
        pwd_input = None
        pwd_selectors = [
            "input.ivu-input[type='password']",
            "input[name='password']",
            "input[name='pwd']",
            "input[type='password']",
            "input[placeholder*='密码']",
            "input[placeholder*='请输入密码']",
        ]
        for sel in pwd_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and el.is_enabled():
                    pwd_input = el
                    logger.info(f"✓ 找到可见密码输入框: {sel}")
                    break
            except Exception:
                continue

        if not pwd_input:
            for ph in ["请输入密码", "密码", "请输入登录密码"]:
                try:
                    loc = page.get_by_placeholder(ph)
                    if loc.count() > 0:
                        el = loc.first
                        if el.is_visible():
                            pwd_input = el
                            logger.info(f"✓ get_by_placeholder 找到密码框: '{ph}'")
                            break
                except Exception:
                    continue

        if not pwd_input:
            logger.error("❌ 所有策略均未找到可见的密码输入框")
            return None

        # ★ 模拟真实输入：click → clear → type(慢速) → Tab（触发Vue blur/change）
        pwd_input.click()
        time.sleep(0.3)
        pwd_input.click(click_count=3)
        time.sleep(0.2)
        pwd_input.press("Backspace")
        time.sleep(0.2)
        pwd_input.type(password, delay=80)
        logger.info("已填写密码")
        time.sleep(0.3)
        pwd_input.press("Tab")
        time.sleep(0.5)
        return pwd_input

    def _check_agreement_checkbox(self) -> None:
        """
        勾选"我已阅读并接受《用户协议》"复选框
        去呼呼登录要求必须勾选协议才能点击登录按钮
        """
        page = self.page
        checkbox_selectors = [
            # iView Checkbox
            ".ivu-checkbox-input",
            "input.ivu-checkbox-input",
            "input[type='checkbox']",
            ".ivu-checkbox",
            # 通用
            "[class*='checkbox']",
            "label:has-text('我已阅读')",
            "label:has-text('用户协议')",
            "span:has-text('我已阅读并接受')",
            # checkbox wrapper
            ".ivu-checkbox-wrapper",
        ]
        for sel in checkbox_selectors:
            try:
                el = page.query_selector(sel)
                if el:
                    # 先尝试点击
                    try:
                        if el.is_visible():
                            # 检查是否已勾选
                            is_checked = el.is_checked() if hasattr(el, 'is_checked') else el.get_attribute("checked") is not None
                            if not is_checked:
                                el.click()
                                logger.info(f"✓ 已勾选协议复选框: {sel}")
                                time.sleep(0.5)
                                return
                            else:
                                logger.info("协议复选框已勾选，跳过")
                                return
                    except Exception:
                        continue
            except Exception:
                continue

        # JS 兜底：查找并勾选协议复选框
        logger.warning("选择器未找到协议复选框，尝试 JS 勾选")
        try:
            checked = page.evaluate("""
                () => {
                    // 找所有 checkbox
                    const checkboxes = document.querySelectorAll(
                        'input[type="checkbox"], .ivu-checkbox-input, [class*="checkbox"]'
                    );
                    for (const cb of checkboxes) {
                        // 检查附近文本是否包含协议关键词
                        const parent = cb.closest('label, .ivu-checkbox-wrapper, div');
                        const text = (parent || cb.parentElement || document.body).innerText || '';
                        if (text.includes('我已阅读') || text.includes('用户协议')
                            || text.includes('委托处理') || text.includes('接受')) {
                            if (!cb.checked) {
                                cb.click();
                                // 也尝试触发 change 事件
                                cb.dispatchEvent(new Event('change', { bubbles: true }));
                                cb.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                return 'checked';
                            }
                            return 'already-checked';
                        }
                    }
                    // 策略2: 查找包含协议文本的 label
                    const labels = document.querySelectorAll('label, span');
                    for (const lbl of labels) {
                        if (lbl.textContent.includes('我已阅读并接受')) {
                            const cb = lbl.querySelector('input[type="checkbox"]');
                            if (cb && !cb.checked) {
                                cb.click();
                                return 'label-checked';
                            }
                        }
                    }
                    // 策略3: 直接勾选所有可见 checkbox
                    const visCheckboxes = document.querySelectorAll('input[type="checkbox"]');
                    for (const cb of visCheckboxes) {
                        if (cb.offsetParent !== null && !cb.checked) {
                            cb.click();
                            return 'any-checked';
                        }
                    }
                    return null;
                }
            """)
            if checked:
                logger.info(f"✓ JS勾选协议成功: {checked}")
                time.sleep(0.5)
                return
        except Exception as e:
            logger.error(f"JS勾选协议失败: {e}")

        logger.warning("⚠ 未找到协议复选框，尝试直接登录")

    def _agree_protocol_popup(self) -> bool:
        """
        处理登录后弹出的第二个协议确认弹窗
        "请您阅读并同意以下协议... [不同意] [同意]"
        必须点击"同意"才能解除登录拦截
        :return: True 表示检测到并处理了弹窗
        """
        page = self.page
        try:
            # 检测弹窗是否存在
            body = page.evaluate("() => document.body.innerText || ''")
            if "请您阅读并同意以下协议" not in body:
                return False

            logger.info("检测到协议确认弹窗，点击'同意'...")

            agree_selectors = [
                "button:has-text('同意')",
                "button.ivu-btn:has-text('同意')",
                "button.ivu-btn-primary:has-text('同意')",
                "span:has-text('同意')",
                "div:has-text('同意')",
                "a:has-text('同意')",
                "text=同意",
                ".ivu-modal-footer button.ivu-btn-primary",
                ".ivu-modal-footer button:has-text('同意')",
            ]
            for sel in agree_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        logger.info(f"✓ 已点击'同意': {sel}")
                        time.sleep(2)
                        return True
                except Exception:
                    continue

            # JS 兜底
            page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, span, a, div');
                    for (const b of btns) {
                        if (b.textContent.trim() === '同意' && b.offsetParent !== null
                            && b.offsetWidth < 150 && b.offsetWidth > 20) {
                            b.click();
                            return;
                        }
                    }
                }
            """)
            logger.info("✓ JS兜底点击'同意'")
            time.sleep(2)
            return True
        except Exception as e:
            logger.debug(f"协议弹窗处理跳过: {e}")
            return False

    def _click_login_button(self, fallback_input=None) -> bool:
        """查找并点击登录按钮"""
        page = self.page
        clicked = False
        btn_selectors = [
            "button.ivu-btn:has-text('登录')",
            "button.ivu-btn-primary:has-text('登录')",
            "button.ivu-btn-large:has-text('登录')",
            "button.ivu-btn:has-text('登 录')",
            "button:has-text('登录')",
            "button:has-text('登 录')",
            "button:has-text('立即登录')",
            "input[type='submit'][value='登录']",
            "input[value='登录']",
            "button[type='submit']",
            ".login-btn",
            ".submit-btn",
            ".btn-login",
            "[class*='login-btn']",
            "[class*='submit']",
        ]
        for sel in btn_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    btn.click()
                    logger.info(f"✓ 点击登录按钮: {sel}")
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            # JS 兜底
            logger.warning("选择器未找到登录按钮，尝试 JS 点击")
            try:
                found = page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button, input[type=submit], a');
                        for (const b of btns) {
                            if ((b.textContent.includes('登录') || b.value === '登录')
                                && b.offsetParent !== null && !b.disabled) {
                                b.click();
                                return b.textContent.trim();
                            }
                        }
                        return null;
                    }
                """)
                if found:
                    logger.info(f"✓ JS兜底点击登录按钮: '{found}'")
                    clicked = True
                elif fallback_input:
                    fallback_input.press("Enter")
                    logger.info("使用回车键提交登录")
                    clicked = True
            except Exception:
                if fallback_input:
                    fallback_input.press("Enter")
                    logger.info("使用回车键提交登录")
                    clicked = True

        return clicked

    def _check_login_result(self) -> bool:
        """检查登录是否成功"""
        page = self.page
        current_url = page.url
        page_title = page.title()
        logger.info(f"登录后 URL: {current_url}")
        logger.info(f"登录后页面标题: {page_title}")

        # 诊断：输出页面上所有可见文本（前500字）
        try:
            body_text = page.evaluate("() => document.body.innerText.substring(0, 500)")
            if body_text:
                logger.info(f"页面文本片段: {body_text[:300]}")
        except Exception:
            pass

        # 成功：进入 kz.quhuhu.com 的房间管理或首页
        success_indicators = [
            "kz.quhuhu.com",
            "/rooms", "/table", "/main", "/index", "/home", "/report",
        ]
        is_success = any(ind in current_url for ind in success_indicators) and "login" not in current_url.lower()

        if is_success:
            self._pending_cookies = json.dumps(self.context.cookies())
            logger.info("✅ 去呼呼登录成功!")
            return True

        # 检查错误提示
        error_selectors = [
            ".ivu-message-error", ".ivu-message-notice",
            ".error-msg", ".errmsg",
            "[class*='error']", "[class*='Error']",
            ".ant-message-error", ".el-message--error",
        ]
        for es in error_selectors:
            try:
                err = page.query_selector(es)
                if err and err.is_visible():
                    txt = err.inner_text()
                    logger.error(f"❌ 登录失败，页面提示: {txt}")
                    return False
            except Exception:
                continue

        error_texts = [
            "密码错误", "账号不存在", "账号或密码错误",
            "验证码", "登录失败", "用户名或密码错误",
            "请先输入", "请输入手机号", "手机号格式",
        ]
        for et in error_texts:
            try:
                el = page.query_selector(f"text={et}")
                if el and el.is_visible():
                    logger.error(f"❌ 登录失败，页面提示: {et}")
                    return False
            except Exception:
                continue

        # 检查是否仍在登录页（可能有未触发的表单验证）
        if "login" in current_url.lower():
            # 尝试检测是否有表单验证错误（iView Form 验证）
            try:
                has_error = page.evaluate("""
                    () => {
                        // iView 表单验证错误
                        const errTips = document.querySelectorAll(
                            '.ivu-form-item-error-tip, .ivu-tooltip-inner, ' +
                            '.ivu-input-group-error, [class*="error"]'
                        );
                        for (const e of errTips) {
                            if (e.offsetParent !== null && e.textContent.trim()) {
                                return e.textContent.trim();
                            }
                        }
                        return null;
                    }
                """)
                if has_error:
                    logger.error(f"❌ 表单验证错误: {has_error}")
                    return False
            except Exception:
                pass

        logger.warning(f"⚠ 登录后 URL 未包含预期关键词，当前: {current_url}")
        return False

    def _select_product(self) -> None:
        """
        SSO登录成功后，可能需要选择产品入口
        三个产品：去呼呼客栈管家 | 去呼呼酒店管家 | 去呼呼集团管家
        点击"去呼呼客栈管家"进入 kz.quhuhu.com
        """
        page = self.page
        current_url = page.url

        # 只有域名真正是 kz.quhuhu.com 才跳过（排除 retUrl 参数里的匹配）
        from urllib.parse import urlparse
        host = urlparse(current_url).hostname or ""
        if host == "kz.quhuhu.com" or host.endswith(".kz.quhuhu.com"):
            logger.info("✓ 已在客栈管家系统，无需选择产品")
            return

        # 检测页面是否包含三个产品入口
        try:
            body_text = page.evaluate("() => document.body.innerText || ''")
            has_product_page = all(kw in body_text for kw in ["客栈管家", "酒店管家", "集团管家"])
            if not has_product_page:
                logger.info("未检测到产品选择页，跳过")
                return
        except Exception:
            pass

        logger.info("检测到产品选择页，正在选择'去呼呼客栈管家'...")

        product_selectors = [
            "a:has-text('去呼呼客栈管家')",
            "div:has-text('去呼呼客栈管家')",
            "span:has-text('去呼呼客栈管家')",
            "text=去呼呼客栈管家",
            "a:has-text('客栈管家')",
            "div:has-text('客栈管家')",
            "span:has-text('客栈管家')",
            ".product-item:has-text('客栈')",
            "[class*='product']:has-text('客栈')",
        ]
        for sel in product_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    logger.info(f"✓ 已点击'去呼呼客栈管家': {sel}")
                    time.sleep(3)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(2)
                    logger.info(f"产品选择后 URL: {page.url}")
                    return
            except Exception:
                continue

        # JS 兜底
        logger.warning("选择器未找到产品入口，尝试 JS 点击")
        try:
            found = page.evaluate("""
                () => {
                    const els = document.querySelectorAll('a, div, span, button');
                    for (const el of els) {
                        const t = el.textContent.trim();
                        if ((t.includes('客栈管家') || t.includes('去呼呼客栈'))
                            && el.offsetParent !== null
                            && el.offsetWidth < 400 && el.offsetWidth > 30) {
                            el.click();
                            return t;
                        }
                    }
                    return null;
                }
            """)
            if found:
                logger.info(f"✓ JS点击产品入口: '{found}'")
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"产品选择失败: {e}")

    # =============================================================
    # 报表页面交互（按用户截图红框标注的步骤实现）
    # 图1: 日期下拉→选「今天」→点「查询」(营业收入tab)
    # 图2-4: 切换Tab → 点「导出」
    # 查询共享，各Tab直接导出
    # =============================================================

    TAB_MAP = {
        "daily_room":    "日租房概况",
        "hourly_room":   "钟点房概况",
        "other_consume": "其他消费概况",
        "income_check":  "营业收入",
    }

    def _setup_report_page(self) -> bool:
        """
        图1: 导航→点日期下拉→选「今天」→点「查询」
        查询一次，所有Tab共享结果。
        """
        page = self.page
        try:
            report_url = "http://kz.quhuhu.com/v2/report/guestRoom.htm"
            page.goto(report_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            self._save_debug_screenshot("08_report_landed.png")

            # 点日期输入框→下拉面板→选「今天」
            self._click_today()
            time.sleep(0.5)

            # 点「查询」
            self._click_button("查询")
            time.sleep(2)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(1)
            self._save_debug_screenshot("08_queried.png")
            logger.info("✓ 报表页就绪（今天+已查询）")
            return True
        except Exception as e:
            logger.error(f"报表页初始化失败: {e}")
            return False

    def _export_one_tab(self, report_type: str, target_date: str) -> Optional[str]:
        """
        图2-4: 切换Tab → 直接导出（日期和查询已在上一步完成，共享）
        """
        tab_name = self.TAB_MAP.get(report_type, report_type)
        self._click_tab(tab_name)
        time.sleep(1.5)
        self._save_debug_screenshot(f"09_{report_type}_tab.png")
        return self._click_export(report_type, target_date) or \
               self._js_export(report_type, target_date)

    def _click_today(self) -> bool:
        """
        步骤1: 点击日期输入框 → 打开下拉面板 → 点击「今天」
        去呼呼使用 iView DatePicker，预设选项在下拉面板中
        """
        page = self.page
        try:
            # 先点日期输入框，打开下拉面板
            # iView DatePicker 的 input 在 .ivu-date-picker 或直接是 input
            date_inputs = page.locator(".ivu-date-picker input.ivu-input, .ivu-date-editor input").all()
            if not date_inputs:
                date_inputs = page.locator("input.ivu-input[type='text']").all()
            
            if date_inputs:
                date_inputs[0].click()
                time.sleep(0.5)
                logger.info("已点击日期输入框，等待下拉面板...")
            else:
                logger.warning("未找到日期输入框")
                return False

            # 下拉面板出现后，点击「今天」
            # 下拉面板通常在 .ivu-picker-panel 或 .ivu-date-picker 的弹出层中
            for sel in [
                ".ivu-picker-panel .ivu-btn:has-text('今天')",
                ".ivu-date-picker-dropdown span:has-text('今天')",
                ".ivu-select-dropdown span:has-text('今天')",
                "span:has-text('今天')",
                "em:has-text('今天')",
            ]:
                try:
                    el = page.locator(sel).first
                    if el and el.is_visible(timeout=2000):
                        el.click()
                        logger.info(f"✓ 已点击「今天」: {sel}")
                        time.sleep(0.5)
                        return True
                except Exception:
                    continue

            # JS 兜底：在下拉面板中找"今天"
            page.evaluate("""() => {
                const panels = document.querySelectorAll('.ivu-picker-panel, .ivu-date-picker-dropdown, .ivu-select-dropdown, .ivu-dropdown');
                for (const panel of panels) {
                    if (panel.offsetParent) {
                        const all = panel.querySelectorAll('span, em, button, li, div');
                        for (const el of all) {
                            if (el.textContent.trim() === '今天' && el.offsetParent) {
                                el.click();
                                return;
                            }
                        }
                    }
                }
            }""")
            logger.info("✓ JS点击「今天」")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"点击「今天」失败: {e}")
            return False

    def _click_tab(self, tab_name: str) -> bool:
        """点击Tab标签。优先用 iView 的 tabs-tab 选择器。"""
        page = self.page
        selectors = [
            f".ivu-tabs-tab:has-text('{tab_name}')",
            f"[role='tab']:has-text('{tab_name}')",
            f".ivu-tabs-nav .ivu-tabs-tab:has-text('{tab_name}')",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el and el.is_visible(timeout=3000):
                    el.click()
                    logger.info(f"✓ Tab[{tab_name}]: {sel}")
                    return True
            except Exception:
                continue

        # JS 兜底
        try:
            page.evaluate(f"""(tab) => {{
                for (const el of document.querySelectorAll('.ivu-tabs-tab, [role=tab], div, span')) {{
                    if (el.textContent.includes(tab) && el.offsetParent) {{
                        el.click(); return;
                    }}
                }}
            }}""", tab_name)
            logger.info(f"✓ Tab[{tab_name}]: JS")
            return True
        except Exception:
            pass
        logger.warning(f"✗ Tab未找到: {tab_name}")
        return False

    def _click_button(self, text: str) -> bool:
        """点击页面按钮（查询/导出等）。"""
        page = self.page
        # 优先找绿色主按钮（ivu-btn-primary）
        for sel in [
            f"button.ivu-btn-primary:has-text('{text}')",
            f"button.ivu-btn:has-text('{text}')",
            f"button:has-text('{text}')",
            f"span:has-text('{text}')",
        ]:
            try:
                el = page.locator(sel).first
                if el and el.is_visible(timeout=3000):
                    el.click()
                    logger.info(f"✓ 按钮[{text}]: {sel}")
                    return True
            except Exception:
                continue

        # JS 兜底
        try:
            page.evaluate(f"""(t) => {{
                for (const b of document.querySelectorAll('button')) {{
                    if (b.textContent.includes(t) && b.offsetParent) {{ b.click(); return; }}
                }}
            }}""", text)
            logger.info(f"✓ 按钮[{text}]: JS")
            return True
        except Exception:
            pass
        logger.warning(f"✗ 按钮未找到: {text}")
        return False

    def _click_export(self, report_type: str, target_date: str) -> Optional[str]:
        """点击导出按钮并通过Playwright拦截下载。"""
        page = self.page
        for sel in [
            "button.ivu-btn:has-text('导出')",
            "button:has-text('导出')",
            "span:has-text('导出')",
        ]:
            try:
                loc = page.locator(sel)
                cnt = loc.count()
                if cnt == 0:
                    continue
                # 从后往前找第一个可见的（导出按钮在最右侧）
                for i in range(cnt - 1, -1, -1):
                    btn = loc.nth(i)
                    if btn.is_visible():
                        with page.expect_download(timeout=60000) as dl_info:
                            btn.click()
                        download = dl_info.value
                        save_path = os.path.join(IMPORT_DIR,
                            f"quhuhu_{report_type}_{target_date}.xlsx")
                        download.save_as(save_path)
                        logger.info(f"✓ 下载: {save_path}")
                        return save_path
            except Exception:
                continue
        return None

    def _js_export(self, report_type: str, target_date: str) -> Optional[str]:
        """JS触发导出 + 监听下载事件兜底。"""
        page = self.page
        try:
            # 设置下载监听
            dl_promise = page.wait_for_event("download", timeout=30000)
            page.evaluate("""() => {
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent.includes('导出') && b.offsetParent) {
                        b.click(); return;
                    }
                }
            }""")
            download = dl_promise
            save_path = os.path.join(IMPORT_DIR,
                f"quhuhu_{report_type}_{target_date}.xlsx")
            download.save_as(save_path)
            logger.info(f"✓ JS下载: {save_path}")
            return save_path
        except Exception as e:
            logger.warning(f"JS导出失败: {e}")
            return None
            pass

        logger.warning(f"  导出失败，尝试抓表格: {report_type}")
        return self._fallback_table_capture(report_type, target_date)

    # =============================================================
    # 纯API直连采集（无需浏览器！）
    # 发现: 导出就是一条GET请求 + Cookie，queryType任意值返回同一份明细
    # =============================================================

    EXPORT_API = "https://kz.quhuhu.com/v2/c/api/export/hotelIncomeStatus.do"
    CHANNEL_API = "https://kz.quhuhu.com/v2/c/api/export/channelOrderSummary.do"
    HOTEL_NO = "hotel17873063584414"

    def _api_collect_channels(self, target_date: str) -> Dict:
        """
        客源统计API：导出渠道订单汇总（携程/美团/线下客人）
        :return: {channels: [...], total_online_revenue, total_offline_revenue}
        """
        result = {"channels": [], "online_revenue": 0.0, "offline_revenue": 0.0}
        try:
            cookie_str = self._load_cookie_string()
            if not cookie_str:
                return result

            params = {
                'hotelNo': self.HOTEL_NO,
                'beginTime': f'{target_date} 00:00:00',
                'endTime': f'{target_date} 23:59:59',
                'channelCode': '',
                'payTypeCode': '',
            }
            url = self.CHANNEL_API + '?' + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={
                'Cookie': cookie_str,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            })
            resp = urllib.request.urlopen(req, timeout=30)
            data = resp.read()

            if len(data) < 200:
                return result

            import pandas as pd
            from io import BytesIO
            df = pd.read_excel(BytesIO(data), header=None)

            for i in range(1, len(df)):
                row = df.iloc[i]
                channel_name = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                pay_type = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                orders = int(float(str(row.iloc[2]))) if pd.notna(row.iloc[2]) else 0
                room_nights = float(str(row.iloc[3])) if pd.notna(row.iloc[3]) else 0
                revenue = float(str(row.iloc[6])) if pd.notna(row.iloc[6]) else 0.0

                ch = {
                    "channel": channel_name,
                    "pay_type": pay_type,
                    "orders": orders,
                    "room_nights": room_nights,
                    "revenue": revenue,
                }
                result["channels"].append(ch)

                if "线下" in channel_name or "现付" in pay_type:
                    result["offline_revenue"] += revenue
                else:
                    result["online_revenue"] += revenue

            logger.info(f"客源统计: 线上¥{result['online_revenue']}, 线下¥{result['offline_revenue']}")
        except Exception as e:
            logger.warning(f"客源统计API失败: {e}")
        return result

    def _load_cookie_string(self) -> Optional[str]:
        """从数据库加载Cookie字符串"""
        try:
            import sqlite3
            from app.constants import DB_FILE
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
            row = c.fetchone()
            conn.close()
            if not row:
                return None
            cookies_list = json.loads(row[0])
            return '; '.join([f"{c['name']}={c['value']}" for c in cookies_list])
        except Exception as e:
            logger.error(f"读取Cookie失败: {e}")
            return None

    def _api_collect(self, target_date: str, pay_type: str = "") -> Optional[str]:
        """单日导出"""
        return self._api_collect_by_range(target_date, target_date, pay_type)

    def _api_collect_by_range(self, start_date: str, end_date: str, pay_type: str = "") -> Optional[str]:
        """
        纯HTTP API导出客房销售明细Excel（支持日期范围）
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param pay_type: 支付类型，空=全部，tyf=全额预付，xf=到店现付
        """
        import urllib.request, urllib.error

        cookie_str = self._load_cookie_string()
        if not cookie_str:
            return None

        # 将中文配置值转为API需要的值
        order_status = self._cfg("order_status", "")
        if order_status in ("全部", ""):
            order_status = ""  # 空=全部
        
        params = {
            'hotelNo': self.HOTEL_NO,
            'queryType': 'business',
            'queryChannel': 'false',
            'startDate': f'{start_date} 00:00:00',
            'endDate': f'{end_date} 23:59:00',
            'payType': pay_type,
            'orderStatus': order_status,
            'queryPaymentReceived': 'false',
        }
        url = self.EXPORT_API + '?' + urllib.parse.urlencode(params)

        try:
            req = urllib.request.Request(url, headers={
                'Cookie': cookie_str,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            })
            resp = urllib.request.urlopen(req, timeout=30)
            data = resp.read()

            if len(data) < 500 or data[:2] != b'\xd0\xcf':
                logger.error(f"API返回非Excel: {len(data)} bytes")
                return None

            os.makedirs(IMPORT_DIR, exist_ok=True)
            suffix = pay_type or 'all'
            save_path = os.path.join(IMPORT_DIR, f"quhuhu_{start_date}_{end_date}_{suffix}.xls")
            with open(save_path, 'wb') as f:
                f.write(data)
            logger.info(f"✓ API导出({start_date}~{end_date}): {len(data)} bytes")
            return save_path
        except Exception as e:
            logger.error(f"API导出失败: {e}")
            return None

    def collect(self, target_date: str = "", data_hour: int = None) -> Dict:
        """
        执行自动采集（优先API直连）
        :param target_date: 采集日期，默认今天
        :param data_hour: 数据小时，不传则按当前时间自动判断
        """
        now = datetime.now(TZ)
        if not target_date:
            target_date = now.strftime("%Y-%m-%d")
        
        # 自动确定入库小时
        if data_hour is None:
            if now.hour == 0:
                # 凌晨0点：如用户选的是"今天"，实际应结算昨天h24
                today_str = now.strftime("%Y-%m-%d")
                if target_date == today_str:
                    target_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                data_hour = 24
            else:
                data_hour = now.hour

        result = {
            "success": False, "date": target_date,
            "reports": [], "errors": [],
            "total_sold": 0, "total_revenue": 0.0,
            "income_check": None,
        }

        self._preload_config()
        dev_mode = self._cfg("dev_mode", "0") == "1"

        try:
            # ===== 方式1: API直连（秒级完成，无浏览器）=====
            logger.info(f"API采集: {target_date}")

            # 调用1: 全部支付类型 → 总房间数 + 总房费
            file_all = self._api_collect(target_date, pay_type="")
            if not file_all:
                logger.warning("API全部数据导出失败")
                result["errors"].append("API导出失败")
                return result

            # 调用2: 全额预付(tyf)→ OTA起售价（排除线下到店现付）
            ota_min_price = 0.0
            file_ota = self._api_collect(target_date, pay_type="tyf")
            if file_ota:
                _, ota_cleaned, _ = self._cleaner.parse_excel(file_ota)
                ota_min_price = ota_cleaned.get("min_price", 0.0)
                logger.info(f"OTA起售价(全额预付): ¥{ota_min_price}")

            # 解析全部数据
            _, cleaned, clean_errors = self._cleaner.parse_excel(file_all)
            if clean_errors:
                logger.warning(f"解析警告: {clean_errors}")

            total_rooms = cleaned.get("room_count", 0)
            total_fee = cleaned.get("total_fee", 0.0)
            # ★ 起售价格优先级：手动填入 > 美团浏览器采集 > 去呼呼全部最低
            quhuhu_all_min = cleaned.get("min_price", 0.0)
            min_price = quhuhu_all_min
            price_source = "去呼呼(全部)"
            mt_price = None  # 初始化为None，避免未绑定错误

            # 1) 手动填入的美团底价（最优先，跳过浏览器）
            manual_price = self._cfg("meituan_manual_price", "").strip()
            if manual_price:
                try:
                    mp = float(manual_price)
                    if mp > 0:
                        min_price = mp
                        price_source = "美团(手动)"
                        logger.info(f"✅ 使用手动美团底价: ¥{mp}")
                except ValueError:
                    pass

            # 1.5) 检查当天是否已有手动设定的小时价格（保护手动更新）
            if price_source != "美团(手动)":
                from app.db.database import get_connection as _gc
                _conn = _gc()
                try:
                    _c = _conn.cursor()
                    _c.execute("SELECT min_price FROM hourly_data WHERE data_date=? AND data_source>=2 AND min_price>0 LIMIT 1",
                               (target_date,))
                    _row = _c.fetchone()
                    if _row:
                        min_price = _row["min_price"]
                        price_source = "手动(保护)"
                        logger.info(f"✅ 保护手动价格: ¥{min_price}")
                except Exception:
                    pass
                finally:
                    _conn.close()

            # 2) 浏览器自动化采集（手动价未填时尝试）
            if price_source == "去呼呼(全部)":
                mt_price = fetch_meituan_min_price(target_date)
                if mt_price and mt_price > 0:
                    logger.info(f"✅ 美团底价({target_date}): ¥{mt_price} (去呼呼: ¥{quhuhu_all_min}, OTA: ¥{ota_min_price})")
                    min_price = mt_price
                    price_source = "美团"
                else:
                    logger.info(f"美团底价未获取，使用去呼呼全部订单最低价: ¥{min_price} (OTA全额预付: ¥{ota_min_price})")

            logger.info(f"=== 采集结果: 房间={total_rooms}, 房费=¥{total_fee}, 起售价[{price_source}]=¥{min_price} ===")

            # ===== 对账（开发模式）=====
            if dev_mode:
                result["income_check"] = {
                    "income_amount": total_fee,
                    "calculated_fee": total_fee,
                    "difference": 0.0,
                    "diff_percent": 0.0,
                    "is_match": True,
                    "ota_price": ota_min_price,     # 全额预付参考价
                    "quhuhu_price": quhuhu_all_min, # 去呼呼全部最低价
                    "meituan_price": mt_price,       # 美团底价
                    "price_source": price_source,
                }

            # ===== 数据入库 =====
            # 始终写入数据（即使0间0收入），确保每小时都有记录
            # store_hour 和 target_date 已在函数开头确定
            store_hour = data_hour
            
            hd = calc_hourly(total_rooms, total_fee, min_price)
            with db_transaction() as conn:
                c = conn.cursor()
                # 检查是否已有手动数据，保护不被自动采集覆盖
                c.execute("SELECT data_source, min_price FROM hourly_data WHERE data_date=? AND data_hour=?",
                          (target_date, store_hour))
                existing = c.fetchone()
                ds = DataSource.AUTO_IMPORT
                final_price = hd["min_price"]
                if existing:
                    if existing["data_source"] and existing["data_source"] >= 2:
                        ds = existing["data_source"]  # 保留手动标记
                    # 如果有手动设置的价格且高于自动采集的，保留手动价
                    if existing["min_price"] and existing["min_price"] > 0 and ds >= 2:
                        final_price = existing["min_price"]
                c.execute(
                    """INSERT OR REPLACE INTO hourly_data
                       (data_date, data_hour, sold_rooms, available_rooms,
                        occupancy_rate, min_price, revpar, total_revenue, adr, data_source)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (target_date, store_hour, hd["sold_rooms"], hd["available_rooms"],
                     hd["occupancy_rate"], final_price, hd["revpar"],
                     hd["total_revenue"], hd["adr"], ds)
                )
                c.execute(
                    "INSERT INTO import_record (file_name, report_type, data_date, import_status) VALUES (?,?,?,1)",
                    (f"API采集_{target_date}", "auto_collect", target_date)
                )
            daily_aggregate(target_date)
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            monthly_aggregate_for_month(dt.year, dt.month)

            result["total_sold"] = total_rooms
            result["total_revenue"] = total_fee
            result["success"] = True
            result["reports"].append({
                "type": "api_export", "name": "客房销售明细", "status": "success", "data": cleaned
            })
            logger.info(f"✅ 采集完成: {target_date}, 房间{total_rooms}, 房费¥{total_fee}")

        except Exception as e:
            logger.error(f"采集异常: {e}", exc_info=True)
            result["errors"].append(str(e))
        finally:
            self._close_browser()

        return result


_collector: Optional[QuhuhuCollector] = None
import threading
_collector_lock = threading.Lock()  # 线程安全互斥锁


def get_collector() -> QuhuhuCollector:
    """每次创建新的采集器实例（避免并发冲突）"""
    return QuhuhuCollector()


def auto_collect(date: str = "", data_hour: int = None) -> Dict:
    """自动采集入口，带并发锁保护（最多等待30秒）"""
    acquired = _collector_lock.acquire(timeout=30)
    if not acquired:
        return {"success": False, "date": date, "errors": ["采集任务超时（上轮>30秒未完成），请稍后再试"]}
    try:
        collector = QuhuhuCollector()
        return collector.collect(date, data_hour)
    finally:
        _collector_lock.release()
