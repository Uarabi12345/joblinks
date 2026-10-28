from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    reset_code = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class JobLink(Base):
    __tablename__ = "job_links"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    real_url = Column(String, nullable=False)
    image_url = Column(String, default="")
    status = Column(String, default="available")
    batch_id = Column(Integer, default=1)
    unlock_fee = Column(Integer, default=100)
    payout_amount = Column(String, default="1000")
    taken_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_link_id = Column(Integer, ForeignKey("job_links.id"), nullable=True) # FIXED
    payment_type = Column(String, default="activation")
    message = Column(Text, nullable=True)
    checkout_request_id = Column(String, index=True)
    merchant_request_id = Column(String)
    amount = Column(Integer, default=0)
    phone = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())

class SystemConfig(Base):
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, default=1)
    current_batch = Column(Integer, default=1)