from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base


class ChartOfAccountsMapping(Base):
    __tablename__ = "chart_of_accounts_mappings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_category = Column(String(255), nullable=False)
    standard_category = Column(String(100), nullable=False)
    pnl_bucket = Column(String(50), nullable=False)  # Revenue, COGS, Payroll, OpEx, Non-P&L
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("tenant_id", "raw_category", name="uq_tenant_raw_category"),
    )

    tenant = relationship("Tenant", back_populates="chart_mappings")
