from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, Text, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=True)
    role = Column(String(20), default="user")
    wallet_balance = Column(Float, default=0.0)
    deposit_frozen = Column(Float, default=0.0)           # 制作者保证金冻结额
    # 三级分销树
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    team_size = Column(Integer, default=0)
    # 提现账户
    alipay_account = Column(String(100), nullable=True)
    wechat_account = Column(String(100), nullable=True)
    total_withdrawn = Column(Float, default=0.0)
    frozen_commission = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    # 关系
    children = relationship("User", backref="parent", remote_side=[id])

    @property
    def available_balance(self):
        """可提现余额（扣除保证金）"""
        return self.wallet_balance - self.deposit_frozen


class Template(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100))
    name = Column(String(200))
    jpg_path = Column(String(500))
    doc_path = Column(String(500))
    price = Column(Float, default=1.99)
    is_active = Column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), unique=True, index=True)
    user_id = Column(Integer, nullable=True)
    template_id = Column(Integer, ForeignKey("templates.id"))
    order_type = Column(String(20), default="download")     # download / custom_service
    amount = Column(Float, default=1.99)
    status = Column(String(20), default="pending")
    # 状态枚举:
    #   pending          待支付
    #   paid             已支付
    #   awaiting_claim   待抢单
    #   claimed          已抢单
    #   in_progress      制作中
    #   delivered        已交付(等待验收)
    #   accepted         买家确认
    #   rejected         买家拒绝(退回制作)
    #   refund_requested 已申请退款(等待审核)
    #   refunded         已退款
    #   completed        已完成(佣金已发放)
    #   cancelled        已取消
    ref_user_id = Column(Integer, nullable=True)
    custom_requirements = Column(Text, nullable=True)
    creator_id = Column(Integer, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    freeze_until = Column(DateTime, nullable=True)
    commission_distributed = Column(Boolean, default=False)  # 下载订单分佣标记
    created_at = Column(DateTime, default=datetime.now)


class CommissionConfig(Base):
    """三级分佣比例配置（可动态调整）"""
    __tablename__ = "commission_config"
    id = Column(Integer, primary_key=True, index=True)
    level = Column(Integer, unique=True, nullable=False)
    rate = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.now)


class CommissionRecord(Base):
    """每笔分佣明细"""
    __tablename__ = "commission_records"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    level = Column(Integer)
    amount = Column(Float)
    rate = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User")


class CreatorApplication(Base):
    """制作者入驻申请表"""
    __tablename__ = "creator_applications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    real_name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    wechat = Column(String(50), nullable=False)
    specialty = Column(String(200), default="")
    portfolio_desc = Column(Text, default="")
    experience = Column(Text, default="")
    status = Column(String(20), default="pending")
    review_remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    reviewed_at = Column(DateTime, nullable=True)
    user = relationship("User")


class WithdrawRequest(Base):
    """提现申请"""
    __tablename__ = "withdraw_requests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_info = Column(String(200), nullable=False)
    status = Column(String(20), default="pending")
    admin_remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    reviewed_at = Column(DateTime, nullable=True)
    user = relationship("User")


class Delivery(Base):
    """定制订单交付记录"""
    __tablename__ = "deliveries"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), nullable=False, index=True)
    file_url = Column(String(500), nullable=False)
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)


class Review(Base):
    """买家验收记录"""
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), nullable=False, index=True)
    result = Column(String(20), nullable=False)
    buyer_remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)


class CommissionPending(Base):
    """待发放佣金（冻结期管理）"""
    __tablename__ = "commission_pending"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    freeze_until = Column(DateTime, nullable=False)
    status = Column(String(20), default="pending")
    released_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User")


class SystemConfig(Base):
    """系统配置（管理员可改）"""
    __tablename__ = "system_config"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Float, nullable=False)
    description = Column(String(200), default="")
    updated_at = Column(DateTime, default=datetime.now)


class RefundRequest(Base):
    """退款申请"""
    __tablename__ = "refund_requests"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), nullable=False, index=True)
    buyer_id = Column(Integer, nullable=False)
    creator_id = Column(Integer, nullable=True)
    refund_amount = Column(Float, nullable=False)       # 平台承担的退款额
    creator_deduction = Column(Float, nullable=False)    # 制作者扣款额
    reason = Column(Text, default="")
    status = Column(String(20), default="pending")       # pending / approved / rejected
    admin_remark = Column(String(500), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class RechargeRecord(Base):
    """充值记录"""
    __tablename__ = "recharge_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    method = Column(String(20), default="manual")        # manual / payjs
    status = Column(String(20), default="completed")      # pending / completed / failed
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User")
