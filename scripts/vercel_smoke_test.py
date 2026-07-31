"""Vercel deploy smoke test — parse /health JSON and check n_prices.

Usage:
    python scripts/vercel_smoke_test.py <URL>

Returns exit code 0 if /health returns 200 with n_prices >= 1,000,000.
"""
import json
import sys
import urllib.request

url = sys.argv[1].rstrip("/") + "/health"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "MandiIQ/smoke-test"})
    with urllib.request.urlopen(req, timeout=55) as resp:
        body = resp.read().decode()
        parsed = json.loads(body)
except Exception as e:
    print(f"SMOKE_FAIL: {e}")
    sys.exit(1)

n_prices = parsed.get("n_prices", -1)
if n_prices >= 1_000_000:
    print(f"OK: n_prices={n_prices}")
    sys.exit(0)
else:
    print(f"SMOKE_FAIL: n_prices={n_prices} (expected >= 1,000,000)")
    sys.exit(1)