"""extra reference photos per trace session (side views, close-ups, other angles).

the paper-scaled corrected photo stays the only geometry source; these only
give the model more to look at. files live beside the session's corrected
image, in processed/<session_id>_refs/, so the tracer and namer can find them
from the image path upstream already hands them."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

RefKind = Literal["top", "side", "detail"]
REF_KINDS: tuple[str, ...] = ("top", "side", "detail")
INDEX_NAME = "refs.json"


@dataclass
class ReferencePhoto:
    id: str
    kind: str
    filename: str
    note: str = ""


def session_id_from_image(image_path: str | Path) -> str:
    return Path(image_path).stem.removesuffix("_corrected")


def refs_dir(processed_dir: Path, session_id: str) -> Path:
    return processed_dir / f"{session_id}_refs"


def refs_dir_for_image(image_path: str | Path) -> Path:
    """reference photo dir for a session's corrected image path."""
    path = Path(image_path)
    return refs_dir(path.parent, session_id_from_image(path))


class ReferencePhotoStore:
    def __init__(self, directory: Path, max_photos: int = 6):
        self.directory = directory
        self.max_photos = max_photos

    @property
    def _index(self) -> Path:
        return self.directory / INDEX_NAME

    def list(self) -> list[ReferencePhoto]:
        if not self._index.exists():
            return []
        try:
            entries = json.loads(self._index.read_text())
        except json.JSONDecodeError:
            return []
        return [ReferencePhoto(**e) for e in entries if (self.directory / e["filename"]).exists()]

    def add(self, content: bytes, ext: str, kind: str, note: str = "") -> ReferencePhoto:
        if kind not in REF_KINDS:
            raise ValueError(f"kind must be one of {', '.join(REF_KINDS)}")
        photos = self.list()
        if len(photos) >= self.max_photos:
            raise ValueError(f"at most {self.max_photos} reference photos per session")
        self.directory.mkdir(parents=True, exist_ok=True)
        ref_id = uuid.uuid4().hex[:12]
        photo = ReferencePhoto(id=ref_id, kind=kind, filename=f"{ref_id}{ext}", note=note[:200])
        (self.directory / photo.filename).write_bytes(content)
        self._write(photos + [photo])
        return photo

    def delete(self, ref_id: str) -> bool:
        photos = self.list()
        keep = [p for p in photos if p.id != ref_id]
        if len(keep) == len(photos):
            return False
        removed = next(p for p in photos if p.id == ref_id)
        (self.directory / removed.filename).unlink(missing_ok=True)
        self._write(keep)
        return True

    def clear(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)

    def path(self, photo: ReferencePhoto) -> Path:
        return self.directory / photo.filename

    def _write(self, photos: list[ReferencePhoto]) -> None:
        tmp = self._index.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(p) for p in photos]))
        tmp.replace(self._index)


def delete_for_image(image_path: str | None) -> None:
    """drop a session's reference photos; called when the session is deleted."""
    if image_path:
        ReferencePhotoStore(refs_dir_for_image(image_path)).clear()
