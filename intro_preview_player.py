"""
In-GUI playback of intro previews (same FFmpeg output as the final render).
"""

from __future__ import annotations

import os
import shutil
import tempfile

from process_utils import popen_hidden, run_hidden
import threading
from typing import Callable, Optional

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from PIL import Image, ImageTk


def resolve_ffplay_path(
    ffmpeg_path: Optional[str] = None,
    ffplay_path: Optional[str] = None,
) -> Optional[str]:
    """Resolve ffplay: explicit path, beside ffmpeg, then PATH."""
    if ffplay_path and os.path.isfile(ffplay_path):
        return ffplay_path
    if ffmpeg_path:
        directory = os.path.dirname(ffmpeg_path)
        for name in ("ffplay.exe", "ffplay"):
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which("ffplay") or shutil.which("ffplay.exe")


class IntroVideoPreviewPlayer:
    """Build a temp intro MP4 and play it on a tkinter Canvas."""

    def __init__(
        self,
        canvas,
        on_status: Optional[Callable[[str], None]] = None,
        ffmpeg_path: Optional[str] = None,
        ffplay_path: Optional[str] = None,
    ):
        self.canvas = canvas
        self.on_status = on_status
        self._ffmpeg_path = ffmpeg_path or ""
        self._ffplay_path = resolve_ffplay_path(ffmpeg_path, ffplay_path)
        self._playing = False
        self._after_id = None
        self._capture = None
        self._photo = None
        self._temp_path = None
        self._temp_wav = None
        self._build_thread = None
        self._audio_proc = None
        self._audio_mode = None
        self._preview_width = 520

    def _set_status(self, message: str):
        if self.on_status:
            self.on_status(message)

    def _stop_audio(self):
        if self._audio_mode == "winsound":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        elif self._audio_proc is not None:
            try:
                self._audio_proc.terminate()
                self._audio_proc.wait(timeout=2)
            except Exception:
                try:
                    self._audio_proc.kill()
                except Exception:
                    pass
        self._audio_proc = None
        self._audio_mode = None
        if self._temp_wav and os.path.isfile(self._temp_wav):
            try:
                os.remove(self._temp_wav)
            except OSError:
                pass
        self._temp_wav = None

    def stop(self):
        """Stop playback and release video resources."""
        self._playing = False
        self._stop_audio()
        if self._after_id is not None:
            try:
                self.canvas.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        self.canvas.delete("all")

    def cleanup(self):
        """Stop playback and delete the temp preview file."""
        self.stop()
        if self._temp_path and os.path.isfile(self._temp_path):
            try:
                os.remove(self._temp_path)
            except OSError:
                pass
        self._temp_path = None

    def build_and_play(self, build_fn: Callable[[str], tuple], schedule_on_ui: Callable[[Callable], None]):
        """
        build_fn(output_path) -> (ok, message) using intro_creator.build_intro_video.
        schedule_on_ui(fn) posts callbacks to the Tk main thread.
        """
        if not CV2_AVAILABLE:
            self._set_status("Video preview requires opencv-python (pip install opencv-python).")
            return

        if self._build_thread and self._build_thread.is_alive():
            self._set_status("Preview render already in progress...")
            return

        self.stop()
        self._set_status("Rendering preview (same pipeline as export)...")

        def worker():
            temp_path = None
            try:
                fd, temp_path = tempfile.mkstemp(prefix="avc_intro_preview_", suffix=".mp4")
                os.close(fd)
                ok, message = build_fn(temp_path)

                def finish():
                    if self._temp_path and self._temp_path != temp_path and os.path.isfile(self._temp_path):
                        try:
                            os.remove(self._temp_path)
                        except OSError:
                            pass
                    if ok and temp_path and os.path.isfile(temp_path):
                        self._temp_path = temp_path
                        self._start_playback(temp_path)
                    else:
                        if temp_path and os.path.isfile(temp_path):
                            try:
                                os.remove(temp_path)
                            except OSError:
                                pass
                        self._set_status(f"Preview failed: {message}")

                schedule_on_ui(finish)
            except Exception as exc:
                message = str(exc)
                schedule_on_ui(lambda m=message: self._set_status(f"Preview failed: {m}"))

        self._build_thread = threading.Thread(target=worker, daemon=True)
        self._build_thread.start()

    def _start_audio_ffplay(self, video_path: str) -> bool:
        if not self._ffplay_path:
            return False
        try:
            self._audio_proc = popen_hidden(
                [
                    self._ffplay_path,
                    "-nodisp",
                    "-autoexit",
                    "-loglevel",
                    "error",
                    video_path,
                ],
            )
            self._audio_mode = "ffplay"
            return True
        except Exception:
            self._audio_proc = None
            return False

    def _start_audio_ffmpeg_winsound(self, video_path: str) -> bool:
        if os.name != "nt" or not self._ffmpeg_path:
            return False
        try:
            import winsound
        except ImportError:
            return False

        fd, wav_path = tempfile.mkstemp(prefix="avc_intro_audio_", suffix=".wav")
        os.close(fd)
        result = run_hidden(
            [
                self._ffmpeg_path,
                "-y",
                "-i",
                video_path,
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",
                "-ac",
                "2",
                wav_path,
            ],
            capture_output=True,
        )
        if result.returncode != 0 or not os.path.isfile(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass
            return False

        self._temp_wav = wav_path
        winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        self._audio_mode = "winsound"
        return True

    def _start_audio(self, video_path: str):
        self._stop_audio()
        if self._start_audio_ffplay(video_path):
            return
        if self._start_audio_ffmpeg_winsound(video_path):
            return

    def _start_playback(self, video_path: str):
        self.stop()
        self._capture = cv2.VideoCapture(video_path)
        if not self._capture.isOpened():
            self._set_status("Could not open preview video.")
            self._capture = None
            return

        fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0
        fps = max(10.0, min(60.0, float(fps)))
        frame_count = int(self._capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if frame_count > 0 else 0.0
        self._playing = True
        self._start_audio(video_path)
        if self._audio_mode == "ffplay":
            audio_note = "with audio"
        elif self._audio_mode == "winsound":
            audio_note = "with audio"
        else:
            audio_note = "no audio (add ffplay.exe to your ffmpeg folder)"

        self._set_status(
            f"Playing preview · {duration:.1f}s loop · {audio_note} · matches exported file"
        )
        self._play_next_frame(int(1000 / fps))

    def _play_next_frame(self, delay_ms: int):
        if not self._playing or self._capture is None:
            return

        ok, frame = self._capture.read()
        if not ok:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._start_audio(self._temp_path or "")
            ok, frame = self._capture.read()
        if not ok:
            self._set_status("Preview playback ended.")
            self.stop()
            return

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        src_w, src_h = image.size
        scale = self._preview_width / max(src_w, 1)
        preview_h = max(1, int(src_h * scale))
        image = image.resize((self._preview_width, preview_h), Image.Resampling.LANCZOS)

        self._photo = ImageTk.PhotoImage(image)
        self.canvas.configure(width=self._preview_width, height=preview_h)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

        self._after_id = self.canvas.after(delay_ms, lambda: self._play_next_frame(delay_ms))
