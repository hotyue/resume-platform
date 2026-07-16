"""分佣与违约金核心逻辑"""
from sqlalchemy.orm import Session
from datetime import datetime
import models as m


def audit_log(db: Session, user_id: int, order_no: str, action: str, detail: str, penalty_amount: float = None):
    """记录审计日志"""
    try:
        log = m.AuditLog(user_id=user_id, order_no=order_no, action=action, detail=detail)
        if penalty_amount is not None:
            log.penalty_amount = penalty_amount
        db.add(log)
        db.flush()
    except Exception:
        pass


def load_commission_rates(db: Session) -> dict:
    """从数据库加载分佣比例"""
    configs = db.query(m.CommissionConfig).all()
    return {c.level: c.rate for c in configs}


def get_ref_chain(ref_user_id: int, db: Session) -> list:
    rates = load_commission_rates(db)
    chain = []
    current_id = ref_user_id
    for level in range(1, 4):
        if current_id is None:
            break
        user = db.query(m.User).filter(m.User.id == current_id).first()
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
        user = db.query(m.User).filter(m.User.id == user_id).first()
        if user:
            user.wallet_balance += commission
        records.append(m.CommissionRecord(
            order_no=order.order_no, user_id=user_id, level=level,
            amount=commission, rate=rate,
        ))
    if records:
        db.add_all(records)


def update_parent_team_sizes(parent_id: int, db: Session):
    """更新父级团队的 team_size"""
    current = parent_id
    for _ in range(3):
        u = db.query(m.User).filter(m.User.id == current).first()
        if u:
            u.team_size = db.query(m.User).filter(m.User.parent_id == current).count()
            current = u.parent_id
        else:
            break


def resolve_ref_parent(ref_code: str, db: Session):
    """解析邀请码，返回 parent_id"""
    if not ref_code:
        return None
    try:
        ref_user_id = int(ref_code.replace("INVITE_", ""))
        parent = db.query(m.User).filter(m.User.id == ref_user_id).first()
        if parent:
            return parent.id
    except (ValueError, AttributeError):
        pass
    return None


def check_delivery_penalties(db: Session) -> list:
    """检查超时订单并扣除违约金（每8h扣10%，上限50%），72h超时重新发布"""
    now = datetime.now()
    in_progress_orders = db.query(m.Order).filter(
        m.Order.status == "in_progress",
        m.Order.claimed_at != None,
        m.Order.creator_id != None,
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
            order.penalty_count = 5  # 上限
            order.penalty_deducted = round(order.amount * 0.50, 2)  # 上限50%

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

        # 计算应该扣几个8h周期
        overdue_hours = elapsed_hours - 24
        expected_penalty_count = int(overdue_hours / 8) + 1

        # 违约金上限50%（即5个周期）
        max_penalty_count = 5
        expected_penalty_count = min(expected_penalty_count, max_penalty_count)

        # 是否需要补扣
        current_count = order.penalty_count or 0
        if expected_penalty_count > current_count:
            new_penalties = expected_penalty_count - current_count
            penalty_per_unit = round(order.amount * 0.10, 2)
            total_new_penalty = round(penalty_per_unit * new_penalties, 2)

            creator = db.query(m.User).filter(m.User.id == order.creator_id).first()
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
                "action": "penalty_deducted",
                "amount": total_new_penalty,
                "elapsed_hours": elapsed_hours,
            })

    if results:
        db.commit()

    return results
