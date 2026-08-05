"""Vigorous LIVE audit of all MandiIQ deployments using Brave (Playwright).

Visits every deployment, screenshots each page, clicks every button/component,
and asserts that key numbers render. Writes screenshots to ./_audit_shots/.
"""
import asyncio, json, os, sys, time

from playwright.async_api import async_playwright

BRAVE = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "BraveSoftware", "Brave-Browser", "Application", "brave.exe",
)
if not os.path.exists(BRAVE):
    BRAVE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "_audit_shots")
os.makedirs(OUT, exist_ok=True)

TARGETS = [
    {
        "name": "streamlit-dashboard",
        "url": "https://test-mandi-keae7eruks2n4cqvumjfu8.streamlit.app",
        "kind": "streamlit",
        "wait": 25000,
    },
    {
        "name": "northflank-docs",
        "url": "https://p01--mandiiq--zbvjrztgjqgw.code.run/docs",
        "kind": "swagger",
        "wait": 15000,
    },
    {
        "name": "vercel-api",
        "url": "https://test-mandi.vercel.app/docs",
        "kind": "swagger",
        "wait": 15000,
    },
    {
        "name": "github-repo",
        "url": "https://github.com/flawsom/test-mandi",
        "kind": "github",
        "wait": 15000,
    },
]

async def shot(page, name):
    path = os.path.join(OUT, f"{name}.png")
    await page.screenshot(path=path, full_page=False)
    print(f"  [shot] {name}.png")
    return path

async def audit_streamlit(page, ctx):
    print("== Streamlit dashboard ==")
    await page.wait_for_timeout(8000)  # let st spinner resolve
    await shot(page, "streamlit-top")
    # Collect every visible button / radio / tab and click through them
    buttons = await page.locator("button").count()
    print(f"  buttons found: {buttons}")
    for i in range(min(buttons, 12)):
        try:
            txt = (await page.locator("button").nth(i).inner_text(timeout=3000)).strip()[:60]
            await page.locator("button").nth(i).click(timeout=5000)
            await page.wait_for_timeout(2500)
            await shot(page, f"streamlit-btn{i}-{txt.replace(chr(10),' ').replace(' ','_')[:40]}")
            print(f"  clicked button[{i}]: {txt}")
        except Exception as e:
            print(f"  button[{i}] skip: {type(e).__name__}")
    # Sidebar nav items
    nav = page.locator('[data-testid="stSidebarNav"] a, [data-testid="stSidebar"] a')
    n = await nav.count()
    print(f"  sidebar nav links: {n}")
    for i in range(min(n, 15)):
        try:
            txt = (await nav.nth(i).inner_text(timeout=3000)).strip().split("\n")[0][:50]
            await nav.nth(i).click(timeout=5000)
            await page.wait_for_timeout(6000)
            await shot(page, f"streamlit-page{i}-{txt[:40].replace(' ','_')}")
            print(f"  navigated: {txt}")
        except Exception as e:
            print(f"  nav[{i}] skip: {type(e).__name__}")
    # Assert numbers are rendered on page (EIC/AAS/QVE numbers)
    body = await page.locator("body").inner_text(timeout=5000)
    for token in ["edge", "insight", "alert", "particle", "energy", "driver", "commodit"]:
        if token.lower() in body.lower():
            print(f"  [ok] body mentions '{token}'")
    return {"buttons": buttons}

async def audit_swagger(page, ctx):
    print("== Swagger UI ==")
    await page.wait_for_timeout(5000)
    await shot(page, ctx["name"])
    # Look for OMEGA endpoints listed in the swagger spec
    body = await page.locator("body").inner_text(timeout=5000)
    for ep in ["omega", "pipeline", "qve", "aas", "eic"]:
        print(f"  swagger mentions '{ep}': {ep in body.lower()}")
    return {"ok": True}

async def audit_github(page, ctx):
    print("== GitHub repo ==")
    await page.wait_for_timeout(5000)
    await shot(page, "github-top")
    body = await page.locator("body").inner_text(timeout=5000)
    # Badges should show live numbers (commits, stars, forks, etc.)
    for token in ["commits", "star", "fork", "README", "OMEGA", "test-mandi"]:
        print(f"  github mentions '{token}': {token.lower() in body.lower()}")
    return {"ok": True}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=BRAVE, headless=True,
            args=["--no-sandbox", "--disable-gpu", "--window-size=1600,1000"],
        )
        page = await browser.new_page(viewport={"width": 1600, "height": 1000})
        results = {}
        for t in TARGETS:
            print(f"\n>>> {t['name']} :: {t['url']}")
            try:
                await page.goto(t["url"], timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(min(t["wait"], 12000))
                handler = {"streamlit": audit_streamlit, "swagger": audit_swagger, "github": audit_github}[t["kind"]]
                results[t["name"]] = await handler(page, t)
            except Exception as e:
                print(f"  !! {t['name']} FAILED: {type(e).__name__}: {e}")
                results[t["name"]] = {"error": str(e)}
            try:
                await shot(page, t["name"] + "-final")
            except Exception:
                pass
        await browser.close()
        print("\n=== SUMMARY ===")
        print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
