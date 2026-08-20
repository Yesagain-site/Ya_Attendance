"""Tiny audit-log helper."""
from . import db


def log(user_id, action: str, entity: str, detail: str = ""):
    try:
        db.execute(
            "INSERT INTO audit_log (user_id, action, entity, detail) VALUES (%s,%s,%s,%s)",
            (user_id, action, entity, detail[:500]))
    except Exception:
        pass  # never let auditing break the request
