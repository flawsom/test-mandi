<div align="center" style="position:relative; overflow:hidden; border-radius:20px; background:linear-gradient(135deg, #0B0F1E 0%, #0F1F15 40%, #0B0F1E 100%); padding:44px 20px 36px; margin-bottom:8px; border:1px solid rgba(0,255,136,0.08);">

<div style="position:absolute; top:-120px; left:50%; transform:translateX(-50%); width:600px; height:300px; background:radial-gradient(ellipse, rgba(0,255,136,0.12) 0%, transparent 70%); pointer-events:none;"></div>
<div style="position:absolute; top:0; left:10%; right:10%; height:1px; background:linear-gradient(90deg, transparent, rgba(0,255,136,0.5), transparent);"></div>

<div style="position:relative; z-index:1;">
<h1 style="margin:0; font-size:2.2em; font-weight:700; color:#E0E0E0; letter-spacing:-0.5px;">
  <img src="docs/assets/svg/icon-f8867c21931f.svg" width="36" height="36" alt="" style="vertical-align:middle; max-width:100%;" />
  Historical Price Data (Backfill)
</h1>
<h4 style="color:#94A3B8; font-weight:400; font-size:0.95em; margin:6px 0 0 0;">MandiIQ Documentation</h4>
</div>

</div>
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>

The live `data.gov.in` mandi-prices API (`9ef84268-...`) is a **daily snapshot
feed** — it only ever returns the *current day's* records. That means the
nightly GitHub Action can append one day at a time but can **never create
months/years of history on its own**.

Two KPIs on the Executive Overview need real history to compute:

| KPI | Why it needs history |
|-----|----------------------|
| **RDD Effect** | The regression-discontinuity estimator needs 3+ dates with both deficient AND non-deficient rainfall to find a price jump at the threshold. |
| **Forecast MAPE** | Prophet needs >= 20 daily points for a train/test split (ideally months). |

`Avg Price` and `Districts` work from even a single day, so they populate
immediately. The other two stay `—` until history exists.

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-4fe945889b5c.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="how-to-backfill-one-time-then-automatic"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> How to backfill (one-time, then automatic)
</h2>

1. **Get a historical CSV** from one of these verified sources:
   - **data.gov.in dataset page** for "APMC Mandi Prices / Agmarknet"
     (search "Agmarknet" on https://www.data.gov.in) → look for the
     **Downloads** section with monthly/yearly bulk CSV or ZIP files.
   - **agmarknet.gov.in** → Reports → Daily Prices → yearly ZIP archives
     (official, complete, multi-year).

   Expected columns (Agmarknet / data.gov.in bulk format):
   ```
   arrival_date, state, district, market, commodity, variety,
   grade, min_price, max_price, modal_price
   ```
   The loader auto-detects `dd/mm/yyyy`, `yyyy-mm-dd`, `mm-dd-yyyy`
   and tolerates alternate column names (e.g. `mandi`, `maxprice`).

   ### Hands-off option (no manual download)
   `mandi_rdd/ingestion/fetch_historical.py` can pull the bulk file
   **itself** during the nightly workflow, so you never touch a CSV:
   1. On the data.gov.in dataset **Downloads** page, copy the direct
      link to the bulk CSV/ZIP.
   2. In GitHub → **Settings → Secrets and variables → Actions**, add:
      - Name: `HISTORICAL_SOURCE_URL`
      - Value: that direct download URL
   3. The next `nightly-ingest` run fetches it into `data/historical/`,
      unpacks ZIPs, and the existing backfill ingests it automatically.
   Leave the secret unset to keep the manual-drop behaviour.

2. **Drop it in the historical folder:**
   ```
   mandi_rdd/data/historical/<any-name>.csv
   ```
   (the folder is tracked via `.gitkeep`; do NOT commit the CSV itself
   unless you intend to — see step 3).

3. **Push it** so the online pipeline ingests it:
   ```bash
   git add mandi_rdd/data/historical/<file>.csv
   git commit -m "data: backfill historical prices <range>"
   git push origin master
   ```
   The next `nightly-ingest` run (or a manual "Run workflow") will:
   - `upsert` every row into `prices` (deduped, no duplicates),
   - delete the consumed CSV,
   - then run RDD + forecast + classifier on the combined history,
   - commit the refreshed DB back → Streamlit redeploys automatically.

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-b5297f23fd61.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="alternative-keep-the-csv-out-of-git"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Alternative: keep the CSV out of git
</h2>

If you'd rather not commit a large CSV, you can SSH into the runner or use
the GitHub web UI to place the file before a manual workflow run. The
`ingest_historical_csv.py` script also supports a direct call:

```bash
python -m mandi_rdd.ingestion.ingest_historical_csv path/to/file.csv
# or auto-ingest everything currently in data/historical/:
python -m mandi_rdd.ingestion.ingest_historical_csv --auto
```

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-47f7f2f791a1.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="verifying-it-worked-online"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-5fc91c87ca3d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Verifying it worked (online)
</h2>

After the workflow run completes (Actions tab → Nightly Ingestion → green),
open the dashboard. Within ~1-2 min of Streamlit's redeploy:
- **Avg Price** / **Districts** → real numbers immediately.
- **RDD Effect** → populates once >= 3 qualifying rainfall dates exist.
- **Forecast MAPE** → populates once >= 20 daily points exist per commodity.

You can also check the DB directly:
```sql
SELECT commodity, MIN(arrival_date), MAX(arrival_date), COUNT(*)
FROM prices GROUP BY commodity;
```
A wide date range = successful backfill.

</div></div></div>

<div align="center">
<br />
<a href="#" style="display:inline-block; padding:8px 20px; border-radius:10px; background:linear-gradient(135deg, rgba(0,255,136,0.12) 0%, rgba(0,255,136,0.04) 100%); border:1px solid rgba(0,255,136,0.2); color:#00FF88; font-weight:500; text-decoration:none; font-size:14px;">&#x2191; Back to Top</a>
<br /><br />
</div>