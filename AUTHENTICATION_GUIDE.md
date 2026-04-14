# Alternative Authentication Methods

If you're having trouble with `--cookies-from-browser` (especially for MIT Panopto vs MIT Sloan Panopto), use a cookies file instead.

## Method 1: Export Cookies from Browser (No Need to Close Browser!)

### Step 1: Install Browser Extension

**Chrome/Edge:**
- Install "[Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)"

**Firefox:**
- Install "[cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)"

### Step 2: Export Cookies

1. Navigate to the Panopto site in your browser (e.g., `https://mit.hosted.panopto.com` or `https://mitsloan.hosted.panopto.com`)
2. Make sure you're logged in
3. Click the extension icon
4. Click "Export" or "Export As" → saves `cookies.txt` file
5. Move the file to your project folder

### Step 3: Use Cookies File

```bash
# Single video download with cookies file
panopto-downloader download \
  -u "https://mit.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=YOUR_VIDEO_ID" \
  -o "Lecture.mp4" \
  --cookies cookies.txt

# Download all streams with cookies file
panopto-downloader download \
  -u "https://mit.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=YOUR_VIDEO_ID" \
  -o "Lecture" \
  --all-streams \
  --cookies cookies.txt
```

**Benefits:**
- ✅ No need to close your browser
- ✅ Works for different Panopto domains (MIT vs MIT Sloan)
- ✅ More reliable authentication
- ✅ Can keep using browser while downloading

---

## Method 2: Use Different Browsers for Different Sites

If you have multiple Panopto accounts:

**For MIT Sloan Panopto:**
```bash
panopto-downloader -b chrome download ...
```

**For MIT Panopto:**
```bash
panopto-downloader -b safari download ...
# or use Firefox
panopto-downloader -b firefox download ...
```

---

## Downloading Captions/Subtitles

Captions are now **automatically downloaded by default**!

### Automatic (Default)
```bash
panopto-downloader download -u "URL" -o "Lecture.mp4"
# Downloads video + all available captions
```

### Disable Caption Download
If you want to skip captions:
```bash
panopto-downloader download -u "URL" -o "Lecture.mp4" --no-write-subs
```

### What Gets Downloaded

When captions are available, you'll get:
- `Lecture.mp4` - The video file
- `Lecture.en.vtt` - English captions (VTT format)
- `Lecture.en.srt` - English captions (SRT format, if available)
- Additional language files if available

**Caption formats:**
- `.vtt` - WebVTT format (works with most players)
- `.srt` - SubRip format (universal subtitle format)

Captions are also **embedded in the MP4 file** when possible, so they appear automatically in most video players.

---

## Troubleshooting Authentication

### Issue: "This video is only available for registered users"

**Solution 1: Use cookies.txt file**
```bash
# Export cookies from browser extension
panopto-downloader download -u "URL" -o "video.mp4" --cookies cookies.txt
```

**Solution 2: Check you're logged into correct Panopto**
- `mit.hosted.panopto.com` ≠ `mitsloan.hosted.panopto.com`
- These are different accounts!
- Use cookies.txt to avoid confusion

**Solution 3: Refresh your cookies**
- Logout and login again to Panopto
- Export fresh cookies.txt
- Try downloading again

### Issue: Cookies expired

Cookies typically last 1-2 weeks. If downloads fail:
1. Re-login to Panopto in browser
2. Export fresh cookies.txt
3. Try again

---

## Best Practice for Multiple Panopto Accounts

If you access both MIT and MIT Sloan Panopto:

```bash
# Export separate cookies files
cookies_mit.txt          # From mit.hosted.panopto.com
cookies_mitsloan.txt     # From mitsloan.hosted.panopto.com

# Use appropriate cookies for each site
panopto-downloader download -u "MIT_URL" --cookies cookies_mit.txt
panopto-downloader download -u "MIT_SLOAN_URL" --cookies cookies_mitsloan.txt
```

---

## Example: Complete Download with Cookies

```bash
# 1. Export cookies from mit.hosted.panopto.com (using browser extension)
#    Saves to: ~/Downloads/cookies.txt

# 2. Move cookies to your project
mv ~/Downloads/cookies.txt /path/to/VideoDownloader/

# 3. Download with all features
panopto-downloader download \
  -u "https://mit.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=3d72c71b-6020-41ca-8fff-b3df014248e4" \
  -o "Self_Attention_Lecture" \
  --all-streams \
  --cookies cookies.txt

# Result:
# ✅ All video streams downloaded
# ✅ All captions/subtitles downloaded
# ✅ No need to close browser
# ✅ Works reliably!
```

---

## Summary

**New authentication options:**
- `--cookies cookies.txt` - Use exported cookies file (recommended!)
- `-b chrome|safari|firefox` - Choose browser for cookie extraction

**Subtitle options:**
- Default: Captions downloaded automatically
- `--no-write-subs` - Skip caption download
- Captions embedded in MP4 when possible

**Browser extension to export cookies:**
- Chrome: "[Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)"
- Firefox: "[cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)"
