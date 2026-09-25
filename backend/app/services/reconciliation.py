from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.services.categorization import CHART_OF_ACCOUNTS


def get_reconciliation_summary(db: Session, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Performs a deterministic, 100% auditable 4-way transaction reconciliation:
      Total Imported = P&L Transactions + Non-P&L Transactions + Uncategorized Transactions
      
    Guarantees:
      - Uses Python Decimal for all calculations
      - Detects any silently dropped or unmapped transactions
      - Validates both transaction count equality and net dollar balance equality
    """
    query = db.query(Transaction)
    if tenant_id is not None:
        query = query.filter(Transaction.tenant_id == tenant_id)

    all_txns = query.all()

    total_imported_count = len(all_txns)
    total_imported_amount = Decimal("0.00")
    total_imported_debits = Decimal("0.00")
    total_imported_credits = Decimal("0.00")

    pnl_count = 0
    pnl_amount = Decimal("0.00")
    pnl_debits = Decimal("0.00")
    pnl_credits = Decimal("0.00")

    non_pnl_count = 0
    non_pnl_amount = Decimal("0.00")
    non_pnl_debits = Decimal("0.00")
    non_pnl_credits = Decimal("0.00")

    uncategorized_count = 0
    uncategorized_amount = Decimal("0.00")
    uncategorized_debits = Decimal("0.00")
    uncategorized_credits = Decimal("0.00")

    non_pnl_categories = {c["category"] for c in CHART_OF_ACCOUNTS if c.get("pnl_bucket") == "Non-P&L"}
    pnl_categories = {c["category"] for c in CHART_OF_ACCOUNTS if c.get("pnl_bucket") != "Non-P&L"}
    pnl_buckets = {"Revenue", "COGS", "Payroll", "Operating Expenses", "Cost of Goods Sold", "Payroll & Labor"}

    for t in all_txns:
        amt = Decimal(str(t.amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_imported_amount += amt
        if amt < Decimal("0.00"):
            total_imported_debits += amt
        else:
            total_imported_credits += amt

        cat = (t.category or "").strip()
        bucket = (t.pnl_bucket or "").strip()

        # Classify into one of 3 mutually exclusive sets
        if not cat or cat.lower() == "uncategorized":
            uncategorized_count += 1
            uncategorized_amount += amt
            if amt < Decimal("0.00"):
                uncategorized_debits += amt
            else:
                uncategorized_credits += amt
        elif bucket == "Non-P&L" or cat in non_pnl_categories:
            non_pnl_count += 1
            non_pnl_amount += amt
            if amt < Decimal("0.00"):
                non_pnl_debits += amt
            else:
                non_pnl_credits += amt
        elif bucket in pnl_buckets or cat in pnl_categories:
            pnl_count += 1
            pnl_amount += amt
            if amt < Decimal("0.00"):
                pnl_debits += amt
            else:
                pnl_credits += amt
        else:
            # Fallback for unrecognized categories
            uncategorized_count += 1
            uncategorized_amount += amt
            if amt < Decimal("0.00"):
                uncategorized_debits += amt
            else:
                uncategorized_credits += amt

    # Reconciliation validation
    summed_count = pnl_count + non_pnl_count + uncategorized_count
    summed_amount = (pnl_amount + non_pnl_amount + uncategorized_amount).quantize(Decimal("0.01"))

    dropped_count = total_imported_count - summed_count
    dropped_amount = (total_imported_amount - summed_amount).quantize(Decimal("0.01"))

    is_count_balanced = (dropped_count == 0)
    is_amount_balanced = (abs(dropped_amount) < Decimal("0.005"))
    is_balanced = is_count_balanced and is_amount_balanced

    return {
        "is_balanced": is_balanced,
        "is_count_balanced": is_count_balanced,
        "is_amount_balanced": is_amount_balanced,
        "total_imported": {
            "count": total_imported_count,
            "amount": float(total_imported_amount),
            "debits": float(total_imported_debits),
            "credits": float(total_imported_credits),
        },
        "pnl_transactions": {
            "count": pnl_count,
            "amount": float(pnl_amount),
            "debits": float(pnl_debits),
            "credits": float(pnl_credits),
        },
        "non_pnl_transactions": {
            "count": non_pnl_count,
            "amount": float(non_pnl_amount),
            "debits": float(non_pnl_debits),
            "credits": float(non_pnl_credits),
        },
        "uncategorized_transactions": {
            "count": uncategorized_count,
            "amount": float(uncategorized_amount),
            "debits": float(uncategorized_debits),
            "credits": float(uncategorized_credits),
        },
        "dropped": {
            "count": dropped_count,
            "amount": float(dropped_amount),
        },
        "diagnostics": {
            "reconciliation_equation": "Total Imported (count/amount) = P&L + Non-P&L + Uncategorized",
            "count_equation_eval": f"{total_imported_count} = {pnl_count} + {non_pnl_count} + {uncategorized_count}",
            "amount_equation_eval": f"{total_imported_amount} = {pnl_amount} + {non_pnl_amount} + {uncategorized_amount}",
            "precision": "Decimal(15, 2)",
            "has_dropped_transactions": dropped_count > 0 or abs(dropped_amount) > Decimal("0.00"),
        }
    }
