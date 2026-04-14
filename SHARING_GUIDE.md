# Panopto Downloader - Sharing Guide

This guide explains how to share the Panopto Downloader with others and how to set it up from scratch.

## For the Person Sharing (You)

### Option 1: Share via GitHub (Recommended)

1. **Create a GitHub repository:**
   ```bash
   cd /Users/arehman/Documents/Personal/Software/VideoDownloader
   git init
   git add .
   git commit -m "Initial commit - Panopto Downloader"
   # Create a new repository on GitHub, then:
   git remote add origin https://github.com/YOUR_USERNAME/panopto-downloader.git
   git push -u origin main
   ```

2. **Share the repository URL** with your friend

### Option 2: Share as ZIP file

1. **Create a clean package (without venv and cache):**
   ```bash
   cd /Users/arehman/Documents/Personal/Software/VideoDownloader
   
   # Create a distribution folder
   mkdir -p panopto-downloader-dist
   
   # Copy essential files
   cp -r src panopto-downloader-dist/
   cp -r tests panopto-downloader-dist/
   cp README.md panopto-downloader-dist/
   cp requirements.txt panopto-downloader-dist/
   cp pyproject.toml panopto-downloader-dist/
   cp LICENSE panopto-downloader-dist/
   cp config.example.yaml panopto-downloader-dist/
   
   # Copy example YAML files (optional)
   cp deploying_ai.yaml panopto-downloader-dist/
   cp disciplined_entrepreneurship.yaml panopto-downloader-dist/
   
   # Create ZIP
   zip -r panopto-downloader.zip panopto-downloader-dist/
   ```

2. **Share the ZIP file** via email, Google Drive, Dropbox, etc.

---

## For the Person Receiving (Installation Instructions)

### Prerequisites

- **macOS 13+** (Ventura or later)
- **Python 3.12 or later** (check with `python3 --version`)
- **Chrome or Safari** (must be logged into Panopto)

### Step 1: Download the Code

**If using GitHub:**
```bash
git clone https://github.com/YOUR_USERNAME/panopto-downloader.git
cd panopto-downloader
```

**If using ZIP file:**
```bash
# Extract the ZIP file, then:
cd panopto-downloader-dist
```

### Step 2: Set Up Python Environment

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# You should see (venv) at the start of your terminal prompt
# Example: (venv) username@computer panopto-downloader %
```

### Step 3: Install the Tool

```bash
# Install the package and all dependencies
pip install -e .

# Verify installation
panopto-downloader --version
```

You should see: `panopto-downloader, version 0.1.0`

### Step 4: Test with a Single Video

1. **Log into Panopto** in Chrome
2. **Copy a video URL** from Panopto
3. **Close Chrome completely** (Cmd+Q on Mac)
4. **Run a test download:**

```bash
panopto-downloader download \
  -u "YOUR_PANOPTO_URL_HERE" \
  -o "test_video.mp4"
```

### Step 5: Create Your First Course Config

```bash
# Create a new config file
panopto-downloader init -o my_course.yaml
```

Edit `my_course.yaml` to add your lecture URLs (see examples below).

### Step 6: Download Your Course

```bash
# Close Chrome first!
panopto-downloader -c my_course.yaml download
```

---

## How to Run in a New Terminal

Every time you open a new terminal, you need to:

### 1. Navigate to the project folder
```bash
cd /path/to/panopto-downloader
```

### 2. Activate the virtual environment
```bash
source venv/bin/activate
```

You'll see `(venv)` appear at the start of your prompt when activated.

### 3. Now you can use the tool
```bash
panopto-downloader --help
panopto-downloader -c my_course.yaml download
```

### Pro Tip: Create an Alias (Optional)

Add this to your `~/.zshrc` or `~/.bashrc`:

```bash
alias panopto='cd /path/to/panopto-downloader && source venv/bin/activate'
```

Then in any new terminal, just type:
```bash
panopto
panopto-downloader -c my_course.yaml download
```

---

## Example Config Files

### Example 1: Simple Course

```yaml
# my_course.yaml
browser: chrome
download_path: ~/Videos/My_Course

naming:
  format: "{course}_{title}_{date}"
  date_format: "%Y-%m-%d"

download:
  parallel_workers: 2
  download_all_streams: true

resume:
  check_existing: true

retry:
  enabled: true
  max_attempts: 3

lectures:
  - url: "https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=abc123"
    title: "Lecture 1 - Introduction"
    course: "My Course"
    date: 2026-01-10
    instructor: "Professor Name"

  - url: "https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=def456"
    title: "Lecture 2 - Fundamentals"
    course: "My Course"
    date: 2026-01-12
    instructor: "Professor Name"
```

### Example 2: Quick Download (4 lectures)

```yaml
# quick_download.yaml
browser: chrome
download_path: ~/Videos/Quick_Course

download:
  parallel_workers: 4

lectures:
  - url: "URL_1"
    title: "Lecture 1"
    course: "Course Name"
    date: 2026-01-10

  - url: "URL_2"
    title: "Lecture 2"
    course: "Course Name"
    date: 2026-01-11

  - url: "URL_3"
    title: "Lecture 3"
    course: "Course Name"
    date: 2026-01-12

  - url: "URL_4"
    title: "Lecture 4"
    course: "Course Name"
    date: 2026-01-13
```

---

## Common Commands Quick Reference

```bash
# Download from config
panopto-downloader -c course.yaml download

# Download single video
panopto-downloader download -u "URL" -o "filename.mp4"

# Preview without downloading
panopto-downloader -c course.yaml download -n

# List lectures in config
panopto-downloader -c course.yaml list

# Validate config file
panopto-downloader -c course.yaml validate

# Show video info
panopto-downloader info -u "URL"

# Get help
panopto-downloader --help
```

---

## Troubleshooting

### "panopto-downloader: command not found"

**Solution:** You forgot to activate the virtual environment!
```bash
source venv/bin/activate
```

### "Authentication failed" or "Unable to download"

**Solution:** 
1. Make sure you're logged into Panopto in Chrome
2. **Close Chrome completely** (Cmd+Q)
3. Try again immediately

### "Operation not permitted" (Safari)

**Solution:** Use Chrome instead:
```bash
panopto-downloader -b chrome download
```

### Downloads are slow

**Solution:** Increase parallel workers:
```yaml
download:
  parallel_workers: 4  # or higher
```

### Virtual environment not working

**Solution:** Recreate it:
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

---

## Best Practices

1. **Always close Chrome** before downloading (Chrome locks its cookie database)
2. **Use descriptive titles** in your YAML files for easy identification
3. **Organize by course** - create separate YAML files for each course
4. **Test with one video** before batch downloading
5. **Use dry run** (`-n` flag) to preview before downloading
6. **Keep backups** of your YAML config files

---

## Support

If you encounter issues:
1. Check the README.md for detailed documentation
2. Run with verbose mode: `panopto-downloader -v download`
3. Validate your config: `panopto-downloader -c yourfile.yaml validate`

---

## License

MIT License - Free to use, modify, and share.
