from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    import_batch_id = Column(Integer, ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    transaction_code = Column(String(50), index=True, nullable=True)  # e.g. T1051
    date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    counterparty = Column(String(255), nullable=True)  # e.g. Sysco, Toast POS
    raw_payee = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)  # positive = inflow/revenue, negative = outflow/expense
    method = Column(String(100), nullable=True)  # ACH, Card, Bank deposit
    account_name = Column(String(100), default="Primary Checking")
    
    # Categorization
    category = Column(String(100), nullable=True, index=True)
    pnl_bucket = Column(String(50), nullable=True, index=True)  # Revenue, COGS, Payroll, OpEx, Non-P&L
    confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    rationale = Column(Text, nullable=True)
    
    # Review & Audit
    is_flagged_for_review = Column(Boolean, default=False, index=True)
    review_status = Column(String(50), default="pending")  # pending, confirmed, corrected, dismissed
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="transactions")
    import_batch = relationship("ImportBatch", back_populates="transactions")
    audit_logs = relationship("AuditLog", back_populates="transaction")


class AuditLog(Base):
    """
    Immutable, append-only audit trail for all critical accounting actions,
    manual category overrides, and AI-assisted batch classifications.
    Never cascade-deleted when transactions or users are removed.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type = Column(String(50), default="transaction", nullable=False)
    entity_id = Column(String(100), nullable=True)
    action = Column(String(50), default="category_override", nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # Backward-compatible fields
    previous_category = Column(String(100), nullable=True)
    new_category = Column(String(100), nullable=False)
    source = Column(String(50), default="user", nullable=False)  # "model" or "user"
    note = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    transaction = relationship("Transaction", back_populates="audit_logs")
    tenant = relationship("Tenant", back_populates="audit_logs")
    user = relationship("User")
