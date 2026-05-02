#!/bin/bash
# Auto-increments the build number in __init__.py and pyproject.toml before each commit.
# Build number = total commits after this one (git rev-list count + 1), so it's always
# deterministic and monotonically increasing without needing a separate counter file.
#
# Install (run once per machine from the repo root):
#   cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

BUILD=$(($(git rev-list --count HEAD 2>/dev/null || echo 0) + 1))

python3 - "$BUILD" <<'PYEOF'
import sys, re
from pathlib import Path

build = sys.argv[1]
init_file = Path("src/panopto_downloader/__init__.py")
pyproject  = Path("pyproject.toml")

init_text = init_file.read_text()
m = re.search(r'__version__ = "([^"]+)"', init_text)
if not m:
    print("pre-commit: warning — could not find __version__, skipping bump")
    sys.exit(0)

current     = m.group(1)
base        = re.sub(r'-\d+$', '', current)   # strip existing build suffix
new_version = f"{base}-{build}"

if current == new_version:
    sys.exit(0)

init_file.write_text(init_text.replace(
    f'__version__ = "{current}"',
    f'__version__ = "{new_version}"',
))

pyproject_text = pyproject.read_text()
pyproject.write_text(re.sub(
    r'^version = "[^"]+"',
    f'version = "{new_version}"',
    pyproject_text,
    flags=re.MULTILINE,
))

print(f"pre-commit: version {current} → {new_version}")
PYEOF

git add src/panopto_downloader/__init__.py pyproject.toml
