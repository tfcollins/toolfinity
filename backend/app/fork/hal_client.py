"""client for HAL's OpenAI-compatible /v1/chat/completions vision endpoint.

HAL runs these calls with every tool disabled, so a photo can't steer the
model into doing anything but answering."""

from __future__ import annotations

import base64
import json
import logging

import httpx

from app.fork.settings import ForkSettings, fork_settings

logger = logging.getLogger(__name__)


class HalError(RuntimeError):
    pass


def media_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise HalError("unsupported image bytes; expected png, jpeg or webp")


def build_payload(prompt: str, images: list[bytes], model: str) -> dict:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for data in images:
        url = f"data:{media_type(data)};base64,{base64.b64encode(data).decode('ascii')}"
        content.append({"type": "image_url", "image_url": {"url": url}})
    return {"model": model, "messages": [{"role": "user", "content": content}], "temperature": 0}


async def chat(
    prompt: str,
    images: list[bytes],
    model: str,
    *,
    settings: ForkSettings | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """send one prompt plus images; return the model's text answer."""
    cfg = settings or fork_settings
    if not cfg.hal_configured:
        raise HalError("HAL is not configured; set TOOLFINITY_HAL_URL and TOOLFINITY_HAL_API_KEY")
    url = cfg.hal_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.hal_api_key}"}
    payload = build_payload(prompt, images, model)

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=cfg.hal_timeout_seconds)
    try:
        response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise HalError(f"HAL request failed: {type(exc).__name__}") from exc
    finally:
        if own_client:
            await client.aclose()

    if response.status_code >= 400:
        raise HalError(f"HAL returned {response.status_code}: {response.text[:200]}")
    choices = response.json().get("choices") or [{}]
    content = (choices[0].get("message") or {}).get("content")
    if not content:
        raise HalError("HAL returned no content")
    return content


def extract_json(text: str) -> dict | None:
    """pull the outermost {...} out of a reply that may be fenced or chatty."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
