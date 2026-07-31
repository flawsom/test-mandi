"""MandiIQ — Screenshot test fixtures.

Provides a Playwright browser fixture that boots a local Streamlit server,
navigates to routes, and takes screenshots for visual regression testing.
"""

import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import pytest_asyncio

# `routes` lives in this directory, which pytest does not put on sys.path
# when the tests package is imported as mandi_rdd.tests.*.
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from routes import STREAMLIT_PORT, STREAMLIT_URL, BOOT_TIMEOUT

# ── Paths ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DASHBOARD_APP = _PROJECT_ROOT / "mandi_rdd" / "dashboard" / "app.py"
_BASELINE_DIR = Path(__file__).resolve().parent / "screenshots" / "baseline"
_DIFF_DIR = Path(__file__).resolve().parent / "screenshots" / "diff"


def pytest_addoption(parser):
    parser.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="Regenerate baseline screenshots instead of diffing",
    )


@pytest.fixture(scope="session")
def update_baselines(request):
    return request.config.getoption("--update-baselines")


@pytest.fixture(scope="session")
def baseline_dir():
    _BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    return _BASELINE_DIR


@pytest.fixture(scope="session")
def diff_dir():
    _DIFF_DIR.mkdir(parents=True, exist_ok=True)
    return _DIFF_DIR


# ── Streamlit server fixture ──


@pytest.fixture(scope="session")
def streamlit_server():
    """Boot a local Streamlit server for the duration of the session.

    Captures stderr to a temp file for debugging startup failures.
    Yields the base URL. Cleans up the server process on teardown.
    """
    env = os.environ.copy()
    env["STREAMLIT_SERVER_PORT"] = str(STREAMLIT_PORT)
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    stderr_file = tempfile.NamedTemporaryFile(
        prefix="mandiiq_streamlit_", suffix=".log", delete=False
    )

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(_DASHBOARD_APP),
            "--server.port",
            str(STREAMLIT_PORT),
            "--server.headless",
            "true",
            "--global.developmentMode",
            "false",
            "--browser.gatherUsageStats",
            "false",
            "--server.enableCORS",
            "false",
            "--server.enableXsrfProtection",
            "false",
            "--server.maxMessageSize",
            "500",
        ],
        stdout=subprocess.DEVNULL,
        stderr=stderr_file,
        env=env,
    )
    stderr_file.close()  # writer handle closed, reader still works

    health_url = f"{STREAMLIT_URL}/_stcore/health"
    deadline = time.monotonic() + BOOT_TIMEOUT
    last_err = None
    started = False

    while time.monotonic() < deadline:
        try:
            resp = urllib.request.urlopen(health_url, timeout=3)
            if resp.status == 200:
                started = True
                break
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last_err = e
            time.sleep(1)

    if not started:
        proc.kill()
        proc.wait()
        with open(stderr_file.name) as f:
            stderr_log = f.read()
        try:
            os.unlink(stderr_file.name)
        except Exception:
            pass
        pytest.fail(
            f"Streamlit server did not start within {BOOT_TIMEOUT}s.\n"
            f"Last error: {last_err}\n"
            f"--- stderr ---\n{stderr_log[:2000]}\n--- end ---"
        )

    yield STREAMLIT_URL

    # Teardown
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    try:
        os.unlink(stderr_file.name)
    except Exception:
        pass


# ── Playwright browser fixture ──


@pytest_asyncio.fixture(scope="session")
async def browser():
    """Create a Playwright Chromium browser instance (session-scoped).

    Playwright is only installed in the dedicated E2E job
    (dashboard-integration.yml), so import it lazily and skip the screenshot
    tests when it is unavailable instead of failing collection for the whole
    test directory (which also hosts plain unit tests).
    """
    async_playwright = pytest.importorskip("playwright.async_api")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        yield browser
        await browser.close()


@pytest_asyncio.fixture
async def page(browser, streamlit_server):
    """Create a new browser context and page for each test.

    Uses a fixed viewport size (1280x800) for reproducible screenshots.
    """
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        device_scale_factor=1,
        locale="en-US",
        color_scheme="dark",
    )
    page = await context.new_page()
    page.set_default_timeout(30000)
    yield page
    await context.close()
