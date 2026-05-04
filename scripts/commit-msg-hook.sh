#!/bin/bash
# commit-msg hook: bump version intelligently based on Conventional Commit type.
#
# Rules (all segments to the RIGHT of the bumped one reset to 0):
#   feat!: / BREAKING CHANGE  →  major++,  minor=0, patch=0, build=1
#   feat:                      →  minor++,  patch=0, build=1
#   fix: / refactor: / perf:  →  patch++,  build=1
#   chore: / docs: / test: …  →  build++   (only)
#
# Install (run once per machine from the repo root):
#   cp scripts/commit-msg-hook.sh .git/hooks/commit-msg
#   chmod +x .git/hooks/commit-msg
#
# Remove the old pre-commit hook if it exists:
#   rm -f .git/hooks/pre-commit

COMMIT_MSG=$(cat "$1")

python3 - "$COMMIT_MSG" <<'PYEOF'
import sys, re
from pathlib import Path

msg = sys.argv[1]

# Determine bump type from the conventional commit prefix
if re.match(r'^(feat|feature)![\s(:]', msg, re.IGNORECASE) or 'BREAKING CHANGE' in msg:
    bump = 'major'
elif re.match(r'^(feat|feature)[\s(:]', msg, re.IGNORECASE):
    bump = 'minor'
elif re.match(r'^(fix|refactor|perf)[\s(:]', msg, re.IGNORECASE):
    bump = 'patch'
else:
    bump = 'build'   # chore, docs, test, style, ci, etc.

init_file = Path("src/panopto_downloader/__init__.py")
pyproject  = Path("pyproject.toml")

init_text = init_file.read_text()
m = re.search(r'__version__ = "([^"]+)"', init_text)
if not m:
    print("commit-msg: warning — __version__ not found, skipping bump")
    sys.exit(0)

current = m.group(1)
vm = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-(\d+))?$', current)
if not vm:
    print(f"commit-msg: warning — cannot parse version '{current}', skipping")
    sys.exit(0)

major = int(vm[1])
minor = int(vm[2])
patch = int(vm[3])
build = int(vm[4] or 0)

if bump == 'major':
    major += 1; minor = 0; patch = 0; build = 1
elif bump == 'minor':
    minor += 1; patch = 0; build = 1
elif bump == 'patch':
    patch += 1; build = 1
else:
    build += 1

new_version = f"{major}.{minor}.{patch}-{build}"
if current == new_version:
    sys.exit(0)

init_file.write_text(init_text.replace(
    f'__version__ = "{current}"',
    f'__version__ = "{new_version}"',
))

pyproject.write_text(re.sub(
    r'^version = "[^"]+"',
    f'version = "{new_version}"',
    pyproject.read_text(),
    flags=re.MULTILINE,
))

print(f"commit-msg: {bump} bump  {current}  →  {new_version}")
PYEOF

# Stage the updated version files so they're included in this commit
git add src/panopto_downloader/__init__.py pyproject.toml
