"""per-tool pocket depth estimated from side-view reference photos.

upstream keeps depth on the bin placement (PlacedTool.depth_override), not on
the traced polygon, so estimates live in a per-user sidecar keyed by polygon
id and are applied when a saved tool is first placed in a bin. the user can
still change the depth in the bin editor."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

_lock = threading.Lock()


@dataclass
class DepthEstimate:
    polygon_id: str
    session_id: str
    label: str
    thickness_mm: float
    depth_mm: float
    confidence: float


def estimates_path(user_path: Path) -> Path:
    return user_path / "fork" / "depth_estimates.json"


def _load(user_path: Path) -> dict[str, dict]:
    path = estimates_path(user_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def record(user_path: Path, session_id: str, estimates: list[DepthEstimate]) -> None:
    """replace a session's estimates (a re-trace makes new polygon ids)."""
    with _lock:
        data = {k: v for k, v in _load(user_path).items() if v.get("session_id") != session_id}
        data.update({e.polygon_id: asdict(e) for e in estimates})
        path = estimates_path(user_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(path)


def for_session(user_path: Path, session_id: str) -> list[DepthEstimate]:
    return [DepthEstimate(**v) for v in _load(user_path).values() if v.get("session_id") == session_id]


def for_polygon(user_path: Path, polygon_id: str | None) -> DepthEstimate | None:
    entry = _load(user_path).get(polygon_id or "")
    return DepthEstimate(**entry) if entry else None


def depth_for_tool(user_tools, tool) -> float | None:
    """placement default for a library tool; None keeps the bin's cutout depth.

    takes the user's ToolStore (its tools.json sits in the user dir). never
    raises: a missing or odd estimate must not break bin creation."""
    store_file = getattr(user_tools, "file_path", None)
    polygon_id = getattr(tool, "source_polygon_id", None)
    if not isinstance(store_file, Path) or not isinstance(polygon_id, str):
        return None
    try:
        estimate = for_polygon(store_file.parent, polygon_id)
    except (OSError, TypeError, ValueError):
        return None
    return estimate.depth_mm if estimate else None
