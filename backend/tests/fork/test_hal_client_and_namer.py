"""HAL client and TOOL_LABEL_PROVIDER=hal."""

import asyncio
import base64

import httpx
import pytest

from app.fork import hal_client
from app.fork.namer import HalToolNamer
from app.fork.settings import ForkSettings
from app.services.tool_namer import ToolNamerConfig, create_tool_namer

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 16
CFG = ForkSettings(hal_url="https://hal.test/v1/", hal_api_key="k", name_model="claude-haiku-4-5-20251001")


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_build_payload_sends_every_image_as_data_url():
    payload = hal_client.build_payload("p", [PNG, JPEG], "m")
    parts = payload["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "p"}
    urls = [p["image_url"]["url"] for p in parts[1:]]
    assert urls[0].startswith("data:image/png;base64,")
    assert urls[1].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(urls[1].split(",", 1)[1]) == JPEG


def test_chat_posts_bearer_to_chat_completions():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"name":"hammer"}'}}]})

    text = asyncio.run(hal_client.chat("p", [PNG], "m", settings=CFG, client=_client(handler)))
    assert text == '{"name":"hammer"}'
    assert seen == {"url": "https://hal.test/v1/chat/completions", "auth": "Bearer k"}


def test_chat_raises_on_http_error_and_unconfigured():
    client = _client(lambda r: httpx.Response(502, text="codex exited"))
    with pytest.raises(hal_client.HalError, match="502"):
        asyncio.run(hal_client.chat("p", [PNG], "m", settings=CFG, client=client))
    with pytest.raises(hal_client.HalError, match="not configured"):
        asyncio.run(hal_client.chat("p", [PNG], "m", settings=ForkSettings(hal_url="", hal_api_key="")))


def test_extract_json_handles_fences():
    assert hal_client.extract_json('```json\n{"best": "isnet"}\n```') == {"best": "isnet"}
    assert hal_client.extract_json("no json here") is None


def test_factory_returns_hal_namer():
    namer = create_tool_namer(ToolNamerConfig(provider="hal"))
    assert isinstance(namer, HalToolNamer)


def test_hal_namer_validates_label(monkeypatch):
    async def fake_chat(prompt, images, model, *, settings=None, client=None):
        assert images == [PNG] and model == "claude-haiku-4-5-20251001"
        return '```json\n{"name": "Combination Pliers"}\n```'

    monkeypatch.setattr(hal_client, "chat", fake_chat)
    assert asyncio.run(HalToolNamer(settings=CFG).name(PNG)) == "combination pliers"


def test_hal_namer_swallows_hal_errors(monkeypatch):
    async def fail(*a, **k):
        raise hal_client.HalError("down")

    monkeypatch.setattr(hal_client, "chat", fail)
    assert asyncio.run(HalToolNamer(settings=CFG).name(PNG)) is None
