"""管理员路由 — 审计日志"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()


@router.get("/audit-logs")
async def list_audit_logs(
    user_id: int | None = None,
    order_no: str | None = None,
    action: str | None = None,
    page: int = Query(1),
    page_size: int = Query(50),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员查看审计日志"""
    query = db.query(m.CreatorAuditLog)
    if user_id:
        query = query.filter(m.CreatorAuditLog.user_id == user_id)
    if order_no:
        query = query.filter(m.CreatorAuditLog.order_no == order_no)
    if action:
        query = query.filter(m.CreatorAuditLog.action == action)
    total = query.count()
    results = query.order_by(m.CreatorAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "logs": [{
            "id": log.id, "user_id": log.user_id, "order_no": log.order_no,
            "action": log.action, "detail": log.detail,
            "penalty_amount": log.penalty_amount,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        } for log in results],
        "total": total,
    }
