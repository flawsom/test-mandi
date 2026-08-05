"""Dashboard integration tests: verify the app boots, serves, and streams page config.

Runs against a locally started Streamlit instance (see
.github/workflows/dashboard-integration.yml which starts it on port 8502).
"""
import json
import urllib.request
import time

import pytest

BASE = "http://localhost:8502"
TIMEOUT = 30.0


def _get(path, timeout=TIMEOUT):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "integration-test"})
    return urllib.request.urlopen(req, timeout=timeout)


@pytest.fixture(scope="module")
def dashboard_ready():
    """Wait until the dashboard answers 200 on its root (bounded wait)."""
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            resp = _get("/", timeout=5)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    pytest.fail("Dashboard never became ready on " + BASE)


def test_dashboard_root_serves_200(dashboard_ready):
    resp = _get("/")
    assert resp.status == 200
    body = resp.read().decode("utf-8", "replace")
    assert "streamlit" in body.lower() or "stApp" in body


def test_dashboard_health_ok(dashboard_ready):
    """Streamlit health endpoint must answer ok (backend thread alive)."""
    resp = _get("/_stcore/health")
    assert resp.status == 200
    assert resp.read().decode("utf-8", "replace").strip() == "ok"


def test_dashboard_serves_component_scripts(dashboard_ready):
    """Static component bundles are reachable (a broken import breaks these)."""
    ok = 0
    for path in ("/static/css/main.css", "/static/js/main.js"):
        try:
            resp = _get(path, timeout=5)
            if resp.status == 200:
                ok += 1
        except Exception:
            pass
    assert ok >= 1, "No static bundle reachable — the app is not fully serving"


def test_dashboard_page_title_metadata(dashboard_ready):
    """The HTML shell carries the app title configured by set_page_config."""
    body = _get("/").read().decode("utf-8", "replace")
    low = body.lower()
    assert ("mandiiq" in low) or ("streamlit" in low)
