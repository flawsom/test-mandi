"""
Streamlit Community Cloud entrypoint (root-level).

Auto-detected by Streamlit Cloud when the "Main file path" points to the
repository root. Delegates to the real dashboard app so nested deployments
work regardless of UI-side configuration.
"""
import runpy
from pathlib import Path

_APP = Path(__file__).resolve().parent / "mandi_rdd" / "dashboard" / "app.py"
runpy.run_path(str(_APP), run_name="__main__")
