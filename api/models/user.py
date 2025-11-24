"""
User model - stores user authentication data.
TODO: Implement full SQLAlchemy model
"""
# from sqlalchemy import Column, String, Boolean, DateTime
# from sqlalchemy.dialects.postgresql import UUID
# from database import Base
# import uuid
# from datetime import datetime
#
# class User(Base):
#     __tablename__ = "users"
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     email = Column(String(255), unique=True, nullable=False, index=True)
#     password_hash = Column(String(255), nullable=False)
#     is_email_confirmed = Column(Boolean, default=False)
#     email_confirmation_token = Column(String(255), nullable=True)
#     email_confirmation_sent_at = Column(DateTime, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
