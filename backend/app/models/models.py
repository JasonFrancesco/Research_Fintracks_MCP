from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to transactions and chat histories
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    chat_histories = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    gatling_tests = relationship("GatlingTestRun", back_populates="user", cascade="all, delete-orphan")
    gatling_chat_histories = relationship("GatlingChatHistory", back_populates="user", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    category = Column(String, nullable=False)
    transaction_type = Column(String, nullable=False) # 'income' or 'expense'
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to user
    user = relationship("User", back_populates="transactions")

class ChatHistory(Base):
    __tablename__ = "chat_histories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False) # 'user' or 'ai'
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to user
    user = relationship("User", back_populates="chat_histories")


class GatlingTestRun(Base):
    __tablename__ = "gatling_test_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    simulation_name = Column(String, nullable=False)
    scenario_description = Column(Text, nullable=True)
    target_queue = Column(String, nullable=False)
    virtual_users = Column(Integer, default=100)
    duration_seconds = Column(Integer, default=30)
    status = Column(String, default="completed")  # queued, running, completed, failed
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    mean_response_time = Column(Numeric(10, 2), default=0.0)  # ms
    p95_response_time = Column(Numeric(10, 2), default=0.0)   # ms
    p99_response_time = Column(Numeric(10, 2), default=0.0)   # ms
    error_rate = Column(Numeric(5, 2), default=0.0)           # percentage (e.g. 0.50%)
    report_url = Column(String, nullable=True)
    report_summary = Column(Text, nullable=True)
    generated_script = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="gatling_tests")


class GatlingChatHistory(Base):
    __tablename__ = "gatling_chat_histories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'ai'
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="gatling_chat_histories")


