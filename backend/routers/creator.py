"""制作者路由 — apply / application / resign / orders / take / deliver"""
import os
import traceback as tb
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
import models as m
from auth import get_current_user, require_creator

router = APIRouter(prefix="/api/v1/creator", tags=["creator"])


# ================= Helpers =================

def _get_config(db: Session, key: str, default: float = 0.0) -> float:
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == key).first()
    if cfg:
        return cfg.value
    descriptions = {
        "download_price": "下载订单金额", "custom_price": "定制订单金额",
        "creator_rate": "制作者分佣比例", "level1_rate": "一级推广分佣比例",
        "level2_rate": "二级推广分佣比例", "level3_rate": "三级推广分佣比例(已停用)",
        "deposit_amount": "制作者保证金金额",
    }
    cfg = m.SystemConfig(key=key, value=default, description=descriptions.get(key, key))
    db.add(cfg)
    db.commit()
    return default


def _get_deposit_amount(db: Session) -> float:
    return _get_config(db, "deposit_amount", 20.0)


def _get_auto_accept_hours(db: Session) -> int:
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == "auto_accept_hours").first()
    if cfg:
        try:
            return int(cfg.value)
        except (ValueError, TypeError):
            pass
    return 168


def _audit_log(db: Session, user_id: int, order_no: str, action: str, detail: str = None, penalty_amount: float = 0.0):
    log = m.CreatorAuditLog(
        user_id=user_id,
        order_no=order_no,
        action=action,
        detail=detail,
        penalty_amount=penalty_amount,
        created_at=datetime.now(),
    )
    db.add(log)


def _reset_delivery_cycle(order, db: Session):
    order.claimed_at = datetime.now()
    _audit_log(db, order.creator_id, order.order_no, "cycle_reset", "交付周期重置，重新计时24小时")


def _create_freeze_pending(order, db: Session):
    """定制订单交付时创建冻结记录"""
    if order.commission_distributed:
        return
    amount = order.amount
    hours = _get_auto_accept_hours(db)
    freeze_until = datetime.now() + timedelta(hours=hours)
    pending_records = []

    if not order.creator_id:
        order.commission_distributed = True
        return

    # L1: 制作者本人 30%
    creator_amt = round(amount * 0.30, 2)
    pending_records.append(m.CommissionPending(
        order_no=order.order_no, user_id=order.creator_id,
        role_type="creator", amount=creator_amt, rate=0.30,
        freeze_until=freeze_until,
    ))

    # L2: 制作者的上级 10%
    creator = db.query(m.User).filter(m.User.id == order.creator_id).first()
    if creator and creator.parent_id:
        parent_amt = round(amount * 0.10, 2)
        pending_records.append(m.CommissionPending(
            order_no=order.order_no, user_id=creator.parent_id,
            role_type="referral", amount=parent_amt, rate=0.10,
            freeze_until=freeze_until,
        ))

    if pending_records:
        db.add_all(pending_records)
    order.commission_distributed = True


# ================= File validation =================

ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_WORD_EXTENSIONS = {".doc", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_file_extension(filename: str, file_type: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    if file_type == "pdf":
        return ext in ALLOWED_PDF_EXTENSIONS
    elif file_type == "word":
        return ext in ALLOWED_WORD_EXTENSIONS
    return False


def get_file_content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return content_types.get(ext, "application/octet-stream")


# ================= Schemas =================

class CreatorAppReq:
    pass  # inline for now


class ResignCreatorReq:
    pass


class TakeOrderReq:
    pass


# ================= Endpoints =================

@router.post("/apply")
async def apply_creator(req_body: dict, db: Session = Depends(get_db),
                        current_user: dict = Depends(get_current_user)):
    if db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == current_user["id"],
        m.CreatorApplication.status == "pending"
    ).first():
        raise HTTPException(status_code=400, detail="已有待审核申请")
    deposit_amt = _get_deposit_amount(db)
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if user.wallet_balance < deposit_amt:
        raise HTTPException(status_code=400,
            detail=f"余额不足（需要保证金 {deposit_amt} 元，当前: {round(user.wallet_balance, 2)} 元）")
    user.deposit_frozen += deposit_amt

    # 如果已有 revoked/rejected 记录，直接 UPDATE 复用
    existing = db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == current_user["id"],
        m.CreatorApplication.status.in_(["revoked", "rejected"])
    ).first()
    if existing:
        existing.real_name = req_body.get("real_name", "")
        existing.phone = req_body.get("phone", "")
        existing.wechat = req_body.get("wechat", "")
        existing.specialty = req_body.get("specialty", "")
        existing.portfolio_desc = req_body.get("portfolio_desc", "")
        existing.experience = req_body.get("experience", "")
        existing.status = "pending"
        existing.review_remark = None
        existing.reviewed_at = None
    else:
        db.add(m.CreatorApplication(
            user_id=current_user["id"],
            real_name=req_body.get("real_name", ""),
            phone=req_body.get("phone", ""),
            wechat=req_body.get("wechat", ""),
            specialty=req_body.get("specialty", ""),
            portfolio_desc=req_body.get("portfolio_desc", ""),
            experience=req_body.get("experience", ""),
        ))
    db.commit()
    return {"status": "pending", "message": "申请已提交，保证金已冻结"}


@router.get("/application")
async def get_application(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    a = db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == current_user["id"]
    ).order_by(m.CreatorApplication.created_at.desc()).first()
    if not a:
        return None
    return {"id": a.id, "status": a.status, "review_remark": a.review_remark,
            "real_name": a.real_name, "created_at": str(a.created_at)}


@router.post("/resign")
async def resign_creator(req_body: dict, db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user)):
    """退出制作者

    保证金仅为接单门槛阈值，不代表实际资金。
    正常退出：清除制作者身份和门槛标识
    强制退出：清除制作者身份，未完成订单重新发布
    """
    force = req_body.get("force", False)
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    approved_app = db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == current_user["id"],
        m.CreatorApplication.status == "approved"
    ).first()
    if not approved_app:
        raise HTTPException(status_code=400, detail="当前不是制作者")

    # 检查未完成订单
    pending_orders = db.query(m.Order).filter(
        m.Order.creator_id == current_user["id"],
        m.Order.status.in_(["in_progress", "delivered"])
    ).all()

    if pending_orders:
        if not force:
            order_nos = [o.order_no for o in pending_orders]
            raise HTTPException(
                status_code=400,
                detail=f"存在 {len(pending_orders)} 个未完成订单（{', '.join(order_nos)}），无法退出。如需强制退出，请设置 force=true（将扣除全部余额并将订单重新发布）"
            )

        # 强制退出：扣除全部余额 + 订单重新发布
        balance_deducted = user.wallet_balance
        user.wallet_balance = 0.0
        user.deposit_frozen = 0.0

        # 撤销申请记录
        approved_app.status = "revoked"
        approved_app.reviewed_at = datetime.now()

        for order in pending_orders:
            order.creator_id = None
            order.claimed_at = None
            order.status = "awaiting_claim"
            _audit_log(db, current_user["id"], order.order_no, "creator_exit_forced",
                      "制作者强制退出，订单重新发布至众包大厅")

        _audit_log(db, current_user["id"], "", "creator_exit_forced",
                  f"强制退出制作者，扣除余额 ¥{balance_deducted}，{len(pending_orders)} 个订单重新发布")
        db.commit()
        return {
            "message": "已强制退出制作者",
            "balance_deducted": balance_deducted,
            "orders_republished": len(pending_orders),
        }

    # 正常退出：清除制作者身份
    approved_app.status = "revoked"
    approved_app.reviewed_at = datetime.now()
    user.deposit_frozen = 0.0
    _audit_log(db, current_user["id"], "", "creator_exit_normal", "正常退出制作者，保证金解冻")
    db.commit()
    return {"message": "已退出制作者，保证金已解冻"}


@router.get("/orders")
async def get_creator_orders(
    tab: str = "pending", db: Session = Depends(get_db),
    current_user: dict = Depends(require_creator)):
    # 读取制作者佣金比例
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == "creator_rate").first()
    creator_rate = float(cfg.value) if cfg else 0.30

    query = db.query(m.Order, m.Template).join(m.Template).filter(
        m.Order.order_type.in_(("custom_service", "custom"))
    )
    if tab == "pending":
        results = query.filter(m.Order.status == "awaiting_claim", m.Order.creator_id == None).all()
    else:
        results = query.filter(m.Order.creator_id == current_user["id"]).all()
    out = []
    for o, t in results:
        u = db.query(m.User).filter(m.User.id == o.user_id).first()
        commission_amt = round(o.amount * creator_rate, 2)

        # 进度状态
        delivery_status = "pending"
        if o.status == "in_progress":
            delivery_status = "progress"
        elif o.status == "delivered":
            delivery_status = "delivered"
        elif o.status in ("accepted", "completed"):
            delivery_status = "accepted"

        # 制作超时剩余时间（仅制作中有效）
        hours_remaining = None
        if o.status == "in_progress" and o.claimed_at:
            deadline = o.claimed_at + timedelta(hours=24)
            remaining = (deadline - datetime.now()).total_seconds() / 3600
            hours_remaining = round(remaining, 1)

        # 验收倒计时（仅待验收有效）
        accept_hours_remaining = None
        if o.status == "delivered" and o.freeze_until:
            remaining = (o.freeze_until - datetime.now()).total_seconds() / 3600
            accept_hours_remaining = round(remaining, 1)

        # 制作者未读消息数
        unread_count = (
            db.query(func.count(m.OrderMessage.id))
            .filter(
                m.OrderMessage.order_id == o.id,
                m.OrderMessage.sender_id != current_user["id"],
                m.OrderMessage.is_read == False,
            )
            .scalar() or 0
        )

        out.append({
            "id": o.id,
            "order_no": o.order_no,
            "creator_id": o.creator_id,
            "order_amount": o.amount,
            "commission_amount": commission_amt,
            "commission_rate": creator_rate,
            "status": o.status,
            "requirements": o.custom_requirements,
            "created_at": str(o.created_at),
            "claimed_at": str(o.claimed_at) if o.claimed_at else None,
            "delivered_at": str(o.delivered_at) if o.delivered_at else None,
            "accepted_at": str(o.accepted_at) if o.accepted_at else None,
            "delivery_status": delivery_status,
            "hours_remaining": hours_remaining,
            "accept_hours_remaining": accept_hours_remaining,
            "template_name": t.name,
            "user_name": u.username if u else "未知",
            "unread_count": unread_count,
        })
    return out


@router.post("/take")
async def take_order(
    req_body: dict, db: Session = Depends(get_db),
    current_user: dict = Depends(require_creator)):
    order_no = req_body.get("order_no", "")
    order = db.query(m.Order).filter(
        m.Order.order_no == order_no, m.Order.status == "awaiting_claim", m.Order.creator_id == None
    ).first()
    if not order:
        raise HTTPException(status_code=400, detail="订单已被抢走或状态错误")
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    deposit_amt = _get_deposit_amount(db)
    if user.wallet_balance < deposit_amt:
        raise HTTPException(status_code=400,
            detail=f"余额不足（需要 ≥ {deposit_amt} 元保证金，当前: {round(user.wallet_balance, 2)} 元）")
    order.creator_id = current_user["id"]
    order.status = "in_progress"
    order.claimed_at = datetime.now()
    order.penalty_count = 0
    order.penalty_deducted = 0.0
    db.commit()
    return {"status": "success", "message": "抢单成功"}


@router.post("/deliver")
async def deliver_order(
    order_no: str = Form(...),
    pdf_file: UploadFile = File(...),
    word_file: UploadFile = File(...),
    remark: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_creator),
):
    """交付订单 — 双文件上传（PDF + Word）"""
    from storage import get_storage, StorageError
    try:
        # 1. 查找订单
        order = db.query(m.Order).filter(
            m.Order.order_no == order_no,
            m.Order.creator_id == current_user["id"],
            m.Order.status == "in_progress",
        ).first()
        if not order:
            raise HTTPException(status_code=400, detail="订单异常或无权操作")

        # 2. 校验 PDF 文件
        if not pdf_file.filename or not validate_file_extension(pdf_file.filename, "pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"PDF 文件格式不正确，仅支持 .pdf（当前: {pdf_file.filename}）",
            )

        # 3. 校验 Word 文件
        if not word_file.filename or not validate_file_extension(word_file.filename, "word"):
            raise HTTPException(
                status_code=400,
                detail=f"Word 文件格式不正确，仅支持 .doc / .docx（当前: {word_file.filename}）",
            )

        # 4. 读取文件内容并校验大小
        pdf_data = await pdf_file.read()
        word_data = await word_file.read()

        if len(pdf_data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"PDF 文件过大（{len(pdf_data) / 1024 / 1024:.1f}MB），最大 10MB",
            )
        if len(word_data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Word 文件过大（{len(word_data) / 1024 / 1024:.1f}MB），最大 10MB",
            )

        # 5. 上传到 S3
        try:
            storage = get_storage()
        except StorageError as e:
            raise HTTPException(status_code=503, detail=f"S3 存储未配置: {e}")

        pdf_key = storage.build_key(order.order_no, pdf_file.filename)
        word_key = storage.build_key(order.order_no, word_file.filename)

        storage.upload_file(pdf_key, pdf_data, get_file_content_type(pdf_file.filename))
        storage.upload_file(word_key, word_data, get_file_content_type(word_file.filename))

        # 6. 保存交付记录
        delivery = m.Delivery(
            order_no=order_no,
            pdf_key=pdf_key,
            word_key=word_key,
            pdf_filename=pdf_file.filename,
            word_filename=word_file.filename,
            pdf_size=len(pdf_data),
            word_size=len(word_data),
            remark=remark,
        )
        db.add(delivery)

        order.status = "delivered"
        order.delivered_at = datetime.now()
        hours = _get_auto_accept_hours(db)
        order.freeze_until = datetime.now() + timedelta(hours=hours)
        _reset_delivery_cycle(order, db)
        _create_freeze_pending(order, db)
        db.commit()

        return {
            "status": "success",
            "message": "已交付，等待买家验收",
            "pdf_filename": pdf_file.filename,
            "word_filename": word_file.filename,
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"deliver failed: {tb.format_exc()}")
        raise HTTPException(status_code=500, detail=f"交付失败: {str(e)}")
