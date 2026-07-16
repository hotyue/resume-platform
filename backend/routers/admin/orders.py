"""管理员路由 — 订单管理"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()


@router.get("/orders")
async def admin_orders(
    status: Optional[str] = Query(None, description="按状态筛选"),
    search: Optional[str] = Query(None, description="搜索订单号/模板名"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员订单列表"""
    query = db.query(m.Order, m.Template, m.User).outerjoin(
        m.Template, m.Order.template_id == m.Template.id
    ).outerjoin(
        m.User, m.Order.user_id == m.User.id
    )
    if status:
        query = query.filter(m.Order.status == status)
    if search:
        query = query.filter(
            m.Order.order_no.ilike(f"%{search}%") |
            m.Template.name.ilike(f"%{search}%")
        )
    total = query.count()
    results = query.order_by(m.Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "orders": [{
            "id": o.id, "order_no": o.order_no, "amount": o.amount,
            "status": o.status, "order_type": o.order_type,
            "template_name": t.name if t else "N/A",
            "template_category": t.category if t else "N/A",
            "user_name": u.username if u else "N/A",
            "creator_id": o.creator_id,
            "ref_user_id": o.ref_user_id,
            "created_at": str(o.created_at),
        } for o, t, u in results],
    }


@router.get("/orders/{order_no}")
async def admin_order_detail(
    order_no: str,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """订单详情"""
    order = db.query(m.Order).filter(m.Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    template = db.query(m.Template).filter(m.Template.id == order.template_id).first()
    user = db.query(m.User).filter(m.User.id == order.user_id).first() if order.user_id else None
    creator = db.query(m.User).filter(m.User.id == order.creator_id).first() if order.creator_id else None
    ref_user = db.query(m.User).filter(m.User.id == order.ref_user_id).first() if order.ref_user_id else None
    commissions = db.query(m.CommissionRecord).filter(
        m.CommissionRecord.order_no == order_no
    ).all()
    refunds = db.query(m.RefundRequest).filter(m.RefundRequest.order_no == order_no).all()
    return {
        "order": {
            "id": order.id, "order_no": order.order_no, "amount": order.amount,
            "status": order.status, "order_type": order.order_type,
            "custom_requirements": order.custom_requirements,
            "commission_distributed": order.commission_distributed,
            "created_at": str(order.created_at),
            "template": {"id": template.id, "name": template.name, "category": template.category} if template else None,
            "user": {"id": user.id, "username": user.username, "role": user.role} if user else None,
            "creator": {"id": creator.id, "username": creator.username} if creator else None,
            "ref_user": {"id": ref_user.id, "username": ref_user.username} if ref_user else None,
        },
        "commissions": [{
            "id": c.id, "user_id": c.user_id, "level": c.level,
            "amount": c.amount, "rate": c.rate,
        } for c in commissions],
        "refunds": [{"id": r.id, "refund_amount": r.refund_amount, "creator_deduction": r.creator_deduction,
                     "reason": r.reason, "status": r.status, "created_at": str(r.created_at)} for r in refunds],
    }
