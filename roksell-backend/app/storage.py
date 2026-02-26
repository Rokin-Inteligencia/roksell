from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol
from urllib.parse import urlparse

from app.media import (
    build_public_url,
    ensure_dir,
    media_root,
    relative_path_for_file,
    resolve_media_path_from_url,
)

try:
    import boto3  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    boto3 = None
else:
    from botocore.config import Config  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen


class StorageBackend(Protocol):
    def save(self, key: str, contents: bytes, content_type: str | None) -> str: ...
    def delete_by_url(self, url: str) -> None: ...


@dataclass(frozen=True)
class LocalStorage:
    def save(self, key: str, contents: bytes, content_type: str | None) -> str:
        dest_path = media_root() / key
        ensure_dir(dest_path.parent)
        dest_path.write_bytes(contents)
        return build_public_url(relative_path_for_file(dest_path))

    def delete_by_url(self, url: str) -> None:
        old_path = resolve_media_path_from_url(url)
        if old_path and old_path.exists():
            try:
                old_path.unlink()
            except OSError:
                pass


@dataclass(frozen=True)
class S3Storage:
    bucket: str
    region: str | None
    endpoint_url: str | None
    public_base_url: str | None
    acl: str | None

    def __post_init__(self) -> None:
        if boto3 is None:
            raise RuntimeError("boto3 is required for S3 storage")

    def _client(self):
        config = None
        if self.endpoint_url:
            config = Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": "path",
                    "payload_signing_enabled": False,
                },
            )
        return boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
            config=config,
        )

    def save(self, key: str, contents: bytes, content_type: str | None) -> str:
        extra: dict[str, int | str] = {"ContentLength": len(contents)}
        if content_type:
            extra["ContentType"] = content_type
        if self.acl:
            extra["ACL"] = self.acl
        try:
            self._client().put_object(Bucket=self.bucket, Key=key, Body=contents, **extra)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "MissingContentLength":
                raise
            self._put_object_via_presigned_url(key, contents, content_type)
        return self._build_public_url(key)

    def delete_by_url(self, url: str) -> None:
        key = self._key_from_url(url)
        if not key:
            return
        self._client().delete_object(Bucket=self.bucket, Key=key)

    def _build_public_url(self, key: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{key}"
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{key}"
        if self.region:
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"

    def _key_from_url(self, url: str) -> str | None:
        if self.public_base_url:
            prefix = self.public_base_url.rstrip("/") + "/"
            if url.startswith(prefix):
                return url[len(prefix):]
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        path = parsed.path.lstrip("/")
        if not path:
            return None
        bucket_prefix = f"{self.bucket}/"
        if path.startswith(bucket_prefix):
            return path[len(bucket_prefix):]
        return path

    def _put_object_via_presigned_url(
        self,
        key: str,
        contents: bytes,
        content_type: str | None,
    ) -> None:
        params: dict[str, str] = {"Bucket": self.bucket, "Key": key}
        if content_type:
            params["ContentType"] = content_type
        url = self._client().generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=600,
        )
        headers = {"Content-Length": str(len(contents))}
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(url, data=contents, headers=headers, method="PUT")
        try:
            with urlopen(request) as response:
                if response.status >= 400:
                    raise RuntimeError(f"Presigned upload failed with status {response.status}")
        except HTTPError as exc:
            raise RuntimeError(f"Presigned upload failed with status {exc.code}") from exc


def build_media_key(*parts: str) -> str:
    return "/".join(p.strip("/") for p in parts if p and p.strip("/"))


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if backend == "s3":
        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise RuntimeError("S3_BUCKET must be set when STORAGE_BACKEND=s3")
        region = os.getenv("S3_REGION")
        endpoint_url = os.getenv("S3_ENDPOINT_URL")
        public_base_url = os.getenv("S3_PUBLIC_BASE_URL")
        acl = os.getenv("S3_UPLOAD_ACL", "public-read")
        return S3Storage(
            bucket=bucket,
            region=region,
            endpoint_url=endpoint_url,
            public_base_url=public_base_url,
            acl=acl,
        )
    return LocalStorage()


def is_local_storage() -> bool:
    return isinstance(get_storage_backend(), LocalStorage)


def storage_save(key: str, contents: bytes, content_type: str | None) -> str:
    return get_storage_backend().save(key, contents, content_type)


def storage_delete_by_url(url: str | None) -> None:
    if not url:
        return
    get_storage_backend().delete_by_url(url)
