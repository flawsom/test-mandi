"""Regression tests for the DuckDB path fallback.

Streamlit Community Cloud has no Northflank volume at /data, so a
MANDIIQ_DB_PATH like ``/data/mandi_iq.duckdb`` must NOT win over the
git-LFS-pulled repo DB (``mandi_rdd/data/mandi_iq.duckdb``). These tests pin
the priority implemented by ``resolve_db_path()``:

  1. The configured MANDIIQ_DB_PATH, if its file exists and is a real DB.
  2. The repo-default DB, if it exists and is a real DB.
  3. The configured path unchanged (so callers raise a clear error and the
     R2 bootstrap can try to create it).
"""

from pathlib import Path

import pytest

from mandi_rdd.storage import duckdb_store as store


def _write_real_db(path: Path) -> Path:
    """Write a fake-but-'real' DB file (> LFS pointer size)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 1024)  # real DuckDB files are > 200 bytes
    return path


def _write_lfs_pointer(path: Path) -> Path:
    """Write a file that looks like a Git LFS pointer (~100 bytes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n"
        "size 151000000\n"
    )
    return path


@pytest.fixture(autouse=True)
def _restore_paths():
    yield
    # Recompute from env like module import does, so tests don't leak state.
    import os

    store.DB_PATH = Path(
        os.environ.get(
            "MANDIIQ_DB_PATH",
            Path(__file__).resolve().parent.parent / "data" / "mandi_iq.duckdb",
        )
    )
    store.REPO_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mandi_iq.duckdb"


def test_configured_path_missing_falls_back_to_repo_db(monkeypatch, tmp_path):
    """MANDIIQ_DB_PATH=/data/... doesn't exist -> use repo DB."""
    missing = tmp_path / "data" / "mandi_iq.duckdb"  # not created
    repo_db = _write_real_db(tmp_path / "repo" / "mandi_iq.duckdb")
    monkeypatch.setattr(store, "DB_PATH", missing)
    monkeypatch.setattr(store, "REPO_DB_PATH", repo_db)

    assert store.resolve_db_path() == repo_db


def test_configured_path_is_lfs_pointer_falls_back_to_repo_db(monkeypatch, tmp_path):
    """MANDIIQ_DB_PATH is a stale LFS pointer -> use repo DB."""
    pointer = _write_lfs_pointer(tmp_path / "data" / "mandi_iq.duckdb")
    repo_db = _write_real_db(tmp_path / "repo" / "mandi_iq.duckdb")
    monkeypatch.setattr(store, "DB_PATH", pointer)
    monkeypatch.setattr(store, "REPO_DB_PATH", repo_db)

    assert store.resolve_db_path() == repo_db


def test_configured_real_db_wins(monkeypatch, tmp_path):
    """When MANDIIQ_DB_PATH exists and is a real DB, it wins."""
    configured = _write_real_db(tmp_path / "data" / "mandi_iq.duckdb")
    repo_db = _write_real_db(tmp_path / "repo" / "mandi_iq.duckdb")
    monkeypatch.setattr(store, "DB_PATH", configured)
    monkeypatch.setattr(store, "REPO_DB_PATH", repo_db)

    assert store.resolve_db_path() == configured


def test_neither_exists_returns_configured_path(monkeypatch, tmp_path):
    """No DB at all -> return the configured path (callers raise clearly)."""
    missing = tmp_path / "data" / "mandi_iq.duckdb"
    missing_repo = tmp_path / "repo" / "mandi_iq.duckdb"
    monkeypatch.setattr(store, "DB_PATH", missing)
    monkeypatch.setattr(store, "REPO_DB_PATH", missing_repo)

    assert store.resolve_db_path() == missing


def test_get_connection_uses_repo_db_when_configured_missing(monkeypatch, tmp_path):
    """End-to-end: get_connection() succeeds against the repo DB even when
    MANDIIQ_DB_PATH points at a non-existent /data volume."""
    import duckdb

    missing = tmp_path / "data" / "mandi_iq.duckdb"
    repo_db = tmp_path / "repo" / "mandi_iq.duckdb"
    repo_db.parent.mkdir(parents=True, exist_ok=True)
    # Create a REAL DuckDB file (a junk file would fail duckdb.connect).
    seed = duckdb.connect(str(repo_db))
    seed.execute("CREATE TABLE prices (id INTEGER)")
    seed.close()
    monkeypatch.setattr(store, "DB_PATH", missing)
    monkeypatch.setattr(store, "REPO_DB_PATH", repo_db)
    monkeypatch.setattr(store, "_bootstrap_db_from_r2", lambda: repo_db)

    conn = store.get_connection(read_only=True)
    try:
        result = conn.execute("SELECT COUNT(*) FROM prices").fetchone()
        assert result == (0,)
    finally:
        conn.close()
