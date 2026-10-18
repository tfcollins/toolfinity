"""hal-assist tracer: candidate selection, naming, depth from side views."""

import asyncio

import cv2
import numpy as np
import pytest

import app.api.routes as routes
from app.fork import depth, hal_client, tracers
from app.fork.reference_photos import ReferencePhotoStore, refs_dir_for_image
from app.fork.registry import HAL_ASSIST
from app.fork.settings import ForkSettings
from app.services.tracer_registry import SUPPORTED_TRACERS, TRACER_LABELS

CFG = ForkSettings(
    hal_url="https://hal.test/v1", hal_api_key="k", assist_model="claude-sonnet-5",
    assist_base_tracers="isnet,birefnet-lite", depth_clearance_mm=1.0, depth_min_confidence=0.6,
)


def _mask(boxes, size=(400, 300)):
    """tools black on white, as every tracer writes them."""
    m = np.full((size[1], size[0]), 255, np.uint8)
    for x, y, w, h in boxes:
        cv2.rectangle(m, (x, y), (x + w, y + h), 0, -1)
    return m


class FakeBase:
    def __init__(self, mask):
        self.mask = mask

    async def _generate_mask_saliency(self, image_path, output_path=None, before_mask_write=None):
        cv2.imwrite(output_path, self.mask)
        return output_path


@pytest.fixture
def scene(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    image = processed / "s1_corrected.png"
    cv2.imwrite(str(image), np.full((300, 400, 3), 200, np.uint8))
    bases = {
        # isnet merges two tools into one blob; birefnet-lite separates them
        "isnet": FakeBase(_mask([(40, 40, 300, 120)])),
        "birefnet-lite": FakeBase(_mask([(40, 40, 120, 120), (220, 40, 120, 120)])),
    }
    monkeypatch.setattr(tracers.HalAssistTracer, "_base_tracer", lambda self, tid: bases[tid])
    return image, processed


def _fake_chat(reply, captured):
    async def chat(prompt, images, model, *, settings=None, client=None):
        captured.update(prompt=prompt, images=images, model=model)
        return reply

    return chat


def test_fork_tracer_is_registered():
    assert HAL_ASSIST in SUPPORTED_TRACERS
    assert TRACER_LABELS[HAL_ASSIST].startswith("Claude/Codex")


def test_get_tracer_builds_fork_tracer(monkeypatch):
    routes._tracers.clear()
    assert isinstance(routes._get_tracer(HAL_ASSIST), tracers.HalAssistTracer)
    routes._tracers.clear()


def test_picks_reviewed_candidate_names_and_sets_depth(scene, monkeypatch):
    image, processed = scene
    store = ReferencePhotoStore(refs_dir_for_image(image))
    ok, side = cv2.imencode(".jpg", np.zeros((60, 80, 3), np.uint8))
    store.add(side.tobytes(), ".jpg", "side", "both tools on their side")
    reply = """```json
{"best": "birefnet-lite", "issues": ["isnet merged regions"],
 "tools": [{"region": 1, "name": "Hex Key", "thickness_mm": 6.0, "confidence": 0.9},
           {"region": 2, "name": "pliers", "thickness_mm": 15, "confidence": 0.3}]}
```"""
    captured = {}
    monkeypatch.setattr(hal_client, "chat", _fake_chat(reply, captured))

    out_mask = processed / "s1_mask.png"
    polygons, mask_path = asyncio.run(
        tracers.HalAssistTracer(CFG).trace_tools(str(image), "", str(out_mask))
    )

    assert mask_path == str(out_mask) and out_mask.exists()
    assert [p.label for p in polygons] == ["hex key", "pliers"]
    [estimate] = depth.for_session(processed.parent, "s1")  # pliers is below the confidence bar
    assert (estimate.polygon_id, estimate.depth_mm, estimate.thickness_mm) == (polygons[0].id, 7.0, 6.0)
    # photo + one overlay per candidate + the side reference photo
    assert len(captured["images"]) == 4
    assert captured["model"] == "claude-sonnet-5"
    assert 'candidate "isnet"' in captured["prompt"] and "side view" in captured["prompt"]
    assert "thickness" in captured["prompt"]


def test_hal_failure_falls_back_to_first_candidate(scene, monkeypatch):
    image, processed = scene

    async def down(*a, **k):
        raise hal_client.HalError("HAL returned 503")

    monkeypatch.setattr(hal_client, "chat", down)
    polygons, _ = asyncio.run(
        tracers.HalAssistTracer(CFG).trace_tools(str(image), "", str(processed / "m.png"))
    )
    assert len(polygons) == 1  # isnet's single merged region
    assert polygons[0].label == "tool 1"


def test_no_side_photo_means_no_depth_and_no_thickness_prompt(scene, monkeypatch):
    image, processed = scene
    reply = '{"best": "birefnet-lite", "tools": [{"region": 1, "name": "chisel", "thickness_mm": 9, "confidence": 1}]}'
    captured = {}
    monkeypatch.setattr(hal_client, "chat", _fake_chat(reply, captured))
    polygons, _ = asyncio.run(
        tracers.HalAssistTracer(CFG).trace_tools(str(image), "", str(processed / "m.png"))
    )
    assert polygons[0].label == "chisel"
    assert depth.for_session(processed.parent, "s1") == []
    assert "thickness" not in captured["prompt"]
    assert len(captured["images"]) == 3


def test_parse_review_rejects_unknown_candidate_and_bad_names():
    review = tracers.parse_review(
        '{"best": "gemini", "tools": [{"region": "2", "name": "photo of a tool"}, {"region": "x"}]}',
        ["isnet"],
    )
    assert review.best is None
    assert [(t.region, t.name) for t in review.tools] == [(2, None)]
    assert tracers.parse_review("sorry", ["isnet"]) is None


def test_render_overlay_keeps_size():
    img = np.full((120, 160, 3), 255, np.uint8)
    out = tracers.render_overlay(img, [([(10, 10), (60, 10), (60, 60), (10, 60)], [])])
    assert out.shape == img.shape
    assert not np.array_equal(out, img)


def test_retrace_replaces_session_estimates(tmp_path):
    e = depth.DepthEstimate("p1", "s1", "hammer", 20.0, 21.0, 0.8)
    depth.record(tmp_path, "s1", [e])
    depth.record(tmp_path, "s2", [depth.DepthEstimate("p9", "s2", "saw", 2.0, 3.0, 0.9)])
    depth.record(tmp_path, "s1", [])
    assert depth.for_session(tmp_path, "s1") == []
    assert depth.for_polygon(tmp_path, "p9").depth_mm == 3.0


def test_bin_from_tools_uses_depth_estimate(tmp_path, monkeypatch):
    from app.config import ensure_user_dirs
    from app.models.schemas import Point, Tool

    monkeypatch.setattr(routes.settings, "storage_path", tmp_path)
    routes._store_cache.clear()
    ensure_user_dirs(tmp_path / "default")
    _, user_tools, _ = routes.get_stores("default")
    square = [Point(x=-10, y=-10), Point(x=10, y=-10), Point(x=10, y=10), Point(x=-10, y=10)]
    user_tools.set("t1", Tool(id="t1", name="hammer", points=square, source_polygon_id="p1"))
    user_tools.set("t2", Tool(id="t2", name="saw", points=square, source_polygon_id="p2"))
    depth.record(tmp_path / "default", "s1", [depth.DepthEstimate("p1", "s1", "hammer", 20.0, 21.0, 0.8)])

    bin_model = routes._build_bin_from_tools("b1", "bin", None, ["t1", "t2"], user_tools)
    assert [pt.depth_override for pt in bin_model.placed_tools] == [21.0, None]
