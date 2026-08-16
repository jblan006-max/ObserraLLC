#!/usr/bin/env python3
"""Assemble the on-premise package into a directory (for CI `docker compose build`).

Mirrors the downloadable zip exactly. Usage: python scripts/assemble_onprem.py [outdir]
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import onprem_pack as P  # noqa: E402


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P.ROOT, "dist")
    pkg_dir = os.path.join(out, P.PKG)
    if os.path.exists(pkg_dir):
        shutil.rmtree(pkg_dir)
    count = 0
    for src, arc in P.iter_files():
        dst = os.path.join(pkg_dir, arc)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        count += 1
    with open(os.path.join(pkg_dir, ".dockerignore"), "w") as f:
        f.write(P.DOCKERIGNORE)
    with open(os.path.join(pkg_dir, "VERSION"), "w") as f:
        f.write(P.read_version() + "\n")
    with open(os.path.join(pkg_dir, "BUILD_INFO"), "w") as f:
        f.write(P.build_info())
    ish = os.path.join(pkg_dir, "install.sh")
    if os.path.exists(ish):
        os.chmod(ish, 0o755)
    print(f"Assembled {count} files at {pkg_dir} (Obserra EU CRA Governance v{P.read_version()})")


if __name__ == "__main__":
    main()
