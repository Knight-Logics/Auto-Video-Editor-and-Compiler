"""
Clip player for reviewing compilation source videos (1x speed, standard controls).
"""

from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import ttk

from process_utils import popen_hidden, run_hidden

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from PIL import Image, ImageTk

try:
    from intro_creator import probe_media
except ImportError:
    probe_media = None


def _format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class ClipVideoPlayer:
    """Built-in clip player with accurate 1x playback and familiar media controls."""

    SKIP_SECONDS = 10

    def __init__(self, gui, video_path: str):
        self.gui = gui
        self.video_path = video_path
        self.window: tk.Toplevel | None = None
        self.canvas: tk.Canvas | None = None
        self.progress_var = tk.DoubleVar(value=0.0)
        self.time_label: ttk.Label | None = None
        self.play_btn: ttk.Button | None = None
        self.progress_scale: ttk.Scale | None = None

        self._cap = None
        self._photo = None
        self._after_id = None
        self._audio_proc = None
        self._playing = False
        self._seeking = False
        self._fullscreen = False
        self._saved_geometry = ""
        self.duration = 0.0
        self.fps = 30.0
        self.position = 0.0
        self._playback_clock_origin = 0.0
        self._playback_position_origin = 0.0
        self._cached_canvas_size = (0, 0)

        self._ffplay = gui.get_ffplay_path() if hasattr(gui, "get_ffplay_path") else ""
        self._ffmpeg = gui.get_ffmpeg_path() if hasattr(gui, "get_ffmpeg_path") else ""
        self._ffprobe = ""
        if self._ffmpeg:
            self._ffprobe = os.path.join(os.path.dirname(self._ffmpeg), "ffprobe.exe")

    def _probe_duration_fps(self):
        duration = 0.0
        if probe_media and self._ffprobe and os.path.isfile(self._ffprobe):
            try:
                media = probe_media(self._ffprobe, self.video_path)
                duration = float(media.get("duration") or 0)
            except Exception:
                duration = 0.0

        frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) if self._cap else 0
        reported_fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 0) if self._cap else 0.0

        if duration <= 0 and frame_count > 0 and reported_fps > 0:
            duration = frame_count / reported_fps
        if duration <= 0 and self._cap:
            duration = max(0.0, float(self._cap.get(cv2.CAP_PROP_POS_MSEC) or 0) / 1000.0)

        if frame_count > 0 and duration > 0:
            fps = frame_count / duration
        elif 10.0 <= reported_fps <= 120.0:
            fps = reported_fps
        else:
            fps = 30.0

        fps = max(15.0, min(60.0, fps))
        return max(0.1, duration), fps

    def _configure_player_styles(self):
        style = ttk.Style(self.window)
        style.theme_use("clam")
        style.configure("Player.TFrame", background="#181818")
        style.configure(
            "Player.Transport.TButton",
            background="#2d2d2d",
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(10, 6),
            font=("Segoe UI", 10),
        )
        style.map(
            "Player.Transport.TButton",
            background=[("active", "#404040"), ("pressed", "#505050")],
        )
        style.configure(
            "Player.Play.TButton",
            background="#2E8B57",
            foreground="#ffffff",
            borderwidth=0,
            padding=(14, 6),
            font=("Segoe UI", 11, "bold"),
        )
        style.map(
            "Player.Play.TButton",
            background=[("active", "#3cb371"), ("pressed", "#267349")],
        )
        style.configure(
            "Player.Horizontal.TScale",
            background="#181818",
            troughcolor="#3a3a3a",
            bordercolor="#181818",
            lightcolor="#2E8B57",
            darkcolor="#2E8B57",
        )
        style.configure(
            "Player.Time.TLabel",
            background="#181818",
            foreground="#e0e0e0",
            font=("Segoe UI", 9),
        )

    def show(self):
        if not CV2_AVAILABLE:
            self.gui.preview_custom_order_video(self.video_path)
            return

        existing = getattr(self.gui, "_clip_video_player", None)
        if existing is not None and existing is not self:
            existing.close()

        self.gui._clip_video_player = self
        self.gui.stop_preview()

        self.window = tk.Toplevel(self.gui.root)
        self.window.title(os.path.basename(self.video_path))
        self.window.configure(bg="#101010")
        self.window.transient(self.gui.root)
        self.gui._center_toplevel(self.window, width=980, height=620)
        self._configure_player_styles()

        try:
            self.window.iconbitmap(self.gui.get_icon_path())
        except Exception:
            pass

        self._cap = cv2.VideoCapture(self.video_path)
        if not self._cap.isOpened():
            self.close()
            self.gui.preview_custom_order_video(self.video_path)
            return

        self.duration, self.fps = self._probe_duration_fps()

        main = ttk.Frame(self.window, style="Player.TFrame", padding=(0, 0, 0, 8))
        main.pack(fill="both", expand=True)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(main, bg="#000000", highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        controls = ttk.Frame(main, style="Player.TFrame", padding=(12, 8, 12, 4))
        controls.grid(row=1, column=0, sticky="ew")
        controls.grid_columnconfigure(0, weight=1)

        seek_row = ttk.Frame(controls, style="Player.TFrame")
        seek_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        seek_row.grid_columnconfigure(0, weight=1)

        self.progress_scale = ttk.Scale(
            seek_row,
            from_=0,
            to=max(self.duration, 0.1),
            orient="horizontal",
            variable=self.progress_var,
            command=self._on_scale_drag,
            style="Player.Horizontal.TScale",
        )
        self.progress_scale.grid(row=0, column=0, sticky="ew")
        self.progress_scale.bind("<ButtonPress-1>", lambda _e: self._set_seeking(True))
        self.progress_scale.bind("<ButtonRelease-1>", self._on_scale_release)

        transport = ttk.Frame(controls, style="Player.TFrame")
        transport.grid(row=1, column=0, sticky="ew")

        left = ttk.Frame(transport, style="Player.TFrame")
        left.pack(side="left")

        self.play_btn = ttk.Button(
            left,
            text="Pause",
            command=self.toggle_play_pause,
            style="Player.Play.TButton",
            width=8,
        )
        self.play_btn.pack(side="left", padx=(0, 6))

        ttk.Button(
            left,
            text="Rewind 10s",
            command=lambda: self.skip(-self.SKIP_SECONDS),
            style="Player.Transport.TButton",
        ).pack(side="left", padx=(0, 4))

        ttk.Button(
            left,
            text="Forward 10s",
            command=lambda: self.skip(self.SKIP_SECONDS),
            style="Player.Transport.TButton",
        ).pack(side="left", padx=(0, 12))

        self.time_label = ttk.Label(left, text=self._time_text(), style="Player.Time.TLabel")
        self.time_label.pack(side="left")

        right = ttk.Frame(transport, style="Player.TFrame")
        right.pack(side="right")

        ttk.Button(
            right,
            text="Fullscreen",
            command=self.toggle_fullscreen,
            style="Player.Transport.TButton",
        ).pack(side="right")

        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<space>", lambda _e: self.toggle_play_pause())
        self.window.bind("<Left>", lambda _e: self.skip(-self.SKIP_SECONDS))
        self.window.bind("<Right>", lambda _e: self.skip(self.SKIP_SECONDS))
        self.window.bind("<f>", lambda _e: self.toggle_fullscreen())
        self.window.bind("<F11>", lambda _e: self.toggle_fullscreen())
        self.window.bind("<Escape>", self._on_escape)

        self.window.update_idletasks()
        self._render_current_frame()
        self.play()

    def _reset_playback_clock(self):
        self._playback_clock_origin = time.perf_counter()
        self._playback_position_origin = self.position

    def _time_text(self) -> str:
        return f"{_format_time(self.position)} / {_format_time(self.duration)}"

    def _set_seeking(self, value: bool):
        self._seeking = value

    def _on_scale_drag(self, _value):
        if self._seeking and self.time_label:
            pos = float(self.progress_var.get())
            self.time_label.configure(text=f"{_format_time(pos)} / {_format_time(self.duration)}")

    def _on_scale_release(self, _event=None):
        self.seek_to(float(self.progress_var.get()))
        self._seeking = False

    def seek_to(self, seconds: float):
        was_playing = self._playing
        if was_playing:
            self._stop_audio()

        self.position = max(0.0, min(self.duration, float(seconds)))
        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_POS_MSEC, self.position * 1000.0)
        if not self._seeking:
            self.progress_var.set(self.position)
        self._update_time_label()
        self._render_current_frame()

        if was_playing:
            self._reset_playback_clock()
            self._start_audio(self.position)
            self._schedule_next_frame()

    def skip(self, delta: float):
        self.seek_to(self.position + delta)

    def toggle_play_pause(self):
        if self._playing:
            self.pause()
        else:
            self.play()

    def play(self):
        self._playing = True
        if self.play_btn:
            self.play_btn.configure(text="Pause")
        if self.position >= self.duration - 0.05:
            self.seek_to(0.0)
        else:
            self._reset_playback_clock()
            self._start_audio(self.position)
            self._schedule_next_frame()

    def pause(self):
        self._playing = False
        if self.play_btn:
            self.play_btn.configure(text="Play")
        self._cancel_frame_loop()
        self._stop_audio()

    def _cancel_frame_loop(self):
        if self._after_id is not None and self.window is not None:
            try:
                self.window.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self._after_id = None

    def _stop_audio(self):
        if self._audio_proc is not None:
            try:
                self._audio_proc.terminate()
                self._audio_proc.wait(timeout=1)
            except Exception:
                try:
                    self._audio_proc.kill()
                except Exception:
                    pass
            self._audio_proc = None
        if os.name == "nt" and not self._ffplay:
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        self._temp_wav = getattr(self, "_temp_wav", None)
        if self._temp_wav and os.path.isfile(self._temp_wav):
            try:
                os.remove(self._temp_wav)
            except OSError:
                pass
        self._temp_wav = None

    def _start_audio(self, start_seconds: float):
        self._stop_audio()
        if self._ffplay:
            try:
                self._audio_proc = popen_hidden(
                    [
                        self._ffplay,
                        "-nodisp",
                        "-autoexit",
                        "-loglevel",
                        "error",
                        "-ss",
                        f"{start_seconds:.3f}",
                        self.video_path,
                    ],
                )
                return
            except Exception:
                self._audio_proc = None
        self._start_audio_winsound(start_seconds)

    def _start_audio_winsound(self, start_seconds: float):
        if os.name != "nt" or not self._ffmpeg:
            return
        try:
            import tempfile
            import winsound
        except ImportError:
            return

        fd, wav_path = tempfile.mkstemp(prefix="avc_clip_audio_", suffix=".wav")
        os.close(fd)
        cmd = [
            self._ffmpeg,
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            self.video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            wav_path,
        ]
        result = run_hidden(cmd, capture_output=True)
        if result.returncode != 0 or not os.path.isfile(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass
            return
        self._temp_wav = wav_path
        winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

    def _update_time_label(self):
        if self.time_label:
            self.time_label.configure(text=self._time_text())

    def _canvas_size(self):
        if self.canvas is None:
            return 640, 360
        self.canvas.update_idletasks()
        width = max(320, self.canvas.winfo_width())
        height = max(180, self.canvas.winfo_height())
        return width, height

    def _display_frame(self, frame_rgb):
        if self.canvas is None:
            return
        image = Image.fromarray(frame_rgb)
        canvas_w, canvas_h = self._canvas_size()
        if (canvas_w, canvas_h) != self._cached_canvas_size:
            self._cached_canvas_size = (canvas_w, canvas_h)
            image = image.resize((canvas_w, canvas_h), Image.Resampling.BILINEAR)
        else:
            image.thumbnail((canvas_w, canvas_h), Image.Resampling.BILINEAR)

        self._photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(canvas_w // 2, canvas_h // 2, image=self._photo, anchor="center")

    def _render_current_frame(self):
        if self._cap is None:
            return
        ok, frame = self._cap.read()
        if not ok:
            return
        self.position = float(self._cap.get(cv2.CAP_PROP_POS_MSEC) or 0) / 1000.0
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._display_frame(frame_rgb)

    def _schedule_next_frame(self):
        if self._playing and self.window is not None:
            self._cancel_frame_loop()
            self._after_id = self.window.after(1, self._play_frame)

    def _play_frame(self):
        if not self._playing or self._cap is None or self.window is None:
            return

        frame_started = time.perf_counter()
        elapsed = frame_started - self._playback_clock_origin
        target_position = self._playback_position_origin + elapsed

        if target_position >= self.duration - (1.0 / self.fps):
            self.position = self.duration
            self.progress_var.set(self.duration)
            self._update_time_label()
            self._render_current_frame()
            self.pause()
            return

        if abs(target_position - self.position) > (1.5 / self.fps):
            self._cap.set(cv2.CAP_PROP_POS_MSEC, target_position * 1000.0)

        ok, frame = self._cap.read()
        if not ok:
            self.pause()
            return

        self.position = target_position
        if not self._seeking:
            self.progress_var.set(self.position)
        self._update_time_label()

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._display_frame(frame_rgb)

        work_seconds = time.perf_counter() - frame_started
        delay_ms = max(1, int((1000.0 / self.fps) - (work_seconds * 1000.0)))
        self._after_id = self.window.after(delay_ms, self._play_frame)

    def toggle_fullscreen(self):
        if self.window is None:
            return
        if not self._fullscreen:
            self._saved_geometry = self.window.geometry()
            self.window.attributes("-fullscreen", True)
            self._fullscreen = True
        else:
            self.window.attributes("-fullscreen", False)
            if self._saved_geometry:
                self.window.geometry(self._saved_geometry)
            self._fullscreen = False
        self._cached_canvas_size = (0, 0)

    def _on_escape(self, _event=None):
        if self._fullscreen:
            self.toggle_fullscreen()
        else:
            self.close()

    def close(self):
        self.pause()
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        if getattr(self.gui, "_clip_video_player", None) is self:
            self.gui._clip_video_player = None
