"""操作审计日志"""
from app.db.database import db_transaction

def audit_log(user_name: str, user_role: str, action: str, detail: str = ""):
    """写入操作审计日志"""
    try:
        with db_transaction() as conn:
            conn.execute(
                "INSERT INTO audit_log (user_name, user_role, action, detail) VALUES (?,?,?,?)",
                (user_name or "", user_role or "", action, detail or "")
            )
    except Exception:
        pass  # 日志写入失败不影响主流程
