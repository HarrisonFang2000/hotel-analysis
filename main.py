"""
程序主入口
启动顺序：单实例锁检查 → 目录初始化 → 数据库初始化 → 定时任务启动 → FastAPI服务启动 → 托盘启动 → 自动打开浏览器
"""
import os
import sys
import uvicorn
import webbrowser
import threading
import time

from app.utils.single_instance import SingleInstance
from app.db.database import init_database
from app.core.scheduler import init_scheduler
from app.utils.backup import backup_database
from app.utils.logger import get_logger
from app.utils.tray import SystemTray
from app.api.router import create_app
from app.constants import DATA_DIR, IMPORT_DIR, EXPORT_DIR, BACKUP_DIR, LOG_DIR, DEFAULT_PORT

logger = get_logger(__name__)


def init_dirs() -> None:
    """初始化所有数据目录"""
    for d in [DATA_DIR, IMPORT_DIR, EXPORT_DIR, BACKUP_DIR, LOG_DIR]:
        os.makedirs(d, exist_ok=True)


def init_config() -> None:
    """首次启动时将默认配置模板复制到data目录"""
    from app.constants import CONFIG_FILE
    if not os.path.exists(CONFIG_FILE):
        # PyInstaller打包后文件在sys._MEIPASS中，开发模式在根目录
        if getattr(sys, 'frozen', False):
            default_config = os.path.join(sys._MEIPASS, "config.default.ini")
        else:
            default_config = os.path.join(os.path.dirname(__file__), "config.default.ini")
        if os.path.exists(default_config):
            import shutil
            shutil.copy(default_config, CONFIG_FILE)
            logger.info("默认配置文件已复制到data目录")


def open_browser(port: int) -> None:
    """延迟3秒打开浏览器，多重回退确保打开"""
    time.sleep(3)
    url = f"http://127.0.0.1:{port}"
    # 方法1：webbrowser.open
    try:
        if webbrowser.open(url):
            return
    except Exception:
        pass
    # 方法2：os.startfile（Windows 默认浏览器）
    try:
        os.startfile(url)
        return
    except Exception:
        pass
    # 方法3：直接调 Chrome/Edge
    for browser in ["chrome", "msedge"]:
        try:
            import subprocess
            subprocess.Popen([browser, url], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
    logger.warning("无法自动打开浏览器，请手动访问：" + url)


def print_banner():
    """打印启动横幅"""
    print("""
╔══════════════════════════════════════╗
║     酒店数据分析系统 v0.9.0          ║
║     苏季酒店 · 去呼呼PMS             ║
╚══════════════════════════════════════╝
""")


def main() -> None:
    """主函数"""
    # 命令行参数
    if '--setup' in sys.argv:
        run_setup_mode()
        return
    if '--diagnose' in sys.argv:
        run_diagnose_mode()
        return
    if '--version' in sys.argv:
        print('v0.9.0')
        return
    
    # 安静模式启动——快速诊断，仅致命错误才中断
    from app.utils.installer import run_diagnostics, check_permissions, ensure_directories, check_port
    
    # 权限检查（致命）
    perm = check_permissions()
    if perm['status'] == 'error':
        msg = f"启动失败：{perm['message']}\n请将程序移到非系统目录（如D:\\）"
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "酒店数据分析系统", 0x10)
        except:
            print(msg)
        sys.exit(1)
    
    # 目录和配置初始化
    ensure_directories()
    from app.utils.installer import ensure_config
    ensure_config()
    
    # 数据库初始化（已有数据时只执行迁移，不覆盖）
    try:
        from app.db.database import init_database
        from app.constants import DB_FILE
        db_existed = os.path.exists(DB_FILE)
        init_database()
        if db_existed:
            logger.info("数据库已存在，仅执行迁移检查（数据未受影响）")
        else:
            logger.info("首次运行，数据库已初始化")
    except Exception as e:
        print(f"\n⚠️ 数据库初始化: {e}")
    
    # 1. 单实例锁检查
    instance = SingleInstance()
    if not instance.acquire():
        logger.error("程序已经在运行，请勿重复启动")
        # 尝试打开已运行实例的页面
        try:
            webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}")
        except Exception:
            try:
                os.startfile(f"http://127.0.0.1:{DEFAULT_PORT}")
            except Exception:
                pass
        # 弹窗提示用户
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,
                "酒店数据分析系统已在运行中！\n\n"
                "请查看系统托盘（任务栏右下角）的图标，\n"
                "右键点击可打开系统页面。\n\n"
                "如系统无响应，请在任务管理器中\n"
                "结束「酒店数据分析系统」进程后重试。",
                "酒店数据分析系统", 0x40)
        except Exception:
            pass
        sys.exit(0)
    
    try:
        # 2. 初始化目录
        init_dirs()
        logger.info("目录初始化完成")

        # 2.5 初始化配置文件
        init_config()

        # 3. 初始化数据库
        init_database()
        logger.info("数据库初始化完成")
        
        # 4. 启动定时任务
        init_scheduler()
        logger.info("定时任务启动完成")
        
        # 5. 启动时自动备份一次
        backup_database()
        
        # 6. 创建FastAPI应用
        app = create_app()
        port = DEFAULT_PORT
        
        # 读取配置中的端口
        try:
            from app.core.scheduler import get_config_int
            cfg_port = get_config_int("port", DEFAULT_PORT)
            if 1024 <= cfg_port <= 65535:
                port = cfg_port
        except:
            pass
        
        # 端口冲突检测——自动尝试下一个端口
        import socket
        original_port = port
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    s.close()
                break  # 端口可用
            except OSError:
                if attempt < max_attempts - 1:
                    logger.warning(f"端口 {port} 被占用，尝试 {port + 1}")
                    port += 1
                else:
                    logger.critical(f"端口 {original_port}-{port} 全部被占用")
                    raise
        
        # 7. 启动系统托盘（失败不影响主程序）
        def on_exit():
            logger.info("程序退出中...")
            backup_database()
            # 显式清理锁文件（os._exit 不触发 atexit）
            try:
                from app.constants import LOCK_FILE
                if os.path.exists(LOCK_FILE):
                    os.remove(LOCK_FILE)
            except Exception:
                pass
            os._exit(0)
        
        tray = None
        try:
            tray = SystemTray(on_exit=on_exit)
            tray.run(port=port)
            logger.info("系统托盘启动完成")
            # 启动后弹出通知气泡，让用户知道系统已就绪
            tray.startup_notify()
        except Exception as e:
            logger.warning(f"系统托盘启动失败: {e}（后端服务继续运行）")
        
        # 7.5 后台检测浏览器可用性（不影响启动速度）
        def _check_browser_later():
            time.sleep(4)  # 等托盘就绪
            try:
                from app.core.collector import check_browser_available
                info = check_browser_available()
                if not info["available"]:
                    logger.warning(f"浏览器检测: {info['message']}")
                    if tray and tray.icon:
                        tray.icon.notify(
                            "⚠️ 未检测到 Chromium 内核浏览器\n"
                            "（Edge/Chrome/360等）\n"
                            "自动数据采集功能将不可用。\n"
                            "请安装 Edge 或 Chrome 浏览器。",
                            title="酒店数据分析系统 — 警告"
                        )
            except Exception:
                pass
        threading.Thread(target=_check_browser_later, daemon=True).start()
        
        # 8. 自动打开浏览器
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
        
        # 9. 启动Web服务（PyInstaller无控制台兼容——用NullHandler避免StreamHandler崩溃）
        logger.info(f"服务启动成功，访问地址：http://127.0.0.1:{port}")
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning",
                    log_config={
                        "version": 1,
                        "disable_existing_loggers": False,
                        "formatters": {
                            "default": {"format": "%(asctime)s %(levelname)s %(message)s"},
                        },
                        "handlers": {
                            "null": {"class": "logging.NullHandler"},
                        },
                        "loggers": {
                            "uvicorn": {"handlers": ["null"], "level": "WARNING"},
                            "uvicorn.error": {"handlers": ["null"], "level": "WARNING"},
                            "uvicorn.access": {"handlers": ["null"], "level": "WARNING"},
                        },
                    })
        
    except KeyboardInterrupt:
        logger.info("用户中断")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"程序启动失败：{str(e)}", exc_info=True)
        # EXE无控制台，不能用input()，直接退出
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"启动失败：{str(e)[:200]}", "酒店数据分析系统", 0x10)
        except:
            pass
        sys.exit(1)


def run_setup_mode():
    """安装向导模式"""
    print_banner()
    print("正在进行环境检测和安装...\n")
    
    from app.utils.installer import run_diagnostics, run_setup, check_permissions
    
    diag = run_diagnostics()
    print("═══ 环境检测 ═══")
    for k, v in diag.items():
        if isinstance(v, dict) and 'message' in v:
            icon = '✅' if v.get('status') == 'ok' else ('⚠️' if v.get('status') == 'warning' else '❌')
            print(f"  {icon} {k}: {v['message']}")
    
    if not diag.get('all_ok'):
        print("\n⚠️ 环境检测未完全通过，但仍将尝试安装。")
    
    print("\n═══ 开始安装 ═══")
    report = run_setup()
    for step in report['steps']:
        icon = '✅' if step['ok'] else '❌'
        print(f"  {icon} {step['name']}: {step['result']}")
    
    if report.get('warnings'):
        print("\n⚠️ 警告:")
        for w in report['warnings']:
            print(f"  - {w}")
    
    if report.get('fatal'):
        print(f"\n❌ 致命错误: {report['fatal']}")
        _safe_pause()
        return
    
    if report.get('port'):
        port = report['port'].get('port', 8080)
        print(f"\n✅ 安装完成！启动服务端口: {port}")
        print(f"   浏览器访问: http://127.0.0.1:{port}")
        print(f"   默认管理员账号: 管理员 / 123456")
    
    _safe_pause()


def run_diagnose_mode():
    """诊断模式——仅检测不安装"""
    print_banner()
    print("系统诊断报告\n")
    from app.utils.installer import run_diagnostics
    diag = run_diagnostics()
    
    print("═══ Python 环境 ═══")
    py = diag['python']
    print(f"  版本: {py.get('version','?')[:40]}")
    print(f"  模式: {'独立EXE' if getattr(sys,'frozen',False) else '源码运行'}")
    print(f"  状态: {py['message']}")
    
    print("\n═══ 磁盘空间 ═══")
    d = diag['disk']
    print(f"  可用: {d.get('free_mb', '?')}MB")
    print(f"  状态: {d.get('message', '?')}")
    
    print("\n═══ 文件权限 ═══")
    print(f"  状态: {diag['permissions']['message']}")
    
    print("\n═══ 端口检测 ═══")
    p = diag['port']
    print(f"  状态: {p['message']}")
    
    print(f"\n═══ 运行状态 ═══")
    print(f"  首次运行: {'是' if diag['is_first_run'] else '否'}")
    
    if diag['all_ok']:
        print("\n✅ 所有检查通过，系统可正常运行。")
    else:
        print("\n⚠️ 存在需要注意的问题。")
    
    _safe_pause()


def _safe_pause():
    """EXE安全暂停（EXE无stdin，用messagebox）"""
    try:
        input("\n按任意键退出...")
    except (RuntimeError, OSError):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "按确定退出", "酒店数据分析系统", 0x40)
        except:
            pass


if __name__ == "__main__":
    main()
