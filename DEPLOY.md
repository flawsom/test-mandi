<div align="center" style="position:relative; overflow:hidden; border-radius:20px; background:linear-gradient(135deg, #0B0F1E 0%, #0F1F15 40%, #0B0F1E 100%); padding:44px 20px 36px; margin-bottom:8px; border:1px solid rgba(0,255,136,0.08);">

<div style="position:absolute; top:-120px; left:50%; transform:translateX(-50%); width:600px; height:300px; background:radial-gradient(ellipse, rgba(0,255,136,0.12) 0%, transparent 70%); pointer-events:none;"></div>
<div style="position:absolute; top:0; left:10%; right:10%; height:1px; background:linear-gradient(90deg, transparent, rgba(0,255,136,0.5), transparent);"></div>

<div style="position:relative; z-index:1;">
<h1 style="margin:0; font-size:2.2em; font-weight:700; color:#E0E0E0; letter-spacing:-0.5px;">
  <img src="docs/assets/svg/icon-f8867c21931f.svg" width="36" height="36" alt="" style="vertical-align:middle; max-width:100%;" />
  Mandiiq — Extreme Detail Deployment Guide
</h1>
<h4 style="color:#94A3B8; font-weight:400; font-size:0.95em; margin:6px 0 0 0;">MandiIQ Documentation</h4>
</div>

</div>
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="architecture-overview"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e22ec59e46bc.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Architecture Overview
</h2>

MandiIQ has three deployable surfaces:

| Surface | Technology | Purpose | URL |
|---------|-----------|---------|-----|
| **API Server** | FastAPI + DuckDB | Data endpoints, health checks, pipeline execution | `p01--mandiiq--zbvjrztgjqgw.code.run` |
| **Streamlit Dashboard** | Streamlit 1.59 | Interactive data exploration UI | `test-mandi-keae7eruks2n4cqvumjfu8.streamlit.app` |
| **Static Pages** | HTML + JS (GitHub Pages) | Landing page, docs, heartbeat dashboard | `flawsom.github.io/test-mandi/` |

This guide covers **three deployment providers**:

1. **Northflank** — Docker-based API server + hourly cron job + persistent volume
2. **Vercel** — Serverless Python API (lightweight alternative to Northflank/Render)
3. **Streamlit Cloud** — Dashboard hosting

---

# PART 1: NORTHFLANK

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-4fe945889b5c.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="overview"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e22ec59e46bc.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Overview
</h2>

Northflank runs containerized workloads on its own Kubernetes infrastructure with a generous free tier. MandiIQ runs two services on Northflank:

- **API Server** — The FastAPI backend (always-on web service)
- **Ingestion Cron** — Hourly pipeline that fetches fresh mandi prices (scheduled job)

Both share a **Persistent Volume** so the cron job writes to the same DuckDB that the API reads.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-b5297f23fd61.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="11-prerequisites"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 1.1 Prerequisites
</h2>

- [ ] A [Northflank](https://app.northflank.com) account (free tier: 2 services, 1 GB volume, 512 MB RAM each)
- [ ] Git repo connected to Northflank (GitHub OAuth is simplest)
- [ ] Your `DATA_GOV_IN_API_KEY` from [data.gov.in](https://api.data.gov.in/)

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-47f7f2f791a1.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="12-api-server-step-by-step"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-bee2875cc587.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 1.2 API Server — Step by Step
</h2>

### 1.2.1 Create the Service

1. Go to **Northflank Dashboard → Services → Create Service**
2. Choose **"From Git Repository"** → select `flawsom/test-mandi` (or your fork)
3. Branch: `master`
4. Service Type: **Web Service**

### 1.2.2 Build Settings

| Setting | Value |
|---------|-------|
| Build method | Docker |
| Dockerfile path | `Dockerfile.northflank` |
| Build context | `.` (repo root) |
| Port | `8080` |
| HTTP Port | `8080` |

### 1.2.3 The Dockerfile

**`Dockerfile.northflank`** (already exists in repo — inspect it):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system deps for duckdb, scipy, xgboost, Node.js + mermaid-cli
# Node.js is required for the /pipeline.svg renderer
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @mermaid-js/mermaid-cli --omit=optional \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python deps (lightweight api.txt)
COPY requirements/api.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mandi_rdd/ /app/mandi_rdd/
COPY data/ /app/data/
COPY dashboards/ /app/dashboards/

ENV PYTHONPATH=/app
ENV PORT=8080
ENV MANDIIQ_DB_PATH=/data/mandi_iq.duckdb

EXPOSE 8080

CMD ["uvicorn", "mandi_rdd.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Important details:**
- Uses the `requirements/api.txt` file (lightweight — excludes Streamlit, Prophet)
- DuckDB file lives on a **persistent volume** at `/data/mandi_iq.duckdb`
- Node.js + mermaid-cli are for pipeline SVG rendering (optional but recommended)
- Base image: `python:3.12-slim` (~120 MB compressed)

### 1.2.4 Environment Variables

Set these in the Northflank service dashboard under **Environment**:

```bash
# Required
PYTHONPATH=/app
PORT=8080
MANDIIQ_DB_PATH=/data/mandi_iq.duckdb
DATA_GOV_IN_API_KEY=YOUR_API_KEY_HERE   # Get from https://api.data.gov.in/

# Optional — AI features
GEMINI_API_KEY=
NVIDIA_API_KEY=
OPENROUTER_API_KEY=

# Optional — Sentinel Hub NDVI
SENTINEL_CLIENT_ID=
SENTINEL_CLIENT_SECRET=

# Optional — Grafana Cloud metrics push
GRAFANA_CLOUD_PROM_URL=
GRAFANA_CLOUD_PROM_USER=
GRAFANA_CLOUD_PROM_PASSWORD=

# Optional — Cloudflare R2 backup
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=mandiiq-data
```

### 1.2.5 Persistent Volume

| Setting | Value |
|---------|-------|
| Volume name | `mandiiq-data` |
| Mount path | `/data` |
| Size | 1 GB (free tier max) |
| Access mode | Single Read/Write (only 1 replica possible) |

**Critical:** *Do not scale replicas > 1* — the DuckDB file cannot be safely written to by multiple pods simultaneously. The single-read/write access mode enforces this.

### 1.2.6 Health Check

| Setting | Value |
|---------|-------|
| Protocol | HTTP |
| Path | `/health` |
| Port | `8080` |
| Initial delay | 30s |
| Period | 30s |
| Timeout | 10s |
| Failure threshold | 3 |

### 1.2.7 Resource Limits (Free Tier)

| Resource | Limit |
|----------|-------|
| RAM | 512 MB |
| vCPU | 1 (shared) |
| Replicas | 1 |

### 1.2.8 Initial Data Seed

After the API server deploys for the first time, the DuckDB is **empty**. The API auto-triggers a pipeline when `n_prices < 100`, but this can fail on a cold start if memory is tight. **Manual seed is safer:**

```bash
# 1. Get a shell on the running container (Northflank dashboard → Exec)
# 2. Run the pipeline once:
cd /app && python -c "
from mandi_rdd.ingestion.scheduler import run_ingestion
summary = run_ingestion()
print(summary)
"
```

This will fetch ~1.3M price records, rainfall data, and run RDD analysis. Expect 5–15 minutes.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-659fbdc3b394.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="13-ingestion-cron-job"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 1.3 Ingestion Cron Job
</h2>

### 1.3.1 Create the Cron Service

1. **Northflank Dashboard → Services → Create Service → "Cron Job"**
2. Service name: `mandiiq-hourly-ingest`
3. Schedule: `0 * * * *` (every hour at minute 0)
4. Concurrency policy: **Forbid** (skip if previous run is still active)

### 1.3.2 Build Settings

| Setting | Value |
|---------|-------|
| Dockerfile path | `Dockerfile.cronjob` |
| Build context | `.` |

**`Dockerfile.cronjob`** (already exists):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements/api.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt httpx>=0.27.0 python-dotenv>=1.0.0

COPY mandi_rdd/ /app/mandi_rdd/
COPY data/ /app/data/
COPY run_hourly.py /app/

ENV PYTHONPATH=/app
ENV MANDIIQ_DB_PATH=/data/mandi_iq.duckdb

CMD ["python", "run_hourly.py"]
```

**Key difference from API Dockerfile:** No Node.js, no mermaid-cli — this image is lean (~180 MB vs ~600 MB).

### 1.3.3 Mount the **Same** Persistent Volume

**THIS IS THE MOST COMMON MISTAKE.** Both the API server and the cron job must mount the **identical persistent volume** at `/data`. If you create a second volume, the cron job writes to a DuckDB that the API server never sees.

| Setting | Value |
|---------|-------|
| Volume name | **exactly** `mandiiq-data` (same as API server) |
| Mount path | `/data` |

### 1.3.4 Cron Job Environment Variables

```bash
PYTHONPATH=/app
MANDIIQ_DB_PATH=/data/mandi_iq.duckdb
DATA_GOV_IN_API_KEY=YOUR_API_KEY_HERE   # Get from https://api.data.gov.in/
SENTINEL_CLIENT_ID=      # optional
SENTINEL_CLIENT_SECRET=  # optional
GEMINI_API_KEY=          # optional
OPENROUTER_API_KEY=      # optional
NVIDIA_API_KEY=          # optional
```

### 1.3.5 Timeout

Set cron job timeout to **600 seconds** (10 minutes). The hourly run is normally ~30s (price-only fetch), but the first run and forced full runs can take 5–10 minutes.

### 1.3.6 Testing the Cron Job

```bash
# Manual trigger from Northflank dashboard:
# Services → mandiiq-hourly-ingest → "Run Now"

# Or from a shell on the API container:
cd /app && python run_hourly.py --force-full
```

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-3b0384c03533.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="14-northflank-verification-checklist"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-5fc91c87ca3d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 1.4 Northflank Verification Checklist
</h2>

- [ ] API server deploys successfully (green status)
- [ ] `GET /health` returns 200 with data counts
- [ ] Cron job mounts the **same volume** as the API server
- [ ] Cron job runs successfully (`last_hourly_outcome: "success"`)
- [ ] After cron runs, `/health` shows updated `last_hourly_run_utc`
- [ ] DuckDB file appears on the volume (`ls -lh /data/` from API server shell)

---

# PART 2: VERCEL (Python Serverless)

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-74ecabd2462c.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="overview-1"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e22ec59e46bc.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Overview
</h2>

Vercel can run the FastAPI API as a **serverless function**. This is a lightweight alternative to Northflank/Render — suitable for demo/development but with **significant limitations**:

| Limitation | Detail |
|------------|--------|
| Function timeout | 60s max (Hobby), 900s max (Pro) |
| Memory | 1 GB (Hobby), 5 GB (Pro) |
| Bundle size | 500 MB uncompressed |
| Persistent storage | **None** — DuckDB must be read-only or use external storage |
| Cold start | 5–15s for Python + DuckDB load |

**Verdict:** Vercel is viable for **read-only** API access to a pre-seeded DuckDB bundled in the repo. It cannot run the ingestion pipeline (too slow, no persistence). Use it as a fallback/status endpoint.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-39164435e4b0.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="21-project-structure"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-d57309e9a53d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2.1 Project Structure
</h2>

```
MandiIQ/
├── api/
│   └── index.py          # Vercel serverless entrypoint (FastAPI app wrapped for ASGI)
├── vercel.json           # Vercel configuration
├── requirements.txt      # Dependencies
├── .python-version       # Python version pin
└── ...rest of repo
```

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-64083f9b218a.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="22-the-asgi-wrapper-apiindexpy"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e246b7163f05.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2.2 The ASGI Wrapper (`api/index.py`)
</h2>

Vercel's Python runtime automatically detects a named `app` instance in `api/index.py`. Create this file:

```python
# api/index.py — Vercel serverless entrypoint
# Vercel uses this as the ASGI handler automatically

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so mandi_rdd imports work
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

# ── Critical: tell MandiIQ to use the bundled (read-only) DuckDB ──
import os
os.environ.setdefault(
    "MANDIIQ_DB_PATH",
    str(_root / "mandi_rdd" / "data" / "mandi_iq.duckdb")
)

# Import the real FastAPI app
from mandi_rdd.api.main import app

# Vercel requires the instance to be named 'app' at module scope
# (already satisfied — FastAPI creates 'app')
```

**Important:** Vercel's Python runtime uses its own internal ASGI server wrapper. You do **not** import or call `uvicorn`. The `app` instance is used directly.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-a130f96a3d15.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="23-verceljson"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2.3 `vercel.json`
</h2>

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "maxDuration": 60,
      "memory": 1024,
      "excludeFiles": "{tests/**,data/**.backup,**/__pycache__/**,**.git/**,**.streamlit/**,scripts/**,mandi_rdd/dashboard/**,mandi_rdd/styles/**,landing/**,docs/**}"
    }
  },
  "crons": [
    {
      "path": "/api/cron/keepalive",
      "schedule": "0 */4 * * *"
    }
  ]
}
```

**Key details:**
- `maxDuration: 60` — maximum for Hobby plan; Pro can go to 900s
- `memory: 1024` — 1 GB for Hobby; Pro can go to 5 GB
- `excludeFiles` — strips tests, backups, Streamlit dashboard, static pages from the bundle (critical for keeping under the 500 MB limit)

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-a4b3c8aa44d6.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="24-python-version"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2.4 Python Version
</h2>

Create `.python-version` at repo root:

```
3.12
```

Vercel supports Python 3.9–3.14. Streamlit Cloud uses 3.11 from `runtime.txt`. Pin 3.12 for Vercel to get the best cold-start performance.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-ee41fa0ceea0.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="25-requirementstxt-for-vercel"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2.5 `requirements.txt` for Vercel
</h2>

Use a **minimal** requirements file — strip Streamlit, Prophet, xgboost, and other heavy deps that aren't needed for the read-only API:

```txt
# Vercel-optimized requirements — read-only API only
fastapi>=0.110.0
pydantic>=2.0.0
duckdb>=0.8.0
pandas>=1.5.0
numpy>=1.24.0
scipy>=1.11.0
requests>=2.28.0
```

**Keep under 200 MB total bundle size.** The DuckDB file itself (132 MB via Git LFS) + Python deps (~100 MB) + app code (~10 MB) = ~242 MB. This fits comfortably under the 500 MB limit.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-9bfc8c8cc8b3.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="26-duckdb-on-vercel-read-only-approach"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-a0c60dd90fca.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2.6 DuckDB on Vercel — Read-Only Approach
</h2>

Since Vercel functions are **stateless and ephemeral**, the DuckDB must be:
1. **Bundled in the deployment** (via Git LFS — already set up)
2. **Opened in read-only mode** to prevent accidental writes

The app already handles this gracefully — the `/health` endpoint reads from the DuckDB at `MANDIIQ_DB_PATH`. On Vercel, this path points to the bundled file in the function's ephemeral filesystem.

**What works on Vercel:**
- `GET /health` — full data counts
- `GET /prices?commodity=Onion` — price queries
- `GET /rdd-result/{commodity}` — cached RDD results
- `GET /forecast/{commodity}` — cached forecasts
- `GET /risk-score/{commodity}` — XGBoost risk scores (if XGBoost is installed)

**What does NOT work on Vercel:**
- `POST /refresh` — pipeline takes > 60s
- `POST /ask` — AI orchestrator may timeout
- `GET /pipeline.svg` — mermaid-cli not available
- Any endpoint that writes to the DuckDB

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-672211b064be.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="27-deploy-to-vercel"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-bee2875cc587.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2.7 Deploy to Vercel
</h2>

### Option A: Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy from repo root
vercel --prod

# Set env vars
vercel env add MANDIIQ_DB_PATH
vercel env add DATA_GOV_IN_API_KEY
# ... etc
```

### Option B: Vercel Dashboard

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import `flawsom/test-mandi`
3. Framework preset: **Other** (not FastAPI — the auto-detection only works for simple projects)
4. Root directory: `./`
5. Build command: *leave empty*
6. Output directory: *leave empty*

### Option C: GitHub Actions (Recommended)

Create `.github/workflows/deploy-vercel.yml`:

```yaml
name: Deploy API to Vercel

on:
  push:
    branches: [master]
    paths:
      - "api/**"
      - "mandi_rdd/api/**"
      - "mandi_rdd/storage/**"
      - "requirements/api.txt"
      - "vercel.json"
      - ".github/workflows/deploy-vercel.yml"
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Vercel CLI
        run: npm i -g vercel
      - name: Pull Vercel environment
        run: vercel pull --yes --environment=production --token=${{ secrets.VERCEL_TOKEN }}
      - name: Build
        run: vercel build --prod --token=${{ secrets.VERCEL_TOKEN }}
      - name: Deploy
        run: vercel deploy --prebuilt --prod --token=${{ secrets.VERCEL_TOKEN }}
```

Set `VERCEL_TOKEN` in GitHub secrets.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-dd24d242c628.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="28-vercel-verification-checklist"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-5fc91c87ca3d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2.8 Vercel Verification Checklist
</h2>

- [ ] `vercel dev` runs locally without errors
- [ ] `GET /health` returns 200 on Vercel deployment URL
- [ ] `GET /prices?commodity=Onion&limit=5` returns data
- [ ] Bundle size < 500 MB (check Vercel deployment logs)
- [ ] Cold start < 15s
- [ ] `/api/cron/keepalive` runs on schedule (Pro only)

---

# PART 3: STREAMLIT CLOUD

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-b350e4823cc5.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="overview-2"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e22ec59e46bc.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Overview
</h2>

Streamlit Community Cloud hosts the interactive dashboard (`mandi_rdd/dashboard/app.py`). It connects to the Northflank/Render API server for live data.

**Architecture:**
```
User Browser → Streamlit Cloud (dashboard UI)
                        ↕ HTTP / REST
              Northflank / Render (API server + DuckDB)
```

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-f49ec25352f2.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="31-prerequisites"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 3.1 Prerequisites
</h2>

- [ ] A [Streamlit Cloud](https://streamlit.io/cloud) account (GitHub OAuth)
- [ ] The API server already deployed (Northflank or Render) with a reachable URL
- [ ] All API keys ready for the secrets file

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-b53c27cb21fd.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="32-deploy-via-streamlit-dashboard"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-bee2875cc587.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 3.2 Deploy via Streamlit Dashboard
</h2>

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **"Deploy an app"**
3. Fill in:

| Field | Value |
|-------|-------|
| Repository | `flawsom/test-mandi` |
| Branch | `master` |
| Main file path | `mandi_rdd/dashboard/app.py` |
| Python version | 3.11 (auto-detected from `runtime.txt`) |

4. Click **"Deploy"** — the first build takes 3–8 minutes

### 3.2.1 Dependencies

Streamlit Cloud reads **two** dependency files:

**`mandi_rdd/requirements.txt`** (Python packages):
```
pandas>=1.5.0
numpy>=1.24.0
scipy>=1.11.0
fastapi>=0.110.0
streamlit==1.59.2
plotly==6.9.0
requests>=2.28.0
duckdb>=0.8.0
xgboost>=2.0.0
shap>=0.41.0
scikit-learn>=1.3.0
openai>=1.0.0
```

**`mandi_rdd/packages.txt`** (system packages — one per line):
```
git
```

> **Why git?** It's required by the app to run `git log` for version info and for Git LFS operations during startup. Streamlit Cloud runs Debian, so packages are installed via `apt-get`.

> **Note on Prophet:** Prophet is listed in the requirements but installing it on Streamlit Cloud's free tier can OOM the build. If the forecast page isn't needed, remove `prophet>=1.1.0` from the requirements to save ~200 MB.

### 3.2.2 Secrets (`.streamlit/secrets.toml`)

Streamlit Cloud does NOT read `secrets.toml` from the repo (this would be a security risk). Instead, paste the contents into:

**Streamlit Dashboard → App → Settings → Secrets**

```toml
# MandiIQ Streamlit Secrets
# API server URL — points to your Northflank or Render deployment
MANDIQ_API_URL = "https://p01--mandiiq--zbvjrztgjqgw.code.run"

# AI API keys (optional — used by Ask MandiIQ feature)
OPENROUTER_API_KEY = "sk-or-v1-..."
GEMINI_API_KEY = "..."

# Data.gov.in (optional — used for rainfall fetch)
ALL_INDIA_RAINFALL_API_KEY = "YOUR_API_KEY_HERE"
ALL_INDIA_RAINFALL_RESOURCE_ID = "..."

# API key for data.gov.in (same as above)
DATA_GOV_IN_API_KEY = "YOUR_API_KEY_HERE"   # Get from https://api.data.gov.in/
```

### 3.2.3 The `runtime.txt`

Already exists at repo root:

```
3.11
```

Streamlit Cloud only supports Python 3.9–3.11 on the free tier (as of 2026). The DuckDB Python bindings require ≥3.9 on Linux, and we need 3.11 for the latest pandas/numpy features that the dashboard uses.

### 3.2.4 Make the app public (remove the login wall)

**Symptom:** anonymous visitors hitting your app URL are redirected to `share.streamlit.io/-/auth/app` (or a `/-/login` page) instead of seeing the dashboard. That 303 redirect means the app is **private** — Streamlit Community Cloud defaults new apps to private, and only the owner (and people they invite) can view them.

**Fix — flip the visibility toggle once, in the Streamlit Cloud dashboard:**

1. Go to [share.streamlit.io](https://share.streamlit.io) → open your app.
2. Click the app's **⋮ (three-dot / overflow) menu** in the top-right of the app toolbar.
3. Click **Settings**.
4. Scroll to the **Visibility / access** section (or **General → App access**) and toggle **"Make this app public"** to **ON**.
5. Confirm the save. The URL now loads for anyone without a login prompt.

> **Verify:** `curl -sI https://your-app.streamlit.app/` should return `HTTP/1.1 200` — if it returns `303 See Other` with a `location: .../-/auth/app...`, the app is still private.

### 3.2.5 DuckDB fallback on Streamlit Cloud

The dashboard reads the DuckDB via `get_connection()` in `mandi_rdd/storage/duckdb_store.py`. Streamlit Cloud has **no `/data` volume**, so an env var like `MANDIIQ_DB_PATH=/data/mandi_iq.duckdb` points at a path that does not exist. The storage layer handles this automatically via `resolve_db_path()`:

1. If `MANDIIQ_DB_PATH` exists **and** is a real DB file → use it.
2. Else if the git-LFS-pulled repo DB (`mandi_rdd/data/mandi_iq.duckdb`) exists → **fall back to it** (this is what keeps the deployed dashboard working).
3. Else return the configured path so callers raise a clear "database does not exist" error (and the R2 bootstrap can try to recover it).

The fallback logs a `WARNING` naming both paths, so a failing deployment is diagnosable from the app logs instead of showing a bare `Cannot open database` error. Because the repo DB is fetched via Git LFS, make sure the build pulls it — Streamlit Cloud does run the LFS smudge filter on tracked files, but it can fail (the actual build logs showed `Smudge error ... git@github.com: Permission denied` / `smudge filter lfs failed`). If that happens, `mandi_rdd/data/mandi_iq.duckdb` stays a ~100-byte pointer and the fallback treats it as missing — re-trigger a redeploy, or seed the repo DB object via the R2 bootstrap, to recover.

### 3.2.6 Symptom: `ModuleNotFoundError` for `plotly` at app start

**Symptom:** the app page shows `ModuleNotFoundError` (message redacted) with a traceback ending at `mandi_rdd/dashboard/plotly_theme.py, line 10, in <module> import plotly.graph_objects as go`. The dashboard hard-requires plotly at module load, and Streamlit Cloud can deploy with a **partial or cached dependency environment** where plotly never installed.

**Root cause (most common):** the app's **"Python requirements file"** setting in the Streamlit Cloud dashboard points at the wrong file. The repo ships three requirements files:

| File | Contains plotly? | Used by |
|------|------------------|---------|
| `mandi_rdd/requirements.txt` | ✅ `plotly==6.9.0` | **Streamlit Cloud** (set this as the requirements file) |
| `requirements.txt` (root) | ✅ `plotly==6.9.0` | local dev / generic |
| `requirements-vercel.txt` | ❌ no plotly | **Vercel only** — Vercel copies it over `requirements.txt` during build |

If the Streamlit app's requirements-file setting points at `requirements-vercel.txt` (or at any file without plotly), or if a stale build cache skipped plotly, the app crashes at startup.

**Fix:**
1. Streamlit Cloud → app → **Settings → General** → set **"Python requirements file"** to **`mandi_rdd/requirements.txt`**.
2. Click **Rerun** (or **Rebuild app**) so dependencies install fresh from that file.
3. Verify with `curl -sI https://your-app.streamlit.app/` — should return `200` (not the error page).

**App-side guard:** `mandi_rdd/dashboard/app.py` now runs a plotly preflight before any page import — if plotly is missing it renders an actionable error message with the exact fix above instead of the redacted `ModuleNotFoundError` box.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-372bc36c7202.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="33-how-the-dashboard-connects-to-the-api"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e246b7163f05.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 3.3 How the Dashboard Connects to the API
</h2>

The dashboard reads `MANDIQ_API_URL` from secrets and makes HTTP requests to the API server for every data-fetching operation:

```python
# mandi_rdd/dashboard/data_access.py (conceptual flow)
import streamlit as st
import requests

@st.cache_data(ttl=60)  # Cache responses for 60 seconds
def fetch_prices(commodity: str):
    api_url = st.secrets.get("MANDIQ_API_URL", "http://localhost:8000")
    resp = requests.get(f"{api_url}/prices?commodity={commodity}&limit=100")
    return resp.json()
```

**Key behaviors:**
- All API calls are cached with `@st.cache_data(ttl=60)` — the TTL prevents stale data but avoids hammering the API on every rerun
- When the API is unreachable, the dashboard falls back to reading a local DuckDB file (bundled in the deployment using Git LFS)
- The `st.connection` API is NOT used — MandiIQ predates Streamlit's native connections and uses direct `requests` calls instead

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-0fccc7cd9dac.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="34-resource-constraints"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 3.4 Resource Constraints
</h2>

Streamlit Community Cloud free tier:

| Resource | Limit | Impact |
|----------|-------|--------|
| RAM | ~690 MB – 2.7 GB (dynamic) | The dashboard + DuckDB + XGBoost models can exceed 1 GB — **watch for the "<img src="docs/assets/svg/icon-172f1d1c80b4.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Oh no" error** |
| CPU | 0.078 – 2 cores | Prophet training in real-time would OOM — the dashboard only reads pre-computed forecasts |
| Storage | 50 GB | DuckDB is 132 MB — well within limits |
| Hibernation | After 12h of inactivity | App sleeps; first user triggers wake-up (takes 15–30s) |
| Build timeout | 15 minutes | Keep deps minimal to avoid hitting this |

**Mitigation strategies for resource limits:**

1. **If the app goes over memory:**
   - Remove `prophet` from requirements (saves ~150 MB in build)
   - Remove `xgboost` + `shap` if risk scores aren't critical (saves ~100 MB)
   - Reduce DuckDB file size by deleting historical data > 5 years old
   - Use `@st.cache_data(ttl=60)` on ALL API calls (already done)

2. **If the build times out:**
   - Use `mandi_rdd/requirements.txt` and strip optional packages
   - Ensure `packages.txt` has only `git` (no `build-essential`, `gcc`, etc.)

3. **If the app is too slow on wake-up:**
   - Set up a **keepalive** via GitHub Actions (see section 3.6)

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-4cc0d1affa59.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="35-github-actions-keepalive-prevent-hibernation"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 3.5 GitHub Actions Keepalive (Prevent Hibernation)
</h2>

Create `.github/workflows/streamlit-keepalive.yml`:

```yaml
name: Streamlit Keepalive

on:
  schedule:
    # Every 6 hours — Streamlit hibernates after 12h of inactivity
    - cron: "0 */6 * * *"
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Wake Streamlit app
        run: |
          curl -s -o /dev/null -w "%{http_code}" \
            --max-time 60 \
            "https://test-mandi-keae7eruks2n4cqvumjfu8.streamlit.app/" \
            || echo "Wake-up triggered (non-200 is normal for cold start)"
```

This pings the Streamlit app every 6 hours, preventing the 12-hour hibernation. Without this, users face a 15–30s cold start on the first visit after a period of inactivity.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-29f68a47ea1c.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="36-custom-domain-optional"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 3.6 Custom Domain (Optional)
</h2>

Streamlit Cloud supports custom domains on the **Team** plan ($30/month). For Hobby users, the deployment URL is `https://<app-name>.streamlit.app`.

To add a custom domain on a paid plan:

1. **Streamlit Dashboard → App → Settings → Custom Domain**
2. Enter your custom domain (e.g. `dashboard.mandiiq.in`)
3. Add a `CNAME` record in your DNS provider:
   ```
   dashboard.mandiiq.in → test-mandi-keae7eruks2n4cqvumjfu8.streamlit.app
   ```
4. Wait for DNS propagation (5–30 minutes)
5. Streamlit auto-provisions an SSL certificate via Let's Encrypt

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-cb3305c82394.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="37-streamlit-verification-checklist"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-5fc91c87ca3d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 3.7 Streamlit Verification Checklist
</h2>

- [ ] Dashboard deploys without build errors
- [ ] `MANDIQ_API_URL` secret is set correctly
- [ ] Dashboard loads without "Oh no" memory error
- [ ] KPI cards show live data from API (not `—`)
- [ ] `@st.cache_data(ttl=60)` is applied to API-fetch functions
- [ ] Keepalive workflow is configured (if preventing hibernation matters)
- [ ] Custom domain DNS is configured (if applicable)

---

# PART 4: CONFIGURATION FILES REFERENCE

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-aad100c1898b.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="41-dockerfilenorthflank-api-server"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-bee2875cc587.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 4.1 `Dockerfile.northflank` (API Server)
</h2>

```dockerfile
# Location: ./Dockerfile.northflank
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @mermaid-js/mermaid-cli --omit=optional \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/api.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY mandi_rdd/ /app/mandi_rdd/
COPY data/ /app/data/
COPY dashboards/ /app/dashboards/
ENV PYTHONPATH=/app
ENV PORT=8080
ENV MANDIIQ_DB_PATH=/data/mandi_iq.duckdb
EXPOSE 8080
CMD ["uvicorn", "mandi_rdd.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-ec33afba8732.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="42-dockerfilecronjob-northflank-cron"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-d57309e9a53d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 4.2 `Dockerfile.cronjob` (Northflank Cron)
</h2>

```dockerfile
# Location: ./Dockerfile.cronjob
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/api.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt httpx>=0.27.0 python-dotenv>=1.0.0
COPY mandi_rdd/ /app/mandi_rdd/
COPY data/ /app/data/
COPY run_hourly.py /app/
ENV PYTHONPATH=/app
ENV MANDIIQ_DB_PATH=/data/mandi_iq.duckdb
CMD ["python", "run_hourly.py"]
```

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-7093dec6d46f.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="43-apiindexpy-vercel"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e246b7163f05.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 4.3 `api/index.py` (Vercel)
</h2>

```python
# Location: ./api/index.py
import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
import os
os.environ.setdefault(
    "MANDIIQ_DB_PATH",
    str(_root / "mandi_rdd" / "data" / "mandi_iq.duckdb")
)
from mandi_rdd.api.main import app
```

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-25252116a5b3.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="44-verceljson"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 4.4 `vercel.json`
</h2>

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "maxDuration": 60,
      "memory": 1024,
      "excludeFiles": "{tests/**,data/**.backup,**/__pycache__/**,**.git/**,**.streamlit/**,scripts/**,mandi_rdd/dashboard/**,mandi_rdd/styles/**,landing/**,docs/**}"
    }
  }
}
```

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-192b1adf5aa2.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="45-renderyaml-render-blueprint-existing"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 4.5 `render.yaml` (Render Blueprint — existing)
</h2>

```yaml
services:
  - type: web
    name: mandiiq-api
    runtime: python
    plan: free
    region: oregon
    branch: master
    buildCommand: |
      git lfs install
      git lfs pull --include 'mandi_rdd/data/mandi_iq.duckdb' --exclude=''
      pip install -r requirements/api.txt
    startCommand: uvicorn mandi_rdd.api.main:app --host 0.0.0.0 --port $PORT --workers 1
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: PYTHON_VERSION
        value: "3.11"
      - key: MANDIIQ_DB_PATH
        value: mandi_rdd/data/mandi_iq.duckdb
      - key: PORT
        value: "8000"
      - key: DATA_GOV_IN_API_KEY
        sync: false   # Set in Render Dashboard — get your key from https://api.data.gov.in/
```

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-ce95290f4ec1.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="46-streamlitsecretstoml-template"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-62349b00e07f.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 4.6 `.streamlit/secrets.toml` Template
</h2>

```toml
# Location: .streamlit/secrets.toml.template (DO NOT commit actual secrets)
# Copy to .streamlit/secrets.toml for local dev
# For production, paste into Streamlit Cloud Settings → Secrets

MANDIQ_API_URL = "https://p01--mandiiq--zbvjrztgjqgw.code.run"
OPENROUTER_API_KEY = ""
GEMINI_API_KEY = ""
ALL_INDIA_RAINFALL_API_KEY = ""
ALL_INDIA_RAINFALL_RESOURCE_ID = ""
DATA_GOV_IN_API_KEY = ""
```

---

# PART 5: PLATFORM COMPARISON

| Feature | Northflank | Vercel | Streamlit Cloud |
|---------|-----------|--------|-----------------|
| **What to run** | API server + cron | Read-only API (optional) | Dashboard only |
| **Cost (free tier)** | 2 services, 1 GB volume | Unlimited serverless functions | 1 public app |
| **Python version** | 3.12 (Docker) | 3.9–3.14 | 3.11 |
| **Persistent storage** | <img src="docs/assets/svg/icon-dfc9746e71ac.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> 1 GB free volume | <img src="docs/assets/svg/icon-486d0accc0a6.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Ephemeral only | <img src="docs/assets/svg/icon-486d0accc0a6.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Ephemeral only |
| **Run time limit** | None (web service) | 60s (Hobby), 900s (Pro) | None (but hibernates) |
| **Cron / scheduled jobs** | <img src="docs/assets/svg/icon-dfc9746e71ac.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Native cron service | <img src="docs/assets/svg/icon-dfc9746e71ac.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Vercel Crons (Pro) | <img src="docs/assets/svg/icon-486d0accc0a6.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Not supported |
| **Git LFS** | <img src="docs/assets/svg/icon-dfc9746e71ac.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Manual install in Docker | <img src="docs/assets/svg/icon-dfc9746e71ac.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Automatic | <img src="docs/assets/svg/icon-486d0accc0a6.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Must bundle in Git |
| **Custom domain** | <img src="docs/assets/svg/icon-dfc9746e71ac.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Yes | <img src="docs/assets/svg/icon-dfc9746e71ac.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Yes (free) | <img src="docs/assets/svg/icon-dfc9746e71ac.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Team plan only |
| **Cold start** | None (always-on) | 5–15s | 15–30s (after hibernation) |
| **Best for** | Production API | Read-only fallback | Dashboard hosting |

---

# PART 6: TROUBLESHOOTING MATRIX

| Symptom | Platform | Root Cause | Fix |
|---------|----------|-----------|-----|
| Container keeps restarting | Northflank | OOM (512 MB limit) | Reduce workers to 1, remove heavy deps from Dockerfile |
| `/health` returns stale data | Northflank | Cron volume ≠ API volume | Verify both mount `mandiiq-data` |
| "<img src="docs/assets/svg/icon-172f1d1c80b4.svg" width="20" height="20" alt="" style="vertical-align:middle; max-width:100%;" /> Oh no" error | Streamlit Cloud | Out of memory | Reduce dependencies, stop heavy imports |
| Build timeout | Streamlit Cloud | Too many deps | Strip Prophet, xgboost from requirements |
| 504 Gateway Timeout | Vercel | Function exceeds maxDuration | Increase in vercel.json, or simplify the endpoint |
| DuckDB file shows Git pointers | Any | LFS not pulled during build | Add `git lfs pull` to build command |
| CORS error in dashboard | Streamlit Cloud | API server blocks cross-origin | Ensure `allow_origins=["*"]` in FastAPI CORS middleware |
| CSS not loading | Streamlit Cloud | Runtime upgrade changed class names | Pin Streamlit version: `streamlit==1.59.2` |
| `n_prices = 0` | Northflank | DuckDB is empty on new volume | Run pipeline manually: `python run_hourly.py --force-full` |
| Cron job never runs | Northflank | Schedule syntax wrong | Use `0 * * * *` (not `* * * * *`) for hourly |
| Deployment shows "No Git repo" | Vercel | Missing `.vercel` directory | Run `vercel link` from repo root |

---

# PART 7: QUICK-START SUMMARY

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-0b1dcd987a30.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="the-shortest-path-to-production"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-bee2875cc587.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> The shortest path to production:
</h2>

```bash
# 1. Push to GitHub
git push origin master

# 2. Deploy API to Northflank
#    - Go to app.northflank.com → Create Web Service
#    - Dockerfile: Dockerfile.northflank
#    - Port: 8080
#    - Volume: /data (1 GB)
#    - Set env vars (DATA_GOV_IN_API_KEY, etc.)

# 3. Deploy Dashboard to Streamlit Cloud
#    - Go to share.streamlit.io
#    - Repo: flawsom/test-mandi
#    - Main file: mandi_rdd/dashboard/app.py
#    - Set secrets (MANDIQ_API_URL, API keys)

# 4. Set up hourly cron on Northflank
#    - Create Cron Job service
#    - Dockerfile: Dockerfile.cronjob
#    - Schedule: 0 * * * *
#    - Mount SAME volume: mandiiq-data → /data

# 5. Verify all endpoints
curl https://p01--mandiiq--zbvjrztgjqgw.code.run/health
# → {"status":"healthy","n_prices":1334647,...}

# 6. (Optional) Deploy Vercel as read-only fallback
vercel --prod
```

---

*Generated: July 2026 • MandiIQ v2.0.0*

</div></div></div>

<div align="center">
<br />
<a href="#" style="display:inline-block; padding:8px 20px; border-radius:10px; background:linear-gradient(135deg, rgba(0,255,136,0.12) 0%, rgba(0,255,136,0.04) 100%); border:1px solid rgba(0,255,136,0.2); color:#00FF88; font-weight:500; text-decoration:none; font-size:14px;">&#x2191; Back to Top</a>
<br /><br />
</div>