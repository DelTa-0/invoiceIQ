"""LLM provider clients. Default route = EU (Mistral), per-org policy resolved
via `llm.registry` (docs/13 §5). The Mistral client talks HTTP directly
(httpx) so no extra provider SDK is required."""

from __future__ import annotations

import json
import re
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

MISTRAL_DEFAULT_MODEL = "mistral-medium"


class LLMClient(Protocol):
    name: str

    def complete(
        self, messages: list[dict], *, json_mode: bool = False, temperature: float = 0.0
    ) -> str: ...


class MistralClient:
    """Mistral (EU-hosted) chat completions client. Docs: docs/13 §5."""

    name = "mistral"

    def __init__(self, model: str = MISTRAL_DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"

    def complete(self, messages, *, json_mode=False, temperature=0.0) -> str:
        if not self.api_key:
            raise RuntimeError("IIQ_LLM_API_KEY is not set; refusing to call Mistral")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class MockClient:
    """Deterministic canned responses — local runs without a key + tests."""

    name = "mock"

    def __init__(self, response: str):
        self._response = response

    def complete(self, messages, *, json_mode=False, temperature=0.0) -> str:
        return self._response


def get_client(route: str, *, api_key: str | None = None) -> LLMClient:
    """Build a client for a `provider:model` route from llm.registry."""
    provider, _, model = route.partition(":")
    if provider == "mistral":
        return MistralClient(model or MISTRAL_DEFAULT_MODEL, api_key)
    if provider == "mock":
        return MockClient("{}")
    raise ValueError(f"unimplemented LLM provider: {provider}")


def _strip_fences(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return fence.group(1) if fence else text


def parse_json_text(text: str) -> dict:
    """Parse model output, tolerating code fences and stray prose."""
    candidate = _strip_fences(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def complete_structured[T: BaseModel](
    client: LLMClient, messages: list[dict], model: type[T]
) -> T:
    """Call + parse into `model`, with one retry-with-fix on schema failure
    (docs/12 §4: never free-form re-prompt loops)."""
    raw = client.complete(messages, json_mode=True, temperature=0.0)
    try:
        return model.model_validate(parse_json_text(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        fix = [
            *messages,
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": f"Your previous output failed validation: {exc}. Return ONLY corrected JSON matching the schema.",
            },
        ]
        retry = client.complete(fix, json_mode=True, temperature=0.0)
        return model.model_validate(parse_json_text(retry))
