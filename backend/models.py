from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    role = Column(String, default="user") # user, promoter, creator, admin
    wallet_balance = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Template(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True)
    name = Column(String)
    jpg_path = Column(String)
    doc_path = Column(String)
    price = Column(Float, default=0.99)
    is_active = Column(Boolean, default=True)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    order_type = Column(String, default="download") # download / custom_service
    amount = Column(Float)
    status = Column(String, default="pending") # pending, paid, processing, completed
    ref_user_id = Column(Integer, nullable=True) 
    
    # === 众包代做新增字段 ===
    custom_requirements = Column(Text, nullable=True) # 客户填写的需求
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True) # 接单的创作者ID
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    payment_info = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
