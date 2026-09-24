import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.import_batch import ImportBatch
from app.models.transaction import Transaction, AuditLog
from app.services.ingest import parse_csv_content, ingest_records
from app.services.categorization import run_batch_categorization

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.process_csv_import_batch")
def process_csv_import_batch(batch_id: int, csv_content: str, tenant_id: int, user_id: int):
    """
    Celery background worker processing raw CSV data:
    1. PENDING -> VALIDATING
    2. VALIDATING -> PROCESSING (parsing & db inserts)
    3. PROCESSING -> CATEGORIZING (rule & AI batch classification)
    4. CATEGORIZING -> COMPLETED
    """
    db: Session = SessionLocal()
    try:
        batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        if not batch:
            logger.error(f"ImportBatch {batch_id} not found.")
            return

        # 1. VALIDATING
        batch.status = "VALIDATING"
        db.commit()

        records, parse_errors = parse_csv_content(csv_content)
        if parse_errors and len(records) == 0:
            batch.status = "FAILED"
            batch.error_message = "; ".join(parse_errors[:5])
            db.commit()
            return

        # 2. PROCESSING
        batch.status = "PROCESSING"
        batch.total_records = len(records)
        db.commit()

        # Ingest records scoped to tenant
        stats = ingest_records(db=db, records=records, tenant_id=tenant_id, batch_id=batch.id)
        batch.processed_records = stats.get("inserted", 0)
        db.commit()

        # 3. CATEGORIZING
        batch.status = "CATEGORIZING"
        db.commit()

        cat_stats = run_batch_categorization(db=db, tenant_id=tenant_id, force=False)

        # 4. COMPLETED
        batch.status = "COMPLETED"
        batch.completed_at = datetime.now(timezone.utc)

        # Log to immutable audit log
        audit = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="import_batch",
            entity_id=str(batch.id),
            action="csv_import_completed",
            new_value=f"Ingested {batch.processed_records} transactions; categorized {cat_stats.get('categorized_count', 0)}",
            source="system",
            note=f"Import file: {batch.filename}",
        )
        db.add(audit)
        db.commit()

        logger.info(f"ImportBatch {batch_id} finished successfully: {stats}")
    except Exception as e:
        logger.exception(f"ImportBatch {batch_id} failed: {e}")
        db.rollback()
        batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        if batch:
            batch.status = "FAILED"
            batch.error_message = str(e)
            db.commit()
    finally:
        db.close()
