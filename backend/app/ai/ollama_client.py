import logging
from typing import List, Dict, Any, Optional
import openai
from app.core.config import settings

logger = logging.getLogger("app.ai.ollama")


class OllamaClientError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, is_retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.is_retryable = is_retryable


class OllamaClient:
    """
    OpenAI-compatible client for Ollama API (cloud or local).
    Executes chat completions, tool calls, and handles timeouts gracefully.
    Never logs secret keys.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.OLLAMA_API_KEY or "ollama"
        self.base_url = (base_url or settings.OLLAMA_BASE_URL or "https://ollama.com/v1").rstrip("/")
        self.default_model = default_model or settings.OLLAMA_MODEL or "nemotron-3-nano:30b"
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

        self._client: Optional[openai.OpenAI] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        if not self.api_key:
            logger.warning("Ollama API key not configured. Client initialized in degraded mode.")
            self._client = None
            return

        try:
            self._client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=1,
            )
            logger.info("Ollama client successfully initialized (base_url=%s, model=%s)", self.base_url, self.default_model)
        except Exception as e:
            logger.error("Failed to initialize Ollama client: %s", type(e).__name__)
            self._client = None

    @property
    def is_configured(self) -> bool:
        return self._client is not None and bool(self.api_key)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Any:
        if not self.is_configured:
            raise OllamaClientError("Ollama provider is not configured.", status_code=503)

        chosen_model = model or self.default_model
        request_kwargs: Dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        logger.info("Sending Ollama chat request (model=%s, messages_count=%d)", chosen_model, len(messages))

        try:
            response = self._client.chat.completions.create(**request_kwargs)
            return response
        except openai.AuthenticationError as e:
            logger.error("Ollama authentication failed: status 401")
            raise OllamaClientError("Authentication failed with Ollama provider.", status_code=401) from e
        except openai.RateLimitError as e:
            logger.warning("Ollama rate limit exceeded")
            raise OllamaClientError("Ollama rate limit reached. Please try again shortly.", status_code=429, is_retryable=True) from e
        except openai.APITimeoutError as e:
            logger.error("Ollama request timed out after %.1f seconds", self.timeout)
            raise OllamaClientError("Ollama service timed out while analyzing financial records.", status_code=504, is_retryable=True) from e
        except openai.APIStatusError as e:
            status = getattr(e, "status_code", 500)
            logger.error("Ollama API error status %s: %s", status, getattr(e, "message", type(e).__name__))
            raise OllamaClientError(f"Ollama provider error ({status})", status_code=status) from e
        except Exception as e:
            logger.error("Unexpected error communicating with Ollama: %s", type(e).__name__)
            raise OllamaClientError(f"Unexpected provider error: {type(e).__name__}", status_code=500) from e

    def health_check(self) -> Dict[str, Any]:
        """Validates connectivity to Ollama without logging secret credentials."""
        if not self.is_configured:
            return {
                "provider": "ollama",
                "configured": False,
                "available": False,
                "model": self.default_model,
                "status": "OLLAMA_API_KEY is not configured.",
            }

        try:
            models_page = self._client.models.list()
            available = [m.id for m in getattr(models_page, "data", [])]
            return {
                "provider": "ollama",
                "configured": True,
                "available": True,
                "model": self.default_model,
                "available_models": available[:10],
                "status": "Ollama API reachable and operational.",
            }
        except Exception as e:
            return {
                "provider": "ollama",
                "configured": True,
                "available": False,
                "model": self.default_model,
                "status": f"Ollama connection check failed: {type(e).__name__}",
            }
