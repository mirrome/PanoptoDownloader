# Panopto Lecture Downloader

A Python CLI tool for downloading MIT Sloan Panopto lecture recordings with support for multiple stream types, batch processing, and resume capability.

## Features

- **Multiple Stream Downloads**: Download composed (slides+camera), camera-only, or slides-only
- **ALL Camera Angles**: Download every camera angle (PC1, PC2, Wideshot, chalkboards) using `--all-cameras`
- **Automatic Captions**: Downloads subtitles/closed captions automatically
- **Cookie File Support**: Use cookies.txt file for authentication (no need to close browser)
- **Batch Processing**: Configure once, download entire courses
- **Parallel Downloads**: Concurrent downloads for faster batch processing
- **Resume Support**: Automatically skips already-downloaded files
- **High Quality**: Prefers pre-composed 1920x960 streams when available
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Quick Start

```bash
# Install
git clone <repo-url> && cd panopto-downloader
python3 -m venv venv && source venv/bin/activate
pip install -e .

# Download a single video
panopto-downloader download -u "https://mitsloan.hosted.panopto.com/..." -o "Lecture1.mp4"

# Download all streams (composed, camera, slides)
panopto-downloader download -u "https://..." -o "Lecture1" -a
```

## Installation

### Prerequisites

- macOS 13+ (Ventura or later)
- Python 3.12+
- Chrome or Safari (logged into Panopto)

### Install

```bash
# Clone repository
git clone https://github.com/yourusername/panopto-downloader.git
cd panopto-downloader

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install package
pip install -e .

# Verify installation
panopto-downloader --version
```

## Usage

### Quick Reference

```bash
panopto-downloader [OPTIONS] COMMAND [ARGS]

Commands:
  download   Download lectures from Panopto
  info       Show video information
  list       List configured lectures
  validate   Validate configuration
  init       Create new config file

Options:
  -c, --config PATH   Config file (default: config.yaml)
  -b, --browser TYPE  Browser for cookies (chrome/safari)
  -n, --dry-run       Preview without downloading
  -v, --verbose       Verbose output
  -h                  Quick help
  --help              Detailed help
  --version           Show version
```

### Download Commands

```bash
# Single video download
panopto-downloader download -u "URL" -o "filename.mp4"

# Download all three streams (composed, camera, slides)
panopto-downloader download -u "URL" -o "Lecture1" --all-streams

# Download ALL camera angles (PC1, PC2, Wideshot, chalkboards, etc.)
panopto-downloader download -u "URL" -o "Lecture1" --all-cameras --cookies cookies.txt

# Batch download from config
panopto-downloader download

# Parallel batch download with 3 workers
panopto-downloader download -p -w 3

# Sequential download (one at a time)
panopto-downloader download -s

# Dry run (preview only)
panopto-downloader download -n
```

### Other Commands

```bash
# Show video info and available streams
panopto-downloader info -u "URL"

# List configured lectures with download status
panopto-downloader list

# Validate config file
panopto-downloader validate

# Create new config file
panopto-downloader init
panopto-downloader init -o my_course.yaml
```

## Configuration

### Create Config

```bash
panopto-downloader init
# or
cp config.example.yaml config.yaml
```

### Config File Reference

```yaml
# Browser for cookie extraction (chrome or safari)
browser: chrome

# Download location (supports ~ for home directory)
download_path: ~/Videos/MIT_Lectures

# Naming format for output files
# Available: {course}, {title}, {date}
naming:
  format: "{course}_{title}_{date}"
  date_format: "%Y-%m-%d"

# Parallel download settings
download:
  parallel_workers: 2  # 1-10 concurrent downloads

# Resume/skip existing files
resume:
  enabled: true
  check_existing: true

# Retry on failure
retry:
  enabled: true
  max_attempts: 3

# Lectures to download
lectures:
  - url: https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=...
    title: "Capital Budgeting"
    course: "15.401"
    date: 2025-01-15
    instructor: Prof. Smith  # optional

  - url: https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=...
    title: "WACC and Cost of Capital"
    course: "15.401"
    date: 2025-01-22
```

### Multiple Config Files

Organize by course:

```bash
# Finance course
panopto-downloader -c finance.yaml download

# Strategy course
panopto-downloader -c strategy.yaml download
```

## Step-by-Step: Creating Your First Config File

### Step 1: Create the config file

```bash
panopto-downloader init -o finance.yaml
```

Or copy the example:
```bash
cp config.example.yaml finance.yaml
```

### Step 2: Open Panopto and collect lecture URLs

1. Go to your Panopto course folder in Chrome
2. For each lecture, click to open it
3. Copy the URL from the browser address bar
   - It looks like: `https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=abc123-def456...`

### Step 3: Edit the config file

Open `finance.yaml` in any text editor and fill in:

```yaml
# finance.yaml - Finance Management Course

browser: chrome
download_path: ~/Videos/Finance_Management

naming:
  format: "{course}_{title}_{date}"
  date_format: "%Y-%m-%d"

download:
  parallel_workers: 2

resume:
  check_existing: true

lectures:
  # Lecture 1
  - url: https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=YOUR-ID-HERE
    title: "Introduction to Finance"
    course: "15.401"
    date: 2025-01-08

  # Lecture 2
  - url: https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=YOUR-ID-HERE
    title: "Time Value of Money"
    course: "15.401"
    date: 2025-01-10

  # Add more lectures following the same pattern...
```

### Step 4: Validate the config

```bash
panopto-downloader -c finance.yaml validate
```

### Step 5: Preview (dry run)

```bash
panopto-downloader -c finance.yaml download -n
```

### Step 6: Download

```bash
# Close Chrome first, then:
panopto-downloader -c finance.yaml download
```

### YAML Syntax Tips

- **Indentation matters!** Use 2 spaces (not tabs)
- **Quotes around titles** with special characters: `title: "WACC & Cost of Capital"`
- **Dates** in YYYY-MM-DD format: `date: 2025-01-15`
- **URLs** can be with or without quotes
- **Comments** start with `#`

### Common Mistakes

```yaml
# ❌ WRONG - tabs instead of spaces
lectures:
	- url: https://...

# ❌ WRONG - missing dash before url
lectures:
  url: https://...

# ❌ WRONG - inconsistent indentation
lectures:
  - url: https://...
   title: "Lecture 1"

# ✅ CORRECT
lectures:
  - url: https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=abc123
    title: "Lecture 1"
    course: "15.401"
    date: 2025-01-15
```

## Stream Types

Panopto videos typically have three stream types:

| Type | Description | Resolution | Audio |
|------|-------------|------------|-------|
| Composed (PODCAST) | Pre-composed slides + camera | 1920x960 | ✓ |
| Camera (DV) | Main lecture video | 1280x720 | ✓ |
| Slides (OBJECT) | Slides only | 1366x768 | ✗ |

### Download Specific Streams

```bash
# Default: downloads composed (best quality pre-composed)
panopto-downloader download -u "URL" -o "lecture.mp4"

# All streams: composed, camera, and slides
panopto-downloader download -u "URL" -o "lecture" -a
# Creates: lecture_composed.mp4, lecture_camera.mp4, lecture_slides.mp4
```

## Authentication

The tool extracts cookies from your browser automatically.

### Requirements

1. Log into Panopto in Chrome or Safari
2. **Close Chrome completely** before running (Chrome locks its cookie database)

### Browser Selection

```bash
# Use Chrome (default)
panopto-downloader -b chrome download

# Use Safari
panopto-downloader -b safari download
```

### Cookie File (Alternative)

If browser extraction fails:

1. Install "Get cookies.txt LOCALLY" Chrome extension
2. Export cookies from Panopto page
3. Use cookies file:

```bash
yt-dlp --cookies cookies.txt "URL"
```

## Troubleshooting

### "Authentication failed" error

```bash
# 1. Make sure you're logged into Panopto in browser
# 2. Close Chrome completely (Cmd+Q)
# 3. Try again
panopto-downloader download -u "URL"
```

### "Operation not permitted" (Safari)

Safari has stricter sandboxing. Use Chrome instead:

```bash
panopto-downloader -b chrome download
```

### Wrong video downloaded (camera only instead of composed)

The tool now prefers PODCAST (composed) format. If you still get camera-only:

```bash
# Check available formats
yt-dlp -F --cookies-from-browser chrome "URL"

# Look for PODCAST format and note its ID (e.g., 8 or 10)
```

### Resume interrupted download

Just run the same command again - it skips completed files:

```bash
panopto-downloader download  # Skips already downloaded
```

## Examples

### Download Single Lecture

```bash
panopto-downloader download \
  -u "https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=abc123" \
  -o "Finance_Lecture1.mp4"
```

### Download All Streams for Archiving

```bash
panopto-downloader download \
  -u "https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=abc123" \
  -o "Finance_Lecture1" \
  --all-streams
```

### Batch Download Entire Course

1. Create config:

```yaml
# finance.yaml
browser: chrome
download_path: ~/Videos/Finance_15.401

lectures:
  - url: https://mitsloan.hosted.panopto.com/...?id=lecture1
    title: "Introduction to Finance"
    course: "15.401"
    date: 2025-01-08

  - url: https://mitsloan.hosted.panopto.com/...?id=lecture2
    title: "Time Value of Money"
    course: "15.401"
    date: 2025-01-10
  
  # ... add more lectures
```

2. Download:

```bash
panopto-downloader -c finance.yaml download -p -w 2
```

### Dry Run Preview

```bash
panopto-downloader download -n
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/panopto_downloader

# Format code
black src/ tests/

# Type checking
mypy src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.
