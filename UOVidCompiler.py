#!/usr/bin/env python3
"""
B-Magic's Auto Vid Compiler - Universal Edition
A portable video compilation script for Ultima Online gameplay videos.
Compiles the last 5 seconds of videos with music and intro support.

[MUSIC] MUSIC INCLUDED: 10 royalty-free background tracks ready to use!
[VIDEO] STOCK INTRO: One bundled stock intro video (None / Stock / Random in the GUI).
[TOOLS] FFMPEG INCLUDED: No need to download or install FFmpeg separately!

Setup Instructions:
1. Edit only the video_folder and output_folder paths below (everything else included!)
2. Run the script - FFmpeg, music, and intros work automatically!

Completely self-contained package - no external dependencies!
"""

import os
import json
import subprocess
import random
import glob
import shutil
import shlex
import tempfile
import logging
import sys
import time
from pathlib import Path
from datetime import datetime

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(__file__)
APP_RUNTIME_ROOT = os.environ.get("AUTOVID_STORAGE_DIR", "").strip()
LOG_FILE_PATH = ""


def get_runtime_root():
    if APP_RUNTIME_ROOT:
        path = APP_RUNTIME_ROOT
    elif getattr(sys, 'frozen', False):
        root = os.environ.get("APPDATA") or os.environ.get("PROGRAMDATA") or os.path.expanduser("~")
        path = os.path.join(root, "KnightLogics", "AutoVidCompiler")
    else:
        path = SCRIPT_DIR
    os.makedirs(path, exist_ok=True)
    return path


def get_logs_dir(log_dir=None):
    resolved = str(log_dir or os.environ.get("AUTOVID_LOG_DIR", "") or "").strip()
    if not resolved:
        resolved = os.path.join(get_runtime_root(), "logs")
    os.makedirs(resolved, exist_ok=True)
    return resolved


def get_log_file_path():
    return LOG_FILE_PATH


def _resolve_log_level(log_level=None):
    level_name = str(log_level or os.environ.get("AUTOVID_LOG_LEVEL", "DEBUG") or "DEBUG").upper()
    return getattr(logging, level_name, logging.DEBUG)


def _get_console_stream():
    for candidate in (getattr(sys, "stdout", None), getattr(sys, "__stdout__", None)):
        if candidate is not None and hasattr(candidate, "write"):
            return candidate
    return None

# Set up enhanced logging
def setup_logging(log_dir=None, log_level=None):
    """Set up logging with both file and console output"""

    logs_dir = get_logs_dir(log_dir)
    log_filename = f"bmagic_autovidcompiler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file = os.path.join(logs_dir, log_filename)

    app_logger = logging.getLogger("KnightLogics.AutoVidCompiler")
    app_logger.setLevel(_resolve_log_level(log_level))
    app_logger.propagate = False

    for handler in list(app_logger.handlers):
        app_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(app_logger.level)
    file_handler.setFormatter(formatter)
    app_logger.addHandler(file_handler)

    console_stream = _get_console_stream()
    if console_stream is not None:
        console_handler = logging.StreamHandler(console_stream)
        console_handler.setLevel(app_logger.level)
        console_handler.setFormatter(formatter)
        app_logger.addHandler(console_handler)

    global LOG_FILE_PATH
    LOG_FILE_PATH = log_file

    app_logger.info(f"B-Magic's Auto Vid Compiler started - Log file: {log_file}")
    app_logger.debug(
        "Logging context: frozen=%s runtime_root=%s script_dir=%s cwd=%s python=%s gui_mode=%s",
        getattr(sys, 'frozen', False),
        get_runtime_root(),
        SCRIPT_DIR,
        os.getcwd(),
        sys.executable,
        os.environ.get('GUI_MODE', ''),
    )
    return app_logger


def configure_logging(log_dir=None, log_level=None):
    if log_dir:
        os.environ["AUTOVID_LOG_DIR"] = str(log_dir)
    if log_level:
        os.environ["AUTOVID_LOG_LEVEL"] = str(log_level).upper()

    global logger
    logger = setup_logging(log_dir=log_dir, log_level=log_level)
    return logger

# Initialize logging
logger = setup_logging()

def generate_timestamped_filename(base_filename):
    """Generate a filename with timestamp to prevent overwrites"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(base_filename)
    return f"{name}_{timestamp}{ext}"

def safe_print(text):
    """Print text with emoji fallbacks for Windows console compatibility"""
    # Replace emojis with ASCII equivalents for universal compatibility
    emoji_map = {
        '[GAME]': '[GAME]',
        '[VIDEO]': '[VIDEO]',
        '[FOLDER]': '[FOLDER]',
        '[OUTPUT]': '[OUTPUT]',
        '[INPUT]': '[INPUT]',
        '[WARNING]': '[WARNING]',
        '[OK]': '[OK]',
        '[ERROR]': '[ERROR]',
        '[PROCESS]': '[PROCESS]',
        '[MUSIC]': '[MUSIC]',
        '[INTRO]': '[INTRO]'
    }
    
    for emoji, replacement in emoji_map.items():
        text = text.replace(emoji, replacement)
    
    try:
        print(text, flush=True)  # Force immediate output
    except UnicodeEncodeError:
        # If still encoding issues, strip any remaining non-ASCII
        ascii_text = text.encode('ascii', 'replace').decode('ascii')
        print(ascii_text, flush=True)

# FFmpeg paths (included in package)
FFMPEG_PATH = os.path.join(SCRIPT_DIR, "ffmpeg", "ffmpeg.exe")
FFPROBE_PATH = os.path.join(SCRIPT_DIR, "ffmpeg", "ffprobe.exe")

# ===== CONFIGURATION SECTION =====
# Paths can be set via environment variables from GUI or edit these defaults

# Primary path configuration - now supports GUI configuration
VIDEO_INPUT_PATH = os.environ.get('VIDEO_INPUT_PATH', os.path.expanduser(r"~/Videos/Captures"))
VIDEO_OUTPUT_PATH = os.environ.get('VIDEO_OUTPUT_PATH', os.path.expanduser(r"~/Downloads"))

# Video configuration options - can be set by GUI
trim_value = os.environ.get('TRIM_SECONDS', '15')
TRIM_SECONDS = int(trim_value) if trim_value != 'None' else None  # None means use full video length
MUSIC_SELECTION = os.environ.get('MUSIC_SELECTION', '')  # 'None' means no music
INTRO_SELECTION = os.environ.get('INTRO_SELECTION', '')  # 'None' means no intro
CLIP_ORDER = os.environ.get('CLIP_ORDER', 'newest_first')
CUSTOM_ORDER_FILE = os.environ.get('CUSTOM_ORDER_FILE', '')
CLIP_TIMEFRAME = os.environ.get('CLIP_TIMEFRAME', '1_week')
MUSIC_FOLDER = os.environ.get('MUSIC_FOLDER', os.path.join(os.path.dirname(__file__), "Music"))
INTRO_FOLDER = os.environ.get('INTRO_FOLDER', os.path.join(os.path.dirname(__file__), "Intros"))
# Resolution automatically detected - no GUI option needed for universal compatibility

CONFIG = {
    # Video source folder (where your game recordings are saved)
    "video_folder": VIDEO_INPUT_PATH,
    
    # Music folder (background music for compilations) - Using included music
    "music_folder": MUSIC_FOLDER,
    
    # Output folder (where compiled videos will be saved)
    "output_folder": VIDEO_OUTPUT_PATH,
    
    # Intro folder (optional intro videos) - Using included intros
    "intro_folder": INTRO_FOLDER,
    
    # Video configuration
    "trim_seconds": TRIM_SECONDS,
    "music_selection": MUSIC_SELECTION,
    "intro_selection": INTRO_SELECTION,
    "clip_order": CLIP_ORDER,
    "custom_order_file": CUSTOM_ORDER_FILE,
    "clip_timeframe": CLIP_TIMEFRAME,
    
    # Output filename (will be timestamped automatically)
    "output_filename": "BMagic_Compilation.mp4",
    
    # Intro settings
    "use_intro": INTRO_SELECTION != 'None' if INTRO_SELECTION else True,  # False if 'None' selected
    "intro_duration": 7.0,      # Maximum duration in seconds (will use full length if shorter)
    
    # Video settings
    "clip_duration": float(TRIM_SECONDS) if TRIM_SECONDS else 999999.0,  # Use full length if None selected
    "video_extensions": [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"],
    "intro_extensions": [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".gif"],
    "music_extensions": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"],
    
    # Quality settings (Using S+ working resolution)
    "output_resolution": "2560x1056",  # S+ working resolution for wide compilations
    "output_fps": 30,
    "video_bitrate": "5000k",
    "audio_bitrate": "192k"
}
# ===== END CONFIGURATION SECTION =====

def report_progress(percent, message):
    """Send coarse progress updates to the GUI when available."""
    callback = CONFIG.get("progress_callback")
    if callable(callback):
        try:
            callback(float(percent), str(message))
        except Exception:
            pass


def cancellation_requested():
    """Return True when the GUI requested cancellation."""
    callback = CONFIG.get("cancel_callback")
    if callable(callback):
        try:
            return bool(callback())
        except Exception:
            return False
    return False

def setup_check():
    """Enhanced setup validation with detailed feedback"""
    safe_print("[GAME] " + "="*60)
    safe_print("[GAME]   B-MAGIC'S AUTO VID COMPILER - UNIVERSAL EDITION")
    safe_print("[GAME] " + "="*60)
    safe_print("[SEARCH] Performing system validation...")
    
    issues = []
    
    # Check for placeholder paths
    if "YourUsername" in CONFIG["video_folder"] or "YourUsername" in CONFIG["output_folder"]:
        issues.append("[ERROR] Placeholder paths detected")
        safe_print("\n[ERROR] SETUP REQUIRED:")
        safe_print("   Please edit the path configuration:")
        safe_print(f"   VIDEO_INPUT_PATH = r\"{VIDEO_INPUT_PATH}\"")
        safe_print(f"   VIDEO_OUTPUT_PATH = r\"{VIDEO_OUTPUT_PATH}\"")
        safe_print("   Replace these with your actual folder paths.")
    
    # Check input folder exists
    if not os.path.exists(CONFIG["video_folder"]):
        issues.append("[ERROR] Input folder not found")
        safe_print(f"\n[ERROR] INPUT FOLDER ERROR:")
        safe_print(f"   Folder not found: {CONFIG['video_folder']}")
        safe_print("   Please set VIDEO_INPUT_PATH to your actual recordings folder.")
    else:
        logger.info(f"[OK] Input folder verified: {CONFIG['video_folder']}")
        
        # Count video files
        video_files = get_video_files(CONFIG["video_folder"])
        if video_files:
            safe_print(f"[OK] Found {len(video_files)} video files in input folder")
            logger.info(f"Video files found: {[os.path.basename(f) for f in video_files[:5]]}")
        else:
            issues.append("[WARNING] No video files found in input folder")
            safe_print(f"[WARNING] No video files found in: {CONFIG['video_folder']}")
    
    # Check FFmpeg
    if not os.path.exists(FFMPEG_PATH):
        issues.append("[ERROR] FFmpeg not found")
        safe_print(f"\n[ERROR] FFMPEG ERROR:")
        safe_print(f"   FFmpeg not found at: {FFMPEG_PATH}")
    else:
        safe_print(f"[OK] FFmpeg found: {FFMPEG_PATH}")
        logger.info(f"FFmpeg verified at: {FFMPEG_PATH}")
    
    # Check music folder
    music_files = [f for f in os.listdir(CONFIG["music_folder"]) 
                   if any(f.lower().endswith(ext) for ext in CONFIG["music_extensions"])]
    safe_print(f"[MUSIC] Music tracks available: {len(music_files)}")
    
    # Check intro folder
    if CONFIG["use_intro"]:
        intro_files = [f for f in os.listdir(CONFIG["intro_folder"]) 
                      if any(f.lower().endswith(ext) for ext in CONFIG["intro_extensions"])]
        safe_print(f"[VIDEO] Intro media files available: {len(intro_files)}")
    
    # Create output folder if it doesn't exist
    if not os.path.exists(CONFIG["output_folder"]):
        try:
            os.makedirs(CONFIG["output_folder"], exist_ok=True)
            safe_print(f"[OK] Created output folder: {CONFIG['output_folder']}")
            logger.info(f"Created output directory: {CONFIG['output_folder']}")
        except Exception as e:
            issues.append("[ERROR] Cannot create output folder")
            safe_print(f"[ERROR] Cannot create output folder: {e}")
            logger.error(f"Failed to create output directory: {e}")
    else:
        safe_print(f"[OK] Output folder verified: {CONFIG['output_folder']}")
    
    if issues:
        safe_print(f"\n[STOP] Found {len(issues)} issue(s) that need to be resolved:")
        for issue in issues:
            safe_print(f"   {issue}")
        safe_print("\nPlease fix these issues before running the compiler.")
        logger.warning(f"Setup validation failed: {', '.join(issues)}")
        return False
    else:
        safe_print("\n[CELEBRATE] All checks passed! Ready to compile videos.")
        logger.info("Setup validation completed successfully")
        return True
        safe_print(f"Example: Change {CONFIG['video_folder']}")
        safe_print(f"      To: C:\\Users\\JohnDoe\\Videos\\Captures")
        return False
    
    # Check if video folder exists
    if not os.path.exists(CONFIG["video_folder"]):
        safe_print(f"\n[ERROR] Video folder not found: {CONFIG['video_folder']}")
        safe_print("Please update CONFIG['video_folder'] to point to your video captures folder.")
        return False
    
    # Check if FFmpeg is available (included in package)
    if os.path.exists(FFMPEG_PATH) and os.path.exists(FFPROBE_PATH):
        safe_print("[OK] FFmpeg found (included in package)")
    else:
        safe_print("\n[ERROR] FFmpeg files missing from package!")
        safe_print(f"Expected: {FFMPEG_PATH}")
        safe_print(f"Expected: {FFPROBE_PATH}")
        safe_print("Please ensure the ffmpeg folder is included with this script.")
        return False
    
    safe_print("[OK] Configuration looks good!")
    return True

def auto_detect_paths():
    """Try to auto-detect common Windows video capture locations"""
    username = os.getenv('USERNAME')
    if not username:
        return None
    
    common_paths = [
        rf"C:\Users\{username}\Videos\Captures",
        rf"C:\Users\{username}\Videos",
        rf"C:\Users\{username}\Documents\My Games\Screenshots",
        rf"C:\Users\{username}\Desktop\Videos"
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None

def terminate_process_tree(process):
    """Terminate an FFmpeg shell wrapper and any child process it spawned."""
    if not process or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        else:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def run_ffmpeg_command(command, timeout=60):
    """Run an FFmpeg command and return the result with timeout"""
    try:
        if cancellation_requested():
            return False, "", "Cancelled by user"
        popen_command = shlex.split(command) if os.name == "nt" and isinstance(command, str) else command
        process = subprocess.Popen(
            popen_command,
            shell=os.name != "nt",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        deadline = time.time() + timeout if timeout else None
        while True:
            if cancellation_requested():
                terminate_process_tree(process)
                return False, "", "Cancelled by user"
            if deadline and time.time() >= deadline:
                terminate_process_tree(process)
                try:
                    process.communicate(timeout=5)
                except Exception:
                    pass
                return False, "", f"FFmpeg command timed out after {timeout} seconds"
            try:
                communicate_timeout = 0.25
                if deadline:
                    communicate_timeout = max(0.05, min(0.25, deadline - time.time()))
                stdout, stderr = process.communicate(timeout=communicate_timeout)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode != 0:
            return False, stdout, stderr
        return True, stdout, stderr
    except subprocess.TimeoutExpired:
        return False, "", f"FFmpeg command timed out after {timeout} seconds"
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def get_video_info(video_path):
    """Get video information using ffprobe"""
    command = f'"{FFPROBE_PATH}" -v quiet -print_format json -show_format -show_streams "{video_path}"'
    success, stdout, stderr = run_ffmpeg_command(command)
    
    if success:
        try:
            data = json.loads(stdout)
            video_streams = [stream for stream in data['streams'] if stream['codec_type'] == 'video']
            if video_streams:
                video_stream = video_streams[0]
                width = int(video_stream['width'])
                height = int(video_stream['height'])
                duration = float(video_stream.get('duration', data['format'].get('duration', 0)))
                return width, height, duration
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing video info for {video_path}: {e}")
    
    return None, None, None

def detect_optimal_resolution(video_folder):
    """
    Smart resolution detection - analyzes user's videos to determine optimal output resolution
    This makes the script universal across different gaming setups and monitor configurations
    """
    resolution_counts = {}
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
    sample_count = 0
    max_samples = 10  # Analyze up to 10 recent videos for performance
    
    safe_print("[SEARCH] Analyzing your video resolution patterns...")
    
    try:
        # Get recent video files for analysis
        video_files = []
        for ext in video_extensions:
            files = Path(video_folder).glob(f"*{ext}")
            video_files.extend([(f, os.path.getctime(f)) for f in files])
        
        # Sort by creation time (newest first) and limit samples
        video_files.sort(key=lambda x: x[1], reverse=True)
        video_files = video_files[:max_samples]
        
        for video_file, _ in video_files:
            width, height, duration = get_video_info(str(video_file))
            if width and height:
                # Normalize resolution to standard aspect ratios
                aspect_ratio = width / height
                
                if aspect_ratio > 2.3:  # Ultra-wide (21:9, 32:9, etc)
                    if width >= 3440:
                        resolution = "3440x1440"  # UWQHD
                    elif width >= 2560:
                        resolution = "2560x1080"  # Ultra-wide standard
                    else:
                        resolution = "2560x1080"
                elif aspect_ratio > 1.7:  # Wide aspect ratios (16:9, 16:10)
                    if width >= 2560:
                        resolution = "2560x1440"  # 1440p
                    elif width >= 1920:
                        resolution = "1920x1080"  # 1080p
                    else:
                        resolution = "1280x720"   # 720p
                else:  # Standard/square ratios
                    resolution = "1920x1080"  # Default fallback
                
                resolution_counts[resolution] = resolution_counts.get(resolution, 0) + 1
                sample_count += 1
                
                safe_print(f"   [VIDEO] {Path(video_file).name}: {width}x{height} -> {resolution}")
    
    except Exception as e:
        safe_print(f"[WARNING] Resolution detection error: {e}")
    
    # Determine optimal resolution
    if resolution_counts:
        # Use the most common resolution found
        optimal_resolution = max(resolution_counts.items(), key=lambda x: x[1])[0]
        confidence = resolution_counts[optimal_resolution] / sample_count * 100
        
        safe_print(f"[OK] Detected optimal resolution: {optimal_resolution} ({confidence:.0f}% confidence)")
        safe_print(f"   Analysis based on {sample_count} recent videos")
        return optimal_resolution
    else:
        # Fallback to a versatile standard
        fallback_resolution = "1920x1080"
        safe_print(f"[WARNING] No videos found for analysis, using fallback: {fallback_resolution}")
        return fallback_resolution

def has_audio_stream(video_path):
    """Check if video has audio stream using ffprobe"""
    command = f'"{FFPROBE_PATH}" -v quiet -print_format json -show_streams "{video_path}"'
    success, stdout, stderr = run_ffmpeg_command(command)
    
    if success:
        try:
            data = json.loads(stdout)
            audio_streams = [stream for stream in data['streams'] if stream['codec_type'] == 'audio']
            return len(audio_streams) > 0
        except (json.JSONDecodeError, KeyError, ValueError):
            return False
    return False

def extract_intro_clip(input_path, output_path, max_duration=7.0):
    """Extract intro clip from the beginning of a video (not the end like gameplay clips)"""
    
    width, height, total_duration = get_video_info(input_path)
    
    if total_duration is None or total_duration <= 0:
        safe_print(f"[WARNING] Warning: Could not get duration for {input_path}")
        return False
    
    # For intros, take from the beginning up to max_duration
    start_time = 0
    if total_duration <= max_duration:
        # Use the entire intro if it's shorter than max_duration
        extract_duration = total_duration
    else:
        # Take the first max_duration seconds
        extract_duration = max_duration
    
    # Extract the intro clip from the beginning
    if has_audio_stream(input_path):
        # Video has audio - extract normally
        command = f'"{FFMPEG_PATH}" -y -ss {start_time} -i "{input_path}" -t {extract_duration} -c:v libx264 -preset fast -crf 23 -c:a aac -b:a {CONFIG["audio_bitrate"]} "{output_path}"'
    else:
        # Video has no audio - add silent audio track
        command = f'"{FFMPEG_PATH}" -y -ss {start_time} -i "{input_path}" -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -t {extract_duration} -c:v libx264 -preset fast -crf 23 -c:a aac -b:a {CONFIG["audio_bitrate"]} -shortest "{output_path}"'
    
    success, stdout, stderr = run_ffmpeg_command(command, timeout=90)  # Give intro extraction more time
    
    if not success:
        safe_print(f"[ERROR] Error extracting intro from {input_path}: {stderr}")
    
    return success

def extract_last_n_seconds(input_path, output_path, duration=5.0):
    """Extract the last N seconds from a video"""
    width, height, total_duration = get_video_info(input_path)
    
    if total_duration is None or total_duration <= 0:
        print(f"Warning: Could not get duration for {input_path}")
        return False

    if total_duration <= duration:
        # If video is shorter than requested duration, use the whole video
        start_time = 0
        extract_duration = total_duration
    else:
        start_time = total_duration - duration
        extract_duration = duration

    # Extract the clip
    if has_audio_stream(input_path):
        # Video has audio - extract normally
        command = f'"{FFMPEG_PATH}" -y -ss {start_time} -i "{input_path}" -t {extract_duration} -c:v libx264 -preset fast -crf 23 -c:a aac -b:a {CONFIG["audio_bitrate"]} "{output_path}"'
    else:
        # Video has no audio - add silent audio track
        command = f'"{FFMPEG_PATH}" -y -ss {start_time} -i "{input_path}" -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -t {extract_duration} -c:v libx264 -preset fast -crf 23 -c:a aac -b:a {CONFIG["audio_bitrate"]} -shortest "{output_path}"'

    success, stdout, stderr = run_ffmpeg_command(command)
    if not success:
        print(f"Error extracting from {input_path}: {stderr}")

    return success


def extract_smart_clip(input_path, output_path, start_time, extract_duration):
    """Extract a clip with precise start time and duration to avoid overlaps"""
    width, height, total_duration = get_video_info(input_path)
    
    if total_duration is None or total_duration <= 0:
        print(f"Warning: Could not get duration for {input_path}")
        return False
    
    # Validate extraction parameters
    if start_time < 0:
        start_time = 0
    if start_time >= total_duration:
        print(f"Warning: Start time {start_time}s exceeds video duration {total_duration}s")
        return False
    if start_time + extract_duration > total_duration:
        extract_duration = total_duration - start_time
    if extract_duration <= 0:
        print(f"Warning: No content to extract (duration would be {extract_duration}s)")
        return False
    
    logger.info(f"Smart extract: {input_path} -> start={start_time:.3f}s, duration={extract_duration:.3f}s")
    
    # Extract the clip with precise timing
    if has_audio_stream(input_path):
        command = f'"{FFMPEG_PATH}" -y -ss {start_time} -i "{input_path}" -t {extract_duration} -c:v libx264 -preset fast -crf 23 -c:a aac -b:a {CONFIG["audio_bitrate"]} "{output_path}"'
    else:
        command = f'"{FFMPEG_PATH}" -y -ss {start_time} -i "{input_path}" -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -t {extract_duration} -c:v libx264 -preset fast -crf 23 -c:a aac -b:a {CONFIG["audio_bitrate"]} -shortest "{output_path}"'
    
    success, stdout, stderr = run_ffmpeg_command(command)
    if not success:
        print(f"Error extracting smart clip from {input_path}: {stderr}")
    
    return success


def calculate_smart_clips(video_files, clip_duration):
    """
    Calculate smart clip parameters to avoid overlapping content.
    Accounts for retroactive/buffered recording (Xbox Game Bar, OBS replay buffer).
    
    Args:
        video_files: List of video file paths sorted by modification time (newest first)
        clip_duration: Desired clip duration from GUI
        
    Returns:
        List of tuples: (video_path, start_time, duration, creation_timestamp)
    """
    if not video_files:
        return []
    
    # Get file timestamps (creation time) and sort oldest to newest for chronological processing
    video_data = []
    for video_path in video_files:
        try:
            creation_time = os.path.getctime(video_path)  # When file was created (AFTER recording)
            mod_time = os.path.getmtime(video_path)      # Modification timestamp  
            # Use creation time for overlap detection, fallback to modification time
            timestamp = creation_time if creation_time > 0 else mod_time
            video_data.append((video_path, timestamp))
        except Exception as e:
            logger.warning(f"Could not get timestamp for {video_path}: {e}")
            continue
    
    # Sort by timestamp (oldest first) for chronological processing
    video_data.sort(key=lambda x: x[1])
    
    smart_clips = []
    last_clip_end_in_footage = 0  # Track when the EXTRACTED CLIP ends in the actual footage timeline
    clip_settings = _load_clip_settings()
    requested_total_duration = 0.0
    
    for i, (video_path, creation_timestamp) in enumerate(video_data):
        # Get video duration
        width, height, total_duration = get_video_info(video_path)
        if total_duration is None or total_duration <= 0:
            logger.warning(f"Skipping {video_path} - cannot determine duration")
            continue

        requested_clip_duration = _get_clip_duration_for_path(video_path, clip_duration, clip_settings)
        requested_total_duration += min(total_duration, requested_clip_duration)
        
        # For buffered recording: footage timeline is BEFORE file creation
        # Actual footage spans: (creation_timestamp - total_duration) to creation_timestamp
        footage_start_timestamp = creation_timestamp - total_duration
        footage_end_timestamp = creation_timestamp
        
        # Determine what to extract (last N seconds)
        if total_duration <= requested_clip_duration:
            start_time = 0
            extract_duration = total_duration
        else:
            start_time = total_duration - requested_clip_duration  # Extract LAST requested clip seconds
            extract_duration = requested_clip_duration
        
        # Calculate when this extracted clip exists in the footage timeline
        clip_start_in_footage = footage_start_timestamp + start_time
        clip_end_in_footage = clip_start_in_footage + extract_duration
        
        # For first video, no overlap checking needed
        if i == 0:
            smart_clips.append((video_path, start_time, extract_duration, creation_timestamp))
            last_clip_end_in_footage = clip_end_in_footage
            
            logger.info(f"First clip: {os.path.basename(video_path)} -> start={start_time:.3f}s, duration={extract_duration:.3f}s, footage_timeline={clip_start_in_footage:.1f}-{clip_end_in_footage:.1f}")
            continue
        
        # Check for overlap with previous extracted clip's footage
        time_gap = clip_start_in_footage - last_clip_end_in_footage
        
        if time_gap >= 0:
            # No overlap - extracted clips are chronologically separate
            logger.info(f"No overlap: {os.path.basename(video_path)} (gap: {time_gap:.1f}s) -> start={start_time:.3f}s, duration={extract_duration:.3f}s")
            smart_clips.append((video_path, start_time, extract_duration, creation_timestamp))
            last_clip_end_in_footage = clip_end_in_footage
        
        else:
            # OVERLAP DETECTED in extracted clips
            overlap_duration = abs(time_gap)
            
            logger.info(f"Overlap detected: {os.path.basename(video_path)} (overlap: {overlap_duration:.1f}s)")
            
            # Adjust start_time to skip the overlapping footage
            # We need to start AFTER the previous clip ended
            overlap_offset_in_video = overlap_duration
            
            # Check if we have enough footage left after skipping overlap
            new_start_time = start_time + overlap_offset_in_video
            
            if new_start_time >= total_duration:
                # Entire extracted clip would be overlapping - skip this video
                logger.warning(f"Skipping {os.path.basename(video_path)} - entire clip overlaps with previous")
                continue
            
            # Calculate remaining duration after skipping overlap
            remaining_duration = total_duration - new_start_time
            new_extract_duration = min(requested_clip_duration - overlap_duration, remaining_duration)
            
            if new_extract_duration <= 0.5:
                # Too short after removing overlap - skip it
                logger.warning(f"Skipping {os.path.basename(video_path)} - remaining duration too short ({new_extract_duration:.3f}s)")
                continue
            
            # Use adjusted extraction parameters
            start_time = new_start_time
            extract_duration = new_extract_duration
            
            # Recalculate footage timeline with adjusted extraction
            clip_start_in_footage = footage_start_timestamp + start_time
            clip_end_in_footage = clip_start_in_footage + extract_duration
            
            logger.info(f"Adjusted for overlap: {os.path.basename(video_path)} -> start={start_time:.3f}s, duration={extract_duration:.3f}s")
            
            smart_clips.append((video_path, start_time, extract_duration, creation_timestamp))
            last_clip_end_in_footage = clip_end_in_footage
    
    smart_clips = order_smart_clips_for_output(smart_clips)
    
    # Enhanced logging summary for validation
    logger.info(f"Smart clip calculation complete: {len(smart_clips)} clips from {len(video_files)} videos")
    safe_print(f"\n[SUMMARY] SMART CLIP SUMMARY:")
    total_original_duration = requested_total_duration
    total_smart_duration = sum(clip[2] for clip in smart_clips)
    overlap_time_saved = total_original_duration - total_smart_duration
    
    safe_print(f"   [STATS] Requested duration (pre-overlap): {total_original_duration:.1f}s")
    safe_print(f"   [SMART] Smart duration (no overlap): {total_smart_duration:.1f}s")
    safe_print(f"   [TIME] Overlap time eliminated: {overlap_time_saved:.1f}s")
    efficiency_gain = (overlap_time_saved / total_original_duration * 100) if total_original_duration > 0 else 0
    safe_print(f"   [TARGET] Efficiency gain: {efficiency_gain:.1f}%")
    
    for i, (video_path, start_time, extract_duration, timestamp) in enumerate(smart_clips):
        creation_time = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]
        safe_print(f"   [{i+1}] {os.path.basename(video_path)[:30]:30} | {creation_time} | {start_time:6.2f}s->{start_time+extract_duration:6.2f}s ({extract_duration:5.2f}s)")
    
    return smart_clips


def _load_custom_order_map():
    order_file = str(CONFIG.get("custom_order_file", "") or "").strip()
    if not order_file or not os.path.exists(order_file):
        return {}
    try:
        with open(order_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        paths = data.get("paths", data if isinstance(data, list) else [])
        return {os.path.normcase(os.path.abspath(path)): index for index, path in enumerate(paths)}
    except Exception as e:
        logger.warning(f"Could not load custom order file: {e}")
        return {}


def _load_selected_clip_paths():
    order_file = str(CONFIG.get("custom_order_file", "") or "").strip()
    if not order_file or not os.path.exists(order_file):
        return []
    try:
        with open(order_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            paths = data.get("paths", [])
        elif isinstance(data, list):
            paths = data
        else:
            paths = []
        normalized_paths = []
        for path in paths:
            if not path:
                continue
            normalized_paths.append(os.path.normcase(os.path.abspath(path)))
        return normalized_paths
    except Exception as e:
        logger.warning(f"Could not load selected clip paths: {e}")
        return []


def _load_clip_settings():
    order_file = str(CONFIG.get("custom_order_file", "") or "").strip()
    if not order_file or not os.path.exists(order_file):
        return {}
    try:
        with open(order_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        clip_settings = data.get("clip_settings", {}) if isinstance(data, dict) else {}
        normalized_settings = {}
        if isinstance(clip_settings, dict):
            for path, settings in clip_settings.items():
                if not path:
                    continue
                normalized_settings[os.path.normcase(os.path.abspath(path))] = settings if isinstance(settings, dict) else {"trim_seconds": settings}
        return normalized_settings
    except Exception as e:
        logger.warning(f"Could not load clip settings: {e}")
        return {}


def _get_clip_duration_for_path(video_path, default_duration, clip_settings=None):
    if clip_settings is None:
        clip_settings = _load_clip_settings()
    settings = clip_settings.get(os.path.normcase(os.path.abspath(video_path)), {})
    trim_seconds = settings.get("trim_seconds") if isinstance(settings, dict) else None
    try:
        requested_duration = float(trim_seconds)
        if requested_duration > 0:
            return requested_duration
    except (TypeError, ValueError):
        pass
    return default_duration


def _timeframe_seconds(value):
    lookup = {
        "1_day": 24 * 60 * 60,
        "1_week": 7 * 24 * 60 * 60,
        "2_weeks": 14 * 24 * 60 * 60,
        "1_month": 30 * 24 * 60 * 60,
        "all": None,
        "": None,
    }
    return lookup.get(str(value or "").strip().lower())


def filter_video_files_by_timeframe(video_files):
    timeframe_value = str(CONFIG.get("clip_timeframe", "1_week") or "1_week").lower()
    cutoff_seconds = _timeframe_seconds(timeframe_value)
    if cutoff_seconds is None:
        return list(video_files)
    cutoff = time.time() - cutoff_seconds
    filtered = []
    for path in video_files:
        try:
            if os.path.getmtime(path) >= cutoff:
                filtered.append(path)
        except OSError:
            continue
    return filtered


def order_smart_clips_for_output(smart_clips):
    """Order calculated, de-overlapped clips for the final compilation."""
    order_mode = str(CONFIG.get("clip_order", "newest_first") or "newest_first").lower()
    if order_mode == "oldest_first":
        return sorted(smart_clips, key=lambda clip: clip[3])
    if order_mode == "filename_az":
        return sorted(smart_clips, key=lambda clip: os.path.basename(clip[0]).lower())
    if order_mode == "filename_za":
        return sorted(smart_clips, key=lambda clip: os.path.basename(clip[0]).lower(), reverse=True)
    if order_mode == "custom":
        custom_order = _load_custom_order_map()
        if custom_order:
            return sorted(
                smart_clips,
                key=lambda clip: (
                    custom_order.get(os.path.normcase(os.path.abspath(clip[0])), 999999),
                    clip[3],
                ),
            )
    return sorted(smart_clips, key=lambda clip: clip[3], reverse=True)


def standardize_clip(input_path, output_path):
    """Standardize a video clip to consistent format"""
    target_resolution = CONFIG["output_resolution"]
    target_fps = CONFIG["output_fps"]
    
    command = f'"{FFMPEG_PATH}" -y -i "{input_path}" -vf "scale={target_resolution}:force_original_aspect_ratio=decrease,pad={target_resolution}:(ow-iw)/2:(oh-ih)/2,fps={target_fps}" -c:v libx264 -preset fast -crf 23 -c:a aac -b:a {CONFIG["audio_bitrate"]} "{output_path}"'
    
    success, stdout, stderr = run_ffmpeg_command(command)
    if not success:
        print(f"Error standardizing {input_path}: {stderr}")
    
    return success

def get_video_files(folder):
    """Get all video files from a folder"""
    video_files = []
    
    if not os.path.exists(folder):
        return video_files
    
    for ext in CONFIG["video_extensions"]:
        pattern = os.path.join(folder, f"*{ext}")
        import glob
        video_files.extend(glob.glob(pattern))

    video_files = filter_video_files_by_timeframe(video_files)

    selected_paths = _load_selected_clip_paths()
    if selected_paths:
        selected_set = set(selected_paths)
        video_files = [path for path in video_files if os.path.normcase(os.path.abspath(path)) in selected_set]
    
    order_mode = str(CONFIG.get("clip_order", "newest_first") or "newest_first").lower()
    if order_mode == "oldest_first":
        video_files.sort(key=os.path.getmtime)
    elif order_mode == "filename_az":
        video_files.sort(key=lambda path: os.path.basename(path).lower())
    elif order_mode == "filename_za":
        video_files.sort(key=lambda path: os.path.basename(path).lower(), reverse=True)
    elif order_mode == "custom":
        custom_order = _load_custom_order_map()
        if custom_order:
            video_files.sort(
                key=lambda path: (
                    custom_order.get(os.path.normcase(os.path.abspath(path)), 999999),
                    os.path.getmtime(path),
                )
            )
        else:
            video_files.sort(key=os.path.getmtime, reverse=True)
    else:
        video_files.sort(key=os.path.getmtime, reverse=True)
    return video_files

def generate_unique_filename(base_name="BMagic_Compilation", extension=".mp4"):
    """Generate a unique filename with timestamp to avoid overwriting"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name_without_ext = os.path.splitext(base_name)[0]
    return f"{name_without_ext}_{timestamp}{extension}"

STOCK_INTRO_BASENAME = "StockDefault"


def resolve_stock_intro_path():
    """Only the bundled stock intro is supported."""
    if not os.path.exists(CONFIG["intro_folder"]):
        return None
    for ext in CONFIG["intro_extensions"]:
        intro_file = os.path.join(CONFIG["intro_folder"], f"{STOCK_INTRO_BASENAME}{ext}")
        if os.path.exists(intro_file):
            return intro_file
    return None


def select_random_intro():
    """Random intro uses the stock intro file only."""
    if not CONFIG["use_intro"]:
        return None
    return resolve_stock_intro_path()

def validate_and_convert_audio(file_path, temp_dir):
    """
    Validate audio file and convert to standard MP3 if needed.
    Returns: (success, converted_path or original_path)
    """
    try:
        # Check if file exists and has content
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            logger.warning(f"Audio file missing or empty: {file_path}")
            return False, None
        
        # Try to read audio info
        command = f'"{FFPROBE_PATH}" -v quiet -print_format json -show_streams "{file_path}"'
        success, stdout, stderr = run_ffmpeg_command(command, timeout=10)
        
        if not success:
            logger.warning(f"Cannot read audio file: {os.path.basename(file_path)}")
            return False, None
            
        data = json.loads(stdout)
        audio_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
        
        if not audio_streams:
            logger.warning(f"No audio streams in file: {os.path.basename(file_path)}")
            return False, None
        
        # Check if conversion is needed (non-standard format)
        codec = audio_streams[0].get('codec_name', '')
        
        # If already MP3 with good codec, use directly
        if codec == 'mp3' and file_path.lower().endswith('.mp3'):
            return True, file_path
        
        # Convert to standard MP3 for compatibility
        logger.info(f"Converting {os.path.basename(file_path)} ({codec}) to MP3...")
        converted_path = os.path.join(temp_dir, f"converted_{os.path.basename(file_path)}.mp3")
        
        convert_cmd = f'"{FFMPEG_PATH}" -y -i "{file_path}" -acodec mp3 -ab 192k "{converted_path}"'
        success, stdout, stderr = run_ffmpeg_command(convert_cmd, timeout=30)
        
        if success and os.path.exists(converted_path):
            logger.info(f"Successfully converted to MP3: {os.path.basename(file_path)}")
            return True, converted_path
        else:
            logger.warning(f"Failed to convert audio: {os.path.basename(file_path)}")
            return False, None
            
    except Exception as e:
        logger.error(f"Audio validation error for {file_path}: {e}")
        return False, None

def create_music_playlist(temp_dir, total_duration):
    """Create a music playlist that covers the entire video duration with random tracks"""
    
    # Return None if user selected "None" for music
    if CONFIG.get("music_selection") == "None":
        return None
    
    if not os.path.exists(CONFIG["music_folder"]):
        return None
        
    # Get all available music files and validate/convert them
    music_files = []
    for ext in CONFIG["music_extensions"]:
        pattern = os.path.join(CONFIG["music_folder"], f"*{ext}")
        import glob
        found_files = glob.glob(pattern)
        # Validate and convert each music file if needed
        for music_file in found_files:
            valid, converted_path = validate_and_convert_audio(music_file, temp_dir)
            if valid:
                music_files.append(converted_path)
            else:
                safe_print(f"   [WARNING] Skipping invalid music file: {os.path.basename(music_file)}")
    
    if not music_files:
        logger.warning("No valid music files found")
        safe_print("   [WARNING] No valid music files found, video will have no background music")
        return None
    
    # If user selected specific music, prefer that as the first track
    playlist_tracks = []
    if CONFIG["music_selection"] and CONFIG["music_selection"] not in ("[RANDOM] Random", "None"):
        music_name = CONFIG["music_selection"]
        for ext in CONFIG["music_extensions"]:
            music_file = os.path.join(CONFIG["music_folder"], f"{music_name}{ext}")
            if os.path.exists(music_file):
                # Validate and convert the selected music file if needed
                valid, converted_path = validate_and_convert_audio(music_file, temp_dir)
                if valid:
                    playlist_tracks.append(converted_path)
                    logger.info(f"Using selected music as first track: {music_name}")
                else:
                    safe_print(f"   [WARNING] Selected music '{music_name}' could not be loaded, using random music instead")
                break
    
    # Calculate total duration needed
    current_duration = 0
    estimated_track_length = 120  # Assume average 2 minutes per track
    
    # Add tracks until we cover the video duration
    while current_duration < total_duration:
        if len(playlist_tracks) == 0 or len(music_files) > 1:
            # Select different tracks for variety (avoid repeating immediately)
            available_tracks = [f for f in music_files if f not in playlist_tracks[-2:]] if len(playlist_tracks) >= 2 else music_files
            if not available_tracks:
                available_tracks = music_files  # Fallback if we've used everything
            
            selected_track = random.choice(available_tracks)
            playlist_tracks.append(selected_track)
        else:
            # Only one track available, just use it
            playlist_tracks.append(music_files[0])
        
        current_duration += estimated_track_length
        
        # Safety limit - don't create playlists with more than 10 tracks
        if len(playlist_tracks) >= 10:
            break
    
    # Create FFmpeg-compatible music file for concatenation
    if len(playlist_tracks) == 1:
        # Single track - use directly
        logger.info(f"Using single music track: {os.path.basename(playlist_tracks[0])}")
        return playlist_tracks[0]
    else:
        # Multiple tracks - create concatenated music file
        temp_music_path = os.path.join(temp_dir, "music_playlist.mp3")
        
        # Create concat list file
        music_list_file = os.path.join(temp_dir, "music_list.txt")
        with open(music_list_file, 'w') as f:
            for track in playlist_tracks:
                f.write(f"file '{track}'\n")
        
        # Concatenate music tracks
        concat_cmd = (
            f'"{FFMPEG_PATH}" -y -f concat -safe 0 -i "{music_list_file}" '
            f'-acodec mp3 -ab 320k "{temp_music_path}"'
        )
        
        success, stdout, stderr = run_ffmpeg_command(concat_cmd, timeout=90)  # Give it extra time
        
        if success:
            logger.info(f"Created music playlist with {len(playlist_tracks)} tracks")
            safe_print(f"   [MUSIC] Created playlist with {len(playlist_tracks)} tracks for {total_duration:.1f}s video")
            try:
                os.remove(music_list_file)
            except:
                pass
            return temp_music_path
        else:
            logger.warning("Failed to create music playlist, using single track")
            return playlist_tracks[0]

def concatenate_videos(video_list, output_path, music_playlist=None):
    """Concatenate videos using FFmpeg with pre-normalization for reliability"""
    if not video_list:
        print("No videos to concatenate")
        return False
    
    try:
        # Parse output resolution for normalization
        width, height = map(int, CONFIG["output_resolution"].split('x'))
        
        # Step 1: Normalize all videos to identical parameters (prevents freezing)
        normalized_videos = []
        safe_print(f"[PROCESS] Step 1: Normalizing {len(video_list)} videos for compatibility...")
        
        for i, video in enumerate(video_list):
            safe_print(f"   [VIDEO] Normalizing video {i+1}/{len(video_list)}...")
            normalized_path = os.path.join(tempfile.gettempdir(), f"normalized_{i}.mp4")
            
            # Normalize each video to exact same parameters
            normalize_cmd = (
                f'"{FFMPEG_PATH}" -y -i "{video}" '
                f'-vf "scale={width}:{height}:force_original_aspect_ratio=decrease,'
                f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={CONFIG["output_fps"]}" '
                f'-af "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo" '
                f'-c:v libx264 -preset fast -b:v {CONFIG["video_bitrate"]} '
                f'-c:a aac -b:a {CONFIG["audio_bitrate"]} '
                f'"{normalized_path}"'
            )
            
            success, stdout, stderr = run_ffmpeg_command(normalize_cmd, timeout=120)  # Longer timeout for normalization
            if not success:
                safe_print(f"      [ERROR] Failed to normalize video {i+1}")
                return False
            
            normalized_videos.append(normalized_path)
        
        # Step 2: Create temporary concatenated video using concat demuxer (now safe)
        temp_video = os.path.join(tempfile.gettempdir(), "temp_concatenated.mp4")
        concat_file = os.path.join(tempfile.gettempdir(), "concat_list.txt")
        
        with open(concat_file, 'w') as f:
            for video in normalized_videos:
                f.write(f"file '{video}'\n")
        
        safe_print(f"[PROCESS] Step 2: Concatenating normalized videos...")
        concat_command = (
            f'"{FFMPEG_PATH}" -y -f concat -safe 0 -i "{concat_file}" '
            f'-c copy "{temp_video}"'
        )
        
        success, stdout, stderr = run_ffmpeg_command(concat_command, timeout=180)  # Even longer for concatenation
        if not success:
            safe_print(f"      [ERROR] Failed to concatenate videos")
            return False
        
        # Step 3: Add background music if provided
        if music_playlist:
            safe_print(f"[MUSIC] Step 3: Adding background music...")
            final_command = (
                f'"{FFMPEG_PATH}" -y -i "{temp_video}" -i "{music_playlist}" '
                f'-filter_complex "[0:a][1:a]amix=inputs=2:duration=shortest:weights=1.0 0.4[finalaudio]" '
                f'-map "0:v" -map "[finalaudio]" '
                f'-c:v copy -c:a aac -b:a {CONFIG["audio_bitrate"]} '
                f'"{output_path}"'
            )
            
            success, stdout, stderr = run_ffmpeg_command(final_command, timeout=240)  # Longest timeout for final music mixing
            if not success:
                safe_print(f"      [WARNING] Failed to add background music, creating video without music...")
                logger.warning(f"Music mixing failed: {stderr}")
                # Fallback: create video without music instead of failing completely
                try:
                    shutil.move(temp_video, output_path)
                    safe_print(f"      [OK] Video created successfully (without background music)")
                except Exception as e:
                    safe_print(f"      [ERROR] Failed to save video: {e}")
                    return False
        else:
            # No music: just copy the concatenated video to final output
            shutil.move(temp_video, output_path)
        
        # Clean up temporary files
        try:
            if os.path.exists(concat_file):
                os.remove(concat_file)
            if os.path.exists(temp_video) and temp_video != output_path:
                os.remove(temp_video)
            for norm_video in normalized_videos:
                if os.path.exists(norm_video):
                    os.remove(norm_video)
        except:
            pass
        
        safe_print(f"   [OK] Video compilation completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during concatenation: {e}")
        return False

def main():
    """Enhanced main execution function with progress tracking"""
    start_time = time.time()
    success = False  # Initialize success flag
    report_progress(2, "Starting")
    
    safe_print("\n[GAME] Starting B-Magic's Auto Vid Compiler...")
    logger.info("Starting video compilation process")
    logger.debug(
        "Runtime snapshot: ffmpeg=%s ffprobe=%s input=%s output=%s music=%s intro=%s clip_order=%s clip_timeframe=%s",
        FFMPEG_PATH,
        FFPROBE_PATH,
        CONFIG.get("video_folder", ""),
        CONFIG.get("output_folder", ""),
        CONFIG.get("music_selection", ""),
        CONFIG.get("intro_selection", ""),
        CONFIG.get("clip_order", ""),
        CONFIG.get("clip_timeframe", ""),
    )
    
    # Enhanced setup check
    if not setup_check():
        report_progress(0, "Setup incomplete")
        safe_print("\n[STOP] Setup incomplete. Please fix the issues above and run again.")
        logger.error("Setup validation failed, aborting compilation")
        if not os.environ.get('GUI_MODE'):
            input("Press Enter to exit...")
        return False
    
    # Smart resolution detection for universal compatibility
    report_progress(5, "Detecting output resolution")
    safe_print("\n[TARGET] Configuring optimal video resolution...")
    
    # Always use smart auto-detection for universal compatibility
    optimal_resolution = detect_optimal_resolution(CONFIG["video_folder"])
    safe_print(f"   Auto-detected resolution: {optimal_resolution}")
    
    CONFIG["output_resolution"] = optimal_resolution
    safe_print(f"   Final resolution: {optimal_resolution}")
    
    # Try auto-detection if still using placeholder
    if "YourUsername" in CONFIG["video_folder"]:
        safe_print("[SEARCH] Attempting to auto-detect video folders...")
        detected_path = auto_detect_paths()
        if detected_path:
            CONFIG["video_folder"] = detected_path
            safe_print(f"[OK] Auto-detected video folder: {detected_path}")
            logger.info(f"Auto-detected video path: {detected_path}")
        else:
            safe_print("[ERROR] Could not auto-detect video folder")
            logger.warning("Auto-detection failed")
    
    # Display configuration
    safe_print("\n[CONFIG] COMPILATION CONFIGURATION:")
    safe_print("-" * 50)
    safe_print(f"[VIDEO] Video source: {CONFIG['video_folder']}")
    safe_print(f"[MUSIC] Music source: {CONFIG['music_folder']}")
    unique_output_filename = generate_unique_filename(CONFIG['output_filename'])
    safe_print(f"[OUTPUT] Output file: {os.path.join(CONFIG['output_folder'], unique_output_filename)}")
    safe_print(f"[TIME] Clip duration: {CONFIG['clip_duration']} seconds")
    safe_print(f"[TARGET] Resolution: {CONFIG['output_resolution']} @ {CONFIG['output_fps']}fps")
    safe_print("-" * 50)
    
    # Create output folder
    os.makedirs(CONFIG["output_folder"], exist_ok=True)
    logger.info(f"Output directory ready: {CONFIG['output_folder']}")
    
    # Get video files with enhanced feedback
    report_progress(8, "Scanning source folder")
    safe_print("\n[SEARCH] Scanning for video files...")
    video_files = get_video_files(CONFIG["video_folder"])
    
    if not video_files:
        safe_print(f"\n[ERROR] No video files found in {CONFIG['video_folder']}")
        safe_print(f"[SUMMARY] Supported video formats: {', '.join(CONFIG['video_extensions'])}")
        safe_print("[TIP] Make sure your recordings are in the correct folder!")
        logger.error(f"No video files found in {CONFIG['video_folder']}")
        if not os.environ.get('GUI_MODE'):
            input("Press Enter to exit...")
        return False
    
    safe_print(f"[OK] Found {len(video_files)} video files")
    logger.info(f"Found {len(video_files)} video files for processing")
    
    # Show most recent files
    if len(video_files) > 0:
        safe_print(f"\n[FOLDER] Video files in output order ({CONFIG.get('clip_order', 'newest_first')}):")
        for i, video_file in enumerate(video_files[:5]):
            file_size = os.path.getsize(video_file) / (1024*1024)  # MB
            mod_time = datetime.fromtimestamp(os.path.getmtime(video_file))
            print(f"   {i+1}. {os.path.basename(video_file)} ({file_size:.1f}MB, {mod_time.strftime('%m/%d %H:%M')})")
    
    try:
        safe_print(f"\n[START] Starting compilation process...")
        result = create_compilation_video(video_files)
        
        if result:  # result is now the output path or False
            end_time = time.time()
            duration = end_time - start_time
            safe_print(f"\n[CELEBRATE] Video compilation completed successfully!")
            safe_print(f"[TIME] Total time: {duration:.1f} seconds")
            safe_print(f"[FOLDER] Output saved to: {result}")  # result contains the full output path
            report_progress(100, "Compilation complete")
            logger.info(f"Compilation completed successfully in {duration:.1f} seconds")
            
            # Open output folder
            try:
                import webbrowser
                webbrowser.open(CONFIG["output_folder"])
                safe_print("[FOLDER] Output folder opened")
            except:
                safe_print(f"[FOLDER] You can find your video in: {CONFIG['output_folder']}")
            
            return True
        else:
            safe_print("\n[ERROR] Video compilation failed!")
            logger.error("Video compilation process failed")
            return False
            
    except KeyboardInterrupt:
        safe_print("\n\n[STOP] Compilation cancelled by user")
        logger.info("Compilation cancelled by user interrupt")
        return False
    except Exception as e:
        safe_print(f"\n[CRASH] Unexpected error during compilation: {e}")
        logger.error(f"Unexpected error during compilation: {e}")
        return False
    finally:
        print("\n" + "="*60)
        if not os.environ.get('GUI_MODE'):
            input("Press Enter to exit...")


# Helper Functions will be defined below with the main compilation function


def select_random_music():
    """Select music file - either user selection from GUI or random"""
    if not os.path.exists(CONFIG["music_folder"]):
        return None
    
    # Check if user selected specific music from GUI
    if CONFIG["music_selection"]:
        # Look for the selected music file (without extension in the name)
        music_name = CONFIG["music_selection"]
        for ext in CONFIG["music_extensions"]:
            music_file = os.path.join(CONFIG["music_folder"], f"{music_name}{ext}")
            if os.path.exists(music_file):
                logger.info(f"Using selected music: {music_name}")
                return music_file
    
    # Fall back to random selection if no specific choice or file not found
    music_files = []
    for ext in CONFIG["music_extensions"]:
        pattern = os.path.join(CONFIG["music_folder"], f"*{ext}")
        import glob
        music_files.extend(glob.glob(pattern))
    
    if music_files:
        selected = random.choice(music_files)
        logger.info(f"Using random music: {os.path.basename(selected)}")
        return selected
    return None


def select_intro_video():
    """Select intro video: None, stock file only, or random (stock file only)."""
    selection = CONFIG.get("intro_selection", "")

    if selection == "None":
        logger.info("Intro disabled (None selected)")
        return None

    stock_path = resolve_stock_intro_path()
    if not stock_path:
        logger.warning("Stock intro file not found in intro folder")
        return None

    if selection in (STOCK_INTRO_BASENAME, "[RANDOM] Random"):
        label = "stock" if selection == STOCK_INTRO_BASENAME else "random (stock)"
        logger.info(f"Using {label} intro: {os.path.basename(stock_path)}")
        return stock_path

    logger.warning(f"Unknown intro selection '{selection}', using stock intro")
    return stock_path


def cleanup_temp_files(temp_files):
    """Clean up temporary video files"""
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                logger.info(f"Removed temporary file: {temp_file}")
        except Exception as e:
            logger.warning(f"Could not remove temporary file {temp_file}: {e}")


def create_compilation_video(video_files):
    """Enhanced video compilation with smart overlap detection and progress tracking"""
    
    safe_print(f"[VIDEO] Processing {len(video_files)} video files with smart overlap detection...")
    logger.info(f"Starting smart compilation of {len(video_files)} videos")
    report_progress(10, "Analyzing clips")
    
    # Step 1: Calculate smart clips to avoid overlapping content
    safe_print("\n[SMART] Step 1: Analyzing video timestamps and calculating smart clips...")
    smart_clips = calculate_smart_clips(video_files, CONFIG["clip_duration"])
    
    if not smart_clips:
        safe_print("\n[ERROR] No valid clips could be calculated!")
        logger.error("Smart clip calculation failed - no clips generated")
        return False
    
    safe_print(f"\n[STATS] Smart analysis complete: {len(smart_clips)} clips from {len(video_files)} videos")
    logger.info(f"Smart clips calculated: {len(smart_clips)} clips with overlap prevention")
    
    # Step 2: Extract smart clips
    safe_print("\n[EXTRACT] Step 2: Extracting non-overlapping clips...")
    processed_videos = []
    total_actual_duration = 0
    
    for i, (video_file, start_time, extract_duration, creation_timestamp) in enumerate(smart_clips):
        if cancellation_requested():
            safe_print("\n[STOP] Compilation cancelled by user")
            return False
        report_progress(15 + (50 * (i / max(1, len(smart_clips)))), f"Extracting clip {i+1}/{len(smart_clips)}")
        # Check file size to avoid processing extremely large files
        file_size_mb = os.path.getsize(video_file) / (1024 * 1024)
        safe_print(f"   [{i+1}/{len(smart_clips)}] Smart clip: {os.path.basename(video_file)} ({file_size_mb:.1f}MB)")
        safe_print(f"      [TIME] Extract: {start_time:.2f}s -> {start_time + extract_duration:.2f}s ({extract_duration:.2f}s)")
        logger.info(f"Processing smart clip {i+1}/{len(smart_clips)}: {video_file}")
        
        # Skip extremely large files (over 500MB) to prevent hanging
        if file_size_mb > 500:
            safe_print(f"      [WARNING] Skipping large file ({file_size_mb:.1f}MB) - may cause processing issues")
            logger.warning(f"Skipped large file: {video_file} ({file_size_mb:.1f}MB)")
            continue
        
        try:
            # Create temporary clip from this video using smart parameters
            temp_clip_path = os.path.join(tempfile.gettempdir(), f"smart_clip_{i}_{os.path.basename(video_file)}")
            
            # Use smart extraction with precise timing
            if extract_smart_clip(video_file, temp_clip_path, start_time, extract_duration):
                processed_videos.append(temp_clip_path)
                total_actual_duration += extract_duration
                safe_print(f"      [OK] Smart clip extracted successfully ({extract_duration:.2f}s)")
            else:
                safe_print(f"      [WARNING] Failed to extract smart clip")
                logger.warning(f"Failed to extract smart clip from {video_file}")
        except Exception as e:
            safe_print(f"      [ERROR] Error processing video: {e}")
            logger.error(f"Error processing {video_file}: {e}")
            continue
    
    if not processed_videos:
        safe_print("\n[ERROR] No video clips were successfully processed!")
        logger.error("No clips extracted from any videos")
        return False
    
    report_progress(68, "Building music playlist")
    safe_print(f"\n[OK] Successfully processed {len(processed_videos)} smart clips")
    safe_print(f"[STATS] Total compilation duration: {total_actual_duration:.1f}s (avg: {total_actual_duration/len(processed_videos):.1f}s per clip)")
    
    # Calculate total video duration for smart music playlist
    total_video_duration = total_actual_duration
    if CONFIG["use_intro"]:
        total_video_duration += CONFIG["intro_duration"]
    
    # Step 2: Create music playlist
    safe_print("\n[MUSIC] Step 2: Creating background music playlist...")
    temp_dir = tempfile.gettempdir()
    # Skip music if user selected "None"
    if CONFIG.get("music_selection") == "None":
        music_playlist = None
        safe_print("   [MUSIC] Music disabled (None selected)")
    else:
        music_playlist = create_music_playlist(temp_dir, total_video_duration)
    if music_playlist:
        if os.path.basename(music_playlist).startswith("music_playlist"):
            safe_print(f"   [MUSIC] Created smart playlist for {total_video_duration:.1f}s video")
        else:
            safe_print(f"   [MUSIC] Selected: {os.path.basename(music_playlist)}")
        logger.info(f"Selected background music: {music_playlist}")
    else:
        safe_print("   [WARNING] No background music available")
        logger.warning("No background music found")
        music_playlist = None
    
    # Step 3: Select intro (if enabled) 
    intro_clip_path = None
    if CONFIG["use_intro"]:
        report_progress(76, "Processing intro")
        safe_print("\n[VIDEO] Step 3: Selecting intro video...")
        intro_file = select_intro_video()
        if intro_file:
            safe_print(f"   [INTRO] Selected: {os.path.basename(intro_file)}")
            logger.info(f"Selected intro video: {intro_file}")
            
            # Process intro video (extract and standardize like main videos)
            intro_clip_path = os.path.join(tempfile.gettempdir(), f"intro_{os.path.basename(intro_file)}")
            
            try:
                if extract_intro_clip(intro_file, intro_clip_path, CONFIG["intro_duration"]):
                    safe_print(f"      [OK] Intro processed successfully")
                else:
                    safe_print(f"      [WARNING] Failed to process intro")
                    intro_clip_path = None
            except Exception as e:
                safe_print(f"      [ERROR] Error processing intro: {e}")
                intro_clip_path = None
        else:
            safe_print("   [WARNING] No intro videos available")
            logger.warning("No intro videos found")
    else:
        safe_print("\n[SKIP] Step 3 SKIPPED: Intro videos disabled in configuration")
    
    # Step 4: Combine intro + main clips (S+ style: intro FIRST)
    if intro_clip_path and os.path.exists(intro_clip_path):
        processed_videos = [intro_clip_path] + processed_videos  # Intro FIRST like S+VideoCompiler.py
        safe_print(f"   [VIDEO] Added intro to start of compilation")
    
    # Step 5: Final compilation
    report_progress(86, "Creating final compilation")
    safe_print(f"\n[TOOLS] Step 5: Creating final compilation...")
    unique_filename = generate_unique_filename(CONFIG["output_filename"])
    output_path = os.path.join(CONFIG["output_folder"], unique_filename)
    
    try:
        # Use the existing concatenate_videos function (it takes 3 parameters)
        success = concatenate_videos(processed_videos, output_path, music_playlist)
        
        if success and os.path.exists(output_path):
            # Show final file info
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            safe_print("   [OK] Final video created successfully!")
            safe_print(f"   [FILE] {os.path.basename(output_path)}")
            safe_print(f"   [SIZE] {size_mb:.1f} MB")
            logger.info(f"Compilation successful: {output_path} ({size_mb:.1f}MB)")
            report_progress(100, "Compilation complete")
            
            return output_path  # Return the actual output path on success
        else:
            safe_print("   [ERROR] Failed to create final compilation")
            logger.error("Final concatenation failed")
            return False
            
    except Exception as e:
        safe_print(f"   [ERROR] Error during final compilation: {e}")
        logger.error(f"Error during concatenation: {e}")
        return False
    finally:
        # Cleanup temporary files
        safe_print("\n[CLEANUP] Cleaning up temporary files...")
        cleanup_temp_files(processed_videos)
        logger.info("Temporary files cleaned up")
    
if __name__ == "__main__":
    import sys
    try:
        success = main()
    except Exception:
        logger.exception("Unhandled fatal compiler exception")
        safe_print("[ERROR] Unhandled fatal error. Check the logs folder for details.")
        success = False
    sys.exit(0 if success else 1)
