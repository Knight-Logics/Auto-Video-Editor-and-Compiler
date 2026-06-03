#!/usr/bin/env python3
"""
UO Video Compiler - GUI Control Panel
Professional Windows application for UO video compilation
"""

import sys
import os

# Add local python libraries to path (for portable distribution)
script_dir = os.path.dirname(os.path.abspath(__file__))
python_libs_dir = os.path.join(script_dir, "python-libs")
if os.path.exists(python_libs_dir):
    sys.path.insert(0, python_libs_dir)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import subprocess
import sys
import webbrowser
import urllib.parse
import logging
import platform
import traceback
from types import ModuleType
from datetime import datetime
from PIL import Image, ImageTk
import threading
import urllib.request
import tempfile
import shutil
import time
import hashlib
try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Import compilation functions directly to avoid subprocess
try:
    import UOVidCompiler
    DIRECT_COMPILATION = True
except ImportError:
    DIRECT_COMPILATION = False

try:
    import autovid_license
except ImportError:
    autovid_license = None

try:
    import intro_creator
    INTRO_CREATOR_AVAILABLE = True
except ImportError:
    intro_creator = None
    INTRO_CREATOR_AVAILABLE = False


def get_autovid_license() -> ModuleType:
    if autovid_license is None:
        raise RuntimeError("License module is unavailable")
    return autovid_license


def get_app_storage_dir():
    if getattr(sys, 'frozen', False):
        root = os.environ.get("APPDATA") or os.environ.get("PROGRAMDATA") or os.path.expanduser("~")
        path = os.path.join(root, "KnightLogics", "AutoVidCompiler")
    else:
        path = os.path.dirname(__file__)
    os.makedirs(path, exist_ok=True)
    return path


def get_app_logs_dir():
    path = os.path.join(get_app_storage_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def write_bootstrap_log(prefix, message):
    log_path = os.path.join(get_app_logs_dir(), f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(message)
        if not message.endswith("\n"):
            handle.write("\n")
    return log_path


class CompilerGuiLogHandler(logging.Handler):
    def __init__(self, gui):
        super().__init__(level=logging.DEBUG)
        self.gui = gui

    def emit(self, record):
        try:
            message = self.format(record) if self.formatter else record.getMessage()
            tag = "error" if record.levelno >= logging.ERROR else "warning" if record.levelno >= logging.WARNING else "info"
            self.gui.log_status(f"[COMPILER] {message}", tag=tag)
        except Exception:
            pass

class UOVidCompilerGUI:
    # Version info for auto-updates
    VERSION = "1.3.7"  # Update this when releasing new versions
    RELEASE_EXE_NAME = "Auto_Video_Compiler.exe"
    GITHUB_REPO = "Knight-Logics/Auto-Video-Editor-and-Compiler"  # GitHub repo for auto-updates
    UPDATE_USER_AGENT = "AutoVideoCompiler-Updater"
    MIN_UPDATE_BYTES = 40 * 1024 * 1024  # reject HTML/error pages masquerading as .exe
    GITHUB_API_HEADERS = {
        "User-Agent": UPDATE_USER_AGENT,
        "Accept": "application/vnd.github+json",
    }
    VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v')
    INTRO_EXTENSIONS = VIDEO_EXTENSIONS + ('.gif',)
    STOCK_INTRO_BASENAME = 'StockDefault'
    INTRO_OPTION_STOCK = 'Stock'
    DEPRECATED_INTRO_BASENAMES = frozenset({'Why Knight Logics'})
    MUSIC_EXTENSIONS = ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac')
    CLIP_ORDER_OPTIONS = ('newest_first', 'oldest_first', 'filename_az', 'filename_za', 'custom')
    CLIP_TIMEFRAME_OPTIONS = (
        ('1 day', '1_day'),
        ('1 week', '1_week'),
        ('2 weeks', '2_weeks'),
        ('Month', '1_month'),
        ('All', 'all'),
    )
    
    # Donation addresses
    DONATION_INFO = {
        'venmo': '@nicholas-knight-5',
        'paypal': 'nicholas.jknight@yahoo.com',
        'btc': 'bc1qqcvg6ymyq9c8k323gcktt2acxlwdjjhujc04fk',
        'eth': '0x2FF5DFcfcaCc2D5f3A119F16293833A47b7DA697',
        'sol': 'FUe52dUQEtRuYvjo8LhvFjHsGdNAUXvvLiqW9yNshHA6'
    }
    
    def __init__(self):
        self.root = tk.Tk()
        
        # Initialize critical variables first
        self.bundle_dir = self.get_bundle_dir()
        self.storage_dir = self.get_storage_dir()
        self.gui_logger, self.gui_log_path = self.setup_diagnostics_logging()
        self.config_file = os.path.join(self.storage_dir, "gui_config.json")
        self.install_exception_logging()
        self.config = self.load_config()
        self.log_startup_context()
        
        # Initialize logo state variables
        self.has_logo = False
        self.has_logo_tk = False
        
        # Initialize path variables
        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        
        # Dictionary to store button image references (prevents garbage collection)
        self.button_images = {}
        
        # File monitoring state (check every 5 seconds for changes)
        self.last_music_files = set()
        self.last_intro_files = set()
        self.monitoring_active = False
        self.checkout_session_id = ""
        self.checkout_window = None
        self.license_recovery_window = None
        self.license_status_var = tk.StringVar(value="License status loading...")
        self.config_summary_var = tk.StringVar(value="")
        self.custom_order_file = os.path.join(self.storage_dir, "custom_clip_order.json")
        self.preview_process = None
        self.stop_requested = False
        self._shutdown_in_progress = False
        self._create_intro_window = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text_var = tk.StringVar(value="Idle")
        self.status_text = None
        self.config_summary_label = None
        self.clip_selection_files = []
        self.clip_selection_summary_var = tk.StringVar(value="Select an input folder to load clips.")
        self.clip_trim_overrides = {}
        self.clip_selection_canvas = None
        self.clip_selected_index = 0
        self.clip_drag_index = None
        self.clip_drag_changed = False
        self.clip_row_height = 168
        self.clip_cards_per_row = 2
        self.clip_card_regions = []
        self.clip_thumbnail_cache = {}
        self.clip_trim_inputs = {}
        self.clip_preview_window = None
        self.clip_preview_thumb = None
        self._update_prompt_shown = False
        self._update_download_active = False
        self._update_progress_window = None
        self._update_progress_var = None
        self._update_progress_label = None
        self.updater_batch_path = None
        
        # Set icon IMMEDIATELY for taskbar
        self.set_taskbar_icon()
        
        # Load PNG logo for GUI use BEFORE creating widgets
        self.load_png_logo()

        self.seed_media_folders()
        
        # Load payment method logos
        self.load_payment_logos()
        
        # Load button icons
        self.load_button_icons()
        
        self.root.title("Auto Video Editor & Compiler - Control Panel")
        self.root.geometry("1280x960")
        self.root.minsize(1100, 820)
        self.root.resizable(True, True)
        
        # Set application icon (additional setup)
        self.setup_icon()
        
        # Setup GUI AFTER logo is loaded
        self.setup_styles()
        self.create_widgets()
        self.load_saved_paths()
        self.log_status(f"[LOG] GUI diagnostics log: {self.gui_log_path}")
        # Defer until after the status widget is fully initialized (avoids cp1252 console print crashes).
        self.root.after(0, self._publish_gui_process_identity)
        
        # Start folder monitoring (checks every 5 seconds)
        self.start_folder_monitoring()
        
        # Center window
        self.center_window()
        
        # Check for updates on startup (in background thread)
        threading.Thread(target=self.check_for_updates, daemon=True).start()
        threading.Thread(target=self.refresh_license_status, daemon=True).start()

    def get_bundle_dir(self):
        """Return the bundled resource directory."""
        return getattr(sys, '_MEIPASS', os.path.dirname(__file__))

    def get_storage_dir(self):
        """Return persistent writable app storage."""
        return get_app_storage_dir()

    def get_logs_dir(self):
        path = os.path.join(self.storage_dir, "logs")
        os.makedirs(path, exist_ok=True)
        return path

    def setup_diagnostics_logging(self):
        log_path = os.path.join(self.get_logs_dir(), f"autovid_gui_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        gui_logger = logging.getLogger("KnightLogics.AutoVidCompiler.GUI")
        gui_logger.setLevel(logging.DEBUG)
        gui_logger.propagate = False

        for handler in list(gui_logger.handlers):
            gui_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        gui_logger.addHandler(file_handler)
        gui_logger.info("GUI diagnostics logger initialized")
        return gui_logger, log_path

    def write_diagnostic(self, message, level=logging.INFO, exc_info=None):
        if not hasattr(self, 'gui_logger') or self.gui_logger is None:
            return
        try:
            self.gui_logger.log(level, str(message), exc_info=exc_info)
        except Exception:
            pass

    def log_startup_context(self):
        self.write_diagnostic(
            "Startup context: "
            f"version={self.VERSION} "
            f"platform={platform.platform()} "
            f"python={sys.executable} "
            f"cwd={os.getcwd()} "
            f"frozen={getattr(sys, 'frozen', False)} "
            f"bundle_dir={self.bundle_dir} "
            f"storage_dir={self.storage_dir} "
            f"config_file={self.config_file}"
        )
        self.write_diagnostic(
            "Feature availability: "
            f"direct_compilation={DIRECT_COMPILATION} "
            f"qr_available={QR_AVAILABLE} "
            f"license_module={autovid_license is not None} "
            f"ffmpeg={self.get_ffmpeg_path() or 'missing'} "
            f"ffplay={self.get_ffplay_path() or 'missing'}"
        )

    def install_exception_logging(self):
        self.root.report_callback_exception = self.handle_tk_callback_exception
        sys.excepthook = self.handle_unhandled_exception
        if hasattr(threading, 'excepthook'):
            threading.excepthook = self.handle_thread_exception

    def handle_tk_callback_exception(self, exc_type, exc_value, exc_traceback):
        self.write_diagnostic("Unhandled Tk callback exception", level=logging.ERROR, exc_info=(exc_type, exc_value, exc_traceback))
        try:
            self.log_error("Unexpected UI error. Check the logs folder for details.")
        except Exception:
            pass

    def handle_unhandled_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        self.write_diagnostic("Unhandled application exception", level=logging.ERROR, exc_info=(exc_type, exc_value, exc_traceback))

    def handle_thread_exception(self, args):
        self.write_diagnostic(
            f"Unhandled thread exception in {getattr(args.thread, 'name', 'unknown-thread')}",
            level=logging.ERROR,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        try:
            self.root.after(0, lambda: self.log_error("Background thread error. Check the logs folder for details."))
        except Exception:
            pass

    def get_music_dir(self):
        return os.path.join(self.storage_dir, "Music")

    def get_intro_dir(self):
        return os.path.join(self.storage_dir, "Intros")

    def get_sound_effects_dir(self):
        for base in (self.bundle_dir, os.path.dirname(os.path.abspath(__file__))):
            path = os.path.join(base, "Sound Effects")
            if os.path.isdir(path):
                return path
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "Sound Effects")

    def get_intro_creator_search_roots(self):
        return [self.bundle_dir, os.path.dirname(os.path.abspath(__file__))]

    def get_gui_pid_file(self):
        return os.path.join(self.storage_dir, "gui.pid")

    def _publish_gui_process_identity(self):
        """Write PID so Task Manager / scripts can identify this GUI among other Python apps."""
        pid = os.getpid()
        pid_path = self.get_gui_pid_file()
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            with open(pid_path, "w", encoding="utf-8") as handle:
                handle.write(f"{pid}\n{os.path.abspath(__file__)}\n")
        except OSError:
            pass

        if os.name == "nt":
            try:
                import ctypes

                ctypes.windll.kernel32.SetConsoleTitleW(f"Auto Video Compiler GUI (PID {pid})")
            except Exception:
                pass

        self.log_status(
            f"[APP] GUI process ID {pid}. In Task Manager use Details > Command line "
            f"contains UOVidCompiler_GUI.py (not other Python programs)."
        )

    def _remove_gui_pid_file(self):
        try:
            if os.path.isfile(self.get_gui_pid_file()):
                os.remove(self.get_gui_pid_file())
        except OSError:
            pass

    def get_thumbnail_dir(self):
        path = os.path.join(self.storage_dir, "thumbnail-cache")
        os.makedirs(path, exist_ok=True)
        return path

    def get_icon_path(self):
        return os.path.join(self.bundle_dir, "icons", "AutoVideoCompiler_icon.ico")

    def get_ffmpeg_path(self):
        candidates = [
            os.path.join(self.bundle_dir, "ffmpeg", "ffmpeg.exe"),
            shutil.which("ffmpeg"),
        ]
        return next((path for path in candidates if path and os.path.exists(path)), "")

    def get_ffplay_path(self):
        candidates = [
            os.path.join(self.bundle_dir, "ffmpeg", "ffplay.exe"),
            shutil.which("ffplay"),
        ]
        return next((path for path in candidates if path and os.path.exists(path)), "")

    def remove_deprecated_intro_files(self):
        """Remove legacy bundled intros that should not ship with the app."""
        intro_dir = self.get_intro_dir()
        if not os.path.isdir(intro_dir):
            return
        for name in os.listdir(intro_dir):
            if not name.lower().endswith(self.INTRO_EXTENSIONS):
                continue
            stem = os.path.splitext(name)[0]
            if stem not in self.DEPRECATED_INTRO_BASENAMES:
                continue
            path = os.path.join(intro_dir, name)
            try:
                os.remove(path)
                print(f"Removed deprecated intro: {name}")
            except OSError as e:
                print(f"Could not remove deprecated intro {name}: {e}")

    def seed_media_folders(self):
        """Copy bundled starter media into persistent folders without overwriting user files."""
        self.remove_deprecated_intro_files()
        for folder_name, extensions in (("Music", self.MUSIC_EXTENSIONS), ("Intros", self.INTRO_EXTENSIONS)):
            target_dir = os.path.join(self.storage_dir, folder_name)
            source_dir = os.path.join(self.bundle_dir, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            if not os.path.isdir(source_dir) or os.path.abspath(source_dir) == os.path.abspath(target_dir):
                continue
            for name in os.listdir(source_dir):
                if not name.lower().endswith(extensions):
                    continue
                if folder_name == "Intros":
                    stem = os.path.splitext(name)[0]
                    if stem != self.STOCK_INTRO_BASENAME or stem in self.DEPRECATED_INTRO_BASENAMES:
                        continue
                src = os.path.join(source_dir, name)
                dst = os.path.join(target_dir, name)
                if os.path.isfile(src) and not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                    except Exception as e:
                        print(f"Could not seed media file {name}: {e}")
        
    def set_taskbar_icon(self):
        """Set taskbar icon immediately upon window creation - CRITICAL for Windows taskbar display"""
        try:
            ico_path = self.get_icon_path()
            if os.path.exists(ico_path):
                # IMMEDIATE icon setting before window appears
                self.root.iconbitmap(ico_path)
                
                # Try Windows API approach for better taskbar integration
                try:
                    import ctypes
                    # Set the application model ID to distinguish from Python
                    app_id = 'KnightLogics.AutoVidCompiler.GUI.1.3'
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
                    print(f"Set Windows App ID: {app_id}")
                except Exception as e:
                    print(f"Windows App ID setting failed: {e}")
                
                # Multiple icon setting approaches
                try:
                    self.root.wm_iconbitmap(ico_path)
                    self.root.iconbitmap(default=ico_path)
                    
                    # Force immediate update
                    self.root.update_idletasks()
                    
                    print(f"AGGRESSIVE TASKBAR ICON SET: {ico_path}")
                except Exception as e:
                    print(f"Aggressive icon setting failed: {e}")
                
                print(f"TASKBAR ICON SET IMMEDIATELY: {ico_path}")
            else:
                print(f"ERROR: ICO file not found for taskbar: {ico_path}")
        except Exception as e:
            print(f"CRITICAL ERROR setting taskbar icon: {e}")
        
        # Initialize video configuration variables (moved from set_taskbar_icon)
        self.trim_seconds_var = tk.StringVar()
        self.music_selection_var = tk.StringVar()
        self.intro_selection_var = tk.StringVar()
        self.clip_order_var = tk.StringVar(value="newest_first")
        self.clip_timeframe_var = tk.StringVar(value="1_week")
        # Removed resolution_var - using auto-detection always

    def load_png_logo(self):
        """Load PNG logo for GUI display - called early in initialization"""
        try:
            logo_path = os.path.join(self.bundle_dir, "icons", "AutoVideoCompiler_header_ui.png")
            
            if os.path.exists(logo_path):
                logo_image = Image.open(logo_path)
                self.logo_large = logo_image.copy()
                self.logo_large_tk = ImageTk.PhotoImage(self.logo_large)
                
                # Create small version for any internal use
                self.icon_small = logo_image.resize((48, 48), Image.Resampling.LANCZOS)
                self.icon_tk = ImageTk.PhotoImage(self.icon_small)
                
                # Set flags for successful logo loading
                self.has_logo = True
                self.has_logo_tk = True
                
                print(f"[OK] PNG logo loaded EARLY for GUI use: {logo_path}")
                print(f"[OK] Logo image objects created successfully")
                print(f"[OK] Logo flags set: has_logo={self.has_logo}, has_logo_tk={self.has_logo_tk}")
            else:
                print(f"[ERROR] PNG logo file not found: {logo_path}")
                self.has_logo = False
                self.has_logo_tk = False
                
        except Exception as e:
            print(f"[ERROR] Could not load PNG logo: {e}")
            self.has_logo = False
            self.has_logo_tk = False
    
    def load_payment_logos(self):
        """Load payment method logos for donation buttons"""
        print("[BANK] Loading payment method logos...")
        
        self.payment_logos = {}
        payment_methods = ['venmo', 'paypal', 'bitcoin', 'ethereum', 'solana']
        
        for payment in payment_methods:
            try:
                # Try to load button icon (24x24) for buttons
                button_icon_path = os.path.join(self.bundle_dir, "icons", f"{payment}_button_icon.png")
                
                if os.path.exists(button_icon_path):
                    img = Image.open(button_icon_path)
                    # Convert to RGBA if needed
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    # Create PhotoImage for tkinter
                    self.payment_logos[payment] = ImageTk.PhotoImage(img)
                    print(f"[OK] Loaded {payment} payment logo: {button_icon_path}")
                else:
                    print(f"[WARN] Payment logo not found: {button_icon_path}")
                    
            except Exception as e:
                print(f"[ERROR] Failed to load {payment} payment logo: {e}")
        
        print(f"[TARGET] Payment logos loaded: {len(self.payment_logos)}/5")
        
    def setup_icon(self):
        """Setup application icon from ICO file for proper Windows taskbar integration"""
        try:
            # Only handle ICO file for taskbar (PNG already loaded separately)
            ico_path = self.get_icon_path()
            
            # Set ICO file for taskbar (primary method for Windows)
            if os.path.exists(ico_path):
                # Force refresh taskbar icon
                self.root.iconbitmap(ico_path)
                self.root.iconbitmap(default=ico_path)
                print(f"ICO taskbar icon set successfully: {ico_path}")
                
                # Method 2: Also try wm_iconbitmap for better Windows compatibility
                try:
                    self.root.wm_iconbitmap(ico_path)
                    print("wm_iconbitmap also set for enhanced compatibility")
                except Exception as e:
                    print(f"wm_iconbitmap failed: {e}")
                    
                # Force Windows to update the taskbar
                try:
                    self.root.update_idletasks()
                    self.root.focus_force()
                    print("Forced Windows taskbar refresh")
                except Exception as e:
                    print(f"Taskbar refresh failed: {e}")
                    
            else:
                print(f"ICO file not found: {ico_path}")
                
        except Exception as e:
            print(f"Could not load ICO icon: {e}")
            # Fallback: try to set a basic icon
            try:
                self.root.iconbitmap(default=True)
            except:
                pass
    
    def setup_styles(self):
        """Setup modern styling with UO theme colors"""
        style = ttk.Style()
        
        # Configure colors and themes
        self.colors = {
            'bg': '#2a2a2a',           # Dark header background (darker than charcoal)
            'fg': '#2d3b2d',           # Dark green text
            'accent': '#2E8B57',       # Sea green (UO colors)
            'button': '#228B22',       # Forest green
            'error': '#DC143C',        # Crimson red
            'warning': '#DAA520',      # Goldenrod
            'success': '#32CD32',      # Lime green
            'frame_bg': '#404040',     # Charcoal background for main sections
            'entry_bg': '#ffffff',     # White entry background
            'text_bg': '#1e1e1e',      # Dark text area background
            'text_fg': '#00FF00',      # Bright green text for text areas
            'title_color': '#2E8B57',  # UO green for titles
            'label_color': '#ffffff'   # White labels on charcoal background
        }
        
        # Configure root window with charcoal background
        self.root.configure(bg=self.colors['frame_bg'])
        
        # Configure ttk styles
        style.theme_use('clam')  # Use clam theme for better customization
        
        style.configure('Title.TLabel', 
                       background=self.colors['bg'], 
                       foreground=self.colors['title_color'],
                       font=('Segoe UI', 18, 'bold'))
        
        style.configure('Heading.TLabel',
                       background=self.colors['bg'],
                       foreground='#ffffff',  # White text for subtitle on dark header
                       font=('Segoe UI', 12, 'bold'))
        
        style.configure('Info.TLabel',
                       background=self.colors['frame_bg'],
                       foreground=self.colors['label_color'],
                       font=('Segoe UI', 10))
                       
        style.configure('Custom.TFrame',
                       background=self.colors['frame_bg'],
                       relief='flat')
        
        # Light frame for header area
        style.configure('Header.TFrame',
                       background=self.colors['bg'],
                       relief='flat')
                       
        # Configure LabelFrame with charcoal backgrounds
        style.configure('TLabelFrame',
                       background=self.colors['frame_bg'],
                       foreground=self.colors['title_color'],
                       borderwidth=2,
                       relief='groove')
                       
        style.configure('TLabelFrame.Label',
                       background=self.colors['frame_bg'],
                       foreground=self.colors['title_color'],
                       font=('Segoe UI', 11, 'bold'))
                       
        style.configure('Custom.TEntry',
                       fieldbackground=self.colors['entry_bg'],
                       foreground=self.colors['fg'],
                       borderwidth=1,
                       relief='solid')
                       
        style.configure('Custom.TButton',
                       background=self.colors['button'],
                       foreground='white',
                       borderwidth=1,
                       focuscolor='none')
        
        # Configure Combobox styling
        style.configure('TCombobox',
                       fieldbackground=self.colors['entry_bg'],
                       foreground=self.colors['fg'],
                       borderwidth=1)

        # High-contrast yellow progress bar (default clam grey is hard to see on charcoal UI)
        style.configure(
            'Yellow.Horizontal.TProgressbar',
            troughcolor='#2a2a2a',
            background='#F5C518',
            bordercolor='#404040',
            lightcolor='#FFE566',
            darkcolor='#C9A000',
        )
        
    def create_widgets(self):
        """Create and arrange GUI widgets"""
        
        # Main container with padding and styling
        main_frame = ttk.Frame(self.root, style='Custom.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header with logo and title
        self.create_header(main_frame)
        
        # Configuration section
        self.create_config_section(main_frame)
        
        # Action buttons
        self.create_action_section(main_frame)
        
    def create_header(self, parent):
        """Create professional header with logo, title, and support section"""
        # Main header frame with fixed height
        header_frame = ttk.Frame(parent, style='Header.TFrame')
        header_frame.pack(fill='x', pady=(0, 10), padx=6)
        
        # Configure header frame to maintain consistent height
        header_frame.pack_propagate(False)
        header_frame.configure(height=118)
        
        # Left side: Logo container (centered vertically)
        logo_frame = ttk.Frame(header_frame, style='Header.TFrame')
        logo_frame.pack(side='left', padx=(0, 14), anchor='center')
        
        # Logo (if available) - with error handling
        logo_displayed = False
        if hasattr(self, 'has_logo_tk') and self.has_logo_tk and hasattr(self, 'logo_large_tk'):
            try:
                logo_label = ttk.Label(logo_frame, image=self.logo_large_tk, background=self.colors['bg'])
                logo_label.pack(anchor='center')
                logo_displayed = True
                print("[OK] Header logo displayed successfully from PNG file")
            except Exception as e:
                print(f"[WARN] Error displaying header logo: {e}")
        
        if not logo_displayed:
            # Fallback: Create text logo if image fails
            fallback_logo = ttk.Label(logo_frame, text="VIDEO", font=('Arial', 32), 
                                    background=self.colors['bg'], foreground=self.colors['accent'])
            fallback_logo.pack()
            print("[PACKAGE] Using fallback text logo")

        ttk.Label(
            logo_frame,
            text="Professional video compilation tool v" + str(self.VERSION),
            style='Heading.TLabel',
            font=('Segoe UI', 9)
        ).pack(anchor='center', pady=(2, 0))

        # Center: quick tips (no demo video until one is published)
        title_frame = ttk.Frame(header_frame, style='Header.TFrame')
        title_frame.pack(side='left', fill='both', expand=True, padx=(0, 12))

        title_inner = ttk.Frame(title_frame, style='Header.TFrame')
        title_inner.pack(anchor='center', expand=True)

        quick_tips = (
            "Quick tips\n"
            "• Double-click a clip thumbnail to preview\n"
            "• Bottom-right on each card: seconds from the end of that clip\n"
            "• Drag thumbnails to reorder; use timeframe bubbles to filter\n"
            "• Browse for input/output folders; Add Music… or Open folder for tracks\n"
            "• Intro Video: add your own with Add Intro/GIF… or Open folder\n"
            "• RUN VIDEO COMPILER builds your video; STOP cancels (no credit used)"
        )
        ttk.Label(
            title_inner,
            text=quick_tips,
            style='Heading.TLabel',
            font=('Segoe UI', 8),
            justify='left',
        ).pack(anchor='w')

        # Right side: licensing and attribution
        license_frame = ttk.Frame(header_frame, style='Header.TFrame')
        license_frame.pack(side='right', anchor='n', padx=(0, 5), pady=(4, 0))

        ttk.Label(
            license_frame,
            textvariable=self.license_status_var,
            style='Heading.TLabel',
            font=('Segoe UI', 9, 'bold'),
            justify='right',
        ).pack(anchor='e')

        license_buttons = ttk.Frame(license_frame, style='Header.TFrame')
        license_buttons.pack(anchor='e', pady=(4, 0))

        tk.Button(
            license_buttons,
            text="Plans",
            command=self.show_checkout_window,
            font=('Segoe UI', 8, 'bold'),
            bg=self.colors['accent'],
            fg='white',
            relief='raised',
            padx=8,
            pady=3,
            cursor='hand2',
        ).pack(side='left', padx=(0, 6))

        tk.Button(
            license_buttons,
            text="Restore",
            command=self.show_license_recovery_window,
            font=('Segoe UI', 8),
            bg=self.colors['button'],
            fg='white',
            relief='raised',
            padx=8,
            pady=3,
            cursor='hand2',
        ).pack(side='left', padx=(0, 6))

        tk.Button(
            license_buttons,
            text="Refresh",
            command=lambda: threading.Thread(target=self.refresh_license_status, daemon=True).start(),
            font=('Segoe UI', 8),
            bg=self.colors['button'],
            fg='white',
            relief='raised',
            padx=8,
            pady=3,
            cursor='hand2',
        ).pack(side='left')

        ttk.Label(
            license_frame,
            text="20 free compiles, then packs or monthly access",
            style='Heading.TLabel',
            font=('Segoe UI', 8),
            justify='right',
        ).pack(anchor='e', pady=(3, 0))
        return

    def create_donation_support_section(self, parent):
        """Optional donations: labels sit directly beside payment icons (same row)."""
        support_frame = tk.Frame(parent, bg=self.colors['frame_bg'])
        support_frame.pack(fill='x', pady=(8, 0))

        row = tk.Frame(support_frame, bg=self.colors['frame_bg'])
        row.pack(fill='x', anchor='w')

        tk.Label(
            row,
            text="Optional donations:",
            bg=self.colors['frame_bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 9, 'bold'),
            anchor='w',
        ).pack(side='left', padx=(0, 6))

        tk.Label(
            row,
            text="Extra support only — not credits or monthly access.",
            bg=self.colors['frame_bg'],
            fg='#c6d0dc',
            font=('Segoe UI', 8),
            anchor='w',
        ).pack(side='left', padx=(0, 10))

        icon_row = row

        payment_methods = [
            ('Venmo', 'venmo', lambda: self.open_venmo()),
            ('PayPal', 'paypal', lambda: self.open_paypal()),
            ('Bitcoin', 'bitcoin', lambda: self.copy_crypto_address('btc')),
            ('Ethereum', 'ethereum', lambda: self.copy_crypto_address('eth')),
            ('Solana', 'solana', lambda: self.copy_crypto_address('sol')),
        ]

        for name, logo_key, command in payment_methods:
            if hasattr(self, 'payment_logos') and logo_key in self.payment_logos:
                btn = tk.Button(
                    icon_row,
                    image=self.payment_logos[logo_key],
                    bg=self.colors['frame_bg'],
                    fg='white',
                    width=28,
                    height=28,
                    relief='flat',
                    borderwidth=0,
                    cursor='hand2',
                    command=command,
                    activebackground=self.colors['frame_bg'],
                )
                print(f"[OK] Created {name} donation button with official logo")
            else:
                fallback_icons = {
                    'venmo': 'V', 'paypal': 'P', 'bitcoin': 'B',
                    'ethereum': 'E', 'solana': 'S'
                }
                btn = tk.Button(
                    icon_row,
                    text=fallback_icons.get(logo_key, 'P'),
                    font=('Segoe UI', 10, 'bold'),
                    bg=self.colors['frame_bg'],
                    fg='white',
                    width=2,
                    height=1,
                    relief='flat',
                    borderwidth=0,
                    cursor='hand2',
                    command=command,
                    activebackground=self.colors['frame_bg'],
                )
                print(f"[WARN] Using fallback icon for {name} donation button")

            btn.pack(side='left', padx=(0, 4))
            self.create_tooltip(btn, f"Optional donation via {name}. This does not add credits.")

        
    def create_config_section(self, parent):
        """Create configuration input section"""
        
        # Configuration frame with standard styling
        config_frame = tk.LabelFrame(
            parent,
            text="Path Configuration",
            padx=12,
            pady=10,
            bg=self.colors['frame_bg'],
            fg=self.colors['title_color'],
            font=('Segoe UI', 11, 'bold'),
            relief='groove',
            borderwidth=2,
        )
        config_frame.pack(fill='x', pady=(0, 10))
        
        # Input folder
        self.create_path_row(config_frame, "Input Video Folder:", "input_path", 
                           "Select folder containing your UO gameplay videos",
                           is_directory=True, row=0)
        
        # Output folder  
        self.create_path_row(config_frame, "Output Video Folder:", "output_path",
                           "Select folder where compiled videos will be saved", 
                           is_directory=True, row=1)
        return
        
        # Current paths display with enhanced styling
        current_frame = ttk.Frame(config_frame, style='Custom.TFrame')
        current_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(20, 0))
        
        paths_label = ttk.Label(current_frame, text="[LIST] Current Configuration:", style='Heading.TLabel')
        paths_label.pack(anchor='w', pady=(0, 5))
        
        self.paths_text = tk.Text(current_frame, height=5, wrap='word', 
                                 bg=self.colors['text_bg'], 
                                 fg=self.colors['text_fg'], 
                                 font=('Consolas', 9),
                                 borderwidth=2,
                                 relief='sunken',
                                 insertbackground=self.colors['accent'])
        self.paths_text.pack(fill='x', pady=5)
        
    def create_path_row(self, parent, label_text, config_key, tooltip, is_directory=True, row=0):
        """Create a path selection row"""
        
        # Label
        label = tk.Label(
            parent,
            text=label_text,
            bg=self.colors['frame_bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 10, 'bold'),
        )
        label.grid(row=row, column=0, sticky='w', padx=(0, 10), pady=3)
        
        # Entry with enhanced styling
        entry_var = tk.StringVar()
        setattr(self, f"{config_key}_var", entry_var)
        
        entry = ttk.Entry(parent, textvariable=entry_var, width=55, style='Custom.TEntry')
        entry.grid(row=row, column=1, sticky='ew', padx=(0, 12), pady=4)
        
        # Browse button with enhanced styling and icon
        browse_cmd = lambda: self.browse_path(entry_var, is_directory, tooltip)
        
        # Create the browse button with icon
        browse_btn = tk.Button(parent, text="Browse", 
                              image=self.icons['folder'],
                              compound='left',
                              command=browse_cmd, 
                              font=('Arial', 8),
                              bg=self.colors['button'],
                              fg='white',
                              relief='raised',
                              width=80,  # Pixel width instead of character width
                              padx=6)
        self.button_images[f'browse_{config_key}'] = self.icons['folder']  # Keep reference to prevent garbage collection
        browse_btn.grid(row=row, column=2, pady=4)
        
        # Configure grid weights
        parent.grid_columnconfigure(1, weight=1)
        
    def browse_path(self, var, is_directory, title):
        """Open file/directory browser"""
        if is_directory:
            path = filedialog.askdirectory(title=title)
        else:
            path = filedialog.askopenfilename(title=title)
            
        if path:
            var.set(path)
            self.update_paths_display()
            self.save_config()
            if var is getattr(self, 'input_path_var', None):
                self.refresh_clip_selection_panel(preserve_saved=True)
    
    def get_available_music(self):
        """Get list of available music files"""
        try:
            music_dir = self.get_music_dir()
            if not os.path.exists(music_dir):
                return ['None', '[RANDOM] Random']
            
            music_files = ['None', '[RANDOM] Random']  # None option first, then random option
            for file in os.listdir(music_dir):
                if file.lower().endswith(self.MUSIC_EXTENSIONS):
                    music_files.append(os.path.splitext(file)[0])  # Remove extension for display
            
            return music_files if len(music_files) > 2 else ['None', '[RANDOM] Random']
        except Exception:
            return ['None', '[RANDOM] Random']
    
    def get_stock_intro_path(self):
        """Return the bundled stock intro media file, if present."""
        intro_dir = self.get_intro_dir()
        if not os.path.isdir(intro_dir):
            return ""
        for file in os.listdir(intro_dir):
            if not file.lower().endswith(self.INTRO_EXTENSIONS):
                continue
            if os.path.splitext(file)[0] == self.STOCK_INTRO_BASENAME:
                return os.path.join(intro_dir, file)
        return ""

    def stock_intro_available(self):
        return bool(self.get_stock_intro_path())

    def normalize_intro_selection(self, selection):
        """Map saved values to the fixed intro dropdown options."""
        selection = str(selection or "").strip()
        legacy_stock = {self.STOCK_INTRO_BASENAME, self.INTRO_OPTION_STOCK}
        options = self.get_available_intros()
        if selection in options:
            return selection
        if selection in legacy_stock and self.INTRO_OPTION_STOCK in options:
            return self.INTRO_OPTION_STOCK
        if selection == "[RANDOM] Random" and "[RANDOM] Random" in options:
            return "[RANDOM] Random"
        return options[0] if options else "None"

    def intro_selection_for_compiler(self):
        """Value passed to UOVidCompiler (stock file basename is StockDefault)."""
        selection = self.intro_selection_var.get()
        if selection == self.INTRO_OPTION_STOCK:
            return self.STOCK_INTRO_BASENAME
        return selection

    def get_available_intros(self):
        """Intro choices: None, Stock (bundled), Random, and any files in the Intros folder."""
        try:
            intro_dir = self.get_intro_dir()
            if not os.path.isdir(intro_dir):
                return ["None", "[RANDOM] Random"]

            custom_names = []
            stock_found = False
            for file in os.listdir(intro_dir):
                if not file.lower().endswith(self.INTRO_EXTENSIONS):
                    continue
                stem = os.path.splitext(file)[0]
                if stem == self.STOCK_INTRO_BASENAME:
                    stock_found = True
                else:
                    custom_names.append(stem)

            options = ["None"]
            if stock_found:
                options.append(self.INTRO_OPTION_STOCK)
            options.append("[RANDOM] Random")
            options.extend(sorted(custom_names))
            return options if options else ["None", "[RANDOM] Random"]
        except Exception:
            return ["None", "[RANDOM] Random"]
    
    def create_action_section(self, parent):
        """Create action buttons section with video configuration options"""
        
        # Action buttons with enhanced layout
        action_frame = ttk.Frame(parent, style='Custom.TFrame')
        action_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Video Configuration Options (above the main button)
        config_options_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        config_options_frame.pack(fill='x', pady=(0, 8))
        
        # Create a grid layout for the options with proper spacing
        options_container = ttk.Frame(config_options_frame, style='Custom.TFrame')
        options_container.pack(fill='x', pady=(0, 4))
        
        # Configure grid weights to make columns expand evenly
        options_container.grid_columnconfigure(0, weight=1)
        options_container.grid_columnconfigure(1, weight=1)
        options_container.grid_columnconfigure(2, weight=1)

        ttk.Label(options_container, text="Seconds Trimmed from End:", style='Info.TLabel').grid(row=0, column=0, sticky='w', padx=5)
        ttk.Label(options_container, text="Background Music:", style='Info.TLabel').grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(options_container, text="Intro Video:", style='Info.TLabel').grid(row=0, column=2, sticky='w', padx=5)

        trim_options = ['None', '5', '10', '15', '20', '25', '30']
        self.trim_seconds_var.set('15')  # Default to 15 seconds like S+ working version
        trim_combo = ttk.Combobox(options_container, textvariable=self.trim_seconds_var,
                                values=trim_options, state='readonly')
        trim_combo.grid(row=1, column=0, sticky='ew', padx=5, pady=(2, 0))
        trim_combo.bind('<<ComboboxSelected>>', self.on_trim_seconds_changed)
        
        music_options = self.get_available_music()
        # Set default to None if empty
        if not self.music_selection_var.get() and music_options:
            self.music_selection_var.set(music_options[0])  # 'None'
        self.music_combo = ttk.Combobox(options_container, textvariable=self.music_selection_var,
                                 values=music_options, state='readonly')
        self.music_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=(2, 0))
        # Ensure current selection is visible
        if self.music_selection_var.get() in music_options:
            self.music_combo.current(music_options.index(self.music_selection_var.get()))
        else:
            self.music_combo.current(0)
        self.music_combo.bind('<<ComboboxSelected>>', lambda _event: self.save_config())
        music_tools = ttk.Frame(options_container, style='Custom.TFrame')
        music_tools.grid(row=2, column=1, sticky='w', padx=5, pady=(3, 0))
        tk.Button(
            music_tools,
            text="Add Music...",
            command=self.add_music_files,
            font=('Segoe UI', 8),
            bg=self.colors['button'],
            fg='white',
            relief='raised',
            cursor='hand2',
            padx=6,
            pady=2,
        ).pack(side='left')
        music_link = tk.Label(
            music_tools,
            text="Open folder",
            bg=self.colors['frame_bg'],
            fg=self.colors['accent'],
            cursor='hand2',
            font=('Segoe UI', 8, 'underline'),
        )
        music_link.pack(side='left', padx=(8, 0))
        music_link.bind('<Button-1>', lambda _event: self.open_music_folder())

        intro_options = self.get_available_intros()
        self.intro_selection_var.set(self.normalize_intro_selection(self.intro_selection_var.get() or "None"))
        self.intro_combo = ttk.Combobox(options_container, textvariable=self.intro_selection_var,
                                 values=intro_options, state='readonly')
        self.intro_combo.grid(row=1, column=2, sticky='ew', padx=5, pady=(2, 0))
        if self.intro_selection_var.get() in intro_options:
            self.intro_combo.current(intro_options.index(self.intro_selection_var.get()))
        else:
            self.intro_combo.current(0)
        self.intro_combo.bind('<<ComboboxSelected>>', lambda _event: self.save_config())
        intro_tools = ttk.Frame(options_container, style='Custom.TFrame')
        intro_tools.grid(row=2, column=2, sticky='w', padx=5, pady=(3, 0))
        tk.Button(
            intro_tools,
            text="Add Intro/GIF...",
            command=self.add_intro_files,
            font=('Segoe UI', 8),
            bg=self.colors['button'],
            fg='white',
            relief='raised',
            cursor='hand2',
            padx=6,
            pady=2,
        ).pack(side='left')
        tk.Button(
            intro_tools,
            text="Create Intro...",
            command=self.show_create_intro_dialog,
            font=('Segoe UI', 8),
            bg=self.colors['accent'],
            fg='white',
            relief='raised',
            cursor='hand2',
            padx=6,
            pady=2,
        ).pack(side='left', padx=(6, 0))
        intro_link = tk.Label(
            intro_tools,
            text="Open folder",
            bg=self.colors['frame_bg'],
            fg=self.colors['accent'],
            cursor='hand2',
            font=('Segoe UI', 8, 'underline'),
        )
        intro_link.pack(side='left', padx=(8, 0))
        intro_link.bind('<Button-1>', lambda _event: self.open_intro_folder())

        self.create_clip_selection_panel(action_frame)

        # Main action button (prominent) with stop control
        main_button_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        main_button_frame.pack(fill='x', pady=(0, 8))
        main_button_frame.grid_columnconfigure(0, weight=1)
        
        self.run_btn = tk.Button(main_button_frame, 
                               text="RUN VIDEO COMPILER", 
                               command=self.run_compiler,
                               bg=self.colors['accent'], 
                               fg='white',
                               font=('Segoe UI', 14, 'bold'),
                               relief='raised',
                               borderwidth=3,
                               pady=15,
                               cursor='hand2')
        self.run_btn.grid(row=0, column=0, sticky='ew', padx=(0, 10))

        self.stop_btn = tk.Button(
            main_button_frame,
            text="STOP",
            command=self.request_stop,
            bg=self.colors['error'],
            fg='white',
            font=('Segoe UI', 12, 'bold'),
            relief='raised',
            borderwidth=3,
            padx=18,
            pady=15,
            cursor='hand2',
            state='disabled',
        )
        self.stop_btn.grid(row=0, column=1, sticky='ns')
        self.stop_btn.grid_remove()

        progress_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        progress_frame.pack(fill='x')
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
            style='Yellow.Horizontal.TProgressbar',
        )
        self.progress_bar.pack(fill='x')
        tk.Label(
            progress_frame,
            textvariable=self.progress_text_var,
            bg=self.colors['frame_bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 9),
            anchor='w',
        ).pack(fill='x', pady=(4, 0))

        self.create_donation_support_section(action_frame)

    def create_clip_selection_panel(self, parent):
        """Create the always-visible clip selection and ordering panel."""
        panel = tk.LabelFrame(
            parent,
            text="Clip Selection",
            padx=10,
            pady=8,
            bg=self.colors['frame_bg'],
            fg=self.colors['title_color'],
            font=('Segoe UI', 11, 'bold'),
            relief='groove',
            borderwidth=2,
        )
        panel.pack(fill='both', expand=True, pady=(0, 10))
        self.clip_selection_panel = panel

        toolbar = tk.Frame(panel, bg=self.colors['frame_bg'])
        toolbar.pack(fill='x')

        tk.Label(
            toolbar,
            text="Timeframe:",
            bg=self.colors['frame_bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 9, 'bold'),
        ).pack(side='left', padx=(0, 8))

        for label, value in self.CLIP_TIMEFRAME_OPTIONS:
            bubble = tk.Radiobutton(
                toolbar,
                text=label,
                value=value,
                variable=self.clip_timeframe_var,
                indicatoron=False,
                command=self.on_clip_timeframe_changed,
                bg='#2b3138',
                fg='white',
                activebackground='#30574c',
                activeforeground='white',
                selectcolor=self.colors['accent'],
                relief='ridge',
                borderwidth=1,
                padx=8,
                pady=3,
                cursor='hand2',
                font=('Segoe UI', 8, 'bold'),
            )
            bubble.pack(side='left', padx=(0, 6))

        tk.Label(
            toolbar,
            text="Order:",
            bg=self.colors['frame_bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 9, 'bold'),
        ).pack(side='left', padx=(10, 6))

        if self.clip_order_var.get() not in self.CLIP_ORDER_OPTIONS:
            self.clip_order_var.set('newest_first')
        self.clip_order_combo = ttk.Combobox(
            toolbar,
            textvariable=self.clip_order_var,
            values=self.CLIP_ORDER_OPTIONS,
            state='readonly',
            width=15,
        )
        self.clip_order_combo.pack(side='left')
        self.clip_order_combo.bind('<<ComboboxSelected>>', self.on_clip_order_changed)

        summary_row = tk.Frame(panel, bg=self.colors['frame_bg'])
        summary_row.pack(fill='x', pady=(4, 4))

        tk.Label(
            summary_row,
            textvariable=self.clip_selection_summary_var,
            bg=self.colors['frame_bg'],
            fg=self.colors['accent'],
            font=('Segoe UI', 9, 'bold'),
            justify='left',
        ).pack(side='left', anchor='w')

        self.clip_show_all_link = tk.Label(
            summary_row,
            text="Show all in timeframe",
            bg=self.colors['frame_bg'],
            fg=self.colors['accent'],
            font=('Segoe UI', 8, 'underline'),
            cursor='hand2',
        )
        self.clip_show_all_link.bind(
            '<Button-1>',
            lambda _event: self.refresh_clip_selection_panel(preserve_saved=False),
        )

        body = tk.Frame(panel, bg=self.colors['frame_bg'])
        body.pack(fill='both', expand=True)

        self.clip_selection_canvas = tk.Canvas(body, bg="#1f252c", highlightthickness=0, cursor="hand2", height=360)
        clip_scrollbar = ttk.Scrollbar(body, orient='vertical', command=self.clip_selection_canvas.yview)
        self.clip_selection_canvas.configure(yscrollcommand=clip_scrollbar.set)
        self.clip_selection_canvas.pack(side='left', fill='both', expand=True)
        clip_scrollbar.pack(side='right', fill='y')

        self.clip_selection_canvas.bind('<Configure>', lambda _event: self.draw_clip_selection_rows())
        self.clip_selection_canvas.bind('<B1-Motion>', self.on_clip_drag_motion)
        self.clip_selection_canvas.bind('<ButtonRelease-1>', self.on_clip_drag_end)
        self.refresh_clip_selection_panel(preserve_saved=True, save_snapshot=False)
        
    def create_status_section(self, parent):
        """Create status display section with enhanced styling"""
        self.status_text = None
        self.config_summary_label = None
        return
        
        # Status frame with standard styling
        status_frame = ttk.LabelFrame(parent, text="Status & Information", padding=15)
        status_frame.pack(fill='both', expand=True)

        self.config_summary_label = tk.Label(
            status_frame,
            textvariable=self.config_summary_var,
            bg=self.colors['text_bg'],
            fg=self.colors['text_fg'],
            font=('Consolas', 9),
            anchor='w',
            justify='left',
            padx=8,
            pady=8,
            borderwidth=2,
            relief='sunken',
        )
        self.config_summary_label.pack(fill='x', pady=(0, 10))
        
        # Status text area with dark theme
        self.status_text = tk.Text(status_frame, height=15, width=80, wrap='word',
                                  bg=self.colors['text_bg'],  # Dark background
                                  fg=self.colors['text_fg'],  # Bright green text
                                  font=('Consolas', 11),
                                  borderwidth=2,
                                  relief='sunken',
                                  insertbackground=self.colors['accent'])
        
        # Scrollbar for status text
        scrollbar = ttk.Scrollbar(status_frame, orient='vertical', command=self.status_text.yview)
        
        # Pack text and scrollbar
        self.status_text.pack(side='left', fill='both', expand=True, padx=(0, 5))
        scrollbar.pack(side='right', fill='y')
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        # Enhanced initial status messages - SAFE ASCII VERSION for standalone EXE
        startup_text = """Welcome to Auto Vid Compiler!

********* INSTRUCTIONS *********

Professional Video Compilation Tool
Automatically combines multiple short clips into one polished video with intro and music.

[PATHS] VIDEO INPUT PATH: Select folder containing your video clips
   * IMPORTANT: Will process ALL videos in this folder
   * Video formats: MP4, AVI, MOV, MKV, WEBM, M4V
   * Skips files larger than 500MB to prevent hanging

[TIME] TRIM SECONDS: Duration to take from the END of each video
   * Example: 30 = last 30 seconds of each video file
   * All clips will be standardized to this same duration

[MUSIC] MUSIC SELECTION: Background music for your compilation
   * Audio formats: MP3, WAV, M4A, OGG, FLAC, AAC
   * Music loops/extends to match total video length
   * Mixed at lower volume so original audio stays clear

[INTRO] INTRO VIDEO: Optional intro at the start of the compilation
   * None = no intro (default)
   * Stock = bundled stock intro (StockDefault)
   * Random = random file from your Intros folder
   * Or pick a specific intro you added (Add Intro/GIF... / Open folder)
   * Formats: MP4, AVI, MOV, MKV, WEBM, M4V, GIF
   * Intro duration matches your trim seconds setting

[ORDER] CLIP ORDER: Choose newest-first, oldest-first, filename order, or save a custom order

[RUN] COMPILE VIDEOS: Starts the compilation process
   * Creates: Intro + All Clips + Background Music = Final Video
   * Progress shown in this status area
   * Output saved to your Videos folder
   * A compile credit is recorded only after a successful run
   * STOP cancels the current step; no credit is used when you stop

[TIP] WORKFLOW TIP: 
   1. Clean out old/unwanted clips before running (to avoid too many clips)
   2. Run compiler to create your compilation video
   3. Move/delete clips after compiling to keep folder clean
   4. Keep your best highlights in a separate folder for later

Ready to compile? Configure your settings above and click "Compile Videos"!
"""
        self.status_text.insert('end', startup_text)
        self.status_text.update()
        self.root.update()
        
        # Add proper color coding to the log messages
        self.status_text.tag_configure("success", foreground=self.colors['success'])
        self.status_text.tag_configure("info", foreground=self.colors['text_fg'])
        self.status_text.tag_configure("warning", foreground=self.colors['warning'])
        self.status_text.tag_configure("error", foreground=self.colors['error'])
        
    def update_paths_display(self):
        """Update the current paths display with enhanced formatting"""
        input_path = self.input_path_var.get()
        output_path = self.output_path_var.get()
        music_dir = self.get_music_dir()
        intro_dir = self.get_intro_dir()
        selected_clips = len(getattr(self, 'clip_selection_files', []))
        timeframe_label = self.get_clip_timeframe_label() if hasattr(self, 'clip_timeframe_var') else '1 week'
        ready = "Ready" if input_path and output_path else "Set input and output folders"
        display_text = (
            f"[CONFIG] {ready}\n"
            f"[INPUT] {input_path if input_path else 'Not set'}\n"
            f"[OUTPUT] {output_path if output_path else 'Not set'}\n"
            f"[MUSIC] {music_dir} ({len(self.get_music_files())} tracks) | "
            f"[INTRO] {intro_dir} ({len(self.get_intro_files())} files) | "
            f"[CLIPS] {selected_clips} selected | [TIMEFRAME] {timeframe_label} | "
            f"[ORDER] {self.clip_order_var.get() or 'newest_first'} | [FFMPEG] Included"
        )
        self.config_summary_var.set(display_text)
        
    def get_music_files(self):
        """Get list of available music files"""
        music_dir = self.get_music_dir()
        if os.path.exists(music_dir):
            return [f for f in os.listdir(music_dir) if f.lower().endswith(self.MUSIC_EXTENSIONS)]
        return []
        
    def get_intro_files(self):
        """All intro media files in the Intros folder (for path summary)."""
        intro_dir = self.get_intro_dir()
        if not os.path.isdir(intro_dir):
            return []
        return [
            name for name in os.listdir(intro_dir)
            if name.lower().endswith(self.INTRO_EXTENSIONS)
        ]

    def refresh_license_status(self):
        """Refresh license/trial status from the server, falling back to signed local state."""
        if autovid_license is None:
            self.root.after(0, lambda: self.license_status_var.set("License module unavailable"))
            return
        license_api = get_autovid_license()
        status = license_api.get_status(prefer_remote=True)
        self.root.after(0, lambda s=status: self.apply_license_status(s))

    def open_demo_video(self):
        """Open the demo video when a public URL is configured."""
        demo_url = self.config.get("demo_video_url", "").strip()
        if demo_url:
            webbrowser.open(demo_url)
        else:
            messagebox.showinfo(
                "Demo Video Placeholder",
                "Record and publish the demo video, then add its YouTube URL to gui_config.json as demo_video_url."
            )

    def apply_license_status(self, status):
        """Display current license status."""
        try:
            license_api = get_autovid_license()
            self.license_status_var.set(license_api.status_line(status))
        except Exception:
            self.license_status_var.set("License status unavailable")

    def ensure_compile_entitlement(self):
        """Verify a compile may start; credits are consumed only after success."""
        if autovid_license is None:
            messagebox.showerror(
                "License Error",
                "The license module could not be loaded. Reinstall the app or download the latest release."
            )
            return False

        license_api = get_autovid_license()
        ok, status, warning = license_api.can_compile_use()
        self.apply_license_status(status)
        if warning:
            self.log_warning(warning)

        if ok:
            self.log_status("[LICENSE] Compile allowed — one credit is used only after a successful run.")
            return True

        self.show_checkout_window()
        messagebox.showinfo(
            "License Required",
            str(warning or "Buy a credit pack or monthly unlimited access to continue.")
        )
        return False

    def consume_compile_entitlement_on_success(self):
        """Record one compilation use after the output is created successfully."""
        if autovid_license is None:
            return
        license_api = get_autovid_license()
        ok, status, warning = license_api.consume_use()
        self.apply_license_status(status)
        if warning:
            self.log_warning(warning)
        if ok:
            entitlement = status.get("entitlement", "use")
            self.log_status(f"[LICENSE] Recorded one {entitlement} compilation use.")
        else:
            self.log_warning("Compilation completed, but no license credit could be recorded. Please refresh licensing.")
            self.show_checkout_window()

    def show_checkout_window(self):
        """Open the in-app purchase dialog. Stripe card entry stays on Stripe-hosted checkout."""
        if autovid_license is None:
            messagebox.showerror("License Error", "License module is unavailable.")
            return

        license_api = get_autovid_license()

        if self.checkout_window and self.checkout_window.winfo_exists():
            self.checkout_window.lift()
            return

        window = tk.Toplevel(self.root)
        self.checkout_window = window
        window.title("Auto Vid Compiler Plans")
        window.resizable(False, False)
        window.configure(bg=self.colors['bg'])
        self.position_child_window(window, width=520, height=360, modal=True)

        try:
            ico_path = self.get_icon_path()
            if os.path.exists(ico_path):
                window.iconbitmap(ico_path)
        except Exception:
            pass

        self.checkout_status_var = tk.StringVar(value="Choose a plan. Secure payment is handled by Stripe Checkout.")
        email_var = tk.StringVar()
        plan_var = tk.StringVar(value="credits_12")
        plans = [
            ("credits_5", "$5 - 5 compile credits"),
            ("credits_12", "$10 - 12 compile credits"),
            ("monthly_unlimited", "$10/mo - unlimited compiles"),
        ]

        outer = tk.Frame(window, bg=self.colors['bg'], padx=18, pady=16)
        outer.pack(fill='both', expand=True)

        tk.Label(
            outer,
            text="Auto Vid Compiler Credits",
            bg=self.colors['bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 15, 'bold')
        ).pack(anchor='w', pady=(0, 10))

        tk.Label(
            outer,
            textvariable=self.checkout_status_var,
            bg=self.colors['bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 9),
            wraplength=410,
            justify='left'
        ).pack(anchor='w', pady=(0, 12))

        form = tk.Frame(outer, bg=self.colors['bg'])
        form.pack(fill='x')

        cached_status = license_api.get_status(prefer_remote=False)
        email_var.set(cached_status.get("email", ""))

        tk.Label(form, text="Email (required):", bg=self.colors['bg'], fg=self.colors['label_color'], font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w', pady=5)
        tk.Entry(form, textvariable=email_var, width=34).grid(row=0, column=1, sticky='ew', padx=(10, 0), pady=5)

        tk.Label(form, text="Plan:", bg=self.colors['bg'], fg=self.colors['label_color'], font=('Segoe UI', 9)).grid(row=1, column=0, sticky='nw', pady=5)
        plan_frame = tk.Frame(form, bg=self.colors['bg'])
        plan_frame.grid(row=1, column=1, sticky='ew', padx=(10, 0), pady=5)
        for value, label in plans:
            tk.Radiobutton(
                plan_frame,
                text=label,
                variable=plan_var,
                value=value,
                bg=self.colors['bg'],
                fg=self.colors['label_color'],
                selectcolor=self.colors['frame_bg'],
                activebackground=self.colors['bg'],
                activeforeground=self.colors['label_color'],
                font=('Segoe UI', 9),
            ).pack(anchor='w')
        form.grid_columnconfigure(1, weight=1)

        buttons = tk.Frame(outer, bg=self.colors['bg'])
        buttons.pack(fill='x', pady=(18, 0))

        tk.Button(
            buttons,
            text="Open Secure Stripe Checkout",
            command=lambda: self.start_checkout(email_var.get(), plan_var.get()),
            bg=self.colors['accent'],
            fg='white',
            font=('Segoe UI', 9, 'bold'),
            relief='raised',
            padx=10,
            pady=6,
            cursor='hand2',
        ).pack(side='left')

        tk.Button(
            buttons,
            text="I Paid - Refresh",
            command=self.confirm_checkout_session,
            bg=self.colors['button'],
            fg='white',
            font=('Segoe UI', 9),
            relief='raised',
            padx=10,
            pady=6,
            cursor='hand2',
        ).pack(side='left', padx=(8, 0))

        tk.Button(
            buttons,
            text="Close",
            command=window.destroy,
            bg='#666666',
            fg='white',
            font=('Segoe UI', 9),
            relief='raised',
            padx=10,
            pady=6,
            cursor='hand2',
        ).pack(side='right')

        recovery_hint = license_api.recovery_summary(cached_status)
        tk.Label(
            outer,
            text=recovery_hint,
            bg=self.colors['bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 8),
            wraplength=470,
            justify='left'
        ).pack(anchor='w', pady=(14, 0))

    def show_license_recovery_window(self):
        """Open a dialog to restore a paid license onto this device."""
        if autovid_license is None:
            messagebox.showerror("License Error", "License module is unavailable.")
            return

        license_api = get_autovid_license()

        if self.license_recovery_window and self.license_recovery_window.winfo_exists():
            self.license_recovery_window.lift()
            self.license_recovery_window.focus_force()
            return

        status = license_api.get_status(prefer_remote=False)
        window = tk.Toplevel(self.root)
        self.license_recovery_window = window
        window.title("Restore Auto Vid Compiler License")
        window.resizable(False, False)
        window.configure(bg=self.colors['bg'])
        self.position_child_window(window, width=560, height=320, modal=True)

        try:
            ico_path = self.get_icon_path()
            if os.path.exists(ico_path):
                window.iconbitmap(ico_path)
        except Exception:
            pass

        status_var = tk.StringVar(value="Enter the recovery email and key from your paid checkout.")
        email_var = tk.StringVar(value=status.get("email", ""))
        key_var = tk.StringVar(value=status.get("license_key", ""))

        outer = tk.Frame(window, bg=self.colors['bg'], padx=18, pady=16)
        outer.pack(fill='both', expand=True)

        tk.Label(
            outer,
            text="Restore Paid License",
            bg=self.colors['bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 15, 'bold')
        ).pack(anchor='w', pady=(0, 10))

        tk.Label(
            outer,
            textvariable=status_var,
            bg=self.colors['bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 9),
            wraplength=500,
            justify='left'
        ).pack(anchor='w', pady=(0, 12))

        tk.Label(outer, text="Recovery email:", bg=self.colors['bg'], fg=self.colors['label_color'], font=('Segoe UI', 9)).pack(anchor='w')
        tk.Entry(outer, textvariable=email_var, width=46).pack(fill='x', pady=(4, 10))

        tk.Label(outer, text="Recovery key:", bg=self.colors['bg'], fg=self.colors['label_color'], font=('Segoe UI', 9)).pack(anchor='w')
        tk.Entry(outer, textvariable=key_var, width=46).pack(fill='x', pady=(4, 10))

        tk.Label(
            outer,
            text=license_api.recovery_summary(status),
            bg=self.colors['bg'],
            fg=self.colors['label_color'],
            font=('Segoe UI', 8),
            wraplength=500,
            justify='left'
        ).pack(anchor='w', pady=(2, 0))

        button_row = tk.Frame(outer, bg=self.colors['bg'])
        button_row.pack(fill='x', pady=(18, 0))

        def copy_key():
            key = key_var.get().strip()
            if not key:
                messagebox.showinfo("Copy Recovery Key", "There is no recovery key to copy yet.")
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(key)
            status_var.set("Recovery key copied to clipboard.")

        def activate():
            email = email_var.get().strip()
            license_key = key_var.get().strip()
            if not email or not license_key:
                status_var.set("Both recovery email and recovery key are required.")
                return
            status_var.set("Restoring paid license onto this device...")

            def worker():
                result = license_api.activate_license(email=email, license_key=license_key)
                if result.get("ok"):
                    self.root.after(0, lambda r=result: self.apply_license_status(r))
                    message = str(result.get("recovery_message") or "Paid access restored onto this device.")
                    self.root.after(0, lambda m=message: status_var.set(m))
                    self.root.after(0, lambda m=message: self.log_status(f"[LICENSE] {m}"))
                    self.root.after(0, lambda m=message: messagebox.showinfo("License Restored", m))
                else:
                    error = str(result.get("error", "Could not restore that license."))
                    self.root.after(0, lambda e=error: status_var.set(e))

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(
            button_row,
            text="Activate on This Device",
            command=activate,
            bg=self.colors['accent'],
            fg='white',
            font=('Segoe UI', 9, 'bold'),
            relief='raised',
            padx=10,
            pady=6,
            cursor='hand2',
        ).pack(side='left')

        tk.Button(
            button_row,
            text="Copy Key",
            command=copy_key,
            bg=self.colors['button'],
            fg='white',
            font=('Segoe UI', 9),
            relief='raised',
            padx=10,
            pady=6,
            cursor='hand2',
        ).pack(side='left', padx=(8, 0))

        tk.Button(
            button_row,
            text="Close",
            command=window.destroy,
            bg='#666666',
            fg='white',
            font=('Segoe UI', 9),
            relief='raised',
            padx=10,
            pady=6,
            cursor='hand2',
        ).pack(side='right')

        window.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, 'license_recovery_window', None), window.destroy()))

    def start_checkout(self, email, plan_id):
        """Create a Stripe Checkout session and open it."""
        if autovid_license is None:
            return
        license_api = get_autovid_license()
        email = (email or "").strip()
        if not email:
            if hasattr(self, 'checkout_status_var'):
                self.checkout_status_var.set("Enter a recovery email before opening Stripe Checkout.")
            messagebox.showerror("Recovery Email Required", "Paid plans require a recovery email so credits and subscriptions can be restored on a new device.")
            return
        self.checkout_status_var.set("Creating Stripe Checkout session...")

        def worker():
            result = license_api.create_checkout_session(email=email, plan_id=plan_id)
            if result.get("ok") and result.get("url"):
                self.checkout_session_id = result.get("session_id", "")
                license_api.open_checkout_url(str(result.get("url") or ""))
                self.root.after(0, lambda: self.checkout_status_var.set(
                    "Stripe Checkout opened in your browser. Return here after payment and click refresh."
                ))
                self.root.after(5000, self.poll_checkout_status)
            else:
                error = str(result.get("error", "Could not create checkout session."))
                self.root.after(0, lambda e=error: self.checkout_status_var.set(e))

        threading.Thread(target=worker, daemon=True).start()

    def confirm_checkout_session(self):
        """Manually refresh the current checkout session."""
        if not self.checkout_session_id:
            if hasattr(self, 'checkout_status_var'):
                self.checkout_status_var.set("No checkout session has been started yet.")
            return
        self.poll_checkout_status()

    def poll_checkout_status(self):
        """Check whether Stripe has marked the checkout session paid."""
        if autovid_license is None or not self.checkout_session_id:
            return
        if self.checkout_window and not self.checkout_window.winfo_exists():
            return

        license_api = get_autovid_license()

        def worker():
            result = license_api.confirm_session(self.checkout_session_id)
            if result.get("ok") and result.get("paid"):
                recovery_note = license_api.recovery_summary(result)
                self.checkout_session_id = ""
                self.root.after(0, lambda: self.checkout_status_var.set(f"Payment confirmed. Credits added. {recovery_note}"))
                self.root.after(0, lambda: self.apply_license_status(result))
                self.root.after(0, lambda: messagebox.showinfo("Payment Confirmed", f"Payment confirmed.\n\n{recovery_note}"))
                return
            message = str(result.get("error", "Payment has not completed yet."))
            self.root.after(0, lambda m=message: self.checkout_status_var.set(m))
            if self.checkout_window and self.checkout_window.winfo_exists():
                self.root.after(5000, self.poll_checkout_status)

        threading.Thread(target=worker, daemon=True).start()

    def _copy_selected_files(self, title, target_folder, filetypes, refresh_callback):
        """Import selected files into an app media folder."""
        os.makedirs(target_folder, exist_ok=True)
        selected = filedialog.askopenfilenames(title=title, filetypes=filetypes)
        if not selected:
            return

        copied = 0
        for src in selected:
            if not os.path.isfile(src):
                continue
            base, ext = os.path.splitext(os.path.basename(src))
            target = os.path.join(target_folder, base + ext)
            index = 1
            while os.path.exists(target):
                target = os.path.join(target_folder, f"{base}_{index}{ext}")
                index += 1
            shutil.copy2(src, target)
            copied += 1

        refresh_callback()
        self.update_paths_display()
        self.log_success(f"Imported {copied} file(s) into {target_folder}")

    def add_music_files(self):
        """Add one or more background music files."""
        music_dir = self.get_music_dir()
        self._copy_selected_files(
            "Add background music (MP3, WAV, M4A, OGG, FLAC, AAC)",
            music_dir,
            (("Audio files", "*.mp3 *.wav *.m4a *.ogg *.flac *.aac"), ("All files", "*.*")),
            self.refresh_music_list,
        )

    def show_create_intro_dialog(self):
        """Open the custom intro builder (template + animated text + sound)."""
        if not INTRO_CREATOR_AVAILABLE or intro_creator is None:
            messagebox.showerror("Intro Creator", "The intro creator module could not be loaded.")
            return
        if not self.get_ffmpeg_path():
            messagebox.showerror("Intro Creator", "FFmpeg was not found. Cannot build intro videos.")
            return

        if self._create_intro_window is not None:
            try:
                if self._create_intro_window.winfo_exists():
                    self._create_intro_window.lift()
                    self._create_intro_window.focus_force()
                    return
            except tk.TclError:
                self._create_intro_window = None

        window = tk.Toplevel(self.root)
        self._create_intro_window = window
        window.title("Create Intro Video")
        window.transient(self.root)
        window.configure(bg=self.colors['frame_bg'])
        self._center_toplevel(window, width=1020, height=680)

        content = ttk.Frame(window, style='Custom.TFrame', padding=12)
        content.pack(fill='both', expand=True)

        body = ttk.Frame(content, style='Custom.TFrame')
        body.pack(side='left', fill='both', expand=True, padx=(0, 12))

        preview_panel = ttk.Frame(content, style='Custom.TFrame')
        preview_panel.pack(side='right', fill='y')
        ttk.Label(preview_panel, text="Preview", style='Heading.TLabel', font=('Segoe UI', 10, 'bold')).pack(
            anchor='w', pady=(0, 6)
        )
        preview_image_label = tk.Label(
            preview_panel,
            bg='#101010',
            relief='sunken',
            borderwidth=2,
            width=480,
            height=270,
        )
        preview_image_label.pack()
        preview_caption_var = tk.StringVar(
            value="Shows template frame with text position (matches final overlay)."
        )
        ttk.Label(
            preview_panel,
            textvariable=preview_caption_var,
            style='Info.TLabel',
            wraplength=500,
            justify='left',
        ).pack(anchor='w', pady=(8, 0))

        preview_state = {"frame": None, "frame_key": None, "photo": None, "busy": False}
        ffprobe_path = os.path.join(os.path.dirname(self.get_ffmpeg_path()), "ffprobe.exe")
        search_roots = self.get_intro_creator_search_roots()
        preview_after_id = {"id": None}

        def close_create_intro_window():
            if preview_after_id["id"] is not None:
                try:
                    window.after_cancel(preview_after_id["id"])
                except tk.TclError:
                    pass
                preview_after_id["id"] = None
            try:
                window.grab_release()
            except tk.TclError:
                pass
            self._create_intro_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_create_intro_window)

        ttk.Label(body, text="Template", style='Info.TLabel').grid(row=0, column=0, sticky='w')
        template_var = tk.StringVar(value=intro_creator.INTRO_TEMPLATE_NAMES[0])
        ttk.Combobox(
            body,
            textvariable=template_var,
            values=list(intro_creator.INTRO_TEMPLATE_NAMES),
            state='readonly',
            width=24,
        ).grid(row=0, column=1, columnspan=2, sticky='ew', pady=(0, 6))

        ttk.Label(body, text="Text appears (sec before end)", style='Info.TLabel').grid(row=1, column=0, sticky='w')
        seconds_var = tk.StringVar(value=str(intro_creator.DEFAULT_SECONDS_FROM_END))
        ttk.Spinbox(body, from_=0.3, to=15.0, increment=0.1, textvariable=seconds_var, width=10).grid(
            row=1, column=1, sticky='w', pady=(0, 6)
        )
        ttk.Label(body, text="(1.5 recommended)", style='Info.TLabel').grid(row=1, column=2, sticky='w')

        ttk.Label(body, text="Font style", style='Info.TLabel').grid(row=2, column=0, sticky='w')
        font_style_var = tk.StringVar(value="Arial Bold")
        ttk.Combobox(
            body,
            textvariable=font_style_var,
            values=list(intro_creator.FONT_STYLES.keys()),
            state='readonly',
            width=24,
        ).grid(row=2, column=1, columnspan=2, sticky='ew', pady=(0, 6))

        ttk.Label(body, text="Text size", style='Info.TLabel').grid(row=3, column=0, sticky='w')
        font_size_var = tk.StringVar(value="Large")
        ttk.Combobox(
            body,
            textvariable=font_size_var,
            values=list(intro_creator.FONT_SIZES.keys()),
            state='readonly',
            width=24,
        ).grid(row=3, column=1, columnspan=2, sticky='ew', pady=(0, 6))

        ttk.Label(body, text="Text animation", style='Info.TLabel').grid(row=4, column=0, sticky='w')
        animation_var = tk.StringVar(value=intro_creator.ANIMATIONS[0])
        ttk.Combobox(
            body,
            textvariable=animation_var,
            values=list(intro_creator.ANIMATIONS),
            state='readonly',
            width=24,
        ).grid(row=4, column=1, columnspan=2, sticky='ew', pady=(0, 10))

        sfx_names = ["None"] + intro_creator.list_sound_effects(self.get_sound_effects_dir())

        ttk.Label(body, text="Line 1 text", style='Info.TLabel').grid(row=5, column=0, sticky='w')
        line1_var = tk.StringVar()
        ttk.Entry(body, textvariable=line1_var, width=32).grid(row=5, column=1, sticky='ew', pady=(0, 4))
        line1_sfx_var = tk.StringVar(value="None")
        ttk.Combobox(body, textvariable=line1_sfx_var, values=sfx_names, state='readonly', width=18).grid(
            row=5, column=2, sticky='ew', pady=(0, 4)
        )

        use_line2_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            body,
            text="Add second line (centered below line 1)",
            variable=use_line2_var,
        ).grid(row=6, column=0, columnspan=3, sticky='w', pady=(4, 4))

        ttk.Label(body, text="Line 2 text", style='Info.TLabel').grid(row=7, column=0, sticky='w')
        line2_var = tk.StringVar()
        line2_entry = ttk.Entry(body, textvariable=line2_var, width=32)
        line2_entry.grid(row=7, column=1, sticky='ew', pady=(0, 4))
        line2_sfx_var = tk.StringVar(value="None")
        line2_sfx_combo = ttk.Combobox(
            body, textvariable=line2_sfx_var, values=sfx_names, state='readonly', width=18
        )
        line2_sfx_combo.grid(row=7, column=2, sticky='ew', pady=(0, 4))

        ttk.Label(body, text="Output file name", style='Info.TLabel').grid(row=8, column=0, sticky='w')
        output_var = tk.StringVar()
        ttk.Entry(body, textvariable=output_var, width=32).grid(row=8, column=1, columnspan=2, sticky='ew', pady=(0, 6))
        ttk.Label(
            body,
            text="Saved to your Intros folder. Leave blank to name from line 1.",
            style='Info.TLabel',
        ).grid(row=9, column=0, columnspan=3, sticky='w', pady=(0, 8))

        status_var = tk.StringVar(value="")
        ttk.Label(body, textvariable=status_var, style='Info.TLabel', wraplength=500).grid(
            row=10, column=0, columnspan=3, sticky='w'
        )

        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=1)

        def toggle_line2():
            state = 'normal' if use_line2_var.get() else 'disabled'
            line2_entry.configure(state=state)
            line2_sfx_combo.configure(state='readonly' if use_line2_var.get() else 'disabled')

        def preview_lines():
            lines = []
            text1 = line1_var.get().strip()
            if text1:
                lines.append(text1)
            if use_line2_var.get():
                text2 = line2_var.get().strip()
                if text2:
                    lines.append(text2)
            return lines

        def apply_preview_image(pil_image):
            photo = ImageTk.PhotoImage(pil_image)
            preview_state["photo"] = photo
            preview_image_label.configure(image=photo, width=pil_image.width, height=pil_image.height)

        def redraw_preview_overlay():
            if preview_state["frame"] is None:
                return
            try:
                seconds_from_end = float(seconds_var.get())
            except ValueError:
                seconds_from_end = intro_creator.DEFAULT_SECONDS_FROM_END
            rendered = intro_creator.render_intro_preview_image(
                preview_state["frame"],
                preview_lines(),
                font_style=font_style_var.get(),
                font_size_label=font_size_var.get(),
            )
            template = template_var.get()
            preview_caption_var.set(
                f"{template} — text at ~{seconds_from_end:.1f}s before end (final position)."
            )
            apply_preview_image(rendered)

        def load_preview_frame_worker(frame_key):
            template = template_var.get()
            try:
                seconds_from_end = float(seconds_var.get())
            except ValueError:
                seconds_from_end = intro_creator.DEFAULT_SECONDS_FROM_END

            def worker():
                try:
                    frame = intro_creator.extract_template_frame_image(
                        template,
                        seconds_from_end,
                        search_roots=search_roots,
                        ffmpeg_path=self.get_ffmpeg_path(),
                        ffprobe_path=ffprobe_path,
                    )

                    def apply_frame():
                        preview_state["busy"] = False
                        preview_state["frame"] = frame
                        preview_state["frame_key"] = frame_key
                        redraw_preview_overlay()

                    window.after(0, apply_frame)
                except Exception as exc:
                    def show_error():
                        preview_state["busy"] = False
                        preview_caption_var.set(f"Preview unavailable: {exc}")

                    window.after(0, show_error)

            preview_state["busy"] = True
            threading.Thread(target=worker, daemon=True).start()

        def schedule_preview_refresh():
            if preview_after_id["id"] is not None:
                try:
                    window.after_cancel(preview_after_id["id"])
                except tk.TclError:
                    pass

            def refresh():
                template = template_var.get()
                try:
                    seconds_from_end = float(seconds_var.get())
                except ValueError:
                    seconds_from_end = intro_creator.DEFAULT_SECONDS_FROM_END
                frame_key = (template, round(seconds_from_end, 2))
                if preview_state["frame_key"] == frame_key and preview_state["frame"] is not None:
                    redraw_preview_overlay()
                    return
                if not preview_state["busy"]:
                    load_preview_frame_worker(frame_key)

            preview_after_id["id"] = window.after(200, refresh)

        use_line2_var.trace_add('write', lambda *_args: toggle_line2())
        toggle_line2()

        preview_trace_vars = (
            template_var,
            seconds_var,
            font_style_var,
            font_size_var,
            line1_var,
            line2_var,
            use_line2_var,
        )
        for var in preview_trace_vars:
            var.trace_add('write', lambda *_args: schedule_preview_refresh())
        schedule_preview_refresh()

        button_row = ttk.Frame(window, style='Custom.TFrame', padding=(12, 0, 12, 12))
        button_row.pack(fill='x', side='bottom')

        def resolve_sfx_path(name):
            if not name or name == "None":
                return None
            return os.path.join(self.get_sound_effects_dir(), name)

        def unique_output_path(filename):
            intro_dir = self.get_intro_dir()
            os.makedirs(intro_dir, exist_ok=True)
            base, ext = os.path.splitext(filename)
            if not ext:
                ext = ".mp4"
            candidate = os.path.join(intro_dir, f"{base}{ext}")
            counter = 2
            while os.path.exists(candidate):
                candidate = os.path.join(intro_dir, f"{base}_{counter}{ext}")
                counter += 1
            return candidate

        def on_create():
            line1 = line1_var.get().strip()
            if not line1:
                messagebox.showerror("Create Intro", "Enter text for line 1.")
                return
            prompts = [intro_creator.TextPromptSpec(line1, resolve_sfx_path(line1_sfx_var.get()))]
            if use_line2_var.get():
                line2 = line2_var.get().strip()
                if line2:
                    prompts.append(intro_creator.TextPromptSpec(line2, resolve_sfx_path(line2_sfx_var.get())))

            try:
                seconds_from_end = float(seconds_var.get())
            except ValueError:
                messagebox.showerror("Create Intro", "Seconds before end must be a number.")
                return

            filename = output_var.get().strip() or intro_creator.default_output_name(line1)
            if not filename.lower().endswith(".mp4"):
                filename = f"{filename}.mp4"
            output_path = unique_output_path(filename)

            create_btn.configure(state='disabled')
            status_var.set("Building intro video...")

            def worker():
                ffprobe = os.path.join(os.path.dirname(self.get_ffmpeg_path()), "ffprobe.exe")
                request = intro_creator.IntroBuildRequest(
                    template_name=template_var.get(),
                    output_path=output_path,
                    prompts=prompts,
                    seconds_from_end=seconds_from_end,
                    font_style=font_style_var.get(),
                    font_size_label=font_size_var.get(),
                    animation=animation_var.get(),
                    search_roots=self.get_intro_creator_search_roots(),
                    ffmpeg_path=self.get_ffmpeg_path(),
                    ffprobe_path=ffprobe,
                )
                ok, message = intro_creator.build_intro_video(request)

                def finish():
                    create_btn.configure(state='normal')
                    if ok:
                        stem = os.path.splitext(os.path.basename(output_path))[0]
                        self.refresh_intro_list()
                        self.intro_selection_var.set(stem)
                        self.save_config()
                        status_var.set(f"Created: {os.path.basename(output_path)}")
                        self.log_success(f"[INTRO] Created custom intro: {output_path}")
                        messagebox.showinfo(
                            "Intro Created",
                            f"Intro saved to:\n{output_path}\n\nIt is selected in the Intro Video dropdown.",
                        )
                        close_create_intro_window()
                    else:
                        status_var.set("Build failed.")
                        self.log_error(f"[INTRO] Create failed: {message}")
                        messagebox.showerror("Create Intro Failed", message)

                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        create_btn = tk.Button(
            button_row,
            text="Create Intro Video",
            command=on_create,
            bg=self.colors['accent'],
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            padx=12,
            pady=6,
            cursor='hand2',
        )
        create_btn.pack(side='left')
        tk.Button(
            button_row,
            text="Cancel",
            command=close_create_intro_window,
            bg='#666666',
            fg='white',
            font=('Segoe UI', 9),
            padx=10,
            pady=6,
            cursor='hand2',
        ).pack(side='right')

    def add_intro_files(self):
        """Add one or more intro videos or GIFs."""
        intro_dir = self.get_intro_dir()
        self._copy_selected_files(
            "Add intro video or GIF (MP4, AVI, MOV, MKV, WEBM, M4V, GIF)",
            intro_dir,
            (("Intro media", "*.mp4 *.avi *.mov *.mkv *.webm *.m4v *.gif"), ("All files", "*.*")),
            self.refresh_intro_list,
        )

    def get_input_video_paths(self):
        """Return input videos for the custom ordering dialog."""
        folder = self.input_path_var.get().strip()
        if not folder or not os.path.isdir(folder):
            return []
        files = []
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and name.lower().endswith(self.VIDEO_EXTENSIONS):
                files.append(path)
        files.sort(key=os.path.getmtime, reverse=True)
        return files

    def get_clip_timeframe_seconds(self):
        """Return the selected recency window in seconds, or None when unlimited."""
        return {
            '1_day': 24 * 60 * 60,
            '1_week': 7 * 24 * 60 * 60,
            '2_weeks': 14 * 24 * 60 * 60,
            '1_month': 30 * 24 * 60 * 60,
            'all': None,
        }.get(self.clip_timeframe_var.get(), 7 * 24 * 60 * 60)

    def get_clip_timeframe_label(self):
        """Return the current recency-bubble label."""
        for label, value in self.CLIP_TIMEFRAME_OPTIONS:
            if value == self.clip_timeframe_var.get():
                return label
        return '1 week'

    def filter_video_paths_by_timeframe(self, files):
        """Filter video paths to the active recency window."""
        cutoff_seconds = self.get_clip_timeframe_seconds()
        if cutoff_seconds is None:
            return list(files)
        cutoff = time.time() - cutoff_seconds
        filtered = []
        for path in files:
            try:
                if os.path.getmtime(path) >= cutoff:
                    filtered.append(path)
            except OSError:
                continue
        return filtered

    def load_clip_selection_snapshot(self):
        """Load the saved clip-selection snapshot that drives compilation."""
        if not os.path.exists(self.custom_order_file):
            return {}
        try:
            with open(self.custom_order_file, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            if isinstance(data, dict):
                clip_settings = data.get('clip_settings', {})
                if isinstance(clip_settings, dict):
                    loaded_overrides = {}
                    for path, settings in clip_settings.items():
                        if isinstance(settings, dict):
                            trim_seconds = settings.get('trim_seconds')
                        else:
                            trim_seconds = settings
                        try:
                            trim_value = int(float(str(trim_seconds)))
                        except (TypeError, ValueError):
                            continue
                        if trim_value > 0:
                            loaded_overrides[self.normalize_clip_path(path)] = trim_value
                    self.clip_trim_overrides = loaded_overrides
            if isinstance(data, list):
                return {'paths': data}
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"Error loading clip selection snapshot: {e}")
        return {}

    def normalize_clip_path(self, video_path):
        """Return a normalized absolute path for clip lookup."""
        return os.path.normcase(os.path.abspath(video_path))

    def get_default_clip_trim_seconds(self):
        """Return the global trim seconds setting, or None when using the full clip."""
        value = str(self.trim_seconds_var.get() or '').strip()
        if not value or value == 'None':
            return None
        try:
            parsed = int(float(value))
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def get_clip_trim_seconds(self, video_path):
        """Return the effective trim seconds for a clip, including any per-clip override."""
        normalized = self.normalize_clip_path(video_path)
        if normalized in self.clip_trim_overrides:
            return self.clip_trim_overrides[normalized]
        return self.get_default_clip_trim_seconds()

    def get_clip_trim_badge_text(self, video_path):
        """Return the seconds badge shown on each clip card."""
        trim_seconds = self.get_clip_trim_seconds(video_path)
        return f"{trim_seconds}s" if trim_seconds is not None else 'Full'

    def get_clip_trim_input_value(self, video_path):
        """Return the inline card value shown in the per-clip trim box."""
        trim_seconds = self.get_clip_trim_seconds(video_path)
        return 'Full' if trim_seconds is None else str(int(trim_seconds))

    def clear_clip_trim_inputs(self):
        """Destroy any inline trim controls before redrawing the clip canvas."""
        for widget in self.clip_trim_inputs.values():
            try:
                widget.destroy()
            except Exception:
                pass
        self.clip_trim_inputs = {}

    def commit_inline_clip_trim(self, video_path, trim_var):
        """Persist the per-clip trim box value from the card itself."""
        previous_trim = self.get_clip_trim_seconds(video_path)
        default_trim = self.get_default_clip_trim_seconds()
        raw_value = str(trim_var.get() or '').strip()

        if not raw_value:
            self.set_clip_trim_override(video_path, None)
        else:
            lowered = raw_value.lower()
            if lowered in {'default', 'full', 'none'}:
                self.set_clip_trim_override(video_path, None)
            else:
                try:
                    trim_seconds = int(float(raw_value))
                except (TypeError, ValueError):
                    trim_var.set(self.get_clip_trim_input_value(video_path))
                    messagebox.showerror("Invalid Seconds", "Enter a whole number of seconds for this clip.")
                    return 'break'
                if trim_seconds <= 0:
                    trim_var.set(self.get_clip_trim_input_value(video_path))
                    messagebox.showerror("Invalid Seconds", "Clip seconds must be greater than zero.")
                    return 'break'
                if default_trim is not None and trim_seconds == default_trim:
                    self.set_clip_trim_override(video_path, None)
                else:
                    self.set_clip_trim_override(video_path, trim_seconds)

        trim_var.set(self.get_clip_trim_input_value(video_path))
        self.persist_clip_selection_snapshot(log_message=False)

        current_trim = self.get_clip_trim_seconds(video_path)
        if current_trim != previous_trim:
            clip_name = os.path.basename(video_path)
            if self.normalize_clip_path(video_path) in self.clip_trim_overrides:
                self.log_status(f"[CLIPS] Set {clip_name} to {self.get_clip_trim_badge_text(video_path)}")
            else:
                default_label = self.get_clip_trim_badge_text(video_path)
                self.log_status(f"[CLIPS] Reset {clip_name} to the default {default_label}")
        return 'break'

    def reset_inline_clip_trim_value(self, video_path, trim_var):
        """Restore the visible inline trim box text without changing saved state."""
        trim_var.set(self.get_clip_trim_input_value(video_path))
        return 'break'

    def set_clip_trim_override(self, video_path, trim_seconds=None):
        """Apply or clear a per-clip trim override."""
        normalized = self.normalize_clip_path(video_path)
        if trim_seconds is None:
            self.clip_trim_overrides.pop(normalized, None)
            return
        self.clip_trim_overrides[normalized] = int(trim_seconds)

    def sort_clip_selection_paths(self, files, order_mode=None):
        """Sort clip paths according to the current clip-order selection."""
        order_mode = (order_mode or self.clip_order_var.get() or 'newest_first').lower()
        items = list(files)
        if order_mode == 'oldest_first':
            items.sort(key=os.path.getmtime)
        elif order_mode == 'filename_az':
            items.sort(key=lambda path: os.path.basename(path).lower())
        elif order_mode == 'filename_za':
            items.sort(key=lambda path: os.path.basename(path).lower(), reverse=True)
        elif order_mode != 'custom':
            items.sort(key=os.path.getmtime, reverse=True)
        return items

    def build_clip_selection_files(self, preserve_saved=True):
        """Build the visible clip list so the UI and compiler stay in sync."""
        filtered_files = self.filter_video_paths_by_timeframe(self.get_input_video_paths())
        if not preserve_saved:
            return self.sort_clip_selection_paths(filtered_files)

        snapshot = self.load_clip_selection_snapshot()
        if 'paths' not in snapshot:
            return self.sort_clip_selection_paths(filtered_files)

        current_folder = self.input_path_var.get().strip()
        normalized_folder = os.path.normcase(os.path.abspath(current_folder)) if current_folder else ''
        snapshot_folder = str(snapshot.get('source_folder', '') or '')
        snapshot_timeframe = str(snapshot.get('timeframe', '') or '')

        if snapshot_folder:
            normalized_snapshot_folder = os.path.normcase(os.path.abspath(snapshot_folder))
            if normalized_snapshot_folder != normalized_folder:
                return self.sort_clip_selection_paths(filtered_files)
        if snapshot_timeframe and snapshot_timeframe != self.clip_timeframe_var.get():
            return self.sort_clip_selection_paths(filtered_files)

        available_map = {
            os.path.normcase(os.path.abspath(path)): path
            for path in filtered_files
        }
        saved_paths = []
        for path in snapshot.get('paths', []):
            normalized = os.path.normcase(os.path.abspath(path))
            if normalized in available_map:
                saved_paths.append(available_map[normalized])

        if saved_paths or not snapshot.get('paths'):
            if self.clip_order_var.get() == 'custom':
                return saved_paths
            return self.sort_clip_selection_paths(saved_paths)

        return self.sort_clip_selection_paths(filtered_files)

    def persist_clip_selection_snapshot(self, log_message=False):
        """Persist the visible clip list so compilation matches the GUI."""
        if not hasattr(self, 'clip_selection_files'):
            return
        os.makedirs(os.path.dirname(self.custom_order_file), exist_ok=True)
        clip_settings = {
            path: {'trim_seconds': self.clip_trim_overrides[self.normalize_clip_path(path)]}
            for path in self.clip_selection_files
            if self.normalize_clip_path(path) in self.clip_trim_overrides
        }
        payload = {
            'paths': list(self.clip_selection_files),
            'saved_at': int(time.time()),
            'source_folder': self.input_path_var.get().strip(),
            'timeframe': self.clip_timeframe_var.get(),
            'clip_order': self.clip_order_var.get(),
            'clip_settings': clip_settings,
        }
        try:
            with open(self.custom_order_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
            self.save_config()
            all_files = self.get_input_video_paths()
            filtered_count = len(self.filter_video_paths_by_timeframe(all_files))
            total_count = len(all_files)
            summary = f"{len(self.clip_selection_files)} selected | {filtered_count} in {self.get_clip_timeframe_label()}"
            if total_count != filtered_count:
                summary += f" | {total_count} total"
            summary += f" | {self.clip_order_var.get()}"
            self.clip_selection_summary_var.set(summary)
            self.update_paths_display()
            if log_message:
                self.log_success(f"Saved {len(self.clip_selection_files)} selected clips")
        except Exception as e:
            self.log_error(f"Could not save clip selection: {e}")

    def refresh_clip_selection_panel(self, preserve_saved=True, save_snapshot=True):
        """Refresh the embedded clip-selection panel."""
        all_files = self.get_input_video_paths()
        filtered_files = self.filter_video_paths_by_timeframe(all_files)
        self.clip_selection_files = self.build_clip_selection_files(preserve_saved=preserve_saved)

        if self.clip_selection_files:
            self.clip_selected_index = max(0, min(self.clip_selected_index, len(self.clip_selection_files) - 1))
        else:
            self.clip_selected_index = 0
            self.clip_drag_index = None

        selection_count = len(self.clip_selection_files)
        filtered_count = len(filtered_files)
        total_count = len(all_files)
        summary = f"{selection_count} selected | {filtered_count} in {self.get_clip_timeframe_label()}"
        if total_count != filtered_count:
            summary += f" | {total_count} total"
        summary += f" | {self.clip_order_var.get()}"
        self.clip_selection_summary_var.set(summary)

        if hasattr(self, 'clip_show_all_link'):
            if filtered_count > 0 and selection_count < filtered_count:
                self.clip_show_all_link.pack(side='right', padx=(8, 0))
            else:
                self.clip_show_all_link.pack_forget()

        self.draw_clip_selection_rows()
        if save_snapshot:
            self.persist_clip_selection_snapshot(log_message=False)

    def on_clip_timeframe_changed(self):
        """Refresh the clip-selection list when the recency bubble changes."""
        self.save_config()
        self.refresh_clip_selection_panel(preserve_saved=False)

    def on_clip_order_changed(self, _event=None):
        """Persist clip-order selection and refresh the embedded clip-selection panel."""
        self.save_config()
        self.refresh_clip_selection_panel(preserve_saved=True)

    def on_trim_seconds_changed(self, _event=None):
        """Refresh card badges when the global trim duration changes."""
        self.save_config()
        self.draw_clip_selection_rows()
        self.persist_clip_selection_snapshot(log_message=False)

    def set_progress(self, percent, message):
        """Thread-safe progress update."""
        def update():
            clamped = max(0, min(100, float(percent)))
            self.progress_var.set(clamped)
            self.progress_text_var.set(f"{clamped:.0f}% - {message}")
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, update)
        else:
            update()

    def request_stop(self):
        """Request cancellation of the active compilation."""
        self.stop_requested = True
        self.log_warning("Stop requested. The current FFmpeg step will be cancelled as soon as possible.")
        self.set_progress(self.progress_var.get(), "Stopping...")
        if hasattr(self, 'stop_btn'):
            self.stop_btn.configure(state='disabled')

    def create_video_thumbnail(self, video_path, size=(160, 90)):
        """Create or load a thumbnail image for a video."""
        cache_key = hashlib.sha256(f"{video_path}|{os.path.getmtime(video_path)}".encode("utf-8", errors="ignore")).hexdigest()
        thumb_path = os.path.join(self.get_thumbnail_dir(), f"{cache_key}.jpg")
        if not os.path.exists(thumb_path):
            ffmpeg_path = self.get_ffmpeg_path()
            if ffmpeg_path:
                try:
                    subprocess.run(
                        [
                            ffmpeg_path,
                            "-y",
                            "-ss",
                            "00:00:01",
                            "-i",
                            video_path,
                            "-frames:v",
                            "1",
                            "-vf",
                            f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
                            thumb_path,
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                    )
                except Exception:
                    pass
        try:
            if os.path.exists(thumb_path):
                img = Image.open(thumb_path).convert("RGB").resize(size, Image.Resampling.LANCZOS)
            else:
                raise FileNotFoundError
        except Exception:
            img = Image.new("RGB", size, "#1b2632")
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline="#2E8B57", width=2)
            draw.polygon(
                [(size[0] // 2 - 12, size[1] // 2 - 18), (size[0] // 2 - 12, size[1] // 2 + 18), (size[0] // 2 + 18, size[1] // 2)],
                fill="#64ffda",
            )
        return ImageTk.PhotoImage(img)

    def truncate_text_end(self, text, max_length):
        """Truncate text from the end with an ellipsis."""
        if len(text) <= max_length:
            return text
        return text[:max(0, max_length - 3)].rstrip('-_ ') + "..."

    def truncate_text_start(self, text, max_length):
        """Truncate text from the beginning with an ellipsis."""
        if len(text) <= max_length:
            return text
        return "..." + text[-max(0, max_length - 3):]

    def format_clip_display_name(self, video_path, max_length=44):
        """Format clip names for dense card display."""
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        known_prefix = "recording-Ultima_Online_Retail-"
        if base_name.startswith(known_prefix):
            return self.truncate_text_end(base_name[len(known_prefix):], max_length)
        return self.truncate_text_start(base_name, max_length)

    def format_clip_time_label(self, video_path):
        """Format the clip timestamp shown under each card."""
        return time.strftime("%m/%d/%y %I:%M %p", time.localtime(os.path.getmtime(video_path)))

    def preview_custom_order_video(self, video_path):
        """Preview a clip in an always-on-top window centered over the GUI."""
        self.stop_preview()
        ffplay_path = self.get_ffplay_path()
        if ffplay_path:
            try:
                self.root.update_idletasks()
                preview_width = max(720, min(1280, int(self.root.winfo_width() * 0.72)))
                preview_height = max(405, int(preview_width * 9 / 16))
                left = self.root.winfo_x() + max(20, (self.root.winfo_width() - preview_width) // 2)
                top = self.root.winfo_y() + max(20, (self.root.winfo_height() - preview_height) // 2)
                self.preview_process = subprocess.Popen(
                    [
                        ffplay_path,
                        "-autoexit",
                        "-alwaysontop",
                        "-window_title",
                        os.path.basename(video_path),
                        "-left",
                        str(left),
                        "-top",
                        str(top),
                        "-x",
                        str(preview_width),
                        "-y",
                        str(preview_height),
                        video_path,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception:
                pass
        try:
            os.startfile(video_path)
        except Exception as e:
            messagebox.showerror("Preview Error", f"Could not preview video:\n{e}")

    def stop_preview(self):
        """Stop the current preview process if ffplay is running."""
        if self.preview_process and self.preview_process.poll() is None:
            try:
                self.preview_process.terminate()
            except Exception:
                pass
        self.preview_process = None

    def show_custom_order_window(self):
        """Focus the embedded clip-selection panel instead of opening a separate window."""
        if not self.get_input_video_paths():
            messagebox.showwarning("Clip Selection", "Select an input folder with supported video files first.")
            return
        self.refresh_clip_selection_panel(preserve_saved=True, save_snapshot=False)
        if self.clip_selection_canvas:
            self.clip_selection_canvas.focus_set()
            if self.clip_selection_files:
                position = self.clip_selected_index / max(1, len(self.clip_selection_files))
                self.clip_selection_canvas.yview_moveto(position)

    def show_clip_preview_window(self, index=None):
        """Open a centered clip preview/editor window for per-clip trim overrides."""
        if not self.clip_selection_files:
            return
        if index is None:
            index = self.clip_selected_index
        index = max(0, min(len(self.clip_selection_files) - 1, index))
        self.clip_selected_index = index
        video_path = self.clip_selection_files[index]

        if self.clip_preview_window and self.clip_preview_window.winfo_exists():
            try:
                self.clip_preview_window.destroy()
            except Exception:
                pass

        window = tk.Toplevel(self.root)
        self.clip_preview_window = window
        window.title("Clip Preview")
        window.configure(bg=self.colors['bg'])
        self.position_child_window(window, width=520, height=350, modal=True)
        try:
            window.iconbitmap(self.get_icon_path())
        except Exception:
            pass

        current_trim = self.get_clip_trim_seconds(video_path)
        default_trim = self.get_default_clip_trim_seconds()
        trim_var = tk.StringVar(value="" if current_trim is None else str(current_trim))

        outer = tk.Frame(window, bg=self.colors['bg'], padx=14, pady=14)
        outer.pack(fill='both', expand=True)

        preview_thumb = self.create_video_thumbnail(video_path, size=(320, 180))
        thumb_label = tk.Label(outer, image=preview_thumb, bg=self.colors['bg'])
        self.clip_preview_thumb = preview_thumb
        thumb_label.pack(pady=(0, 10))

        tk.Label(
            outer,
            text=self.format_clip_display_name(video_path, max_length=72),
            bg=self.colors['bg'],
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            wraplength=460,
            justify='center',
        ).pack()

        tk.Label(
            outer,
            text=f"Recorded {self.format_clip_time_label(video_path)} | Current clip length {self.get_clip_trim_badge_text(video_path)}",
            bg=self.colors['bg'],
            fg='#c6d0dc',
            font=('Segoe UI', 8),
        ).pack(pady=(4, 10))

        trim_row = tk.Frame(outer, bg=self.colors['bg'])
        trim_row.pack(fill='x', pady=(0, 10))

        tk.Label(
            trim_row,
            text="Seconds for this clip:",
            bg=self.colors['bg'],
            fg='white',
            font=('Segoe UI', 9, 'bold'),
        ).pack(side='left')

        trim_entry = tk.Spinbox(trim_row, from_=1, to=300, increment=1, textvariable=trim_var, width=8)
        trim_entry.pack(side='left', padx=(8, 8))

        tk.Label(
            trim_row,
            text=f"Default {default_trim}s" if default_trim is not None else "Default Full",
            bg=self.colors['bg'],
            fg='#c6d0dc',
            font=('Segoe UI', 8),
        ).pack(side='left')

        button_row = tk.Frame(outer, bg=self.colors['bg'])
        button_row.pack(fill='x')

        def apply_trim():
            raw_value = str(trim_var.get() or '').strip()
            if not raw_value:
                self.set_clip_trim_override(video_path, None)
            else:
                try:
                    trim_seconds = int(float(raw_value))
                except ValueError:
                    messagebox.showerror("Invalid Seconds", "Enter a whole number of seconds for this clip.")
                    return
                if trim_seconds <= 0:
                    messagebox.showerror("Invalid Seconds", "Clip seconds must be greater than zero.")
                    return
                self.set_clip_trim_override(video_path, trim_seconds)
            self.persist_clip_selection_snapshot(log_message=False)
            self.draw_clip_selection_rows()
            self.log_success(f"Updated clip length for {os.path.basename(video_path)}")

        def reset_trim():
            trim_var.set('')
            self.set_clip_trim_override(video_path, None)
            self.persist_clip_selection_snapshot(log_message=False)
            self.draw_clip_selection_rows()
            self.log_status(f"[CLIPS] Reset clip length for {os.path.basename(video_path)} to the default setting")

        def close_window():
            self.stop_preview()
            self.clip_preview_window = None
            window.destroy()

        tk.Button(
            button_row,
            text="Play Over GUI",
            command=lambda: self.preview_custom_order_video(video_path),
            font=('Segoe UI', 8, 'bold'),
            bg=self.colors['accent'],
            fg='white',
            relief='raised',
            cursor='hand2',
            padx=10,
            pady=4,
        ).pack(side='left')

        tk.Button(
            button_row,
            text="Apply Seconds",
            command=apply_trim,
            font=('Segoe UI', 8),
            bg=self.colors['button'],
            fg='white',
            relief='raised',
            cursor='hand2',
            padx=10,
            pady=4,
        ).pack(side='left', padx=(8, 0))

        tk.Button(
            button_row,
            text="Use Default",
            command=reset_trim,
            font=('Segoe UI', 8),
            bg='#666666',
            fg='white',
            relief='raised',
            cursor='hand2',
            padx=10,
            pady=4,
        ).pack(side='left', padx=(8, 0))

        tk.Button(
            button_row,
            text="Close",
            command=close_window,
            font=('Segoe UI', 8),
            bg='#444444',
            fg='white',
            relief='raised',
            cursor='hand2',
            padx=10,
            pady=4,
        ).pack(side='right')

        tk.Label(
            outer,
            text="Preview opens centered over the main GUI. Use ffplay controls for seek/fullscreen.",
            bg=self.colors['bg'],
            fg='#8ea3b8',
            font=('Segoe UI', 8),
        ).pack(pady=(10, 0))

        window.protocol("WM_DELETE_WINDOW", close_window)
        self.preview_custom_order_video(video_path)

    def draw_clip_selection_rows(self):
        """Render the embedded clip-selection cards with a width-responsive multi-column layout."""
        canvas = self.clip_selection_canvas
        if not canvas:
            return
        self.clear_clip_trim_inputs()
        canvas.delete("all")
        self.clip_card_regions = []
        canvas_width = max(canvas.winfo_width(), 980)
        gutter_x = 12
        gutter_y = 12
        outer_pad = 12
        target_card_width = 200
        columns = max(1, min(6, int((canvas_width - (outer_pad * 2) + gutter_x) // (target_card_width + gutter_x))))
        self.clip_cards_per_row = columns
        cell_width = max(180, (canvas_width - (outer_pad * 2) - (gutter_x * (columns - 1))) // columns)
        thumb_width = min(190, max(130, cell_width - 24))
        thumb_height = int(thumb_width * 9 / 16)
        card_height = thumb_height + 60
        self.clip_row_height = card_height + gutter_y

        if not self.clip_selection_files:
            canvas.create_text(
                canvas_width // 2,
                90,
                text="No videos match the current timeframe. Choose a wider bubble or a different folder.",
                fill="#cdd6e3",
                font=('Segoe UI', 11, 'bold'),
            )
            canvas.configure(scrollregion=(0, 0, canvas_width, 180))
            return

        for index, path in enumerate(self.clip_selection_files):
            row = index // columns
            column = index % columns
            x0 = outer_pad + column * (cell_width + gutter_x)
            y0 = outer_pad + row * (card_height + gutter_y)
            x1 = x0 + cell_width
            y1 = y0 + card_height
            row_tag = f"clip_row_{index}"
            remove_tag = f"clip_remove_{index}"
            fill = "#23483d" if index == self.clip_selected_index else "#2b3138"
            outline = "#64ffda" if index == self.clip_selected_index else "#3d4854"

            thumb_key = f"{path}|{int(os.path.getmtime(path))}|{thumb_width}x{thumb_height}"
            if thumb_key not in self.clip_thumbnail_cache:
                self.clip_thumbnail_cache[thumb_key] = self.create_video_thumbnail(path, size=(thumb_width, thumb_height))

            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=2, tags=(row_tag,))
            thumb_x = x0 + (cell_width - thumb_width) // 2
            thumb_y = y0 + 10
            canvas.create_image(thumb_x, thumb_y, image=self.clip_thumbnail_cache[thumb_key], anchor='nw', tags=(row_tag,))

            badge_x1 = x0 + 10
            badge_y1 = y0 + 10
            badge_x2 = badge_x1 + 28
            badge_y2 = badge_y1 + 22
            canvas.create_rectangle(badge_x1, badge_y1, badge_x2, badge_y2, fill="#16242d", outline="#64ffda", width=1, tags=(row_tag,))
            canvas.create_text((badge_x1 + badge_x2) // 2, (badge_y1 + badge_y2) // 2, text=str(index + 1), fill="#ffffff", font=('Segoe UI', 8, 'bold'), tags=(row_tag,))

            remove_x1 = x1 - 82
            remove_x2 = x1 - 10
            remove_y1 = y0 + 10
            remove_y2 = remove_y1 + 22
            canvas.create_rectangle(remove_x1, remove_y1, remove_x2, remove_y2, fill=self.colors['error'], outline='#ff9e9e', width=1, tags=(remove_tag,))
            canvas.create_text((remove_x1 + remove_x2) // 2, (remove_y1 + remove_y2) // 2, text="Remove", fill="white", font=('Segoe UI', 8, 'bold'), tags=(remove_tag,))

            canvas.create_text(
                (x0 + x1) // 2,
                thumb_y + thumb_height + 10,
                text=self.format_clip_display_name(path, max_length=max(18, min(34, int(cell_width / 7)))),
                anchor='n',
                fill="#ffffff",
                font=('Segoe UI', 8, 'bold'),
                width=cell_width - 18,
                justify='center',
                tags=(row_tag,),
            )
            canvas.create_text(
                x0 + 10,
                y1 - 12,
                text=self.format_clip_time_label(path),
                anchor='sw',
                fill="#c6d0dc",
                font=('Segoe UI', 7),
                width=max(60, cell_width - 84),
                justify='left',
                tags=(row_tag,),
            )

            trim_var = tk.StringVar(master=self.root, value=self.get_clip_trim_input_value(path))
            trim_entry = tk.Entry(
                canvas,
                textvariable=trim_var,
                width=5,
                justify='center',
                font=('Segoe UI', 7, 'bold'),
                bg="#163342",
                fg="white",
                insertbackground="white",
                relief='solid',
                bd=1,
                highlightthickness=1,
                highlightbackground="#74d9ff",
                highlightcolor="#64ffda",
            )
            trim_entry.bind('<Return>', lambda _event, clip_path=path, var=trim_var: self.commit_inline_clip_trim(clip_path, var))
            trim_entry.bind('<FocusOut>', lambda _event, clip_path=path, var=trim_var: self.commit_inline_clip_trim(clip_path, var))
            trim_entry.bind('<Escape>', lambda _event, clip_path=path, var=trim_var: self.reset_inline_clip_trim_value(clip_path, var))
            canvas.create_window(x1 - 10, y1 - 8, window=trim_entry, anchor='se')
            self.clip_trim_inputs[index] = trim_entry

            self.clip_card_regions.append((index, x0, y0, x1, y1))

            canvas.tag_bind(row_tag, '<ButtonPress-1>', lambda _event, idx=index: self.start_clip_drag(idx))
            canvas.tag_bind(row_tag, '<Double-Button-1>', lambda _event, idx=index: self.preview_selected_clip(idx))
            canvas.tag_bind(remove_tag, '<ButtonPress-1>', lambda _event, idx=index: self.remove_clip_at_index(idx))

        total_rows = (len(self.clip_selection_files) + columns - 1) // columns
        content_height = max(card_height + (outer_pad * 2), outer_pad + total_rows * (card_height + gutter_y))
        canvas.configure(scrollregion=(0, 0, canvas_width, content_height))

    def clip_index_from_event(self, event):
        """Translate a mouse event to the corresponding clip row index."""
        canvas = self.clip_selection_canvas
        if canvas is None or not self.clip_selection_files:
            return 0
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        for index, x0, y0, x1, y1 in self.clip_card_regions:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return index
        closest = min(
            self.clip_card_regions,
            key=lambda region: abs(((region[1] + region[3]) / 2) - x) + abs(((region[2] + region[4]) / 2) - y),
        )
        return closest[0]

    def start_clip_drag(self, index):
        """Select a clip row and prepare it for drag-reordering."""
        if not self.clip_selection_files:
            return
        self.clip_selected_index = index
        self.clip_drag_index = index
        self.clip_drag_changed = False
        if self.clip_selection_canvas:
            self.clip_selection_canvas.configure(cursor='fleur')
        self.draw_clip_selection_rows()

    def on_clip_drag_motion(self, event):
        """Reorder clip rows while dragging."""
        if self.clip_drag_index is None or not self.clip_selection_files:
            return
        target = self.clip_index_from_event(event)
        current = self.clip_drag_index
        if target != current:
            item = self.clip_selection_files.pop(current)
            self.clip_selection_files.insert(target, item)
            self.clip_drag_index = target
            self.clip_selected_index = target
            self.clip_drag_changed = True
            self.draw_clip_selection_rows()

    def on_clip_drag_end(self, _event=None):
        """Finish a drag operation and persist the new clip order."""
        if self.clip_drag_index is None:
            return
        self.clip_drag_index = None
        if self.clip_selection_canvas:
            self.clip_selection_canvas.configure(cursor='hand2')
        if self.clip_drag_changed:
            self.clip_order_var.set('custom')
            self.persist_clip_selection_snapshot(log_message=False)
        self.draw_clip_selection_rows()

    def preview_selected_clip(self, index=None):
        """Open the selected clip's centered preview/editor window."""
        if not self.clip_selection_files:
            return
        if index is None:
            index = self.clip_selected_index
        index = max(0, min(len(self.clip_selection_files) - 1, index))
        self.clip_selected_index = index
        self.draw_clip_selection_rows()
        self.show_clip_preview_window(index)

    def remove_clip_at_index(self, index, log_message=True):
        """Remove a clip from the active selection without deleting the source file."""
        if index < 0 or index >= len(self.clip_selection_files):
            return
        removed = self.clip_selection_files.pop(index)
        if self.clip_selection_files:
            self.clip_selected_index = max(0, min(index, len(self.clip_selection_files) - 1))
        else:
            self.clip_selected_index = 0
        self.persist_clip_selection_snapshot(log_message=False)
        self.draw_clip_selection_rows()
        if log_message:
            self.log_warning(f"Removed {os.path.basename(removed)} from this compilation selection")

    def remove_selected_clip(self):
        """Remove the currently highlighted clip from the active selection."""
        self.remove_clip_at_index(self.clip_selected_index)
    
    def run_compiler(self):
        """Run the video compiler with current settings"""
        print("DEBUG: run_compiler() called - ENTRY POINT")
        
        # Validate paths
        input_path = self.input_path_var.get().strip()
        output_path = self.output_path_var.get().strip()
        
        if not input_path or not output_path:
            print("DEBUG: Path validation failed - missing paths")
            self.log_error("Both input and output paths must be set!")
            messagebox.showerror("Configuration Error", "Please set both input and output paths before running the compiler!")
            return
            
        if not os.path.exists(input_path):
            print(f"DEBUG: Input path validation failed: {input_path}")
            self.log_error(f"Input path does not exist: {input_path}")
            messagebox.showerror("Path Error", f"Input path does not exist:\n{input_path}")
            return
            
        # Create output directory if it doesn't exist
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path)
                self.log_success(f"Created output directory: {output_path}")
            except Exception as e:
                self.log_error(f"Could not create output directory: {e}")
                messagebox.showerror("Directory Error", f"Could not create output directory:\n{e}")
                return

        video_candidates = [
            name for name in os.listdir(input_path)
            if os.path.isfile(os.path.join(input_path, name)) and name.lower().endswith(self.VIDEO_EXTENSIONS)
        ]
        if not video_candidates:
            self.log_error("No supported video files were found in the input folder.")
            messagebox.showerror(
                "No Videos Found",
                "The input folder does not contain any supported videos.\n\n"
                f"Supported formats: {', '.join(self.VIDEO_EXTENSIONS)}"
            )
            return

        self.refresh_clip_selection_panel(preserve_saved=True)
        if not self.clip_selection_files:
            self.log_error("No videos are selected for the current timeframe/clip selection.")
            messagebox.showerror(
                "No Selected Videos",
                "The current clip selection is empty.\n\n"
                "Widen the timeframe bubble or use Show all in timeframe before running the compiler."
            )
            return
        self.persist_clip_selection_snapshot(log_message=False)

        if not self.ensure_compile_entitlement():
            return
        
        # FIXED: Clear status area BEFORE any operations that might log messages
        print("DEBUG: Clearing status text area BEFORE script path update")
        if self.status_text is not None:
            self.status_text.delete(1.0, tk.END)
        print("DEBUG: Status text cleared")
        self.stop_requested = False
        self.set_progress(0, "Starting")
        
        # Update the main script with these paths
        self.update_main_script_paths(input_path, output_path)
        
        # Reset and disable run button for new compilation
        self.run_btn.configure(state='disabled', text="Compiling... Please Wait", bg=self.colors['warning'])
        self.stop_btn.grid()
        self.stop_btn.configure(state='normal')
        self.root.update_idletasks()  # Force immediate GUI update to show button change
        
        self.log_status("[START] Starting video compilation process...")
        self.log_status(f"[INPUT] Input folder: {input_path}")
        self.log_status(f"[OUTPUT] Output folder: {output_path}")
        self.log_status("")
        
        # Run in separate thread to avoid GUI freezing
        threading.Thread(target=self.run_compiler_thread, daemon=True).start()
        
    def update_main_script_paths(self, input_path, output_path):
        """Update the main UOVidCompiler.py script with the selected paths (skip if running from executable)"""
        
        # Check if running from PyInstaller executable
        if getattr(sys, 'frozen', False):
            # Running from executable - skip file modification
            self.log_status("Running from executable - paths will be passed via environment variables")
            return
        
        script_path = os.path.join(os.path.dirname(__file__), "UOVidCompiler.py")
        
        try:
            # Check if file exists and is writable
            if not os.path.exists(script_path):
                self.log_status("Script file not found - paths will be passed via environment variables")
                return
                
            if not os.access(script_path, os.W_OK):
                self.log_status("Script file is read-only - paths will be passed via environment variables")
                return
            
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update the paths in the configuration section
            # Look for the path configuration lines
            import re
            
            # Update input path
            content = re.sub(
                r'VIDEO_INPUT_PATH\s*=\s*r?"[^"]*"',
                f'VIDEO_INPUT_PATH = r"{input_path}"',
                content
            )
            
            # Update output path  
            content = re.sub(
                r'VIDEO_OUTPUT_PATH\s*=\s*r?"[^"]*"',
                f'VIDEO_OUTPUT_PATH = r"{output_path}"',
                content
            )
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.log_status("Updated script paths successfully")
            
        except Exception as e:
            self.log_status(f"Could not update script paths (will use environment variables): {e}")
    
    def run_compiler_thread(self):
        """Run the compiler in a separate thread with real-time output display"""
        
        # Test log_status from background thread
        self.log_status("[START] Background compilation thread started")
        success = False
        cancelled = False

        try:
            # Set up environment variables for the compilation
            os.environ['GUI_MODE'] = '1'  # Prevent waiting for input
            os.environ['VIDEO_INPUT_PATH'] = self.input_path_var.get()
            os.environ['VIDEO_OUTPUT_PATH'] = self.output_path_var.get()
            os.environ['TRIM_SECONDS'] = self.trim_seconds_var.get()
            os.environ['MUSIC_SELECTION'] = self.music_selection_var.get()
            os.environ['INTRO_SELECTION'] = self.intro_selection_for_compiler()
            os.environ['CLIP_ORDER'] = self.clip_order_var.get()
            os.environ['CUSTOM_ORDER_FILE'] = self.custom_order_file
            os.environ['CLIP_TIMEFRAME'] = self.clip_timeframe_var.get()
            os.environ['MUSIC_FOLDER'] = self.get_music_dir()
            os.environ['INTRO_FOLDER'] = self.get_intro_dir()
            os.environ['AUTOVID_LOG_DIR'] = self.get_logs_dir()
            os.environ['AUTOVID_LOG_LEVEL'] = 'DEBUG'
            
            # Log the settings being used
            self.log_status(f"[CONFIG] Trim seconds: {self.trim_seconds_var.get()}")
            self.log_status(f"[CONFIG] Music selection: {self.music_selection_var.get()}")
            self.log_status(f"[CONFIG] Intro selection: {self.intro_selection_for_compiler()}")
            self.log_status(f"[CONFIG] Clip order: {self.clip_order_var.get()}")
            self.log_status(f"[CONFIG] Clip timeframe: {self.get_clip_timeframe_label()}")
            
            self.log_status("[PROCESS] Starting direct compilation...")
            
            if DIRECT_COMPILATION and hasattr(UOVidCompiler, 'main'):
                # Run compilation directly with live output capture
                self.log_status("[OK] Running compilation directly in same process...")
                compiler_gui_handler = None
                compiler_logger = None
                
                # CRITICAL: Update the CONFIG dictionary directly since module is already imported
                if hasattr(UOVidCompiler, 'CONFIG'):
                    trim_selection = self.trim_seconds_var.get()
                    trim_value = None if trim_selection == 'None' else int(trim_selection)
                    UOVidCompiler.CONFIG['intro_selection'] = self.intro_selection_for_compiler()
                    UOVidCompiler.CONFIG['music_selection'] = self.music_selection_var.get()
                    UOVidCompiler.CONFIG['trim_seconds'] = trim_value
                    UOVidCompiler.CONFIG['clip_duration'] = float(trim_value) if trim_value is not None else 999999.0
                    UOVidCompiler.CONFIG['video_folder'] = self.input_path_var.get()
                    UOVidCompiler.CONFIG['output_folder'] = self.output_path_var.get()
                    UOVidCompiler.CONFIG['clip_order'] = self.clip_order_var.get()
                    UOVidCompiler.CONFIG['custom_order_file'] = self.custom_order_file
                    UOVidCompiler.CONFIG['clip_timeframe'] = self.clip_timeframe_var.get()
                    UOVidCompiler.CONFIG['music_folder'] = self.get_music_dir()
                    UOVidCompiler.CONFIG['intro_folder'] = self.get_intro_dir()
                    UOVidCompiler.CONFIG['use_intro'] = self.intro_selection_for_compiler() != 'None'
                    UOVidCompiler.CONFIG['progress_callback'] = self.set_progress
                    UOVidCompiler.CONFIG['cancel_callback'] = lambda: self.stop_requested
                    self.log_status("[OK] CONFIG dictionary updated with GUI selections")

                if hasattr(UOVidCompiler, 'configure_logging'):
                    UOVidCompiler.configure_logging(log_dir=self.get_logs_dir(), log_level='DEBUG')

                compiler_logger = getattr(UOVidCompiler, 'logger', None)
                if isinstance(compiler_logger, logging.Logger):
                    compiler_gui_handler = CompilerGuiLogHandler(self)
                    compiler_gui_handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
                    compiler_logger.addHandler(compiler_gui_handler)

                if hasattr(UOVidCompiler, 'get_log_file_path'):
                    compiler_log_path = UOVidCompiler.get_log_file_path()
                    if compiler_log_path:
                        self.log_status(f"[LOG] Compiler diagnostics log: {compiler_log_path}")
                
                # Create a custom stdout that writes to GUI in real-time
                class GUIOutputStream:
                    def __init__(self, log_func):
                        self.log_func = log_func
                        self.line_count = 0
                        
                    def write(self, text):
                        if text.strip():  # Only log non-empty lines
                            self.line_count += 1
                            # Schedule GUI update on main thread
                            self.log_func(f"[{self.line_count}] {text.strip()}")
                    
                    def flush(self):
                        pass  # Required for file-like interface
                
                # Capture the original stdout/stderr to restore later
                original_stdout = sys.stdout
                original_stderr = sys.stderr
                
                # Set up real-time GUI output
                gui_output = GUIOutputStream(self.log_status)
                sys.stdout = gui_output
                sys.stderr = gui_output
                
                try:
                    compile_result = UOVidCompiler.main()
                    cancelled = bool(self.stop_requested and not compile_result)
                    success = bool(compile_result) and not cancelled
                    if success:
                        self.log_status("[SUCCESS] Direct compilation completed successfully!")
                    elif cancelled:
                        self.log_status("[STOP] Compilation cancelled.")
                    else:
                        self.log_status("[ERROR] Compilation did not complete.")
                except Exception as e:
                    success = False
                    cancelled = bool(self.stop_requested)
                    self.log_status(f"[ERROR] Compilation error: {str(e)}")
                    self.write_diagnostic("Direct compilation exception", level=logging.ERROR, exc_info=True)
                finally:
                    # Restore original stdout/stderr
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                    if isinstance(compiler_logger, logging.Logger) and compiler_gui_handler is not None:
                        compiler_logger.removeHandler(compiler_gui_handler)
                            
            else:
                # Fallback to subprocess if direct import failed
                self.log_status("[WARNING] Falling back to subprocess method...")
                success = self._run_subprocess_compilation()
                cancelled = bool(self.stop_requested and not success)

        except Exception as e:
            success = False
            cancelled = bool(self.stop_requested)
            self.log_status(f"[ERROR] Thread error: {str(e)}")
            self.write_diagnostic("Compilation thread exception", level=logging.ERROR, exc_info=True)
        
        # Handle completion on main thread
        self.root.after(0, lambda: self._handle_compilation_completion(success, cancelled))
                
    def _handle_compilation_completion(self, success, cancelled=False):
        """Handle completion of compilation process"""
        if success:
            self.consume_compile_entitlement_on_success()
            self.set_progress(100, "Compilation complete")
            self.log_status("[SUCCESS] Video compilation completed successfully!")
            messagebox.showinfo("Success!", 
                "Video compilation completed successfully!\n\nYour compiled video is ready in the output folder.")
            self.run_btn.configure(
                state='normal', 
                text="[OK] Compilation Complete! Click to Compile Again",
                bg=self.colors['success'])
        elif cancelled:
            self.set_progress(0, "Cancelled")
            self.log_status("[STOP] Compilation cancelled — no credit was used.")
            messagebox.showinfo(
                "Stopped",
                "Compilation was stopped.\n\nNo compile credit was used."
            )
            self.run_btn.configure(
                state='normal',
                text="RUN VIDEO COMPILER",
                bg=self.colors['button'])
        else:
            self.set_progress(0, "Failed")
            self.log_status("[ERROR] Compilation failed — no credit was used.")
            messagebox.showerror("Compilation Failed", 
                "Compilation failed.\n\nNo compile credit was used. Check the status log for details.")
            self.run_btn.configure(
                state='normal', 
                text="[ERROR] Compilation Failed - Click to Try Again",
                bg=self.colors['error'])
        self.stop_btn.configure(state='disabled')
        self.stop_btn.grid_remove()
                
    def _run_subprocess_compilation(self):
        """Fallback subprocess compilation method"""
        script_path = os.path.join(os.path.dirname(__file__), "UOVidCompiler.py")
        
        try:
            env = os.environ.copy()
            env['GUI_MODE'] = '1'
            env['VIDEO_INPUT_PATH'] = self.input_path_var.get()
            env['VIDEO_OUTPUT_PATH'] = self.output_path_var.get()
            env['TRIM_SECONDS'] = self.trim_seconds_var.get()
            env['MUSIC_SELECTION'] = self.music_selection_var.get()
            env['INTRO_SELECTION'] = self.intro_selection_for_compiler()
            env['CLIP_ORDER'] = self.clip_order_var.get()
            env['CUSTOM_ORDER_FILE'] = self.custom_order_file
            env['CLIP_TIMEFRAME'] = self.clip_timeframe_var.get()
            env['MUSIC_FOLDER'] = self.get_music_dir()
            env['INTRO_FOLDER'] = self.get_intro_dir()
            env['AUTOVID_LOG_DIR'] = self.get_logs_dir()
            env['AUTOVID_LOG_LEVEL'] = 'DEBUG'

            self.log_status(f"[LOG] Subprocess diagnostics directory: {env['AUTOVID_LOG_DIR']}")
            
            process = subprocess.Popen(
                [sys.executable, "-u", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.path.dirname(__file__),
                env=env,
                bufsize=1,
                universal_newlines=True
            )
            
            line_count = 0
            if process.stdout:
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        line_count += 1
                        self.log_status(f"[{line_count}] {line}")
                        
            process.wait()
            return process.returncode == 0
            
        except Exception as e:
            self.log_status(f"[ERROR] Subprocess error: {str(e)}")
            self.write_diagnostic("Subprocess compilation exception", level=logging.ERROR, exc_info=True)
            return False
        
        finally:
            # Only reset button if it hasn't been set by success/error handlers above
            # This ensures the success/error messages remain visible
            pass
    
    def test_subprocess_output(self):
        """Test basic subprocess output capture"""
        if self.status_text is not None:
            self.status_text.delete(1.0, tk.END)
        self.log_status("[TEST] Testing subprocess output capture...")
        
        # Run in a separate thread
        def test_thread():
            try:
                script_path = os.path.join(os.path.dirname(__file__), "test_subprocess.py")
                
                # Simple approach - no fancy buffering
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    universal_newlines=True
                )
                
                # Read all output
                stdout, _ = process.communicate()
                
                # Display results
                if stdout:
                    lines = stdout.strip().split('\n')
                    for line in lines:
                        if line.strip():
                            self.root.after(0, lambda l=line.strip(): self.log_status(f"CAPTURED: {l}"))
                else:
                    self.root.after(0, lambda: self.log_error("No output captured from test subprocess"))
                    
                self.root.after(0, lambda: self.log_status(f"[TEST] Test complete. Return code: {process.returncode}"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_error(f"Test failed: {e}"))
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def open_config_file(self):
        """Open the configuration file in default editor"""
        config_path = os.path.join(os.path.dirname(__file__), "UOVidCompiler.py")
        try:
            os.startfile(config_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open config file:\n{e}")
    
    def view_logs(self):
        """View application logs"""
        logs_dir = self.get_logs_dir()
        if os.path.exists(logs_dir):
            try:
                os.startfile(logs_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open logs directory:\n{e}")
        else:
            messagebox.showinfo("Info", "No logs directory found yet. Logs will be created after running the compiler.")
    
    def open_output_folder(self):
        """Open the output folder in Windows Explorer"""
        output_path = self.output_path_var.get().strip()
        if output_path and os.path.exists(output_path):
            try:
                os.startfile(output_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open output folder:\n{e}")
        else:
            messagebox.showwarning("Warning", "Output folder not set or does not exist.")
    
    def open_music_folder(self):
        """Open the included music folder in Windows Explorer and refresh dropdown"""
        music_path = self.get_music_dir()
        if os.path.exists(music_path):
            try:
                os.startfile(music_path)
                # Auto-refresh after a short delay
                self.root.after(1000, self.refresh_music_list)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open music folder:\n{e}")
        else:
            messagebox.showwarning("Warning", "Music folder not found.")
    
    def open_intro_folder(self):
        """Open the included intro videos folder in Windows Explorer and refresh dropdown"""
        intro_path = self.get_intro_dir()
        if os.path.exists(intro_path):
            try:
                os.startfile(intro_path)
                # Auto-refresh after a short delay
                self.root.after(1000, self.refresh_intro_list)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open intro folder:\n{e}")
        else:
            messagebox.showwarning("Warning", "Intro folder not found.")
    
    def refresh_music_list(self):
        """Refresh the music dropdown with newly added files"""
        try:
            # Get updated list of music files
            music_options = self.get_available_music()
            
            # Store current selection
            current_selection = self.music_selection_var.get()
            
            # Update combobox values
            if hasattr(self, 'music_combo'):
                self.music_combo['values'] = music_options
                
                # Restore selection if still valid, otherwise default to None
                if current_selection in music_options:
                    self.music_selection_var.set(current_selection)
                else:
                    self.music_selection_var.set(music_options[0] if music_options else 'None')
                
                self.log_status(f"[OK] Music list refreshed - {len(music_options)} tracks available")
        except Exception as e:
            self.log_error(f"Failed to refresh music list: {e}")
            messagebox.showerror("Error", f"Could not refresh music list:\n{e}")
    
    def refresh_intro_list(self):
        """Refresh the intro dropdown with newly added files"""
        try:
            # Get updated list of intro files
            intro_options = self.get_available_intros()
            
            # Store current selection
            current_selection = self.intro_selection_var.get()
            
            # Update combobox values
            if hasattr(self, 'intro_combo'):
                self.intro_combo['values'] = intro_options
                
                if current_selection in intro_options:
                    self.intro_selection_var.set(current_selection)
                else:
                    self.intro_selection_var.set(self.normalize_intro_selection(current_selection))
                
                self.log_status(f"[OK] Intro list refreshed - {len(intro_options)} intro media files available")
        except Exception as e:
            self.log_error(f"Failed to refresh intro list: {e}")
            messagebox.showerror("Error", f"Could not refresh intro list:\n{e}")
    
    def start_folder_monitoring(self):
        """Start monitoring Music and Intros folders for changes (checks every 5 seconds)"""
        self.monitoring_active = True
        self.last_music_files = self.get_music_file_set()
        self.last_intro_files = self.get_intro_file_set()
        self.check_folder_changes()
    
    def get_music_file_set(self):
        """Get set of music filenames for comparison"""
        try:
            music_dir = self.get_music_dir()
            if os.path.exists(music_dir):
                return set(f for f in os.listdir(music_dir) 
                          if f.lower().endswith(self.MUSIC_EXTENSIONS))
        except Exception:
            pass
        return set()
    
    def get_intro_file_set(self):
        """Get set of intro filenames for comparison"""
        try:
            intro_dir = self.get_intro_dir()
            if os.path.exists(intro_dir):
                return set(f for f in os.listdir(intro_dir) 
                          if f.lower().endswith(self.INTRO_EXTENSIONS))
        except Exception:
            pass
        return set()
    
    def check_folder_changes(self):
        """Check for changes in Music and Intros folders (runs every 5 seconds)"""
        if not self.monitoring_active:
            return
        
        try:
            # Check music folder for changes
            current_music = self.get_music_file_set()
            if current_music != self.last_music_files:
                added = current_music - self.last_music_files
                removed = self.last_music_files - current_music
                
                if added or removed:
                    self.refresh_music_list()
                    if added:
                        self.log_status(f"[+] Added {len(added)} music file(s)")
                    if removed:
                        self.log_status(f"[-] Removed {len(removed)} music file(s)")
                
                self.last_music_files = current_music
            
            # Check intro folder for changes
            current_intros = self.get_intro_file_set()
            if current_intros != self.last_intro_files:
                added = current_intros - self.last_intro_files
                removed = self.last_intro_files - current_intros
                
                if added or removed:
                    self.refresh_intro_list()
                    if added:
                        self.log_status(f"[+] Added {len(added)} intro video(s)")
                    if removed:
                        self.log_status(f"[-] Removed {len(removed)} intro video(s)")
                
                self.last_intro_files = current_intros
        
        except Exception as e:
            # Silently fail - don't spam errors if folders are temporarily unavailable
            pass
        
        # Schedule next check in 5000ms (5 seconds)
        if self.monitoring_active:
            self.root.after(5000, self.check_folder_changes)
    
    def stop_folder_monitoring(self):
        """Stop monitoring folders"""
        self.monitoring_active = False
    
    def log_status(self, message, tag="info"):
        """Add a message to the status log - THREAD SAFE VERSION for standalone EXE"""
        
        # If called from a background thread, schedule on main thread
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, lambda: self._log_status_main_thread(message, tag))
            return
            
        self._log_status_main_thread(message, tag)
    
    def _log_status_main_thread(self, message, tag="info"):
        """Internal method to log status - must be called from main thread"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = str(message)
        
        # Keep log/console output ASCII-safe on Windows (cp1252 console during early startup).
        safe_message = (
            message.replace("\u2192", "->")
            .replace("\u2014", "-")
            .replace("\u2013", "-")
        )
        if getattr(sys, "frozen", False) or self.status_text is None:
            safe_message = safe_message.encode("ascii", errors="replace").decode("ascii")

        level_map = {
            "error": logging.ERROR,
            "warning": logging.WARNING,
            "success": logging.INFO,
        }
        self.write_diagnostic(safe_message, level=level_map.get(tag, logging.INFO))
        
        log_message = f"[{timestamp}] {safe_message}\n"

        if self.status_text is None:
            try:
                print(log_message.rstrip())
            except UnicodeEncodeError:
                print(log_message.encode("ascii", errors="replace").decode("ascii").rstrip())
            return
        
        try:
            # Ensure widget is normal state and insert text
            self.status_text.config(state='normal')
            self.status_text.insert('end', log_message, tag)
            self.status_text.see('end')
            
            # Force immediate updates
            self.status_text.update()
            self.root.update()
            
            # Keep log reasonable size (last 1000 lines)
            lines = self.status_text.get('1.0', 'end').split('\n')
            if len(lines) > 1000:
                self.status_text.delete('1.0', f"{len(lines)-1000}.0")
                
        except Exception as e:
            self.write_diagnostic(f"ERROR in log_status: {e}", level=logging.ERROR, exc_info=True)
    
    def log_success(self, message):
        """Log a success message in green"""
        self.log_status(f"[OK] {message}", "success")
    
    def log_warning(self, message):
        """Log a warning message in yellow"""
        self.log_status(f"[WARN] {message}", "warning")
    
    def log_error(self, message):
        """Log an error message in red"""
        self.log_status(f"[ERROR] {message}", "error")
    
    def load_config(self):
        """Load saved configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.write_diagnostic(f"Loaded config from {self.config_file}")
                return config
        except Exception as e:
            self.write_diagnostic(f"Error loading config: {e}", level=logging.ERROR, exc_info=True)
        
        return {
            "input_path": os.path.expanduser("~/Videos/Captures"), 
            "output_path": os.path.expanduser("~/Downloads")
        }
    
    def save_config(self):
        """Save current configuration"""
        try:
            config = {
                "input_path": getattr(self, 'input_path_var', tk.StringVar()).get(),
                "output_path": getattr(self, 'output_path_var', tk.StringVar()).get(),
                "trim_seconds": getattr(self, 'trim_seconds_var', tk.StringVar()).get(),
                "music_selection": getattr(self, 'music_selection_var', tk.StringVar()).get(),
                "intro_selection": getattr(self, 'intro_selection_var', tk.StringVar()).get(),
                "clip_order": getattr(self, 'clip_order_var', tk.StringVar(value="newest_first")).get(),
                "clip_timeframe": getattr(self, 'clip_timeframe_var', tk.StringVar(value="1_week")).get()
                # Resolution auto-detected - no GUI config needed
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            self.write_diagnostic(f"Saved config to {self.config_file}")
        except Exception as e:
            self.write_diagnostic(f"Error saving config: {e}", level=logging.ERROR, exc_info=True)
    
    def load_saved_paths(self):
        """Load previously saved configuration"""
        if hasattr(self, 'input_path_var'):
            self.input_path_var.set(self.config.get("input_path", os.path.expanduser("~/Videos/Captures")))
        if hasattr(self, 'output_path_var'):
            self.output_path_var.set(self.config.get("output_path", os.path.expanduser("~/Downloads")))
        if hasattr(self, 'trim_seconds_var'):
            self.trim_seconds_var.set(self.config.get("trim_seconds") or "15")
        if hasattr(self, 'music_selection_var'):
            self.music_selection_var.set(self.config.get("music_selection") or "None")
        if hasattr(self, 'intro_selection_var'):
            self.intro_selection_var.set(
                self.normalize_intro_selection(self.config.get("intro_selection") or "None")
            )
        if hasattr(self, 'clip_order_var'):
            self.clip_order_var.set(self.config.get("clip_order", "newest_first"))
        if hasattr(self, 'clip_timeframe_var'):
            self.clip_timeframe_var.set(self.config.get("clip_timeframe", "1_week"))
        # Resolution auto-detected by main script - no GUI config needed
        if hasattr(self, 'music_combo'):
            self.refresh_music_list()
        if hasattr(self, 'intro_combo'):
            self.refresh_intro_list()
        if hasattr(self, 'clip_selection_canvas'):
            self.refresh_clip_selection_panel(preserve_saved=True, save_snapshot=False)
        self.update_paths_display()
    
    def center_window(self):
        """Open the main window large and centered without forcing full-screen."""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(max(1280, int(screen_width * 0.82)), max(1280, screen_width - 120))
        height = min(max(900, int(screen_height * 0.84)), max(900, screen_height - 140))
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def position_child_window(self, window, width=None, height=None, modal=False):
        """Center a child window over the main control panel."""
        self.root.update_idletasks()
        window.transient(self.root)

        if width is None or height is None:
            window.update_idletasks()
            width = width or window.winfo_reqwidth()
            height = height or window.winfo_reqheight()

        width = int(width)
        height = int(height)
        x = self.root.winfo_x() + max(20, (self.root.winfo_width() - width) // 2)
        y = self.root.winfo_y() + max(20, (self.root.winfo_height() - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.lift(self.root)
        window.focus_force()

        def close_child_window():
            try:
                window.grab_release()
            except tk.TclError:
                pass
            if getattr(self, "clip_preview_window", None) is window:
                self.stop_preview()
                self.clip_preview_window = None
            if getattr(self, "license_recovery_window", None) is window:
                self.license_recovery_window = None
            if getattr(self, "checkout_window", None) is window:
                self.checkout_window = None
            try:
                window.destroy()
            except tk.TclError:
                pass

        window.protocol("WM_DELETE_WINDOW", close_child_window)
        # Avoid grab_set: it blocks closing the main window from the taskbar on Windows.
    
    # Donation system methods
    def open_venmo(self):
        """Open Venmo payment"""
        try:
            # Use web approach since deep link opens MS Store
            # Copy username and provide clear instructions
            self.copy_to_clipboard(self.DONATION_INFO['venmo'])
            
            # Show detailed instructions with multiple options
            instruction_window = tk.Toplevel(self.root)
            instruction_window.title("Venmo Donation Instructions")
            instruction_window.resizable(False, False)
            instruction_window.configure(bg='white')
            
            # Set icon for popup window
            try:
                ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
                if os.path.exists(ico_path):
                    instruction_window.iconbitmap(ico_path)
            except:
                pass
            
            self.position_child_window(instruction_window, width=450, height=300, modal=True)
            
            # Header
            header_label = tk.Label(instruction_window, text="[CARD] Venmo Donation", 
                                  font=('Segoe UI', 16, 'bold'), 
                                  bg='white', fg='#3D95CE')
            header_label.pack(pady=(20, 15))
            
            # Instructions
            instructions = f"""Username copied to clipboard: {self.DONATION_INFO['venmo']}

To send a donation:

[MOBILE] Mobile App Method:
1. Open your Venmo mobile app
2. Tap "Pay or Request" 
3. Search for: {self.DONATION_INFO['venmo']}
4. Send your donation amount

[WEB] Web Method:
1. Go to venmo.com on your browser
2. Log into your account
3. Search for: {self.DONATION_INFO['venmo']}
4. Send your donation amount"""
            
            text_label = tk.Label(instruction_window, text=instructions,
                                font=('Segoe UI', 10), bg='white', fg='#2c3e50',
                                justify='left', wraplength=400)
            text_label.pack(pady=(0, 20), padx=20)
            
            # Buttons
            button_frame = tk.Frame(instruction_window, bg='white')
            button_frame.pack(pady=10)
            
            copy_btn = tk.Button(button_frame, text="[COPY] Copy Username Again", 
                               font=('Segoe UI', 10, 'bold'),
                               bg='#3D95CE', fg='white',
                               relief='raised', borderwidth=2,
                               command=lambda: self.copy_to_clipboard(self.DONATION_INFO['venmo']))
            copy_btn.pack(side='left', padx=10)
            
            close_btn = tk.Button(button_frame, text="[X] Close", 
                                font=('Segoe UI', 10, 'bold'),
                                bg='#95a5a6', fg='white',
                                relief='raised', borderwidth=2,
                                command=instruction_window.destroy)
            close_btn.pack(side='left', padx=10)
            
            # Thank you message
            thank_you_label = tk.Label(instruction_window, text="Thank you for supporting development!", 
                                     font=('Segoe UI', 11, 'italic'), 
                                     bg='white', fg='#27ae60')
            thank_you_label.pack(pady=(10, 20))
            
        except Exception as e:
            # Simple fallback
            self.copy_to_clipboard(self.DONATION_INFO['venmo'])
            messagebox.showinfo("Venmo Instructions", 
                              f"Venmo username copied: {self.DONATION_INFO['venmo']}\n\n"
                              f"Open your Venmo app and search for this username to donate.\n\n"
                              f"Thank you for your support!")
    
    def open_paypal(self):
        """Open PayPal payment"""
        try:
            paypal_email = self.DONATION_INFO['paypal'].replace('@', '%40')
            paypal_url = f"https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business={paypal_email}&item_name=UO+Video+Compiler+Development"
            webbrowser.open(paypal_url)
            messagebox.showinfo("Thank You!", 
                              f"Opening PayPal for {self.DONATION_INFO['paypal']}\n\nThank you for supporting development!")
        except Exception as e:
            self.copy_to_clipboard(self.DONATION_INFO['paypal'])
            messagebox.showinfo("PayPal Info", 
                              f"PayPal email copied to clipboard: {self.DONATION_INFO['paypal']}")
    
    def copy_crypto_address(self, crypto_type):
        """Copy cryptocurrency address to clipboard and show QR code"""
        address = self.DONATION_INFO.get(crypto_type, '')
        if address:
            self.copy_to_clipboard(address)
            crypto_names = {'btc': 'Bitcoin', 'eth': 'Ethereum', 'sol': 'Solana'}
            crypto_name = crypto_names.get(crypto_type, crypto_type.upper())
            
            # Show QR code if available
            if QR_AVAILABLE:
                self.show_crypto_qr(crypto_name, address, crypto_type)
            else:
                print(f"{crypto_name} address copied to clipboard: {address}")
        else:
            messagebox.showerror("Error", f"No {crypto_type.upper()} address available")
    
    def show_crypto_qr(self, crypto_name, address, crypto_type):
        """Show QR code for cryptocurrency address"""
        try:
            # Create QR code window
            qr_window = tk.Toplevel(self.root)
            qr_window.title(f"{crypto_name} Donation Address")
            qr_window.resizable(False, False)
            qr_window.configure(bg='white')
            
            # Set icon for popup window
            try:
                ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
                if os.path.exists(ico_path):
                    qr_window.iconbitmap(ico_path)
            except:
                pass
            
            self.position_child_window(qr_window, width=450, height=550, modal=True)
            
            # Generate QR code with crypto URI scheme
            qr = qrcode.QRCode(version=1, box_size=8, border=4)
            
            # Create proper crypto URI based on type
            crypto_uri = self.create_crypto_uri(crypto_type, address)
            qr.add_data(crypto_uri)
            qr.make(fit=True)
            
            # Create QR code image and convert directly
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Create a temporary file path
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"qr_temp_{crypto_name.lower()}.png")
            
            # Save QR image to temporary file
            with open(temp_path, 'wb') as f:
                qr_img.save(f)
            
            # Load and resize the image
            pil_img = Image.open(temp_path)
            pil_img = pil_img.resize((200, 200))
            qr_photo = ImageTk.PhotoImage(pil_img)
            
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
            
            # Store image reference globally to prevent garbage collection
            if not hasattr(self, '_qr_images'):
                self._qr_images = []
            self._qr_images.append(qr_photo)
            
            # Header
            header_label = tk.Label(qr_window, text=f"[MONEY] {crypto_name} Donation", 
                                  font=('Segoe UI', 16, 'bold'), 
                                  bg='white', fg='#2c3e50')
            header_label.pack(pady=(20, 5))
            
            # Instruction
            instruction_label = tk.Label(qr_window, text="[MOBILE] Scan with your crypto wallet app", 
                                       font=('Segoe UI', 10, 'italic'), 
                                       bg='white', fg='#7f8c8d')
            instruction_label.pack(pady=(0, 5))
            
            # Additional info
            info_label = tk.Label(qr_window, text="(CashApp, MetaMask, Trust Wallet, Coinbase Wallet, etc.)", 
                                font=('Segoe UI', 8), 
                                bg='white', fg='#95a5a6')
            info_label.pack(pady=(0, 10))
            
            # QR code image
            qr_label = tk.Label(qr_window, image=qr_photo, bg='white')
            qr_label.pack(pady=10)
            qr_label.pack(pady=10)
            
            # Address text (show both URI and plain address)
            address_frame = tk.Frame(qr_window, bg='white')
            address_frame.pack(pady=10, padx=20, fill='x')
            
            # Show what the QR contains
            qr_info_label = tk.Label(address_frame, text="QR Code Contains:", 
                                   font=('Segoe UI', 9, 'bold'), 
                                   bg='white', fg='#7f8c8d')
            qr_info_label.pack()
            
            qr_content_text = tk.Text(address_frame, height=2, width=40, 
                                    font=('Courier New', 8), 
                                    wrap=tk.WORD, bg='#f8f9fa', 
                                    relief='solid', borderwidth=1)
            qr_content_text.pack(pady=(2, 10))
            qr_content_text.insert(tk.END, crypto_uri)
            qr_content_text.config(state='disabled')
            
            # Plain address
            address_label = tk.Label(address_frame, text="Plain Address:", 
                                   font=('Segoe UI', 9, 'bold'), 
                                   bg='white', fg='#34495e')
            address_label.pack()
            
            address_text = tk.Text(address_frame, height=2, width=40, 
                                 font=('Courier New', 9), 
                                 wrap=tk.WORD, bg='#f8f9fa', 
                                 relief='solid', borderwidth=1)
            address_text.pack(pady=(2, 0))
            address_text.insert(tk.END, address)
            address_text.config(state='disabled')
            
            # Buttons
            button_frame = tk.Frame(qr_window, bg='white')
            button_frame.pack(pady=15)
            
            copy_btn = tk.Button(button_frame, text="[COPY] Copy Address", 
                               font=('Segoe UI', 10, 'bold'),
                               bg='#3498db', fg='white',
                               relief='raised', borderwidth=2,
                               command=lambda: self.copy_to_clipboard(address))
            copy_btn.pack(side='left', padx=10)
            
            close_btn = tk.Button(button_frame, text="[X] Close", 
                                font=('Segoe UI', 10, 'bold'),
                                bg='#95a5a6', fg='white',
                                relief='raised', borderwidth=2,
                                command=qr_window.destroy)
            close_btn.pack(side='left', padx=10)
            
            # Trading platform note
            trading_note = tk.Label(qr_window, 
                                  text="[TIP] For Robinhood/Webull: Copy address and paste manually in app", 
                                  font=('Segoe UI', 9, 'italic'), 
                                  bg='white', fg='#f39c12', wraplength=380)
            trading_note.pack(pady=(5, 10))
            
            # Thank you message
            thank_you_label = tk.Label(qr_window, text="Thank you for supporting development!", 
                                     font=('Segoe UI', 11, 'italic'), 
                                     bg='white', fg='#27ae60')
            thank_you_label.pack(pady=(0, 20))
            
        except Exception as e:
            # Fallback to simple message if QR generation fails
            print(f"QR code generation error: {e}")
            messagebox.showerror("QR Generation Error", 
                               f"Could not generate QR code. Address copied to clipboard:\n\n{address}")
    
    def copy_to_clipboard(self, text):
        """Copy text to system clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception as e:
            print(f"Error copying to clipboard: {e}")
    
    def create_crypto_uri(self, crypto_type, address):
        """Create proper crypto URI scheme for wallet apps"""
        if crypto_type == 'btc':
            # Bitcoin URI with suggested donation amount - try multiple formats
            return f"bitcoin:{address}?amount=0.001&message=UO%20Video%20Compiler%20Development%20Support"
        elif crypto_type == 'eth':
            # Ethereum URI with suggested amount (in wei - 0.01 ETH) 
            return f"ethereum:{address}?value=10000000000000000&gas=21000"
        elif crypto_type == 'sol':
            # Solana URI with suggested amount  
            return f"solana:{address}?amount=0.1&label=UO%20Video%20Compiler%20Donation"
        else:
            # Fallback to plain address
            return address
    
    def create_button_icon(self, icon_type, size=(16, 16)):
        """Create simple icon images for buttons"""
        from PIL import Image, ImageDraw
        
        # Create a transparent image
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        if icon_type == 'folder':
            # Draw a simple folder icon
            draw.rectangle([(2, 6), (14, 13)], fill=(255, 215, 0), outline=(200, 150, 0))
            draw.rectangle([(2, 4), (8, 6)], fill=(255, 215, 0), outline=(200, 150, 0))
        elif icon_type == 'test':
            # Draw a simple gear/settings icon
            draw.ellipse([(4, 4), (12, 12)], fill=(100, 150, 255), outline=(50, 100, 200))
            draw.ellipse([(6, 6), (10, 10)], fill=(255, 255, 255))
        elif icon_type == 'logs':
            # Draw a simple document icon
            draw.rectangle([(4, 2), (12, 14)], fill=(255, 255, 255), outline=(128, 128, 128))
            draw.line([(5, 5), (11, 5)], fill=(128, 128, 128))
            draw.line([(5, 7), (11, 7)], fill=(128, 128, 128))
            draw.line([(5, 9), (11, 9)], fill=(128, 128, 128))
        elif icon_type == 'output':
            # Draw a simple output/export icon
            draw.rectangle([(2, 4), (10, 12)], fill=(100, 255, 100), outline=(50, 200, 50))
            draw.polygon([(10, 6), (14, 8), (10, 10)], fill=(50, 200, 50))
        elif icon_type == 'video':
            # Draw a simple video camera icon
            draw.rectangle([(2, 5), (10, 11)], fill=(255, 100, 100), outline=(200, 50, 50))
            draw.polygon([(10, 6), (14, 8), (10, 10)], fill=(200, 50, 50))
        elif icon_type == 'music':
            # Draw a simple music note icon
            draw.ellipse([(4, 10), (8, 14)], fill=(255, 150, 255), outline=(200, 100, 200))
            draw.rectangle([(8, 3), (9, 11)], fill=(200, 100, 200))
            draw.arc([(9, 3), (13, 7)], 270, 90, fill=(200, 100, 200))
        elif icon_type == 'config':
            # Draw a simple config/settings icon
            draw.rectangle([(4, 2), (12, 14)], fill=(200, 200, 200), outline=(150, 150, 150))
            draw.rectangle([(6, 4), (10, 6)], fill=(100, 100, 255))
            draw.rectangle([(6, 8), (10, 10)], fill=(100, 100, 255))
            draw.rectangle([(6, 12), (10, 14)], fill=(100, 100, 255))
        elif icon_type == 'gift':
            # Draw a gift/heart icon
            # Heart shape using two circles and a triangle
            draw.ellipse([3, 4, 7, 8], fill=(255, 100, 100))
            draw.ellipse([9, 4, 13, 8], fill=(255, 100, 100))
            # Bottom triangle part of heart
            draw.polygon([(3, 7), (13, 7), (8, 13)], fill=(255, 100, 100))
        
        return ImageTk.PhotoImage(img)

    def load_button_icons(self):
        """Load all button icons"""
        print("[ICONS] Loading button icons...")
        try:
            self.icons = {
                'folder': self.create_button_icon('folder'),
                'test': self.create_button_icon('test'),
                'logs': self.create_button_icon('logs'),
                'output': self.create_button_icon('output'),
                'video': self.create_button_icon('video'),
                'music': self.create_button_icon('music'),
                'config': self.create_button_icon('config'),
                'gift': self.create_button_icon('gift')
            }
            print(f"[ICONS] Successfully loaded {len(self.icons)} button icons")
        except Exception as e:
            print(f"[ERROR] Failed to load button icons: {e}")
            # Fallback to empty dict if icon creation fails
            self.icons = {}
    
    def create_tooltip(self, widget, text):
        """Create a simple tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(tooltip, text=text, 
                           background='lightyellow', 
                           relief='solid', 
                           borderwidth=1,
                           font=('Segoe UI', 9))
            label.pack()
            
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def _github_request(self, url, timeout=30):
        """GitHub API or release download with required headers."""
        req = urllib.request.Request(url, headers={**self.GITHUB_API_HEADERS, "User-Agent": self.UPDATE_USER_AGENT})
        return urllib.request.urlopen(req, timeout=timeout)

    def _find_release_exe_asset(self, release_data):
        """Return (download_url, asset_name, expected_size) for the release exe only."""
        for asset in release_data.get("assets", []):
            name = str(asset.get("name", "") or "")
            if name == self.RELEASE_EXE_NAME:
                return (
                    asset.get("browser_download_url"),
                    name,
                    int(asset.get("size", 0) or 0),
                )
        return None, None, 0

    def _validate_downloaded_update(self, path, expected_size=0):
        """Ensure the downloaded file is a real PE executable, not an HTML error page."""
        if not os.path.isfile(path):
            return False, "Downloaded file is missing."
        size = os.path.getsize(path)
        if size < self.MIN_UPDATE_BYTES:
            return False, f"Download looks incomplete ({size:,} bytes). Check your connection and try again."
        if expected_size and size < int(expected_size * 0.95):
            return False, f"Download size mismatch (got {size:,} bytes, expected about {expected_size:,})."
        with open(path, "rb") as handle:
            if handle.read(2) != b"MZ":
                return False, "Download is not a valid Windows program file. Try again or install manually from GitHub."
        return True, ""

    def check_for_updates(self):
        """Check GitHub for newer version and prompt user to update."""
        try:
            if not getattr(sys, "frozen", False):
                return
            if self._update_download_active:
                return

            api_url = f"https://api.github.com/repos/{self.GITHUB_REPO}/releases/latest"
            with self._github_request(api_url, timeout=15) as response:
                data = json.loads(response.read().decode())

            latest_version = str(data.get("tag_name", "")).lstrip("vV")
            if not self.compare_versions(latest_version, self.VERSION):
                return

            download_url, asset_name, expected_size = self._find_release_exe_asset(data)
            if not download_url:
                print("Update check: release has no Auto_Video_Compiler.exe asset")
                return

            self.root.after(
                0,
                lambda: self.prompt_update(latest_version, download_url, data.get("body", ""), expected_size),
            )
        except Exception as e:
            print(f"Update check failed: {e}")

    def compare_versions(self, version1, version2):
        """Compare two version strings (returns True if version1 > version2)."""
        try:
            v1_parts = [int(x) for x in str(version1).split(".")]
            v2_parts = [int(x) for x in str(version2).split(".")]
            while len(v1_parts) < len(v2_parts):
                v1_parts.append(0)
            while len(v2_parts) < len(v1_parts):
                v2_parts.append(0)
            return v1_parts > v2_parts
        except (TypeError, ValueError):
            return False

    def prompt_update(self, new_version, download_url, changelog, expected_size=0):
        """Show update dialog and handle download."""
        if self._update_prompt_shown or self._update_download_active:
            return
        self._update_prompt_shown = True

        message = f"New version available: v{new_version}\n"
        message += f"Current version: v{self.VERSION}\n\n"
        if changelog:
            message += f"Changes:\n{changelog[:200]}"
            if len(changelog) > 200:
                message += "...\n"
        message += (
            "\n\nDownload happens in the background (~200 MB). "
            "Close the app when prompted to finish installing.\n\n"
            "Download and install the update now?"
        )

        if messagebox.askyesno("Update Available", message):
            self._update_download_active = True
            threading.Thread(
                target=self._download_update_worker,
                args=(download_url, new_version, expected_size),
                daemon=True,
            ).start()
        else:
            self._update_prompt_shown = False

    def _show_update_progress(self, title="Downloading update"):
        """Show a small progress window on the main thread."""
        if self._update_progress_window is not None:
            return

        window = tk.Toplevel(self.root)
        window.title(title)
        window.resizable(False, False)
        window.transient(self.root)
        self._update_progress_var = tk.DoubleVar(value=0)
        ttk.Label(window, text="Downloading update (~200 MB)...", padding=12).pack()
        self._update_progress_label = ttk.Label(window, text="Starting...", padding=(12, 0))
        self._update_progress_label.pack()
        ttk.Progressbar(window, variable=self._update_progress_var, maximum=100, length=320).pack(padx=12, pady=12)
        window.update_idletasks()
        self._center_toplevel(window)
        self._update_progress_window = window

    def _center_toplevel(self, window, width=None, height=None):
        window.update_idletasks()
        if width and height:
            window.geometry(f"{width}x{height}")
            window.update_idletasks()
        win_w = window.winfo_width()
        win_h = window.winfo_height()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - win_w) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - win_h) // 2)
        window.geometry(f"+{x}+{y}")

    def _set_update_progress(self, percent, label):
        def apply():
            if self._update_progress_var is not None:
                self._update_progress_var.set(max(0, min(100, percent)))
            if self._update_progress_label is not None:
                self._update_progress_label.configure(text=label)
        self.root.after(0, apply)

    def _close_update_progress(self):
        def apply():
            if self._update_progress_window is not None:
                try:
                    self._update_progress_window.grab_release()
                    self._update_progress_window.destroy()
                except tk.TclError:
                    pass
                self._update_progress_window = None
            self._update_progress_var = None
            self._update_progress_label = None
        self.root.after(0, apply)

    def _download_update_worker(self, download_url, new_version, expected_size=0):
        """Background download with validation and a safe swap-on-exit installer."""
        temp_path = None
        try:
            self.root.after(0, self._show_update_progress)
            self._set_update_progress(0, "Connecting to GitHub...")

            current_exe = os.path.abspath(sys.executable)
            install_dir = os.path.dirname(current_exe)
            exe_name = os.path.basename(current_exe)
            staged_name = f"{os.path.splitext(exe_name)[0]}_NEW.exe"
            staged_path = os.path.join(install_dir, staged_name)

            for stale in (staged_path, os.path.join(install_dir, "updater.bat")):
                if os.path.exists(stale):
                    try:
                        os.remove(stale)
                    except OSError:
                        pass

            temp_fd, temp_path = tempfile.mkstemp(prefix="avc_update_", suffix=".part", dir=install_dir)
            os.close(temp_fd)

            req = urllib.request.Request(download_url, headers={"User-Agent": self.UPDATE_USER_AGENT})
            with urllib.request.urlopen(req, timeout=600) as response:
                total = int(response.headers.get("Content-Length", 0) or expected_size or 0)
                downloaded = 0
                chunk_size = 1024 * 256
                with open(temp_path, "wb") as out_file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            percent = (downloaded / total) * 100
                            label = f"{downloaded // (1024 * 1024)} / {total // (1024 * 1024)} MB"
                        else:
                            percent = min(99, downloaded // (2 * 1024 * 1024))
                            label = f"{downloaded // (1024 * 1024)} MB downloaded"
                        self._set_update_progress(percent, label)

            ok, reason = self._validate_downloaded_update(temp_path, expected_size=expected_size)
            if not ok:
                raise RuntimeError(reason)

            if os.path.exists(staged_path):
                os.remove(staged_path)
            os.replace(temp_path, staged_path)
            temp_path = None

            batch_path = os.path.join(install_dir, "updater.bat")
            log_path = os.path.join(install_dir, "update_install.log")
            batch_script = f'''@echo off
setlocal
cd /d "%~dp0"
echo [%date% %time%] Starting update to v{new_version}>>"{log_path}"
timeout /t 3 /nobreak >nul
if exist "{exe_name}.bak" del /f /q "{exe_name}.bak"
if exist "{exe_name}" ren "{exe_name}" "{exe_name}.bak"
move /y "{staged_name}" "{exe_name}"
if errorlevel 1 (
  echo [%date% %time%] Update move failed>>"{log_path}"
  if exist "{exe_name}.bak" ren "{exe_name}.bak" "{exe_name}"
  exit /b 1
)
if exist "{exe_name}.bak" del /f /q "{exe_name}.bak"
start "" "%~dp0{exe_name}"
echo [%date% %time%] Update complete>>"{log_path}"
del "%~f0"
'''
            with open(batch_path, "w", encoding="utf-8", newline="\r\n") as handle:
                handle.write(batch_script)

            self.updater_batch_path = batch_path
            self.log_status(f"[UPDATE] v{new_version} downloaded and ready to install on exit.")

            def notify_ready():
                self._close_update_progress()
                messagebox.showinfo(
                    "Update Ready",
                    f"Version {new_version} downloaded successfully.\n\n"
                    "Close Auto Video Compiler to install the update. "
                    "The app will restart automatically.\n\n"
                    "If anything goes wrong, download the latest .exe from GitHub Releases.",
                )

            self.root.after(0, notify_ready)
        except Exception as e:
            def notify_failed():
                self._close_update_progress()
                self.log_error(f"Update download failed: {e}")
                messagebox.showerror(
                    "Update Failed",
                    f"Could not download the update:\n{e}\n\n"
                    "Install manually from:\n"
                    f"https://github.com/{self.GITHUB_REPO}/releases/latest",
                )
                self._update_prompt_shown = False
                self._update_download_active = False

            self.root.after(0, notify_failed)
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            if not self.updater_batch_path:
                self._update_download_active = False

    def _close_all_child_windows(self):
        """Close dialogs and release modal grabs so the main window can exit."""
        self.stop_preview()
        self._close_update_progress()

        tracked = (
            getattr(self, "clip_preview_window", None),
            getattr(self, "license_recovery_window", None),
            getattr(self, "checkout_window", None),
            getattr(self, "_create_intro_window", None),
            getattr(self, "_update_progress_window", None),
        )
        for win in tracked:
            if win is None:
                continue
            try:
                if win.winfo_exists():
                    try:
                        win.grab_release()
                    except tk.TclError:
                        pass
                    win.destroy()
            except tk.TclError:
                pass

        self.clip_preview_window = None
        self.license_recovery_window = None
        self.checkout_window = None
        self._create_intro_window = None

        try:
            for child in list(self.root.winfo_children()):
                try:
                    child.grab_release()
                except tk.TclError:
                    pass
                try:
                    child.destroy()
                except tk.TclError:
                    pass
        except tk.TclError:
            pass

    def on_closing(self):
        """Handle application closing (X button, Alt+F4, taskbar close)."""
        if self._shutdown_in_progress:
            os._exit(0)
            return

        if self.stop_requested is False and hasattr(self, "run_btn"):
            try:
                btn_text = str(self.run_btn.cget("text") or "")
                if "Compiling" in btn_text:
                    if not messagebox.askyesno(
                        "Compilation Running",
                        "A compilation is still running.\n\nClose anyway?",
                    ):
                        return
            except tk.TclError:
                pass

        self._shutdown_in_progress = True
        self.stop_requested = True
        self.stop_folder_monitoring()
        self._close_all_child_windows()

        try:
            self.save_config()
        except Exception:
            pass

        self._remove_gui_pid_file()

        updater_batch = getattr(self, "updater_batch_path", None)
        if updater_batch and os.path.exists(updater_batch):
            try:
                subprocess.Popen(
                    ["cmd.exe", "/c", updater_batch],
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                    close_fds=True,
                    shell=False,
                )
            except Exception:
                pass

        try:
            self.root.quit()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

        os._exit(0)

    def run(self):
        """Start the GUI application"""
        self.root.mainloop()


def ensure_single_instance():
    """Prevent multiple GUI instances (common cause of 'stuck' taskbar entries)."""
    if os.name != "nt":
        return True
    import ctypes

    mutex_name = "Global\\KnightLogics.AutoVideoCompiler.SingleInstance"
    ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
    if ctypes.windll.kernel32.GetLastError() != 183:
        return True

    pid_hint = ""
    pid_path = os.path.join(get_app_storage_dir(), "gui.pid")
    if os.path.isfile(pid_path):
        try:
            with open(pid_path, "r", encoding="utf-8") as handle:
                existing_pid = int((handle.readline() or "").strip())
            pid_hint = (
                f"\n\nRunning GUI process ID: {existing_pid}\n"
                "Task Manager > Details > Command line contains UOVidCompiler_GUI.py"
            )
        except (OSError, ValueError):
            pass

    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning(
            "Already Running",
            "Auto Video Compiler is already open.\n\n"
            "Check the taskbar for the existing window."
            f"{pid_hint}\n\n"
            "To force-close only this app, run Kill-AutoVideoCompiler-GUI.ps1 "
            "in the project folder (does not stop other Python programs).",
        )
        root.destroy()
    except Exception:
        pass
    return False


def main():
    """Main application entry point"""
    try:
        if not ensure_single_instance():
            return
        app = UOVidCompilerGUI()
        app.run()
    except Exception as e:
        error_msg = f"Error starting UO Video Compiler GUI:\n{traceback.format_exc()}"
        log_path = write_bootstrap_log("autovid_gui_startup_failure", error_msg)
        print(f"{error_msg}\nLogged to: {log_path}")
        
        # Try to show error in messagebox if possible
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Application Error", f"{error_msg}\n\nLogged to: {log_path}")
        except:
            pass

if __name__ == "__main__":
    main()
