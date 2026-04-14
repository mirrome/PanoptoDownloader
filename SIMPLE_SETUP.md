# Panopto Downloader - Simple Setup

## ✅ Works on Windows, macOS, and Linux!

## 3-Step Setup (5 minutes)

### Step 1: Extract the ZIP
Unzip the file you received.

### Step 2: Run Setup Script

**On Windows (PowerShell):**
```powershell
cd panopto-downloader-package
.\setup.ps1
```

**On Windows (Command Prompt):**
```cmd
cd panopto-downloader-package
setup.bat
```

**On macOS/Linux (Terminal):**
```bash
cd panopto-downloader-package
./setup.sh
```

That's it! The script will automatically:
- Create a Python virtual environment
- Install all dependencies
- Verify everything works

### Step 3: Use the Tool

**On Windows (PowerShell):**
```powershell
# Activate the environment (do this in each new terminal)
.\venv\Scripts\Activate.ps1

# Create your first config
panopto-downloader init -o my_course.yaml

# Edit my_course.yaml to add your video URLs (see examples below)

# Download your videos
# (Log into Panopto in Chrome first, then close Chrome)
panopto-downloader -c my_course.yaml download
```

**On Windows (Command Prompt):**
```cmd
# Activate the environment
venv\Scripts\activate.bat

# Then use the tool the same way
panopto-downloader -c my_course.yaml download
```

**On macOS/Linux:**
```bash
# Activate the environment (do this in each new terminal)
source venv/bin/activate

# Create your first config
panopto-downloader init -o my_course.yaml

# Edit my_course.yaml to add your video URLs (see examples below)

# Download your videos
# (Log into Panopto in Chrome first, then close Chrome)
panopto-downloader -c my_course.yaml download
```

---

## Quick Config Example

Edit `my_course.yaml`:

```yaml
browser: chrome
download_path: ~/Videos/My_Lectures

download:
  parallel_workers: 4

lectures:
  - url: "https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=YOUR_ID_1"
    title: "Lecture 1"
    course: "My Course"
    date: 2026-01-15

  - url: "https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=YOUR_ID_2"
    title: "Lecture 2"
    course: "My Course"
    date: 2026-01-16
```

Replace `YOUR_ID_1`, `YOUR_ID_2`, etc. with your actual Panopto video IDs.

---

## Using in a New Terminal

**Windows (PowerShell):**
```powershell
cd panopto-downloader-package
.\venv\Scripts\Activate.ps1
panopto-downloader -c my_course.yaml download
```

**Windows (Command Prompt):**
```cmd
cd panopto-downloader-package
venv\Scripts\activate.bat
panopto-downloader -c my_course.yaml download
```

**macOS/Linux:**
```bash
cd panopto-downloader-package
source venv/bin/activate
panopto-downloader -c my_course.yaml download
```

---

## Troubleshooting

### Windows: "Execution policy" error in PowerShell

Fix:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then run `.\setup.ps1` again.

### macOS/Linux: "Permission denied" when running setup.sh

Fix:
```bash
chmod +x setup.sh
./setup.sh
```

### "panopto-downloader: command not found"

Fix: You forgot to activate the virtual environment

**Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
**Windows (cmd):** `venv\Scripts\activate.bat`
**macOS/Linux:** `source venv/bin/activate`

### "Authentication failed"

Fix: 
1. Log into Panopto in Chrome
2. **Close Chrome completely** (Cmd+Q on Mac)
3. Try downloading again immediately

---

---

## Browser Support

**Windows:** Chrome, Edge, Firefox, Opera, Brave
**macOS:** Chrome, Safari, Firefox, Opera, Brave
**Linux:** Chrome, Firefox, Opera, Brave

In your config file, use:
```yaml
browser: chrome  # or edge, firefox, safari (macOS only)
```

---

## Windows Users

See `WINDOWS_SETUP.md` for detailed Windows-specific instructions, including:
- PowerShell execution policy setup
- Path handling tips
- Browser configuration
- Windows-specific troubleshooting

---

## That's It!

You now have a working Panopto downloader. See example config files included in the package for more complex setups.
