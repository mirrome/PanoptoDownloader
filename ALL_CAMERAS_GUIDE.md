# Downloading All Camera Angles from Panopto

## The Problem

Panopto videos often have **multiple camera angles** (PC1, PC2, Wideshot, Left, Right, Middle chalkboard, etc.) that you can switch between in the player. However, the standard download method only gets 3 streams:
- Composed (main view)
- Camera (primary)
- Slides

**You were missing:** PC1, PC2, Wideshot, and all the individual chalkboard cameras!

## The Solution: `--all-cameras` Flag

I've added direct Panopto API support to download **ALL camera angles** available in the video.

---

## How to Use

### Download All Camera Angles

```bash
panopto-downloader download \
  -u "PANOPTO_URL" \
  -o "Lecture_Name" \
  --all-cameras \
  --cookies cookies.txt
```

### Example: MIT Panopto Video

```bash
panopto-downloader download \
  -u "https://mit.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=3d72c71b-6020-41ca-8fff-b3df014248e4" \
  -o "Self_Attention_Lecture" \
  --all-cameras \
  --cookies cookies.txt
```

**What you get:**
- `Self_Attention_Lecture_tracking_camera.mp4` (2.0 GB)
- `Self_Attention_Lecture_wideshot_camera.mp4` (1.9 GB)
- `Self_Attention_Lecture_pc1_camera.mp4` (340 MB)
- `Self_Attention_Lecture_pc2_camera.mp4` (216 MB)
- `Self_Attention_Lecture_middle_chalkboard.mp4` (1.2 GB)
- `Self_Attention_Lecture_left_chalkboard.mp4` (1.2 GB)
- `Self_Attention_Lecture_right_chalkboard.mp4` (1.2 GB)

**Total: 7 camera angles!**

---

## Comparison: Standard vs All Cameras

### Standard Download (--all-streams)

```bash
panopto-downloader download -u "URL" -o "Lecture" --all-streams --cookies cookies.txt
```

**Downloads 3 streams:**
- Composed (slides + camera combined)
- Camera (primary camera)
- Slides (screen capture)

### All Cameras (--all-cameras)

```bash
panopto-downloader download -u "URL" -o "Lecture" --all-cameras --cookies cookies.txt
```

**Downloads ALL camera angles (typically 5-7):**
- Tracking camera
- Wideshot camera
- PC1 (Primary Camera 1)
- PC2 (Primary Camera 2)
- Middle chalkboard
- Left chalkboard
- Right chalkboard

---

## When to Use Each Option

### Use `--all-streams` when:
- You want the standard 3 views (composed, camera, slides)
- You're downloading from MIT Sloan Panopto (usually 3 streams)
- You want quick downloads with less data

### Use `--all-cameras` when:
- The video has multiple camera angles in the player
- You want to archive ALL available views
- You're downloading classroom recordings with multiple cameras
- You want the complete recording with all angles

---

## Requirements

### Must Have:
1. **Cookies file** - Required for authentication
   ```bash
   --cookies cookies.txt
   ```
   
2. **Direct Panopto URL** - Must be a single video URL

### Optional:
- `--no-write-subs` - Skip caption download to save time/space
- `-n` or `--dry-run` - Preview what would be downloaded

---

## Technical Details

### How It Works

1. **Queries Panopto API** - Uses `/Panopto/Pages/Viewer/DeliveryInfo.aspx` endpoint
2. **Discovers all streams** - Gets metadata for ALL camera streams
3. **Downloads each stream** - Downloads all camera angles individually
4. **Names appropriately** - Gives each camera a descriptive name

### Stream Types Detected

The tool automatically detects and names:
- **tracking_camera** - Main tracking/follow camera
- **wideshot_camera** - Wide angle classroom view
- **pc1_camera** - Primary Camera 1 (usually instructor)
- **pc2_camera** - Primary Camera 2 (alternate angle)
- **middle_chalkboard** - Middle chalkboard/whiteboard
- **left_chalkboard** - Left chalkboard/whiteboard
- **right_chalkboard** - Right chalkboard/whiteboard

---

## Examples

### Dry Run (Preview)

```bash
panopto-downloader download \
  -u "PANOPTO_URL" \
  -o "Lecture" \
  --all-cameras \
  --cookies cookies.txt \
  --dry-run
```

Shows what would be downloaded without actually downloading.

### Download Without Captions

```bash
panopto-downloader download \
  -u "PANOPTO_URL" \
  -o "Lecture" \
  --all-cameras \
  --cookies cookies.txt \
  --no-write-subs
```

Saves time by skipping caption downloads.

### Full Download with Everything

```bash
panopto-downloader download \
  -u "PANOPTO_URL" \
  -o "Lecture" \
  --all-cameras \
  --cookies cookies.txt
```

Downloads all cameras + all captions (default).

---

## Batch Download with YAML

You can also configure batch downloads to use all cameras. In your YAML file:

```yaml
# Add this to your YAML config
download:
  download_all_cameras: true  # Use --all-cameras for each video
  parallel_workers: 2  # Recommend fewer workers for all-cameras mode
```

**Note:** Batch mode with `--all-cameras` is not yet implemented, but you can download each lecture individually.

---

## File Sizes

Camera angle downloads can be large! Here's what to expect:

| Camera Type | Typical Size | Quality |
|-------------|--------------|---------|
| Tracking | 1.5-2.5 GB | 1920x1080, High bitrate |
| Wideshot | 1.5-2.5 GB | 1920x1080, High bitrate |
| PC1/PC2 | 200-400 MB | 672x382, Lower bitrate |
| Chalkboards | 1-1.5 GB each | 960-1352 resolution |

**Total for all 7 cameras:** ~8-12 GB per lecture

---

## Troubleshooting

### "Panopto API error: No streams found"

**Solution:** The video might not have multiple camera angles. Use `--all-streams` instead.

### "Authentication failed"

**Solution:** Make sure your cookies.txt is from the correct Panopto domain (MIT vs MIT Sloan).

### Downloads are slow

**Solution:** This is normal - you're downloading 7 separate video files! Each camera is downloaded sequentially.

### Some cameras failed to download

**Solution:** Some streams may be unavailable or restricted. The tool will download what's available and report which cameras succeeded/failed.

---

## Summary

**New flag:** `--all-cameras`

**What it does:** Downloads ALL camera angles from Panopto (not just the standard 3)

**When to use:** Multi-camera classroom recordings where you want every angle

**Requirements:** Cookies file for authentication

**Result:** 5-7 separate MP4 files, one for each camera angle

---

You now have access to **every camera angle** in the Panopto recording! 🎥📹
