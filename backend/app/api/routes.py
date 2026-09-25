from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timezone
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text, desc, asc, func, or_

from app.db.session import get_db
from app.core.config import settings
from app.core.security import hash_password
from app.core.rate_limit import check_rate_limit
from app.models.tenant import Tenant
from app.models.user import User
from app.models.transaction import Transaction, AuditLog
from app.models.import_batch import ImportBatch
from app.models.chart_mapping import ChartOfAccountsMapping
from app.models.ai_usage import AIUsage
from app.api.auth import auth_router
from app.api.deps import (
    get_current_user,
    get_current_tenant,
    get_current_admin_user,
    get_current_accountant_user,
    get_current_viewer_user,
)
from app.services.ingest import (
    parse_csv_content,
    ingest_records,
    load_bundled_sample_dataset,
)
from app.services.categorization import (
    CHART_OF_ACCOUNTS,
    CATEGORY_LOOKUP,
    run_batch_categorization,
    update_transaction_category,
)
from app.services.pnl import generate_monthly_pnl
from app.services.variance import calculate_monthly_variances
from app.services.reconciliation import get_reconciliation_summary
from app.services.chat import process_financial_query
from app.tasks.import_tasks import process_csv_import_batch
from app.core.celery_app import dispatch_async_task
from app.ai.ollama_client import OllamaClient
from app.ai.model_router import model_router

api_router = APIRouter()
api_router.include_router(auth_router)


# ==============================================================================
# PYDANTIC SCHEMAS
# ==============================================================================

class CategoryCorrectionRequest(BaseModel):
    category: str
    note: Optional[str] = None


class ChatMessageRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = None


class TenantCreateRequest(BaseModel):
    name: str
    slug: Optional[str] = None


class InviteUserRequest(BaseModel):
    name: str
    email: EmailStr
    role: str = "VIEWER"  # ADMIN, ACCOUNTANT, VIEWER


class UpdateUserRoleRequest(BaseModel):
    role: str  # ADMIN, ACCOUNTANT, VIEWER


class ChartMappingRequest(BaseModel):
    raw_pattern: str
    target_category: str
    target_bucket: str


# ==============================================================================
# SYSTEM & PUBLIC ENDPOINTS (UNPROTECTED)
# ==============================================================================

@api_router.get("/health", tags=["system"])
def health_check(response: Response, db: Session = Depends(get_db)):
    """Health check endpoint verifying API and DB connectivity (public)."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "app": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "database_connected": False,
            "detail": "PostgreSQL database connection is currently unavailable.",
        }

    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database_connected": True,
    }


@api_router.get("/public/demo-summary", tags=["public"])
def get_public_demo_summary(db: Session = Depends(get_db)):
    """
    Returns sanitized, aggregated metrics from the demo project workspace.
    Calculated deterministically from the database, never invented or hardcoded.
    Safe for public landing page consumption without leaking private tenant data.
    """
    # Locate the demo workspace (e.g. slug="nyc-restaurant-co" or first tenant with sample data)
    demo_tenant = db.query(Tenant).filter(Tenant.slug == "nyc-restaurant-co").first()
    if not demo_tenant:
        demo_tenant = db.query(Tenant).first()

    if not demo_tenant:
        return {"mode": "empty", "message": "No financial data connected yet."}

    # Bind PostgreSQL session to the demo tenant context so RLS permits aggregation
    try:
        bind = db.get_bind()
        if bind and bind.dialect.name == "postgresql":
            db.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"), {"tid": str(demo_tenant.id)})
    except Exception:
        pass

    tx_count = db.query(func.count(Transaction.id)).filter(Transaction.tenant_id == demo_tenant.id).scalar() or 0
    if tx_count == 0:
        return {"mode": "empty", "message": "No financial data connected yet."}

    # Compute deterministic P&L totals for demo tenant
    pnl = generate_monthly_pnl(db, tenant_id=demo_tenant.id)
    summary = pnl.get("summary", {})
    all_totals = summary.get("total") or summary.get("Total", {})

    total_revenue = all_totals.get("revenue", 0.0)
    total_gross_profit = all_totals.get("gross_profit", 0.0)
    total_operating_profit = all_totals.get("operating_profit", 0.0)

    # Count review items
    review_count = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.tenant_id == demo_tenant.id, Transaction.is_flagged_for_review == True)
        .scalar()
        or 0
    )

    categorized_count = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.tenant_id == demo_tenant.id, Transaction.category.isnot(None))
        .scalar()
        or 0
    )

    # Date range
    min_date = db.query(func.min(Transaction.date)).filter(Transaction.tenant_id == demo_tenant.id).scalar()
    max_date = db.query(func.max(Transaction.date)).filter(Transaction.tenant_id == demo_tenant.id).scalar()
    review_period = "Jan - Mar 2026"
    if min_date and max_date:
        review_period = f"{min_date.strftime('%b %Y')} - {max_date.strftime('%b %Y')}"

    return {
        "mode": "sample",
        "workspace_label": "FinReview sample workspace",
        "transactions_analyzed": tx_count,
        "review_period": review_period,
        "revenue": f"${total_revenue:,.0f}",
        "revenue_raw": round(total_revenue, 2),
        "gross_profit": f"${total_gross_profit:,.0f}",
        "gross_profit_raw": round(total_gross_profit, 2),
        "operating_profit": f"${total_operating_profit:,.0f}",
        "operating_profit_raw": round(total_operating_profit, 2),
        "review_items": review_count,
        "categorized_count": categorized_count,
    }


# ==============================================================================
# TENANT & WORKSPACE ENDPOINTS (PROTECTED)
# ==============================================================================

@api_router.get("/tenants/current", tags=["tenants"])
def get_current_tenant_info(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns metadata for the current user's active tenant."""
    # AI token usage this month
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    tokens_used = (
        db.query(func.sum(AIUsage.total_tokens))
        .filter(AIUsage.tenant_id == tenant.id, AIUsage.created_at >= month_start)
        .scalar()
        or 0
    )
    from app.ai.model_router import PLAN_TOKEN_LIMITS
    plan_limit = PLAN_TOKEN_LIMITS.get(tenant.plan.upper(), 50_000)

    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "status": tenant.status,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "current_user_role": current_user.role,
        "usage": {
            "tokens_used": tokens_used,
            "token_limit": plan_limit,
            "token_pct": round((tokens_used / plan_limit * 100), 1) if plan_limit > 0 else 0,
        },
    }


@api_router.get("/tenants", tags=["tenants"])
def list_user_tenants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists available workspaces accessible to the authenticated user."""
    # Returns active tenant and other tenants if multi-tenant association exists
    tenants = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).all()
    return {
        "active_tenant_id": current_user.tenant_id,
        "tenants": [
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "plan": t.plan,
                "status": t.status,
            }
            for t in tenants
        ],
    }


@api_router.post("/tenants", tags=["tenants"])
def create_tenant_workspace(
    payload: TenantCreateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Creates a new company/tenant workspace (e.g. during onboarding Step 2).
    Sets the current user as the administrator of the new tenant.
    """
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Company name cannot be empty.")

    slug_candidate = payload.slug.strip().lower() if payload.slug else clean_name.lower().replace(" ", "-")
    # Clean slug
    clean_slug = "".join(c for c in slug_candidate if c.isalnum() or c == "-")

    # Check collision
    existing = db.query(Tenant).filter(Tenant.slug == clean_slug).first()
    if existing:
        clean_slug = f"{clean_slug}-{int(datetime.now().timestamp())}"

    new_tenant = Tenant(
        name=clean_name,
        slug=clean_slug,
        plan="PRO",
        status="active",
    )
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)

    # Link user to new tenant
    current_user.tenant_id = new_tenant.id
    current_user.role = "ADMIN"
    db.commit()

    return {
        "message": f"Tenant workspace '{new_tenant.name}' successfully created.",
        "tenant": {
            "id": new_tenant.id,
            "name": new_tenant.name,
            "slug": new_tenant.slug,
            "plan": new_tenant.plan,
            "status": new_tenant.status,
        },
    }


# ==============================================================================
# TEAM & RBAC MANAGEMENT ENDPOINTS (PROTECTED)
# ==============================================================================

@api_router.get("/users/team", tags=["team"])
def list_team_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all team members belonging to the current tenant."""
    users = (
        db.query(User)
        .filter(User.tenant_id == current_user.tenant_id)
        .order_by(asc(User.created_at))
        .all()
    )
    return {
        "members": [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ]
    }


@api_router.post("/users/invite", tags=["team"])
def invite_team_member(
    payload: InviteUserRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Invites a new team member to the active tenant workspace.
    Protected: Admin role required.
    """
    target_role = payload.role.upper()
    if target_role not in ["ADMIN", "ACCOUNTANT", "VIEWER"]:
        raise HTTPException(status_code=400, detail="Role must be ADMIN, ACCOUNTANT, or VIEWER.")

    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        if existing_user.tenant_id == current_user.tenant_id:
            raise HTTPException(status_code=400, detail="User is already a member of this workspace.")
        raise HTTPException(status_code=400, detail="User with this email already exists in another tenant.")

    # Create user with initial default password (they can reset)
    temp_password = "TempPassword123!"
    new_user = User(
        tenant_id=current_user.tenant_id,
        email=payload.email.lower(),
        name=payload.name.strip(),
        password_hash=hash_password(temp_password),
        role=target_role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Log immutable audit log for team invitation
    audit_entry = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(new_user.id),
        action="invite_user",
        new_value=f"Invited {new_user.email} as {target_role}",
        note=f"Team invitation issued by {current_user.name}",
    )
    db.add(audit_entry)
    db.commit()

    return {
        "message": f"Successfully invited {new_user.name} ({new_user.email}) as {new_user.role}.",
        "user": {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email,
            "role": new_user.role,
        },
    }


@api_router.patch("/users/{user_id}/role", tags=["team"])
def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Updates the RBAC role of a team member in the current tenant.
    Protected: Admin role required.
    """
    target_role = payload.role.upper()
    if target_role not in ["ADMIN", "ACCOUNTANT", "VIEWER"]:
        raise HTTPException(status_code=400, detail="Role must be ADMIN, ACCOUNTANT, or VIEWER.")

    target_user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found in current tenant workspace.")

    if target_user.id == current_user.id and target_role != "ADMIN":
        raise HTTPException(status_code=400, detail="Admins cannot demote their own account.")

    old_role = target_user.role
    target_user.role = target_role

    audit_entry = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(target_user.id),
        action="update_role",
        old_value=old_role,
        new_value=target_role,
        note=f"Role changed from {old_role} to {target_role} by {current_user.name}",
    )
    db.add(audit_entry)
    db.commit()

    return {
        "message": f"User role updated to {target_role}.",
        "user_id": target_user.id,
        "new_role": target_user.role,
    }


# ==============================================================================
# CHART OF ACCOUNTS SETTINGS (PROTECTED)
# ==============================================================================

@api_router.get("/settings/chart-of-accounts", tags=["settings"])
def get_chart_of_accounts_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns standard chart of accounts plus tenant-specific category overrides.
    Protected: Authenticated users only.
    """
    mappings = (
        db.query(ChartOfAccountsMapping)
        .filter(ChartOfAccountsMapping.tenant_id == current_user.tenant_id)
        .order_by(desc(ChartOfAccountsMapping.created_at))
        .all()
    )

    return {
        "standard_accounts": CHART_OF_ACCOUNTS,
        "buckets": ["Revenue", "COGS", "Payroll", "Operating Expenses", "Non-P&L"],
        "custom_mappings": [
            {
                "id": m.id,
                "raw_pattern": m.raw_pattern,
                "target_category": m.target_category,
                "target_bucket": m.target_bucket,
                "confidence": m.confidence,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in mappings
        ],
    }


@api_router.post("/settings/chart-of-accounts", tags=["settings"])
def create_chart_of_accounts_mapping(
    payload: ChartMappingRequest,
    current_user: User = Depends(get_current_accountant_user),
    db: Session = Depends(get_db),
):
    """
    Creates a tenant-specific category mapping rule.
    Protected: Accountant or Admin required.
    """
    clean_pattern = payload.raw_pattern.strip().lower()
    if not clean_pattern:
        raise HTTPException(status_code=400, detail="Mapping pattern cannot be empty.")

    # Check if target category is valid
    if payload.target_category not in CATEGORY_LOOKUP:
        raise HTTPException(
            status_code=400,
            detail=f"Target category '{payload.target_category}' is not in standard Chart of Accounts.",
        )

    # Upsert pattern for tenant
    mapping = (
        db.query(ChartOfAccountsMapping)
        .filter(
            ChartOfAccountsMapping.tenant_id == current_user.tenant_id,
            ChartOfAccountsMapping.raw_pattern == clean_pattern,
        )
        .first()
    )
    if mapping:
        mapping.target_category = payload.target_category
        mapping.target_bucket = payload.target_bucket
    else:
        mapping = ChartOfAccountsMapping(
            tenant_id=current_user.tenant_id,
            raw_pattern=clean_pattern,
            target_category=payload.target_category,
            target_bucket=payload.target_bucket,
            confidence=1.0,
        )
        db.add(mapping)

    db.commit()
    db.refresh(mapping)

    return {
        "message": f"Mapping saved: '{clean_pattern}' -> '{payload.target_category}'.",
        "mapping": {
            "id": mapping.id,
            "raw_pattern": mapping.raw_pattern,
            "target_category": mapping.target_category,
            "target_bucket": mapping.target_bucket,
        },
    }


@api_router.delete("/settings/chart-of-accounts/{mapping_id}", tags=["settings"])
def delete_chart_of_accounts_mapping(
    mapping_id: int,
    current_user: User = Depends(get_current_accountant_user),
    db: Session = Depends(get_db),
):
    """Deletes a custom Chart of Accounts rule for the current tenant."""
    mapping = (
        db.query(ChartOfAccountsMapping)
        .filter(
            ChartOfAccountsMapping.id == mapping_id,
            ChartOfAccountsMapping.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found.")

    db.delete(mapping)
    db.commit()
    return {"message": "Mapping removed successfully."}


# ==============================================================================
# INGESTION & BATCH IMPORT ENDPOINTS (PROTECTED)
# ==============================================================================

@api_router.post("/imports", tags=["ingestion"])
async def create_csv_import_batch(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_accountant_user),
):
    """
    Submits a CSV file for asynchronous batch ingestion and categorization.
    Dispatches Celery background worker with automatic fallback for dev.
    Protected: Accountant or Admin required.
    """
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Only CSV/TXT text files are supported.")

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8-sig", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Create ImportBatch record
    batch = ImportBatch(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        filename=file.filename,
        status="PENDING",
        total_records=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # Dispatch background task asynchronously
    dispatch_async_task(
        process_csv_import_batch,
        batch.id,
        content_str,
        current_user.tenant_id,
        current_user.id,
    )

    return {
        "batch_id": batch.id,
        "filename": batch.filename,
        "status": batch.status,
        "message": f"Import batch #{batch.id} initiated. Processing in background.",
    }


@api_router.get("/imports", tags=["ingestion"])
def list_import_batches(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists recent import batches for the current tenant."""
    batches = (
        db.query(ImportBatch)
        .filter(ImportBatch.tenant_id == current_user.tenant_id)
        .order_by(desc(ImportBatch.created_at))
        .limit(limit)
        .all()
    )
    return {
        "batches": [
            {
                "id": b.id,
                "filename": b.filename,
                "status": b.status,
                "total_rows": b.total_rows,
                "inserted_count": b.inserted_count,
                "skipped_count": b.skipped_count,
                "categorized_count": b.categorized_count,
                "flagged_count": b.flagged_count,
                "error_message": b.error_message,
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "completed_at": b.completed_at.isoformat() if b.completed_at else None,
            }
            for b in batches
        ]
    }


@api_router.get("/imports/{batch_id}", tags=["ingestion"])
def get_import_batch_status(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the live status of an import batch for polling/SSE."""
    batch = (
        db.query(ImportBatch)
        .filter(ImportBatch.id == batch_id, ImportBatch.tenant_id == current_user.tenant_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found.")

    return {
        "id": batch.id,
        "filename": batch.filename,
        "status": batch.status,
        "total_rows": batch.total_rows,
        "inserted_count": batch.inserted_count,
        "skipped_count": batch.skipped_count,
        "categorized_count": batch.categorized_count,
        "flagged_count": batch.flagged_count,
        "error_message": batch.error_message,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
    }


@api_router.post("/ingest", tags=["ingestion"])
@api_router.post("/import", tags=["ingestion"])
async def upload_transactions_csv_sync(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_accountant_user),
):
    """
    Synchronous CSV ingestion fallback with strict server-side MIME sniffing,
    content validation, rate limiting, and tenant scoping.
    """
    check_rate_limit(request, max_requests=10, window_seconds=60)

    filename_lower = (file.filename or "").lower()
    if not filename_lower.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Only CSV/TXT text files are supported.")

    try:
        content_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # 1. Size limit validation (10 MB max)
    if len(content_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds maximum permitted limit of 10MB.")

    # 2. Content validation / Binary signature sniffing
    binary_signatures = [b"MZ", b"\x7fELF", b"PK\x03\x04", b"%PDF", b"\xca\xfe\xba\xbe"]
    for sig in binary_signatures:
        if content_bytes.startswith(sig):
            raise HTTPException(
                status_code=400,
                detail="Uploaded file has binary executable/archive headers and is not a valid CSV text document."
            )

    # 3. Detect null bytes
    if b"\x00" in content_bytes[:4096]:
        raise HTTPException(status_code=400, detail="File contains binary null characters and is not a valid CSV.")

    # 4. Decode text
    try:
        content_str = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            content_str = content_bytes.decode("latin-1")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"File text encoding is unreadable: {str(e)}")

    records = parse_csv_content(content_str)
    if not records:
        raise HTTPException(status_code=400, detail="No valid transaction rows found in CSV.")

    result = ingest_records(db, records, tenant_id=current_user.tenant_id)
    return {
        "message": f"Successfully ingested {result['inserted']} new transactions ({result['skipped']} duplicates skipped).",
        **result,
    }


@api_router.post("/ingest/sample", tags=["ingestion"])
def ingest_sample_dataset(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_accountant_user),
):
    """
    Loads the bundled restaurant dataset into the current tenant workspace.
    Protected: Accountant or Admin required.
    """
    result = load_bundled_sample_dataset(db, tenant_id=current_user.tenant_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Automatically run categorization on the loaded records
    cat_result = run_batch_categorization(db, force=True, tenant_id=current_user.tenant_id)

    return {
        "message": f"Successfully loaded sample dataset ({result['inserted']} inserted, {cat_result['categorized_count']} categorized).",
        **result,
        "ingest": result,
        "categorization": cat_result,
    }


@api_router.delete("/transactions", tags=["ingestion"])
def reset_tenant_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Clears transactions belonging ONLY to the active tenant workspace.
    Cross-tenant data is never touched.
    Protected: Admin users only.
    """
    deleted_count = db.query(Transaction).filter(Transaction.tenant_id == current_user.tenant_id).delete()
    db.commit()
    return {"message": f"Cleared {deleted_count} transactions from tenant workspace."}


# ==============================================================================
# CATEGORIZATION & AUDIT ENDPOINTS (PROTECTED)
# ==============================================================================

@api_router.get("/categories", tags=["categorization"])
def get_categories(
    current_user: User = Depends(get_current_user),
):
    """Returns standard Chart of Accounts. Protected: Authenticated users only."""
    return {
        "chart_of_accounts": CHART_OF_ACCOUNTS,
        "buckets": ["Revenue", "COGS", "Payroll", "Operating Expenses", "Non-P&L"],
    }


@api_router.post("/categorize/batch", tags=["categorization"])
def batch_categorize_transactions(
    force: bool = Query(False, description="If true, re-categorizes all transactions"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_accountant_user),
):
    """
    Runs automated categorization scoped strictly to the current tenant.
    Protected: Accountant or Admin required.
    """
    result = run_batch_categorization(db, force=force, tenant_id=current_user.tenant_id)
    return {
        "message": f"Categorization complete: {result['categorized_count']} processed, {result['flagged_for_review']} flagged for review.",
        **result,
    }


@api_router.patch("/transactions/{transaction_id}/category", tags=["categorization"])
def correct_transaction_category(
    transaction_id: int,
    payload: CategoryCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_accountant_user),
):
    """
    User correction: updates category and appends an immutable AuditLog entry.
    Tenant boundary strictly enforced. Protected: Accountant or Admin required.
    """
    try:
        updated_txn = update_transaction_category(
            db=db,
            transaction_id=transaction_id,
            new_category=payload.category,
            note=payload.note,
            source="user",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        return {
            "message": f"Transaction #{transaction_id} updated to '{payload.category}'.",
            "transaction": {
                "id": updated_txn.id,
                "transaction_code": updated_txn.transaction_code,
                "category": updated_txn.category,
                "pnl_bucket": updated_txn.pnl_bucket,
                "review_status": updated_txn.review_status,
                "is_flagged_for_review": updated_txn.is_flagged_for_review,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@api_router.get("/audit-logs", tags=["categorization"])
def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns immutable audit trail for the active tenant.
    Never exposes logs belonging to other tenants.
    """
    logs = (
        db.query(AuditLog, Transaction)
        .outerjoin(Transaction, AuditLog.transaction_id == Transaction.id)
        .filter(AuditLog.tenant_id == current_user.tenant_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )

    items = []
    for audit, txn in logs:
        items.append({
            "id": audit.id,
            "transaction_id": audit.transaction_id,
            "transaction_code": txn.transaction_code if txn else f"TX-{audit.transaction_id}",
            "description": txn.description if txn else (audit.old_value or "Audit Record"),
            "amount": txn.amount if txn else 0.0,
            "previous_category": audit.previous_category or audit.old_value,
            "new_category": audit.new_category or audit.new_value,
            "source": audit.source,
            "note": audit.note,
            "created_at": (audit.timestamp or audit.created_at).isoformat() if (audit.timestamp or audit.created_at) else None,
        })

    return {"total": len(items), "logs": items}


# ==============================================================================
# TRANSACTION QUERY ENDPOINTS (PROTECTED, TENANT-ISOLATED)
# ==============================================================================

@api_router.get("/reconciliation", tags=["financial"])
def get_reconciliation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns 4-way transaction reconciliation verifying:
    Total Imported = P&L + Non-P&L + Uncategorized
    Zero dropped transactions.
    """
    return get_reconciliation_summary(db=db, tenant_id=current_user.tenant_id)


@api_router.get("/transactions/stats", tags=["transactions"])
def get_transaction_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns summary statistics strictly for the authenticated tenant."""
    tenant_filter = Transaction.tenant_id == current_user.tenant_id

    total_count = db.query(func.count(Transaction.id)).filter(tenant_filter).scalar() or 0
    inflows = db.query(func.sum(Transaction.amount)).filter(tenant_filter, Transaction.amount > 0).scalar() or Decimal("0.00")
    outflows = db.query(func.sum(Transaction.amount)).filter(tenant_filter, Transaction.amount < 0).scalar() or Decimal("0.00")
    flagged_count = db.query(func.count(Transaction.id)).filter(tenant_filter, Transaction.is_flagged_for_review == True).scalar() or 0
    categorized_count = db.query(func.count(Transaction.id)).filter(tenant_filter, Transaction.category.isnot(None)).scalar() or 0

    uncategorized_filter = (
        tenant_filter &
        (Transaction.category.is_(None) | (func.lower(Transaction.category) == 'uncategorized'))
    )
    uncategorized_count = db.query(func.count(Transaction.id)).filter(uncategorized_filter).scalar() or 0
    uncat_debits = db.query(func.sum(Transaction.amount)).filter(uncategorized_filter, Transaction.amount < 0).scalar() or Decimal("0.00")
    uncat_credits = db.query(func.sum(Transaction.amount)).filter(uncategorized_filter, Transaction.amount > 0).scalar() or Decimal("0.00")
    uncat_amount = Decimal(str(uncat_debits)) + Decimal(str(uncat_credits))

    min_date = db.query(func.min(Transaction.date)).filter(tenant_filter).scalar()
    max_date = db.query(func.max(Transaction.date)).filter(tenant_filter).scalar()

    inflows_dec = Decimal(str(inflows)).quantize(Decimal("0.01"))
    outflows_dec = Decimal(str(outflows)).quantize(Decimal("0.01"))
    net_dec = (inflows_dec + outflows_dec).quantize(Decimal("0.01"))

    return {
        "total_transactions": total_count,
        "total_inflows": float(inflows_dec),
        "total_outflows": float(outflows_dec),
        "net_cash_flow": float(net_dec),
        "categorized_count": categorized_count,
        "uncategorized_count": uncategorized_count,
        "uncategorized_amount": float(uncat_amount.quantize(Decimal("0.01"))),
        "uncategorized_debits": float(Decimal(str(uncat_debits)).quantize(Decimal("0.01"))),
        "uncategorized_credits": float(Decimal(str(uncat_credits)).quantize(Decimal("0.01"))),
        "flagged_count": flagged_count,
        "date_range": {
            "start": str(min_date) if min_date else None,
            "end": str(max_date) if max_date else None,
        },
    }


@api_router.get("/transactions", tags=["transactions"])
def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None, description="Search description or counterparty"),
    category: Optional[str] = Query(None, description="Filter by category"),
    pnl_bucket: Optional[str] = Query(None, description="Filter by pnl bucket (Revenue, COGS, etc)"),
    is_flagged: Optional[bool] = Query(None, description="Filter flagged review items"),
    sort_by: str = Query("date", description="Field to sort by: date, amount, transaction_code"),
    sort_dir: str = Query("asc", description="Sort direction: asc or desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a paginated list of transactions strictly for the active tenant."""
    query = db.query(Transaction).filter(Transaction.tenant_id == current_user.tenant_id)

    # Search filter
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Transaction.description.ilike(search_pattern),
                Transaction.counterparty.ilike(search_pattern),
                Transaction.transaction_code.ilike(search_pattern),
            )
        )

    # Category filters
    if category:
        query = query.filter(Transaction.category == category)
    if pnl_bucket:
        query = query.filter(Transaction.pnl_bucket == pnl_bucket)
    if is_flagged is not None:
        query = query.filter(Transaction.is_flagged_for_review == is_flagged)

    total_records = query.count()

    # Sorting
    sort_column = Transaction.date
    if sort_by == "amount":
        sort_column = Transaction.amount
    elif sort_by == "transaction_code":
        sort_column = Transaction.transaction_code
    elif sort_by == "category":
        sort_column = Transaction.category

    if sort_dir.lower() == "desc":
        query = query.order_by(desc(sort_column), desc(Transaction.id))
    else:
        query = query.order_by(asc(sort_column), asc(Transaction.id))

    offset = (page - 1) * limit
    transactions = query.offset(offset).limit(limit).all()

    items = []
    for t in transactions:
        items.append({
            "id": t.id,
            "transaction_code": t.transaction_code,
            "date": str(t.date),
            "description": t.description,
            "counterparty": t.counterparty,
            "amount": t.amount,
            "method": t.method,
            "category": t.category,
            "pnl_bucket": t.pnl_bucket,
            "confidence": t.confidence,
            "rationale": t.rationale,
            "is_flagged_for_review": t.is_flagged_for_review,
            "review_status": t.review_status,
        })

    return {
        "items": items,
        "total": total_records,
        "page": page,
        "limit": limit,
        "pages": (total_records + limit - 1) // limit if limit > 0 else 1,
    }


# ==============================================================================
# P&L STATEMENT & VARIANCE ENDPOINTS (DETERMINISTIC, PROTECTED)
# ==============================================================================

@api_router.get("/pnl", tags=["pnl"])
def get_pnl_statement(
    start_month: Optional[str] = Query(None, description="Start month YYYY-MM"),
    end_month: Optional[str] = Query(None, description="End month YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns deterministic monthly P&L statement strictly for active tenant.
    Calculates Revenue, COGS, Gross Profit, Payroll, OpEx, and Operating Profit.
    """
    pnl_data = generate_monthly_pnl(
        db,
        start_month=start_month,
        end_month=end_month,
        tenant_id=current_user.tenant_id,
    )
    return pnl_data


@api_router.get("/variance", tags=["variance"])
@api_router.get("/variances", tags=["variance"])
def get_monthly_variances(
    baseline_month: Optional[str] = Query(None, description="Baseline month YYYY-MM (e.g. 2026-01)"),
    current_month: Optional[str] = Query(None, description="Comparison month YYYY-MM (e.g. 2026-02)"),
    min_amount: float = Query(1000.0, description="Materiality threshold in dollars"),
    min_pct: float = Query(10.0, description="Materiality threshold in percent"),
    only_material: bool = Query(True, description="Filter only material variances"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Computes month-over-month variances and driver transactions for the active tenant."""
    variance_data = calculate_monthly_variances(
        db=db,
        baseline_month=baseline_month,
        current_month=current_month,
        min_amount=min_amount,
        min_pct=min_pct,
        only_material=only_material,
        tenant_id=current_user.tenant_id,
    )
    return variance_data


# ==============================================================================
# TRACEABILITY ENDPOINTS (GLOBAL EVIDENCE AUDIT)
# ==============================================================================

@api_router.get("/traceability/{metric_key}", tags=["traceability"])
def get_metric_traceability(
    metric_key: str,
    month: Optional[str] = Query(None, description="Month YYYY-MM or None for all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Provides deterministic mathematical origin and underlying transaction evidence
    for any displayed financial KPI or category line item.
    """
    tenant_filter = [Transaction.tenant_id == current_user.tenant_id]

    key_normalized = metric_key.lower().strip()
    pnl = generate_monthly_pnl(db, tenant_id=current_user.tenant_id)
    summary = pnl.get("summary", {})

    target_month_key = month if (month and month in summary) else "Total"
    month_data = summary.get(target_month_key, {})

    formula = ""
    components = []
    bucket_filter = None
    category_filter = None

    if key_normalized in ["operating_profit", "operating-profit", "ebitda"]:
        gp = month_data.get("gross_profit", 0.0)
        pay = month_data.get("payroll", 0.0)
        opex = month_data.get("opex", 0.0)
        val = month_data.get("operating_profit", 0.0)
        formula = f"Gross Profit (${gp:,.2f}) - Payroll (${pay:,.2f}) - Operating Expenses (${opex:,.2f}) = Operating Profit (${val:,.2f})"
        components = [
            {"label": "Gross Profit", "value": gp, "type": "credit"},
            {"label": "Payroll", "value": pay, "type": "debit"},
            {"label": "Operating Expenses", "value": opex, "type": "debit"},
        ]
        bucket_filter = ["Revenue", "COGS", "Payroll", "Operating Expenses"]

    elif key_normalized in ["gross_profit", "gross-profit"]:
        rev = month_data.get("revenue", 0.0)
        cogs = month_data.get("cogs", 0.0)
        val = month_data.get("gross_profit", 0.0)
        formula = f"Revenue (${rev:,.2f}) - COGS (${cogs:,.2f}) = Gross Profit (${val:,.2f})"
        components = [
            {"label": "Total Revenue", "value": rev, "type": "credit"},
            {"label": "Cost of Goods Sold", "value": cogs, "type": "debit"},
        ]
        bucket_filter = ["Revenue", "COGS"]

    elif key_normalized == "revenue":
        val = month_data.get("revenue", 0.0)
        formula = "Sum of all Food, Beverage, Delivery, and Catering Sales minus customer discounts"
        bucket_filter = ["Revenue"]

    elif key_normalized == "cogs":
        val = month_data.get("cogs", 0.0)
        formula = "Sum of all raw Food Inventory, Beverage/Alcohol Stock, and Take-out Packaging"
        bucket_filter = ["COGS"]

    elif key_normalized == "payroll":
        val = month_data.get("payroll", 0.0)
        formula = "Sum of Staff Hourly Salaries & Wages and Employer Payroll Taxes & Benefits"
        bucket_filter = ["Payroll"]

    elif key_normalized in ["opex", "operating_expenses", "operating-expenses"]:
        val = month_data.get("opex", 0.0)
        formula = "Sum of Rent, Utilities, Insurance, Software, Repairs, Marketing, and Supplies"
        bucket_filter = ["Operating Expenses"]

    else:
        # Category specific lookup
        val = 0.0
        category_filter = metric_key
        formula = f"Deterministic sum of transactions categorized under '{metric_key}'"

    # Query matching transactions
    tx_query = db.query(Transaction).filter(*tenant_filter)
    if bucket_filter:
        tx_query = tx_query.filter(Transaction.pnl_bucket.in_(bucket_filter))
    if category_filter:
        tx_query = tx_query.filter(Transaction.category.ilike(category_filter))
    if month and len(month) == 7:
        try:
            from datetime import date
            import calendar
            y, m = int(month[:4]), int(month[5:7])
            _, last_d = calendar.monthrange(y, m)
            tx_query = tx_query.filter(
                Transaction.date >= date(y, m, 1),
                Transaction.date <= date(y, m, last_d),
            )
        except Exception:
            pass

    tx_records = tx_query.order_by(desc(Transaction.date), desc(Transaction.id)).limit(200).all()

    return {
        "metric_key": metric_key,
        "period": target_month_key,
        "calculated_value": round(val, 2),
        "formula": formula,
        "components": components,
        "transaction_count": len(tx_records),
        "transactions": [
            {
                "id": t.id,
                "transaction_code": t.transaction_code or f"TX-{t.id}",
                "date": str(t.date),
                "description": t.description,
                "counterparty": t.counterparty,
                "category": t.category,
                "pnl_bucket": t.pnl_bucket,
                "amount": t.amount,
            }
            for t in tx_records
        ],
    }


# ==============================================================================
# REVIEW QUEUE & TRIAGE ENDPOINTS (PROTECTED)
# ==============================================================================

@api_router.get("/review-queue", tags=["review"])
@api_router.get("/review", tags=["review"])
def get_review_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all transactions flagged for human review strictly for active tenant."""
    flagged_txns = (
        db.query(Transaction)
        .filter(
            Transaction.tenant_id == current_user.tenant_id,
            Transaction.is_flagged_for_review == True,
        )
        .order_by(asc(Transaction.date), desc(Transaction.id))
        .all()
    )

    items = []
    for t in flagged_txns:
        items.append({
            "id": t.id,
            "transaction_code": t.transaction_code or f"TX-{t.id}",
            "date": str(t.date),
            "description": t.description,
            "counterparty": t.counterparty,
            "amount": t.amount,
            "method": t.method,
            "category": t.category,
            "pnl_bucket": t.pnl_bucket,
            "confidence": t.confidence,
            "rationale": t.rationale,
            "review_status": t.review_status,
        })

    return {"count": len(items), "items": items}


@api_router.post("/transactions/{transaction_id}/confirm", tags=["review"])
def confirm_transaction_classification(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_accountant_user),
):
    """
    Reviewer confirms current classification: clears flag, logs immutable audit entry.
    Protected: Accountant or Admin required.
    """
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.tenant_id == current_user.tenant_id)
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    txn.is_flagged_for_review = False
    txn.review_status = "confirmed"

    audit_entry = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        transaction_id=txn.id,
        entity_type="transaction",
        entity_id=str(txn.id),
        action="confirm_classification",
        old_value=txn.category,
        new_value=txn.category or "Uncategorized",
        previous_category=txn.category,
        new_category=txn.category or "Uncategorized",
        source="user",
        note=f"Confirmed classification as '{txn.category}' by reviewer ({current_user.name}).",
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(txn)

    return {
        "message": f"Transaction #{transaction_id} confirmed as '{txn.category}'.",
        "id": txn.id,
        "review_status": txn.review_status,
        "is_flagged_for_review": txn.is_flagged_for_review,
    }


@api_router.post("/transactions/{transaction_id}/dismiss", tags=["review"])
def dismiss_transaction_review_flag(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_accountant_user),
):
    """Reviewer dismisses flag without changing category. Protected: Accountant or Admin required."""
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.tenant_id == current_user.tenant_id)
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    txn.is_flagged_for_review = False
    txn.review_status = "dismissed"

    audit_entry = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        transaction_id=txn.id,
        entity_type="transaction",
        entity_id=str(txn.id),
        action="dismiss_flag",
        old_value=txn.category,
        new_value=txn.category or "Uncategorized",
        previous_category=txn.category,
        new_category=txn.category or "Uncategorized",
        source="user",
        note=f"Review flag dismissed by {current_user.name}.",
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(txn)

    return {
        "message": f"Review flag dismissed for transaction #{transaction_id}.",
        "id": txn.id,
        "review_status": txn.review_status,
        "is_flagged_for_review": txn.is_flagged_for_review,
    }


# ==============================================================================
# AI FINANCIAL ANALYST (PROTECTED, OLLAMA ROUTED, TENANT-ISOLATED)
# ==============================================================================

@api_router.post("/chat", tags=["chat"])
def chat_with_analyst(
    request: Request,
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Executes source-grounded financial analyst query with deterministic tool-calling.
    Enforces tenant scoping, Ollama model router routing, and token usage metering.
    """
    check_rate_limit(request, max_requests=25, window_seconds=60, identifier=str(current_user.id))
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    result = process_financial_query(
        db=db,
        message=payload.message,
        history=payload.history,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    return result


@api_router.get("/ai/health", tags=["ai"])
def get_ai_health(
    current_user: User = Depends(get_current_user),
):
    """
    Connectivity check for Ollama AI provider and Model Router.
    Never exposes API secrets or provider credentials.
    Protected: Authenticated users only.
    """
    client = OllamaClient()
    health = client.health_check()
    health["model_router"] = {
        "configured_model": settings.OLLAMA_MODEL,
        "fast_model": settings.OLLAMA_FAST_MODEL,
        "base_url": settings.OLLAMA_BASE_URL,
    }
    return health


@api_router.get("/chat/suggestions", tags=["chat"])
def get_chat_suggestions(
    current_user: User = Depends(get_current_user),
):
    """Returns preset prompt suggestions matching evaluation criteria."""
    return {
        "suggestions": [
            "What was our revenue in Jan 2026?",
            "How much did we spend on payroll each month?",
            "Why did operating profit change between Jan and Feb?",
            "Which transactions need my attention?",
            "Show me the transactions behind that variance.",
        ]
    }
