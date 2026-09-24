import logging
from typing import List, Dict, Any, Optional
import openai
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger("app.ai.deepseek")


class DeepSeekClientError(Exception):
    """Base exception for DeepSeek client errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, is_retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.is_retryable = is_retryable


class DeepSeekClient:
    """
    Dedicated client for DeepSeek LLM API communication.
    
    Responsibilities:
    - Initialize DeepSeek client with timeouts
    - Safe execution of chat completions and tool calls
    - Structured response parsing
    - Provider error handling & retry classification
    - Secret redaction (never log or expose credentials)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key = settings.DEEPSEEK_API_KEY if api_key is None else api_key
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL
        self.model = model or settings.DEEPSEEK_MODEL
        self.timeout = timeout or settings.DEEPSEEK_TIMEOUT_SECONDS
        self._client: Optional[OpenAI] = None

        if self._api_key and self._api_key.strip():
            try:
                self._client = OpenAI(
                    api_key=self._api_key.strip(),
                    base_url=self.base_url,
                    timeout=self.timeout,
                    max_retries=settings.DEEPSEEK_MAX_RETRIES,
                )
                logger.info("DeepSeek client initialized with model: %s", self.model)
            except Exception as e:
                logger.error("Failed to initialize DeepSeek client: %s", type(e).__name__)
                self._client = None
        else:
            logger.info("DeepSeek client initialized without API key (unconfigured)")

    @property
    def is_configured(self) -> bool:
        """Indicates whether a non-empty API key is configured and client initialized."""
        return bool(self._api_key and self._api_key.strip() and self._client is not None)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> Any:
        """
        Sends chat completion request to DeepSeek with optional tool calling definitions.
        
        Returns the chat completion response object from OpenAI SDK.
        Raises DeepSeekClientError on provider failures.
        """
        if not self.is_configured or self._client is None:
            raise DeepSeekClientError("DeepSeek API key is not configured.", status_code=503)

        logger.info("DeepSeek chat request started: model=%s, messages_count=%d", self.model, len(messages))

        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        try:
            response = self._client.chat.completions.create(**request_kwargs)
            logger.info("DeepSeek chat request completed successfully")
            return response

        except openai.RateLimitError as e:
            logger.warning("DeepSeek rate limit exceeded")
            raise DeepSeekClientError("DeepSeek rate limit exceeded. Please try again shortly.", status_code=429, is_retryable=True) from e

        except openai.APITimeoutError as e:
            logger.warning("DeepSeek request timed out after %s seconds", self.timeout)
            raise DeepSeekClientError("DeepSeek request timed out. Please try again.", status_code=504, is_retryable=True) from e

        except openai.APIStatusError as e:
            status = e.status_code
            logger.error("DeepSeek API error status %s: %s", status, getattr(e, 'message', type(e).__name__))
            
            if status == 401:
                msg = "DeepSeek authentication failed. Please verify API key configuration."
            elif status == 402:
                msg = "DeepSeek account balance is insufficient to process AI requests."
            elif status == 404:
                msg = f"DeepSeek model '{self.model}' was not found on this endpoint."
            else:
                msg = f"DeepSeek provider returned status {status}."
                
            raise DeepSeekClientError(msg, status_code=status, is_retryable=False) from e

        except openai.APIConnectionError as e:
            logger.error("DeepSeek connection error: %s", type(e).__name__)
            raise DeepSeekClientError("Failed to connect to DeepSeek API service.", status_code=502, is_retryable=True) from e

        except Exception as e:
            logger.error("Unexpected error in DeepSeek request: %s", type(e).__name__)
            raise DeepSeekClientError(f"Unexpected AI provider error: {type(e).__name__}", status_code=500) from e

    def health_check(self) -> Dict[str, Any]:
        """
        Performs a safe connectivity check against DeepSeek.
        Never exposes the API key or raw secret tokens.
        """
        if not self.is_configured:
            return {
                "provider": "deepseek",
                "configured": False,
                "available": False,
                "model": self.model,
                "status": "API key not configured in environment.",
            }

        try:
            # Query models endpoint to test credential and endpoint validity without token spend
            assert self._client is not None
            models = self._client.models.list()
            available_ids = [m.id for m in models.data] if hasattr(models, "data") else []
            return {
                "provider": "deepseek",
                "configured": True,
                "available": True,
                "model": self.model,
                "available_models": available_ids,
                "status": "DeepSeek API reachable and operational.",
            }
        except openai.APIStatusError as e:
            status = e.status_code
            desc = "Authentication failed" if status == 401 else (
                "Insufficient balance" if status == 402 else f"HTTP {status}"
            )
            return {
                "provider": "deepseek",
                "configured": True,
                "available": False,
                "model": self.model,
                "status": f"DeepSeek provider check returned status {status}: {desc}",
            }
        except Exception as e:
            return {
                "provider": "deepseek",
                "configured": True,
                "available": False,
                "model": self.model,
                "status": f"DeepSeek connectivity test failed: {type(e).__name__}",
            }
