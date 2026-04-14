# Panopto Downloader - Windows Setup Guide

## ✅ Yes, it works on Windows!

The Panopto Downloader works on **Windows 10/11**, **macOS**, and **Linux**.

---

## Windows Quick Setup

### Option 1: PowerShell (Recommended)

1. **Extract the ZIP** file
2. **Open PowerShell** in the extracted folder:
   - Right-click the folder → "Open in Terminal" or "Open PowerShell window here"
3. **Enable script execution** (one-time, if needed):
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
4. **Run setup**:
   ```powershell
   .\setup.ps1
   ```

### Option 2: Command Prompt (cmd)

1. **Extract the ZIP** file
2. **Open Command Prompt** in the extracted folder:
   - Type `cmd` in the folder address bar and press Enter
3. **Run setup**:
   ```cmd
   setup.bat
   ```

### Option 3: Git Bash (if you have Git installed)

```bash
cd panopto-downloader-package
./setup.sh
```

---

## After Setup - Using the Tool

### PowerShell:
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Create config
panopto-downloader init -o my_course.yaml

# Edit my_course.yaml with your URLs

# Download
panopto-downloader -c my_course.yaml download
```

### Command Prompt:
```cmd
# Activate environment
venv\Scripts\activate.bat

# Create config
panopto-downloader init -o my_course.yaml

# Edit my_course.yaml with your URLs

# Download
panopto-downloader -c my_course.yaml download
```

---

## Browser Support on Windows

**Supported browsers:**
- ✅ Chrome (recommended)
- ✅ Microsoft Edge
- ✅ Firefox
- ✅ Opera
- ✅ Brave

**Not supported:**
- ❌ Safari (macOS only)

### Using Chrome on Windows:
```yaml
browser: chrome
```

### Using Edge on Windows:
```yaml
browser: edge
```

---

## Platform Differences

| Feature | Windows | macOS | Linux |
|---------|---------|-------|-------|
| Chrome cookies | ✅ | ✅ | ✅ |
| Edge cookies | ✅ | ✅ | ✅ |
| Firefox cookies | ✅ | ✅ | ✅ |
| Safari cookies | ❌ | ✅ | ❌ |
| Setup script | `.bat` or `.ps1` | `.sh` | `.sh` |
| Activate venv | `venv\Scripts\activate` | `source venv/bin/activate` | `source venv/bin/activate` |
| Path separator | `\` | `/` | `/` |

---

## Example Windows Config

```yaml
# my_course.yaml
browser: chrome  # or edge, firefox, etc.
download_path: C:/Users/YourName/Videos/Lectures  # or use ~

naming:
  format: "{course}_{title}_{date}"
  date_format: "%Y-%m-%d"

download:
  parallel_workers: 4

lectures:
  - url: "https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=abc123"
    title: "Lecture 1"
    course: "My Course"
    date: 2026-01-15
```

**Note:** You can use forward slashes (`/`) in paths on Windows - Python handles this correctly!

---

## Troubleshooting Windows

### PowerShell: "Execution policy" error

**Error:**
```
.\setup.ps1 : File cannot be loaded because running scripts is disabled
```

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then run `.\setup.ps1` again.

### "Python is not recognized"

**Solution:**
1. Install Python from [python.org](https://www.python.org/downloads/)
2. **Important:** Check "Add Python to PATH" during installation
3. Restart your terminal
4. Run setup again

### "pip is not recognized"

**Solution:**
```cmd
python -m pip install --upgrade pip
```

### Chrome is locked / cookies can't be read

**Solution:**
1. Log into Panopto in Chrome
2. **Close Chrome completely** (File → Exit, or end all Chrome processes in Task Manager)
3. Run the download command immediately

### Antivirus blocking yt-dlp

Some antivirus software may flag `yt-dlp.exe`. This is a false positive. You may need to:
1. Add an exception for the `venv\Scripts` folder
2. Or temporarily disable antivirus during installation

---

## Windows Tips

### Create a Desktop Shortcut

1. Create a new `.bat` file on your desktop: `Panopto-Downloader.bat`
2. Edit it with:
   ```bat
   @echo off
   cd C:\path\to\panopto-downloader-package
   call venv\Scripts\activate.bat
   cmd /k
   ```
3. Double-click to open a terminal with the environment activated!

### Windows Terminal (Modern)

If you have [Windows Terminal](https://aka.ms/terminal):
- Better Unicode support (emojis, progress bars work better)
- Multiple tabs
- Better color support

---

## Summary

**Windows Setup:**
1. Extract ZIP
2. Run `setup.ps1` (PowerShell) or `setup.bat` (Command Prompt)
3. Done!

**To use:**
- Activate: `.\venv\Scripts\Activate.ps1` (PowerShell) or `venv\Scripts\activate.bat` (cmd)
- Download: `panopto-downloader -c my_course.yaml download`

**Works great on Windows!** 🎉
