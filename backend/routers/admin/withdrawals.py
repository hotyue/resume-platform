"""管理员路由 — 提现审核"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()


@router.get("/withdrawals")
async def admin_withdrawals(
    status: Optional[str] = Query(None, description="pending/approved/rejected"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """提现列表"""
    query = db.query(m.WithdrawRequest, m.User).join(m.User)
    if status:
        query = query.filter(m.WithdrawRequest.status == status)
    total = query.count()
    results = query.order_by(m.WithdrawRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "withdrawals": [{
            "id": w.id, "user_id": w.user_id, "username": u.username,
            "amount": w.amount, "payment_info": w.payment_info,
            "account_type": w.account_type, "status": w.status,
            "transfer_proof": w.transfer_proof,
            "admin_remark": w.admin_remark,
            "created_at": str(w.created_at),
            "reviewed_at": str(w.reviewed_at) if w.reviewed_at else None,
        } for w, u in results],
    }


@router.post("/withdrawals/review")
async def review_withdraw(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """审核提现"""
    request_id = req_body.get("request_id")
    status = req_body.get("status")
    remark = req_body.get("remark", "")
    transfer_proof = req_body.get("transfer_proof")
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    w = db.query(m.WithdrawRequest).filter(m.WithdrawRequest.id == request_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="提现申请不存在")
    if w.status != "pending":
        raise HTTPException(status_code=400, detail=f"已处理（当前: {w.status}）")

    w.status = status
    w.admin_remark = remark
    w.transfer_proof = transfer_proof
    w.reviewed_at = datetime.now()

    if status == "approved":
        # 方案C：批准时扣减余额 + 解冻
        user = db.query(m.User).filter(m.User.id == w.user_id).first()
        if user:
            user.wallet_balance -= w.amount
            user.frozen_withdraw = max(0, (user.frozen_withdraw or 0) - w.amount)
            user.total_withdrawn = (user.total_withdrawn or 0) + w.amount
    elif status == "rejected":
        # 拒绝时解冻
        user = db.query(m.User).filter(m.User.id == w.user_id).first()
        if user:
            user.frozen_withdraw = max(0, (user.frozen_withdraw or 0) - w.amount)

    db.commit()
    return {"id": w.id, "status": w.status, "message": "审核完成"}
