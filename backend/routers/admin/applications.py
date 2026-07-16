"""管理员路由 — 入驻审核"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()


@router.get("/applications")
async def list_applications(
    status: str | None = None,
    page: int = Query(1),
    page_size: int = Query(20),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员查看入驻申请列表"""
    query = db.query(m.CreatorApplication).join(m.User)
    if status:
        query = query.filter(m.CreatorApplication.status == status)
    total = query.count()
    results = query.order_by(m.CreatorApplication.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "applications": [{
        "id": a.id, "user_id": a.user_id, "username": a.user.username,
        "real_name": a.real_name, "phone": a.phone, "wechat": a.wechat,
        "specialty": a.specialty, "portfolio_desc": a.portfolio_desc,
        "experience": a.experience, "status": a.status, "created_at": str(a.created_at),
        "review_remark": a.review_remark, "reviewed_at": str(a.reviewed_at) if a.reviewed_at else None,
    } for a in results]}


@router.post("/applications/review")
async def review_application(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员审核入驻申请"""
    application_id = req_body.get("request_id") or req_body.get("application_id")
    status = req_body.get("status")
    remark = req_body.get("remark", "")
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    a = db.query(m.CreatorApplication).filter(
        m.CreatorApplication.id == application_id
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="申请不存在")
    if a.status != "pending":
        raise HTTPException(status_code=400, detail="已处理")
    a.status = status
    a.review_remark = remark
    a.reviewed_at = datetime.now()
    if status == "approved":
        # 制作者身份通过 creator_applications 记录体现，不修改 user.role
        pass
    db.commit()
    return {"id": a.id, "status": a.status}
