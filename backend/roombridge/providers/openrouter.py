"""OpenRouter adapter. Multi-backbone via one endpoint, matching MAD's approach
(sec5_infer_api.py posts to openrouter.ai) but with retry/backoff, typed errors,
usage capture, and no hardcoded key (MAD hardcoded it at sec5_infer_api.py:10)."""
from __future__ import annotations

import time

import httpx

from ..config import settings
from .base import CallResult, LLMError, Message


def _redact(text: str) -> str:
    key = settings.openrouter_api_key
    return text.replace(key, "***") if key else text


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self) -> None:
        if not settings.openrouter_api_key:
            raise LLMError(
                "OPENROUTER_API_KEY is not set. Put it in a gitignored .env, or use the "
                "mock provider (--provider mock) for zero-cost development."
            )
        self._client = httpx.Client(
            base_url=settings.openrouter_base_url,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/d3yja/RoomBridge",
                "X-Title": "RoomBridge",
            },
            timeout=settings.request_timeout_s,
        )

    def complete_text(
        self, messages: list[Message], *, model: str, seed: int | None, temperature: float
    ) -> CallResult:
        body = {"model": model, "messages": messages, "temperature": temperature}
        if seed is not None:
            body["seed"] = seed

        last_err: Exception | None = None
        for attempt in range(settings.max_retries):
            try:
                resp = self._client.post("/chat/completions", json=body)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"retryable status {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
                if "choices" not in data:
                    raise LLMError(f"no choices in response: {_redact(str(data))[:400]}")
                content = data["choices"][0]["message"]["content"]
                return CallResult(raw=content, usage=data.get("usage", {}) or {}, model=model)
            except (httpx.HTTPStatusError, httpx.TransportError, LLMError) as e:
                last_err = e
                if attempt < settings.max_retries - 1:
                    time.sleep(2 ** (attempt + 1))  # 2s, 4s, 8s
        raise LLMError(f"OpenRouter call failed after {settings.max_retries} attempts: "
                       f"{_redact(str(last_err))}")
