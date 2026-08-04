"""
Integration test for the backfill lifecycle.

Creates a temp DuckDB with the full prices schema, inserts rows with empty
state, runs backfill(dry_run=False), and verifies:
  1. Districts from MANUAL_OVERRIDES are populated correctly
  2. Rows with existing state are NOT overwritten
  3. The STATE_ALIASES canonicalization normalizes aliased state names
  4. Districts not in the lookup remain unchanged
  5. The idx_prices_state index still exists after the DROP -> UPDATE -> CREATE cycle
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def _imports():
    """Import backfill modules once, skipping if dependencies missing."""
    try:
        import duckdb  # noqa: F401
    except ImportError:
        pytest.skip("duckdb not installed")
    from mandi_rdd.storage.duckdb_store import init_schema
    from mandi_rdd.ingestion.backfill_state import build_lookup, backfill
    return init_schema, build_lookup, backfill


def test_backfill_lifecycle(tmp_path, monkeypatch, _imports):
    init_schema, build_lookup, backfill = _imports

    # -- 1. Set up temp DuckDB --
    import duckdb

    db_path = tmp_path / "test_mandi_iq.duckdb"
    conn = duckdb.connect(str(db_path))

    # Create the full schema (tables + indexes).
    # Note: prices.state is VARCHAR NOT NULL, so we use empty string ''
    # to represent "missing state", not SQL NULL.
    init_schema(conn)

    # -- 2. Insert test rows --
    # 2 districts from MANUAL_OVERRIDES with empty state (should be backfilled)
    # 1 row with state already populated (should NOT be overwritten)
    # 1 row with a STATE_ALIAS state value (should be canonicalized)
    # 1 district not in any lookup (should remain empty)
    conn.execute("""
        INSERT INTO prices
            (state, district, market, commodity, variety, grade,
             arrival_date, modal_price)
        VALUES
            ('',                  'Ambala',    'Market A', 'Onion', 'Red', 'FAQ', '2024-01-15', 1500),
            ('',                  'Amritsar',  'Market B', 'Tomato', NULL,  NULL,  '2024-01-16', 2000),
            ('Maharashtra',       'Pune',      'Market D', 'Onion',  'Red', 'FAQ', '2024-01-18', 1800),
            ('jammu and kashmir', 'Srinagar',  'Market E', 'Apple',  NULL,  NULL,  '2024-01-19', 5000),
            ('',                  'XMissing',  'Market F', 'Wheat',  NULL,  NULL,  '2024-01-20', 2000)
    """)
    conn.commit()

    # Confirm the index exists before backfill
    before = conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE index_name = 'idx_prices_state'"
    ).fetchall()
    assert len(before) == 1, "idx_prices_state should exist before backfill"

    # Confirm rows are in expected initial state
    pre = conn.execute(
        "SELECT district, state FROM prices ORDER BY district"
    ).fetchall()
    assert len(pre) == 5
    empty_states = [r for r in pre if r[1] is None or r[1] == '']
    assert len(empty_states) == 3  # Ambala, Amritsar, XMissing
    conn.close()

    # -- 3. Build lookup (coords + MANUAL_OVERRIDES, no Ashoka) --
    lookup = build_lookup(use_ashoka=False)

    # -- 4. Monkeypatch get_connection in backfill_state to use temp DB --
    def mock_get_connection(read_only=False):
        return duckdb.connect(str(db_path), read_only=read_only)

    monkeypatch.setattr(
        'mandi_rdd.ingestion.backfill_state.get_connection',
        mock_get_connection,
    )

    # -- 5. Run backfill with real writes --
    matched = backfill(lookup, dry_run=False)

    # -- 6. Assert results --
    conn = duckdb.connect(str(db_path))

    # Ambala -> Haryana (from MANUAL_OVERRIDES)
    row = conn.execute(
        "SELECT state FROM prices WHERE district = 'Ambala'"
    ).fetchone()
    assert row is not None
    assert row[0] == 'Haryana', f"Ambala expected 'Haryana', got {row[0]}"

    # Amritsar -> Punjab (from MANUAL_OVERRIDES)
    row = conn.execute(
        "SELECT state FROM prices WHERE district = 'Amritsar'"
    ).fetchone()
    assert row is not None
    assert row[0] == 'Punjab', f"Amritsar expected 'Punjab', got {row[0]}"

    # Pune (already 'Maharashtra') should NOT be overwritten
    row = conn.execute(
        "SELECT state FROM prices WHERE district = 'Pune'"
    ).fetchone()
    assert row is not None
    assert row[0] == 'Maharashtra', f"Pune expected 'Maharashtra', got {row[0]}"

    # Srinagar state 'jammu and kashmir' -> canonicalized to 'Jammu & Kashmir'
    # by the STATE_ALIASES loop, not by the per-district backfill (which only
    # touches empty-state rows).
    row = conn.execute(
        "SELECT state FROM prices WHERE district = 'Srinagar'"
    ).fetchone()
    assert row is not None
    assert row[0] == 'Jammu & Kashmir', f"Srinagar expected 'Jammu & Kashmir', got {row[0]}"

    # XMissing (not in lookup) should remain empty string
    row = conn.execute(
        "SELECT state FROM prices WHERE district = 'XMissing'"
    ).fetchone()
    assert row is not None
    assert row[0] == '', f"XMissing expected empty string, got {row[0]!r}"

    # -- 7. Verify idx_prices_state index still exists --
    indexes = conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE index_name = 'idx_prices_state'"
    ).fetchall()
    assert len(indexes) == 1, (
        f"idx_prices_state index missing after backfill. "
        f"Found indexes: {[r[0] for r in conn.execute('SELECT index_name FROM duckdb_indexes()').fetchall()]}"
    )

    conn.close()

    # matched should cover Ambala + Amritsar (= 2)
    assert matched >= 2, f"Expected >= 2 districts matched, got {matched}"
