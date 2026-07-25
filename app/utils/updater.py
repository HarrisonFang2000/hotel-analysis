"""
更新管理器
处理软件版本检查、下载更新、安全替换、失败回滚
"""
import os
import sys
import json
import shutil
import hashlib
from datetime import datetime
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def get_app_dir() -> str:
    if is_frozen():
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_current_version() -> str:
    """获取当前版本号"""
    version_file = os.path.join(get_app_dir(), 'VERSION')
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            return f.read().strip()
    return '0.9.0'


def check_update_available(update_url: str = None) -> dict:
    """
    检查是否有可用更新
    从远程URL获取最新版本信息（JSON格式）
    """
    if update_url is None:
        # 默认更新地址（可配置）
        update_url = os.environ.get('APP_UPDATE_URL', '')
    
    if not update_url:
        return {'available': False, 'message': '未配置更新地址'}
    
    try:
        import urllib.request
        import ssl
        ctx = ssl.create_default_context()
        req = urllib.request.Request(update_url + '/version.json', 
                                       headers={'User-Agent': 'HotelAnalysis/1.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        
        current = get_current_version()
        latest = data.get('version', '0.0.0')
        
        return {
            'available': _compare_versions(latest, current) > 0,
            'current': current,
            'latest': latest,
            'release_notes': data.get('notes', ''),
            'download_url': data.get('download_url', ''),
            'file_hash': data.get('sha256', ''),
            'message': f'当前 v{current}，最新 v{latest}' + 
                       ('（有新版本可用）' if _compare_versions(latest, current) > 0 else '（已是最新）')
        }
    except Exception as e:
        return {'available': False, 'message': f'检查更新失败: {e}'}


def _compare_versions(v1: str, v2: str) -> int:
    """比较版本号，v1>v2返回1，v1<v2返回-1，相等返回0"""
    try:
        parts1 = [int(x) for x in v1.replace('v','').split('.')]
        parts2 = [int(x) for x in v2.replace('v','').split('.')]
        # 补齐长度
        while len(parts1) < 3: parts1.append(0)
        while len(parts2) < 3: parts2.append(0)
        for a, b in zip(parts1, parts2):
            if a > b: return 1
            if a < b: return -1
        return 0
    except:
        return 0


def backup_before_update() -> str:
    """更新前备份当前系统"""
    from app.utils.backup import backup_database
    backup_dir = os.path.join(get_app_dir(), 'data', 'backup', 'pre_update')
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_database()
    backup_path = os.path.join(backup_dir, f'pre_update_{datetime.now().strftime("%Y%m%d_%H%M")}')
    os.makedirs(backup_path, exist_ok=True)
    
    # 备份当前 EXE
    if is_frozen():
        exe_path = sys.executable
        shutil.copy2(exe_path, os.path.join(backup_path, os.path.basename(exe_path)))
    
    # 备份当前代码（源码模式）
    if not is_frozen():
        app_dir = os.path.join(get_app_dir(), 'app')
        shutil.copytree(app_dir, os.path.join(backup_path, 'app'), dirs_exist_ok=True)
    
    return backup_path


def verify_download(file_path: str, expected_hash: str = '') -> bool:
    """验证下载文件完整性"""
    if not expected_hash:
        return os.path.exists(file_path) and os.path.getsize(file_path) > 0
    
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_hash


def apply_update(update_package_path: str, backup_path: str = None) -> dict:
    """
    应用更新
    :param update_package_path: 更新包路径（zip或exe）
    :param backup_path: 回滚备份路径
    """
    result = {'success': False, 'message': '', 'steps': []}
    
    try:
        if not os.path.exists(update_package_path):
            result['message'] = '更新包不存在'
            return result
        
        # ZIP包：解压替换
        if update_package_path.endswith('.zip'):
            import zipfile
            app_dir = get_app_dir()
            with zipfile.ZipFile(update_package_path, 'r') as zf:
                # 不解压 data 目录（保护数据）
                members = [m for m in zf.namelist() if not m.startswith('data/')]
                zf.extractall(app_dir, members=[m for m in zf.infolist() if m.filename in members])
            result['steps'].append('解压更新包完成')
        
        # EXE：直接替换
        elif update_package_path.endswith('.exe') and is_frozen():
            exe_path = sys.executable
            exe_name = os.path.basename(exe_path)
            # 先重命名旧EXE（Windows不允许删除运行中的EXE）
            old_path = exe_path + '.old'
            if os.path.exists(old_path):
                os.remove(old_path)
            os.rename(exe_path, old_path)
            shutil.copy2(update_package_path, exe_path)
            # 标记下次启动删除旧文件
            with open(os.path.join(get_app_dir(), '.cleanup_on_start'), 'w') as f:
                f.write(old_path)
            result['steps'].append('EXE已替换（需要重启）')
        
        # 源码更新：复制文件
        elif not is_frozen():
            import zipfile
            app_dir = get_app_dir()
            with zipfile.ZipFile(update_package_path, 'r') as zf:
                zf.extractall(app_dir, members=[m for m in zf.infolist() if not m.filename.startswith('data/')])
            result['steps'].append('源码更新完成')
        
        else:
            result['message'] = '不支持的更新包格式'
            return result
        
        # 运行数据库迁移
        try:
            from app.db.database import init_database
            init_database()
            result['steps'].append('数据库迁移完成')
        except Exception as e:
            result['steps'].append(f'数据库迁移: {e}')
        
        result['success'] = True
        result['message'] = '更新成功，请重启应用'
        
    except Exception as e:
        result['message'] = f'更新失败: {e}'
        # 尝试回滚
        if backup_path and os.path.exists(backup_path):
            try:
                rollback_update(backup_path)
                result['steps'].append('已回滚到更新前版本')
            except:
                result['steps'].append('回滚失败，请手动恢复')
    
    return result


def rollback_update(backup_path: str) -> bool:
    """回滚到备份版本"""
    app_dir = get_app_dir()
    if is_frozen():
        backup_exe = os.path.join(backup_path, os.path.basename(sys.executable))
        if os.path.exists(backup_exe):
            shutil.copy2(backup_exe, sys.executable + '.restored')
    else:
        backup_app = os.path.join(backup_path, 'app')
        if os.path.exists(backup_app):
            current_app = os.path.join(app_dir, 'app')
            if os.path.exists(current_app):
                shutil.rmtree(current_app)
            shutil.copytree(backup_app, current_app)
    return True


def setup_update_check_scheduler(update_url: str = None, interval_hours: int = 24):
    """设置定期检查更新的定时任务"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        
        def check_and_notify():
            result = check_update_available(update_url)
            if result.get('available'):
                from app.utils.logger import get_logger
                logger = get_logger(__name__)
                logger.info(f"🔄 发现新版本: {result.get('latest')}（当前 {result.get('current')}）")
        
        # 获取调度器实例并添加任务
        from app.core.scheduler import scheduler
        scheduler.add_job(
            check_and_notify,
            trigger=IntervalTrigger(hours=interval_hours),
            id='update_check',
            replace_existing=True
        )
        return True
    except Exception:
        return False
