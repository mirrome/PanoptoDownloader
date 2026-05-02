#!/usr/bin/env python3
"""Delete old-format duplicate files where a new-format equivalent exists.

Old format: 'Lecture on 9202024 (Fri)_composed.mp4'   (no dashes in date)
New format: 'Lecture on 9-20-2024 (Fri)_composed.mp4' (dashes in date)

This script finds old-format files and deletes them ONLY when the
new-format equivalent (and matching size > 50% of old) is already on disk.

Usage:
    python cleanup_duplicates.py                # dry run, just lists
    python cleanup_duplicates.py --delete       # actually delete
"""

import re
import sys
from pathlib import Path

ROOT = Path("/Volumes/NAS/MIT EMBA/MIT_Lectures")

# Match a date with no separators (M-or-MM, DD, YYYY) flanked by " on " and " ("
PATTERN = re.compile(r"^(.*\bon )(\d{1,2})(\d{2})(\d{4})( \(.*)$")


def main(delete: bool = False) -> int:
    if not ROOT.exists():
        print(f"Root path not found: {ROOT}", file=sys.stderr)
        return 1

    found = 0
    deleted = 0
    skipped = 0

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        match = PATTERN.match(path.name)
        if not match:
            continue

        prefix, month, day, year, suffix = match.groups()
        new_name = f"{prefix}{int(month)}-{int(day)}-{year}{suffix}"
        new_path = path.parent / new_name

        if not new_path.exists():
            continue

        old_size = path.stat().st_size
        new_size = new_path.stat().st_size

        # Safety check: only delete if new file is at least 50% the size of old
        if new_size < old_size * 0.5:
            print(f"SKIP (new file suspiciously small): {path.name}")
            print(f"     old={old_size:,} new={new_size:,}")
            skipped += 1
            continue

        found += 1
        if delete:
            path.unlink()
            deleted += 1
            print(f"DELETED: {path.name}")
        else:
            print(f"WOULD DELETE: {path.name}")
            print(f"  -> kept: {new_name}")

    print()
    print(f"Found {found} duplicate(s); skipped {skipped}; deleted {deleted}.")
    if not delete and found:
        print("Re-run with --delete to actually remove them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(delete="--delete" in sys.argv))
