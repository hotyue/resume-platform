"""三级分佣核心逻辑"""
from sqlalchemy.orm import Session
import models


def load_commission_rates(db: Session) -> dict:
    """从数据库加载分佣比例"""
    configs = db.query(models.CommissionConfig).all()
    return {c.level: c.rate for c in configs}


def get_ref_chain(ref_user_id: int, db: Session) -> list:
    rates = load_commission_rates(db)
    chain = []
    current_id = ref_user_id
    for level in range(1, 4):
        if current_id is None:
            break
        user = db.query(models.User).filter(models.User.id == current_id).first()
        if not user:
            break
        rate = rates.get(level, 0)
        chain.append((user.id, level, rate))
        current_id = user.parent_id
    return chain


def distribute_commission(order, db: Session):
    if not order.ref_user_id:
        return
    chain = get_ref_chain(order.ref_user_id, db)
    records = []
    for user_id, level, rate in chain:
        if level > 3:
            break
        commission = round(order.amount * rate, 2)
        if commission <= 0:
            continue
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.wallet_balance += commission
        records.append(models.CommissionRecord(
            order_no=order.order_no, user_id=user_id, level=level,
            amount=commission, rate=rate,
        ))
    if records:
        db.add_all(records)


def update_parent_team_sizes(parent_id: int, db: Session):
    """更新父级团队的 team_size"""
    current = parent_id
    for _ in range(3):
        u = db.query(models.User).filter(models.User.id == current).first()
        if u:
            u.team_size = db.query(models.User).filter(models.User.parent_id == current).count()
            current = u.parent_id
        else:
            break


def resolve_ref_parent(ref_code: str, db: Session):
    """解析邀请码，返回 parent_id"""
    if not ref_code:
        return None
    try:
        ref_user_id = int(ref_code.replace("INVITE_", ""))
        parent = db.query(models.User).filter(models.User.id == ref_user_id).first()
        if parent:
            return parent.id
    except (ValueError, AttributeError):
        pass
    return None


# ---------------------------------------------------------------------------
# 辅助函数（原在 main.py 中）
# ---------------------------------------------------------------------------
from datetime import datetime


def audit_log(db: Session, user_id: int, order_no: str, action: str, detail: str = None, penalty_amount: float = 0.0):
    """记录制作者风险管控审计日志"""
    log = models.CreatorAuditLog(
        user_id=user_id,
        order_no=order_no,
        action=action,
        detail=detail,
        penalty_amount=penalty_amount,
        created_at=datetime.now(),
    )
    db.add(log)


def settle_custom_commission(order, db: Session):
    """验收通过 — 释放冻结佣金，创建分佣记录，加统计字段和余额"""
    pending = db.query(models.CommissionPending).filter(
        models.CommissionPending.order_no == order.order_no,
        models.CommissionPending.status == "pending"
    ).all()
    now = datetime.now()
    for p in pending:
        user = db.query(models.User).filter(models.User.id == p.user_id).first()
        if user:
            if p.role_type == "creator":
                user.making_commission += p.amount
            else:
                user.referral_commission += p.amount
            user.wallet_balance += p.amount

        # 创建分佣记录（验收后才产生）
        level = 0 if p.role_type == "creator" else 1
        db.add(models.CommissionRecord(
            order_no=order.order_no, user_id=p.user_id,
            level=level, amount=p.amount, rate=p.rate,
        ))

        p.status = "released"
        p.released_at = now


def check_delivery_penalties(db: Session):
    """检查超时订单并扣除违约金（每8h扣10%，上限50%），72h超时重新发布"""
    now = datetime.now()
    in_progress_orders = db.query(models.Order).filter(
        models.Order.status == "in_progress",
        models.Order.claimed_at != None,
        models.Order.creator_id != None,
    ).all()

    results = []
    for order in in_progress_orders:
        if not order.claimed_at:
            continue

        elapsed = now - order.claimed_at
        elapsed_hours = elapsed.total_seconds() / 3600

        # 超过72小时：重新发布到众包大厅
        if elapsed_hours >= 72:
            creator_id = order.creator_id
            order_no = order.order_no
            order.status = "awaiting_claim"
            order.creator_id = None
            order.claimed_at = None
            order.penalty_count = 5
            order.penalty_deducted = round(order.amount * 0.50, 2)

            audit_log(db, creator_id, order_no, "order_republished",
                      f"72h超时重新发布至众包大厅（累计违约金 ¥{order.penalty_deducted}）")

            results.append({
                "order_no": order_no,
                "creator_id": creator_id,
                "action": "republished",
                "reason": "72h超时",
            })
            continue

        # 超过24小时才开始扣违约金
        if elapsed_hours < 24:
            continue

        overdue_hours = elapsed_hours - 24
        expected_penalty_count = int(overdue_hours / 8) + 1
        expected_penalty_count = min(expected_penalty_count, 5)

        current_count = order.penalty_count or 0
        if expected_penalty_count > current_count:
            new_penalties = expected_penalty_count - current_count
            penalty_per_unit = round(order.amount * 0.10, 2)
            total_new_penalty = round(penalty_per_unit * new_penalties, 2)

            creator = db.query(models.User).filter(models.User.id == order.creator_id).first()
            if creator:
                can_deduct = min(total_new_penalty, creator.wallet_balance)
                creator.wallet_balance -= can_deduct

                if can_deduct < total_new_penalty:
                    audit_log(db, order.creator_id, order.order_no, "penalty_insufficient",
                              f"余额不足以支付违约金：需 ¥{total_new_penalty}，仅扣 ¥{can_deduct}")

            order.penalty_count = expected_penalty_count
            order.penalty_deducted = round((order.penalty_deducted or 0) + total_new_penalty, 2)

            audit_log(db, order.creator_id, order.order_no, "penalty_deducted",
                      f"超时违约金：已逾期 {elapsed_hours:.1f}h，第 {expected_penalty_count} 个周期，"
                      f"扣除 ¥{total_new_penalty}（累计 ¥{order.penalty_deducted}）",
                      penalty_amount=total_new_penalty)

            results.append({
                "order_no": order.order_no,
                "creator_id": order.creator_id,
                "penalty": total_new_penalty,
                "total_deducted": order.penalty_deducted,
            })

    if results:
        db.commit()

    return results
