<div align="center" style="position:relative; overflow:hidden; border-radius:20px; background:linear-gradient(135deg, #0B0F1E 0%, #0F1F15 40%, #0B0F1E 100%); padding:44px 20px 36px; margin-bottom:8px; border:1px solid rgba(0,255,136,0.08);">

<div style="position:absolute; top:-120px; left:50%; transform:translateX(-50%); width:600px; height:300px; background:radial-gradient(ellipse, rgba(0,255,136,0.12) 0%, transparent 70%); pointer-events:none;"></div>
<div style="position:absolute; top:0; left:10%; right:10%; height:1px; background:linear-gradient(90deg, transparent, rgba(0,255,136,0.5), transparent);"></div>

<div style="position:relative; z-index:1;">
<h1 style="margin:0; font-size:2.2em; font-weight:700; color:#E0E0E0; letter-spacing:-0.5px;">
  <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#00FF88" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M12 2v18"/><path d="M8 6c0-2 4-4 4 0"/><path d="M16 6c0-2-4-4-4 0"/><path d="M8 12c0-2 4-4 4 0"/><path d="M16 12c0-2-4-4-4 0"/><path d="M6 18c0-3 6-5 6 0"/><path d="M18 18c0-3-6-5-6 0"/><path d="M9 22h6"/></svg>
  Contributing To Mandiiq
</h1>
<h4 style="color:#94A3B8; font-weight:400; font-size:0.95em; margin:6px 0 0 0;">MandiIQ Documentation</h4>
</div>

</div>
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>

Thanks for your interest in MandiIQ. This document covers the things a first-time
contributor needs to know — especially the repo conventions that aren't obvious
from the code alone.

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <svg viewBox="0 0 1440 60" width="100%" height="60" preserveAspectRatio="none" style="position:absolute;bottom:0;">
    <defs>
      <linearGradient id="wg-1" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#0B0F1E" stop-opacity="0" />
        <stop offset="25%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="50%" stop-color="#00FF88" stop-opacity="0.4" />
        <stop offset="75%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#0B0F1E" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d="M0,30 C240,10 480,50 720,30 C960,10 1200,50 1440,30 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.6" />
    <path d="M0,40 C240,25 480,55 720,40 C960,25 1200,55 1440,40 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.3" />
  </svg>
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="canonical-remote"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> Canonical remote
</h2>

The canonical remote for this repository is **`origin`** and it must point at:

```
https://github.com/flawsom/MandiIQ.git
```

Verify before pushing:

```bash
git remote -v
# origin  https://github.com/flawsom/MandiIQ.git (fetch/push)
```

If `origin` points anywhere else (e.g. a `Margin-Intelligence-System` repo), fix it:

```bash
git remote set-url origin https://github.com/flawsom/MandiIQ.git
```

Any other repository (a separate project, a fork you maintain) should use a
**distinct remote name** such as `margin-intelligence` or `fork` — never leave an
unrelated repo as `origin` in a MandiIQ working copy.

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <svg viewBox="0 0 1440 60" width="100%" height="60" preserveAspectRatio="none" style="position:absolute;bottom:0;">
    <defs>
      <linearGradient id="wg-2" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#0B0F1E" stop-opacity="0" />
        <stop offset="25%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="50%" stop-color="#00FF88" stop-opacity="0.4" />
        <stop offset="75%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#0B0F1E" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d="M0,30 C240,10 480,50 720,30 C960,10 1200,50 1440,30 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.6" />
    <path d="M0,40 C240,25 480,55 720,40 C960,25 1200,55 1440,40 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.3" />
  </svg>
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="data-storage-decision-prd-phase-6-external-store"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg> Data storage decision (PRD Phase 6 — external store)
</h2>

The ingestion pipeline writes its DuckDB database to `mandi_rdd/data/mandi_iq.duckdb`
by default. The path is configurable via the `MANDIIQ_DB_PATH` environment variable
so the database can instead live in an external object store (R2/S3/GCS) or mounted
persistent storage.

**Decision:** we prefer keeping the database **out of git** (PRD Phase 6, option A).
The daily ingestion workflow uploads the refreshed DB to an external store (R2) when
`R2_BUCKET` + credentials are configured as repository secrets. Until those secrets
exist, the workflow falls back to committing the DB to `master` (with a log warning)
so the project still works for a single-owner portfolio deployment.

This is a deliberate tradeoff: a binary committed daily grows history, but it keeps
the demo self-contained without an external account. If you add R2 credentials to
the repo secrets, the git-commit fallback is no longer used.

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <svg viewBox="0 0 1440 60" width="100%" height="60" preserveAspectRatio="none" style="position:absolute;bottom:0;">
    <defs>
      <linearGradient id="wg-3" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#0B0F1E" stop-opacity="0" />
        <stop offset="25%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="50%" stop-color="#00FF88" stop-opacity="0.4" />
        <stop offset="75%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#0B0F1E" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d="M0,30 C240,10 480,50 720,30 C960,10 1200,50 1440,30 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.6" />
    <path d="M0,40 C240,25 480,55 720,40 C960,25 1200,55 1440,40 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.3" />
  </svg>
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="ingestion-automation-branch-protection-prd-phase-8"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> Ingestion automation & branch protection (PRD Phase 8)
</h2>

The nightly ingestion runs as a GitHub Actions schedule (`0 6 * * *`). Its commits
**do not** use `[skip ci]`, so the normal quality gates (test suite + no-mock-data
check) still run against them.

**Branch protection decision (PRD Phase 8, option A):** when `master` is put behind
branch protection for external PRs, the ingestion bot's `GITHUB_TOKEN` actor should
be **exempted** from the protection rules (GitHub supports this). The real gate is the
data-integrity / no-mock-data check that runs on every bot commit — not human review
of automated data commits.

> Turn this on *after* the exemption is configured, not before — enabling protection
> first will silently break the scheduled workflow.

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <svg viewBox="0 0 1440 60" width="100%" height="60" preserveAspectRatio="none" style="position:absolute;bottom:0;">
    <defs>
      <linearGradient id="wg-4" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#0B0F1E" stop-opacity="0" />
        <stop offset="25%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="50%" stop-color="#00FF88" stop-opacity="0.4" />
        <stop offset="75%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#0B0F1E" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d="M0,30 C240,10 480,50 720,30 C960,10 1200,50 1440,30 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.6" />
    <path d="M0,40 C240,25 480,55 720,40 C960,25 1200,55 1440,40 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.3" />
  </svg>
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="local-setup"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg> Local setup
</h2>

```bash
git clone https://github.com/flawsom/MandiIQ.git
cd MandiIQ
python -m venv .venv && source .venv/bin/activate
pip install -r mandi_rdd/requirements.txt
cp .env.example .env   # set DATA_GOV_IN_API_KEY for live price pulls
```

Run the dashboard:

```bash
streamlit run mandi_rdd/dashboard/app.py
```

Run ingestion manually (same as the CI job):

```bash
python -m mandi_rdd.run_nightly --max-records 5000
```

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <svg viewBox="0 0 1440 60" width="100%" height="60" preserveAspectRatio="none" style="position:absolute;bottom:0;">
    <defs>
      <linearGradient id="wg-5" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#0B0F1E" stop-opacity="0" />
        <stop offset="25%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="50%" stop-color="#00FF88" stop-opacity="0.4" />
        <stop offset="75%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#0B0F1E" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d="M0,30 C240,10 480,50 720,30 C960,10 1200,50 1440,30 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.6" />
    <path d="M0,40 C240,25 480,55 720,40 C960,25 1200,55 1440,40 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.3" />
  </svg>
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="api-keys-secrets"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg> API keys & secrets
</h2>

- `DATA_GOV_IN_API_KEY` — **required** for live price ingestion. A missing or invalid
  key fails the job loudly; there is **no fallback/default key** in the code.
- `GEMINI_API_KEY` / `OPENROUTER_API_KEY` — for the LLM narrative + Ask MandiIQ.
- `OPENMETEO_API_KEY` — optional weather source.

Never commit secrets or a fallback API key.

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <svg viewBox="0 0 1440 60" width="100%" height="60" preserveAspectRatio="none" style="position:absolute;bottom:0;">
    <defs>
      <linearGradient id="wg-6" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#0B0F1E" stop-opacity="0" />
        <stop offset="25%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="50%" stop-color="#00FF88" stop-opacity="0.4" />
        <stop offset="75%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#0B0F1E" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d="M0,30 C240,10 480,50 720,30 C960,10 1200,50 1440,30 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.6" />
    <path d="M0,40 C240,25 480,55 720,40 C960,25 1200,55 1440,40 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.3" />
  </svg>
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="tests"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M14 2H10"/><path d="M12 2v10"/><path d="M9 10a4 4 0 0 0 6 0"/><path d="M14 6a4 4 0 0 1 0-4"/><path d="M6 18a4 4 0 0 0 4 4h4a4 4 0 0 0 4-4"/></svg> Tests
</h2>

```bash
python -m pytest mandi_rdd/tests/ -q
```

The suite includes `test_no_mock_data.py` (fails the build if any mock/fabricated
data appears) and `test_scheduler_integrity.py` (missing-key-fail, idempotency,
no-`[skip ci]` on the ingest commit).

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <svg viewBox="0 0 1440 60" width="100%" height="60" preserveAspectRatio="none" style="position:absolute;bottom:0;">
    <defs>
      <linearGradient id="wg-7" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#0B0F1E" stop-opacity="0" />
        <stop offset="25%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="50%" stop-color="#00FF88" stop-opacity="0.4" />
        <stop offset="75%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#0B0F1E" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d="M0,30 C240,10 480,50 720,30 C960,10 1200,50 1440,30 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.6" />
    <path d="M0,40 C240,25 480,55 720,40 C960,25 1200,55 1440,40 L1440,60 L0,60 Z" fill="url(#wg)" opacity="0.3" />
  </svg>
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="authorship-tooling-note"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.78 7.78 5.5 5.5 0 0 1 7.78-7.78zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg> Authorship & tooling note
</h2>

All commits in this repository are authored by **Siba Prasad Panda** (sibaprasadpanda56@gmail.com)
and the nightly ingestion bot (mandiiq-bot). No third-party AI coding assistants are
listed as commit authors or co-authors. Historical references to any such tooling have
been removed from the commit history.

</div></div></div>

<div align="center">
<br />
<a href="#" style="display:inline-block; padding:8px 20px; border-radius:10px; background:linear-gradient(135deg, rgba(0,255,136,0.12) 0%, rgba(0,255,136,0.04) 100%); border:1px solid rgba(0,255,136,0.2); color:#00FF88; font-weight:500; text-decoration:none; font-size:14px;">&#x2191; Back to Top</a>
<br /><br />
</div>