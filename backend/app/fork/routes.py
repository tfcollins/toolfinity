"""reference photo endpoints, mounted at /api/fork."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.routes import ALLOWED_IMAGE_EXTENSIONS, MAX_UPLOAD_DIM, _ingest_with_limits, _user_path, get_stores
from app.auth import get_user_id
from app.config import settings
from app.fork import depth
from app.fork.reference_photos import REF_KINDS, ReferencePhotoStore, refs_dir
from app.fork.settings import fork_settings

router = APIRouter(prefix="/fork", tags=["fork"])


class ReferencePhotoOut(BaseModel):
    id: str
    kind: str
    note: str
    url: str


class ReferencePhotoList(BaseModel):
    photos: list[ReferencePhotoOut]
    kinds: list[str]
    max_photos: int


def _store(user_id: str, session_id: str) -> tuple[ReferencePhotoStore, Path]:
    user_sessions, _, _ = get_stores(user_id)
    if not user_sessions.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    up = _user_path(user_id)
    directory = refs_dir(up / "processed", session_id)
    return ReferencePhotoStore(directory, fork_settings.max_reference_photos), up


def _out(store: ReferencePhotoStore, up: Path, user_id: str) -> ReferencePhotoList:
    rel = store.directory.relative_to(up).as_posix()
    photos = [
        ReferencePhotoOut(id=p.id, kind=p.kind, note=p.note, url=f"/storage/{user_id}/{rel}/{p.filename}")
        for p in store.list()
    ]
    return ReferencePhotoList(photos=photos, kinds=list(REF_KINDS), max_photos=store.max_photos)


@router.get("/sessions/{session_id}/reference-photos", response_model=ReferencePhotoList)
async def list_reference_photos(session_id: str, user_id: str = Depends(get_user_id)):
    store, up = _store(user_id, session_id)
    return _out(store, up, user_id)


@router.post("/sessions/{session_id}/reference-photos", response_model=ReferencePhotoList)
async def add_reference_photo(
    session_id: str,
    image: UploadFile = File(...),
    kind: str = Form("side"),
    note: str = Form(""),
    user_id: str = Depends(get_user_id),
):
    store, up = _store(user_id, session_id)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")
    ext = Path(image.filename or "image.jpg").suffix.lower() or ".jpg"
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="unsupported image format")
    content = await image.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"file too large (max {settings.max_upload_mb}MB)")
    # same normalisation as the main upload: HEIC -> JPEG, EXIF rotation, size cap
    content, ext, _ = _ingest_with_limits(content, ext, MAX_UPLOAD_DIM)
    try:
        store.add(content, ext, kind, note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(store, up, user_id)


@router.delete("/sessions/{session_id}/reference-photos/{ref_id}", response_model=ReferencePhotoList)
async def delete_reference_photo(session_id: str, ref_id: str, user_id: str = Depends(get_user_id)):
    store, up = _store(user_id, session_id)
    if not store.delete(ref_id):
        raise HTTPException(status_code=404, detail="reference photo not found")
    return _out(store, up, user_id)


class DepthEstimateOut(BaseModel):
    polygon_id: str
    label: str
    thickness_mm: float
    depth_mm: float
    confidence: float


@router.get("/sessions/{session_id}/depth-estimates", response_model=list[DepthEstimateOut])
async def session_depth_estimates(session_id: str, user_id: str = Depends(get_user_id)):
    _, up = _store(user_id, session_id)
    return [DepthEstimateOut(**asdict(e)) for e in depth.for_session(up, session_id)]


@router.get("/tools/{tool_id}/depth-estimate", response_model=DepthEstimateOut | None)
async def tool_depth_estimate(tool_id: str, user_id: str = Depends(get_user_id)):
    _, user_tools, _ = get_stores(user_id)
    tool = user_tools.get(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="tool not found")
    estimate = depth.for_polygon(_user_path(user_id), tool.source_polygon_id)
    return DepthEstimateOut(**asdict(estimate)) if estimate else None
