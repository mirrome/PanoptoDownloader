# Coding Rules & Contributing Guide

## Version Convention

Versions follow `{major}.{minor}.{fixes}-{build}`:

| Segment | Meaning | Who changes it |
|---------|---------|----------------|
| **major** | Breaking changes (e.g. incompatible config format) | Manual |
| **minor** | New features, backwards-compatible | Manual |
| **fixes** | Bug fixes | Manual |
| **build** | Auto-incremented on every commit | Pre-commit hook |

The build number equals the total commit count, so it is always monotonically
increasing and deterministic — no counter file, no merge conflicts.

### Setup the pre-commit hook (once per machine)

```bash
cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

After this, every `git commit` will automatically bump the build number in
`src/panopto_downloader/__init__.py` and `pyproject.toml` before the commit
is recorded. You never need to touch the version manually unless bumping
major/minor/fixes.

### Bumping major, minor, or fixes manually

Edit both files, then commit as usual — the hook will append the next build
number automatically:

```python
# src/panopto_downloader/__init__.py
__version__ = "0.2.0"   # hook will rewrite to e.g. "0.2.0-25"
```

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New command, option, or capability |
| `fix:` | Bug fix |
| `refactor:` | Code restructure, no behavior change |
| `docs:` | Documentation only |
| `chore:` | Build tooling, dependencies, hooks |

Examples:
```
feat: add --only flag to batch command for filtering courses
fix: separator-insensitive matching in migrate_existing_assets
chore: add pre-commit version bump hook
```

---

## Auth Profiles

Each user or Panopto server gets a **named profile**. Profiles store tokens
independently in `~/.config/panopto-downloader/tokens-<profile>.json`.

| Profile | Server | User |
|---------|--------|------|
| `default` | `mitsloan.hosted.panopto.com` | Abdul Rehman (Sloan) |
| `eecs` | `mit.hosted.panopto.com` | Abdul Rehman (MIT EECS) |
| `menard` | `mitsloan.hosted.panopto.com` | Daniel Menard |
| `sargent` | `mitsloan.hosted.panopto.com` | Daniel Sargent |

### Logging in for a new profile

Run on a machine with a browser (not over SSH):

```bash
# Daniel Menard
venv/bin/panopto-downloader --profile menard auth login \
  --server mitsloan.hosted.panopto.com \
  --client-id <menard_client_id> \
  --client-secret "<menard_client_secret>"

# Daniel Sargent
venv/bin/panopto-downloader --profile sargent auth login \
  --server mitsloan.hosted.panopto.com \
  --client-id <sargent_client_id> \
  --client-secret "<sargent_client_secret>"
```

A browser window opens — the person whose profile it is must log in with
their Panopto username and password. The client ID/secret alone is not enough;
the browser login step is required once to obtain a refresh token.

After login, tokens are stored locally. Copy them to Mac mini if needed:

```bash
scp ~/.config/panopto-downloader/tokens-menard.json \
    abdulrehman@192.168.68.74:~/.config/panopto-downloader/
```

### Discovering accessible courses

```bash
# What can Daniel Menard access?
venv/bin/panopto-downloader --profile menard discover --all

# What can Daniel Sargent access?
venv/bin/panopto-downloader --profile sargent discover --all
```

### Running a batch download for a friend's courses

```bash
# Create menard_courses.yaml (same format as courses.yaml),
# then run:
venv/bin/panopto-downloader --profile menard batch \
  -c menard_courses.yaml --all-streams
```

---

## Course YAML Files

| File | Profile | Description |
|------|---------|-------------|
| `courses.yaml` | `default` | Abdul's Sloan EMBA courses |
| `eecs_courses.yaml` | `eecs` | Abdul's MIT EECS courses |
| `menard_courses.yaml` | `menard` | Daniel Menard's courses (create after `discover`) |
| `sargent_courses.yaml` | `sargent` | Daniel Sargent's courses (create after `discover`) |

---

## Download Output Layout

```
/Volumes/NAS/MIT EMBA/MIT_Lectures/
  <Course Folder>/
    <Session Name>/
      <Session Name>_composed.mp4
      <Session Name>_camera.mp4
      <Session Name>_slides.mp4
```

Composed view is downloaded to a local temp dir first, then moved to the NAS,
to avoid SMB-specific `[Errno 22]` failures during yt-dlp write/close.
