"""
单实例锁
防止程序同时运行多个实例，避免数据库冲突
"""
import os
import sys
import atexit

from app.constants import LOCK_FILE


class SingleInstance:
    """单实例锁实现"""
    
    def __init__(self):
        self.lock_file = LOCK_FILE
        self.fp = None
    
    def acquire(self) -> bool:
        """
        获取锁
        :return: 获取成功返回True，已存在实例返回False
        """
        try:
            # 如果锁文件存在，检查进程是否确实在运行
            if os.path.exists(self.lock_file):
                with open(self.lock_file, "r") as f:
                    pid = f.read().strip()
                if pid and pid.isdigit():
                    pid = int(pid)
                    if self._is_process_running(pid):
                        return False
                    else:
                        # 锁文件是残留的（进程已死），删除它
                        try:
                            os.remove(self.lock_file)
                        except Exception:
                            pass
            
            # 创建锁文件，写入当前PID
            self.fp = open(self.lock_file, "w")
            self.fp.write(str(os.getpid()))
            self.fp.flush()
            
            # 退出时自动删除锁文件
            atexit.register(self.release)
            return True
        except Exception:
            return False
    
    @staticmethod
    def _is_process_running(pid: int) -> bool:
        """检查指定PID的进程是否在运行（且是我们的程序）"""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                kernel32 = ctypes.windll.kernel32
                # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
                process = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
                if not process:
                    return False
                # 检查进程退出码——僵尸进程不应阻止启动
                exit_code = wintypes.DWORD()
                if kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                    if exit_code.value != 259:  # 259 = STILL_ACTIVE
                        kernel32.CloseHandle(process)
                        return False  # 进程已退出
                # 获取进程名验证
                try:
                    psapi = ctypes.windll.psapi
                    exe_name = ctypes.create_unicode_buffer(260)
                    size = wintypes.DWORD(260)
                    if psapi.GetModuleBaseNameW(process, None, exe_name, size):
                        name = exe_name.value.lower()
                        if "酒店数据分析系统" in name or "hotel" in name:
                            kernel32.CloseHandle(process)
                            return True
                except Exception:
                    pass
                kernel32.CloseHandle(process)
                return False  # 能打开但不认识 → PID重用
            except Exception:
                return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
    
    def release(self) -> None:
        """释放锁"""
        try:
            if self.fp:
                self.fp.close()
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception:
            pass
