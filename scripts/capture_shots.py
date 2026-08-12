#!/usr/bin/env python3
"""Auto-capture fresh dashboard screenshots for the Obserra EU CRA Governance guides.

Drives the live app with Playwright (Chromium), logs in as an admin, walks the EU
CRA Governance tabs and saves JPEGs to scripts/shots using the exact filenames
gen_docs.py embeds. Best-effort: any page that fails is skipped so a partial
refresh still succeeds.

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

# (cra tab id, screenshot filename) — must match gen_docs.py SECTIONS.
CRA_TABS = [
    ("mission", "cra_mission"),
    ("products", "cra_products"),
    ("ledger", "cra_ledger"),
    ("vulnerability", "cra_vuln"),
    ("declaration", "cra_declaration"),
    ("regulation", "cra_regulation"),
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
        # Login (auth form lives on the landing route "/")
        page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("input[type=email]", state="visible", timeout=25000)
        try:
            page.screenshot(path=os.path.join(SHOTS, "01_login.jpg"), type="jpeg", quality=70)
            print("captured 01_login")
        except Exception:
            pass
        page.fill("input[type=email]", EMAIL)
        page.fill("input[type=password]", PASSWORD)
        page.get_by_test_id("auth-submit").click()
        page.wait_for_timeout(3000)
        _settle(page)
        _dismiss_overlays(page)

        only = os.environ.get("SHOT_ONLY")
        tabs = CRA_TABS
        if only:
            wanted = set(only.split(","))
            tabs = [t for t in tabs if t[1] in wanted]

        # Open the EU CRA Governance workspace once, then click through its tabs.
        page.goto(f"{BASE}/app/cra-governance", wait_until="domcontentloaded", timeout=45000)
        _settle(page)
        page.wait_for_timeout(800)
        _dismiss_overlays(page)
        for tab, name in tabs:
            try:
                btn = page.query_selector(f"[data-testid=cra-tab-{tab}]")
                if btn:
                    btn.click()
                    page.wait_for_timeout(700)
                _settle(page)
                if tab == "mission":
                    try:
                        page.wait_for_selector("[data-testid=cra-insight-headline]", timeout=20000)
                    except Exception:
                        pass
                page.evaluate("() => window.scrollTo(0, 0)")
                page.wait_for_timeout(300)
                page.screenshot(path=os.path.join(SHOTS, f"{name}.jpg"), type="jpeg", quality=70)
                print("captured", name)
            except Exception as e:
                print("skip", name, e)

        # Shared Settings screen (branding + deployment downloads).
        try:
            page.goto(f"{BASE}/app/settings", wait_until="domcontentloaded", timeout=45000)
            _settle(page)
            page.wait_for_timeout(600)
            _dismiss_overlays(page)
            page.evaluate("() => window.scrollTo(0, 0)")
            page.screenshot(path=os.path.join(SHOTS, "cra_settings.jpg"), type="jpeg", quality=70)
            print("captured cra_settings")
        except Exception as e:
            print("skip cra_settings", e)
        browser.close()


if __name__ == "__main__":
    run()
