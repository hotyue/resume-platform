"""管理员路由 — 退款审核"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()


@router.get("/refunds")
async def admin_refunds(
    status: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(20),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    query = db.query(m.RefundRequest)
    if status:
        query = query.filter(m.RefundRequest.status == status)
    total = query.count()
    results = query.order_by(m.RefundRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for r in results:
        buyer = db.query(m.User).filter(m.User.id == r.buyer_id).first()
        creator = db.query(m.User).filter(m.User.id == r.creator_id).first() if r.creator_id else None
        items.append({
            "id": r.id, "order_no": r.order_no,
            "buyer": buyer.username if buyer else "未知",
            "creator": creator.username if creator else "无",
            "refund_amount": r.refund_amount, "creator_deduction": r.creator_deduction,
            "reason": r.reason, "status": r.status, "created_at": str(r.created_at)
        })
    return {"total": total, "page": page, "page_size": page_size, "refunds": items}


@router.post("/refunds/review")
async def review_refund(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    refund_id = req_body.get("refund_id")
    status = req_body.get("status")
    remark = req_body.get("remark", "")
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    r = db.query(m.RefundRequest).filter(m.RefundRequest.id == refund_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="退款申请不存在")
    if r.status != "pending":
        raise HTTPException(status_code=400, detail="已处理")
    r.status = status
    r.admin_remark = remark
    r.reviewed_at = datetime.now()
    if status == "approved":
        order = db.query(m.Order).filter(m.Order.order_no == r.order_no).first()
        buyer = db.query(m.User).filter(m.User.id == r.buyer_id).first()
        if order:
            order.status = "refunded"
        if buyer:
            buyer.wallet_balance += r.refund_amount
        if r.creator_id:
            creator = db.query(m.User).filter(m.User.id == r.creator_id).first()
            if creator:
                creator.wallet_balance -= r.creator_deduction
    db.commit()
    return {"id": r.id, "status": r.status}
