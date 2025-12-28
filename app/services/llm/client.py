# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import httpx


class LLMClient:
    """
    OpenAI-compatible HTTP client.
    Работает с любым провайдером, который поддерживает:
    POST {BASE_URL}/chat/completions
    Headers: Authorization: Bearer <KEY>
    Body: {model, messages, temperature, max_tokens}
    """
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY") or ""
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        self.timeout_s = timeout_s

    def enabled(self) -> bool:
        return bool(self.api_key)

    async def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        if not self.enabled():
            return ""

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.post(url, headers=headers, content=json.dumps(payload))
            r.raise_for_status()
            data = r.json()

        # стандартный формат: choices[0].message.content
        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            return ""
