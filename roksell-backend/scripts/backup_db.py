from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_env_file(path: Path) -> None:
    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_backup_dir() -> Path:
    backup_dir = os.getenv("BACKUP_DIR", "backups").strip()
    if not backup_dir:
        backup_dir = "backups"
    path = Path(backup_dir)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_pg_dump(database_url: str, output_path: Path) -> None:
    cmd = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--dbname",
        database_url,
        "--file",
        str(output_path),
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(f"pg_dump failed with exit code {result.returncode}")


def upload_backup(path: Path) -> str | None:
    bucket = os.getenv("BACKUP_S3_BUCKET")
    if not bucket:
        return None
    prefix = os.getenv("BACKUP_S3_PREFIX", "backups/db").strip().strip("/")
    key = f"{prefix}/{path.name}" if prefix else path.name
    endpoint_url = os.getenv("S3_ENDPOINT_URL")
    region = os.getenv("S3_REGION")

    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise SystemExit("boto3 is required for BACKUP_S3_BUCKET uploads") from exc

    config = None
    if endpoint_url:
        config = Config(
            signature_version="s3v4",
            s3={
                "addressing_style": "path",
                "payload_signing_enabled": False,
            },
        )

    client = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint_url,
        config=config,
    )
    client.upload_file(str(path), bucket, key)
    return f"s3://{bucket}/{key}"


def prune_old_backups(backup_dir: Path) -> None:
    keep_days_raw = os.getenv("BACKUP_KEEP_DAYS", "").strip()
    if not keep_days_raw:
        return
    try:
        keep_days = int(keep_days_raw)
    except ValueError:
        raise SystemExit("BACKUP_KEEP_DAYS must be an integer")
    if keep_days <= 0:
        return
    cutoff = datetime.now(timezone.utc).timestamp() - (keep_days * 86400)
    for path in backup_dir.glob("db-*.dump"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def main() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_env_file(env_path)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    backup_dir = resolve_backup_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = backup_dir / f"db-{timestamp}.dump"

    run_pg_dump(database_url, output_path)

    uploaded = upload_backup(output_path)
    if uploaded:
        print(f"Uploaded backup to {uploaded}")
    else:
        print(f"Backup saved to {output_path}")

    prune_old_backups(backup_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
