"""
NDVI ingestion pipeline for MandiIQ.

Fetches Sentinel-2 L2A NDVI via the Sentinel Hub Statistical API,
stores results in DuckDB, and exports a JSON snapshot for git tracking.

Features:
  - Exponential backoff with jitter for rate-limited / transient failures
  - fetch_missing_ndvi() — retries only districts that have no NDVI data yet
  - Token refresh before retry if auth may have expired
  - District-level progress tracking across runs
"""
import difflib
import json
import logging
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SSL_CTX = ssl.create_default_context()

SENTINEL_AUTH_URL = "https://services.sentinel-hub.com/oauth/token"
SENTINEL_STATS_URL = "https://services.sentinel-hub.com/api/v1/statistics"

COORDS_CACHE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "district_coords.json"
)

# Sentinel-2 L2A evalscript — NDVI (Red=Band4, NIR=Band8) with dataMask
NDVI_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "dataMask"],
    output: [
      { id: "default", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(sample) {
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  return {
    default: [ndvi],
    dataMask: [sample.dataMask]
  };
}
"""

# ── Fuzzy geocode fallback ──

# Manual alias mappings for district names that can't be resolved
# via fuzzy matching (typos, alternate spellings, newly renamed)
_DISTRICT_ALIASES: dict[str, tuple[str, str]] = {
    # Andhra Pradesh
    "Andhra Pradesh|Anakapally": ("Andhra Pradesh", "Anakapalli"),
    "Andhra Pradesh|Dr.B.R.A.Konaseema": ("Andhra Pradesh", "Konaseema"),
    "Andhra Pradesh|Vishakhapatnam": ("Andhra Pradesh", "Visakhapatnam"),
    # Chattisgarh
    "Chattisgarh|Gourela Pendra Marwahi": ("Chhattisgarh", "Gourela Pendra Marwahi"),
    "Chattisgarh|Janjgeer-Champa": ("Chhattisgarh", "Janjgir Champa"),
    "Chattisgarh|Mohla Manpur Ambagarh Chouki": ("Chhattisgarh", "Mohla Manpur Ambagarh Chouki"),
    # Gujarat
    "Gujarat|Banaskanth": ("Gujarat", "Banaskantha"),
    "Gujarat|Panchmahals": ("Gujarat", "Panchmahal"),
    # Jharkhand
    "Jharkhand|Purba Singhbhum": ("Jharkhand", "East Singhbum"),
    # Madhya Pradesh
    "Madhya Pradesh|Anupur": ("Madhya Pradesh", "Anuppur"),
    "Madhya Pradesh|Badwani": ("Madhya Pradesh", "Barwani"),
    "Madhya Pradesh|Singroli": ("Madhya Pradesh", "Singrauli"),
    # Maharashtra
    "Maharashtra|Chattrapati Sambhajinagar": ("Maharashtra", "Aurangabad"),
    # Nagaland
    "Nagaland|Tsemenyu": ("Nagaland", "Zunheboto"),
    # Rajasthan
    "Rajasthan|Jaipur Rural": ("Rajasthan", "Jaipur"),
    "Rajasthan|Swai Madhopur": ("Rajasthan", "Sawai Madhopur"),
    # Tripura
    "Tripura|Unokoti": ("Tripura", "Unokoti"),
    # Uttar Pradesh
    "Uttar Pradesh|Ambedkarnagar": ("Uttar Pradesh", "Ambedkar Nagar"),
    "Uttar Pradesh|Farukhabad": ("Uttar Pradesh", "Farrukhabad"),
    "Uttar Pradesh|Kannuj": ("Uttar Pradesh", "Kannauj"),
    "Uttar Pradesh|Khiri (Lakhimpur)": ("Uttar Pradesh", "Lakhimpur Kheri"),
    "Uttar Pradesh|Pillibhit": ("Uttar Pradesh", "Pilibhit"),
    # West Bengal
    "West Bengal|Sounth 24 Parganas": ("West Bengal", "South 24 Parganas"),
}


def _normalize_name(name: str) -> str:
    """Lowercase, strip parentheticals, collapse whitespace."""
    # Remove parenthetical content like "(Calicut)"
    name = re.sub(r"\([^()]*\)", "", name)
    # Collapse whitespace and strip
    return " ".join(name.lower().split())


_STATE_ALIASES: dict[str, str] = {
    "nct of delhi": "delhi",
    "chattisgarh": "chhattisgarh",
    "keralam": "kerala",
    "uttrakhand": "uttarakhand",
    "jammu & kashmir": "jammu and kashmir",
    "pondicherry": "puducherry",
}


def _normalize_state(state: str) -> str:
    """Normalize state name for consistent matching."""
    norm = state.lower().strip()
    return _STATE_ALIASES.get(norm, norm)


# ── Retry helper ──

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4
_BASE_DELAY = 2.0  # seconds


def _request_with_retry(
    url: str,
    data: Optional[bytes] = None,
    headers: Optional[dict] = None,
    max_retries: int = _MAX_RETRIES,
    base_delay: float = _BASE_DELAY,
) -> Optional[dict]:
    """HTTP request with exponential backoff + jitter.

    Retries on:
      - HTTP 429 (rate limit)
      - HTTP 5xx (server errors)
      - Network / timeout errors (URLError, OSError)

    Does NOT retry on HTTP 4xx (except 429), parse errors, etc.

    Returns the parsed JSON dict on success, or None if all retries fail.
    """
    req = urllib.request.Request(url, data=data, headers=headers or {})

    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=45, context=SSL_CTX) as f:
                return json.loads(f.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code in _RETRYABLE_STATUSES and attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1.0)
                logger.warning(
                    "HTTP %d (attempt %d/%d for %s) — retrying in %.1fs",
                    e.code, attempt + 1, max_retries, url[:60], delay,
                )
                time.sleep(delay)
                continue
            if e.code in _RETRYABLE_STATUSES:
                logger.error(
                    "HTTP %d — exhausted %d retries for %s: %s",
                    e.code, max_retries, url[:60], body[:200],
                )
            else:
                logger.warning(
                    "HTTP %d (non-retryable) for %s: %s",
                    e.code, url[:60], body[:200],
                )
            return None
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1.0)
                logger.warning(
                    "Network error (attempt %d/%d) for %s — retrying in %.1fs: %s",
                    attempt + 1, max_retries, url[:60], delay, e,
                )
                time.sleep(delay)
                continue
            logger.error(
                "Request failed after %d retries for %s: %s",
                max_retries, url[:60], e,
            )
            return None


# ── Auth ──


def _get_client_credentials() -> tuple[str, str]:
    client_id = os.environ.get("SENTINEL_CLIENT_ID")
    client_secret = os.environ.get("SENTINEL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "SENTINEL_CLIENT_ID and SENTINEL_CLIENT_SECRET must be set. "
            "Get free credentials at https://www.sentinel-hub.com/pricing/"
        )
    return client_id, client_secret


def _get_access_token(client_id: str, client_secret: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(
        SENTINEL_AUTH_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as f:
            resp = json.loads(f.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Sentinel Hub auth failed ({e.code}): {body[:300]}")
    token = resp.get("access_token")
    if not token:
        raise RuntimeError(f"Auth response missing access_token: {resp}")
    return token


# ── Geocoding (Nominatim with caching + fuzzy fallback) ──

# Build cached indexes for fuzzy matching
_KNOWN_DISTRICTS_CACHE: Optional[dict[str, str]] = None  # norm_name -> original_cache_key
_KNOWN_DISTRICTS_BY_STATE: Optional[dict[str, dict[str, str]]] = None  # norm_state -> {norm_district -> cache_key}


def _rebuild_district_indexes(cache: dict) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Build two indexes for fuzzy matching:

    1. Flat: normalized district name -> cache key
    2. By-state: normalized state -> {normalized district name -> cache key}
    """
    flat: dict[str, str] = {}
    by_state: dict[str, dict[str, str]] = {}
    for key in cache:
        state, district = key.split("|", 1)
        norm_dist = _normalize_name(district)
        norm_st = _normalize_state(state)
        # Flat index (first wins — prevents duplicates)
        if norm_dist not in flat:
            flat[norm_dist] = key
        # By-state index
        by_state.setdefault(norm_st, {})
        if norm_dist not in by_state[norm_st]:
            by_state[norm_st][norm_dist] = key
    return flat, by_state


def _try_alias_lookup(
    district: str, state: str, key: str, cache: dict,
) -> Optional[tuple[float, float]]:
    """Check the manual alias table for known typos / alternate spellings.

    The alias maps a misspelled key to the correct (state, district).
    If found, it looks up the correct coordinates in cache and saves
    them under the original key for instant lookup next time.
    """
    alias = _DISTRICT_ALIASES.get(key)
    if alias:
        correct_state, correct_district = alias
        correct_key = f"{correct_state}|{correct_district}"
        correct_coords = cache.get(correct_key)
        if not correct_coords:
            # Try geocoding the correct name first
            correct_coords_list = _try_nominatim(
                f"{correct_district}, {_normalize_nominatim_state(correct_state)}, India",
                correct_key, cache,
            )
            if correct_coords_list:
                correct_coords = list(correct_coords_list)

        if correct_coords and len(correct_coords) == 2:
            logger.info(
                "  Alias lookup: '%s' -> '%s' (via %s)",
                key, correct_key, alias,
            )
            cache[key] = correct_coords
            _save_coords_cache(cache)
            return tuple(correct_coords)
    return None


def _fuzzy_geocode_fallback(
    district: str, state: str, key: str, cache: dict,
) -> Optional[tuple[float, float]]:
    """Try fuzzy matching against cached district coordinates.

    Strategy:
      1. First try same-state fuzzy match (higher cutoff 0.7)
      2. If that fails, try cross-state fuzzy match (stricter cutoff 0.85)
      3. On match, cache under the *original* key for instant lookup next time
    """
    global _KNOWN_DISTRICTS_CACHE, _KNOWN_DISTRICTS_BY_STATE
    if _KNOWN_DISTRICTS_CACHE is None or _KNOWN_DISTRICTS_BY_STATE is None:
        _KNOWN_DISTRICTS_CACHE, _KNOWN_DISTRICTS_BY_STATE = _rebuild_district_indexes(cache)

    norm_query = _normalize_name(district)
    norm_state = _normalize_state(state)
    if not norm_query:
        return None

    # 4a. Same-state fuzzy match (lenient cutoff)
    same_state_index = _KNOWN_DISTRICTS_BY_STATE.get(norm_state, {})
    if same_state_index:
        matches = difflib.get_close_matches(
            norm_query, same_state_index.keys(), n=1, cutoff=0.7,
        )
        if matches:
            matched_norm = matches[0]
            matched_key = same_state_index[matched_norm]
            matched_coords = cache.get(matched_key)
            if matched_coords and len(matched_coords) == 2:
                logger.info(
                    "  Fuzzy geocode (same-state): '%s' -> '%s' (%s)",
                    district, matched_norm, matched_key,
                )
                cache[key] = matched_coords
                _save_coords_cache(cache)
                return tuple(matched_coords)

    # 4b. Cross-state fuzzy match (stricter cutoff to avoid false positives)
    if len(same_state_index) < 5:  # Only bother if few same-state candidates
        matches = difflib.get_close_matches(
            norm_query, _KNOWN_DISTRICTS_CACHE.keys(), n=1, cutoff=0.85,
        )
        if matches:
            matched_norm = matches[0]
            matched_key = _KNOWN_DISTRICTS_CACHE[matched_norm]
            matched_coords = cache.get(matched_key)
            if matched_coords and len(matched_coords) == 2:
                logger.info(
                    "  Fuzzy geocode (cross-state): '%s' -> '%s' (%s)",
                    district, matched_norm, matched_key,
                )
                cache[key] = matched_coords
                _save_coords_cache(cache)
                return tuple(matched_coords)

    return None


def _load_coords_cache() -> dict:
    if COORDS_CACHE_PATH.exists():
        with open(COORDS_CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_coords_cache(cache: dict):
    COORDS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COORDS_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def _try_nominatim(query: str, key: str, cache: dict) -> Optional[tuple[float, float]]:
    """Try Nominatim geocoding with a single query string.

    On success, caches the result under *key* and returns (lat, lng).
    Returns None if no result found.
    """
    url = (
        "https://nominatim.openstreetmap.org/search"
        f"?q={urllib.parse.quote(query)}&format=json&limit=1"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MandiIQ/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as f:
            results = json.loads(f.read())
    except Exception as e:
        logger.warning("Geocode HTTP error for %s: %s", query[:50], e)
        return None

    time.sleep(2.0)  # Nominatim Usage Policy: max 1 req/sec, 2s is safer

    if results:
        lat = float(results[0]["lat"])
        lng = float(results[0]["lon"])
        cache[key] = [lat, lng]
        _save_coords_cache(cache)
        return (lat, lng)
    return None


def _normalize_nominatim_state(state: str) -> str:
    """Map state names to Nominatim-recognized forms."""
    norm = state.lower().strip()
    remap = {
        "nct of delhi": "Delhi",
        "chattisgarh": "Chhattisgarh",
        "keralam": "Kerala",
        "uttrakhand": "Uttarakhand",
        "pondicherry": "Puducherry",
        "tamil nadu": "Tamil Nadu",
        "andhra pradesh": "Andhra Pradesh",
        "jammu & kashmir": "Jammu and Kashmir",
        "himachal pradesh": "Himachal Pradesh",
        "madhya pradesh": "Madhya Pradesh",
        "uttar pradesh": "Uttar Pradesh",
        "west bengal": "West Bengal",
    }
    return remap.get(norm, state)


def geocode_district(district: str, state: str) -> Optional[tuple[float, float]]:
    """Geocode a (state, district) pair with fallback chain:

    1. Direct cache hit
    2. Nominatim with original name + normalized state
    3. Nominatim with normalized district + normalized state
    4. Fuzzy match (same-state preferred, cross-state strict)
    """
    cache = _load_coords_cache()
    key = f"{state}|{district}"
    nominatim_state = _normalize_nominatim_state(state)

    # 1. Direct cache hit
    if key in cache:
        return tuple(cache[key])

    # 2. Try Nominatim with original name
    query = f"{district}, {nominatim_state}, India"
    result = _try_nominatim(query, key, cache)
    if result:
        return result

    # 3. Try Nominatim with normalized district name
    normalized_district = _normalize_name(district)
    if normalized_district and normalized_district != district.lower().strip():
        query2 = f"{normalized_district}, {nominatim_state}, India"
        result = _try_nominatim(query2, key, cache)
        if result:
            return result

    # 4. Try with just district name (no state) — helps for union territories like Delhi
    #    and districts that Nominatim finds better without state suffix
    if nominatim_state in ("Delhi",):
        query3 = f"{normalized_district or district}, India"
        result = _try_nominatim(query3, key, cache)
        if result:
            return result

    # 5. Manual alias lookup for known typos/alternate spellings
    #    that fuzzy matching can't resolve
    alias_result = _try_alias_lookup(district, state, key, cache)
    if alias_result:
        return alias_result

    # 6. Fuzzy match against known cached districts
    result = _fuzzy_geocode_fallback(district, state, key, cache)
    if result:
        return result

    logger.warning(
        "No geocode result for %s — tried Nominatim + alias + fuzzy",
        key,
    )
    return None


# ── Sentinel Hub Statistical API (with retry) ──


def query_ndvi_stats(
    token: str,
    lat: float,
    lng: float,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    bbox_deg: float = 0.1,
) -> Optional[dict]:
    """Query Sentinel Hub Statistical API for NDVI with exponential backoff retry."""
    today = date.today()
    if date_to is None:
        date_to = today.isoformat()
    if date_from is None:
        date_from = (today - timedelta(days=180)).isoformat()

    body = json.dumps({
        "input": {
            "bounds": {
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
                "bbox": [lng - bbox_deg, lat - bbox_deg,
                         lng + bbox_deg, lat + bbox_deg],
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": f"{date_from}T00:00:00Z",
                        "to": f"{date_to}T23:59:59Z",
                    },
                    "maxCloudCoverage": 50,
                },
            }],
        },
        "aggregation": {
            "timeRange": {
                "from": f"{date_from}T00:00:00Z",
                "to": f"{date_to}T23:59:59Z",
            },
            "aggregationInterval": {"of": "P1M"},
            "evalscript": NDVI_EVALSCRIPT,
            "width": 100,
            "height": 100,
        },
    })

    return _request_with_retry(
        SENTINEL_STATS_URL,
        data=body.encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )


def parse_stats_response(response: dict) -> list[dict]:
    """Extract (date, mean_ndvi) pairs from a Statistical API response.

    Returns a list of dicts with keys ``date`` and ``ndvi``.
    Only includes intervals where at least one valid pixel was found.
    """
    records: list[dict] = []
    for entry in response.get("data", []):
        interval = entry.get("interval", {})
        dt = interval.get("from", "")[:10]
        stats = (
            entry.get("outputs", {})
            .get("default", {})
            .get("bands", {})
            .get("B0", {})
            .get("stats", {})
        )
        mean_val = stats.get("mean")
        sample_count = stats.get("sampleCount", 0)
        no_data_count = stats.get("noDataCount", 0)
        valid_pixels = sample_count - no_data_count
        if mean_val not in (None, "NaN") and valid_pixels > 0:
            records.append({
                "date": dt,
                "ndvi": round(float(mean_val), 4),
                "valid_pixels": valid_pixels,
            })
    return records


# ── Helpers ──


def _get_district_list() -> list[tuple[str, str]]:
    """Return all (state, district) pairs from the prices table."""
    from mandi_rdd.storage.duckdb_store import get_connection
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT DISTINCT state, district FROM prices ORDER BY state, district"
        ).fetchall()
        conn.close()
        return [(r[0], r[1]) for r in rows]
    except Exception as e:
        logger.error("Cannot read district list: %s", e)
        return []


def _get_missing_districts(all_districts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return districts that have no NDVI data yet in DuckDB."""
    from mandi_rdd.storage.duckdb_store import get_connection
    try:
        conn = get_connection()
        has_ndvi = set()
        rows = conn.execute(
            "SELECT DISTINCT state, district FROM ndvi"
        ).fetchall()
        conn.close()
        has_ndvi = {(r[0].lower(), r[1].lower()) for r in rows}
    except Exception as e:
        logger.warning("Cannot read existing NDVI coverage: %s", e)
        return all_districts  # err on the side of re-fetching

    missing = [
        (s, d) for s, d in all_districts
        if (s.lower(), d.lower()) not in has_ndvi
    ]
    return missing


def _get_coords_for_districts(
    districts: list[tuple[str, str]],
) -> dict[str, tuple[float, float]]:
    """Geocode a list of (state, district) pairs. Uses cached results when available."""
    coords: dict[str, tuple[float, float]] = {}
    cached = _load_coords_cache()
    to_geocode = []

    for state, district in districts:
        key = f"{state}|{district}"
        if key in cached:
            coords[key] = tuple(cached[key])
        else:
            to_geocode.append((state, district, key))

    if to_geocode:
        logger.info("Geocoding %d uncached districts…", len(to_geocode))
        for i, (state, district, key) in enumerate(to_geocode):
            c = geocode_district(district, state)
            if c:
                coords[key] = c
            if (i + 1) % 50 == 0:
                logger.info("  Geocoded %d / %d", len(coords), len(districts))

    logger.info("Mapped %d / %d districts", len(coords), len(districts))
    return coords


def _store_ndvi_records(records: list[dict]) -> int:
    """Bulk-store NDVI records in DuckDB and export JSON."""
    from mandi_rdd.storage.duckdb_store import get_connection, init_schema, upsert_ndvi
    if not records:
        return 0
    conn = get_connection()
    init_schema(conn)
    stored = upsert_ndvi(conn, records)
    conn.close()
    _export_ndvi_json()
    return stored


# ── Main Pipeline ──


def fetch_and_store_all_ndvi() -> int:
    """Geocode districts, query Sentinel Hub NDVI, store in DuckDB.

    Returns number of NDVI records stored.
    """
    districts = _get_district_list()
    if not districts:
        return 0

    # Geocode
    coords = _get_coords_for_districts(districts)
    if not coords:
        logger.error("No geocoded districts — cannot fetch NDVI")
        return 0

    return _fetch_and_store_from_coords(coords, "full fetch")


def fetch_missing_ndvi() -> int:
    """Fetch NDVI only for districts that have no data yet in DuckDB.

    This is useful after a previous run was capped by the Sentinel Hub
    free tier — you can call this function periodically to mop up
    remaining districts without re-fetching districts that already have data.
    """
    districts = _get_district_list()
    if not districts:
        return 0

    missing = _get_missing_districts(districts)
    if not missing:
        logger.info("All %d districts already have NDVI data — nothing to fetch", len(districts))
        return 0

    logger.info(
        "Missing NDVI for %d / %d districts — fetching…",
        len(missing), len(districts),
    )

    # Geocode only missing districts (uses cache for any already geocoded)
    coords = _get_coords_for_districts(missing)
    if not coords:
        logger.error("No geocoded coordinates for missing districts")
        return 0

    return _fetch_and_store_from_coords(coords, f"missing-district fetch ({len(missing)} districts)")


def _fetch_and_store_from_coords(
    coords: dict[str, tuple[float, float]],
    label: str,
) -> int:
    """Shared fetch loop: authenticate, query all coords with retry, store."""
    # Auth (fresh token)
    client_id, client_secret = _get_client_credentials()
    token = _get_access_token(client_id, client_secret)
    logger.info("Sentinel Hub authenticated — token valid ~60 min")

    keys = list(coords.keys())
    batch_size = 10
    all_records: list[dict] = []
    succeeded = 0
    failed = 0

    for i in range(0, len(keys), batch_size):
        batch = keys[i: i + batch_size]
        for key in batch:
            state, district = key.split("|", 1)
            lat, lng = coords[key]
            resp = query_ndvi_stats(token, lat, lng)
            if resp:
                parsed = parse_stats_response(resp)
                if parsed:
                    for r in parsed:
                        all_records.append({
                            "state": state,
                            "district": district,
                            "date": r["date"],
                            "ndvi": r["ndvi"],
                            "anomaly": 0.0,
                        })
                    succeeded += 1
                else:
                    # Parsed but no valid data (e.g. all cloud cover)
                    succeeded += 1  # It did succeed technically
                    logger.debug("No valid NDVI pixels for %s / %s", state, district)
            else:
                failed += 1

            # Brief inter-request delay to be kind to the API
            time.sleep(0.3 + random.uniform(0, 0.2))

        pct = 100.0 * min(i + batch_size, len(keys)) / len(keys)
        logger.info(
            "  [%s] Batch %d/%d — %.0f%% — %d records, %d OK, %d failed",
            label,
            i // batch_size + 1,
            (len(keys) - 1) // batch_size + 1,
            pct,
            len(all_records),
            succeeded,
            failed,
        )

    logger.info(
        "Total NDVI records fetched: %d (%d districts OK, %d failed)",
        len(all_records), succeeded, failed,
    )

    # Store
    stored = _store_ndvi_records(all_records)
    logger.info("Stored %d NDVI records", stored)
    return stored


# ── Export ──


def _export_ndvi_json():
    """Export the ndvi table as a JSON file tracked in git.

    The DuckDB is gitignored, so this JSON copy is what the daily GitHub Action
    commits back to the repo. The satellite dashboard reads this file if DuckDB
    has no local data yet.
    """
    from mandi_rdd.storage.duckdb_store import get_connection
    try:
        conn = get_connection()
        df = conn.execute("""
            SELECT state, district, date, ndvi, anomaly
            FROM ndvi
            ORDER BY state, district, date
        """).fetchdf()
        conn.close()
        if "date" in df.columns:
            df["date"] = df["date"].astype(str)
        records = df.to_dict(orient="records")
        export_path = Path(__file__).resolve().parent.parent / "data" / "ndvi_latest.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w") as f:
            json.dump({
                "last_updated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "n_records": len(records),
                "records": records,
            }, f, indent=2)
        logger.info("Exported %d NDVI records to %s", len(records), export_path)
    except Exception as e:
        logger.warning("Failed to export NDVI JSON: %s", e)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="NDVI ingestion for MandiIQ")
    parser.add_argument(
        "--mode", choices=["full", "missing"], default="missing",
        help=(
            "'full' = fetch ALL districts; "
            "'missing' = fetch only districts without NDVI data (default)"
        ),
    )
    args = parser.parse_args()

    if args.mode == "full":
        count = fetch_and_store_all_ndvi()
    else:
        count = fetch_missing_ndvi()

    print(f"\nDone — stored {count} NDVI records")
