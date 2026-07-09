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
