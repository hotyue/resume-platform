from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
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
    category = Column(String, index=True) # 比如 "1.中文简历", "2.EnglishResume"
    name = Column(String) # 比如 "001"
    jpg_path = Column(String) # 预览图相对路径
    doc_path = Column(String) # doc/docx 源文件相对路径
    price = Column(Float, default=0.99)
    is_active = Column(Boolean, default=True)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    order_type = Column(String) # "download" 或 "custom_service"
    amount = Column(Float)
    status = Column(String, default="pending") # pending, paid, processing, completed
    ref_user_id = Column(Integer, nullable=True) # 推广人ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
