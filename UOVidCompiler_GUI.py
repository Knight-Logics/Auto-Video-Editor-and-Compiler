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
from PIL import Image, ImageTk
import threading
import urllib.request
import tempfile
import shutil
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

class UOVidCompilerGUI:
    # Version info for auto-updates
    VERSION = "1.2.1"  # Update this when releasing new versions
    GITHUB_REPO = "Knight-Logics/Auto-Video-Editor-and-Compiler"  # GitHub repo for auto-updates
    
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
        self.config_file = os.path.join(os.path.dirname(__file__), "gui_config.json")
        self.config = self.load_config()
        
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
        
        # Set icon IMMEDIATELY for taskbar
        self.set_taskbar_icon()
        
        # Load PNG logo for GUI use BEFORE creating widgets
        self.load_png_logo()
        
        # Load payment method logos
        self.load_payment_logos()
        
        # Load button icons
        self.load_button_icons()
        
        self.root.title("Auto Video Editor & Compiler - Control Panel")
        self.root.geometry("950x800")  # Slightly larger for better header visibility
        self.root.minsize(900, 750)    # Larger minimum size to prevent layout issues
        self.root.resizable(True, True)
        
        # Set application icon (additional setup)
        self.setup_icon()
        
        # Setup GUI AFTER logo is loaded
        self.setup_styles()
        self.create_widgets()
        self.load_saved_paths()
        
        # Start folder monitoring (checks every 5 seconds)
        self.start_folder_monitoring()
        
        # Center window
        self.center_window()
        
        # Check for updates on startup (in background thread)
        threading.Thread(target=self.check_for_updates, daemon=True).start()
        
    def set_taskbar_icon(self):
        """Set taskbar icon immediately upon window creation - CRITICAL for Windows taskbar display"""
        try:
            ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
            if os.path.exists(ico_path):
                # IMMEDIATE icon setting before window appears
                self.root.iconbitmap(ico_path)
                
                # Try Windows API approach for better taskbar integration
                try:
                    import ctypes
                    # Set the application model ID to distinguish from Python
                    app_id = 'BMagic.UOVidCompiler.GUI.1.0'
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
        # Removed resolution_var - using auto-detection always

    def load_png_logo(self):
        """Load PNG logo for GUI display - called early in initialization"""
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "icons", "KnightLogicsVidCompiler_transparent.png")
            
            if os.path.exists(logo_path):
                # Load and resize logo for display in GUI (150x150 pixels)
                logo_image = Image.open(logo_path)
                self.logo_large = logo_image.resize((150, 150), Image.Resampling.LANCZOS)
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
                button_icon_path = os.path.join(os.path.dirname(__file__), "icons", f"{payment}_button_icon.png")
                
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
            ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
            
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
        
    def create_widgets(self):
        """Create and arrange GUI widgets"""
        
        # Main container with padding and styling
        main_frame = ttk.Frame(self.root, style='Custom.TFrame')
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Header with logo and title
        self.create_header(main_frame)
        
        # Configuration section
        self.create_config_section(main_frame)
        
        # Action buttons
        self.create_action_section(main_frame)
        
        # Status area
        self.create_status_section(main_frame)
        
    def create_header(self, parent):
        """Create professional header with logo, title, and support section"""
        # Main header frame with fixed height
        header_frame = ttk.Frame(parent, style='Header.TFrame')
        header_frame.pack(fill='x', pady=(0, 20), padx=10)
        
        # Configure header frame to maintain consistent height
        header_frame.pack_propagate(False)
        header_frame.configure(height=140)
        
        # Left side: Logo container (centered vertically)
        logo_frame = ttk.Frame(header_frame, style='Header.TFrame')
        logo_frame.pack(side='left', padx=(0, 20), anchor='center')
        
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
        
        # Center: Title section - vertically centered
        title_frame = ttk.Frame(header_frame, style='Header.TFrame')
        title_frame.pack(side='left', fill='both', expand=True, padx=(0, 20))
        
        # Create inner frame for vertical centering
        title_inner = ttk.Frame(title_frame, style='Header.TFrame')
        title_inner.pack(anchor='center', expand=True)
        
        # Title
        title_label = ttk.Label(title_inner, text="Auto Video Editor & Compiler", 
                              style='Title.TLabel', font=('Segoe UI', 18, 'bold'))
        title_label.pack(anchor='w')
        
        # Subtitle and version on same line
        info_frame = ttk.Frame(title_inner, style='Header.TFrame')
        info_frame.pack(anchor='w', pady=(3, 0))
        
        subtitle_label = ttk.Label(info_frame, 
                                 text="Professional video compilation tool  •  v" + str(self.VERSION),
                                 style='Heading.TLabel', font=('Segoe UI', 9))
        subtitle_label.pack(anchor='w')
        
        # Right side: Support section - vertically centered
        support_frame = ttk.Frame(header_frame, style='Header.TFrame')
        support_frame.pack(side='right', anchor='center', padx=(0, 5))
        
        # Support header
        support_label = ttk.Label(support_frame, text="❤ Support Development", 
                                style='Heading.TLabel', font=('Segoe UI', 10, 'bold'))
        support_label.pack()
        
        # Payment buttons frame
        buttons_frame = ttk.Frame(support_frame, style='Header.TFrame')
        buttons_frame.pack(pady=(5, 0))
        
        # Payment method configurations - now with logo support
        payment_methods = [
            ('Venmo', 'venmo', self.colors['button'], lambda: self.open_venmo()),
            ('PayPal', 'paypal', '#0070ba', lambda: self.open_paypal()),
            ('Bitcoin', 'bitcoin', '#f7931a', lambda: self.copy_crypto_address('btc')),
            ('Ethereum', 'ethereum', '#627eea', lambda: self.copy_crypto_address('eth')),
            ('Solana', 'solana', '#14f195', lambda: self.copy_crypto_address('sol'))
        ]
        
        # Create payment buttons with logos
        for i, (name, logo_key, color, command) in enumerate(payment_methods):
            # Check if we have a logo for this payment method
            if hasattr(self, 'payment_logos') and logo_key in self.payment_logos:
                # Use actual logo image with transparent button background
                btn = tk.Button(buttons_frame, 
                              image=self.payment_logos[logo_key],
                              bg=self.colors['bg'],  # Match header background
                              fg='white',
                              width=36,
                              height=36,
                              relief='flat',  # Flat relief for minimal button appearance
                              borderwidth=0,  # No border
                              cursor='hand2',
                              command=command,
                              activebackground=self.colors['bg'])  # Keep same bg when clicked
                
                # Add tooltip with payment method name
                self.create_tooltip(btn, f"Donate via {name}")
                print(f"[OK] Created {name} button with official logo")
            else:
                # Fallback to text/emoji if logo not available - also with transparent background
                fallback_icons = {
                    'venmo': 'V', 'paypal': 'P', 'bitcoin': 'B', 
                    'ethereum': 'E', 'solana': 'S'
                }
                
                btn = tk.Button(buttons_frame, 
                              text=fallback_icons.get(logo_key, 'P'),
                              font=('Segoe UI', 12, 'bold'),
                              bg=self.colors['bg'],  # Match header background
                              fg='white',
                              width=3,
                              height=1,
                              relief='flat',  # Flat relief for minimal appearance
                              borderwidth=0,  # No border
                              cursor='hand2',
                              command=command,
                              activebackground=self.colors['bg'])  # Keep same bg when clicked
                
                print(f"[WARN] Using fallback icon for {name} (logo not available)")
            btn.pack(side='left', padx=2)
            
            # Add tooltip
            self.create_tooltip(btn, f"{name}: Click to {('open' if name in ['Venmo', 'PayPal'] else 'copy address')}")
        

        
    def create_config_section(self, parent):
        """Create configuration input section"""
        
        # Configuration frame with standard styling
        config_frame = ttk.LabelFrame(parent, text="Path Configuration", padding=20)
        config_frame.pack(fill='x', pady=(0, 20))
        
        # Input folder
        self.create_path_row(config_frame, "Input Video Folder:", "input_path", 
                           "Select folder containing your UO gameplay videos",
                           is_directory=True, row=0)
        
        # Output folder  
        self.create_path_row(config_frame, "[OUTPUT] Output Video Folder:", "output_path",
                           "Select folder where compiled videos will be saved", 
                           is_directory=True, row=1)
        
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
        label = ttk.Label(parent, text=label_text, style='Info.TLabel')
        label.grid(row=row, column=0, sticky='w', padx=(0, 10), pady=5)
        
        # Entry with enhanced styling
        entry_var = tk.StringVar()
        setattr(self, f"{config_key}_var", entry_var)
        
        entry = ttk.Entry(parent, textvariable=entry_var, width=55, style='Custom.TEntry')
        entry.grid(row=row, column=1, sticky='ew', padx=(0, 15), pady=8)
        
        # Browse button with enhanced styling and icon
        browse_cmd = lambda: self.browse_path(entry_var, is_directory, tooltip)
        
        # Create the browse button with icon
        browse_btn = tk.Button(parent, text="Browse", 
                              image=self.icons['folder'],
                              compound='left',
                              command=browse_cmd, 
                              font=('Arial', 9),
                              bg=self.colors['button'],
                              fg='white',
                              relief='raised',
                              width=80,  # Pixel width instead of character width
                              padx=8)
        self.button_images[f'browse_{config_key}'] = self.icons['folder']  # Keep reference to prevent garbage collection
        browse_btn.grid(row=row, column=2, pady=8)
        
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
    
    def get_available_music(self):
        """Get list of available music files"""
        try:
            music_dir = os.path.join(os.path.dirname(__file__), "Music")
            if not os.path.exists(music_dir):
                return ['None', '[RANDOM] Random']
            
            music_files = ['None', '[RANDOM] Random']  # None option first, then random option
            for file in os.listdir(music_dir):
                if file.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    music_files.append(os.path.splitext(file)[0])  # Remove extension for display
            
            return music_files if len(music_files) > 2 else ['None', '[RANDOM] Random']
        except Exception:
            return ['[RANDOM] Random']
    
    def get_available_intros(self):
        """Get list of available intro video files"""
        try:
            intro_dir = os.path.join(os.path.dirname(__file__), "Intros")
            if not os.path.exists(intro_dir):
                return ['StockDefault']
            
            intro_files = []
            stock_default_found = False
            
            for file in os.listdir(intro_dir):
                if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    filename = os.path.splitext(file)[0]  # Remove extension for display
                    if filename == 'StockDefault':
                        stock_default_found = True
                    else:
                        intro_files.append(filename)
            
            # Put None first, then StockDefault if it exists, then Random, then alphabetically sorted others
            result = ['None']
            if stock_default_found:
                result.append('StockDefault')
            result.append('[RANDOM] Random')
            result.extend(sorted(intro_files))
            
            return result if result else ['None', 'StockDefault']
        except Exception:
            return ['StockDefault']
    
    def create_action_section(self, parent):
        """Create action buttons section with video configuration options"""
        
        # Action buttons with enhanced layout
        action_frame = ttk.Frame(parent, style='Custom.TFrame')
        action_frame.pack(fill='x', pady=(0, 20))
        
        # Video Configuration Options (above the main button)
        config_options_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        config_options_frame.pack(fill='x', pady=(0, 20))
        
        # Create a grid layout for the 3 options with proper spacing
        options_container = ttk.Frame(config_options_frame, style='Custom.TFrame')
        options_container.pack(fill='x', pady=(0, 10))
        
        # Configure grid weights to make columns expand evenly
        options_container.grid_columnconfigure(0, weight=1)
        options_container.grid_columnconfigure(1, weight=1)
        options_container.grid_columnconfigure(2, weight=1)
        
        # Option 1: Trim seconds (left column)
        trim_frame = ttk.Frame(options_container, style='Custom.TFrame')
        trim_frame.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        
        ttk.Label(trim_frame, text="Seconds Trimmed from End:", style='Info.TLabel').pack(anchor='w')
        trim_options = ['None', '5', '10', '15', '20', '25', '30']
        self.trim_seconds_var.set('15')  # Default to 15 seconds like S+ working version
        trim_combo = ttk.Combobox(trim_frame, textvariable=self.trim_seconds_var, 
                                values=trim_options, state='readonly')
        trim_combo.pack(fill='x', pady=(2, 0))
        
        # Option 2: Background Music (center column)
        music_frame = ttk.Frame(options_container, style='Custom.TFrame')
        music_frame.grid(row=0, column=1, sticky='ew', padx=5)

        ttk.Label(music_frame, text="Background Music:", style='Info.TLabel').pack(anchor='w')
        music_options = self.get_available_music()
        # Set default to None if empty
        if not self.music_selection_var.get() and music_options:
            self.music_selection_var.set(music_options[0])  # 'None'
        self.music_combo = ttk.Combobox(music_frame, textvariable=self.music_selection_var,
                                 values=music_options, state='readonly')
        self.music_combo.pack(fill='x', pady=(2, 0))
        # Ensure current selection is visible
        self.music_combo.current(0 if not self.music_selection_var.get() else self.music_combo['values'].index(self.music_selection_var.get()))

        # Option 3: Intro Video (right column)
        intro_frame = ttk.Frame(options_container, style='Custom.TFrame')
        intro_frame.grid(row=0, column=2, sticky='ew', padx=(10, 0))

        ttk.Label(intro_frame, text="Intro:", style='Info.TLabel').pack(anchor='w')
        intro_options = self.get_available_intros()
        # Set default to None if empty
        if not self.intro_selection_var.get() and intro_options:
            self.intro_selection_var.set(intro_options[0])  # 'None'
        self.intro_combo = ttk.Combobox(intro_frame, textvariable=self.intro_selection_var,
                                 values=intro_options, state='readonly')
        self.intro_combo.pack(fill='x', pady=(2, 0))
        # Ensure current selection is visible
        self.intro_combo.current(0 if not self.intro_selection_var.get() else self.intro_combo['values'].index(self.intro_selection_var.get()))
        
        # Main action button (prominent)
        main_button_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        main_button_frame.pack(fill='x', pady=(0, 15))
        
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
        self.run_btn.pack(fill='x')
        
        # Secondary buttons in a row
        secondary_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        secondary_frame.pack(fill='x')
        
        # Remove font from ttk.Button style dict since ttk doesn't support it
        btn_style = {'width': 18, 'style': 'Custom.TButton'}
        
        # Create action buttons with icons (removed problematic config and test buttons)
        action_buttons = [
            ("View Logs", self.view_logs, 'logs'),
            ("Output Folder", self.open_output_folder, 'output'),
            ("Intro Videos", self.open_intro_folder, 'video'),
            ("Music Folder", self.open_music_folder, 'music')
        ]
        
        for i, (text, command, icon_key) in enumerate(action_buttons):
            btn = tk.Button(
                secondary_frame, 
                text=text,
                image=self.icons[icon_key],
                compound='left',
                command=command,
                font=('Arial', 9),
                bg=self.colors['button'],
                fg='white',
                relief='raised',
                width=90,  # Pixel width
                padx=8,
                pady=4
            )
            self.button_images[f'action_{icon_key}'] = self.icons[icon_key]  # Keep reference
            
            if i < 4:  # First 4 buttons on the left
                btn.pack(side='left', padx=(0, 10))
            else:  # Last 2 buttons on the right
                btn.pack(side='right', padx=(10, 0))
        
    def create_status_section(self, parent):
        """Create status display section with enhanced styling"""
        
        # Status frame with standard styling
        status_frame = ttk.LabelFrame(parent, text="Status & Information", padding=15)
        status_frame.pack(fill='both', expand=True)
        
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
        startup_text = """Welcome to Knight Logics Auto Video Editor & Compiler!

********* INSTRUCTIONS *********

Professional Video Compilation Tool
Automatically combines multiple short clips into one polished video with intro and music.

[PATHS] VIDEO INPUT PATH: Select folder containing your video clips
   * IMPORTANT: Will process ALL videos in this folder
   * Only processes video files (MP4, AVI, MOV, MKV, etc.)
   * Skips files larger than 500MB to prevent hanging

[TIME] TRIM SECONDS: Duration to take from the END of each video
   * Example: 30 = last 30 seconds of each video file
   * All clips will be standardized to this same duration

[MUSIC] MUSIC SELECTION: Background music for your compilation
   * Choose from included royalty-free tracks
   * Music loops/extends to match total video length
   * Mixed at lower volume so original audio stays clear

[INTRO] INTRO SELECTION: Optional intro video to start compilation
   * Adds professional touch to your final video
   * Intro duration matches your trim seconds setting

[RUN] COMPILE VIDEOS: Starts the compilation process
   * Creates: Intro + All Clips + Background Music = Final Video
   * Progress shown in this status area
   * Output saved to your Videos folder

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
        self.paths_text.delete(1.0, tk.END)
        
        input_path = self.input_path_var.get()
        output_path = self.output_path_var.get()
        
        # Enhanced display with status indicators
        display_text = "[FOLDER] FOLDER CONFIGURATION:\n"
        display_text += "-" * 50 + "\n"
        display_text += f"[INPUT] Input:  {input_path if input_path else '[ERROR] Not set - Click Browse button'}\n"
        display_text += f"[OUTPUT] Output: {output_path if output_path else '[ERROR] Not set - Click Browse button'}\n"
        display_text += f"[MUSIC] Music:  {os.path.join(os.path.dirname(__file__), 'Music')} ({len(self.get_music_files())} tracks) [OK]\n"
        display_text += f"Intros: {os.path.join(os.path.dirname(__file__), 'Intros')} ({len(self.get_intro_files())} videos) [OK]\n"
        display_text += f"[TOOLS] FFmpeg: Included in package [OK]\n"
        display_text += "-" * 50 + "\n"
        
        # Add status based on configuration
        if input_path and output_path:
            display_text += "[OK] Ready to compile videos!"
        else:
            display_text += "[WARN] Please set input and output folders above"
        
        self.paths_text.insert(1.0, display_text)
        
    def get_music_files(self):
        """Get list of available music files"""
        music_dir = os.path.join(os.path.dirname(__file__), "Music")
        if os.path.exists(music_dir):
            return [f for f in os.listdir(music_dir) if f.lower().endswith(('.mp3', '.wav', '.m4a'))]
        return []
        
    def get_intro_files(self):
        """Get list of available intro files"""
        intro_dir = os.path.join(os.path.dirname(__file__), "Intros")
        if os.path.exists(intro_dir):
            return [f for f in os.listdir(intro_dir) if f.lower().endswith(('.mp4', '.mov', '.avi'))]
        return []
    
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
        
        # FIXED: Clear status area BEFORE any operations that might log messages
        print("DEBUG: Clearing status text area BEFORE script path update")
        self.status_text.delete(1.0, tk.END)
        print("DEBUG: Status text cleared")
        
        # Update the main script with these paths
        self.update_main_script_paths(input_path, output_path)
        
        # Reset and disable run button for new compilation
        self.run_btn.configure(state='disabled', text="Compiling... Please Wait", bg=self.colors['warning'])
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
        
        try:
            # Set up environment variables for the compilation
            os.environ['GUI_MODE'] = '1'  # Prevent waiting for input
            os.environ['VIDEO_INPUT_PATH'] = self.input_path_var.get()
            os.environ['VIDEO_OUTPUT_PATH'] = self.output_path_var.get()
            os.environ['TRIM_SECONDS'] = self.trim_seconds_var.get()
            os.environ['MUSIC_SELECTION'] = self.music_selection_var.get()
            os.environ['INTRO_SELECTION'] = self.intro_selection_var.get()
            
            # Log the settings being used
            self.log_status(f"[CONFIG] Trim seconds: {self.trim_seconds_var.get()}")
            self.log_status(f"[CONFIG] Music selection: {self.music_selection_var.get()}")
            self.log_status(f"[CONFIG] Intro selection: {self.intro_selection_var.get()}")
            
            self.log_status("[PROCESS] Starting direct compilation...")
            
            if DIRECT_COMPILATION and hasattr(UOVidCompiler, 'main'):
                # Run compilation directly with live output capture
                self.log_status("[OK] Running compilation directly in same process...")
                
                # CRITICAL: Update the CONFIG dictionary directly since module is already imported
                if hasattr(UOVidCompiler, 'CONFIG'):
                    trim_selection = self.trim_seconds_var.get()
                    trim_value = None if trim_selection == 'None' else int(trim_selection)
                    UOVidCompiler.CONFIG['intro_selection'] = self.intro_selection_var.get()
                    UOVidCompiler.CONFIG['music_selection'] = self.music_selection_var.get()
                    UOVidCompiler.CONFIG['trim_seconds'] = trim_value
                    UOVidCompiler.CONFIG['clip_duration'] = float(trim_value) if trim_value is not None else 999999.0
                    UOVidCompiler.CONFIG['video_folder'] = self.input_path_var.get()
                    UOVidCompiler.CONFIG['output_folder'] = self.output_path_var.get()
                    self.log_status("[OK] CONFIG dictionary updated with GUI selections")
                
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
                    # Disable logging to prevent the 'NoneType' write errors
                    import logging
                    logging.disable(logging.CRITICAL)
                    
                    # Run the main compilation function directly
                    UOVidCompiler.main()
                    success = True
                    self.log_status("[SUCCESS] Direct compilation completed successfully!")
                    
                except Exception as e:
                    success = False
                    self.log_status(f"[ERROR] Compilation error: {str(e)}")
                finally:
                    # Re-enable logging
                    logging.disable(logging.NOTSET)
                    
                    # Restore original stdout/stderr
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                            
            else:
                # Fallback to subprocess if direct import failed
                self.log_status("[WARNING] Falling back to subprocess method...")
                success = self._run_subprocess_compilation()
                
        except Exception as e:
            success = False
            self.log_status(f"[ERROR] Thread error: {str(e)}")
            print(f"DEBUG: Thread exception: {e}")
        
        # Handle completion on main thread
        self.root.after(0, lambda: self._handle_compilation_completion(success))
                
    def _handle_compilation_completion(self, success):
        """Handle completion of compilation process"""
        if success:
            self.log_status("[SUCCESS] Video compilation completed successfully!")
            messagebox.showinfo("Success!", 
                "Video compilation completed successfully!\n\nYour compiled video is ready in the output folder.")
            self.run_btn.configure(
                state='normal', 
                text="[OK] Compilation Complete! Click to Compile Again",
                bg=self.colors['success'])
        else:
            self.log_status("[ERROR] Compilation failed")
            messagebox.showerror("Compilation Failed", 
                "Compilation failed\n\nCheck the status log for details.")
            self.run_btn.configure(
                state='normal', 
                text="[ERROR] Compilation Failed - Click to Try Again",
                bg=self.colors['error'])
                
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
            env['INTRO_SELECTION'] = self.intro_selection_var.get()
            
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
            return False
        
        finally:
            # Only reset button if it hasn't been set by success/error handlers above
            # This ensures the success/error messages remain visible
            pass
    
    def test_subprocess_output(self):
        """Test basic subprocess output capture"""
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
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
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
        music_path = os.path.join(os.path.dirname(__file__), "Music")
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
        intro_path = os.path.join(os.path.dirname(__file__), "Intros")
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
                
                # Restore selection if still valid, otherwise default to StockDefault
                if current_selection in intro_options:
                    self.intro_selection_var.set(current_selection)
                else:
                    self.intro_selection_var.set(intro_options[0] if intro_options else 'StockDefault')
                
                self.log_status(f"[OK] Intro list refreshed - {len(intro_options)} videos available")
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
            music_dir = os.path.join(os.path.dirname(__file__), "Music")
            if os.path.exists(music_dir):
                return set(f for f in os.listdir(music_dir) 
                          if f.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')))
        except Exception:
            pass
        return set()
    
    def get_intro_file_set(self):
        """Get set of intro filenames for comparison"""
        try:
            intro_dir = os.path.join(os.path.dirname(__file__), "Intros")
            if os.path.exists(intro_dir):
                return set(f for f in os.listdir(intro_dir) 
                          if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')))
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
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Remove problematic Unicode characters for standalone EXE compatibility
        safe_message = message
        if getattr(sys, 'frozen', False):
            # Running from executable - replace any remaining Unicode characters with ASCII
            # Use only ASCII in the replacement process
            safe_message = safe_message.encode('ascii', errors='replace').decode('ascii')
        
        log_message = f"[{timestamp}] {safe_message}\n"
        
        try:
            # Ensure widget is normal state and insert text
            self.status_text.config(state='normal')
            self.status_text.insert('end', log_message)
            self.status_text.see('end')
            
            # Force immediate updates
            self.status_text.update()
            self.root.update()
            
            # Keep log reasonable size (last 1000 lines)
            lines = self.status_text.get('1.0', 'end').split('\n')
            if len(lines) > 1000:
                self.status_text.delete('1.0', f"{len(lines)-1000}.0")
                
        except Exception as e:
            print(f"ERROR in log_status: {e}")
    
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
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
        
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
                "intro_selection": getattr(self, 'intro_selection_var', tk.StringVar()).get()
                # Resolution auto-detected - no GUI config needed
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def load_saved_paths(self):
        """Load previously saved configuration"""
        if hasattr(self, 'input_path_var'):
            self.input_path_var.set(self.config.get("input_path", os.path.expanduser("~/Videos/Captures")))
        if hasattr(self, 'output_path_var'):
            self.output_path_var.set(self.config.get("output_path", os.path.expanduser("~/Downloads")))
        if hasattr(self, 'trim_seconds_var'):
            self.trim_seconds_var.set(self.config.get("trim_seconds", "10"))
        if hasattr(self, 'music_selection_var'):
            self.music_selection_var.set(self.config.get("music_selection", ""))
        if hasattr(self, 'intro_selection_var'):
            self.intro_selection_var.set(self.config.get("intro_selection", ""))
        # Resolution auto-detected by main script - no GUI config needed
        self.update_paths_display()
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")
    
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
            instruction_window.geometry("450x300")
            instruction_window.resizable(False, False)
            instruction_window.configure(bg='white')
            
            # Set icon for popup window
            try:
                ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
                if os.path.exists(ico_path):
                    instruction_window.iconbitmap(ico_path)
            except:
                pass
            
            # Center the window on the parent GUI
            instruction_window.transient(self.root)
            instruction_window.grab_set()
            
            # Calculate center position
            self.root.update_idletasks()
            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            main_width = self.root.winfo_width()
            main_height = self.root.winfo_height()
            
            window_width = 450
            window_height = 300
            center_x = main_x + (main_width - window_width) // 2
            center_y = main_y + (main_height - window_height) // 2
            
            instruction_window.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
            
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
            qr_window.geometry("450x550")
            qr_window.resizable(False, False)
            qr_window.configure(bg='white')
            
            # Set icon for popup window
            try:
                ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
                if os.path.exists(ico_path):
                    qr_window.iconbitmap(ico_path)
            except:
                pass
            
            # Center the window on the parent GUI
            qr_window.transient(self.root)
            qr_window.grab_set()
            
            # Calculate position to center on main window
            self.root.update_idletasks()  # Ensure main window geometry is updated
            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            main_width = self.root.winfo_width()
            main_height = self.root.winfo_height()
            
            qr_width = 450
            qr_height = 550
            
            # Center position calculation
            center_x = main_x + (main_width - qr_width) // 2
            center_y = main_y + (main_height - qr_height) // 2
            
            qr_window.geometry(f"{qr_width}x{qr_height}+{center_x}+{center_y}")
            
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

    def check_for_updates(self):
        """Check GitHub for newer version and prompt user to update"""
        try:
            # Only check if running from executable (not development)
            if not getattr(sys, 'frozen', False):
                return
            
            api_url = f"https://api.github.com/repos/{self.GITHUB_REPO}/releases/latest"
            
            # Make request with timeout
            req = urllib.request.Request(api_url, headers={'User-Agent': 'BMagic-AutoVidCompiler'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                
            latest_version = data['tag_name'].lstrip('v')  # Remove 'v' prefix if present
            
            # Compare versions
            if self.compare_versions(latest_version, self.VERSION):
                # New version available
                download_url = None
                for asset in data.get('assets', []):
                    if asset['name'].endswith('.exe'):
                        download_url = asset['browser_download_url']
                        break
                
                if download_url:
                    # Show update prompt on main thread
                    self.root.after(0, lambda: self.prompt_update(latest_version, download_url, data.get('body', '')))
                
        except Exception as e:
            # Silently fail - don't interrupt user experience for update check failures
            print(f"Update check failed: {e}")
    
    def compare_versions(self, version1, version2):
        """Compare two version strings (returns True if version1 > version2)"""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad shorter version with zeros
            while len(v1_parts) < len(v2_parts):
                v1_parts.append(0)
            while len(v2_parts) < len(v1_parts):
                v2_parts.append(0)
            
            return v1_parts > v2_parts
        except:
            return False
    
    def prompt_update(self, new_version, download_url, changelog):
        """Show update dialog and handle download"""
        message = f"New version available: v{new_version}\n"
        message += f"Current version: v{self.VERSION}\n\n"
        
        if changelog:
            # Show first 200 chars of changelog
            message += f"Changes:\n{changelog[:200]}"
            if len(changelog) > 200:
                message += "...\n"
        
        message += "\n\nWould you like to download and install the update?"
        
        if messagebox.askyesno("Update Available", message):
            self.download_and_install_update(download_url)
    
    def download_and_install_update(self, download_url):
        """Download and install update"""
        try:
            self.log_status("[UPDATE] Downloading update...")
            
            # Get current executable path
            current_exe = sys.executable if getattr(sys, 'frozen', False) else __file__
            
            # Download next to current exe with .new extension
            new_exe_path = current_exe.replace('.exe', '_NEW.exe')
            
            with urllib.request.urlopen(download_url, timeout=60) as response:
                with open(new_exe_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            
            self.log_status("[OK] Update downloaded successfully!")
            
            # Create batch file updater (works better than Python for .exe replacement)
            batch_script = f'''@echo off
REM Wait for app to fully close and release all file locks
timeout /t 3 /nobreak >nul

REM Try to delete old exe, retry if locked
:retry_delete
del /f /q "{current_exe}" 2>nul
if exist "{current_exe}" (
    timeout /t 1 /nobreak >nul
    goto retry_delete
)

REM Move new version to replace old
move /y "{new_exe_path}" "{current_exe}"

REM Wait a moment before restarting to ensure file system is ready
timeout /t 1 /nobreak >nul

REM Start the updated version
start "" "{current_exe}"

REM Clean up this batch file
del "%~f0"
'''
            
            batch_path = os.path.join(os.path.dirname(current_exe), "updater.bat")
            with open(batch_path, 'w') as f:
                f.write(batch_script)
            
            messagebox.showinfo("Update Ready", 
                              "Update will be installed when you close the application.\n"
                              "The program will restart automatically.")
            
            # Store batch path for execution on close
            self.updater_batch_path = batch_path
            
        except Exception as e:
            self.log_error(f"Update download failed: {e}")
            messagebox.showerror("Update Failed", f"Could not download update:\n{e}")

    def on_closing(self):
        """Handle application closing"""
        self.stop_folder_monitoring()
        self.save_config()
        
        # Run updater batch file if pending
        if hasattr(self, 'updater_batch_path') and os.path.exists(self.updater_batch_path):
            # Run batch file silently in background - completely detached from parent process
            subprocess.Popen(['cmd.exe', '/c', self.updater_batch_path], 
                           creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                           close_fds=True,
                           shell=False)
        
        self.root.destroy()
        
        # Ensure clean exit for PyInstaller apps
        import sys
        sys.exit(0)
    
    def run(self):
        """Start the GUI application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

def main():
    """Main application entry point"""
    try:
        app = UOVidCompilerGUI()
        app.run()
    except Exception as e:
        import traceback
        error_msg = f"Error starting UO Video Compiler GUI:\n{traceback.format_exc()}"
        print(error_msg)
        
        # Try to show error in messagebox if possible
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Application Error", error_msg)
        except:
            pass

if __name__ == "__main__":
    main()
