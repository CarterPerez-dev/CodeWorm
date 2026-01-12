"""
ⒸAngelaMos | 2026
llm/client.py
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from codeworm.core import get_logger

if TYPE_CHECKING:
    from codeworm.core.config import OllamaSettings

logger = get_logger("llm")


class OllamaError(Exception):
    """
    Base exception for Ollama errors
    """

class OllamaConnectionError(OllamaError):
    """
    Failed to connect to Ollama
    """

class OllamaModelError(OllamaError):
    """
    Model-related error like OOM
    """

class OllamaTimeoutError(OllamaError):
    """
    Request timed out
    """

@dataclass
class GenerationResult:
    """
    Result from an LLM generation request
    """
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_duration_ms: int
    tokens_per_second: float

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class OllamaClient:
    """
    Async client for Ollama API
    Handles connection pooling, retries, and OOM recovery
    """
    DEFAULT_TIMEOUT = httpx.Timeout(timeout=600.0, connect=10.0)

    def __init__(self, settings: OllamaSettings) -> None:
        """
        Initialize client with settings
        """
        self.settings = settings
        self.base_url = settings.base_url
        self._client: httpx.AsyncClient | None = None
        self._model_loaded = False

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create the HTTP client
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.DEFAULT_TIMEOUT,
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=50,
                    keepalive_expiry=60.0,
                ),
            )
        return self._client

    async def close(self) -> None:
        """
        Close the HTTP client
        """
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """
        Check if Ollama is running and responsive
        """
        try:
            client = await self._get_client()
            response = await client.get("/")
            return response.status_code == 200
        except Exception:
            return False

    async def prewarm(self) -> bool:
        """
        Load model into memory and keep it warm
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/generate",
                json={
                    "model": self.settings.model,
                    "prompt": "",
                    "keep_alive": self.settings.keep_alive,
                    "options": {
                        "num_ctx": self.settings.num_ctx,
                    },
                },
            )

            if response.status_code == 200:
                self._model_loaded = True
                logger.info(
                    "model_prewarmed",
                    model=self.settings.model,
                    num_ctx=self.settings.num_ctx,
                )
                return True

            return False

        except Exception as e:
            logger.error("prewarm_failed", error=str(e))
            return False

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """
        Generate text from a prompt
        """
        client = await self._get_client()

        options = {
            "temperature": temperature or self.settings.temperature,
            "num_predict": max_tokens or self.settings.num_predict,
            "num_ctx": self.settings.num_ctx,
        }

        payload = {
            "model": self.settings.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }

        if system:
            payload["system"] = system

        try:
            response = await client.post("/api/generate", json=payload)

            if response.status_code != 200:
                error_text = response.text
                if "out of memory" in error_text.lower() or "cuda" in error_text.lower():
                    raise OllamaModelError(f"Model OOM: {error_text}")
                raise OllamaError(f"Generation failed: {error_text}")

            data = response.json()

            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            total_duration = data.get("total_duration", 0) / 1_000_000

            tokens_per_sec = 0.0
            if total_duration > 0 and completion_tokens > 0:
                tokens_per_sec = completion_tokens / (total_duration / 1000)

            return GenerationResult(
                text=data.get("response", ""),
                model=data.get("model", self.settings.model),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_duration_ms=int(total_duration),
                tokens_per_second=tokens_per_sec,
            )

        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Cannot connect to Ollama at {self.base_url}: {e}")
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Request timed out: {e}")

    async def generate_with_retry(
        self,
        prompt: str,
        system: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> GenerationResult:
        """
        Generate with automatic retry on transient failures
        """
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                return await self.generate(prompt, system)

            except OllamaModelError:
                logger.warning("model_oom_detected", attempt=attempt + 1)
                await self._recover_from_oom()
                last_error = OllamaModelError("Model OOM after recovery attempt")

            except OllamaTimeoutError as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

            except OllamaConnectionError as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        raise last_error or OllamaError("Generation failed after retries")

    async def _recover_from_oom(self) -> None:
        """
        Attempt to recover from OOM by unloading and reloading model
        """
        logger.info("attempting_oom_recovery")

        try:
            client = await self._get_client()
            await client.post(
                "/api/generate",
                json={
                    "model": self.settings.model,
                    "keep_alive": "0",
                },
            )

            await asyncio.sleep(5)

            reduced_ctx = min(self.settings.num_ctx, 8192)
            await client.post(
                "/api/generate",
                json={
                    "model": self.settings.model,
                    "prompt": "",
                    "keep_alive": self.settings.keep_alive,
                    "options": {"num_ctx": reduced_ctx},
                },
            )

            logger.info("oom_recovery_complete", new_ctx=reduced_ctx)

        except Exception as e:
            logger.error("oom_recovery_failed", error=str(e))
            raise OllamaModelError(f"OOM recovery failed: {e}")

    async def list_models(self) -> list[dict]:
        """
        List available models
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            if response.status_code == 200:
                return response.json().get("models", [])
            return []
        except Exception:
            return []


async def create_client(settings: OllamaSettings) -> OllamaClient:
    """
    Create and initialize an Ollama client
    """
    client = OllamaClient(settings)

    if not await client.health_check():
        logger.warning("ollama_not_responding", url=settings.base_url)

    return client
