# Northflank deployment configuration for MandiIQ
# Connect your GitHub repo at https://app.northflank.com and create a new service
# Select "Docker" build, point to this repo

# Build settings (in Northflank UI):
# - Build context: .
# - Dockerfile: Dockerfile.northflank
# - Port: 8080

# Environment variables (set in Northflank UI):
# - PYTHONPATH=/app
# - PORT=8080
# - MANDIIQ_DB_PATH=/data/mandi_iq.duckdb
# - DATA_GOV_IN_API_KEY=579b464db66ec23bdd000001ec9b9663040e48184cdb0c4cda06eaf5
# - GEMINI_API_KEY (optional)
# - NVIDIA_API_KEY (optional)
# - OPENROUTER_API_KEY (optional)
# - GRAFANA_CLOUD_PROM_URL (optional)
# - GRAFANA_CLOUD_PROM_USER (optional)
# - GRAFANA_CLOUD_PROM_PASSWORD (optional)
# - R2_ACCOUNT_ID=e27f25b7a13997395e9a17005dc3cf3c
# - R2_ACCESS_KEY_ID=a10ae7518bacda96683e30c28739ce31
# - R2_SECRET_ACCESS_KEY=55abbb6292bd2492e24f5406bf01b0424cbe785289a62bc99f71d65305eaa5a6
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