<div align="center" style="position:relative; overflow:hidden; border-radius:20px; background:linear-gradient(135deg, #0B0F1E 0%, #0F1F15 40%, #0B0F1E 100%); padding:44px 20px 36px; margin-bottom:8px; border:1px solid rgba(0,255,136,0.08);">

<div style="position:absolute; top:-120px; left:50%; transform:translateX(-50%); width:600px; height:300px; background:radial-gradient(ellipse, rgba(0,255,136,0.12) 0%, transparent 70%); pointer-events:none;"></div>
<div style="position:absolute; top:0; left:10%; right:10%; height:1px; background:linear-gradient(90deg, transparent, rgba(0,255,136,0.5), transparent);"></div>

<div style="position:relative; z-index:1;">
<h1 style="margin:0; font-size:2.2em; font-weight:700; color:#E0E0E0; letter-spacing:-0.5px;">
  <img src="docs/assets/svg/icon-f8867c21931f.svg" width="36" height="36" alt="" style="vertical-align:middle; max-width:100%;" />
  Mandiiq Deployment Guide
</h1>
<h4 style="color:#94A3B8; font-weight:400; font-size:0.95em; margin:6px 0 0 0;">MandiIQ Documentation</h4>
</div>

</div>
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="quick-start-4-step-deploy"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-bee2875cc587.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Quick Start (4-Step Deploy)
</h2>

### Step 1: Push code to GitHub ✅ DONE
```bash
git push origin HEAD
```

### Step 2: Deploy API to Render
**Blueprint reads `render.yaml`**

#### Reconnect Blueprint (REQUIRED after repo recreate):
1. Go to https://dashboard.render.com
2. Click **Blueprints** in left sidebar
3. Click **Connect Blueprint** → select `flawsom/MandiIQ`
4. It will auto-detect `render.yaml` and deploy all services
5. ⏳ Wait 2-5 minutes for build

#### Set these Environment Variables in Render Dashboard:
| Variable | Value |
|----------|-------|
| `DATA_GOV_IN_API_KEY` | (your key from data.gov.in) |
| `NVIDIA_API_KEY` | (your key from build.nvidia.com) |
| `GEMINI_API_KEY` | (your key from aistudio.google.com) |
| `OPENROUTER_API_KEY` | (your key from openrouter.ai) |
| `MANDIIQ_DB_PATH` | `mandi_rdd/data/mandi_iq.duckdb` |
| `SENTINEL_CLIENT_ID` | (your Sentinel Hub client ID) |
| `SENTINEL_CLIENT_SECRET` | (your Sentinel Hub secret) |
| `WEBHOOK_SECRET` | (webhook shared secret) |
| `R2_ACCOUNT_ID` | (Cloudflare R2 account ID) |
| `R2_ACCESS_KEY_ID` | (R2 access key) |
| `R2_SECRET_ACCESS_KEY` | (R2 secret key) |
| `R2_BUCKET` | `mandiiq-data` |
| `RENDER_DEPLOY_HOOK_URL` | (create in Render Dashboard → Settings → Deploy Hooks) |
| `ALL_INDIA_RAINFALL_API_KEY` | (same as DATA_GOV_IN_API_KEY) |
| `ALL_INDIA_RAINFALL_RESOURCE_ID` | (rainfall resource ID) |
| `GRAFANA_CLOUD_PROM_URL` | `https://prometheus-prod-43-prod-ap-south-1.grafana.net` |
| `GRAFANA_CLOUD_PROM_USER` | `3400476` |
| `GRAFANA_CLOUD_PROM_PASS` | Grafana Cloud API token (set as GitHub secret) |

### Step 3: Deploy Dashboard to Streamlit Cloud
1. Go to https://share.streamlit.io
2. Click **Deploy an app**
3. Set Repository: `flawsom/MandiIQ`
4. Branch: `master`
5. Main file: `mandi_rdd/dashboard/app.py`
6. Click **Deploy**

#### Set these Secrets in Streamlit Cloud Dashboard:
In Settings → Secrets:
```toml
MANDIQ_API_URL = "https://mandiiq-api.onrender.com"
OPENROUTER_API_KEY = "sk-or-v1-..."
GEMINI_API_KEY = "..."
ALL_INDIA_RAINFALL_API_KEY = "..."
ALL_INDIA_RAINFALL_RESOURCE_ID = "..."
```

### Step 4: Fix Custom Domain
**Option A — Point DNS to Render (easiest):**
Set `CNAME` record for `mandiiq.unifies.codes` → `mandiiq-api.onrender.com`

**Option B — Vercel:**
Add domain in Vercel project settings, deploy a wrapper/proxy

### Step 5: Verify all 4 URLs
- ✅ https://mandiiq-api.onrender.com/health
- ✅ https://mandiiq.streamlit.app
- ❌ https://mandiiq.unifies.codes (needs DNS/deploy)
- ✅ https://github.com/flawsom/MandiIQ

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-4fe945889b5c.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="troubleshooting"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-da4a634619e1.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Troubleshooting
</h2>

| Issue | Fix |
|-------|-----|
| LFS pointer file in DuckDB | Add `git lfs pull` to Render build command |
| OOM on free tier | Never set `--workers` beyond 1 (512 MB limit) |
| GitHub 500 on push | Use SSH: `git remote set-url origin git@github.com:flawsom/MandiIQ.git` |
| Rainfall 403 | Find working data.gov.in resource ID |
| Render deploy hook fails | Set `RENDER_DEPLOY_HOOK_URL` in Render env vars |
| API returns 404 for forecast | Fixed in code — now returns 200 with `"status":"unavailable"` |
| Risk score = 50 always | Need XGBoost installed + pipeline run (`POST /refresh`) |

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-b5297f23fd61.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="github-secrets-for-actions-workflows"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e22ec59e46bc.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> GitHub Secrets (for Actions workflows)
</h2>

Set in: https://github.com/flawsom/MandiIQ/settings/secrets/actions

| Secret | Status |
|--------|--------|
| `OPENROUTER_API_KEY` | ✅ Set (from local env) |
| `DATA_GOV_IN_API_KEY` | ❌ Needs value |
| `GEMINI_API_KEY` | ❌ Needs value |
| `R2_ACCOUNT_ID` | ❌ Needs value |
| `R2_ACCESS_KEY_ID` | ❌ Needs value |
| `R2_SECRET_ACCESS_KEY` | ❌ Needs value |
| `HISTORICAL_SOURCE_URL` | ❌ Needs value |
| `RAINFALL_RESOURCE_ID` | ❌ Needs value |

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
<a name="onboarding-checklist"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-5fc91c87ca3d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Onboarding Checklist
</h2>

### GitHub ✅
- [x] Push code to master
- [x] Verify remote matches local
- [ ] Set GitHub Secrets (Actions tab)

### Render
- [ ] Reconnect Blueprint
- [ ] Verify all env vars
- [ ] Verify API health endpoint

### Streamlit Cloud
- [ ] Deploy dashboard
- [ ] Set secrets
- [ ] Verify loads

### Custom Domain
- [ ] Fix DNS or Vercel deploy
- [ ] Verify HTTPS works

### CI/CD (Optional)
- [ ] Nightly Ingestion workflow
- [ ] Freshness check workflow
- [ ] Render Keepalive workflow

### R2 Backup (Optional)
- [ ] Set R2 env vars
- [ ] Verify backup runs

### NDVI (Optional)
- [ ] Set Sentinel Hub credentials

### Grafana (Optional)
- [ ] Upgrade to starter plan on Render
- [ ] Configure Grafana dashboard

</div></div></div>

<div align="center">
<br />
<a href="#" style="display:inline-block; padding:8px 20px; border-radius:10px; background:linear-gradient(135deg, rgba(0,255,136,0.12) 0%, rgba(0,255,136,0.04) 100%); border:1px solid rgba(0,255,136,0.2); color:#00FF88; font-weight:500; text-decoration:none; font-size:14px;">&#x2191; Back to Top</a>
<br /><br />
</div>