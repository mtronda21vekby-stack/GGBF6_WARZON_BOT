from typing import List, Dict
from openai import OpenAI


class AI:
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat(self, system: str, messages: List[Dict[str, str]]) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=0.7,
        )
        return (resp.choices[0].message.content or "").strip()