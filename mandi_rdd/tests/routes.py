"""MandiIQ — Screenshot test routes and configuration constants."""

# Streamlit port and URL
STREAMLIT_PORT = 18501
STREAMLIT_URL = f"http://127.0.0.1:{STREAMLIT_PORT}"

# Routes to test: (url_path, slug, display_label)
ROUTES = [
    ("/", "executive-overview", "Executive Overview"),
    ("/discontinuity", "discontinuity", "Discontinuity Explorer"),
    ("/forecast", "forecast", "Forecast Explorer"),
    ("/risk-map", "risk-map", "Risk Map"),
    ("/satellite", "satellite", "Satellite View"),
    ("/discount-simulator", "discount-simulator", "Discount Simulator"),
    ("/ask", "ask", "Ask MandiIQ"),
    ("/settings", "settings", "Settings"),
    ("/about", "about", "About"),
    ("/performance", "performance", "Performance"),
]

# Visual diff tolerances
MAX_DIFF_RATIO = 0.01  # 1% — tighter now that animations are frozen
PIXEL_THRESHOLD = 10   # Min channel difference to count as changed

# Streamlit boot timeout (seconds)
BOOT_TIMEOUT = 60

# Omega FastAPI endpoints (NOT Streamlit screenshot routes — keep out of ROUTES
# above so dashboard-integration E2E navigation is unaffected). These are API
# contract-checked by mandi_rdd/tests/test_omega_*.py.
OMEGA_API_PATHS = [
    ("GET", "/qve/placement", "Omega QVE particle placement"),
    ("GET", "/omega/status", "Omega layer registry/health"),
    ("GET", "/omega/pipeline", "Omega pipeline"),
]
