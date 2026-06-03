# 🛠️ Included FFmpeg

This folder contains the FFmpeg executables needed for video processing. **No separate installation required!**

## 📁 Contents

- **ffmpeg.exe** - Main video processing engine
- **ffprobe.exe** - Video analysis tool for getting file information
- **ffplay.exe** - Audio/video playback for intro preview (sound effects in preview)

## 🎯 Why Included?

FFmpeg is essential for video processing but can be challenging for users to install and configure properly. By including it in the package:

- ✅ **Zero setup required** - works immediately
- ✅ **No PATH configuration** needed 
- ✅ **No version conflicts** with other installations
- ✅ **Consistent behavior** across all systems
- ✅ **Portable package** - works from any folder

## 📊 Technical Details

- **Version**: FFmpeg 7.1.1 (essentials build)
- **Build**: Optimized for Windows with essential codecs
- **Size**: ~150MB (includes all necessary libraries)
- **License**: GPL v3 (open source)

## ⚙️ How It's Used

The script automatically uses these executables via:
```python
FFMPEG_PATH = os.path.join(SCRIPT_DIR, "ffmpeg", "ffmpeg.exe")
FFPROBE_PATH = os.path.join(SCRIPT_DIR, "ffmpeg", "ffprobe.exe")
FFPLAY_PATH = os.path.join(SCRIPT_DIR, "ffmpeg", "ffplay.exe")
```

All FFmpeg commands in the script reference these local executables instead of expecting FFmpeg to be in the system PATH.

## 🔧 Advanced Users

If you prefer to use your own FFmpeg installation:
1. Delete this ffmpeg folder
2. Modify the script to use `"ffmpeg"` and `"ffprobe"` directly
3. Ensure FFmpeg is in your system PATH

But for most users, the included version is the easiest and most reliable option!

---

**No more FFmpeg installation headaches!** 🎬✨