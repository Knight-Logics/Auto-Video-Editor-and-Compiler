#!/usr/bin/env python3
"""
Vid Compiler Tab - Original video compilation functionality
Extracted from UOVidCompiler_GUI.py for modular design
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import subprocess
import sys
import threading
from PIL import Image, ImageTk
import tempfile

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARN] OpenCV not available - video thumbnails disabled")

try:
    import UOVidCompiler
    DIRECT_COMPILATION = True
except ImportError:
    DIRECT_COMPILATION = False


class VidCompilerTab:
    """Video Compiler tab functionality"""
    
    def __init__(self, parent_frame, main_app):
        """
        Initialize Vid Compiler tab
        
        Args:
            parent_frame: The ttk.Frame that this tab lives in
            main_app: Reference to the main UOVidCompilerGUI instance for accessing shared resources
        """
        self.parent = parent_frame
        self.app = main_app
        
        # Initialize path variables
        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        
        # Initialize video configuration variables
        self.trim_seconds_var = tk.StringVar()
        self.music_selection_var = tk.StringVar()
        self.intro_selection_var = tk.StringVar()
        
        # File monitoring state
        self.last_music_files = set()
        self.last_intro_files = set()
        self.monitoring_active = False
        
        # Thumbnail cache
        self.thumbnail_cache = {}
        self.thumbnail_labels = []
        self.last_video_files = set()
        
        # Create the tab content
        self.create_content()
        
        # Load saved paths
        self.load_saved_paths()
        
        # Start folder monitoring
        self.start_folder_monitoring()
    
    def create_content(self):
        """Create all content for the Vid Compiler tab"""
        # Main scrollable frame for tab content
        canvas = tk.Canvas(self.parent, bg=self.app.colors['frame_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Custom.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Make canvas expand with window
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_frame, width=event.width)
        canvas.bind('<Configure>', on_canvas_configure)
        
        # Configuration section
        self.create_config_section(scrollable_frame)
        
        # Video thumbnail viewer
        self.create_thumbnail_section(scrollable_frame)
        
        # Action buttons
        self.create_action_section(scrollable_frame)
        
        # Status area
        self.create_status_section(scrollable_frame)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_config_section(self, parent):
        """Create configuration input section"""
        config_frame = ttk.LabelFrame(parent, text="Path Configuration", padding=20)
        config_frame.pack(fill='x', pady=(20, 20), padx=20)
        
        # Input folder
        self.create_path_row(config_frame, "Input Video Folder:", "input_path", 
                           "Select folder containing your UO gameplay videos",
                           is_directory=True, row=0)
        
        # Output folder  
        self.create_path_row(config_frame, "[OUTPUT] Output Video Folder:", "output_path",
                           "Select folder where compiled videos will be saved", 
                           is_directory=True, row=1)
        
        # Current paths display
        current_frame = ttk.Frame(config_frame, style='Custom.TFrame')
        current_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(20, 0))
        
        paths_label = ttk.Label(current_frame, text="[LIST] Current Configuration:", style='Heading.TLabel')
        paths_label.pack(anchor='w', pady=(0, 5))
        
        self.paths_text = tk.Text(current_frame, height=5, wrap='word', 
                                 bg=self.app.colors['text_bg'], 
                                 fg=self.app.colors['text_fg'], 
                                 font=('Consolas', 9),
                                 borderwidth=2,
                                 relief='sunken',
                                 insertbackground=self.app.colors['accent'])
        self.paths_text.pack(fill='x', pady=5)
    
    def create_path_row(self, parent, label_text, config_key, tooltip, is_directory=True, row=0):
        """Create a path selection row"""
        # Label
        label = ttk.Label(parent, text=label_text, style='Info.TLabel')
        label.grid(row=row, column=0, sticky='w', padx=(0, 10), pady=5)
        
        # Entry
        entry_var = getattr(self, f"{config_key}_var")
        entry = ttk.Entry(parent, textvariable=entry_var, width=55, style='Custom.TEntry')
        entry.grid(row=row, column=1, sticky='ew', padx=(0, 15), pady=8)
        
        # Browse button
        browse_cmd = lambda: self.browse_path(entry_var, is_directory, tooltip)
        browse_btn = tk.Button(parent, text="Browse", 
                              image=self.app.icons['folder'],
                              compound='left',
                              command=browse_cmd, 
                              font=('Arial', 9),
                              bg=self.app.colors['button'],
                              fg='white',
                              relief='raised',
                              width=80,
                              padx=8)
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
    
    def create_action_section(self, parent):
        """Create action buttons section with video configuration options"""
        action_frame = ttk.Frame(parent, style='Custom.TFrame')
        action_frame.pack(fill='x', pady=(0, 20), padx=20)
        
        # Video Configuration Options
        config_options_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        config_options_frame.pack(fill='x', pady=(0, 20))
        
        options_container = ttk.Frame(config_options_frame, style='Custom.TFrame')
        options_container.pack(fill='x', pady=(0, 10))
        
        # Configure grid
        options_container.grid_columnconfigure(0, weight=1)
        options_container.grid_columnconfigure(1, weight=1)
        options_container.grid_columnconfigure(2, weight=1)
        
        # Trim seconds
        trim_frame = ttk.Frame(options_container, style='Custom.TFrame')
        trim_frame.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        
        ttk.Label(trim_frame, text="[TIME] Trim End:", style='Info.TLabel').pack(anchor='w')
        trim_options = ['None', '5', '10', '15', '20', '25', '30']
        self.trim_seconds_var.set('15')
        trim_combo = ttk.Combobox(trim_frame, textvariable=self.trim_seconds_var, 
                                values=trim_options, state='readonly')
        trim_combo.pack(fill='x', pady=(2, 0))
        
        # Background Music
        music_frame = ttk.Frame(options_container, style='Custom.TFrame')
        music_frame.grid(row=0, column=1, sticky='ew', padx=5)

        ttk.Label(music_frame, text="[MUSIC] Music:", style='Info.TLabel').pack(anchor='w')
        music_options = self.get_available_music()
        if not self.music_selection_var.get() and music_options:
            self.music_selection_var.set(music_options[0])
        self.music_combo = ttk.Combobox(music_frame, textvariable=self.music_selection_var,
                                 values=music_options, state='readonly')
        self.music_combo.pack(fill='x', pady=(2, 0))

        # Intro Video
        intro_frame = ttk.Frame(options_container, style='Custom.TFrame')
        intro_frame.grid(row=0, column=2, sticky='ew', padx=(10, 0))

        ttk.Label(intro_frame, text="Intro Video:", style='Info.TLabel').pack(anchor='w')
        intro_options = self.get_available_intros()
        if not self.intro_selection_var.get() and intro_options:
            self.intro_selection_var.set(intro_options[0])
        self.intro_combo = ttk.Combobox(intro_frame, textvariable=self.intro_selection_var,
                                 values=intro_options, state='readonly')
        self.intro_combo.pack(fill='x', pady=(2, 0))
        
        # Main action button
        main_button_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        main_button_frame.pack(fill='x', pady=(0, 15))
        
        self.run_btn = tk.Button(main_button_frame, 
                               text="RUN VIDEO COMPILER", 
                               command=self.run_compiler,
                               bg=self.app.colors['accent'], 
                               fg='white',
                               font=('Segoe UI', 14, 'bold'),
                               relief='raised',
                               borderwidth=3,
                               pady=15,
                               cursor='hand2')
        self.run_btn.pack(fill='x')
        
        # Secondary buttons
        secondary_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        secondary_frame.pack(fill='x')
        
        action_buttons = [
            ("View Logs", self.view_logs, 'logs'),
            ("Output Folder", self.open_output_folder, 'output'),
            ("Intro Videos", self.open_intro_folder, 'video'),
            ("Music Folder", self.open_music_folder, 'music')
        ]
        
        for text, command, icon_key in action_buttons:
            btn = tk.Button(
                secondary_frame, 
                text=text,
                image=self.app.icons[icon_key],
                compound='left',
                command=command,
                font=('Arial', 9),
                bg=self.app.colors['button'],
                fg='white',
                relief='raised',
                width=90,
                padx=8,
                pady=4
            )
            btn.pack(side='left', padx=(0, 10))
    
    def create_status_section(self, parent):
        """Create status display section"""
        status_frame = ttk.LabelFrame(parent, text="Status & Information", padding=15)
        status_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        self.status_text = tk.Text(status_frame, height=15, width=80, wrap='word',
                                  bg=self.app.colors['text_bg'],
                                  fg=self.app.colors['text_fg'],
                                  font=('Consolas', 11),
                                  borderwidth=2,
                                  relief='sunken',
                                  insertbackground=self.app.colors['accent'])
        
        scrollbar = ttk.Scrollbar(status_frame, orient='vertical', command=self.status_text.yview)
        
        self.status_text.pack(side='left', fill='both', expand=True, padx=(0, 5))
        scrollbar.pack(side='right', fill='y')
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        # Initial instructions
        startup_text = """Welcome to Vid Compiler!

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
        
        # Add color coding
        self.status_text.tag_configure("success", foreground=self.app.colors['success'])
        self.status_text.tag_configure("info", foreground=self.app.colors['text_fg'])
        self.status_text.tag_configure("warning", foreground=self.app.colors['warning'])
        self.status_text.tag_configure("error", foreground=self.app.colors['error'])
    
    # Helper methods
    def get_available_music(self):
        """Get list of available music files"""
        try:
            music_dir = os.path.join(os.path.dirname(__file__), "Music")
            if not os.path.exists(music_dir):
                return ['None', '[RANDOM] Random']
            
            music_files = ['None', '[RANDOM] Random']
            for file in os.listdir(music_dir):
                if file.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    music_files.append(os.path.splitext(file)[0])
            
            return music_files if len(music_files) > 2 else ['None', '[RANDOM] Random']
        except Exception:
            return ['None', '[RANDOM] Random']
    
    def get_available_intros(self):
        """None, Stock, Random, and any intro files in the Intros folder."""
        intro_dir = os.path.join(os.path.dirname(__file__), "Intros")
        custom_names = []
        stock_found = False
        if os.path.isdir(intro_dir):
            for file in os.listdir(intro_dir):
                if not file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.gif')):
                    continue
                stem = os.path.splitext(file)[0]
                if stem == 'StockDefault':
                    stock_found = True
                else:
                    custom_names.append(stem)
        options = ['None']
        if stock_found:
            options.append('Stock')
        options.append('[RANDOM] Random')
        options.extend(sorted(custom_names))
        return options if options else ['None', '[RANDOM] Random']
    
    def update_paths_display(self):
        """Update the current paths display"""
        self.paths_text.delete(1.0, tk.END)
        
        input_path = self.input_path_var.get()
        output_path = self.output_path_var.get()
        
        display_text = "[FOLDER] FOLDER CONFIGURATION:\n"
        display_text += "-" * 50 + "\n"
        display_text += f"[INPUT] Input:  {input_path if input_path else '[ERROR] Not set - Click Browse button'}\n"
        display_text += f"[OUTPUT] Output: {output_path if output_path else '[ERROR] Not set - Click Browse button'}\n"
        display_text += f"[MUSIC] Music:  {os.path.join(os.path.dirname(__file__), 'Music')} ({len(self.get_music_files())} tracks) [OK]\n"
        display_text += f"Intros: {os.path.join(os.path.dirname(__file__), 'Intros')} ({len(self.get_intro_files())} videos) [OK]\n"
        display_text += f"[TOOLS] FFmpeg: Included in package [OK]\n"
        display_text += "-" * 50 + "\n"
        
        if input_path and output_path:
            display_text += "[OK] Ready to compile videos!"
        else:
            display_text += "[WARN] Please set input and output folders above"
        
        self.paths_text.insert(1.0, display_text)
    
    def create_thumbnail_section(self, parent):
        """Create video thumbnail preview section"""
        thumb_frame = ttk.LabelFrame(parent, text="Video Preview", padding=15)
        thumb_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        # Header with refresh button
        header_frame = ttk.Frame(thumb_frame, style='Custom.TFrame')
        header_frame.pack(fill='x', pady=(0, 10))
        
        info_label = ttk.Label(header_frame, 
                              text="Videos in Input Folder:",
                              style='Info.TLabel')
        info_label.pack(side='left')
        
        self.video_count_label = ttk.Label(header_frame,
                                           text="0 videos",
                                           style='Info.TLabel',
                                           foreground=self.app.colors['accent'])
        self.video_count_label.pack(side='left', padx=(5, 0))
        
        refresh_btn = tk.Button(header_frame,
                               text="🔄 Refresh",
                               command=self.refresh_thumbnails,
                               bg=self.app.colors['button'],
                               fg='white',
                               font=('Arial', 9),
                               relief='raised',
                               padx=10,
                               pady=2)
        refresh_btn.pack(side='right')
        
        # Scrollable thumbnail container
        thumb_canvas = tk.Canvas(thumb_frame, 
                                bg=self.app.colors['frame_bg'],
                                height=150,
                                highlightthickness=0)
        thumb_scrollbar = ttk.Scrollbar(thumb_frame, orient='horizontal', 
                                       command=thumb_canvas.xview)
        self.thumb_container = ttk.Frame(thumb_canvas, style='Custom.TFrame')
        
        self.thumb_container.bind(
            "<Configure>",
            lambda e: thumb_canvas.configure(scrollregion=thumb_canvas.bbox("all"))
        )
        
        thumb_canvas.create_window((0, 0), window=self.thumb_container, anchor="nw")
        thumb_canvas.configure(xscrollcommand=thumb_scrollbar.set)
        
        thumb_canvas.pack(fill='both', expand=True)
        thumb_scrollbar.pack(fill='x')
        
        # No videos message
        self.no_videos_label = tk.Label(self.thumb_container,
                                       text="No videos found in input folder\n\nSelect an input folder above to see video thumbnails",
                                       bg=self.app.colors['frame_bg'],
                                       fg=self.app.colors['label_color'],
                                       font=('Segoe UI', 10, 'italic'))
        self.no_videos_label.pack(pady=20)
        
        # Auto-refresh thumbnails when input path changes
        self.input_path_var.trace_add('write', lambda *args: self.refresh_thumbnails())
    
    def refresh_thumbnails(self):
        """Refresh video thumbnails from input folder"""
        if not CV2_AVAILABLE:
            return
        
        input_path = self.input_path_var.get().strip()
        if not input_path or not os.path.exists(input_path):
            # Clear thumbnails
            for label in self.thumbnail_labels:
                label.destroy()
            self.thumbnail_labels.clear()
            self.no_videos_label.pack(pady=20)
            self.video_count_label.config(text="0 videos")
            return
        
        # Get video files
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
        try:
            video_files = [
                f for f in os.listdir(input_path)
                if f.lower().endswith(video_extensions)
            ]
            video_files.sort()  # Sort alphabetically
        except Exception as e:
            self.log_error(f"Could not read input folder: {e}")
            return
        
        # Update count
        self.video_count_label.config(text=f"{len(video_files)} videos")
        
        if not video_files:
            # Show no videos message
            for label in self.thumbnail_labels:
                label.destroy()
            self.thumbnail_labels.clear()
            self.no_videos_label.pack(pady=20)
            return
        
        # Hide no videos message
        self.no_videos_label.pack_forget()
        
        # Clear old thumbnails
        for label in self.thumbnail_labels:
            label.destroy()
        self.thumbnail_labels.clear()
        
        # Create thumbnails (limit to first 20 for performance)
        max_thumbnails = 20
        for i, filename in enumerate(video_files[:max_thumbnails]):
            if i >= max_thumbnails:
                break
            
            filepath = os.path.join(input_path, filename)
            self.create_thumbnail(filepath, filename)
        
        # Show "and X more" if there are more videos
        if len(video_files) > max_thumbnails:
            more_label = tk.Label(self.thumb_container,
                                 text=f"...and {len(video_files) - max_thumbnails} more",
                                 bg=self.app.colors['frame_bg'],
                                 fg=self.app.colors['warning'],
                                 font=('Segoe UI', 9, 'italic'))
            more_label.pack(side='left', padx=10)
            self.thumbnail_labels.append(more_label)
    
    def create_thumbnail(self, video_path, filename):
        """Create a thumbnail for a video file"""
        try:
            # Check cache first
            if video_path in self.thumbnail_cache:
                thumb_img = self.thumbnail_cache[video_path]
            else:
                # Extract thumbnail using OpenCV
                cap = cv2.VideoCapture(video_path)
                success, frame = cap.read()
                cap.release()
                
                if not success:
                    return
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Convert to PIL Image and resize
                pil_image = Image.fromarray(frame_rgb)
                pil_image.thumbnail((120, 90), Image.Resampling.LANCZOS)
                
                # Cache the thumbnail
                thumb_img = ImageTk.PhotoImage(pil_image)
                self.thumbnail_cache[video_path] = thumb_img
            
            # Create frame for thumbnail
            thumb_frame = ttk.Frame(self.thumb_container, style='Custom.TFrame')
            thumb_frame.pack(side='left', padx=5, pady=5)
            
            # Thumbnail image
            img_label = tk.Label(thumb_frame,
                               image=thumb_img,
                               bg=self.app.colors['bg'],
                               relief='solid',
                               borderwidth=1)
            img_label.image = thumb_img  # Keep reference
            img_label.pack()
            
            # Filename label (truncated)
            display_name = filename if len(filename) <= 15 else filename[:12] + '...'
            name_label = tk.Label(thumb_frame,
                                text=display_name,
                                bg=self.app.colors['frame_bg'],
                                fg=self.app.colors['label_color'],
                                font=('Segoe UI', 8))
            name_label.pack()
            
            # Add tooltip with full filename
            self.create_tooltip(img_label, filename)
            
            # Store references
            self.thumbnail_labels.extend([thumb_frame, img_label, name_label])
            
        except Exception as e:
            print(f"Failed to create thumbnail for {filename}: {e}")
    
    def create_tooltip(self, widget, text):
        """Create tooltip for widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(tooltip, text=text,
                           background='lightyellow',
                           relief='solid',
                           borderwidth=1,
                           font=('Segoe UI', 9),
                           padx=5, pady=2)
            label.pack()
            
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
    
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
    
    # Action methods
    def run_compiler(self):
        """Run the video compiler with current settings"""
        print("DEBUG: run_compiler() called - ENTRY POINT")
        
        # Validate paths
        input_path = self.input_path_var.get().strip()
        output_path = self.output_path_var.get().strip()
        
        if not input_path or not output_path:
            self.log_error("Both input and output paths must be set!")
            messagebox.showerror("Configuration Error", "Please set both input and output paths!")
            return
            
        if not os.path.exists(input_path):
            self.log_error(f"Input path does not exist: {input_path}")
            messagebox.showerror("Path Error", f"Input path does not exist:\n{input_path}")
            return
            
        # Create output directory if needed
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path)
                self.log_success(f"Created output directory: {output_path}")
            except Exception as e:
                self.log_error(f"Could not create output directory: {e}")
                messagebox.showerror("Directory Error", f"Could not create output directory:\n{e}")
                return
        
        # Clear status
        self.status_text.delete(1.0, tk.END)
        
        # Update main script paths
        self.update_main_script_paths(input_path, output_path)
        
        # Disable run button
        self.run_btn.configure(state='disabled', text="Compiling... Please Wait", bg=self.app.colors['warning'])
        self.app.root.update_idletasks()
        
        self.log_status("[START] Starting video compilation process...")
        self.log_status(f"[INPUT] Input folder: {input_path}")
        self.log_status(f"[OUTPUT] Output folder: {output_path}")
        self.log_status("")
        
        # Run in separate thread
        threading.Thread(target=self.run_compiler_thread, daemon=True).start()
    
    def update_main_script_paths(self, input_path, output_path):
        """Update the main UOVidCompiler.py script paths"""
        if getattr(sys, 'frozen', False):
            self.log_status("Running from executable - paths will be passed via environment variables")
            return
        
        script_path = os.path.join(os.path.dirname(__file__), "UOVidCompiler.py")
        
        try:
            if not os.path.exists(script_path):
                self.log_status("Script file not found - paths will be passed via environment variables")
                return
                
            if not os.access(script_path, os.W_OK):
                self.log_status("Script file is read-only - paths will be passed via environment variables")
                return
            
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            
            content = re.sub(
                r'VIDEO_INPUT_PATH\s*=\s*r?"[^"]*"',
                f'VIDEO_INPUT_PATH = r"{input_path}"',
                content
            )
            
            content = re.sub(
                r'VIDEO_OUTPUT_PATH\s*=\s*r?"[^"]*"',
                f'VIDEO_OUTPUT_PATH = r"{output_path}"',
                content
            )
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.log_status("Updated script paths successfully")
            
        except Exception as e:
            self.log_status(f"Could not update script paths: {e}")
    
    def run_compiler_thread(self):
        """Run the compiler in a separate thread"""
        self.log_status("[START] Background compilation thread started")
        
        try:
            # Set up environment variables
            os.environ['GUI_MODE'] = '1'
            os.environ['VIDEO_INPUT_PATH'] = self.input_path_var.get()
            os.environ['VIDEO_OUTPUT_PATH'] = self.output_path_var.get()
            os.environ['TRIM_SECONDS'] = self.trim_seconds_var.get()
            os.environ['MUSIC_SELECTION'] = self.music_selection_var.get()
            os.environ['INTRO_SELECTION'] = self.intro_selection_var.get()
            
            self.log_status(f"[CONFIG] Trim seconds: {self.trim_seconds_var.get()}")
            self.log_status(f"[CONFIG] Music selection: {self.music_selection_var.get()}")
            self.log_status(f"[CONFIG] Intro selection: {self.intro_selection_var.get()}")
            
            self.log_status("[PROCESS] Starting direct compilation...")
            
            if DIRECT_COMPILATION and hasattr(UOVidCompiler, 'main'):
                self.log_status("[OK] Running compilation directly...")
                
                # Update CONFIG dictionary
                if hasattr(UOVidCompiler, 'CONFIG'):
                    trim_selection = self.trim_seconds_var.get()
                    trim_value = None if trim_selection == 'None' else int(trim_selection)
                    UOVidCompiler.CONFIG['intro_selection'] = self.intro_selection_var.get()
                    UOVidCompiler.CONFIG['music_selection'] = self.music_selection_var.get()
                    UOVidCompiler.CONFIG['trim_seconds'] = trim_value
                    UOVidCompiler.CONFIG['clip_duration'] = float(trim_value) if trim_value is not None else 999999.0
                    UOVidCompiler.CONFIG['video_folder'] = self.input_path_var.get()
                    UOVidCompiler.CONFIG['output_folder'] = self.output_path_var.get()
                    self.log_status("[OK] CONFIG dictionary updated")
                
                # Custom stdout
                class GUIOutputStream:
                    def __init__(self, log_func):
                        self.log_func = log_func
                        self.line_count = 0
                        
                    def write(self, text):
                        if text.strip():
                            self.line_count += 1
                            self.log_func(f"[{self.line_count}] {text.strip()}")
                    
                    def flush(self):
                        pass
                
                original_stdout = sys.stdout
                original_stderr = sys.stderr
                
                gui_output = GUIOutputStream(self.log_status)
                sys.stdout = gui_output
                sys.stderr = gui_output
                
                try:
                    import logging
                    logging.disable(logging.CRITICAL)
                    
                    UOVidCompiler.main()
                    success = True
                    self.log_status("[SUCCESS] Direct compilation completed!")
                    
                except Exception as e:
                    success = False
                    self.log_status(f"[ERROR] Compilation error: {str(e)}")
                finally:
                    logging.disable(logging.NOTSET)
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                            
            else:
                self.log_status("[WARNING] Falling back to subprocess method...")
                success = self._run_subprocess_compilation()
                
        except Exception as e:
            success = False
            self.log_status(f"[ERROR] Thread error: {str(e)}")
        
        # Handle completion
        self.app.root.after(0, lambda: self._handle_compilation_completion(success))
    
    def _handle_compilation_completion(self, success):
        """Handle completion of compilation"""
        if success:
            self.log_status("[SUCCESS] Video compilation completed!")
            messagebox.showinfo("Success!", 
                "Video compilation completed!\n\nYour compiled video is ready.")
            self.run_btn.configure(
                state='normal', 
                text="[OK] Compilation Complete! Click to Compile Again",
                bg=self.app.colors['success'])
        else:
            self.log_status("[ERROR] Compilation failed")
            messagebox.showerror("Compilation Failed", 
                "Compilation failed\n\nCheck the status log for details.")
            self.run_btn.configure(
                state='normal', 
                text="[ERROR] Compilation Failed - Click to Try Again",
                bg=self.app.colors['error'])
    
    def _run_subprocess_compilation(self):
        """Fallback subprocess compilation"""
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
    
    def view_logs(self):
        """View application logs"""
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        if os.path.exists(logs_dir):
            try:
                os.startfile(logs_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open logs directory:\n{e}")
        else:
            messagebox.showinfo("Info", "No logs directory found yet.")
    
    def open_output_folder(self):
        """Open the output folder"""
        output_path = self.output_path_var.get().strip()
        if output_path and os.path.exists(output_path):
            try:
                os.startfile(output_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open output folder:\n{e}")
        else:
            messagebox.showwarning("Warning", "Output folder not set or does not exist.")
    
    def open_music_folder(self):
        """Open the music folder"""
        music_path = os.path.join(os.path.dirname(__file__), "Music")
        if os.path.exists(music_path):
            try:
                os.startfile(music_path)
                self.app.root.after(1000, self.refresh_music_list)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open music folder:\n{e}")
        else:
            messagebox.showwarning("Warning", "Music folder not found.")
    
    def open_intro_folder(self):
        """Open the intro videos folder"""
        intro_path = os.path.join(os.path.dirname(__file__), "Intros")
        if os.path.exists(intro_path):
            try:
                os.startfile(intro_path)
                self.app.root.after(1000, self.refresh_intro_list)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open intro folder:\n{e}")
        else:
            messagebox.showwarning("Warning", "Intro folder not found.")
    
    def refresh_music_list(self):
        """Refresh the music dropdown"""
        try:
            music_options = self.get_available_music()
            current_selection = self.music_selection_var.get()
            
            if hasattr(self, 'music_combo'):
                self.music_combo['values'] = music_options
                
                if current_selection in music_options:
                    self.music_selection_var.set(current_selection)
                else:
                    self.music_selection_var.set(music_options[0] if music_options else '[RANDOM] Random')
                
                self.log_status(f"[OK] Music list refreshed - {len(music_options)} tracks")
        except Exception as e:
            self.log_error(f"Failed to refresh music list: {e}")
    
    def refresh_intro_list(self):
        """Refresh the intro dropdown"""
        try:
            intro_options = self.get_available_intros()
            current_selection = self.intro_selection_var.get()
            
            if hasattr(self, 'intro_combo'):
                self.intro_combo['values'] = intro_options
                
                if current_selection in intro_options:
                    self.intro_selection_var.set(current_selection)
                else:
                    self.intro_selection_var.set(intro_options[0] if intro_options else 'StockDefault')
                
                self.log_status(f"[OK] Intro list refreshed - {len(intro_options)} videos")
        except Exception as e:
            self.log_error(f"Failed to refresh intro list: {e}")
    
    # Folder monitoring
    def start_folder_monitoring(self):
        """Start monitoring folders for changes"""
        self.monitoring_active = True
        self.last_music_files = self.get_music_file_set()
        self.last_intro_files = self.get_intro_file_set()
        self.check_folder_changes()
    
    def get_music_file_set(self):
        """Get set of music filenames"""
        try:
            music_dir = os.path.join(os.path.dirname(__file__), "Music")
            if os.path.exists(music_dir):
                return set(f for f in os.listdir(music_dir) 
                          if f.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')))
        except Exception:
            pass
        return set()
    
    def get_intro_file_set(self):
        """Get set of intro filenames"""
        try:
            intro_dir = os.path.join(os.path.dirname(__file__), "Intros")
            if os.path.exists(intro_dir):
                return set(f for f in os.listdir(intro_dir) 
                          if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')))
        except Exception:
            pass
        return set()
    
    def check_folder_changes(self):
        """Check for folder changes every 5 seconds"""
        if not self.monitoring_active:
            return
        
        try:
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
        except Exception:
            pass
        
        if self.monitoring_active:
            self.app.root.after(5000, self.check_folder_changes)
    
    def stop_folder_monitoring(self):
        """Stop monitoring folders"""
        self.monitoring_active = False
    
    # Logging methods
    def log_status(self, message, tag="info"):
        """Add message to status log - thread safe"""
        if threading.current_thread() != threading.main_thread():
            self.app.root.after(0, lambda: self._log_status_main_thread(message, tag))
            return
            
        self._log_status_main_thread(message, tag)
    
    def _log_status_main_thread(self, message, tag="info"):
        """Internal log method - must be on main thread"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        safe_message = message
        if getattr(sys, 'frozen', False):
            safe_message = safe_message.encode('ascii', errors='replace').decode('ascii')
        
        log_message = f"[{timestamp}] {safe_message}\n"
        
        try:
            self.status_text.config(state='normal')
            self.status_text.insert('end', log_message)
            self.status_text.see('end')
            
            self.status_text.update()
            self.app.root.update()
            
            lines = self.status_text.get('1.0', 'end').split('\n')
            if len(lines) > 1000:
                self.status_text.delete('1.0', f"{len(lines)-1000}.0")
                
        except Exception as e:
            print(f"ERROR in log_status: {e}")
    
    def log_success(self, message):
        """Log success message"""
        self.log_status(f"[OK] {message}", "success")
    
    def log_warning(self, message):
        """Log warning message"""
        self.log_status(f"[WARN] {message}", "warning")
    
    def log_error(self, message):
        """Log error message"""
        self.log_status(f"[ERROR] {message}", "error")
    
    # Configuration
    def load_saved_paths(self):
        """Load previously saved paths"""
        config = self.app.config
        if hasattr(self, 'input_path_var'):
            self.input_path_var.set(config.get("input_path", os.path.expanduser("~/Videos/Captures")))
        if hasattr(self, 'output_path_var'):
            self.output_path_var.set(config.get("output_path", os.path.expanduser("~/Downloads")))
        if hasattr(self, 'trim_seconds_var'):
            self.trim_seconds_var.set(config.get("trim_seconds", "15"))
        if hasattr(self, 'music_selection_var'):
            self.music_selection_var.set(config.get("music_selection", ""))
        if hasattr(self, 'intro_selection_var'):
            self.intro_selection_var.set(config.get("intro_selection", ""))
        self.update_paths_display()
    
    def save_config(self):
        """Save current configuration"""
        self.app.save_tab_config('vid_compiler', {
            "input_path": self.input_path_var.get(),
            "output_path": self.output_path_var.get(),
            "trim_seconds": self.trim_seconds_var.get(),
            "music_selection": self.music_selection_var.get(),
            "intro_selection": self.intro_selection_var.get()
        })
