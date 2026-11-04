"""Deterministic Vercel web-only install into the builder's active virtualenv."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    active = os.environ.get("VIRTUAL_ENV")
    if not active or Path(active).resolve() != Path(sys.prefix).resolve():
        raise SystemExit("Activate an isolated API virtualenv first; refusing to modify an implicit environment")
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("uv is required; the Vercel Python builder supplies it")
    root = Path(__file__).resolve().parents[1]
    subprocess.run([uv, "sync", "--active", "--frozen", "--no-dev", "--no-default-groups", "--no-extra", "research", "--no-extra", "test", "--no-editable", "--link-mode", "copy"], cwd=root, check=True)
    subprocess.run([sys.executable, str(root / "scripts" / "check_api_install.py")], cwd=root, check=True)


if __name__ == "__main__":
    main()
