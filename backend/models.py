from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, Text, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True)
    role = Column(String(20), default="user")          # user / promoter / creator
    wallet_balance = Column(Float, default=0.0)
    # 三级分销树
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)   # 上级ID
    team_size = Column(Integer, default=0)             # 团队成员数（不含自己）
    # 关系
    children = relationship("User", backref="parent", remote_side=[id])


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
    status = Column(String(20), default="pending")           # pending / paid / processing / completed
    ref_user_id = Column(Integer, nullable=True)              # 推广员ID（仅记录直接推荐人）
    custom_requirements = Column(Text, nullable=True)
    creator_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class CommissionConfig(Base):
    """三级分佣比例配置（可动态调整）"""
    __tablename__ = "commission_config"
    id = Column(Integer, primary_key=True, index=True)
    level = Column(Integer, unique=True, nullable=False)         # 1 / 2 / 3
    rate = Column(Float, nullable=False)                         # 例如 0.15 / 0.08 / 0.05
    updated_at = Column(DateTime, default=datetime.now)


class CommissionRecord(Base):
    """每笔分佣明细"""
    __tablename__ = "commission_records"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), index=True)                   # 关联订单
    user_id = Column(Integer, ForeignKey("users.id"), index=True)  # 获佣用户
    level = Column(Integer)                                      # 1/2/3 级
    amount = Column(Float)                                       # 分佣金额
    rate = Column(Float)                                         # 当时的分佣比例
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
    status = Column(String(20), default="pending")             # pending / approved / rejected
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
    payment_info = Column(String(200), nullable=False)         # 支付宝账号/微信号
    status = Column(String(20), default="pending")             # pending / approved / rejected
    admin_remark = Column(String(500), nullable=True)          # 管理员备注
    created_at = Column(DateTime, default=datetime.now)
    reviewed_at = Column(DateTime, nullable=True)

    user = relationship("User")
