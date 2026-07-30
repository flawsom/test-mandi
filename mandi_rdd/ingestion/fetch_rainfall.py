"""
MandiRDD — rainfall departure data fetcher.

Primary source: Open-Meteo (free, no API key) — fetches daily precipitation
for representative districts, aggregates to monthly sub-division totals,
computes departure from normal using rolling climatology.

Fallbacks: data.gov.in rainfall resources (require ALL_INDIA_RAINFALL_API_KEY),
then Datameet GitHub CSV (stale/404, kept for backward compat).

The rainfall data is joined with mandi prices on
(district ~ sub_division, year, month) to create the running variable
for the RDD: monthly rainfall departure from normal (%).
"""

import json
import os
import re
import csv
import io
import time
import urllib.parse
import urllib.request
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from mandi_rdd.ingestion.http_client import (
    safe_float,
    get_api_key,
    http_get,
    http_get_json,
    http_get_text,
    SSL_CTX,
)

logger = logging.getLogger(__name__)


# ── Open-Meteo (free, no API key needed) ─────────────────────────────
# Primary rainfall data source. Returns daily precipitation for any
# coordinate. Free for non-commercial use, no registration required.
OPEN_METEO_BASE = "https://archive-api.open-meteo.com/v1/archive"
# Number of years of historical data to fetch for normal computation
OPEN_METEO_YEARS = 5

# data.gov.in resource IDs to try (rainfall-related)
# These exist on the platform but most have no actual data rows.
RAINFALL_CANDIDATE_IDS = [
    "9b915b52-b840-4b4b-9f9f-8d6e7c0e1a2b",
    "a4b2e5f6-c7d8-9012-3456-7890abcdef12",
]

# Deprecated — Datameet rainfall repo has been restructured.
FALLBACK_CSV_URL = "https://raw.githubusercontent.com/datameet/rainfall/master/data/rainfall_monthly_subdivisions.csv"

# ── API key helpers ────────────────────────────────────────────────────

def _get_rainfall_api_key() -> str | None:
    """Resolve the API key for rainfall-specific data.gov.in resources.

    Checks ALL_INDIA_RAINFALL_API_KEY first (rainfall-specific), then
    falls back to DATA_GOV_IN_API_KEY (general-purpose).
    """
    key = os.environ.get("ALL_INDIA_RAINFALL_API_KEY")
    if key:
        return key
    key = get_api_key("DATA_GOV_IN_API_KEY")
    if key:
        return key
    # Try .env as last resort
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    return os.environ.get("ALL_INDIA_RAINFALL_API_KEY") or os.environ.get("DATA_GOV_IN_API_KEY")


def _load_district_coords() -> dict:
    """Load the district coordinates JSON from the project data folder.

    Returns dict with "State|District" keys and [lat, lon] values,
    or empty dict if the file cannot be loaded.
    """
    # Look relative to this file: ../../data/district_coords.json
    path = Path(__file__).resolve().parent.parent.parent / "data" / "district_coords.json"
    try:
        with open(path) as f:
            coords = json.load(f)
        logger.info(f"Loaded {len(coords)} district coordinates from {path.name}")
        return coords
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Cannot load district coordinates: {e}")
        return {}


def fetch_rainfall_from_open_meteo() -> list[dict]:
    """Fetch historical monthly rainfall from Open-Meteo (free, no API key).

    Strategy:
    1. Load district → sub-division mapping and coordinates
    2. Pick one representative district per sub-division
    3. Fetch ~5 years of daily precipitation for each representative
    4. Aggregate to monthly totals
    5. Compute "normal" as the multi-year monthly average
    6. Compute departure_pct = ((actual - normal) / normal) * 100

    Returns list of {sub_division, year, month, rainfall_mm, normal_mm, departure_pct}.
    Returns [] on any failure (callers must handle gracefully).
    """
    dmap = load_district_subdivision_map()
    coords = _load_district_coords()
    if not coords or not dmap:
        logger.warning("Missing district mapping or coordinates — cannot use Open-Meteo")
        return []

    # Build state|district keys (same format as coords dict)
    # coords keys: "State|District" (with possible trailing space)
    state_district_to_subdiv = {}
    for (state, district), subdiv in dmap.items():
        # Try exact match
        key = f"{state}|{district}"
        state_district_to_subdiv[key.lower()] = subdiv
        # Also try with the key format from coords (which may have different casing)
        for coord_key in coords:
            parts = coord_key.split("|")
            if len(parts) == 2:
                cs, cd = parts[0].strip(), parts[1].strip()
                if cs.lower() == state.lower() and cd.lower() == district.lower():
                    state_district_to_subdiv[coord_key.strip().lower()] = subdiv

    # Pick one representative district per sub-division
    subdiv_reps: dict[str, tuple[str, float, float]] = {}  # subdiv -> (coord_key, lat, lon)
    for coord_key, (lat, lon) in coords.items():
        key_normalized = coord_key.strip().lower()
        subdiv = state_district_to_subdiv.get(key_normalized)
        if subdiv and subdiv not in subdiv_reps:
            subdiv_reps[subdiv] = (coord_key, lat, lon)

    if not subdiv_reps:
        logger.warning("No district→sub-division coordinate mappings found")
        return []

    logger.info(f"Open-Meteo: fetching rainfall for {len(subdiv_reps)} sub-divisions...")

    # Date range: last N years
    today = date.today()
    from datetime import timedelta
    # Open-Meteo archive is typically 1-2 days behind real-time
    end_date = today - timedelta(days=2)
    start_date = date(today.year - OPEN_METEO_YEARS, 1, 1)

    # Collect daily data per sub-division
    subdiv_daily: dict[str, list[dict]] = {}
    failures = 0
    for subdiv, (coord_key, lat, lon) in sorted(subdiv_reps.items()):
        time.sleep(0.2)
        url = (
            f"{OPEN_METEO_BASE}"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={start_date.isoformat()}"
            f"&end_date={end_date.isoformat()}"
            f"&daily=precipitation_sum"
            f"&timezone=Asia%2FKolkata"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MandiIQ/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())

            daily = data.get("daily", {})
            times = daily.get("time", [])
            precip = daily.get("precipitation_sum", [])

            rows = []
            for t, p in zip(times, precip):
                if p is not None:
                    rows.append({"date": t, "precip_mm": float(p)})
            if rows:
                subdiv_daily[subdiv] = rows
            logger.debug(f"  {subdiv}: {len(rows)} daily records (lat={lat:.2f}, lon={lon:.2f})")
        except Exception as e:
            failures += 1
            logger.debug(f"  {subdiv}: Open-Meteo fetch failed: {e}")
            continue

    if not subdiv_daily:
        logger.warning("Open-Meteo: no data returned for any sub-division")
        return []

    logger.info(f"Open-Meteo: got data for {len(subdiv_daily)}/{len(subdiv_reps)} sub-divisions "
                f"({failures} failures)")

    # Aggregate daily → monthly per sub-division
    # subdiv_monthly[(subdiv, year, month)] = list of precip values
    monthly_groups: dict = {}
    for subdiv, rows in subdiv_daily.items():
        for r in rows:
            try:
                d = date.fromisoformat(r["date"])
                key = (subdiv, d.year, d.month)
                monthly_groups.setdefault(key, []).append(r["precip_mm"])
            except (ValueError, TypeError):
                continue

    # Compute monthly totals and monthly climatology
    monthly_totals: dict = {}  # (subdiv, year, month) -> total_mm
    climato: dict = {}         # (subdiv, month) -> list of totals across years

    for (subdiv, yr, mo), vals in monthly_groups.items():
        total_mm = sum(vals)
        monthly_totals[(subdiv, yr, mo)] = total_mm
        climato.setdefault((subdiv, mo), []).append(total_mm)

    # Compute normal as mean across years for each (subdiv, month)
    normal: dict = {}
    for (subdiv, mo), totals in climato.items():
        normal[(subdiv, mo)] = sum(totals) / len(totals) if totals else 0.0

    # Build output records
    records = []
    for (subdiv, yr, mo), total_mm in monthly_totals.items():
        nrm = normal.get((subdiv, mo), 0.0)
        departure = ((total_mm - nrm) / nrm * 100.0) if nrm > 0 else 0.0
        records.append({
            "sub_division": subdiv,
            "year": yr,
            "month": mo,
            "rainfall_mm": round(total_mm, 2),
            "normal_mm": round(nrm, 2),
            "departure_pct": round(departure, 2),
        })

    records.sort(key=lambda r: (r["sub_division"], r["year"], r["month"]))
    logger.info(f"Open-Meteo: {len(records)} monthly rainfall records "
                f"({len(subdiv_daily)} sub-divisions)")
    return records


def search_rainfall_resource() -> Optional[str]:
    """Search data.gov.in catalog for the rainfall departure resource.

    Uses ALL_INDIA_RAINFALL_API_KEY (falls back to DATA_GOV_IN_API_KEY).
    Returns the resource ID if found, None otherwise.
    """
    logger.info("Searching for rainfall departure resource on data.gov.in...")

    api_key = _get_rainfall_api_key()
    if not api_key:
        logger.warning("No API key set for rainfall search")
        return None

    search_urls = [
        f"https://api.data.gov.in/catalog?api-key={api_key}&format=json&limit=10&search=rainfall+departure+normal+monthly+sub-division",
        f"https://api.data.gov.in/catalog?api-key={api_key}&format=json&limit=10&search=sub-division+rainfall+departure",
        f"https://api.data.gov.in/catalog?api-key={api_key}&format=json&limit=10&search=imd+rainfall+monthly",
    ]

    for url in search_urls:
        try:
            data = http_get_json(url, timeout=15, max_retries=1)
            if "records" in data and len(data["records"]) > 0:
                for r in data["records"]:
                    rid = r.get("resource_id", r.get("id", ""))
                    title = r.get("title", r.get("name", ""))
                    logger.info(f"  Found: {title} (ID: {rid})")
                    return rid
        except Exception as e:
            logger.debug(f"  Search failed: {e}")
            continue

    return None


def try_rainfall_resource(resource_id: str) -> Optional[list[dict]]:
    """Try to pull data from a rainfall resource ID.

    Uses ALL_INDIA_RAINFALL_API_KEY (falls back to DATA_GOV_IN_API_KEY).
    Returns records if successful, None otherwise.
    """
    api_key = _get_rainfall_api_key()
    if not api_key:
        return None
    url = f"https://api.data.gov.in/resource/{resource_id}?api-key={api_key}&format=json&limit=10"

    try:
        data = http_get_json(url, timeout=15, max_retries=1)
        records = data.get("records", [])
        if records:
            logger.info(f"  Resource {resource_id} returned {len(records)} records")
            logger.info(f"  Columns: {list(records[0].keys())}")
            return records
    except Exception as e:
        logger.warning(f"  Resource {resource_id} failed: {e}")

    return None


def fetch_rainfall_from_github() -> list[dict]:
    """Fetch rainfall data from Datameet's maintained CSV on GitHub.

    NOTE: This dataset URL is stale (404). Kept for backward compatibility
    — Open-Meteo is the primary source now.
    """
    logger.info("Fetching rainfall data from Datameet GitHub...")

    try:
        content = http_get_text(FALLBACK_CSV_URL, timeout=30, max_retries=2)

        reader = csv.DictReader(io.StringIO(content))
        records = []

        for row in reader:
            try:
                sub_div = row.get("sub_division") or row.get("Sub_Division") or row.get("subdivision") or row.get("SUBDIVISION") or ""
                year = int(row.get("year") or row.get("Year") or 0)
                month = int(row.get("month") or row.get("Month") or 0)

                rainfall = safe_float(row.get("rainfall") or row.get("Rainfall") or row.get("RAINFALL"))
                normal = safe_float(row.get("normal") or row.get("Normal") or row.get("NORMAL"))

                departure = safe_float(
                    row.get("departure_pct")
                    or row.get("departure")
                    or row.get("Departure")
                    or row.get("DEPARTURE")
                    or row.get("anomaly_pct")
                    or row.get("Anomaly")
                )

                if departure is None and rainfall is not None and normal and normal > 0:
                    departure = ((rainfall - normal) / normal) * 100

                if sub_div and year and month:
                    records.append({
                        "sub_division": sub_div.strip(),
                        "year": year,
                        "month": month,
                        "rainfall_mm": rainfall,
                        "normal_mm": normal,
                        "departure_pct": departure,
                    })
            except (ValueError, TypeError):
                continue

        logger.info(f"  Loaded {len(records)} rainfall records from GitHub")
        return records

    except Exception as e:
        logger.error(f"  Failed to fetch rainfall data: {e}")
        return []


def load_district_subdivision_map() -> dict:
    """
    Load a mapping of (state, district) -> IMD meteorological sub-division.

    Returns dict with (state, district) keys and sub_division values.
    Covers all ~640 (state, district) pairs from the prices table.
    Uses case-insensitive matching for robustness against spelling variations.
    """
    mapping = {}

    # Andaman & Nicobar Islands
    for d in ['Andaman Islands', 'Nicobar', 'North and Middle Andaman', 'North and Middle Andaman ', 'South Andaman']:
        mapping[('Andaman & Nicobar', d)] = 'Andaman & Nicobar Islands'
    for d in ['Nicobar', 'North and Middle Andaman', 'North and Middle Andaman ', 'South Andaman']:
        mapping[('Andaman and Nicobar', d)] = 'Andaman & Nicobar Islands'

    # Arunachal Pradesh
    for d in ['Anjaw', 'Changlang', 'Dibang Valley', 'East Kameng', 'East Siang', 'Kra Daadi', 'Kurung Kumey', 'Lohit', 'Longding', 'Lower Dibang Valley', 'Lower Subansiri', 'Namsai', 'Papum Pare', 'Siang', 'Tawang', 'Tirap', 'Upper Siang', 'Upper Subansiri', 'West Kameng', 'West Siang']:
        mapping[('Arunachal Pradesh', d)] = 'Arunachal Pradesh'

    # Assam & Meghalaya
    for d in ['Baksa', 'Barpeta', 'Bongaigaon', 'Cachar', 'Charaideo', 'Darrang', 'Dhemaji', 'Dhubri', 'Dibrugarh', 'Goalpara', 'Golaghat', 'Hailakandi', 'Hojai', 'Jorhat', 'Kamrup', 'Kamrup Metro', 'Karimganj', 'Kokrajhar', 'Lakhimpur', 'Majuli', 'Nagaon', 'Nalbari', 'Sivasagar', 'Sonitpur', 'Tinsukia', 'Udalguri']:
        mapping[('Assam', d)] = 'Assam & Meghalaya'
    for d in ['East Garo Hills', 'East Jaintia Hills', 'East Khasi Hills', 'Jaintia Hills', 'Ri Bhoi', 'South Garo Hills', 'South West Khasi Hills', 'West Garo Hills', 'West Jaintia Hills', 'West Khasi Hills']:
        mapping[('Meghalaya', d)] = 'Assam & Meghalaya'

    # Bihar
    for d in ['Araria', 'Arwal', 'Aurangabad', 'Banka', 'Begusarai', 'Bhagalpur', 'Bhojpur', 'Buxar', 'Chhapra', 'Darbhanga', 'East Champaran/ Motihari', 'Gaya', 'Gopalganj', 'Jamui', 'Jehanabad', 'Kaimur', 'Katihar', 'Khagaria', 'Kishanganj', 'Lakhisarai', 'Madhepura', 'Madhubani', 'Munger', 'Muzaffarpur', 'Nalanda', 'Nawada', 'Patna', 'Purba Champaran', 'Purnia', 'Rohtas', 'Saharsa', 'Samastipur', 'Saran', 'Sheikhpura', 'Sheohar', 'Sitamarhi', 'Siwan', 'Supaul', 'Vaishali', 'West Champaran']:
        mapping[('Bihar', d)] = 'Bihar'

    # Chhattisgarh
    for d in ['Balod', 'Balodabazar', 'Balrampur', 'Bastar', 'Bhilai', 'Bijapur', 'Bilaspur', 'Dantewada', 'Dhamtari', 'Durg', 'Gourela Pendra Marwahi', 'Janjgeer-Champa', 'Jashpur', 'Kabirdham', 'Kanker', 'Khairagarh Chhuikhadan Gandai', 'Kondagaon', 'Korba', 'Koriya', 'Mahasamund', 'Manendragarh', 'Mohla Manpur Ambagarh Chouki', 'Mungeli', 'Narayanpur', 'Raigarh', 'Raipur', 'Rajnandgaon', 'Sarangarh Bilaigarh', 'Sukma', 'Surajpur', 'Surguja']:
        mapping[('Chattisgarh', d)] = 'Chhattisgarh'
    for d in ['Bastar', 'Bilaspur', 'Dantewada', 'Durg', 'Surguja']:
        mapping[('Chhattisgarh', d)] = 'Chhattisgarh'

    # Coastal Andhra Pradesh
    for d in ['Alluri Sitharama Raju', 'Anakapally', 'Bapatla', 'Dr.B.R.A.Konaseema', 'East Godavari', 'Eluru', 'Guntur', 'Kakinada', 'Konaseema', 'Krishna', 'Markapuram', 'NTR', 'Nellore', 'Palnadu', 'Parvathipuram Manyam', 'Polavaram', 'Prakasam', 'SPSR Nellore', 'Srikakulam', 'Vijayanagaram', 'Visakhapatnam', 'Vishakhapatnam', 'Vizianagaram', 'West Godavari']:
        mapping[('Andhra Pradesh', d)] = 'Coastal Andhra Pradesh'

    # Coastal Karnataka
    for d in ['Dakshin Kannad', 'Dakshina Kannada', 'Karwar', 'Udupi', 'Uttara Kannada']:
        mapping[('Karnataka', d)] = 'Coastal Karnataka'

    # East Madhya Pradesh
    for d in ['Anuppur', 'Anupur', 'Balaghat', 'Betul', 'Chhatarpur', 'Chhindwara', 'Damoh', 'Dindori', 'Harda', 'Hoshangabad', 'Jabalpur', 'Katni', 'Maihar', 'Mandla', 'Narmadapuram', 'Narsinghpur', 'Panna', 'Rewa', 'Sagar', 'Satna', 'Seoni', 'Shahdol', 'Shehdol', 'Sidhi', 'Singrauli', 'Singroli', 'Tikamgarh', 'Umaria', 'Umariya']:
        mapping[('Madhya Pradesh', d)] = 'East Madhya Pradesh'

    # East Rajasthan
    for d in ['Ajmer', 'Alwar', 'Banswara', 'Baran', 'Beawar', 'Bharatpur', 'Bhilwara', 'Bundi', 'Chittorgarh', 'Dausa', 'Deeg', 'Dholpur', 'Dudu', 'Dungarpur', 'Gangapur City', 'Jaipur', 'Jaipur Rural', 'Jhalawar', 'Jhunjhunu', 'Karauli', 'Kekri', 'Khairthal Tijara', 'Kota', 'Kotputli- Behror', 'Neem Ka Thana', 'Pratapgarh', 'Rajsamand', 'Sikar', 'Swai Madhopur', 'Tonk', 'Udaipur']:
        mapping[('Rajasthan', d)] = 'East Rajasthan'

    # East Uttar Pradesh
    for d in ['Allahabad', 'Ambedkar Nagar', 'Ambedkarnagar', 'Amethi', 'Ayodhya', 'Azamgarh', 'Bahraich', 'Ballia', 'Balrampur', 'Barabanki', 'Basti', 'Bhadohi(Sant Ravi Nagar)', 'Chandauli', 'Deoria', 'Faizabad', 'Fatehpur', 'Ghazipur', 'Gonda', 'Gorakhpur', 'Hardoi', 'Jaunpur', 'Kaushambi', 'Khiri (Lakhimpur)', 'Kushinagar', 'Lakhimpur', 'Lakhimpur Kheri', 'Lucknow', 'Maharajganj', 'Mau(Maunathbhanjan)', 'Maunath Bhanjan', 'Mirzapur', 'Pratapgarh', 'Prayagraj', 'Raebareli', 'Raebarelli', 'Sant Kabir Nagar', 'Shravasti', 'Siddharth Nagar', 'Sitapur', 'Sonbhadra', 'Sultanpur', 'Unnao', 'Varanasi']:
        mapping[('Uttar Pradesh', d)] = 'East Uttar Pradesh'

    # Gangetic West Bengal
    for d in ['Bankura', 'Birbhum', 'Dakshin Dinajpur', 'East Midnapore', 'Hooghly', 'Howrah', 'Jhargram', 'Kolkata', 'Malda', 'Maldah', 'Medinipur(E)', 'Medinipur(W)', 'Murshidabad', 'Nadia', 'North 24 Parganas', 'Paschim Bardhaman', 'Purba Bardhaman', 'Puruliya', 'Sounth 24 Parganas', 'South 24 Parganas', 'Uttar Dinajpur', 'West Midnapore']:
        mapping[('West Bengal', d)] = 'Gangetic West Bengal'

    # Gujarat
    for d in ['Ahmadabad', 'Ahmedabad', 'Amreli', 'Anand', 'Banaskanth', 'Banaskantha', 'Bharuch', 'Bhavnagar', 'Botad', 'Chhota Udaipur', 'Dahod', 'Dang', 'Devbhumi Dwarka', 'Gandhinagar', 'Gir Somnath', 'Jamnagar', 'Junagadh', 'Junagarh', 'Kachchh', 'Kheda', 'Mehsana', 'Morbi', 'Narmada', 'Navsari', 'Panchmahal', 'Panchmahals', 'Patan', 'Porbandar', 'Rajkot', 'Sabarkantha', 'Surat', 'Surendranagar', 'The Dangs', 'Vadodara', 'Vadodara(Baroda)', 'Valsad']:
        mapping[('Gujarat', d)] = 'Gujarat'

    # Haryana, Delhi & Chandigarh
    for d in ['Chandigarh']:
        mapping[('Chandigarh', d)] = 'Haryana, Delhi & Chandigarh'
    for d in ['Ambala', 'Bhiwani', 'Faridabad', 'Fatehabad', 'Gurgaon', 'Gurugram', 'Hisar', 'Hissar', 'Jhajar', 'Jhajjar', 'Jind', 'Kaithal', 'Karnal', 'Kurukshetra', 'Mahendragarh', 'Mahendragarh-Narnaul', 'Mewat', 'Nuh', 'Palwal', 'Panchkula', 'Panipat', 'Rewari', 'Rohtak', 'Sirsa', 'Sonipat', 'Yamuna Nagar']:
        mapping[('Haryana', d)] = 'Haryana, Delhi & Chandigarh'
    for d in ['Delhi']:
        mapping[('NCT of Delhi', d)] = 'Haryana, Delhi & Chandigarh'

    # Himachal Pradesh
    for d in ['Bilaspur', 'Chamba', 'Hamirpur', 'Kangra', 'Kinnaur', 'Kullu', 'Lahul & Spiti', 'Mandi', 'Shimla', 'Sirmaur', 'Solan', 'Una']:
        mapping[('Himachal Pradesh', d)] = 'Himachal Pradesh'

    # Jammu & Kashmir
    for d in ['Anantnag', 'Bandipora', 'Baramulla', 'Budgam', 'Doda', 'Ganderbal', 'Jammu', 'Kargil', 'Kathua', 'Kishtwar', 'Kulgam', 'Kupwara', 'Ladakh', 'Leh', 'Poonch', 'Pulwama', 'Rajouri', 'Ramban', 'Reasi', 'Shopian', 'Srinagar', 'Udhampur']:
        mapping[('Jammu & Kashmir', d)] = 'Jammu & Kashmir'
    for d in ['Ganderbal', 'Jammu', 'Kathua', 'Rajouri', 'Udhampur']:
        mapping[('Jammu and Kashmir', d)] = 'Jammu & Kashmir'

    # Jharkhand
    for d in ['Bokaro', 'Chatra', 'Dhanbad', 'Dumka', 'East Singhbhum', 'Garhwa', 'Giridih', 'Gumla', 'Hazaribagh', 'Jamtara', 'Koderma', 'Latehar', 'Lohardaga', 'Pakur', 'Palamu', 'Purba Singhbhum', 'Ramgarh', 'Ranchi', 'Sahibganj', 'Seraikela Kharsawan', 'Simdega', 'West Singhbhum']:
        mapping[('Jharkhand', d)] = 'Jharkhand'

    # Kerala & Mahe
    for d in ['Alappuzha', 'Ernakulam', 'Idukki', 'Kannur', 'Kasaragod', 'Kasargod', 'Kollam', 'Kottayam', 'Kozhikode', 'Kozhikode(Calicut)', 'Malappuram', 'Palakad', 'Palakkad', 'Pathanamthitta', 'Thirssur', 'Thiruvananthapuram', 'Thrissur', 'Wayanad']:
        mapping[('Kerala', d)] = 'Kerala & Mahe'
    for d in ['Alappuzha', 'Ernakulam', 'Idukki', 'Kannur', 'Kasargod', 'Kollam', 'Kottayam', 'Kozhikode(Calicut)', 'Malappuram', 'Palakad', 'Pathanamthitta', 'Thirssur', 'Thiruvananthapuram', 'Wayanad']:
        mapping[('Keralam', d)] = 'Kerala & Mahe'

    # Konkan & Goa
    for d in ['North Goa', 'South Goa']:
        mapping[('Goa', d)] = 'Konkan & Goa'
    for d in ['Mumbai', 'Mumbai city', 'Palghar', 'Raigad', 'Raigarh', 'Ratnagiri', 'Sindhudurg', 'Thane']:
        mapping[('Maharashtra', d)] = 'Konkan & Goa'

    # Madhya Maharashtra
    for d in ['Ahilyanagar', 'Ahmednagar', 'Dhule', 'Jalgaon', 'Kolhapur', 'Nandurbar', 'Nashik', 'Pune', 'Sangli', 'Satara', 'Solapur']:
        mapping[('Maharashtra', d)] = 'Madhya Maharashtra'

    # Marathwada
    for d in ['Aurangabad', 'Beed', 'Bid', 'Chattrapati Sambhajinagar', 'Dharashiv', 'Hingoli', 'Jalna', 'Latur', 'Nanded', 'Osmanabad', 'Parbhani']:
        mapping[('Maharashtra', d)] = 'Marathwada'

    # Nagaland, Manipur, Mizoram & Tripura
    for d in ['Bishnupur', 'Chandel', 'Churachandpur', 'Imphal East', 'Imphal West', 'Jiribam', 'Kakching', 'Kamjong', 'Noney', 'Senapati', 'Tamenglong', 'Tengnoupal', 'Thoubal', 'Ukhrul', 'West Imphal']:
        mapping[('Manipur', d)] = 'Nagaland, Manipur, Mizoram & Tripura'
    for d in ['Aizawl']:
        mapping[('Mizoram', d)] = 'Nagaland, Manipur, Mizoram & Tripura'
    for d in ['Dimapur', 'Kiphire', 'Kohima', 'Longleng', 'Mokokchung', 'Mon', 'Peren', 'Phek', 'Tsemenyu', 'Tseminyu', 'Tuensang', 'Wokha', 'Zunheboto']:
        mapping[('Nagaland', d)] = 'Nagaland, Manipur, Mizoram & Tripura'
    for d in ['Dhalai', 'Gomati', 'Khowai', 'North Tripura', 'Sepahijala', 'South District', 'South Tripura', 'Unokoti', 'West District', 'West Tripura']:
        mapping[('Tripura', d)] = 'Nagaland, Manipur, Mizoram & Tripura'

    # North Interior Karnataka
    for d in ['Bagalkot', 'Bagalkote', 'Ballari', 'Belagavi', 'Belgaum', 'Bellary', 'Bidar', 'Bijapur', 'Dharwad', 'Gadag', 'Gulbarga', 'Haveri', 'Hubli', 'Kalaburagi', 'Koppal', 'Raichur', 'Vijayapura', 'Yadagiri', 'Yadgir']:
        mapping[('Karnataka', d)] = 'North Interior Karnataka'

    # Odisha
    for d in ['Angul', 'Balangir', 'Balasore', 'Baleshwar', 'Bargarh', 'Bhadrak', 'Bolangir', 'Boudh', 'Cuttack', 'Dhenkanal', 'Gajapati', 'Ganjam', 'Jagatsinghpur', 'Jharsuguda', 'Kalahandi', 'Kendrapara', 'Kendujhar', 'Keonjhar', 'Khordha', 'Khurda', 'Koraput', 'Mayurbhanj', 'Mayurbhanja', 'Nayagarh', 'Puri', 'Rayagada', 'Sambalpur', 'Sonepur', 'Sundargarh', 'Sundergarh']:
        mapping[('Odisha', d)] = 'Odisha'

    # Punjab
    for d in ['Amritsar', 'Barnala', 'Bathinda', 'Bhatinda', 'Faridkot', 'Fatehgarh', 'Fatehgarh Sahib', 'Fazilka', 'Ferozpur', 'Firozpur', 'Gurdaspur', 'Hoshiarpur', 'Jalandhar', 'Kapurthala', 'Ludhiana', 'Malerkotla', 'Mansa', 'Moga', 'Mohali', 'Muktsar', 'Nawanshahr', 'Pathankot', 'Patiala', 'Ropar (Rupnagar)', 'Rupnagar', 'Sahibzada Ajit Singh Nagar', 'Sangrur', 'Shaheed Bhagat Singh Nagar', 'Sri Muktsar Sahib', 'Tarn Taran', 'Tarntaran', 'kapurthala']:
        mapping[('Punjab', d)] = 'Punjab'

    # Rayalaseema
    for d in ['Anantapur', 'Ananthapuramu', 'Annamayya', 'Chittoor', 'Chittor', 'Cuddapah', 'Kurnool', 'Nandyal', 'Sri Sathya Sai', 'Tirupathi', 'YSR Kadapa']:
        mapping[('Andhra Pradesh', d)] = 'Rayalaseema'

    # South Interior Karnataka
    for d in ['Bangalore', 'Bangalore Rural', 'Bangalore Urban', 'Bengaluru', 'Bengaluru Rural', 'Bengaluru South', 'Chamarajanagar', 'Chikkaballapur', 'Chikkaballapura', 'Chikkamagaluru', 'Chikmagalur', 'Chitradurga', 'Davanagere', 'Davangere', 'Hassan', 'Kodagu', 'Kolar', 'Mandya', 'Mysore', 'Mysuru', 'Ramanagara', 'Shimoga', 'Shivamogga', 'Tumakuru', 'Tumkur', 'Vijayanagara']:
        mapping[('Karnataka', d)] = 'South Interior Karnataka'

    # Sub-Himalayan West Bengal & Sikkim
    for d in ['East', 'Gangtok', 'Gyalshing', 'Mangan', 'Namchi', 'North', 'Pakyong', 'Soreng', 'South', 'West']:
        mapping[('Sikkim', d)] = 'Sub-Himalayan West Bengal & Sikkim'
    for d in ['Alipurduar', 'Cooch Behar', 'Coochbehar', 'Darjeeling', 'Darjiling', 'Jalpaiguri', 'Kalimpong']:
        mapping[('West Bengal', d)] = 'Sub-Himalayan West Bengal & Sikkim'

    # Tamil Nadu & Puducherry
    for d in ['Karaikal']:
        mapping[('Pondicherry', d)] = 'Tamil Nadu & Puducherry'
    for d in ['Karaikal', 'Pondicherry', 'Puducherry']:
        mapping[('Puducherry', d)] = 'Tamil Nadu & Puducherry'
    for d in ['Ariyalur', 'Chengalpattu', 'Chennai', 'Coimbatore', 'Cuddalore', 'Dharmapuri', 'Dindigul', 'Erode', 'Kallakuruchi', 'Kancheepuram', 'Kanyakumari', 'Karur', 'Krishnagiri', 'Madurai', 'Nagapattinam', 'Nagercoil (Kannyiakumari)', 'Namakkal', 'Perambalur', 'Pudukkottai', 'Ramanathapuram', 'Ranipet', 'Salem', 'Sivaganga', 'Tenkasi', 'Thanjavur', 'The Nilgiris', 'Theni', 'Thiruchirappalli', 'Thirunelveli', 'Thirupathur', 'Thirupur', 'Thiruvannamalai', 'Thiruvarur', 'Thiruvellore', 'Thoothukudi', 'Tiruchchirappalli', 'Tiruchirappalli', 'Tirunelveli', 'Tirunelveli Kattabo', 'Tirupathur', 'Tirupur', 'Tiruvallore', 'Tiruvannamalai', 'Tuticorin', 'Vellore', 'Villupuram', 'Viluppuram', 'Virudhunagar']:
        mapping[('Tamil Nadu', d)] = 'Tamil Nadu & Puducherry'

    # Telangana
    for d in ['Adilabad', 'Asifabad', 'Bhadradri Kothagudem', 'Hyderabad', 'Jagtial', 'Jogulamba Gadwal', 'Karimnagar', 'Khammam', 'Mahabubabad', 'Mahbubnagar', 'Medak', 'Nagarkurnool', 'Nalgonda', 'Nirmal', 'Nizamabad', 'Peddapalli', 'Ranga Reddy', 'Sangareddy', 'Siddipet', 'Suryapet', 'Vikarabad', 'Wanaparthy', 'Warangal']:
        mapping[('Telangana', d)] = 'Telangana'

    # Uttarakhand
    for d in ['Almora', 'Bageshwar', 'Chamoli', 'Champawat', 'Dehra Dun', 'Dehradoon', 'Garhwal (Pauri)', 'Haridwar', 'Naini Tal', 'Nanital', 'Pauri Garhwal', 'Pithoragarh', 'Rudraprayag', 'Tehri Garhwal', 'Udham Singh Nagar', 'Udhamsinghnagar']:
        mapping[('Uttarakhand', d)] = 'Uttarakhand'
    for d in ['Champawat', 'Dehradoon', 'Haridwar', 'Nanital', 'UdhamSinghNagar']:
        mapping[('Uttrakhand', d)] = 'Uttarakhand'

    # Vidarbha
    for d in ['Akola', 'Amarawati', 'Amravati', 'Bhandara', 'Buldhana', 'Chandrapur', 'Gadchiroli', 'Gondia', 'Nagpur', 'Wardha', 'Washim', 'Yavatmal']:
        mapping[('Maharashtra', d)] = 'Vidarbha'

    # West Madhya Pradesh
    for d in ['Agar Malwa', 'Alirajpur', 'Ashoknagar', 'Badwani', 'Barwani', 'Bhind', 'Bhopal', 'Burhanpur', 'Datia', 'Dewas', 'Dhar', 'East Nimar', 'Guna', 'Gwalior', 'Indore', 'Jhabua', 'Khandwa', 'Khargone', 'Mandsaur', 'Morena', 'Neemuch', 'Raisen', 'Rajgarh', 'Ratlam', 'Sehore', 'Shajapur', 'Sheopur', 'Shivpuri', 'Ujjain', 'Vidisha', 'West Nimar']:
        mapping[('Madhya Pradesh', d)] = 'West Madhya Pradesh'

    # West Rajasthan
    for d in ['Anupgarh', 'Balotra', 'Barmer', 'Bikaner', 'Churu', 'Deedwana Kuchaman', 'Ganganagar', 'Hanumangarh', 'Jaisalmer', 'Jalore', 'Jodhpur', 'Jodhpur Rural', 'Nagaur', 'Pali', 'Phalodi', 'Sanchore', 'Sirohi']:
        mapping[('Rajasthan', d)] = 'West Rajasthan'

    # West Uttar Pradesh
    for d in ['Agra', 'Aligarh', 'Amroha', 'Auraiya', 'Badaun', 'Baghpat', 'Banda', 'Bareilly', 'Bijnor', 'Buduan', 'Bulandshahar', 'Bulandshahr', 'Chitrakoot', 'Chitrakut', 'Etah', 'Etawah', 'Farrukhabad', 'Farukhabad', 'Firozabad', 'Gautam Budh Nagar', 'Ghaziabad', 'Hamirpur', 'Hathras', 'Jalaun (Orai)', 'Jhansi', 'Kannauj', 'Kannuj', 'Kanpur', 'Kanpur Dehat', 'Kanpur Nagar', 'Kasganj', 'Lalitpur', 'Mahoba', 'Mainpuri', 'Mathura', 'Meerut', 'Moradabad', 'Muzaffarnagar', 'Noida', 'Pilibhit', 'Pillibhit', 'Rampur', 'Saharanpur', 'Sambhal', 'Shahjahanpur', 'Shamli']:
        mapping[('Uttar Pradesh', d)] = 'West Uttar Pradesh'

    return mapping


def fetch_district_daily_rainfall(resource_id: str, districts: list[str],
                                  max_rows_per_district: int = 4000) -> list[dict]:
    """Fetch daily district-wise rainfall from a data.gov.in resource.

    Uses ALL_INDIA_RAINFALL_API_KEY (falls back to DATA_GOV_IN_API_KEY).
    Returns a flat list of raw records.
    """
    api_key = _get_rainfall_api_key()
    if not api_key:
        logger.warning("No API key set for district rainfall fetch")
        return []

    all_recs: list[dict] = []
    for dist in districts:
        offset = 0
        fetched = 0
        while fetched < max_rows_per_district:
            limit = min(1000, max_rows_per_district - fetched)
            url = (
                f"https://api.data.gov.in/resource/{resource_id}"
                f"?api-key={api_key}&format=json&limit={limit}&offset={offset}"
                f"&filters[District]={urllib.parse.quote(str(dist))}"
            )
            try:
                data = http_get_json(url, timeout=25, max_retries=1)
            except Exception as e:
                logger.warning(f"  Rainfall fetch failed for {dist}: {e}")
                break
            recs = data.get("records", [])
            if not recs:
                break
            all_recs.extend(recs)
            fetched += len(recs)
            if len(recs) < limit:
                break
            offset += limit
            time.sleep(0.2)
        logger.info(f"  Fetched {fetched} daily rows for {dist}")
    return all_recs


def aggregate_daily_to_monthly(records: list[dict]) -> list[dict]:
    """Aggregate raw daily district rainfall into monthly sub-division records.

    departure_pct is computed against each district's own climatology.
    """
    dmap = load_district_subdivision_map()
    dist_to_subdiv = {}
    for (state, district), subdiv in dmap.items():
        dist_to_subdiv.setdefault(district.lower(), subdiv)

    groups: dict = {}
    for r in records:
        dist = (r.get("District") or "").strip()
        yr = r.get("Year")
        mo = r.get("Month")
        val = safe_float(r.get("Avg_rainfall"))
        if not dist or val is None or yr is None or mo is None:
            continue
        try:
            yr = int(yr); mo = int(mo)
        except (ValueError, TypeError):
            continue
        groups.setdefault((dist.lower(), yr, mo), []).append(val)

    monthly = {}
    dist_month_vals: dict = {}
    for (dist, yr, mo), vals in groups.items():
        avg = sum(vals) / len(vals)
        monthly[(dist, yr, mo)] = avg
        dist_month_vals.setdefault(dist, {}).setdefault(mo, []).append(avg)

    normal = {}
    for dist, monthmap in dist_month_vals.items():
        for mo, avgs in monthmap.items():
            normal[(dist, mo)] = sum(avgs) / len(avgs) if avgs else 0.0

    out = []
    for (dist, yr, mo), avg in monthly.items():
        subdiv = dist_to_subdiv.get(dist)
        if not subdiv:
            continue
        nrm = normal.get((dist, mo), 0.0)
        departure = ((avg - nrm) / nrm * 100.0) if nrm > 0 else 0.0
        out.append({
            "sub_division": subdiv,
            "year": yr,
            "month": mo,
            "rainfall_mm": round(avg, 2),
            "normal_mm": round(nrm, 2),
            "departure_pct": round(departure, 2),
        })
    return out


def fetch_and_store_all_rainfall() -> list[dict]:
    """Fetch rainfall data from the most reliable available source.

    Order: Open-Meteo (primary) → RAINFALL_RESOURCE_ID → data.gov.in search
    → candidate IDs → GitHub mirror.

    Never raises: if every source fails, returns [] so the nightly ingestion can
    still commit prices + precomputed RDD results.
    """
    # Step 0: Primary source — Open-Meteo (free, no API key, always works)
    try:
        records = fetch_rainfall_from_open_meteo()
        if records:
            return records
    except Exception as e:
        logger.warning(f"Open-Meteo rainfall fetch failed: {e}")

    # Step 1: Explicit resource ID from environment.
    explicit_raw = os.environ.get("RAINFALL_RESOURCE_ID", "")
    explicit_ids = [s.strip() for s in re.split(r"[,;]", explicit_raw) if s.strip()]
    if explicit_ids:
        try:
            from mandi_rdd.storage.duckdb_store import get_connection
            dmap = load_district_subdivision_map()
            try:
                conn = get_connection()
                price_districts = [r[0] for r in conn.execute(
                    "SELECT DISTINCT district FROM prices"
                ).fetchall()]
                conn.close()
            except Exception:
                price_districts = []
            needed_subdivs = set()
            for pd_ in price_districts:
                for (state, district), subdiv in dmap.items():
                    if district.lower() == pd_.lower():
                        needed_subdivs.add(subdiv)
                        break
            rep_by_subdiv = {}
            for pd_ in price_districts:
                for (state, district), subdiv in dmap.items():
                    if district.lower() == pd_.lower() and subdiv not in rep_by_subdiv:
                        rep_by_subdiv[subdiv] = pd_
            districts = list(rep_by_subdiv.values()) if rep_by_subdiv else price_districts[:60]
            for explicit in explicit_ids:
                logger.info(f"Using RAINFALL_RESOURCE_ID: {explicit}")
                try:
                    raw = fetch_district_daily_rainfall(explicit, districts)
                except Exception as e2:
                    logger.warning(f"RAINFALL_RESOURCE_ID {explicit} fetch failed: {e2}")
                    raw = None
                if raw:
                    monthly = aggregate_daily_to_monthly(raw)
                    if monthly:
                        logger.info(f"Aggregated to {len(monthly)} monthly rainfall rows from {explicit}")
                        return monthly
        except Exception as e:
            logger.warning(f"RAINFALL_RESOURCE_ID ingestion failed: {e}")

    # Step 2: Try data.gov.in rainfall resources
    try:
        resource_id = search_rainfall_resource()
        if resource_id:
            records = try_rainfall_resource(resource_id)
            if records and len(records) > 50:
                logger.info(f"Using data.gov.in rainfall resource: {resource_id}")
                return records
    except Exception as e:
        logger.warning(f"data.gov.in rainfall search failed: {e}")

    # Step 3: Try candidate IDs
    for rid in RAINFALL_CANDIDATE_IDS:
        try:
            records = try_rainfall_resource(rid)
            if records and len(records) > 50:
                logger.info(f"Using rainfall resource: {rid}")
                return records
        except Exception:
            continue

    # Step 4: Fall back to GitHub Datameet CSV (likely stale)
    try:
        logger.info("Falling back to Datameet GitHub rainfall dataset...")
        records = fetch_rainfall_from_github()
        if records:
            return records
    except Exception as e:
        logger.warning(f"Datameet rainfall fetch failed: {e}")

    logger.warning(
        "No rainfall data source available. RDD causal analysis (rainfall "
        "controls) will be skipped until a rainfall data source is available."
    )
    return []


def fetch_all_india_monsoon(resource_id: str, api_key: str | None = None) -> list[dict]:
    """Fetch the all-India monsoon rainfall series (1901-2019) from data.gov.in
    resource af34a228.

    Returns list of {"year", "jun", "jul", "aug", "sep", "jun_sep"} dicts.
    Never raises: returns [] on any failure.
    """
    if not resource_id:
        return []
    key = api_key or _get_rainfall_api_key()
    if not key:
        logger.warning("No API key set; skipping all-India monsoon fetch.")
        return []
    url = (
        f"https://api.data.gov.in/resource/{resource_id}"
        f"?api-key={key}&format=json&limit=500"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25, context=SSL_CTX) as f:
            data = json.loads(f.read())
        recs = data.get("records", [])
        out = []
        for r in recs:
            try:
                out.append({
                    "year": int(r.get("year", 0)),
                    "jun": safe_float(r.get("jun")),
                    "jul": safe_float(r.get("jul")),
                    "aug": safe_float(r.get("aug")),
                    "sep": safe_float(r.get("sep")),
                    "jun_sep": safe_float(r.get("jun_sep")),
                })
            except (ValueError, TypeError):
                continue
        out.sort(key=lambda x: x["year"])
        logger.info(f"Fetched {len(out)} all-India monsoon rows (1901-2019)")
        return out
    except Exception as e:
        logger.warning(f"All-India monsoon fetch failed: {e}")
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    records = fetch_and_store_all_rainfall()
    print(f"Total rainfall records: {len(records)}")

    if records:
        print(f"Sample columns: {list(records[0].keys())}")
        print(f"Sample: {records[0]}")
        print(f"Last: {records[-1]}")

        deps = [r.get("departure_pct") for r in records if r.get("departure_pct") is not None]
        if deps:
            print(f"Departure range: {min(deps):.1f}% to {max(deps):.1f}%")
            print(f"Below -19% (deficient): {sum(1 for d in deps if d < -19)} / {len(deps)}")

    mapping = load_district_subdivision_map()
    print(f"\nDistrict-subdivision mappings: {len(mapping)}")
    sample = list(mapping.items())[:3]
    for (s, d), sub in sample:
        print(f"  {s} / {d} → {sub}")
