import hashlib
import json
import logging
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.core.config import settings
from app.models.ai_usage import AIUsage
from app.models.tenant import Tenant
from app.ai.ollama_client import OllamaClient
from app.ai.deepseek_client import DeepSeekClient

logger = logging.getLogger("app.ai.router")

# Plan limits for monthly AI tokens
PLAN_TOKEN_LIMITS = {
    "STARTER": 50_000,
    "PRO": 500_000,
    "ENTERPRISE": 10_000_000,
}

# Local in-memory cache fallback when Redis is offline
_IN_MEMORY_AI_CACHE: Dict[str, Dict[str, Any]] = {}


class TaskType(str, Enum):
    CATEGORIZATION = "categorization"
    ANALYST = "analyst"
    VARIANCE_EXPLANATION = "variance_explanation"


class UsageLimitExceededError(Exception):
    def __init__(self, tenant_id: int, current_tokens: int, limit: int):
        super().__init__(
            f"Monthly AI token limit reached ({current_tokens:,} / {limit:,} tokens). "
            f"Please upgrade your workspace plan to continue AI investigations."
        )
        self.tenant_id = tenant_id
        self.current_tokens = current_tokens
        self.limit = limit


class ModelRouter:
    """
    Intelligent Model Router that handles:
    1. Provider & model routing (Ollama as primary assistant, DeepSeek as optional secondary)
    2. Tenant-scoped AI question caching (ensuring strict isolation between companies)
    3. Monthly AI token metering and plan limit enforcement per tenant
    """

    def __init__(self):
        self.ollama = OllamaClient()
        self.deepseek = DeepSeekClient()

    def get_client(self, task_type: TaskType = TaskType.ANALYST):
        """
        Selects client provider. Ollama is primary assistant provider per system configuration.
        """
        if self.ollama.is_configured:
            return self.ollama
        if self.deepseek.is_configured:
            return self.deepseek
        return self.ollama

    def get_model_name(self, task_type: TaskType = TaskType.ANALYST) -> str:
        if self.ollama.is_configured:
            return settings.OLLAMA_MODEL or "nemotron-3-nano:30b"
        return settings.DEEPSEEK_MODEL or "deepseek-flash"

    # ==========================================================================
    # TENANT-SCOPED CACHING
    # ==========================================================================

    def _generate_cache_key(self, tenant_id: int, query: str, context_key: str = "") -> str:
        clean_q = query.strip().lower()
        content_hash = hashlib.sha256(f"{clean_q}:{context_key}".encode("utf-8")).hexdigest()[:16]
        # Strict tenant prefix: tenant_id ALWAYS isolates cache entries
        return f"ai_cache:{tenant_id}:{content_hash}"

    def get_cached_response(self, tenant_id: int, query: str, context_key: str = "") -> Optional[Dict[str, Any]]:
        cache_key = self._generate_cache_key(tenant_id, query, context_key)
        # 1. Try Redis
        try:
            import redis
            r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1)
            raw = r.get(cache_key)
            if raw:
                logger.info("AI Cache HIT (Redis) for tenant %s", tenant_id)
                return json.loads(raw.decode("utf-8"))
        except Exception:
            pass

        # 2. Try In-Memory Fallback
        entry = _IN_MEMORY_AI_CACHE.get(cache_key)
        if entry:
            logger.info("AI Cache HIT (In-Memory) for tenant %s", tenant_id)
            return entry
        return None

    def set_cached_response(self, tenant_id: int, query: str, response_data: Dict[str, Any], context_key: str = "", ttl_seconds: int = 3600) -> None:
        cache_key = self._generate_cache_key(tenant_id, query, context_key)
        try:
            import redis
            r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1)
            r.setex(cache_key, ttl_seconds, json.dumps(response_data, default=str))
        except Exception:
            _IN_MEMORY_AI_CACHE[cache_key] = response_data

    # ==========================================================================
    # TENANT TOKEN USAGE & LIMITS
    # ==========================================================================

    def check_and_assert_token_limit(self, db: Session, tenant_id: int) -> None:
        """
        Asserts that the tenant has not exceeded their monthly AI token allowance.
        Raises UsageLimitExceededError before invoking external LLMs if limit reached.
        """
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        plan = (tenant.plan if tenant else "STARTER").upper()
        limit = PLAN_TOKEN_LIMITS.get(plan, PLAN_TOKEN_LIMITS["STARTER"])

        now = datetime.now(timezone.utc)
        month_usage = (
            db.query(func.coalesce(func.sum(AIUsage.total_tokens), 0))
            .filter(
                AIUsage.tenant_id == tenant_id,
                extract("year", AIUsage.created_at) == now.year,
                extract("month", AIUsage.created_at) == now.month,
            )
            .scalar()
        )

        current_tokens = int(month_usage or 0)
        if current_tokens >= limit:
            logger.warning(
                "Tenant %s exceeded monthly token limit (%d >= %d) on plan %s",
                tenant_id, current_tokens, limit, plan
            )
            raise UsageLimitExceededError(tenant_id, current_tokens, limit)

    def record_usage(
        self,
        db: Session,
        tenant_id: int,
        user_id: Optional[int],
        model: str,
        input_tokens: int,
        output_tokens: int,
        task_type: TaskType = TaskType.ANALYST,
        request_id: Optional[str] = None,
    ) -> AIUsage:
        total = input_tokens + output_tokens
        # Estimated cost tracking ($0.20 / 1M tokens estimated for small models)
        cost = round((total / 1_000_000.0) * 0.20, 6)

        usage = AIUsage(
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            model=model,
            task_type=task_type.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost=cost,
        )
        db.add(usage)
        db.commit()
        return usage


model_router = ModelRouter()

