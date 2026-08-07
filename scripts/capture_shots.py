#!/usr/bin/env python3
"""Auto-capture fresh dashboard screenshots for the Install & User Guide.

Drives the live app with Playwright (Chromium), logs in as an admin, and saves
JPEGs to scripts/shots using the exact filenames gen_docs.py embeds. Best-effort:
any page that fails is skipped so a partial refresh still succeeds.

Env overrides: SHOT_BASE_URL, SHOT_EMAIL, SHOT_PASSWORD.
"""
import os

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "shots")
os.makedirs(SHOTS, exist_ok=True)


def _backend_url():
    if os.environ.get("SHOT_BASE_URL"):
        return os.environ["SHOT_BASE_URL"].rstrip("/")
    envp = os.path.join(os.path.dirname(HERE), "frontend", ".env")
    try:
        with open(envp) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return "http://localhost:3000"


BASE = _backend_url()
EMAIL = os.environ.get("SHOT_EMAIL", "jblan2026@gmail.com")
PASSWORD = os.environ.get("SHOT_PASSWORD", "Obserra2026!")

# route -> screenshot filename (must match gen_docs.py SECTIONS)
PAGES = [
    ("", "02_exec_overview"),
    ("risks", "04_risk_register"),
    ("ai-governance", "05_ai_governance"),
    ("controls", "06_control_monitoring"),
    ("compliance", "07_compliance"),
    ("reporting", "08_reporting"),
    ("settings", "09_settings"),
]


def run():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        # Login
        page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("input[type=email]", state="visible", timeout=20000)
        page.fill("input[type=email]", EMAIL)
        page.fill("input[type=password]", PASSWORD)
        page.get_by_test_id("auth-submit").click()
        page.wait_for_timeout(4000)
        for _ in range(3):
            s = page.query_selector("text=Skip")
            if s:
                s.click(); page.wait_for_timeout(500)
        try:
            page.screenshot(path=os.path.join(SHOTS, "01_login.jpg"), type="jpeg", quality=70)
        except Exception:
            pass
        for route, name in PAGES:
            try:
                page.goto(f"{BASE}/app/{route}", wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(1800)
                s = page.query_selector("text=Skip")
                if s:
                    s.click(); page.wait_for_timeout(400)
                c = page.query_selector("[data-testid=advisor-close]")
                if c:
                    c.click(); page.wait_for_timeout(300)
                page.screenshot(path=os.path.join(SHOTS, f"{name}.jpg"), type="jpeg", quality=70)
                print("captured", name)
            except Exception as e:
                print("skip", name, e)
        browser.close()


if __name__ == "__main__":
    run()
