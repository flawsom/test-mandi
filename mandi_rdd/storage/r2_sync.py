"""Reusable Cloudflare R2 (S3-compatible) helpers — stdlib only (SigV4).

Shared by:
  * scripts/sync_duckdb_to_r2.py    — CLI: --check / --list / --push
  * run_hourly.py                   — uploads the DuckDB to R2 after a successful run
                                      (R2-as-data-bus: the Northflank cron runs volumeless
                                      on the free tier, so R2 is how the API gets fresh data)
  * mandi_rdd/api/main.py lifespan  — restores the DuckDB from R2 on a fresh/empty volume
                                      instead of re-ingesting from scratch

Credentials come from the environment (duckdb_store.py already loads .env):
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET

Object key: mandi_iq.duckdb.gz — matches main.py's /admin/backup-to-r2 and
/admin/restore-from-r2, so anything uploaded here is restorable by the API.

Gzip is deterministic (mtime=0) so a local re-gzip's md5 can be compared to
the remote ETag (single-part PUT ETag == md5 of the uploaded bytes).
"""

from __future__ import annotations

import datetime
import gzip
import hashlib
import hmac
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

SERVICE = "s3"
REGION = "auto"
R2_KEY = "mandi_iq.duckdb.gz"


class R2NotConfigured(ValueError):
    """Raised when any R2_* credential is missing from the environment."""


def get_creds() -> dict:
    """Return validated R2 credentials; raise R2NotConfigured if any is missing."""
    account_id = os.environ.get("R2_ACCOUNT_ID", "")
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    bucket = os.environ.get("R2_BUCKET", "")
    missing = [
        name
        for name, val in (
            ("R2_ACCOUNT_ID", account_id),
            ("R2_ACCESS_KEY_ID", access_key),
            ("R2_SECRET_ACCESS_KEY", secret_key),
            ("R2_BUCKET", bucket),
        )
        if not val
    ]
    if missing:
        raise R2NotConfigured(f"missing R2 credentials: {', '.join(missing)}")
    return {
        "account_id": account_id,
        "access_key": access_key,
        "secret_key": secret_key,
        "bucket": bucket,
    }


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode(), date_stamp)
    k_region = _sign(k_date, REGION)
    k_service = _sign(k_region, SERVICE)
    return _sign(k_service, "aws4_request")


def _headers(
    method: str,
    creds: dict,
    body: Optional[bytes] = None,
    key: str = R2_KEY,
    query: str = "",
    payload_hash_override: Optional[str] = None,
) -> dict:
    """Build SigV4 headers for a request against the R2 S3-compatible endpoint.

    ``query`` must be the exact (URL-encoded, sorted) query string sent in the
    URL — callers pass pre-encoded queries (e.g. 'list-type=2').
    ``payload_hash_override`` lets streaming callers sign the body's SHA-256
    without holding the whole body in memory.
    """
    account_id = creds["account_id"]
    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    host = f"{account_id}.r2.cloudflarestorage.com"
    if payload_hash_override is not None:
        payload_hash = payload_hash_override
    else:
        payload_hash = hashlib.sha256(body if body is not None else b"").hexdigest()
    canonical_uri = f"/{creds['bucket']}/{key}" if key else f"/{creds['bucket']}"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    canonical_request = (
        f"{method}\n{canonical_uri}\n{query}\n{canonical_headers}\n"
        f"{signed_headers}\n{payload_hash}"
    )
    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{REGION}/{SERVICE}/aws4_request"
    string_to_sign = (
        f"{algorithm}\n{amz_date}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )
    signature = hmac.new(
        _signing_key(creds["secret_key"], date_stamp),
        string_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "Host": host,
        "X-Amz-Content-Sha256": payload_hash,
        "X-Amz-Date": amz_date,
        "Authorization": (
            f"{algorithm} Credential={creds['access_key']}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "User-Agent": "MandiIQ/r2-sync",
    }
    if method == "PUT":
        headers["Content-Type"] = "application/gzip"
    return headers


def _base_url(creds: dict) -> str:
    return f"https://{creds['account_id']}.r2.cloudflarestorage.com"


def remote_metadata(creds: dict) -> dict:
    """HEAD the R2 object; returns {} if it does not exist (404)."""
    url = f"{_base_url(creds)}/{creds['bucket']}/{R2_KEY}"
    req = urllib.request.Request(
        url,
        method="HEAD",
        headers=_headers("HEAD", creds),
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {
                "content_length": int(resp.headers.get("Content-Length", 0) or 0),
                "etag": resp.headers.get("ETag", "").strip('"'),
                "last_modified": resp.headers.get("Last-Modified", ""),
                "content_encoding": resp.headers.get("Content-Encoding", ""),
            }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise


def list_objects(creds: dict) -> list[dict]:
    """List object keys in the bucket (ListObjectsV2).

    NOTE: unpaginated — R2 caps at 1000 keys per page. Fine for a bucket that
    holds a handful of objects; add continuation handling if that ever grows.
    """
    import xml.etree.ElementTree as ET

    url = f"{_base_url(creds)}/{creds['bucket']}?list-type=2"
    req = urllib.request.Request(
        url,
        method="GET",
        headers=_headers("GET", creds, key="", query="list-type=2"),
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    objects = []
    for contents in root.findall("s3:Contents", ns):
        objects.append(
            {
                "key": contents.findtext("s3:Key", "", ns) or "",
                "size": int(contents.findtext("s3:Size", "0", ns) or 0),
                "last_modified": contents.findtext("s3:LastModified", "", ns) or "",
            }
        )
    return objects


def gzip_db(db_path: Path) -> tuple[bytes, int]:
    """Deterministic gzip of the DB file (mtime=0) — keeps --check md5 valid.

    In-memory (use ``_gzip_db_to_file`` for large DBs).
    """
    raw = db_path.read_bytes()
    return gzip.compress(raw, compresslevel=6, mtime=0), len(raw)


_MIN_UPLOAD_ROWS = 100_000
"""Clobber guard: refuse to upload a DB with fewer prices than this.

The Northflank cron runs volumeless on the free tier, so its ephemeral DB
starts empty/tiny; without this guard its post-ingest upload would overwrite
the ~1.3M-row R2 backup with a few thousand rows.
"""


def _file_sha256(path: Path) -> str:
    """Streaming SHA-256 of a file — flat memory for large DuckDBs."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


def _gzip_db_to_file(db_path: Path) -> Path:
    """Stream a deterministic gzip (mtime=0) of the DB into a temp file.

    Byte-identical to ``gzip_db``'s output (so --check md5 still matches the
    remote ETag) but never holds the raw DB in memory.
    """
    gz_path = db_path.with_suffix(".duckdb.gz.tmp")
    gz_path.unlink(missing_ok=True)
    with open(db_path, "rb") as fin, gzip.GzipFile(
        filename="", mode="wb", compresslevel=6, mtime=0, fileobj=open(gz_path, "wb")
    ) as gout:
        shutil.copyfileobj(fin, gout, length=1024 * 256)
    return gz_path


def _db_price_count(db_path: Path) -> int:
    """Open the DB read-only and return the prices row count (-1 on failure)."""
    try:
        import duckdb  # type: ignore

        chk = duckdb.connect(str(db_path), read_only=True)
        try:
            return int(chk.execute("SELECT COUNT(*) FROM prices").fetchone()[0])
        finally:
            chk.close()
    except Exception:
        return -1


def upload_db(db_path: Optional[Path] = None) -> dict:
    """Gzip the DuckDB and PUT it to R2 as mandi_iq.duckdb.gz (streamed).

    Refuses to upload a DB with fewer than ``_MIN_UPLOAD_ROWS`` prices so a
    volumeless cron that started from an empty DB can never clobber the good
    backup with its tiny post-ingest state.

    Raises FileNotFoundError / ValueError (clobber guard) /
    urllib.error.HTTPError (403 = read-only token, etc.) / R2NotConfigured.
    """
    from mandi_rdd.storage.duckdb_store import resolve_db_path

    # resolve_db_path(): on the volumeless cron, MANDIIQ_DB_PATH=/data/...
    # doesn't exist, so restore + ingest target the repo DB — upload the SAME
    # file the pipeline actually wrote, never the un-created env path.
    path = db_path or resolve_db_path()
    if not path.exists():
        raise FileNotFoundError(f"Database file not found: {path}")
    n_prices = _db_price_count(path)
    if n_prices < _MIN_UPLOAD_ROWS:
        raise ValueError(
            f"upload_db: refusing to upload — DB has {n_prices} prices "
            f"(< {_MIN_UPLOAD_ROWS}). Volumeless crons must restore from R2 "
            f"before ingesting so the backup never shrinks."
        )
    creds = get_creds()
    gz_path = _gzip_db_to_file(path)
    try:
        raw_size = path.stat().st_size
        compressed_bytes = gz_path.stat().st_size
        payload_hash = _file_sha256(gz_path)
        url = f"{_base_url(creds)}/{creds['bucket']}/{R2_KEY}"
        headers = _headers("PUT", creds, body=b"", payload_hash_override=payload_hash)
        headers["Content-Length"] = str(compressed_bytes)
        with open(gz_path, "rb") as fbody:
            req = urllib.request.Request(url, data=fbody, method="PUT", headers=headers)
            with urllib.request.urlopen(req, timeout=600) as resp:
                resp.read()
        return {
            "status": "ok",
            "r2_key": R2_KEY,
            "raw_bytes": raw_size,
            "compressed_bytes": compressed_bytes,
            "compression_pct": round(100 * (1 - compressed_bytes / raw_size), 1),
        }
    finally:
        gz_path.unlink(missing_ok=True)


def restore_db(db_path: Optional[Path] = None) -> dict:
    """Download the R2 backup and atomically replace the local DuckDB file.

    Fully streamed (download -> temp .gz file, then gzip -> temp .duckdb) so
    peak memory stays flat — a 152 MB gz / ~500 MB DB restore fits in a 256 MB
    container that the old in-memory ``gzip.decompress`` OOM-killed.

    Mirrors main.py's /admin/restore-from-r2 (temp file + rename). Used at API
    startup on a fresh/empty volume so the 1.3M-row DB is available instantly
    instead of re-ingesting from scratch.
    """
    from mandi_rdd.storage.duckdb_store import resolve_db_path

    path = db_path or resolve_db_path()
    creds = get_creds()
    gz_tmp = path.with_suffix(".duckdb.gz.tmp")
    tmp = path.with_suffix(".duckdb.tmp")
    bytes_downloaded = 0
    try:
        # 1) stream the gzipped backup to a temp file
        url = f"{_base_url(creds)}/{creds['bucket']}/{R2_KEY}"
        req = urllib.request.Request(url, method="GET", headers=_headers("GET", creds))
        with urllib.request.urlopen(req, timeout=600) as resp, open(gz_tmp, "wb") as out:
            shutil.copyfileobj(resp, out, length=1024 * 256)
        bytes_downloaded = gz_tmp.stat().st_size
        # 2) stream-decompress to the temp DuckDB
        with gzip.open(gz_tmp, "rb") as fin, open(tmp, "wb") as fout:
            shutil.copyfileobj(fin, fout, length=1024 * 256)
    except Exception as e:  # noqa: BLE001
        gz_tmp.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
        raise ValueError(f"R2 restore failed: {e}") from e
    # Sanity gate: never replace the volume DB with garbage. A corrupt,
    # truncated, or stale-LFS-pointer backup would brick the fresh volume
    # (init_schema + auto-pipeline would both fail on the broken file).
    try:
        import duckdb  # type: ignore

        chk = duckdb.connect(str(tmp), read_only=True)
        try:
            n = chk.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        finally:
            chk.close()
    except Exception as e:  # noqa: BLE001
        gz_tmp.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
        raise ValueError(f"R2 restore: downloaded backup is not a valid DuckDB (prices query failed): {e}") from e
    if not isinstance(n, int) or n <= 0:
        gz_tmp.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
        raise ValueError(f"R2 restore: backup has {n} prices — refusing to replace the DB.")
    decompressed_bytes = tmp.stat().st_size
    gz_tmp.unlink(missing_ok=True)
    tmp.replace(path)
    return {
        "status": "ok",
        "prices": n,
        "bytes_downloaded": bytes_downloaded,
        "bytes_decompressed": decompressed_bytes,
        "db_path": str(path),
    }
