# How to Run Panopto Downloader in a New Terminal

## The Problem
When you open a new terminal, you get `panopto-downloader: command not found` because the tool is installed in a **virtual environment** that needs to be activated first.

## The Solution: 2 Simple Steps

### Every time you open a new terminal:

#### Step 1: Navigate to the project folder
```bash
cd /Users/arehman/Documents/Personal/Software/VideoDownloader
```

#### Step 2: Activate the virtual environment
```bash
source venv/bin/activate
```

**You'll see `(venv)` appear at the start of your prompt:**
```
(venv) arehman@computer VideoDownloader %
```

#### Step 3: Now use the tool
```bash
# Download using a config file
panopto-downloader -c deploying_ai.yaml download

# Or download a single video
panopto-downloader download -u "URL" -o "video.mp4"

# List lectures
panopto-downloader -c deploying_ai.yaml list
```

---

## Quick Commands Reference

```bash
# Navigate and activate (do this FIRST in every new terminal)
cd /Users/arehman/Documents/Personal/Software/VideoDownloader
source venv/bin/activate

# Download Deploying AI lectures
panopto-downloader -c deploying_ai.yaml download

# Download Disciplined Entrepreneurship lectures
panopto-downloader -c disciplined_entrepreneurship.yaml download

# Download Organizations Lab lectures
panopto-downloader -c organizations_lab.yaml download

# Download Finance Management lectures
panopto-downloader -c finance_management.yaml download

# Download Marketing Management lectures
panopto-downloader -c marketing_management.yaml download
```

---

## Pro Tip: Create a Shortcut

Add this to your `~/.zshrc` file:

```bash
alias panopto='cd /Users/arehman/Documents/Personal/Software/VideoDownloader && source venv/bin/activate'
```

After reloading your terminal, you can just type:
```bash
panopto
# Now you're in the right folder with venv activated!
panopto-downloader -c deploying_ai.yaml download
```

### To add the alias:

1. Open your zsh config:
   ```bash
   nano ~/.zshrc
   ```

2. Add this line at the end:
   ```bash
   alias panopto='cd /Users/arehman/Documents/Personal/Software/VideoDownloader && source venv/bin/activate'
   ```

3. Save (Ctrl+O, Enter, Ctrl+X)

4. Reload:
   ```bash
   source ~/.zshrc
   ```

5. Now from any directory:
   ```bash
   panopto
   panopto-downloader -c deploying_ai.yaml download
   ```

---

## Why Do I Need to Activate the Virtual Environment?

Python virtual environments keep project dependencies isolated. The `panopto-downloader` command is installed in the `venv` folder, not system-wide. This prevents conflicts with other Python projects.

When you activate the venv:
- Your PATH is temporarily modified to find commands in `venv/bin/`
- Python uses packages from `venv/lib/python3.14/site-packages/`
- Deactivate anytime with: `deactivate`

---

## Summary

**Always remember these 2 steps in a new terminal:**

1. `cd /Users/arehman/Documents/Personal/Software/VideoDownloader`
2. `source venv/bin/activate`

Then you're good to go! 🚀
