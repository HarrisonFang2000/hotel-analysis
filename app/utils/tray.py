"""
系统托盘实现
后端服务独立运行，关闭浏览器不影响数据采集和定时任务
"""
import os
import webbrowser
import pystray
from PIL import Image
import threading
from typing import Callable

from app.constants import DEFAULT_PORT


class SystemTray:
    """系统托盘类"""
    
    def __init__(self, on_restart: Callable = None, on_exit: Callable = None):
        self.on_restart = on_restart
        self.on_exit = on_exit
        self.icon = None
        self.port = DEFAULT_PORT
    
    def _open_browser(self, icon, item):
        """打开系统页面"""
        try:
            webbrowser.open(f"http://127.0.0.1:{self.port}")
        except Exception:
            os.startfile(f"http://127.0.0.1:{self.port}")
    
    def _open_data_dir(self, icon, item):
        """打开数据目录"""
        from app.constants import DATA_DIR
        os.startfile(DATA_DIR)
    
    def _show_info(self, icon, item):
        """显示使用提示"""
        icon.notify(
            "后端服务在后台持续运行中\n"
            "• 关闭浏览器 ≠ 关闭系统\n"
            "• 数据采集和定时任务不受影响\n"
            "• 右键托盘 →「打开系统页面」可随时恢复\n"
            "• 右键托盘 →「退出系统」可完全关闭",
            title="酒店数据分析系统 — 使用提示"
        )
    
    def _restart(self, icon, item):
        """重启服务"""
        if self.on_restart:
            threading.Thread(target=self.on_restart, daemon=True).start()
    
    def _exit(self, icon, item):
        """退出程序"""
        if self.on_exit:
            self.on_exit()
        icon.stop()
    
    def _create_image(self):
        """创建托盘图标（PNG→ICO→蓝色方块递次回退）"""
        import sys
        search_names = ['app_icon.png', 'app_icon.ico']
        search_paths = []
        
        if getattr(sys, 'frozen', False):
            for name in search_names:
                search_paths.append(os.path.join(sys._MEIPASS, name))
        
        # 开发模式路径
        dev_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for name in search_names:
            search_paths.append(os.path.join(dev_root, name))
        
        # 额外回退：EXE同目录
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            for name in search_names:
                search_paths.append(os.path.join(exe_dir, name))
        
        for path in search_paths:
            if path and os.path.exists(path):
                try:
                    img = Image.open(path)
                    # 托盘图标不需要太大，缩放到合适尺寸
                    img = img.resize((64, 64), Image.LANCZOS)
                    # 确保 RGBA 模式
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    return img
                except Exception:
                    pass
        
        # 最终回退：蓝色方块
        return Image.new('RGB', (64, 64), (22, 119, 255))
    
    def run(self, port: int = DEFAULT_PORT):
        """运行托盘"""
        self.port = port
        image = self._create_image()
        
        menu = pystray.Menu(
            pystray.MenuItem("打开系统页面", self._open_browser, default=True),
            pystray.MenuItem("打开数据目录", self._open_data_dir),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("💡 使用提示", self._show_info),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("重启服务", self._restart),
            pystray.MenuItem("退出系统", self._exit)
        )
        
        self.icon = pystray.Icon(
            "hotel_analysis",
            image,
            f"酒店数据分析系统 (端口:{port})",
            menu
        )
        
        # 在独立线程中启动托盘（后台运行，不阻塞主程序）
        def _run_tray():
            try:
                self.icon.run()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"托盘图标启动失败: {e}")
        
        threading.Thread(target=_run_tray, daemon=True).start()
        import logging
        logging.getLogger(__name__).info(f"系统托盘已启动 (端口:{port})")
    
    def startup_notify(self):
        """启动后显示通知气泡（延迟调用，等托盘就绪）"""
        def _notify():
            import time
            time.sleep(1.5)
            try:
                if self.icon:
                    self.icon.notify(
                        f"系统已启动成功！\n访问地址：http://127.0.0.1:{self.port}\n右键托盘图标可进行更多操作",
                        title="酒店数据分析系统"
                    )
            except Exception:
                pass
        threading.Thread(target=_notify, daemon=True).start()
    
    def stop(self):
        """停止托盘"""
        if self.icon:
            try:
                self.icon.stop()
            except:
                pass
