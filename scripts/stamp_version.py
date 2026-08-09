#!/usr/bin/env python3
"""Bump VERSION from the latest git tag (strips a leading 'v'); no-op when untagged.

CI runs this on tag pushes so every download and image is traceable to a release.
Honors an explicit OBSERRA_VERSION env override (used by the release workflow).
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _latest_tag():
    env = (os.environ.get("OBSERRA_VERSION") or "").strip()
    if env:
        return env.lstrip("v")
    try:
        out = subprocess.run(["git", "describe", "--tags", "--abbrev=0"],
                             cwd=ROOT, capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().lstrip("v")
    except Exception:
        pass
    return None


def main():
    v = _latest_tag()
    if not v:
        print("No git tag / OBSERRA_VERSION found — keeping existing VERSION")
        return
    with open(os.path.join(ROOT, "VERSION"), "w") as f:
        f.write(v + "\n")
    print(f"Stamped VERSION = {v}")


if __name__ == "__main__":
    main()
