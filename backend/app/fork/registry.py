"""fork tracer ids. kept free of app imports: tracer_registry imports this."""

from __future__ import annotations

HAL_ASSIST = "hal-assist"

FORK_TRACER_LABELS = {
    HAL_ASSIST: "Claude/Codex assisted (HAL)",
}


def is_fork_tracer(tracer_id: str) -> bool:
    return tracer_id in FORK_TRACER_LABELS
