from __future__ import annotations

import argparse
import os
import subprocess
import sys
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


def run_pg_restore(database_url: str, backup_path: Path) -> None:
    cmd = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--dbname",
        database_url,
        str(backup_path),
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(f"pg_restore failed with exit code {result.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore database from a .dump backup.")
    parser.add_argument("--backup", required=True, help="Path to the .dump file")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm you want to overwrite the target database",
    )
    args = parser.parse_args()

    if not args.confirm:
        raise SystemExit("Refusing to run without --confirm")

    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_env_file(env_path)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    backup_path = Path(args.backup).expanduser()
    if not backup_path.exists():
        raise SystemExit(f"Backup file not found: {backup_path}")

    run_pg_restore(database_url, backup_path)
    print("Restore completed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
