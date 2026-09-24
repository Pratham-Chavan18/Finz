import os
import logging
from celery import Celery
from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "finreview_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min hard limit
)


def dispatch_async_task(task, *args, **kwargs):
    """
    Safely dispatches a Celery task. If Redis/Celery broker is unreachable
    (e.g., in local lightweight development), executes the task synchronously inline
    so developer workflows and background state transitions never stall.
    """
    try:
        res = task.delay(*args, **kwargs)
        return {"mode": "async", "task_id": res.id}
    except Exception as e:
        logger.warning(
            f"Celery broker unavailable ({e}); executing task '{task.__name__}' inline."
        )
        try:
            task(*args, **kwargs)
            return {"mode": "inline", "task_id": "inline"}
        except Exception as inline_err:
            logger.error(f"Inline task execution failed: {inline_err}")
            raise
