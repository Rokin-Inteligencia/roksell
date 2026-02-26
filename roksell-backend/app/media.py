from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_MEDIA_ROOT = "uploads"
DEFAULT_MEDIA_URL = "/media"
DEFAULT_PUBLIC_BASE_URL = "http://127.0.0.1:8000"


def media_root() -> Path:
    root = os.getenv("MEDIA_ROOT", DEFAULT_MEDIA_ROOT)
    return Path(root).resolve()


def media_url() -> str:
    return os.getenv("MEDIA_URL", DEFAULT_MEDIA_URL).rstrip("/")


def public_base_url() -> str:
    base = os.getenv("PUBLIC_BASE_URL", os.getenv("API_PUBLIC_URL", DEFAULT_PUBLIC_BASE_URL))
    return base.rstrip("/")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_public_url(relative_path: str) -> str:
    rel = relative_path.lstrip("/")
    return f"{public_base_url()}{media_url()}/{rel}"


def relative_path_for_file(path: Path) -> str:
    return path.relative_to(media_root()).as_posix()


def resolve_media_path_from_url(url: str) -> Path | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    prefix = media_url()
    if not parsed.path.startswith(prefix):
        return None
    rel = parsed.path[len(prefix):].lstrip("/")
    if not rel:
        return None
    candidate = media_root() / rel
    try:
        resolved = candidate.resolve()
        root_resolved = media_root().resolve()
    except OSError:
        return None
    if root_resolved == resolved or root_resolved in resolved.parents:
        return resolved
    return None
