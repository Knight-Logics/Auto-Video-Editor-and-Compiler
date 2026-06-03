"""
Create Intro Video dialog — layout and preview UI.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import intro_creator
except ImportError:
    intro_creator = None

try:
    from intro_preview_player import IntroVideoPreviewPlayer

    PREVIEW_PLAYER_AVAILABLE = True
except ImportError:
    IntroVideoPreviewPlayer = None
    PREVIEW_PLAYER_AVAILABLE = False


class IntroCreatorDialog:
    """Modal-style intro builder with live video preview."""

    LABEL_WIDTH = 20

    def __init__(self, gui):
        self.gui = gui
        self.window = None
        self.video_player = None
        self.preview_debounce = {"id": None}
        self._create_btn = None

    def show(self):
        if intro_creator is None:
            messagebox.showerror("Intro Creator", "The intro creator module could not be loaded.")
            return
        if not self.gui.get_ffmpeg_path():
            messagebox.showerror("Intro Creator", "FFmpeg was not found. Cannot build intro videos.")
            return

        if self.gui._create_intro_window is not None:
            try:
                if self.gui._create_intro_window.winfo_exists():
                    self.gui._create_intro_window.lift()
                    self.gui._create_intro_window.focus_force()
                    return
            except tk.TclError:
                self.gui._create_intro_window = None

        c = self.gui.colors
        self.window = tk.Toplevel(self.gui.root)
        self.gui._create_intro_window = self.window
        self.window.title("Create Intro Video")
        self.window.transient(self.gui.root)
        self.window.configure(bg=c["intro_bg"])
        self.gui._center_toplevel(self.window, width=1180, height=760)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        self._configure_intro_styles(c)
        self._build_ui(c)

    def _configure_intro_styles(self, c):
        style = ttk.Style()
        style.configure(
            "Intro.TFrame",
            background=c["intro_bg"],
        )
        style.configure(
            "Intro.CardInner.TFrame",
            background=c["intro_card"],
        )
        style.configure(
            "Intro.Card.TLabelframe",
            background=c["intro_card"],
            foreground=c["title_color"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Intro.Card.TLabelframe.Label",
            background=c["intro_card"],
            foreground=c["title_color"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Intro.Field.TLabel",
            background=c["intro_card"],
            foreground=c["label_color"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "Intro.Hint.TLabel",
            background=c["intro_card"],
            foreground=c["intro_hint"],
            font=("Segoe UI", 8),
        )
        style.configure(
            "Intro.Header.TLabel",
            background=c["intro_bg"],
            foreground=c["title_color"],
            font=("Segoe UI", 16, "bold"),
        )
        style.configure(
            "Intro.Subheader.TLabel",
            background=c["intro_bg"],
            foreground=c["intro_hint"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "Intro.Status.TLabel",
            background=c["intro_preview_bg"],
            foreground="#d8d8d8",
            font=("Segoe UI", 9),
        )

    def _build_ui(self, c):
        root = ttk.Frame(self.window, style="Intro.TFrame", padding=(16, 14, 16, 10))
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Intro.TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Create Intro Video", style="Intro.Header.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Pick a template, add animated text and optional sound effects, then preview before saving.",
            style="Intro.Subheader.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(root, style="Intro.TFrame")
        body.pack(fill="both", expand=True)

        left_outer = ttk.Frame(body, style="Intro.TFrame")
        left_outer.pack(side="left", fill="both", expand=True, padx=(0, 14))

        left_canvas = tk.Canvas(
            left_outer,
            bg=c["intro_bg"],
            highlightthickness=0,
            borderwidth=0,
        )
        left_scroll = ttk.Scrollbar(left_outer, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left_scroll.pack(side="right", fill="y")
        left_canvas.pack(side="left", fill="both", expand=True)

        form = ttk.Frame(left_canvas, style="Intro.TFrame")
        form_window = left_canvas.create_window((0, 0), window=form, anchor="nw")

        def _on_form_configure(_event):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))

        def _on_canvas_configure(event):
            left_canvas.itemconfigure(form_window, width=event.width)

        form.bind("<Configure>", _on_form_configure)
        left_canvas.bind("<Configure>", _on_canvas_configure)

        def _mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_event):
            left_canvas.bind_all("<MouseWheel>", _mousewheel)

        def _unbind_wheel(_event):
            left_canvas.unbind_all("<MouseWheel>")

        left_canvas.bind("<Enter>", _bind_wheel)
        left_canvas.bind("<Leave>", _unbind_wheel)

        preview_col = tk.Frame(body, bg=c["intro_preview_bg"], padx=14, pady=14)
        preview_col.pack(side="right", fill="y")

        self.ffprobe_path = os.path.join(os.path.dirname(self.gui.get_ffmpeg_path()), "ffprobe.exe")
        self.search_roots = self.gui.get_intro_creator_search_roots()
        self.sfx_names = ["None"] + intro_creator.list_sound_effects(self.gui.get_sound_effects_dir())

        self._build_form_sections(form, c)
        self._build_preview_panel(preview_col, c)
        self._build_footer(root, c)

    def _form_row(self, parent, row, label, widget, hint=None, hint_colspan=1):
        ttk.Label(parent, text=label, style="Intro.Field.TLabel", width=self.LABEL_WIDTH, anchor="e").grid(
            row=row, column=0, sticky="ne", padx=(0, 10), pady=5
        )
        widget.grid(row=row, column=1, sticky="ew", pady=5)
        if hint:
            ttk.Label(parent, text=hint, style="Intro.Hint.TLabel", wraplength=360).grid(
                row=row + 1, column=1, sticky="w", pady=(0, 6), columnspan=hint_colspan
            )
            return row + 2
        return row + 1

    def _build_form_sections(self, form, c):
        appearance = ttk.LabelFrame(form, text=" Appearance ", style="Intro.Card.TLabelframe", padding=12)
        appearance.pack(fill="x", pady=(0, 10))

        self.template_var = tk.StringVar(value=intro_creator.INTRO_TEMPLATE_NAMES[0])
        self.seconds_var = tk.StringVar(value=str(intro_creator.DEFAULT_SECONDS_FROM_END))
        self.font_style_var = tk.StringVar(value="Arial Bold")
        self.font_size_var = tk.StringVar(value="Large")
        self.animation_var = tk.StringVar(value=intro_creator.ANIMATIONS[0])

        row = 0
        row = self._form_row(
            appearance,
            row,
            "Template",
            ttk.Combobox(
                appearance,
                textvariable=self.template_var,
                values=list(intro_creator.INTRO_TEMPLATE_NAMES),
                state="readonly",
            ),
        )
        timing = ttk.Frame(appearance, style="Intro.CardInner.TFrame")
        ttk.Spinbox(timing, from_=0.3, to=15.0, increment=0.1, textvariable=self.seconds_var, width=8).pack(
            side="left"
        )
        ttk.Label(timing, text=" sec before end", style="Intro.Field.TLabel").pack(side="left", padx=(6, 0))
        row = self._form_row(
            appearance,
            row,
            "Text timing",
            timing,
            hint="How long before the intro ends the text animation starts (1.5 s works well for most templates).",
        )
        row = self._form_row(
            appearance,
            row,
            "Font",
            ttk.Combobox(
                appearance,
                textvariable=self.font_style_var,
                values=list(intro_creator.FONT_STYLES.keys()),
                state="readonly",
            ),
        )
        row = self._form_row(
            appearance,
            row,
            "Text size",
            ttk.Combobox(
                appearance,
                textvariable=self.font_size_var,
                values=list(intro_creator.FONT_SIZES.keys()),
                state="readonly",
            ),
        )
        self._form_row(
            appearance,
            row,
            "Animation",
            ttk.Combobox(
                appearance,
                textvariable=self.animation_var,
                values=list(intro_creator.ANIMATIONS),
                state="readonly",
            ),
        )
        appearance.grid_columnconfigure(1, weight=1)

        line1 = ttk.LabelFrame(form, text=" Line 1 ", style="Intro.Card.TLabelframe", padding=12)
        line1.pack(fill="x", pady=(0, 10))
        self.line1_var = tk.StringVar()
        self.line1_sfx_var = tk.StringVar(value="None")
        r = 0
        r = self._form_row(line1, r, "On-screen text", ttk.Entry(line1, textvariable=self.line1_var))
        self._form_row(
            line1,
            r,
            "Sound effect",
            ttk.Combobox(line1, textvariable=self.line1_sfx_var, values=self.sfx_names, state="readonly"),
            hint="Optional clip from your Sound Effects library, timed when this line appears.",
        )
        line1.grid_columnconfigure(1, weight=1)

        line2 = ttk.LabelFrame(form, text=" Line 2 ", style="Intro.Card.TLabelframe", padding=12)
        line2.pack(fill="x", pady=(0, 10))
        ttk.Label(
            line2,
            text="Leave blank to skip. Any text here adds a second centered line.",
            style="Intro.Hint.TLabel",
            wraplength=400,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.line2_var = tk.StringVar()
        self.line2_sfx_var = tk.StringVar(value="None")
        self.line2_delay_var = tk.StringVar(value=str(intro_creator.DEFAULT_LINE2_DELAY))
        r = 1
        self.line2_entry = ttk.Entry(line2, textvariable=self.line2_var)
        r = self._form_row(line2, r, "On-screen text", self.line2_entry)
        self.line2_sfx_combo = ttk.Combobox(
            line2, textvariable=self.line2_sfx_var, values=self.sfx_names, state="readonly"
        )
        r = self._form_row(
            line2,
            r,
            "Sound effect",
            self.line2_sfx_combo,
            hint="Optional; plays when line 2 appears (not with line 1).",
        )
        delay_row = ttk.Frame(line2, style="Intro.CardInner.TFrame")
        self.line2_delay_spin = ttk.Spinbox(
            delay_row,
            from_=intro_creator.MIN_LINE2_DELAY,
            to=intro_creator.MAX_LINE2_DELAY,
            increment=0.1,
            textvariable=self.line2_delay_var,
            width=8,
        )
        self.line2_delay_spin.pack(side="left")
        ttk.Label(delay_row, text=" seconds after line 1", style="Intro.Field.TLabel").pack(side="left", padx=(6, 0))
        self.line2_delay_label = ttk.Label(line2, text="Line 2 delay", style="Intro.Field.TLabel", width=self.LABEL_WIDTH, anchor="e")
        self.line2_delay_label.grid(row=r, column=0, sticky="ne", padx=(0, 10), pady=5)
        delay_row.grid(row=r, column=1, sticky="w", pady=5)
        ttk.Label(
            line2,
            text="Staggers line 2 text and its sound so they do not overlap line 1 (0.5–1 s works well).",
            style="Intro.Hint.TLabel",
            wraplength=360,
        ).grid(row=r + 1, column=1, sticky="w", pady=(0, 6))
        self.line2_delay_row = r
        line2.grid_columnconfigure(1, weight=1)

        output = ttk.LabelFrame(form, text=" Output ", style="Intro.Card.TLabelframe", padding=12)
        output.pack(fill="x", pady=(0, 6))
        self.output_var = tk.StringVar()
        r = self._form_row(output, 0, "File name", ttk.Entry(output, textvariable=self.output_var))
        ttk.Label(
            output,
            text="Saved to your Intros folder. Leave blank to use line 1 text as the file name.",
            style="Intro.Hint.TLabel",
            wraplength=400,
        ).grid(row=r, column=1, sticky="w")
        output.grid_columnconfigure(1, weight=1)

        self.status_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.status_var, style="Intro.Hint.TLabel", wraplength=480).pack(
            anchor="w", pady=(4, 0)
        )

        self.line2_var.trace_add("write", lambda *_: self._update_line2_fields())
        self._update_line2_fields()

        trace_vars = (
            self.template_var,
            self.seconds_var,
            self.font_style_var,
            self.font_size_var,
            self.animation_var,
            self.line1_var,
            self.line1_sfx_var,
            self.line2_var,
            self.line2_sfx_var,
            self.line2_delay_var,
        )
        for var in trace_vars:
            var.trace_add("write", lambda *_a: self._schedule_video_preview())

    def _build_preview_panel(self, parent, c):
        tk.Label(
            parent,
            text="LIVE PREVIEW",
            bg=c["intro_preview_bg"],
            fg=c["title_color"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        frame_border = tk.Frame(parent, bg="#1a1a1a", padx=2, pady=2)
        frame_border.pack(pady=(8, 0))

        self.preview_canvas = tk.Canvas(
            frame_border,
            bg="#000000",
            highlightthickness=0,
            width=520,
            height=292,
        )
        self.preview_canvas.pack()

        status_frame = tk.Frame(parent, bg="#2a2a2a", padx=8, pady=6)
        status_frame.pack(fill="x", pady=(10, 0))
        self.preview_caption_var = tk.StringVar(
            value="Click Play to render and watch the exact intro (video, text animation, and sound)."
        )
        tk.Label(
            status_frame,
            textvariable=self.preview_caption_var,
            bg="#2a2a2a",
            fg="#cccccc",
            font=("Segoe UI", 9),
            wraplength=500,
            justify="left",
        ).pack(anchor="w")

        controls = tk.Frame(parent, bg=c["intro_preview_bg"])
        controls.pack(fill="x", pady=(12, 0))

        if PREVIEW_PLAYER_AVAILABLE and IntroVideoPreviewPlayer is not None:
            self.video_player = IntroVideoPreviewPlayer(
                self.preview_canvas,
                on_status=lambda msg: self.preview_caption_var.set(msg),
                ffmpeg_path=self.gui.get_ffmpeg_path(),
                ffplay_path=self.gui.get_ffplay_path(),
            )

        accent = c["accent"]
        btn_font = ("Segoe UI", 9, "bold")
        tk.Button(
            controls,
            text="▶  Play Preview",
            command=self._on_play_preview,
            bg=accent,
            fg="white",
            activebackground="#3cb371",
            activeforeground="white",
            font=btn_font,
            padx=14,
            pady=6,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            controls,
            text="■  Stop",
            command=self._on_stop_preview,
            bg="#4a4a4a",
            fg="white",
            activebackground="#5a5a5a",
            font=("Segoe UI", 9),
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            controls,
            text="↻  Refresh",
            command=self._run_video_preview,
            bg="#4a4a4a",
            fg="white",
            activebackground="#5a5a5a",
            font=("Segoe UI", 9),
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
        ).pack(side="left")

        self.auto_preview_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            parent,
            text="Auto-refresh preview when settings change",
            variable=self.auto_preview_var,
            bg=c["intro_preview_bg"],
            fg="#dddddd",
            selectcolor="#2a2a2a",
            activebackground=c["intro_preview_bg"],
            activeforeground="#ffffff",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(10, 0))

    def _build_footer(self, root, c):
        footer = tk.Frame(root, bg=c["intro_bg"])
        footer.pack(fill="x", pady=(12, 0))

        self._create_btn = tk.Button(
            footer,
            text="Create Intro Video",
            command=self._on_create,
            bg=c["accent"],
            fg="white",
            activebackground="#3cb371",
            font=("Segoe UI", 10, "bold"),
            padx=18,
            pady=8,
            relief="flat",
            cursor="hand2",
        )
        self._create_btn.pack(side="left")
        tk.Button(
            footer,
            text="Cancel",
            command=self._close,
            bg="#555555",
            fg="white",
            activebackground="#666666",
            font=("Segoe UI", 9),
            padx=16,
            pady=8,
            relief="flat",
            cursor="hand2",
        ).pack(side="right")

    def _line2_active(self) -> bool:
        return bool(self.line2_var.get().strip())

    def _update_line2_fields(self):
        delay_state = "normal" if self._line2_active() else "disabled"
        self.line2_delay_spin.configure(state=delay_state)

    def _parse_line2_delay(self):
        try:
            value = float(self.line2_delay_var.get())
        except ValueError:
            return None, "Line 2 delay must be a number."
        value = max(intro_creator.MIN_LINE2_DELAY, min(intro_creator.MAX_LINE2_DELAY, value))
        return value, None

    def _resolve_sfx_path(self, name):
        if not name or name == "None":
            return None
        return os.path.join(self.gui.get_sound_effects_dir(), name)

    def _build_prompts(self, require_line1=False):
        line1 = self.line1_var.get().strip()
        if require_line1 and not line1:
            return None, "Enter text for line 1."
        if not line1:
            line1 = "Preview"
        prompts = [intro_creator.TextPromptSpec(line1, self._resolve_sfx_path(self.line1_sfx_var.get()))]
        line2 = self.line2_var.get().strip()
        if line2:
            prompts.append(
                intro_creator.TextPromptSpec(line2, self._resolve_sfx_path(self.line2_sfx_var.get()))
            )
        return prompts, None

    def _make_build_request(self, output_path):
        prompts, err = self._build_prompts(require_line1=False)
        if err:
            return None, err
        try:
            seconds_from_end = float(self.seconds_var.get())
        except ValueError:
            return None, "Seconds before end must be a number."
        line2_delay, delay_err = self._parse_line2_delay()
        if delay_err:
            return None, delay_err
        return (
            intro_creator.IntroBuildRequest(
                template_name=self.template_var.get(),
                output_path=output_path,
                prompts=prompts,
                seconds_from_end=seconds_from_end,
                line2_delay=line2_delay,
                font_style=self.font_style_var.get(),
                font_size_label=self.font_size_var.get(),
                animation=self.animation_var.get(),
                search_roots=self.search_roots,
                ffmpeg_path=self.gui.get_ffmpeg_path(),
                ffprobe_path=self.ffprobe_path,
            ),
            None,
        )

    def _run_video_preview(self):
        if self.video_player is None:
            self.preview_caption_var.set(
                "Video preview requires opencv-python. Install it, then restart the app."
            )
            return
        if not self.line1_var.get().strip():
            self.preview_caption_var.set("Enter line 1 text to preview.")
            return

        def build_fn(temp_path):
            request, err = self._make_build_request(temp_path)
            if err or request is None:
                return False, err or "Could not build preview request."
            try:
                return intro_creator.build_intro_video(request)
            except Exception as build_exc:
                return False, str(build_exc)

        self.video_player.build_and_play(build_fn, schedule_on_ui=lambda fn: self.window.after(0, fn))

    def _schedule_video_preview(self):
        if not self.auto_preview_var.get():
            return
        if self.preview_debounce["id"] is not None:
            try:
                self.window.after_cancel(self.preview_debounce["id"])
            except tk.TclError:
                pass
        self.preview_debounce["id"] = self.window.after(900, self._run_video_preview)

    def _on_play_preview(self):
        self.auto_preview_var.set(False)
        self._run_video_preview()

    def _on_stop_preview(self):
        if self.video_player is not None:
            self.video_player.stop()
        self.preview_caption_var.set("Preview stopped.")

    def _unique_output_path(self, filename):
        intro_dir = self.gui.get_intro_dir()
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

    def _on_create(self):
        line1 = self.line1_var.get().strip()
        if not line1:
            messagebox.showerror("Create Intro", "Enter text for line 1.")
            return

        filename = self.output_var.get().strip() or intro_creator.default_output_name(line1)
        if not filename.lower().endswith(".mp4"):
            filename = f"{filename}.mp4"
        output_path = self._unique_output_path(filename)
        request, err = self._make_build_request(output_path)
        if err or request is None:
            messagebox.showerror("Create Intro", err or "Invalid intro settings.")
            return

        self._create_btn.configure(state="disabled")
        self.status_var.set("Building intro video...")
        if self.video_player is not None:
            self.video_player.stop()

        def worker():
            ok, message = intro_creator.build_intro_video(request)

            def finish():
                self._create_btn.configure(state="normal")
                if ok:
                    stem = os.path.splitext(os.path.basename(output_path))[0]
                    self.gui.refresh_intro_list()
                    self.gui.intro_selection_var.set(stem)
                    self.gui.save_config()
                    self.status_var.set(f"Created: {os.path.basename(output_path)}")
                    self.gui.log_success(f"[INTRO] Created custom intro: {output_path}")
                    messagebox.showinfo(
                        "Intro Created",
                        f"Intro saved to:\n{output_path}\n\nIt is selected in the Intro Video dropdown.",
                    )
                    self._close()
                else:
                    self.status_var.set("Build failed.")
                    self.gui.log_error(f"[INTRO] Create failed: {message}")
                    messagebox.showerror("Create Intro Failed", message)

            self.gui.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _close(self):
        if self.preview_debounce["id"] is not None:
            try:
                self.window.after_cancel(self.preview_debounce["id"])
            except tk.TclError:
                pass
        try:
            self.window.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        if self.video_player is not None:
            self.video_player.cleanup()
        try:
            self.window.grab_release()
        except tk.TclError:
            pass
        self.gui._create_intro_window = None
        self.window.destroy()
