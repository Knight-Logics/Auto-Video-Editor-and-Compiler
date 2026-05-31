#!/usr/bin/env python3
"""
UO Video Compiler - GUI Control Panel with Tabbed Interface
Professional Windows application for UO video compilation and auto-clipping

MODULAR STRUCTURE:
- This file: Main GUI shell with shared components (header, donations, styles)
- tab_auto_clipper.py: Auto Clipper tab (coming soon)
- tab_vid_compiler.py: Vid Compiler tab (original functionality)
"""

import sys
import os

# Add local python libraries to path (for portable distribution)
script_dir = os.path.dirname(os.path.abspath(__file__))
python_libs_dir = os.path.join(script_dir, "python-libs")
if os.path.exists(python_libs_dir):
    sys.path.insert(0, python_libs_dir)

import tkinter as tk
from tkinter import ttk, messagebox
import json
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

# Import tab modules
from tab_auto_clipper import AutoClipperTab
from tab_vid_compiler import VidCompilerTab


class UOVidCompilerGUI:
    """Main application with tabbed interface"""
    
    # Version info for auto-updates
    VERSION = "1.2.1"  # Updated for tabbed interface
    GITHUB_REPO = "Knight-Logics/Auto-Video-Editor-and-Compiler"
    
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
        
        # Dictionary to store button image references (prevents garbage collection)
        self.button_images = {}
        
        # Set icon IMMEDIATELY for taskbar
        self.set_taskbar_icon()
        
        # Load PNG logo for GUI use BEFORE creating widgets
        self.load_png_logo()
        
        # Load payment method logos
        self.load_payment_logos()
        
        # Load button icons
        self.load_button_icons()
        
        self.root.title("Auto Video Editor & Compiler - Control Panel")
        self.root.geometry("950x920")
        self.root.minsize(900, 920)
        self.root.resizable(True, True)
        
        # Set application icon
        self.setup_icon()
        
        # Setup GUI AFTER logo is loaded
        self.setup_styles()
        self.create_widgets()
        
        # Center window
        self.center_window()
        
        # Check for updates on startup (in background thread)
        threading.Thread(target=self.check_for_updates, daemon=True).start()
    
    def set_taskbar_icon(self):
        """Set taskbar icon immediately upon window creation"""
        try:
            ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
                
                try:
                    import ctypes
                    app_id = 'BMagic.UOVidCompiler.GUI.1.2'
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
                except Exception as e:
                    print(f"Windows App ID setting failed: {e}")
                
                print(f"TASKBAR ICON SET: {ico_path}")
            else:
                print(f"ERROR: ICO file not found: {ico_path}")
        except Exception as e:
            print(f"CRITICAL ERROR setting taskbar icon: {e}")
    
    def load_png_logo(self):
        """Load PNG logo for GUI display"""
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "icons", "KnightLogicsVidCompiler_transparent.png")
            
            if os.path.exists(logo_path):
                logo_image = Image.open(logo_path)
                self.logo_large = logo_image.resize((150, 150), Image.Resampling.LANCZOS)
                self.logo_large_tk = ImageTk.PhotoImage(self.logo_large)
                
                self.icon_small = logo_image.resize((48, 48), Image.Resampling.LANCZOS)
                self.icon_tk = ImageTk.PhotoImage(self.icon_small)
                
                self.has_logo = True
                self.has_logo_tk = True
                
                print(f"[OK] PNG logo loaded: {logo_path}")
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
                button_icon_path = os.path.join(os.path.dirname(__file__), "icons", f"{payment}_button_icon.png")
                
                if os.path.exists(button_icon_path):
                    img = Image.open(button_icon_path)
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    self.payment_logos[payment] = ImageTk.PhotoImage(img)
                    print(f"[OK] Loaded {payment} payment logo")
                else:
                    print(f"[WARN] Payment logo not found: {button_icon_path}")
                    
            except Exception as e:
                print(f"[ERROR] Failed to load {payment} payment logo: {e}")
        
        print(f"[TARGET] Payment logos loaded: {len(self.payment_logos)}/5")
    
    def setup_icon(self):
        """Setup application icon from ICO file"""
        try:
            ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
            
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
                self.root.iconbitmap(default=ico_path)
                print(f"ICO taskbar icon set: {ico_path}")
                
                try:
                    self.root.wm_iconbitmap(ico_path)
                except Exception as e:
                    print(f"wm_iconbitmap failed: {e}")
                    
                try:
                    self.root.update_idletasks()
                    self.root.focus_force()
                except Exception as e:
                    print(f"Taskbar refresh failed: {e}")
            else:
                print(f"ICO file not found: {ico_path}")
                
        except Exception as e:
            print(f"Could not load ICO icon: {e}")
    
    def setup_styles(self):
        """Setup modern styling with UO theme colors"""
        style = ttk.Style()
        
        # Configure colors and themes
        self.colors = {
            'bg': '#2a2a2a',
            'fg': '#2d3b2d',
            'accent': '#2E8B57',
            'button': '#228B22',
            'error': '#DC143C',
            'warning': '#DAA520',
            'success': '#32CD32',
            'frame_bg': '#404040',
            'entry_bg': '#ffffff',
            'text_bg': '#1e1e1e',
            'text_fg': '#00FF00',
            'title_color': '#2E8B57',
            'label_color': '#ffffff'
        }
        
        self.root.configure(bg=self.colors['frame_bg'])
        
        style.theme_use('clam')
        
        # Configure notebook tabs
        style.configure('TNotebook', background=self.colors['frame_bg'])
        style.configure('TNotebook.Tab', 
                       background=self.colors['bg'],
                       foreground=self.colors['label_color'],
                       padding=[20, 10],
                       font=('Segoe UI', 11, 'bold'))
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', 'white')])
        
        style.configure('Title.TLabel', 
                       background=self.colors['bg'], 
                       foreground=self.colors['title_color'],
                       font=('Segoe UI', 18, 'bold'))
        
        style.configure('Heading.TLabel',
                       background=self.colors['bg'],
                       foreground='#ffffff',
                       font=('Segoe UI', 12, 'bold'))
        
        style.configure('Info.TLabel',
                       background=self.colors['frame_bg'],
                       foreground=self.colors['label_color'],
                       font=('Segoe UI', 10))
                       
        style.configure('Custom.TFrame',
                       background=self.colors['frame_bg'],
                       relief='flat')
        
        style.configure('Header.TFrame',
                       background=self.colors['bg'],
                       relief='flat')
                       
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
        
        style.configure('TCombobox',
                       fieldbackground=self.colors['entry_bg'],
                       foreground=self.colors['fg'],
                       borderwidth=1)
    
    def create_widgets(self):
        """Create and arrange GUI widgets with tabbed interface"""
        
        # Main container with padding
        main_frame = ttk.Frame(self.root, style='Custom.TFrame')
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Header with logo and title (shared across all tabs)
        self.create_header(main_frame)
        
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True, pady=(10, 0))
        
        # Tab 1: Auto Clipper
        self.auto_clipper_frame = ttk.Frame(self.notebook, style='Custom.TFrame')
        self.notebook.add(self.auto_clipper_frame, text='Auto Clipper')
        self.auto_clipper = AutoClipperTab(self.auto_clipper_frame, self)
        
        # Tab 2: Vid Compiler
        self.vid_compiler_frame = ttk.Frame(self.notebook, style='Custom.TFrame')
        self.notebook.add(self.vid_compiler_frame, text='Vid Compiler')
        self.vid_compiler = VidCompilerTab(self.vid_compiler_frame, self)
    
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
                              bg=self.colors['bg'],
                              fg='white',
                              width=36,
                              height=36,
                              relief='flat',
                              borderwidth=0,
                              cursor='hand2',
                              command=command,
                              activebackground=self.colors['bg'])
                self.create_tooltip(btn, f"Donate via {name}")
                print(f"[OK] Created {name} button with official logo")
            else:
                # Fallback to text/emoji if logo not available
                fallback_icons = {
                    'venmo': 'V', 'paypal': 'P', 'bitcoin': 'B', 
                    'ethereum': 'E', 'solana': 'S'
                }
                btn = tk.Button(buttons_frame, 
                              text=fallback_icons.get(logo_key, 'P'),
                              font=('Segoe UI', 12, 'bold'),
                              bg=self.colors['bg'],
                              fg='white',
                              width=3,
                              height=1,
                              relief='flat',
                              borderwidth=0,
                              cursor='hand2',
                              command=command,
                              activebackground=self.colors['bg'])
                print(f"[WARN] Using fallback icon for {name} (logo not available)")
            btn.pack(side='left', padx=2)
            self.create_tooltip(btn, f"{name}: Click to {('open' if name in ['Venmo', 'PayPal'] else 'copy address')}")
    
    def create_donation_section(self, parent):
        """Create donation section (shared across tabs)"""
        donation_frame = ttk.Frame(parent, style='Header.TFrame')
        donation_frame.pack(side='right', padx=(20, 0), pady=10)
        
        header_frame = tk.Frame(donation_frame, bg=self.colors['bg'])
        header_frame.pack(pady=(0, 8))
        
        if hasattr(self, 'icons') and 'gift' in self.icons:
            gift_label = tk.Label(header_frame, image=self.icons['gift'], 
                                 bg=self.colors['bg'])
            gift_label.pack(side='left', padx=(0, 5))
            
        donate_label = ttk.Label(header_frame, text="Support Development", 
                               style='Heading.TLabel', font=('Segoe UI', 11, 'bold'))
        donate_label.pack(side='left')
        
        buttons_frame = ttk.Frame(donation_frame, style='Header.TFrame')
        buttons_frame.pack()
        
        payment_methods = [
            ('Venmo', 'venmo', self.colors['button'], lambda: self.open_venmo()),
            ('PayPal', 'paypal', '#0070ba', lambda: self.open_paypal()),
            ('Bitcoin', 'bitcoin', '#f7931a', lambda: self.copy_crypto_address('btc')),
            ('Ethereum', 'ethereum', '#627eea', lambda: self.copy_crypto_address('eth')),
            ('Solana', 'solana', '#14f195', lambda: self.copy_crypto_address('sol'))
        ]
        
        for i, (name, logo_key, color, command) in enumerate(payment_methods):
            if hasattr(self, 'payment_logos') and logo_key in self.payment_logos:
                btn = tk.Button(buttons_frame, 
                              image=self.payment_logos[logo_key],
                              bg=self.colors['bg'],
                              fg='white',
                              width=36,
                              height=36,
                              relief='flat',
                              borderwidth=0,
                              cursor='hand2',
                              command=command,
                              activebackground=self.colors['bg'])
                
                self.create_tooltip(btn, f"Donate via {name}")
            else:
                fallback_icons = {
                    'venmo': 'V', 'paypal': 'P', 'bitcoin': 'B', 
                    'ethereum': 'E', 'solana': 'S'
                }
                
                btn = tk.Button(buttons_frame, 
                              text=fallback_icons.get(logo_key, 'P'),
                              font=('Segoe UI', 12, 'bold'),
                              bg=self.colors['bg'],
                              fg='white',
                              width=3,
                              height=1,
                              relief='flat',
                              borderwidth=0,
                              cursor='hand2',
                              command=command,
                              activebackground=self.colors['bg'])
            
            btn.pack(side='left', padx=2)
            self.create_tooltip(btn, f"{name}: Click to {('open' if name in ['Venmo', 'PayPal'] else 'copy address')}")
    
    def create_auto_clipper_content(self, parent):
        """Create content for Auto Clipper tab"""
        # Main scrollable frame
        canvas = tk.Canvas(parent, bg=self.colors['frame_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Custom.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Welcome message
        welcome_frame = ttk.LabelFrame(scrollable_frame, text="Welcome to Auto Clipper", padding=20)
        welcome_frame.pack(fill='x', padx=20, pady=20)
        
        welcome_text = """
Auto Clipper - Coming Soon!

This feature will automatically detect and extract highlight moments from your gameplay videos.

Features planned:
• Automatic detection of kills, deaths, and significant events
• Configurable detection sensitivity
• Batch processing of multiple videos
• Smart clip duration optimization
• Preview before saving

Stay tuned for updates!
"""
        
        welcome_label = tk.Label(welcome_frame, text=welcome_text,
                               bg=self.colors['frame_bg'],
                               fg=self.colors['label_color'],
                               font=('Segoe UI', 11),
                               justify='left')
        welcome_label.pack(fill='both', expand=True)
        
        # Placeholder configuration
        config_frame = ttk.LabelFrame(scrollable_frame, text="Configuration (Preview)", padding=20)
        config_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        ttk.Label(config_frame, text="Detection Sensitivity:", style='Info.TLabel').grid(row=0, column=0, sticky='w', pady=5)
        sensitivity_var = tk.StringVar(value='Medium')
        ttk.Combobox(config_frame, textvariable=sensitivity_var, 
                    values=['Low', 'Medium', 'High'], state='readonly').grid(row=0, column=1, sticky='ew', padx=(10, 0))
        
        ttk.Label(config_frame, text="Clip Duration:", style='Info.TLabel').grid(row=1, column=0, sticky='w', pady=5)
        duration_var = tk.StringVar(value='15')
        ttk.Combobox(config_frame, textvariable=duration_var,
                    values=['10', '15', '20', '30'], state='readonly').grid(row=1, column=1, sticky='ew', padx=(10, 0))
        
        config_frame.grid_columnconfigure(1, weight=1)
        
        # Status
        status_frame = ttk.LabelFrame(scrollable_frame, text="Status", padding=15)
        status_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        status_text = tk.Text(status_frame, height=10, wrap='word',
                            bg=self.colors['text_bg'],
                            fg=self.colors['text_fg'],
                            font=('Consolas', 10))
        status_text.pack(fill='both', expand=True)
        status_text.insert('end', "[INFO] Auto Clipper feature coming in next update!\n")
        status_text.insert('end', "[INFO] Switch to 'Vid Compiler' tab for current functionality.\n")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
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
            self.icons = {}
    
    def create_button_icon(self, icon_type, size=(16, 16)):
        """Create simple icon images for buttons"""
        from PIL import Image, ImageDraw
        
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        if icon_type == 'folder':
            draw.rectangle([(2, 6), (14, 13)], fill=(255, 215, 0), outline=(200, 150, 0))
            draw.rectangle([(2, 4), (8, 6)], fill=(255, 215, 0), outline=(200, 150, 0))
        elif icon_type == 'test':
            draw.ellipse([(4, 4), (12, 12)], fill=(100, 150, 255), outline=(50, 100, 200))
            draw.ellipse([(6, 6), (10, 10)], fill=(255, 255, 255))
        elif icon_type == 'logs':
            draw.rectangle([(4, 2), (12, 14)], fill=(255, 255, 255), outline=(128, 128, 128))
            draw.line([(5, 5), (11, 5)], fill=(128, 128, 128))
            draw.line([(5, 7), (11, 7)], fill=(128, 128, 128))
            draw.line([(5, 9), (11, 9)], fill=(128, 128, 128))
        elif icon_type == 'output':
            draw.rectangle([(2, 4), (10, 12)], fill=(100, 255, 100), outline=(50, 200, 50))
            draw.polygon([(10, 6), (14, 8), (10, 10)], fill=(50, 200, 50))
        elif icon_type == 'video':
            draw.rectangle([(2, 5), (10, 11)], fill=(255, 100, 100), outline=(200, 50, 50))
            draw.polygon([(10, 6), (14, 8), (10, 10)], fill=(200, 50, 50))
        elif icon_type == 'music':
            draw.ellipse([(4, 10), (8, 14)], fill=(255, 150, 255), outline=(200, 100, 200))
            draw.rectangle([(8, 3), (9, 11)], fill=(200, 100, 200))
            draw.arc([(9, 3), (13, 7)], 270, 90, fill=(200, 100, 200))
        elif icon_type == 'config':
            draw.rectangle([(4, 2), (12, 14)], fill=(200, 200, 200), outline=(150, 150, 150))
            draw.rectangle([(6, 4), (10, 6)], fill=(100, 100, 255))
            draw.rectangle([(6, 8), (10, 10)], fill=(100, 100, 255))
            draw.rectangle([(6, 12), (10, 14)], fill=(100, 100, 255))
        elif icon_type == 'gift':
            draw.ellipse([3, 4, 7, 8], fill=(255, 100, 100))
            draw.ellipse([9, 4, 13, 8], fill=(255, 100, 100))
            draw.polygon([(3, 7), (13, 7), (8, 13)], fill=(255, 100, 100))
        
        return ImageTk.PhotoImage(img)
    
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
    
    # Donation methods (reuse existing ones)
    def open_venmo(self):
        """Open Venmo payment - placeholder"""
        messagebox.showinfo("Venmo", f"Venmo: {self.DONATION_INFO['venmo']}")
    
    def open_paypal(self):
        """Open PayPal payment - placeholder"""
        messagebox.showinfo("PayPal", f"PayPal: {self.DONATION_INFO['paypal']}")
    
    def copy_crypto_address(self, crypto_type):
        """Copy crypto address - placeholder"""
        address = self.DONATION_INFO.get(crypto_type, '')
        messagebox.showinfo("Crypto", f"{crypto_type.upper()}: {address}")
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception as e:
            print(f"Error copying to clipboard: {e}")
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")
    
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
            "output_path": os.path.expanduser("~/Downloads"),
            "auto_clipper": {},
            "vid_compiler": {}
        }
    
    def save_config(self):
        """Save current configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def save_tab_config(self, tab_name, tab_config):
        """Save configuration for a specific tab"""
        self.config[tab_name] = tab_config
        self.save_config()
    
    def check_for_updates(self):
        """Check for updates (placeholder)"""
        pass
    
    def on_closing(self):
        """Handle application closing"""
        # Stop monitoring in vid compiler tab
        if hasattr(self, 'vid_compiler'):
            self.vid_compiler.stop_folder_monitoring()
        
        self.save_config()
        self.root.destroy()
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
        error_msg = f"Error starting application:\n{traceback.format_exc()}"
        print(error_msg)
        
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
