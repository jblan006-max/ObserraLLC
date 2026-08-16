"""Shared on-premise package layout.

Used by both the download endpoint (backend/deploy.py) and the CI assembler
(scripts/assemble_onprem.py) so the shipped zip and the CI-built package stay
identical. Deliberately has no app/DB imports, so it can be loaded standalone in CI.
"""
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ONPREM = os.path.join(ROOT, "deploy", "onprem")
PKG = "obserra-sap-uac"

SKIP_DIRS = {"node_modules", "__pycache__", ".git", "build", ".venv", "venv",
             ".emergent", ".ruff_cache", ".pytest_cache", "dist", ".yarn", ".idea", ".vscode"}
SKIP_EXT = {".pyc", ".pyo", ".log"}
DOCKERIGNORE = (
    "**/node_modules\n**/__pycache__\n**/*.pyc\n**/*.pyo\n**/.git\n**/.venv\n**/venv\n"
    "frontend/build\nbackend/assets/docs\n**/.env\n**/.emergent\n**/.ruff_cache\n**/.pytest_cache\n"
)


def read_version():
    v = (os.environ.get("OBSERRA_VERSION") or "").strip().lstrip("v")
    if v:
        return v
    try:
        with open(os.path.join(ROOT, "VERSION")) as f:
            return f.read().strip() or "1.0.0"
    except Exception:
        return "1.0.0"


def _build_date(build_date=None):
    return build_date or datetime.now(timezone.utc).date().isoformat()


def build_info(build_date=None):
    return f"name=Obserra Cyber Crisis Commander\nversion={read_version()}\nbuilt={_build_date(build_date)}\n"


def zip_name(build_date=None):
    return f"Obserra-Cyber-Crisis-Commander-OnPrem-v{read_version()}-{_build_date(build_date)}.zip"


def _walk(src_root, arc_prefix, skip_rel_prefixes=()):
    if not os.path.isdir(src_root):
        return
    for root, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if fn == ".env" or os.path.splitext(fn)[1] in SKIP_EXT:
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, src_root)
            if any(rel == p or rel.startswith(p + os.sep) for p in skip_rel_prefixes):
                continue
            yield fp, f"{arc_prefix}/{rel}".replace(os.sep, "/")


def iter_files():
    """Yield (abs_src_path, arcname_relative_to_package_root)."""
    yield from _walk(os.path.join(ROOT, "backend"), "backend", skip_rel_prefixes=("assets/docs",))
    yield from _walk(os.path.join(ROOT, "frontend"), "frontend")
    for root, _dirs, files in os.walk(ONPREM):
        for fn in files:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, ONPREM).replace(os.sep, "/")
            yield fp, ("install.sh" if rel == "install.sh" else f"deploy/{rel}")
    yield from _walk(os.path.join(ROOT, "deploy", "wheels"), "deploy/wheels")
