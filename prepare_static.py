"""Prepare the same public files as the Docker build, without requiring Docker."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
static = root / "static"
static.mkdir(exist_ok=True)
for name in ("index.html", "privacy.html", "reset.html", "terms.html", "simple-flow-fix.js"):
    shutil.copyfile(root / name, static / name)

index = static / "index.html"
html = index.read_text(encoding="utf-8")
tag = '<script src="/simple-flow-fix.js?v=5"></script>'
html = html.replace('<script src="/simple-flow-fix.js"></script>', tag)
if tag not in html:
    html = html.replace("</body>", tag + "\n</body>", 1)
index.write_text(html, encoding="utf-8")