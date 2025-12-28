from __future__ import annotations

import os
import json
from dataclasses import dataclass

import httpx


@dataclass
class AIResult:
    ok: bool
    text: str
    error: str | None = None


class OpenAIClient:
    """
    Минималистичный клиент OpenAI Responses API.
    Ключ берём ТОЛЬКО из env: OPENAI_API_KEY
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_s: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout_s = timeout_s

    def enabled(self) -> bool:
        return bool(self.api_key)

    async def generate(self, system: str, user: str) -> AIResult:
        if not self.api_key:
            return AIResult(ok=False, text="", error="OPENAI_API_KEY is missing")

        url = "https://api.openai.com/v1/responses"
        headers = {
            "Authorization": f"Bearer {self.api_key}",  # Bearer auth  [oai_citation:2‡platform.openai.com](https://platform.openai.com/docs/api-reference/introduction?utm_source=chatgpt.com)
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "text", "text": system}]},
                {"role": "user", "content": [{"type": "text", "text": user}]},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.post(url, headers=headers, content=json.dumps(payload))
                if r.status_code >= 400:
                    return AIResult(ok=False, text="", error=f"HTTP {r.status_code}: {r.text[:3000]}")

                data = r.json()

                # В Responses API текст лежит в output[].content[].text (может быть несколько кусочков)
                out_text_parts: list[str] = []
                for item in data.get("output", []) or []:
                    for c in item.get("content", []) or []:
                        t = c.get("text")
                        if isinstance(t, str) and t.strip():
                            out_text_parts.append(t.strip())

                text = "\n\n".join(out_text_parts).strip()
                if not text:
                    text = str(data)[:1500]

                return AIResult(ok=True, text=text)

        except Exception as e:
            return AIResult(ok=False, text="", error=str(e))
