"""
安装向导 & 环境检测
处理首次安装、环境依赖检查、系统初始化等
"""
import os
import sys
import shutil
import socket


def is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def get_app_dir() -> str:
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_python() -> dict:
    info = {'version': sys.version, 'platform': sys.platform, 'is_frozen': is_frozen()}
    if is_frozen():
        info['status'] = 'ok'
        info['message'] = '独立EXE模式'
        return info
    v = sys.version_info
    info['status'] = 'ok' if v >= (3, 9) else 'error'
    info['message'] = f'Python {v.major}.{v.minor}.{v.micro}' if v >= (3, 9) else '版本过低需3.9+'
    return info


def check_disk_space(path=None, required_mb=500):
    if path is None: path = get_app_dir()
    try:
        free = shutil.disk_usage(path).free / 1048576
        return {'status': 'ok' if free >= required_mb else 'warning', 'free_mb': round(free,1), 'message': f'可用 {free:.0f}MB'}
    except Exception as e:
        return {'status': 'warning', 'free_mb': 0, 'message': str(e)}


def check_port(port=8080, max_attempts=10):
    orig = port
    for _ in range(max_attempts):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', port)); s.close()
            return {'status': 'ok', 'port': port, 'message': f'端口 {port} 可用'}
        except OSError:
            port += 1
    return {'status': 'error', 'port': None, 'message': f'端口 {orig}-{port-1} 全被占用'}


def check_permissions(path=None):
    if path is None: path = get_app_dir()
    tf = os.path.join(path, '.wtest')
    try:
        with open(tf, 'w') as f: f.write('t')
        os.remove(tf)
        return {'status': 'ok', 'message': 'OK'}
    except PermissionError:
        return {'status': 'error', 'message': '无写入权限，请移到非系统目录'}
    except Exception as e:
        return {'status': 'warning', 'message': str(e)}


def check_is_first_run():
    from app.constants import DB_FILE
    return not os.path.exists(DB_FILE)


def ensure_directories():
    from app.constants import DATA_DIR, IMPORT_DIR, EXPORT_DIR, BACKUP_DIR, LOG_DIR
    created = []
    for d in [DATA_DIR, IMPORT_DIR, EXPORT_DIR, BACKUP_DIR, LOG_DIR]:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
            created.append(d)
    return created


def ensure_config():
    from app.constants import CONFIG_FILE
    if not os.path.exists(CONFIG_FILE):
        default = os.path.join(sys._MEIPASS if is_frozen() else get_app_dir(), "config.default.ini")
        if os.path.exists(default):
            shutil.copy(default, CONFIG_FILE)
        else:
            with open(CONFIG_FILE, 'w') as f: f.write('[system]\nport=8080\n')
    return "OK"


def run_diagnostics():
    r = {'python': check_python(), 'disk': check_disk_space(), 'permissions': check_permissions(),
         'port': check_port(), 'is_first_run': check_is_first_run()}
    r['all_ok'] = all(v.get('status') == 'ok' for v in [r['python'], r['permissions']])
    return r


def run_setup():
    report = {'success': True, 'steps': [], 'warnings': []}
    p = check_permissions()
    report['steps'].append({'name': '权限检查', 'result': p['message'], 'ok': p['status'] != 'error'})
    if p['status'] == 'error':
        report['success'] = False; report['fatal'] = p['message']; return report
    c = ensure_directories()
    report['steps'].append({'name': '创建目录', 'result': f'{len(c)}个', 'ok': True})
    report['steps'].append({'name': '配置文件', 'result': ensure_config(), 'ok': True})
    try:
        from app.db.database import init_database; init_database()
        report['steps'].append({'name': '数据库', 'result': 'OK', 'ok': True})
    except Exception as e:
        report['steps'].append({'name': '数据库', 'result': str(e), 'ok': False})
    report['port'] = check_port()
    report['steps'].append({'name': '端口', 'result': report['port']['message'], 'ok': True})
    return report
