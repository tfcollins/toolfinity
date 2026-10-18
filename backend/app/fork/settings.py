from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ForkSettings(BaseSettings):
    """fork-only settings, read from TOOLFINITY_* env vars so app/config.py
    stays identical to upstream."""

    model_config = SettingsConfigDict(
        env_prefix="TOOLFINITY_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    # HAL's OpenAI-compatible base url, e.g. https://hal.home.tfcollins.me/v1
    hal_url: str = ""
    hal_api_key: str = ""
    hal_timeout_seconds: float = 180.0

    # per-crop naming (TOOL_LABEL_PROVIDER=hal); codex-default = codex account default
    name_model: str = "claude-haiku-4-5-20251001"
    # hal-assist mask selection, batch naming and depth
    assist_model: str = "claude-sonnet-5"
    assist_base_tracers: str = "isnet,birefnet-lite"
    assist_image_max_px: int = 1280

    max_reference_photos: int = 6
    depth_clearance_mm: float = 1.0
    depth_min_confidence: float = 0.6

    @property
    def hal_configured(self) -> bool:
        return bool(self.hal_url and self.hal_api_key)

    @property
    def base_tracers(self) -> list[str]:
        return [t.strip() for t in self.assist_base_tracers.split(",") if t.strip()]


fork_settings = ForkSettings()
