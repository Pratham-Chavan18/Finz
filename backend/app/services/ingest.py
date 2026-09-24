import csv
import io
import os
import re
from datetime import datetime, date
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.transaction import Transaction


def parse_currency(val: Any) -> float:
    """
    Cleans and parses a currency string into a float.
    Handles:
      -$4,151.25 -> -4151.25
      "$17,513.84" -> 17513.84
      -$875.00 -> -875.00
      $750.84 -> 750.84
      ($1,250.00) -> -1250.00
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return 0.0

    # Check for accounting parentheses e.g. ($1,250.00)
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    # Check for negative sign before or after dollar sign
    if s.startswith("-"):
        is_negative = True
        s = s[1:].strip()

    # Remove currency symbol, quotes, commas, and whitespace
    s = s.replace("$", "").replace(",", "").replace('"', "").replace("'", "").strip()

    if s.startswith("-"):
        is_negative = True
        s = s[1:].strip()

    try:
        num = float(s)
        return -num if is_negative else num
    except ValueError:
        return 0.0


def parse_date_value(val: Any) -> date:
    """Parses various date string formats into a date object."""
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()

    s = str(val).strip()
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    # Fallback to today if unparseable
    return date.today()


def parse_csv_content(content_str: str) -> List[Dict[str, Any]]:
    """
    Parses raw CSV content into normalized transaction dictionaries.
    """
    reader = csv.DictReader(io.StringIO(content_str))
    records = []

    for row in reader:
        # Standardize keys by stripping and lowercasing
        clean_row = {k.strip().lower(): v for k, v in row.items() if k is not None}

        # Extract fields with multiple possible column names
        code = clean_row.get("transaction id") or clean_row.get("transaction_id") or clean_row.get("id") or clean_row.get("code")
        dt_raw = clean_row.get("date") or clean_row.get("transaction date") or clean_row.get("timestamp")
        desc = clean_row.get("description") or clean_row.get("memo") or clean_row.get("details") or ""
        counterparty = clean_row.get("counterparty") or clean_row.get("payee") or clean_row.get("vendor") or clean_row.get("customer") or ""
        amt_raw = clean_row.get("amount") or clean_row.get("total") or clean_row.get("net")
        method = clean_row.get("method") or clean_row.get("payment method") or clean_row.get("type") or ""

        if not desc and not code and amt_raw is None:
            continue  # empty row

        parsed_amount = parse_currency(amt_raw)
        parsed_date = parse_date_value(dt_raw) if dt_raw else date.today()

        records.append({
            "transaction_code": code.strip() if code else None,
            "date": parsed_date,
            "description": desc.strip(),
            "counterparty": counterparty.strip() if counterparty else None,
            "raw_payee": counterparty.strip() if counterparty else None,
            "amount": parsed_amount,
            "method": method.strip() if method else None,
        })

    return records


def ingest_records(
    db: Session,
    records: List[Dict[str, Any]],
    tenant_id: Optional[int] = None,
    batch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Ingests parsed records into the database with tenant-scoped duplicate prevention.
    """
    if not records:
        return {"total": 0, "inserted": 0, "skipped": 0, "errors": []}

    # Fetch existing transaction codes for this tenant to avoid duplicate insertion
    code_query = db.query(Transaction.transaction_code).filter(Transaction.transaction_code.isnot(None))
    if tenant_id is not None:
        code_query = code_query.filter(Transaction.tenant_id == tenant_id)
    existing_codes = {c for (c,) in code_query.all()}

    inserted = 0
    skipped = 0
    errors = []

    for r in records:
        code = r.get("transaction_code")
        if code and code in existing_codes:
            skipped += 1
            continue

        try:
            txn = Transaction(
                tenant_id=tenant_id,
                import_batch_id=batch_id,
                transaction_code=code,
                date=r["date"],
                description=r["description"],
                counterparty=r.get("counterparty"),
                raw_payee=r.get("raw_payee"),
                amount=r["amount"],
                method=r.get("method"),
                account_name="Primary Checking",
                review_status="pending",
            )
            db.add(txn)
            if code:
                existing_codes.add(code)
            inserted += 1
        except Exception as e:
            errors.append(f"Row {code or r.get('description')}: {str(e)}")

    db.commit()

    return {
        "total": len(records),
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
    }


def load_bundled_sample_dataset(db: Session, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Locates and ingests the bundled NYC Restaurant Co. challenge dataset, scoped to tenant_id if provided.
    """
    possible_paths = [
        "docs/NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv",
        "../docs/NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv",
        "../../docs/NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv",
        "d:/Project/Finz/docs/NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv",
        "NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv",
        "../NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv",
        "../../NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv",
        "d:/Project/Finz/NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv",
    ]

    target_path = None
    for p in possible_paths:
        if os.path.exists(p):
            target_path = p
            break

    if not target_path:
        return {
            "error": "Sample dataset file not found",
            "inserted": 0,
            "total": 0,
        }

    with open(target_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    records = parse_csv_content(content)
    return ingest_records(db, records, tenant_id=tenant_id)
