"""TOOL_LABEL_PROVIDER=hal: name each tool crop with Claude or Codex via HAL."""

from __future__ import annotations

import logging

from app.fork import hal_client
from app.fork.settings import ForkSettings, fork_settings
from app.services.tool_namer import LABEL_PROMPT, parse_label_response

logger = logging.getLogger(__name__)


class HalToolNamer:
    def __init__(self, config=None, settings: ForkSettings | None = None):
        # config is the upstream ToolNamerConfig; HAL settings come from TOOLFINITY_*
        self.config = config
        self.settings = settings or fork_settings

    async def name(self, image_png: bytes) -> str | None:
        if not self.settings.hal_configured:
            logger.warning("tool naming provider=hal but TOOLFINITY_HAL_URL/API_KEY not set")
            return None
        try:
            raw = await hal_client.chat(
                LABEL_PROMPT, [image_png], self.settings.name_model, settings=self.settings
            )
        except hal_client.HalError as exc:
            logger.info("hal naming failed: %s", exc)
            return None
        return parse_label_response(raw)
