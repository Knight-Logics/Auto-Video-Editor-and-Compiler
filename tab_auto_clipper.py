#!/usr/bin/env python3
"""
Auto Clipper Tab - Automatic highlight detection and clipping
Future functionality for detecting and extracting gameplay highlights
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os


class AutoClipperTab:
    """Auto Clipper tab functionality (Coming Soon)"""
    
    def __init__(self, parent_frame, main_app):
        """
        Initialize Auto Clipper tab
        
        Args:
            parent_frame: The ttk.Frame that this tab lives in
            main_app: Reference to the main UOVidCompilerGUI instance
        """
        self.parent = parent_frame
        self.app = main_app
        
        # Initialize variables
        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.sensitivity_var = tk.StringVar(value='Medium')
        self.clip_duration_var = tk.StringVar(value='15')
        
        # Create the tab content
        self.create_content()
        
        # Load saved configuration
        self.load_saved_config()
    
    def create_content(self):
        """Create all content for the Auto Clipper tab"""
        # Main scrollable frame
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
        
        # Welcome section
        self.create_welcome_section(scrollable_frame)
        
        # Configuration section
        self.create_config_section(scrollable_frame)
        
        # Action section
        self.create_action_section(scrollable_frame)
        
        # Status section
        self.create_status_section(scrollable_frame)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_welcome_section(self, parent):
        """Create welcome message section"""
        welcome_frame = ttk.LabelFrame(parent, text="Auto Clipper Setup - Choose Your Configuration", padding=20)
        welcome_frame.pack(fill='x', padx=20, pady=20)
        
        # Info text
        info_text = """Select a configuration below to get the Orion script code for automatic clip recording.
Each option provides different levels of tracking and notification capabilities."""
        
        info_label = tk.Label(welcome_frame, text=info_text,
                            bg=self.app.colors['frame_bg'],
                            fg=self.app.colors['label_color'],
                            font=('Segoe UI', 10),
                            justify='left')
        info_label.pack(fill='x', pady=(0, 15))
        
        # Radio button selection frame
        selection_frame = ttk.Frame(welcome_frame, style='Custom.TFrame')
        selection_frame.pack(fill='x', pady=(0, 10))
        
        # Selection variable
        self.config_selection = tk.StringVar(value='basic')
        
        # Radio button options
        options = [
            ('basic', '🎯 Basic - Simple Kill Recording', 'Records kills only, no extra features'),
            ('webhook', '🔔 With Discord Webhook', 'Basic recording + Discord notifications'),
            ('full', '📊 With Player Data & Webhook', 'Full tracking with stats and Discord notifications')
        ]
        
        for value, label, description in options:
            radio_frame = ttk.Frame(selection_frame, style='Custom.TFrame')
            radio_frame.pack(fill='x', pady=5)
            
            radio = tk.Radiobutton(radio_frame,
                                  text=label,
                                  variable=self.config_selection,
                                  value=value,
                                  command=self.update_code_display,
                                  bg=self.app.colors['frame_bg'],
                                  fg=self.app.colors['label_color'],
                                  selectcolor=self.app.colors['bg'],
                                  activebackground=self.app.colors['frame_bg'],
                                  activeforeground=self.app.colors['accent'],
                                  font=('Segoe UI', 11, 'bold'),
                                  cursor='hand2')
            radio.pack(anchor='w')
            
            desc_label = tk.Label(radio_frame, text=f"     {description}",
                                bg=self.app.colors['frame_bg'],
                                fg=self.app.colors['label_color'],
                                font=('Segoe UI', 9, 'italic'))
            desc_label.pack(anchor='w', padx=(20, 0))
    
    def create_config_section(self, parent):
        """Create code display section"""
        code_frame = ttk.LabelFrame(parent, text="Orion Script Code", padding=20)
        code_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        # Instructions
        instructions = tk.Label(code_frame,
                               text="Copy the code below and paste it into your Orion script:",
                               bg=self.app.colors['frame_bg'],
                               fg=self.app.colors['label_color'],
                               font=('Segoe UI', 10, 'bold'))
        instructions.pack(anchor='w', pady=(0, 10))
        
        # Code display area with scrollbar
        code_container = ttk.Frame(code_frame, style='Custom.TFrame')
        code_container.pack(fill='both', expand=True)
        
        self.code_text = tk.Text(code_container, 
                                height=20,
                                wrap='none',
                                bg='#1e1e1e',
                                fg='#d4d4d4',
                                font=('Consolas', 9),
                                borderwidth=2,
                                relief='sunken',
                                insertbackground=self.app.colors['accent'])
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(code_container, orient='vertical', command=self.code_text.yview)
        h_scrollbar = ttk.Scrollbar(code_container, orient='horizontal', command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.code_text.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        code_container.grid_rowconfigure(0, weight=1)
        code_container.grid_columnconfigure(0, weight=1)
        
        # Copy button
        copy_btn = tk.Button(code_frame,
                            text="📋 Copy Code to Clipboard",
                            command=self.copy_code_to_clipboard,
                            bg=self.app.colors['accent'],
                            fg='white',
                            font=('Segoe UI', 11, 'bold'),
                            relief='raised',
                            borderwidth=2,
                            pady=10,
                            cursor='hand2')
        copy_btn.pack(fill='x', pady=(10, 0))
        
        # Initialize with basic code
        self.update_code_display()
    
    def create_action_section(self, parent):
        """Create action buttons section"""
        action_frame = ttk.Frame(parent, style='Custom.TFrame')
        action_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        # Info section
        info_text = """💡 Quick Setup Instructions:
1. Select your desired configuration above
2. Copy the code using the button
3. Paste it into your Orion script
4. Configure any variables (Discord webhook URL, etc.)
5. Run your script and start recording kills automatically!"""
        
        info_label = tk.Label(action_frame, text=info_text,
                            bg=self.app.colors['frame_bg'],
                            fg=self.app.colors['label_color'],
                            font=('Segoe UI', 9),
                            justify='left')
        info_label.pack(fill='x', pady=(0, 10))
        
        # Secondary buttons
        secondary_frame = ttk.Frame(action_frame, style='Custom.TFrame')
        secondary_frame.pack(fill='x')
        
        # Info button
        info_btn = tk.Button(secondary_frame,
                            text="ℹ️ Learn More",
                            command=self.show_more_info,
                            bg=self.app.colors['button'],
                            fg='white',
                            font=('Arial', 10),
                            relief='raised',
                            padx=20,
                            pady=5)
        info_btn.pack(side='left', padx=(0, 10))
        
        # Switch to Vid Compiler button
        switch_btn = tk.Button(secondary_frame,
                              text="➜ Use Vid Compiler Tab",
                              command=self.switch_to_vid_compiler,
                              bg=self.app.colors['accent'],
                              fg='white',
                              font=('Arial', 10, 'bold'),
                              relief='raised',
                              padx=20,
                              pady=5)
        switch_btn.pack(side='left')
    
    def create_status_section(self, parent):
        """Create status display section"""
        status_frame = ttk.LabelFrame(parent, text="Setup Notes & Tips", padding=15)
        status_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        self.status_text = tk.Text(status_frame, height=12, wrap='word',
                                  bg=self.app.colors['text_bg'],
                                  fg=self.app.colors['text_fg'],
                                  font=('Consolas', 10),
                                  borderwidth=2,
                                  relief='sunken')
        
        scrollbar = ttk.Scrollbar(status_frame, orient='vertical', 
                                 command=self.status_text.yview)
        
        self.status_text.pack(side='left', fill='both', expand=True, padx=(0, 5))
        scrollbar.pack(side='right', fill='y')
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        # Initial status messages
        status_messages = [
            "[SETUP] How to use these scripts:",
            "",
            "1. SELECT a configuration option above (Basic, Webhook, or Full)",
            "2. COPY the code using the 'Copy Code to Clipboard' button",
            "3. PASTE into your Orion script file",
            "4. CONFIGURE these variables in the code:",
            "   - outputFolder: Change to your desired clip save location",
            "   - discordWebhook: (If using webhook/full) Get from Discord Server Settings",
            "   - clipDuration: Adjust recording length if needed (default: 30 sec)",
            "",
            "[DISCORD] To get a webhook URL:",
            "  1. Open Discord and go to your server",
            "  2. Server Settings → Integrations → Webhooks",
            "  3. Click 'New Webhook' or copy existing webhook URL",
            "  4. Paste the URL into the discordWebhook variable",
            "",
            "[TIP] The scripts automatically:",
            "  • Detect when you get a kill",
            "  • Start recording for the configured duration",
            "  • Save clips with timestamps and victim names",
            "  • Send notifications to Discord (if configured)",
            "",
            "[NOTE] After pasting the code, make sure to:",
            "  ✓ Update the outputFolder path to match your system",
            "  ✓ Test with a single kill first to verify it's working",
            "  ✓ Check the output folder to confirm clips are being saved"
        ]
        
        for msg in status_messages:
            self.status_text.insert('end', msg + '\n')
        
        self.status_text.config(state='disabled')
    
    def show_more_info(self):
        """Show more information about Auto Clipper"""
        info_window = tk.Toplevel(self.app.root)
        info_window.title("Auto Clipper - More Information")
        info_window.geometry("600x500")
        info_window.resizable(False, False)
        info_window.configure(bg='white')
        
        # Set icon
        try:
            ico_path = os.path.join(os.path.dirname(__file__), "icons", "image.ico")
            if os.path.exists(ico_path):
                info_window.iconbitmap(ico_path)
        except Exception:
            pass
        
        # Center on parent
        info_window.transient(self.app.root)
        info_window.grab_set()
        
        # Header
        header = tk.Label(info_window, 
                         text="🎯 Auto Clipper - Coming Soon",
                         font=('Segoe UI', 18, 'bold'),
                         bg='white',
                         fg=self.app.colors['accent'])
        header.pack(pady=20)
        
        # Info text
        info_text = tk.Text(info_window, wrap='word', font=('Segoe UI', 10),
                          bg='white', relief='flat', padx=20)
        info_text.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        info_content = """How Auto Clipper Will Work:

1. AUTOMATIC DETECTION
   Auto Clipper will analyze your gameplay videos and automatically identify exciting moments like kills, deaths, and multi-kills.

2. SMART TIMING
   Each clip will include context - capturing a few seconds before and after the event so viewers understand what happened.

3. BATCH PROCESSING
   Process multiple videos at once. Perfect for creating a highlight reel from an entire gaming session.

4. PREVIEW & EDIT
   Review all detected clips before saving. Accept, reject, or adjust timing for each clip.

5. EXPORT OPTIONS
   Save clips individually or compile them into one highlight video with transitions.

TECHNICAL APPROACH:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Audio analysis to detect combat sounds and kill notifications
• Visual recognition for on-screen indicators
• Frame difference analysis for significant events
• Machine learning (future) for improved accuracy

TIMELINE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Version 1.3.0 - Alpha testing (invite-only)
• Version 1.4.0 - Public beta release
• Version 1.5.0 - Full release with all features

Want to be notified? Star the GitHub repo and watch for updates!
"""
        
        info_text.insert('1.0', info_content)
        info_text.config(state='disabled')
        
        # Close button
        close_btn = tk.Button(info_window,
                             text="Close",
                             command=info_window.destroy,
                             bg=self.app.colors['button'],
                             fg='white',
                             font=('Segoe UI', 10, 'bold'),
                             padx=30,
                             pady=5)
        close_btn.pack(pady=(0, 20))
    
    def switch_to_vid_compiler(self):
        """Switch to the Vid Compiler tab"""
        # Find the Vid Compiler tab index and switch to it
        if hasattr(self.app, 'notebook'):
            # Tab 0 = Auto Clipper, Tab 1 = Vid Compiler
            self.app.notebook.select(1)
            messagebox.showinfo("Switched to Vid Compiler",
                              "You can now use the Vid Compiler to create compilations from your existing clips!")
    
    def update_code_display(self):
        """Update the code display based on selected configuration"""
        selection = self.config_selection.get()
        
        # Clear current code
        self.code_text.delete('1.0', tk.END)
        
        # Get the appropriate code template
        if selection == 'basic':
            code = self.get_basic_code()
        elif selection == 'webhook':
            code = self.get_webhook_code()
        else:  # full
            code = self.get_full_code()
        
        # Insert the code
        self.code_text.insert('1.0', code)
        
        # Make read-only but still allow selection/copying
        self.code_text.config(state='normal')
    
    def get_basic_code(self):
        """Get basic kill recording code"""
        return """// ═══════════════════════════════════════════════════════════════
// B-Magic's Auto Clipper - BASIC CONFIGURATION
// Simple kill recording with no extra features
// ═══════════════════════════════════════════════════════════════

// Configuration
var clipDuration = 30; // Duration in seconds to record
var outputFolder = "C:\\\\Users\\\\YourName\\\\Videos\\\\UO_Clips"; // Change this path

// Kill detection function
function onKill(victim) {
    var timestamp = new Date().toISOString().replace(/:/g, '-');
    var filename = "Kill_" + victim + "_" + timestamp + ".mp4";
    var filepath = outputFolder + "\\\\" + filename;
    
    // Start recording
    console.log("Recording kill: " + victim);
    startRecording(filepath, clipDuration);
}

// Hook into game events
game.on('player.kill', function(event) {
    onKill(event.victimName);
});

console.log("Auto Clipper: Basic mode active - Recording kills only");
"""
    
    def get_webhook_code(self):
        """Get webhook-enabled code"""
        return """// ═══════════════════════════════════════════════════════════════
// B-Magic's Auto Clipper - WITH DISCORD WEBHOOK
// Records kills + sends Discord notifications
// ═══════════════════════════════════════════════════════════════

// Configuration
var clipDuration = 30; // Duration in seconds to record
var outputFolder = "C:\\\\Users\\\\YourName\\\\Videos\\\\UO_Clips"; // Change this path
var discordWebhook = "YOUR_DISCORD_WEBHOOK_URL_HERE"; // Get from Discord Server Settings > Integrations

// Kill detection with Discord notification
function onKill(victim) {
    var timestamp = new Date().toISOString().replace(/:/g, '-');
    var filename = "Kill_" + victim + "_" + timestamp + ".mp4";
    var filepath = outputFolder + "\\\\" + filename;
    
    // Start recording
    console.log("Recording kill: " + victim);
    startRecording(filepath, clipDuration);
    
    // Send Discord notification
    sendDiscordNotification(victim, filename);
}

function sendDiscordNotification(victim, filename) {
    var message = {
        "content": "🎯 Kill Recorded!",
        "embeds": [{
            "title": "New Kill Clip",
            "description": "Victim: **" + victim + "**",
            "color": 3066993,
            "fields": [
                {
                    "name": "Filename",
                    "value": filename,
                    "inline": true
                },
                {
                    "name": "Duration",
                    "value": clipDuration + " seconds",
                    "inline": true
                }
            ],
            "timestamp": new Date().toISOString()
        }]
    };
    
    // Send to Discord
    fetch(discordWebhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(message)
    }).catch(err => console.log("Discord notification failed: " + err));
}

// Hook into game events
game.on('player.kill', function(event) {
    onKill(event.victimName);
});

console.log("Auto Clipper: Webhook mode active - Recording kills + Discord notifications");
"""
    
    def get_full_code(self):
        """Get full featured code with player data tracking"""
        return """// ═══════════════════════════════════════════════════════════════
// B-Magic's Auto Clipper - FULL CONFIGURATION
// Records kills + player stats + Discord notifications
// ═══════════════════════════════════════════════════════════════

// Configuration
var clipDuration = 30; // Duration in seconds to record
var outputFolder = "C:\\\\Users\\\\YourName\\\\Videos\\\\UO_Clips"; // Change this path
var discordWebhook = "YOUR_DISCORD_WEBHOOK_URL_HERE"; // Get from Discord Server Settings > Integrations

// Player statistics tracking
var playerStats = {
    kills: 0,
    deaths: 0,
    sessionStart: new Date(),
    killStreak: 0,
    bestStreak: 0
};

// Kill detection with full tracking
function onKill(victim, location, weapon) {
    var timestamp = new Date().toISOString().replace(/:/g, '-');
    var filename = "Kill_" + victim + "_" + timestamp + ".mp4";
    var filepath = outputFolder + "\\\\" + filename;
    
    // Update stats
    playerStats.kills++;
    playerStats.killStreak++;
    if (playerStats.killStreak > playerStats.bestStreak) {
        playerStats.bestStreak = playerStats.killStreak;
    }
    
    // Start recording
    console.log("Recording kill #" + playerStats.kills + ": " + victim);
    startRecording(filepath, clipDuration);
    
    // Send Discord notification with stats
    sendDiscordNotification(victim, filename, location, weapon);
}

function onDeath(killer) {
    playerStats.deaths++;
    playerStats.killStreak = 0; // Reset streak
    
    // Optional: Send death notification
    var deathMessage = {
        "content": "💀 Death",
        "embeds": [{
            "title": "Killed by " + killer,
            "color": 15158332,
            "fields": [
                {
                    "name": "Session K/D",
                    "value": playerStats.kills + "/" + playerStats.deaths,
                    "inline": true
                }
            ]
        }]
    };
    
    fetch(discordWebhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(deathMessage)
    }).catch(err => console.log("Discord notification failed: " + err));
}

function sendDiscordNotification(victim, filename, location, weapon) {
    var sessionTime = Math.floor((new Date() - playerStats.sessionStart) / 60000); // minutes
    var kdr = playerStats.deaths > 0 ? (playerStats.kills / playerStats.deaths).toFixed(2) : playerStats.kills;
    
    var message = {
        "content": "🎯 Kill Recorded!",
        "embeds": [{
            "title": "New Kill Clip - " + victim,
            "description": "Weapon: **" + weapon + "**\\nLocation: " + location,
            "color": 3066993,
            "fields": [
                {
                    "name": "Filename",
                    "value": filename,
                    "inline": false
                },
                {
                    "name": "Session Stats",
                    "value": "Kills: " + playerStats.kills + "\\nDeaths: " + playerStats.deaths + "\\nK/D: " + kdr,
                    "inline": true
                },
                {
                    "name": "Kill Streak",
                    "value": "Current: " + playerStats.killStreak + "\\nBest: " + playerStats.bestStreak,
                    "inline": true
                },
                {
                    "name": "Session Time",
                    "value": sessionTime + " minutes",
                    "inline": true
                }
            ],
            "timestamp": new Date().toISOString(),
            "footer": {
                "text": "B-Magic's Auto Clipper"
            }
        }]
    };
    
    fetch(discordWebhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(message)
    }).catch(err => console.log("Discord notification failed: " + err));
}

// Hook into game events
game.on('player.kill', function(event) {
    onKill(event.victimName, event.location, event.weapon);
});

game.on('player.death', function(event) {
    onDeath(event.killerName);
});

// Session summary on exit
game.on('session.end', function() {
    var sessionTime = Math.floor((new Date() - playerStats.sessionStart) / 60000);
    console.log("═══════════════════════════════════════════");
    console.log("Session Summary:");
    console.log("Duration: " + sessionTime + " minutes");
    console.log("Kills: " + playerStats.kills);
    console.log("Deaths: " + playerStats.deaths);
    console.log("Best Kill Streak: " + playerStats.bestStreak);
    console.log("═══════════════════════════════════════════");
});

console.log("Auto Clipper: Full mode active - Recording kills + player stats + Discord");
console.log("Session started at: " + playerStats.sessionStart.toLocaleString());
"""
    
    def copy_code_to_clipboard(self):
        """Copy the displayed code to clipboard"""
        try:
            code = self.code_text.get('1.0', 'end-1c')
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(code)
            self.app.root.update()
            
            messagebox.showinfo("Code Copied!", 
                              "The code has been copied to your clipboard!\n\n"
                              "Paste it into your Orion script to start using Auto Clipper.")
        except Exception as e:
            messagebox.showerror("Copy Failed", f"Could not copy code to clipboard:\n{e}")
    
    def load_saved_config(self):
        """Load saved configuration from main app"""
        config = self.app.config.get('auto_clipper', {})
        
        if 'config_selection' in config:
            self.config_selection.set(config['config_selection'])
        
        if 'input_path' in config:
            self.input_path_var.set(config['input_path'])
        if 'output_path' in config:
            self.output_path_var.set(config['output_path'])
        if 'sensitivity' in config:
            self.sensitivity_var.set(config['sensitivity'])
        if 'clip_duration' in config:
            self.clip_duration_var.set(config['clip_duration'])
    
    def save_config(self):
        """Save current configuration to main app"""
        self.app.save_tab_config('auto_clipper', {
            'config_selection': self.config_selection.get(),
            'input_path': self.input_path_var.get(),
            'output_path': self.output_path_var.get(),
            'sensitivity': self.sensitivity_var.get(),
            'clip_duration': self.clip_duration_var.get()
        })
