# -*- coding: utf-8 -*-
"""系统相关接口：配置、重算、状态查询"""
import os
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from urllib.request import urlopen, Request

from app.db.database import db_transaction
from app.schemas.common import ApiResponse
from app.core.scheduler import (
    daily_aggregate,
    monthly_aggregate_for_month,
    quarterly_aggregate_for_quarter,
    yearly_aggregate_for_year,
)
from app.constants import DB_FILE
from app.core.collector import QuhuhuCollector
import hashlib

router = APIRouter(prefix="/api", tags=["系统接口"])

# 安全关键键，不可通过普通配置API修改
PROTECTED_KEYS = {"current_role", "current_user_name"}


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str


@router.get("/config/list", summary="获取所有配置")
def get_config_list():
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT config_key, config_value, config_desc FROM sys_config")
        configs = []
        for row in cursor.fetchall():
            configs.append({
                "key": row["config_key"],
                "value": row["config_value"],
                "desc": row["config_desc"]
            })
        return ApiResponse.success(configs)


@router.put("/config", summary="更新单个配置")
def update_config(req: ConfigUpdateRequest):
    role = get_current_role()
    if role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    # 安全关键键不允许通过此API修改
    if req.key in PROTECTED_KEYS:
        raise HTTPException(status_code=403, detail="该配置项不可通过此接口修改")
    allowed_keys = [
        "collection_interval", "dev_mode", "port", "auto_backup_hours",
        "quhuhu_username", "quhuhu_password", "quhuhu_login_url",
        "collect_retry_times", "collect_offset_minute",
        "order_status",  # 订单状态筛选：全部/未入住/已入住
        "timezone",  # 时区设置
        "qweather_key",  # 和风天气API Key
        "meituan_enabled",      # 是否启用美团采集（1=启用）
        "meituan_username",     # 美团商家登录手机号
        "meituan_password",     # 美团商家登录密码
        "meituan_calendar_url", # 美团房价日历页面URL
        "meituan_manual_price", # 美团今日底价（手动填入）
    ]
    if req.key not in allowed_keys:
        raise HTTPException(status_code=400, detail=f"无效的配置键: {req.key}")
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sys_config SET config_value = ?, update_time = datetime('now','localtime') WHERE config_key = ?",
            (req.value, req.key)
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO sys_config (config_key, config_value, config_desc) VALUES (?, ?, ?)",
                (req.key, req.value, "用户配置")
            )
        return ApiResponse.success()


@router.post("/daily/recalculate", summary="重算指定日期日报")
def recalculate_daily(date: str):
    try:
        daily_aggregate(date)
        from datetime import datetime
        dt = datetime.strptime(date, "%Y-%m-%d")
        monthly_aggregate_for_month(dt.year, dt.month)
        return ApiResponse.success()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重算失败：{str(e)}")


@router.post("/monthly/recalculate", summary="重算指定月报")
def recalculate_monthly(year: int, month: int):
    try:
        monthly_aggregate_for_month(year, month)
        return ApiResponse.success()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重算失败：{str(e)}")


@router.post("/recalculate/all", summary="全量重算")
def recalculate_all():
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT data_date FROM hourly_data WHERE data_hour = 24")
            dates = [row["data_date"] for row in cursor.fetchall()]

        from datetime import datetime
        for date_str in dates:
            daily_aggregate(date_str)

        years_months = set()
        for date_str in dates:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            years_months.add((dt.year, dt.month))
        for year, month in sorted(years_months):
            monthly_aggregate_for_month(year, month)

        return ApiResponse.success(message="全量重算完成")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重算失败：{str(e)}")


@router.get("/system/status", summary="获取系统状态")
def get_system_status():
    db_size = 0
    if os.path.exists(DB_FILE):
        db_size = os.path.getsize(DB_FILE) / 1024 / 1024

    last_backup = ""
    backup_dir = os.path.join(os.path.dirname(DB_FILE), "backup")
    if os.path.exists(backup_dir):
        files = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db') and f != os.path.basename(DB_FILE)], reverse=True)
        if files:
            last_backup = files[0].replace("hotel_data_", "").replace(".db", "")

    # 浏览器可用性检测
    browser_info = {"available": False, "name": "", "message": "检测中..."}
    try:
        from app.core.collector import check_browser_available
        browser_info = check_browser_available()
    except Exception:
        pass

    return ApiResponse.success({
        "running": True,
        "db_size": round(db_size, 2),
        "last_backup_time": last_backup,
        "browser": browser_info,
    })


# ==================== 角色与权限 ====================

def _get_config_val(key: str, default: str = "") -> str:
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT config_value FROM sys_config WHERE config_key=?", (key,))
        row = c.fetchone()
        return row["config_value"] if row else default


def get_current_user() -> dict:
    """获取当前登录用户信息，同时验证用户是否仍活跃"""
    name = _get_config_val("current_user_name", "")
    role = _get_config_val("current_role", "")
    # 未登录或默认状态 → 返回空
    if not name or not role:
        return {"name": "", "role": "guest"}
    # 超管无需查users表
    if name == "超管" and role == "super_admin":
        return {"name": name, "role": role}
    # 验证普通用户是否仍活跃
    try:
        with db_transaction() as conn:
            c = conn.cursor()
            c.execute("SELECT active FROM users WHERE name=? AND role=?", (name, role))
            row = c.fetchone()
            if not row or not row["active"]:
                return {"name": "", "role": "guest"}  # 已停用则视为未登录
    except Exception:
        pass
    return {"name": name, "role": role}


def get_current_role() -> str:
    return get_current_user()["role"] or "guest"


def require_role(*roles: str):
    """权限守卫：当前角色不在允许列表中则403"""
    current = get_current_role()
    if current not in roles:
        raise HTTPException(status_code=403, detail=f"权限不足，需要{roles}角色")


class RoleSwitchRequest(BaseModel):
    name: str = ""
    pin: str = ""


@router.get("/role/check", summary="检查当前用户")
def check_role():
    """返回当前用户信息及用户列表"""
    user = get_current_user()
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, role, active FROM users ORDER BY role DESC, name")
        users = [{"id": r["id"], "name": r["name"], "role": r["role"], "active": r["active"]} for r in c.fetchall()]
    return ApiResponse.success({
        "current_user": user,
        "users": users,
    })


@router.post("/role/switch", summary="用户登录(PIN验证)")
def switch_role(req: RoleSwitchRequest):
    """通过姓名+PIN登录"""
    if not req.name or not req.pin:
        raise HTTPException(status_code=400, detail="请输入姓名和PIN")
    
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE name=? AND pin=? AND active=1", (req.name, _hash_pin(req.pin)))
        user = c.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="姓名或PIN错误，或账号已停用")
        
        # 保存当前用户信息到配置
        for k, v in [("current_user_name", user["name"]), ("current_role", user["role"])]:
            c.execute("UPDATE sys_config SET config_value=?, update_time=datetime('now','localtime') WHERE config_key=?", (v, k))
            if c.rowcount == 0:
                c.execute("INSERT INTO sys_config (config_key, config_value, config_desc) VALUES (?,?,?)", (k, v, "当前用户"))
    
    from app.utils.audit import audit_log
    audit_log(user["name"], user["role"], "用户登录", f"角色: {user['role']}")
    
    return ApiResponse.success({
        "name": user["name"], "role": user["role"]
    }, message=f"欢迎，{user['name']}({user['role']})")


@router.post("/role/logout", summary="退出登录")
def logout():
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE sys_config SET config_value='', update_time=datetime('now','localtime') WHERE config_key='current_role'")
        c.execute("UPDATE sys_config SET config_value='', update_time=datetime('now','localtime') WHERE config_key='current_user_name'")
    return ApiResponse.success(message="已退出，请重新登录")


class ChangePinRequest(BaseModel):
    old_pin: str
    new_pin: str


@router.post("/role/verify-pin", summary="验证当前用户密码")
def verify_pin(pin: str = ""):
    """验证当前用户密码是否正确"""
    user = get_current_user()
    if not user["name"] or user["role"] == "guest":
        raise HTTPException(status_code=400, detail="请先登录")
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name=? AND pin=? AND active=1", (user["name"], _hash_pin(pin)))
        if not c.fetchone():
            raise HTTPException(status_code=400, detail="旧密码错误")
    return ApiResponse.success(message="验证通过")


@router.put("/role/change-pin", summary="修改自己的密码")
def change_own_pin(req: ChangePinRequest):
    """当前登录用户修改自己的PIN，需验证旧PIN"""
    user = get_current_user()
    if user["name"] == "超管" and user["role"] == "super_admin" and get_current_role() != "super_admin":
        raise HTTPException(status_code=400, detail="请先登录")
    if not req.new_pin or len(req.new_pin) > 20:
        raise HTTPException(status_code=400, detail="新密码需1-20位")
    
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE name=? AND pin=? AND active=1", (user["name"], _hash_pin(req.old_pin)))
        if not c.fetchone():
            raise HTTPException(status_code=400, detail="旧密码错误")
        c.execute("UPDATE users SET pin=? WHERE name=?", (_hash_pin(req.new_pin), user["name"]))
    
    from app.utils.audit import audit_log
    audit_log(user["name"], user["role"], "修改密码", "修改了自己的登录密码")
    return ApiResponse.success(message="密码修改成功")


# ==================== 用户管理（管理员专用）====================

class CreateUserRequest(BaseModel):
    name: str
    pin: str
    role: str = "operator"


@router.get("/user/list", summary="用户列表")
def list_users():
    if get_current_role() != 'super_admin':
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, role, active, create_time FROM users ORDER BY role DESC, name")
        users = [dict(r) for r in c.fetchall()]
    return ApiResponse.success(users)


@router.post("/user/create", summary="创建用户")
def create_user(req: CreateUserRequest):
    if get_current_role() != 'super_admin':
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    if not req.name or len(req.name) > 20:
        raise HTTPException(status_code=400, detail="姓名需1-20字符")
    if not req.pin or len(req.pin) > 20:
        raise HTTPException(status_code=400, detail="PIN需1-20位字符")
    if req.role not in ("admin", "operator"):
        raise HTTPException(status_code=400, detail="无效角色")
    
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name=?", (req.name,))
        if c.fetchone():
            raise HTTPException(status_code=400, detail="用户名已存在")
        c.execute("INSERT INTO users (name, pin, role) VALUES (?,?,?)", (req.name, _hash_pin(req.pin), req.role))
    
    user = get_current_user()
    from app.utils.audit import audit_log
    audit_log(user["name"], user["role"], "创建用户", f"创建 {req.name}({req.role})")
    return ApiResponse.success(message=f"用户 {req.name} 创建成功")


@router.put("/user/update", summary="更新用户")
def update_user(user_id: int, name: str = "", pin: str = "", role: str = "", active: int = None):
    if get_current_role() != 'super_admin':
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    with db_transaction() as conn:
        c = conn.cursor()
        # 禁止停用/改角色内置用户
        c.execute("SELECT name FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        if row["name"] in ("超管",):
            if active == 0:
                raise HTTPException(status_code=400, detail="系统内置用户不可停用")
            if role and role != "super_admin":
                raise HTTPException(status_code=400, detail="系统内置用户不可降级")
    # 重开事务执行更新
    updates = []
    params = []
    if name:
        updates.append("name=?"); params.append(name)
    if pin:
        if len(pin) > 20:
            raise HTTPException(status_code=400, detail="PIN最多20位")
        updates.append("pin=?"); params.append(_hash_pin(pin))
    if role and role in ("super_admin", "admin", "operator"):
        updates.append("role=?"); params.append(role)
    if active is not None:
        updates.append("active=?"); params.append(active)
    
    if not updates:
        raise HTTPException(status_code=400, detail="无更新内容")
    params.append(user_id)
    
    with db_transaction() as conn:
        conn.execute(f"UPDATE users SET {','.join(updates)} WHERE id=?", params)
    
    user = get_current_user()
    from app.utils.audit import audit_log
    audit_log(user["name"], user["role"], "更新用户", f"更新用户ID={user_id}")
    return ApiResponse.success(message="用户已更新")


@router.delete("/user/{user_id}", summary="删除用户")
def delete_user(user_id: int):
    if get_current_role() != 'super_admin':
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        if row["name"] in ("超管", "管理员"):
            raise HTTPException(status_code=400, detail="系统内置用户不可删除")
        c.execute("DELETE FROM users WHERE id=?", (user_id,))
    
    user = get_current_user()
    from app.utils.audit import audit_log
    audit_log(user["name"], user["role"], "删除用户", f"删除 {row['name']}")
    return ApiResponse.success(message=f"已删除 {row['name']}")


# ==================== 审计日志 ====================

@router.get("/audit/list", summary="操作日志列表")
def list_audit_logs(limit: int = 50):
    if get_current_role() != 'super_admin':
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM audit_log ORDER BY create_time DESC LIMIT ?", (limit,))
        logs = [dict(r) for r in c.fetchall()]
    return ApiResponse.success(logs)


@router.get("/audit/export", summary="导出全部操作日志CSV")
def export_audit_logs():
    """导出所有审计日志为CSV文件"""
    if get_current_role() != 'super_admin':
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    import csv, io
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM audit_log ORDER BY create_time DESC")
        logs = [dict(r) for r in c.fetchall()]
    
    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel
    writer = csv.DictWriter(output, fieldnames=['id', 'user_name', 'user_role', 'action', 'detail', 'create_time'])
    writer.writeheader()
    for log in logs:
        writer.writerow(log)
    
    from fastapi.responses import Response
    return Response(
        content=output.getvalue().encode('utf-8-sig'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=操作日志_全部.csv'}
    )


# ==================== 备份管理 ====================

@router.get("/backup/list", summary="获取备份文件列表")
def list_backups():
    """列出所有备份文件，含文件大小和创建时间"""
    backup_dir = os.path.join(os.path.dirname(DB_FILE), "backup")
    backups = []
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith(".db") and f != os.path.basename(DB_FILE):
                fpath = os.path.join(backup_dir, f)
                size_kb = round(os.path.getsize(fpath) / 1024, 1)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                backups.append({"filename": f, "size_kb": size_kb, "time": mtime})
    return ApiResponse.success(backups)


@router.post("/backup/create", summary="手动创建备份")
def create_backup():
    """立即创建一次数据库备份"""
    from app.utils.backup import backup_database
    ok = backup_database()
    if ok:
        return ApiResponse.success(message="备份创建成功")
    else:
        raise HTTPException(status_code=500, detail="备份创建失败")


@router.post("/backup/restore", summary="从备份文件还原数据库")
def restore_backup(filename: str):
    """
    从指定备份文件还原数据库，操作不可逆请谨慎！
    还原前会自动创建当前数据的一次备份。
    """
    backup_dir = os.path.join(os.path.dirname(DB_FILE), "backup")
    backup_path = os.path.join(backup_dir, filename)
    
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail=f"备份文件不存在: {filename}")
    if not filename.endswith(".db") or filename == os.path.basename(DB_FILE):
        raise HTTPException(status_code=400, detail="无效的备份文件名")
    
    import shutil
    try:
        # 1. 还原前先备份当前数据库（安全措施）
        pre_restore = f"backup_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DB_FILE, os.path.join(backup_dir, pre_restore))
        
        # 2. 用备份文件覆盖当前数据库
        shutil.copy2(backup_path, DB_FILE)
        
        return ApiResponse.success(message=f"已从 {filename} 还原，当前数据已备份为 {pre_restore}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"还原失败: {str(e)}")


# ==================== Cookie 管理 ====================
@router.post("/cookie/capture", summary="一键读取去呼呼Cookie")
def capture_cookie():
    """打开浏览器让用户手动登录，然后一键读取登录Cookie"""
    try:
        collector = QuhuhuCollector()
        result = collector.capture_cookie()
        collector._close_browser()
        if result["success"]:
            return ApiResponse.success(result, message=result["message"])
        else:
            return ApiResponse.error(message=result["message"], code=400)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取Cookie失败: {str(e)}")


@router.post("/meituan/cookie", summary="美团商家后台一键读取Cookie")
def capture_meituan_cookie():
    """打开浏览器让用户手动登录美团，成功后自动保存Cookie"""
    try:
        from app.core.meituan_collector import MeituanCollector
        collector = MeituanCollector()
        result = collector.capture_cookie(wait_timeout=180)
        collector._close_browser()
        if result["success"]:
            return ApiResponse.success(result, message=f"美团登录成功！已保存 {result['cookie_count']} 个Cookie")
        else:
            return ApiResponse.error(message=result.get("message", "登录超时"), code=400)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"美团Cookie读取失败: {str(e)}")


# ==================== 数据库管理接口 ====================

@router.get("/db/tables", summary="获取所有数据表列表")
def get_db_tables():
    """返回所有用户数据表名及行数"""
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'schema_version' ORDER BY name")
        tables = []
        for row in c.fetchall():
            t = row["name"]
            c.execute(f"SELECT COUNT(*) FROM [{t}]")
            cnt = c.fetchone()[0]
            tables.append({"name": t, "rows": cnt})
        return ApiResponse.success(tables)


@router.get("/db/table/{table_name}", summary="浏览数据表")
def browse_table(table_name: str, page: int = 1, page_size: int = 50):
    """分页浏览指定表数据"""
    with db_transaction() as conn:
        c = conn.cursor()
        # 验证表存在
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not c.fetchone():
            raise HTTPException(status_code=404, detail=f"表不存在: {table_name}")
        # 获取列信息
        c.execute(f"PRAGMA table_info([{table_name}])")
        columns = [{"name": r[1], "type": r[2]} for r in c.fetchall()]
        # 总数
        c.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        total = c.fetchone()[0]
        # 分页数据
        offset = (page - 1) * page_size
        col_names = [col["name"] for col in columns]
        c.execute(f"SELECT {','.join(col_names)} FROM [{table_name}] LIMIT {page_size} OFFSET {offset}")
        rows = [dict(zip(col_names, row)) for row in c.fetchall()]
        return ApiResponse.success({
            "columns": columns,
            "rows": rows,
            "total": total,
            "page": page,
            "page_size": page_size
        })


@router.put("/db/table/{table_name}/row/{row_id}", summary="编辑数据行")
def update_table_row(table_name: str, row_id: int, data: dict):
    """更新指定表中某行数据（仅管理员）"""
    require_role("admin")
    allowed = {"hourly_data","daily_data","monthly_data","quarterly_data","yearly_data","sys_config","users"}
    if table_name not in allowed:
        raise HTTPException(status_code=400, detail="该表不支持直接编辑")
    if not data:
        raise HTTPException(status_code=400, detail="无更新数据")
    with db_transaction() as conn:
        c = conn.cursor()
        sets = ", ".join(f"[{k}]=?" for k in data.keys())
        vals = list(data.values()) + [row_id]
        c.execute(f"UPDATE [{table_name}] SET {sets} WHERE id=?", vals)
        return ApiResponse.success({"updated": c.rowcount})


@router.delete("/db/table/{table_name}/row/{row_id}", summary="删除数据行")
def delete_table_row(table_name: str, row_id: int):
    """删除指定表中某行（仅超管）"""
    require_role("super_admin")
    allowed = {"hourly_data","daily_data","monthly_data","quarterly_data","yearly_data","import_record","operation_log","audit_log"}
    if table_name not in allowed:
        raise HTTPException(status_code=400, detail="该表不支持直接删除")
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute(f"DELETE FROM [{table_name}] WHERE id=?", (row_id,))
        return ApiResponse.success({"deleted": c.rowcount})


@router.post("/db/execute", summary="执行SQL（仅超管）")
def execute_sql(req: dict):
    """执行只读SQL查询（超管）"""
    require_role("super_admin")
    sql = (req.get("sql") or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL不能为空")
    sql_upper = sql.upper()
    forbidden = ["DROP", "ALTER", "CREATE", "INSERT", "UPDATE", "DELETE", "ATTACH", "DETACH", "VACUUM", "PRAGMA"]
    for kw in forbidden:
        if sql_upper.startswith(kw):
            raise HTTPException(status_code=400, detail=f"禁止执行 {kw} 语句，仅允许SELECT查询")
    with db_transaction() as conn:
        c = conn.cursor()
        try:
            c.execute(sql)
            if sql_upper.startswith("SELECT"):
                cols = [d[0] for d in c.description] if c.description else []
                rows = [dict(zip(cols, row)) for row in c.fetchall()]
                return ApiResponse.success({"columns": cols, "rows": rows, "count": len(rows)})
            return ApiResponse.success({"message": "OK"})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"SQL错误: {str(e)}")


@router.get("/db/stats", summary="数据库统计信息")
def get_db_stats():
    """返回数据库大小、各表行数和大小"""
    import os as _os
    stats = {"db_file": _os.path.basename(DB_FILE), "db_size_kb": round(_os.path.getsize(DB_FILE) / 1024, 1)}
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = []
        for row in c.fetchall():
            t = row["name"]
            c.execute(f"SELECT COUNT(*) FROM [{t}]")
            cnt = c.fetchone()[0]
            c.execute(f"PRAGMA table_info([{t}])")
            cols = len(c.fetchall())
            tables.append({"name": t, "rows": cnt, "columns": cols})
        stats["tables"] = tables
        c.execute("PRAGMA page_count")
        stats["page_count"] = c.fetchone()[0]
        c.execute("PRAGMA freelist_count")
        stats["freelist"] = c.fetchone()[0]
    return ApiResponse.success(stats)


@router.get("/db/table/{table_name}/ddl", summary="获取建表DDL")
def get_table_ddl(table_name: str):
    """返回指定表的CREATE TABLE语句"""
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        row = c.fetchone()
        if not row or not row["sql"]:
            raise HTTPException(status_code=404, detail=f"表不存在或无DDL: {table_name}")
        return ApiResponse.success({"table": table_name, "ddl": row["sql"]})


@router.post("/db/table/{table_name}/row", summary="新增数据行")
def insert_table_row(table_name: str, data: dict):
    """向指定表插入一行数据（仅管理员）"""
    require_role("admin")
    allowed = {"hourly_data","daily_data","monthly_data","quarterly_data","yearly_data","sys_config","users"}
    if table_name not in allowed:
        raise HTTPException(status_code=400, detail="该表不支持直接插入")
    if not data:
        raise HTTPException(status_code=400, detail="无数据")
    with db_transaction() as conn:
        c = conn.cursor()
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ",".join(["?" for _ in cols])
        col_names = ",".join([f"[{k}]" for k in cols])
        c.execute(f"INSERT INTO [{table_name}] ({col_names}) VALUES ({placeholders})", vals)
        return ApiResponse.success({"inserted": c.lastrowid})


@router.delete("/db/table/{table_name}", summary="清空数据表（仅超管）")
def truncate_table(table_name: str):
    """清空指定表全部数据（不可恢复！）"""
    require_role("super_admin")
    protected = {"users", "sys_config", "schema_version"}
    if table_name in protected:
        raise HTTPException(status_code=400, detail="受保护的表，不可清空")
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute(f"DELETE FROM [{table_name}]")
        c.execute("VACUUM")
        return ApiResponse.success({"deleted": c.rowcount, "message": f"表 {table_name} 已清空"})


# ==================== 天气代理接口 ====================
# 舟山朱家尖坐标
ZHOUSHAN_LAT = 29.92
ZHOUSHAN_LON = 122.41
QWEATHER_LOCATION_ID = "101211101"  # 和风天气舟山城市ID


def _get_config(key: str, default: str = "") -> str:
    """从数据库读取配置值"""
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT config_value FROM sys_config WHERE config_key = ?", (key,))
            row = cursor.fetchone()
            return row["config_value"] if row else default
    except Exception:
        return default


def _http_get(url: str) -> dict:
    """简单的HTTP GET请求，返回JSON"""
    try:
        req = Request(url, headers={"User-Agent": "HotelAnalysis/1.0"})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


@router.get("/weather/monthly", summary="获取指定月份天气（和风+open-meteo）")
def get_monthly_weather(year: int, month: int):
    """
    获取指定月份每天天气：
    - 历史日期使用 open-meteo archive（实测数据，较准）
    - 未来7天优先用和风天气（需配 qweather_key），否则用 open-meteo 预报
    - 未来日期标注"预报"，历史日期标注"实测"
    """
    import calendar

    days_in_month = calendar.monthrange(year, month)[1]
    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{days_in_month}"
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    result = {}  # { "YYYY-MM-DD": {code, hi, lo, source, is_history} }

    # ① open-meteo archive 历史实测数据（最准）
    try:
        archive_end = min(yesterday, month_end)
        if month_start <= archive_end:
            archive_url = (
                f"https://archive-api.open-meteo.com/v1/archive"
                f"?latitude={ZHOUSHAN_LAT}&longitude={ZHOUSHAN_LON}"
                f"&start_date={max(month_start, '2020-01-01')}&end_date={archive_end}"
                f"&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum"
                f"&timezone=Asia/Shanghai"
            )
            archive_data = _http_get(archive_url)
            if archive_data.get("daily"):
                times = archive_data["daily"]["time"]
                for i, t in enumerate(times):
                    if t not in result:
                        code = archive_data["daily"]["weathercode"][i]
                        hi = round(archive_data["daily"]["temperature_2m_max"][i])
                        lo = round(archive_data["daily"]["temperature_2m_min"][i])
                        rain = archive_data["daily"].get("precipitation_sum", [0])[i] or 0
                        result[t] = {"code": code, "hi": hi, "lo": lo, "rain": rain, "source": "open-meteo", "is_history": True}
    except Exception:
        pass

    # ② 和风天气（优先用于未来7天，中文描述更准）
    qweather_key = _get_config("qweather_key", "").strip()
    if qweather_key:
        try:
            qw_url = (
                f"https://devapi.qweather.com/v7/weather/7d"
                f"?location={QWEATHER_LOCATION_ID}&key={qweather_key}"
            )
            qw_data = _http_get(qw_url)
            if qw_data.get("code") == "200" and qw_data.get("daily"):
                for day in qw_data["daily"]:
                    t = day["fxDate"]
                    if month_start <= t <= month_end:
                        hi = int(day["tempMax"])
                        lo = int(day["tempMin"])
                        result[t] = {
                            "code": int(day.get("iconDay", 100)),
                            "hi": hi, "lo": lo,
                            "text": day.get("textDay", ""),
                            "source": "qweather",
                            "is_history": (t <= yesterday)
                        }
        except Exception:
            pass

    # ③ open-meteo 预报（补充和风未覆盖的日期）
    try:
        forecast_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={ZHOUSHAN_LAT}&longitude={ZHOUSHAN_LON}"
            f"&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum"
            f"&timezone=Asia/Shanghai&forecast_days=16"
        )
        forecast_data = _http_get(forecast_url)
        if forecast_data.get("daily"):
            times = forecast_data["daily"]["time"]
            for i, t in enumerate(times):
                if month_start <= t <= month_end and t not in result:
                    code = forecast_data["daily"]["weathercode"][i]
                    hi = round(forecast_data["daily"]["temperature_2m_max"][i])
                    lo = round(forecast_data["daily"]["temperature_2m_min"][i])
                    rain = forecast_data["daily"].get("precipitation_sum", [0])[i] or 0
                    result[t] = {"code": code, "hi": hi, "lo": lo, "rain": rain, "source": "open-meteo", "is_history": False}
    except Exception:
        pass

    # ③ 格式化输出
    weather_map = {
        0: ("☀️", "晴"), 1: ("🌤", "晴"), 2: ("⛅", "多云"), 3: ("☁️", "阴"),
        45: ("🌫", "雾"), 51: ("🌧", "小雨"), 53: ("🌧", "中雨"), 55: ("🌧", "大雨"),
        61: ("⛈", "暴雨"), 63: ("⛈", "大暴雨"), 65: ("⛈", "特大暴雨"),
        71: ("❄️", "小雪"), 73: ("❄️", "中雪"), 75: ("❄️", "大雪"),
        80: ("🌦", "阵雨"), 81: ("🌦", "阵雨"), 82: ("⛈", "雷雨"),
        85: ("❄️", "小雪"), 86: ("❄️", "雪"),
        95: ("⛈", "雷暴"), 96: ("⛈", "雷暴"), 99: ("⛈", "雷暴"),
    }
    # 和风天气 icon 映射（100-399）
    qw_icon_map = {
        100: ("☀️", "晴"), 101: ("🌤", "多云"), 102: ("🌤", "少云"), 103: ("⛅", "晴间多云"),
        104: ("☁️", "阴"), 150: ("🌙", "晴"), 151: ("🌙", "多云"), 152: ("🌙", "少云"), 153: ("☁️", "阴"),
        300: ("🌧", "阵雨"), 301: ("🌧", "强阵雨"), 302: ("⛈", "雷阵雨"), 303: ("⛈", "强雷阵雨"),
        304: ("🌧", "雷阵雨伴有冰雹"), 305: ("🌧", "小雨"), 306: ("🌧", "中雨"), 307: ("🌧", "大雨"),
        308: ("🌧", "暴雨"), 309: ("🌧", "大暴雨"), 310: ("🌧", "特大暴雨"),
        400: ("❄️", "小雪"), 401: ("❄️", "中雪"), 402: ("❄️", "大雪"), 403: ("❄️", "暴雪"),
        404: ("🌧", "雨夹雪"), 405: ("🌧", "雨雪天气"),
        500: ("🌫", "雾"), 501: ("🌫", "雾"), 502: ("🌫", "霾"), 503: ("🌫", "扬沙"),
        504: ("🌫", "浮尘"), 507: ("🌫", "沙尘暴"), 508: ("🌫", "强沙尘暴"),
    }

    output = {}
    for ds in sorted(result.keys()):
        info = result[ds]
        code = info.get("code", 0)
        hi = info.get("hi", 0)
        lo = info.get("lo", 0)
        src = info.get("source", "")
        is_hist = info.get("is_history", False)
        rain = info.get("rain", 0)

        if src == "qweather" and "text" in info:
            icon, name = qw_icon_map.get(code, ("🌤", info["text"]))
        else:
            icon, name = weather_map.get(code, ("🌤", "多云"))

        # 未来日期标注"预报"
        tag = "" if is_hist else "📡"
        rain_info = f" 降水{rain}mm" if rain > 0.5 else ""

        output[ds] = {
            "name": f"{icon}{tag}{name}",
            "desc": f"{lo}°~{hi}°{rain_info}",
            "type": "weather"
        }

    return ApiResponse.success(output)
