"""Sync the local DuckDB to Cloudflare R2 (SigV4, no external deps).

Thin CLI wrapper over mandi_rdd.storage.r2_sync (shared with run_hourly.py
and the API's startup restore).

Reads R2 credentials from the environment (or .env at repo root):
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET

Usage:
    python scripts/sync_duckdb_to_r2.py --check   # read-only: HEAD remote object, compare to local
    python scripts/sync_duckdb_to_r2.py --list    # read-only: list objects in the R2 bucket
    python scripts/sync_duckdb_to_r2.py --push    # gzip local DB and PUT to s3://<bucket>/mandi_iq.duckdb.gz

Exit codes (automation contract):
  --check : 0 = R2 up to date with local, 1 = stale/missing/unreachable
  --push  : 0 = uploaded, 1 = any failure

NOTE: --push unconditionally overwrites s3://<bucket>/mandi_iq.duckdb.gz
(prints the remote object's last-modified first as a record of what was
replaced). The DB path honors MANDIIQ_DB_PATH when it points at an
existing file, else falls back to the repo default.

The --check ETag comparison assumes the object was pushed by THIS tool
(deterministic gzip via mtime=0). Backups written by main.py's
/admin/backup-to-r2 or the GitHub Actions `gzip -c` embed a fresh mtime,
so their ETag will differ from a local re-gzip — that only makes --check
report STALE spuriously (re-push is idempotent; restore ignores mtime).
"""

import argparse
import hashlib
import os
import sys
import urllib.error
from pathlib import Path

# Ensure the repo root is on sys.path so mandi_rdd imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mandi_rdd.storage import r2_sync  # noqa: E402


def _load_env() -> None:
    """Load .env at repo root if present (never overwrite real env vars)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _resolve_db_path() -> Path:
    default = (
        Path(__file__).resolve().parent.parent / "mandi_rdd" / "data" / "mandi_iq.duckdb"
    )
    env_db = os.environ.get("MANDIIQ_DB_PATH", "")
    if env_db and Path(env_db).exists():
        return Path(env_db)
    return default


def _lock_hint() -> str:
    return (
        "\nThe DuckDB file is currently locked by another process (e.g. a running\n"
        "Streamlit dashboard or the API dev server on Windows). Close those apps\n"
        "first (Ctrl+C in their terminals), then re-run this script."
    )


def _db_rows(db_path: Path) -> int | None:
    try:
        import duckdb  # type: ignore

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            return conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return None


def cmd_check(db_path: Path) -> int:
    creds = r2_sync.get_creds()
    try:
        local_size = db_path.stat().st_size
    except PermissionError:
        print(f"ERROR: cannot stat {db_path}.{_lock_hint()}")
        return 1
    try:
        gz, _raw = r2_sync.gzip_db(db_path)
        rows = _db_rows(db_path)
    except PermissionError:
        print(f"ERROR: cannot read {db_path}.{_lock_hint()}")
        return 1
    print(f"Local:  {db_path}")
    print(f"  size          : {local_size:,} bytes ({local_size / 1e6:.1f} MB)")
    print(f"  gzipped size  : {len(gz):,} bytes ({len(gz) / 1e6:.1f} MB)")
    if rows is not None:
        print(f"  prices rows   : {rows:,}")
    try:
        remote = r2_sync.remote_metadata(creds)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: could not reach R2: {e}")
        return 1
    if not remote:
        print(f"Remote: {r2_sync.R2_KEY} not present in s3://{creds['bucket']}/")
        return 1
    print(f"Remote: s3://{creds['bucket']}/{r2_sync.R2_KEY}")
    print(f"  size          : {remote['content_length']:,} bytes ({remote['content_length'] / 1e6:.1f} MB)")
    print(f"  gzip?         : {remote['content_encoding'] or 'no'}")
    print(f"  last modified : {remote['last_modified']}")
    print(f"  etag (md5)    : {remote['etag'] or '(none)'}")
    # For single-part PUTs R2's ETag is the MD5 of the gzip — a stronger check than size.
    local_md5 = hashlib.md5(gz).hexdigest()
    print(f"  local md5      : {local_md5}")
    etag_ok = not remote["etag"] or remote["etag"].lower() == local_md5
    size_ok = remote["content_length"] == len(gz)
    if size_ok and etag_ok:
        print("\n=> R2 is UP TO DATE with the local DB (size + ETag match).")
        return 0
    print("\n=> R2 is STALE (size or content differs). Run with --push to update it.")
    return 1


def cmd_list() -> int:
    creds = r2_sync.get_creds()
    try:
        objects = r2_sync.list_objects(creds)
    except urllib.error.HTTPError as e:
        print(f"ERROR: list failed (HTTP {e.code}): {e.reason}")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: could not reach R2: {e}")
        return 1
    if not objects:
        print(f"s3://{creds['bucket']}/ is EMPTY (no objects).")
        return 0
    print(f"Objects in s3://{creds['bucket']}/:")
    for o in sorted(objects, key=lambda x: x["key"]):
        size = o["size"]
        human = f"{size / 1e6:.1f} MB" if size >= 1_000_000 else f"{size:,} bytes"
        print(f"  {o['key']:<28} {human:>12}  {o['last_modified']}")
    return 0


def cmd_push(db_path: Path) -> int:
    creds = r2_sync.get_creds()
    if not db_path.exists():
        print(f"Local DB missing: {db_path}")
        return 1
    try:
        prev = r2_sync.remote_metadata(creds)
    except Exception:  # noqa: BLE001
        prev = {}
    if prev:
        print(
            f"Replacing previous s3://{creds['bucket']}/{r2_sync.R2_KEY}: "
            f"{prev['content_length']:,} bytes, last modified {prev['last_modified']}"
        )
    try:
        result = r2_sync.upload_db(db_path)
    except PermissionError:
        print(f"ERROR: cannot read {db_path}.{_lock_hint()}")
        return 1
    except urllib.error.HTTPError as e:
        print(f"ERROR: upload failed (HTTP {e.code}): {e.reason}")
        if e.code == 403:
            print(
                "\nHINT: the R2 API token can READ but not WRITE. Create a token with\n"
                "'Object Read + Object Write' (or Admin) permission in Cloudflare:\n"
                "R2 -> Manage API Tokens -> Create API token, and grant Object Write.\n"
                "Then update R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY in .env and retry."
            )
        return 1
    pct = result["compression_pct"]
    print(
        f"Uploaded {result['compressed_bytes']:,} bytes (gzip of {result['raw_bytes']:,} bytes, "
        f"{pct}% smaller) to s3://{creds['bucket']}/{result['r2_key']}"
    )
    print("Now restorable by the API via POST /admin/restore-from-r2.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local DuckDB to Cloudflare R2")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--check", action="store_true",
        help="HEAD remote object and compare to local (read-only)",
    )
    group.add_argument(
        "--list", action="store_true",
        help="list objects in the R2 bucket (read-only)",
    )
    group.add_argument(
        "--push", action="store_true",
        help="gzip local DB and PUT to R2",
    )
    args = parser.parse_args()
    _load_env()
    db_path = _resolve_db_path()
    try:
        if args.list:
            return cmd_list()
        return cmd_check(db_path) if args.check else cmd_push(db_path)
    except r2_sync.R2NotConfigured as e:
        print(f"ERROR: {e}")
        print("Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and"
              " R2_BUCKET in .env or the environment, then retry.")
        return 1



if __name__ == "__main__":
    sys.exit(main())
