<div align="center" style="position:relative; overflow:hidden; border-radius:20px; background:linear-gradient(135deg, #0B0F1E 0%, #0F1F15 40%, #0B0F1E 100%); padding:44px 20px 36px; margin-bottom:8px; border:1px solid rgba(0,255,136,0.08);">

<div style="position:absolute; top:-120px; left:50%; transform:translateX(-50%); width:600px; height:300px; background:radial-gradient(ellipse, rgba(0,255,136,0.12) 0%, transparent 70%); pointer-events:none;"></div>
<div style="position:absolute; top:0; left:10%; right:10%; height:1px; background:linear-gradient(90deg, transparent, rgba(0,255,136,0.5), transparent);"></div>

<div style="position:relative; z-index:1;">
<h1 style="margin:0; font-size:2.2em; font-weight:700; color:#E0E0E0; letter-spacing:-0.5px;">
  <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#00FF88" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M12 2v18"/><path d="M8 6c0-2 4-4 4 0"/><path d="M16 6c0-2-4-4-4 0"/><path d="M8 12c0-2 4-4 4 0"/><path d="M16 12c0-2-4-4-4 0"/><path d="M6 18c0-3 6-5 6 0"/><path d="M18 18c0-3-6-5-6 0"/><path d="M9 22h6"/></svg>
  Northflank Deployment Configuration
</h1>
<h4 style="color:#94A3B8; font-weight:400; font-size:0.95em; margin:6px 0 0 0;">MandiIQ Documentation</h4>
</div>

</div>
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>


# - PYTHONPATH=/app
# - PORT=8080
# - MANDIIQ_DB_PATH=/data/mandi_iq.duckdb
# - DATA_GOV_IN_API_KEY=YOUR_API_KEY_HERE   # Get from https://api.data.gov.in/
# - GEMINI_API_KEY (optional)
# - NVIDIA_API_KEY (optional)
# - OPENROUTER_API_KEY (optional)
# - GRAFANA_CLOUD_PROM_URL (optional)
# - GRAFANA_CLOUD_PROM_USER (optional)
# - GRAFANA_CLOUD_PROM_PASSWORD (optional)
# - R2_ACCOUNT_ID=your_r2_account_id
# - R2_ACCESS_KEY_ID=your_r2_access_key_id
# - R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
# - R2_BUCKET=mandiiq-data

# Persistent Volume:
# - Name: mandiiq-data
# - Mount path: /data
# - Size: 1 GB (free tier includes 1GB)

# Health check:
# - Path: /health
# - Port: 8080
# - Interval: 30s
# - Timeout: 10s

# Resources (free tier):
# - 512 MB RAM
# - 1 vCPU
# - 1 replica


# ═══════════════════════════════════════════════
# HOURLY INGESTION CRON JOB (Northflank Cron Job)
# ═══════════════════════════════════════════════
#
# Dockerfile: Dockerfile.cronjob  (separate from the API server's Dockerfile)
#
# Runs every hour to fetch fresh mandi prices from data.gov.in.
# Smart: quick price-only fetch (~30s) every hour, full analysis
# (RDD + FE + Forecast + NDVI) only once every 24 hours.
# Writes to the same Persistent Volume (/data) as the API server.
#
# Setup in Northflank UI:
#
# 1. Create a new service -> "Cron Job" type
#    - Name: mandiiq-hourly-ingest
#    - Schedule: 0 * * * *  (every hour at minute 0)
#
# 2. Build settings:
#    - Build context: .
#    - Dockerfile: Dockerfile.cronjob
#
# 3. Persistent Volume:
#    - Name: mandiiq-data
#    - Mount path: /data
#    - This MUST be the SAME volume as the API server's
#      so they share the same DuckDB file
#
# 4. Environment variables (set these):
#    - PYTHONPATH=/app
#    - MANDIIQ_DB_PATH=/data/mandi_iq.duckdb
#    - DATA_GOV_IN_API_KEY=your_key_here
#    - SENTINEL_CLIENT_ID (optional, for NDVI)
#    - SENTINEL_CLIENT_SECRET (optional, for NDVI)
#    - GEMINI_API_KEY (optional, for AI narratives)
#    - OPENROUTER_API_KEY (optional, for AI narratives)
#    - NVIDIA_API_KEY (optional, for AI narratives)
#
# 5. Resources: same as API server
#    - 512 MB RAM
#    - 1 vCPU
#    - 1 replica (cron jobs always run 1 at a time)
#
# To test the cron job manually (local):
#   python run_hourly.py
#
# To force a full analysis run (not just price fetch):
#   python run_hourly.py --force-full
#
# ⚠️ IMPORTANT: The cron job container and the API server container
#    must mount the EXACT SAME Persistent Volume at /data.
#    If they use separate volumes, the cron job will write to a
#    DuckDB that the API server never sees. Verify in the Northflank
#    dashboard that both services reference "mandiiq-data" as the
#    volume source.
</div></div></div>

<div align="center">
<br />
<a href="#" style="display:inline-block; padding:8px 20px; border-radius:10px; background:linear-gradient(135deg, rgba(0,255,136,0.12) 0%, rgba(0,255,136,0.04) 100%); border:1px solid rgba(0,255,136,0.2); color:#00FF88; font-weight:500; text-decoration:none; font-size:14px;">&#x2191; Back to Top</a>
<br /><br />
</div>