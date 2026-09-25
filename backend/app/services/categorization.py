from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.transaction import Transaction, AuditLog


# Standard Chart of Accounts (COA) mapped to P&L Buckets
CHART_OF_ACCOUNTS = [
    # 1. Revenue
    {"category": "Food Sales", "pnl_bucket": "Revenue", "description": "Gross sales from in-house food orders"},
    {"category": "Beverage Sales", "pnl_bucket": "Revenue", "description": "Gross sales from bar, beer, and non-alcoholic drinks"},
    {"category": "Catering Revenue", "pnl_bucket": "Revenue", "description": "Direct corporate and private catering orders"},
    {"category": "Delivery Revenue", "pnl_bucket": "Revenue", "description": "Gross marketplace payouts (DoorDash, Uber Eats)"},
    {"category": "Discounts & Refunds", "pnl_bucket": "Revenue", "description": "Customer refunds, comps, and promotional adjustments"},

    # 2. Cost of Goods Sold (COGS)
    {"category": "Food Inventory / Supplies", "pnl_bucket": "COGS", "description": "Raw ingredients, meat, produce, bakery"},
    {"category": "Beverage Inventory / Alcohol", "pnl_bucket": "COGS", "description": "Liquor, wine, craft beer, and beverage stock"},
    {"category": "Packaging & Disposables", "pnl_bucket": "COGS", "description": "Take-out packaging, napkins, to-go bags"},

    # 3. Payroll
    {"category": "Salaries & Wages", "pnl_bucket": "Payroll", "description": "Hourly BOH kitchen and FOH floor staff wages"},
    {"category": "Payroll Taxes & Benefits", "pnl_bucket": "Payroll", "description": "Employer payroll taxes, health benefits, workers comp"},

    # 4. Operating Expenses (OpEx)
    {"category": "Rent & Occupancy", "pnl_bucket": "Operating Expenses", "description": "Monthly facility lease and property charges"},
    {"category": "Utilities (Electric, Gas, Water)", "pnl_bucket": "Operating Expenses", "description": "Power, municipal water, and commercial gas"},
    {"category": "Insurance Premium", "pnl_bucket": "Operating Expenses", "description": "General liability, property, and casualty insurance"},
    {"category": "Software & POS Subscriptions", "pnl_bucket": "Operating Expenses", "description": "Toast POS, reservations, scheduling software"},
    {"category": "Professional Services", "pnl_bucket": "Operating Expenses", "description": "External bookkeeping, CPA, and legal retainers"},
    {"category": "Delivery Platform Commissions", "pnl_bucket": "Operating Expenses", "description": "Take-rates deducted by third-party delivery services"},
    {"category": "Marketing & Advertising", "pnl_bucket": "Operating Expenses", "description": "Paid social, Yelp/Google ads, local promotions"},
    {"category": "Repairs & Maintenance", "pnl_bucket": "Operating Expenses", "description": "Kitchen equipment repairs, HVAC servicing"},
    {"category": "Linen & Laundry Services", "pnl_bucket": "Operating Expenses", "description": "Chef coats, aprons, bar towels, and tablecloths"},
    {"category": "Operating Supplies & Office", "pnl_bucket": "Operating Expenses", "description": "Cleaning chemicals, POS paper, office essentials"},
    {"category": "Telephone & Internet", "pnl_bucket": "Operating Expenses", "description": "Commercial broadband and business phone lines"},

    # 5. Non-P&L / Balance Sheet Items (Critical Accounting Distinction)
    {"category": "Capital Expenditure - Equipment Asset", "pnl_bucket": "Non-P&L", "description": "Long-term capitalized assets (e.g. commercial ovens, walk-in coolers)"},
    {"category": "Sales Tax Remittance", "pnl_bucket": "Non-P&L", "description": "Pass-through sales tax collected and remitted to Dept of Revenue"},
    {"category": "Financing & Owner Equity", "pnl_bucket": "Non-P&L", "description": "Debt service principal, owner distributions or injections"},
]

# Quick lookup by category name
CATEGORY_LOOKUP = {c["category"]: c for c in CHART_OF_ACCOUNTS}


def classify_transaction_rule_based(
    description: str,
    counterparty: Optional[str] = None,
    amount: float = 0.0,
    method: Optional[str] = None,
) -> Tuple[str, str, float, str, bool]:
    """
    Evaluates accounting rules against transaction attributes.
    Returns:
      (category, pnl_bucket, confidence, rationale, is_flagged_for_review)
    """
    text = f"{description or ''} {counterparty or ''}".lower()

    # 1. Non-P&L Items (High Priority Check to prevent P&L distortion)
    if any(k in text for k in ["equipment purchase", "new oven", "restaurant equipment world", "walk-in cooler", "capex"]):
        return (
            "Capital Expenditure - Equipment Asset",
            "Non-P&L",
            0.92,
            "Major physical asset purchase (oven/equipment); capitalized to balance sheet, not expensed on P&L.",
            True,  # Flag for review to ensure depreciation scheduling
        )

    if any(k in text for k in ["dept. of revenue", "sales tax remittance", "department of revenue"]):
        return (
            "Sales Tax Remittance",
            "Non-P&L",
            0.94,
            "Sales tax payment remitted to state authority; balance sheet liability reduction, not an operating expense.",
            True,
        )

    # 2. Revenue Items (Typically positive inflows)
    if "food sales" in text or ("pos batch" in text and "food" in text):
        return (
            "Food Sales",
            "Revenue",
            0.98,
            "Daily/weekly batch deposit from POS representing food sales revenue.",
            False,
        )

    if "beverage sales" in text or ("pos batch" in text and "beverage" in text):
        return (
            "Beverage Sales",
            "Revenue",
            0.98,
            "POS batch deposit attributable to bar and drink sales.",
            False,
        )

    if "catering" in text:
        return (
            "Catering Revenue",
            "Revenue",
            0.96,
            "Direct corporate/private event catering client payment.",
            False,
        )

    if "delivery marketplace payout" in text or (any(d in text for d in ["doordash", "uber eats"]) and "payout" in text):
        return (
            "Delivery Revenue",
            "Revenue",
            0.95,
            "Net marketplace settlement disbursement from third-party delivery channels.",
            False,
        )

    if "refund" in text or "comp" in text or "discount" in text:
        return (
            "Discounts & Refunds",
            "Revenue",
            0.93,
            "POS contra-revenue adjustment for customer refunds or promotional discounts.",
            False,
        )

    # 3. COGS Items (Food, Beverage, Packaging)
    if any(k in text for k in ["sysco", "us foods", "local produce", "butcher & sons", "bakery supply"]) or "food inventory" in text:
        return (
            "Food Inventory / Supplies",
            "COGS",
            0.96,
            "Wholesale ingredient/meat/produce procurement directly linked to food production.",
            False,
        )

    if any(k in text for k in ["southern glazer", "craft beer", "beverage depot"]) or "beverage inventory" in text:
        return (
            "Beverage Inventory / Alcohol",
            "COGS",
            0.96,
            "Wholesale beer, wine, and liquor distributor invoices.",
            False,
        )

    if any(k in text for k in ["packaging", "disposables", "restaurant depot"]) and "oven" not in text:
        return (
            "Packaging & Disposables",
            "COGS",
            0.94,
            "Takeaway containers, cups, cutlery, and food presentation disposables.",
            False,
        )

    # 4. Payroll
    if any(k in text for k in ["gusto", "wage", "payroll", "hourly wages", "foh", "boh"]):
        return (
            "Salaries & Wages",
            "Payroll",
            0.98,
            "Bi-weekly hourly/salaried wage disbursement processed via Gusto.",
            False,
        )

    # 5. Operating Expenses
    if "rent" in text or "landlord" in text:
        return (
            "Rent & Occupancy",
            "Operating Expenses",
            0.99,
            "Commercial lease obligation paid to property landlord.",
            False,
        )

    if any(k in text for k in ["city utilities", "electric", "gas", "water"]):
        return (
            "Utilities (Electric, Gas, Water)",
            "Operating Expenses",
            0.97,
            "Monthly utility billing for restaurant kitchen power, heating, and water.",
            False,
        )

    if any(k in text for k in ["next insurance", "insurance premium", "commercial insurance"]):
        return (
            "Insurance Premium",
            "Operating Expenses",
            0.97,
            "Business property and general liability insurance policy coverage.",
            False,
        )

    if "toast" in text and ("software" in text or "subscription" in text or "pos" in text):
        return (
            "Software & POS Subscriptions",
            "Operating Expenses",
            0.96,
            "Monthly cloud software fee for Toast POS terminals and kitchen display system.",
            False,
        )

    if any(k in text for k in ["ledgerpro", "bookkeeping", "accounting", "cpa", "legal"]):
        return (
            "Professional Services",
            "Operating Expenses",
            0.97,
            "Monthly bookkeeping and financial statement preparation fee.",
            False,
        )

    if "delivery" in text and ("commission" in text or "marketplace deduction" in text):
        return (
            "Delivery Platform Commissions",
            "Operating Expenses",
            0.95,
            "Platform take-rate fee charged by DoorDash/Uber Eats for marketplace facilitation.",
            False,
        )

    if any(k in text for k in ["linenpro", "linen", "laundry"]):
        return (
            "Linen & Laundry Services",
            "Operating Expenses",
            0.95,
            "Weekly linen rental and commercial laundry sanitation service.",
            False,
        )

    if any(k in text for k in ["meta", "google", "yelp", "advertising", "marketing"]):
        return (
            "Marketing & Advertising",
            "Operating Expenses",
            0.95,
            "Digital customer acquisition and local search advertising campaigns.",
            False,
        )

    if any(k in text for k in ["kitchen repair", "repair", "maintenance", "hvac"]):
        return (
            "Repairs & Maintenance",
            "Operating Expenses",
            0.94,
            "Equipment servicing and preventative maintenance in commercial kitchen.",
            False,
        )

    if any(k in text for k in ["staples", "amazon", "office supply"]):
        return (
            "Operating Supplies & Office",
            "Operating Expenses",
            0.92,
            "General office consumables, receipt paper, and cleaning supplies.",
            False,
        )

    if any(k in text for k in ["comcast", "internet", "phone"]):
        return (
            "Telephone & Internet",
            "Operating Expenses",
            0.96,
            "Broadband connectivity for guest Wi-Fi and POS cloud sync.",
            False,
        )

    # Fallback for unclassified transactions: marked as uncertain with low confidence
    return (
        "Operating Supplies & Office",
        "Operating Expenses",
        0.65,
        "General operating transaction; requires human verification due to ambiguous payee information.",
        True,
    )


def categorize_single_transaction(txn: Transaction) -> Tuple[str, str, float, str, bool]:
    """Classifies a transaction and returns categorized fields."""
    return classify_transaction_rule_based(
        description=txn.description,
        counterparty=txn.counterparty,
        amount=txn.amount,
        method=txn.method,
    )


def run_batch_categorization(
    db: Session,
    tenant_id: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Categorizes transactions currently stored in the database.
    Scoped to tenant_id if provided. Checks tenant-specific ChartOfAccountsMapping first.
    """
    from app.models.chart_mapping import ChartOfAccountsMapping

    # Load custom tenant mappings if tenant_id is provided
    custom_mappings = {}
    if tenant_id:
        tenant_maps = db.query(ChartOfAccountsMapping).filter(ChartOfAccountsMapping.tenant_id == tenant_id).all()
        for tm in tenant_maps:
            custom_mappings[tm.raw_category.lower().strip()] = (tm.standard_category, tm.pnl_bucket)

    query = db.query(Transaction)
    if tenant_id is not None:
        query = query.filter(Transaction.tenant_id == tenant_id)
    if not force:
        query = query.filter(Transaction.category.isnot(None) == False)

    txns = query.all()
    count = 0
    flagged = 0

    for t in txns:
        # Check custom tenant override first
        desc_key = (t.description or "").lower().strip()
        counterparty_key = (t.counterparty or "").lower().strip()
        if desc_key in custom_mappings:
            category, pnl_bucket = custom_mappings[desc_key]
            confidence, rationale, is_flagged = 1.0, "Tenant custom Chart of Accounts rule matched.", False
        elif counterparty_key in custom_mappings:
            category, pnl_bucket = custom_mappings[counterparty_key]
            confidence, rationale, is_flagged = 1.0, "Tenant custom Chart of Accounts rule matched.", False
        else:
            category, pnl_bucket, confidence, rationale, is_flagged = categorize_single_transaction(t)

        t.category = category
        t.pnl_bucket = pnl_bucket
        t.confidence = confidence
        t.rationale = rationale
        t.is_flagged_for_review = is_flagged or (confidence < 0.85)
        t.review_status = "flagged" if t.is_flagged_for_review else "pending"
        count += 1
        if t.is_flagged_for_review:
            flagged += 1

    db.commit()

    return {
        "categorized_count": count,
        "flagged_for_review": flagged,
    }


def update_transaction_category(
    db: Session,
    transaction_id: int,
    new_category: str,
    note: Optional[str] = None,
    source: str = "user",
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> Transaction:
    """
    Applies user or model correction to a transaction and writes an immutable AuditLog entry.
    Asserts tenant boundary if tenant_id is provided.
    """
    query = db.query(Transaction).filter(Transaction.id == transaction_id)
    if tenant_id is not None:
        query = query.filter(Transaction.tenant_id == tenant_id)
    txn = query.first()

    if not txn:
        raise ValueError(f"Transaction with ID {transaction_id} not found.")

    prev_category = txn.category

    # Determine P&L bucket from lookup
    coa_entry = CATEGORY_LOOKUP.get(new_category)
    new_bucket = coa_entry["pnl_bucket"] if coa_entry else "Operating Expenses"

    # Update transaction
    txn.category = new_category
    txn.pnl_bucket = new_bucket
    txn.review_status = "corrected" if source == "user" else "confirmed"
    txn.is_flagged_for_review = False  # resolved by human reviewer

    # Create immutable audit log with tenant, user, old/new category tracking
    audit_entry = AuditLog(
        tenant_id=txn.tenant_id,
        user_id=user_id,
        transaction_id=txn.id,
        entity_type="transaction",
        entity_id=str(txn.id),
        action="category_override",
        old_value=prev_category,
        new_value=new_category,
        previous_category=prev_category,
        new_category=new_category,
        source=source,
        note=note or ("Manual category override by reviewer" if source == "user" else None),
    )
    db.add(audit_entry)
    db.commit()

    return txn
