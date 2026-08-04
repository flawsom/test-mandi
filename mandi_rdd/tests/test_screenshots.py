"""MandiIQ — Automated Screenshot Regression Tests.

Visits all 10 navigable dashboard routes, captures viewport screenshots,
freezes animations to eliminate flakiness, and diffs each against its
baseline using Pillow.  Fails if the pixel-diff ratio exceeds the
configured threshold.

Usage:

    # Run tests (diff mode — compares against baseline)
    pytest mandi_rdd/tests/test_screenshots.py -v

    # Regenerate baseline images (run after intentional visual changes)
    pytest mandi_rdd/tests/test_screenshots.py -v --update-baselines

    # Test only a single route
    pytest mandi_rdd/tests/test_screenshots.py -v -k "satellite"
"""

import numpy as np
from pathlib import Path
from PIL import Image, ImageChops

import pytest
from routes import ROUTES, STREAMLIT_URL, MAX_DIFF_RATIO, PIXEL_THRESHOLD


# ── Image comparison ──


def _diff_images(baseline_path: Path, current_path: Path, diff_path: Path | None) -> dict:
    """Compare two PNG images using Pillow + numpy.

    Returns a dict with keys:
        diff_ratio  — fraction of pixels that differ beyond PIXEL_THRESHOLD
        max_diff    — maximum per-pixel channel difference
        mse         — mean squared error across all 4 RGBA channels
        size_ok     — whether dimensions matched (within 5px tolerance)
    """
    bl = Image.open(baseline_path).convert("RGBA")
    cur = Image.open(current_path).convert("RGBA")

    # Size check
    bw, bh = bl.size
    cw, ch = cur.size
    size_diff = abs(bw - cw) + abs(bh - ch)
    size_ok = size_diff <= 10

    if not size_ok:
        bl = bl.resize(cur.size, Image.LANCZOS)

    # Per-channel difference image via vectorised PIL + numpy
    diff = ImageChops.difference(bl, cur)
    arr = np.array(diff, dtype=np.float64)

    per_pixel_max = arr.max(axis=2)
    diff_pixels = int(np.sum(per_pixel_max > PIXEL_THRESHOLD))
    total_pixels = arr.shape[0] * arr.shape[1]
    max_diff = int(per_pixel_max.max()) if total_pixels > 0 else 0
    mse = float(np.mean(arr ** 2))
    diff_ratio = diff_pixels / total_pixels if total_pixels else 0.0

    # Write red-tinted diff overlay only on actual diffs
    if diff_path is not None and diff_pixels > 0:
        cur_arr = np.array(cur, dtype=np.uint8)
        overlay = np.zeros_like(cur_arr)
        mask = per_pixel_max > PIXEL_THRESHOLD
        overlay[mask] = [255, 60, 60, 180]
        overlay[~mask] = [
            cur_arr[~mask][:, 0] // 4,
            cur_arr[~mask][:, 1] // 4,
            cur_arr[~mask][:, 2] // 4,
            120,
        ]
        alpha = overlay[:, :, 3:4].astype(np.float64) / 255.0
        blended = (
            cur_arr.astype(np.float64) * (1 - alpha)
            + overlay[:, :, :4].astype(np.float64) * alpha
        ).clip(0, 255).astype(np.uint8)
        Image.fromarray(blended, "RGBA").save(str(diff_path))

    return {
        "diff_ratio": diff_ratio,
        "max_diff": max_diff,
        "mse": mse,
        "size_ok": size_ok,
        "size_current": f"{cw}x{ch}",
        "size_baseline": f"{bw}x{bh}",
    }


# ── Helpers ──


async def _freeze_animations(page):
    """Inject CSS to disable all animations, transitions, and rAF loops.

    This eliminates flakiness from the atmosphere dot grid, WebGL particle
    field, GSAP SplitText, rAF-smoothed counters, and Plotly hover effects.
    """
    await page.add_style_tag(content="""
        *,
        *::before,
        *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
        .atmosphere-drifter,
        .atmosphere-flash,
        .atmosphere-cloud {
            animation: none !important;
            opacity: 0.03 !important;
        }
        .scroll-progress { display: none !important; }
        .fresh-dot { animation: none !important; box-shadow: none !important; }
    """)


async def _wait_for_page_ready(page, slug: str):
    """Wait for the page to finish rendering, then freeze animations."""
    await page.wait_for_load_state("networkidle")

    try:
        await page.wait_for_selector("h1, h2", timeout=10000)
    except Exception:
        pass

    try:
        await page.wait_for_selector(
            ".js-plotly-plot, .stPlotlyChart, .freshness-table",
            timeout=8000,
        )
    except Exception:
        pass

    await page.wait_for_timeout(1000)
    await _freeze_animations(page)
    await page.wait_for_timeout(300)


# ── Tests ──


@pytest.mark.parametrize("route,slug,label", ROUTES)
@pytest.mark.asyncio
async def test_route_screenshot(
    page, route, slug, label, baseline_dir, diff_dir, update_baselines
):
    """Visit a dashboard route, screenshot it, and compare to baseline."""

    url = f"{STREAMLIT_URL}{route}"
    await page.goto(url, wait_until="domcontentloaded")
    await _wait_for_page_ready(page, slug)

    screenshot_bytes = await page.screenshot(type="png")

    baseline_path = baseline_dir / f"{slug}.png"
    current_path = diff_dir / "current" / f"{slug}.png"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    with open(current_path, "wb") as f:
        f.write(screenshot_bytes)

    # ── Baseline update mode ──
    if update_baselines:
        with open(baseline_path, "wb") as f:
            f.write(screenshot_bytes)
        pytest.skip(f"Baseline updated: {slug}.png")
        return

    # ── No baseline yet → save current as baseline ──
    if not baseline_path.exists():
        with open(baseline_path, "wb") as f:
            f.write(screenshot_bytes)
        pytest.skip(f"No baseline existed — created: {slug}.png")
        return

    # ── Diff mode ──
    diff_path = diff_dir / f"{slug}_diff.png"
    result = _diff_images(baseline_path, current_path, diff_path)

    # Clean up diff file on clean passes (keeps diff directory focused)
    if result["diff_ratio"] <= MAX_DIFF_RATIO and diff_path.exists():
        try:
            diff_path.unlink()
        except Exception:
            pass

    summary = (
        f"[{label}] {slug}.png: "
        f"diff_ratio={result['diff_ratio']:.4f} "
        f"(max {MAX_DIFF_RATIO:.2f}), "
        f"max_diff={result['max_diff']}, "
        f"MSE={result['mse']:.2f}, "
        f"size_ok={result['size_ok']} "
        f"({result['size_baseline']}→{result['size_current']})"
    )

    if result["diff_ratio"] > MAX_DIFF_RATIO:
        pytest.fail(
            f"Visual regression detected on {slug}!\n"
            f"  Changed pixels: {result['diff_ratio']*100:.1f}% "
            f"(threshold: {MAX_DIFF_RATIO*100:.1f}%)\n"
            f"  Max pixel diff: {result['max_diff']}\n"
            f"  MSE: {result['mse']:.2f}\n"
            f"  Size: {result['size_baseline']} → {result['size_current']} "
            f"(ok={result['size_ok']})\n"
            f"  Diff overlay: {diff_path}"
        )

    if not result["size_ok"]:
        print(f"  ⚠ {summary}")
    else:
        print(f"  ✓ {summary}")
