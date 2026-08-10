#!/usr/bin/env python3
"""Auto-capture fresh dashboard screenshots for the SAP UAC Install & User Guide.

Drives the live app with Playwright (Chromium), logs in as an admin, and saves
JPEGs to scripts/shots using the exact filenames gen_docs.py embeds. Best-effort:
any page that fails is skipped so a partial refresh still succeeds.

Env overrides: SHOT_BASE_URL, SHOT_EMAIL, SHOT_PASSWORD.
"""
import os
import shutil

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "shots")
os.makedirs(SHOTS, exist_ok=True)
PUBLIC_TOUR = os.path.join(os.path.dirname(HERE), "frontend", "public", "tour")
# in-app onboarding tour previews (served from /tour/*.jpg)
TOUR_MAP = {"02_exec_overview": "overview", "04_sod_command_center": "sod",
            "05_sod_watchlist_leaderboard": "watchlist", "07_access_monitoring": "monitoring"}


def _copy_tour_shots():
    os.makedirs(PUBLIC_TOUR, exist_ok=True)
    for src, dst in TOUR_MAP.items():
        sp = os.path.join(SHOTS, f"{src}.jpg")
        if os.path.exists(sp):
            try:
                shutil.copyfile(sp, os.path.join(PUBLIC_TOUR, f"{dst}.jpg"))
            except Exception:
                pass


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

# (route under /app, screenshot filename, scroll_y) — must match gen_docs.py SECTIONS
PAGES = [
    ("", "02_exec_overview", 0),
    ("systems", "20_go_live", 0),
    ("analytics", "03_sap_analytics", 0),
    ("sod", "04_sod_command_center", 0),
    ("sod", "05_sod_watchlist_leaderboard", 520),
    ("privileged", "06_privileged_access", 0),
    ("monitoring", "07_access_monitoring", 0),
    ("identities", "08_identities", 0),
    ("lifecycle", "09_lifecycle", 0),
    ("hr-reconciliation", "10_hr_reconciliation", 0),
    ("roles", "11_role_intelligence", 0),
    ("access-requests", "12_access_requests", 0),
    ("certifications", "13_certifications", 0),
    ("settings", "14_settings", 0),
]


def _dismiss_overlays(page):
    for _ in range(3):
        s = page.query_selector("[data-testid=tour-skip]") or page.query_selector("text=Skip")
        if s:
            try:
                s.click(); page.wait_for_timeout(400)
            except Exception:
                break
        else:
            break
    c = page.query_selector("[data-testid=advisor-close]")
    if c:
        try:
            c.click(); page.wait_for_timeout(300)
        except Exception:
            pass


def _settle(page):
    """Wait for network to go idle and the app's lazy-route Suspense spinner to clear."""
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    try:
        page.wait_for_function(
            "() => { const m = document.querySelector('main'); return m && !m.querySelector('.animate-spin'); }",
            timeout=12000)
    except Exception:
        pass


def _chromium_exe():
    import glob
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")
    for pat in ("chromium_headless_shell-*/chrome-linux/headless_shell",
                "chromium-*/chrome-linux/chrome"):
        matches = sorted(glob.glob(os.path.join(base, pat)))
        if matches:
            return matches[-1]
    return None


def run():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        _exe = _chromium_exe()
        _lk = {"headless": True, "args": ["--no-sandbox"]}
        if _exe:
            _lk["executable_path"] = _exe
        browser = p.chromium.launch(**_lk)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        # Login (SAP UAC auth form lives on the landing route "/")
        page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("input[type=email]", state="visible", timeout=25000)
        try:
            page.screenshot(path=os.path.join(SHOTS, "01_login.jpg"), type="jpeg", quality=70)
        except Exception:
            pass
        page.fill("input[type=email]", EMAIL)
        page.fill("input[type=password]", PASSWORD)
        page.get_by_test_id("auth-submit").click()
        page.wait_for_timeout(3000)
        _settle(page)
        _dismiss_overlays(page)
        pages = [p for p in PAGES if p[1] in TOUR_MAP] if os.environ.get("SHOT_TOUR_ONLY") else PAGES
        only = os.environ.get("SHOT_ONLY")
        if only:
            wanted = set(only.split(","))
            pages = [p for p in pages if p[1] in wanted]
        for route, name, scroll_y in pages:
            try:
                page.goto(f"{BASE}/app/{route}", wait_until="domcontentloaded", timeout=45000)
                _settle(page)
                page.wait_for_timeout(800)
                _dismiss_overlays(page)
                if scroll_y:
                    page.evaluate("(y) => window.scrollTo(0, y)", scroll_y)
                    page.wait_for_timeout(700)
                else:
                    page.evaluate("() => window.scrollTo(0, 0)")
                    page.wait_for_timeout(200)
                page.screenshot(path=os.path.join(SHOTS, f"{name}.jpg"), type="jpeg", quality=70)
                print("captured", name)
            except Exception as e:
                print("skip", name, e)
        browser.close()
    _copy_tour_shots()


if __name__ == "__main__":
    run()
