"""Webhook dispatcher.  Fires POST with JSON payload on export completion."""

from __future__ import annotations

import asyncio

import httpx


async def dispatch_webhook(url: str, payload: dict) -> dict:
    """POST JSON payload to webhook URL.  Returns the response JSON or
    raises on non-2xx status."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}


def dispatch_webhook_sync(url: str, payload: dict) -> dict:
    """Synchronous wrapper for dispatch_webhook."""
    return asyncio.run(dispatch_webhook(url, payload))