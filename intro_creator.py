"""
Build custom intro videos from templates, animated text, and optional sound effects.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
from dataclasses import dataclass

from process_utils import run_hidden
from typing import List, Optional, Tuple

INTRO_TEMPLATE_NAMES = ("Blue", "Blue2", "Lion", "Play", "Red", "UFO")

FONT_STYLES = {
    "Arial Bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf"),
    "Impact": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "impact.ttf"),
    "Segoe UI Bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "segoeuib.ttf"),
    "Times New Roman Bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "timesbd.ttf"),
    "Comic Sans MS Bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "comicbd.ttf"),
}

FONT_SIZES = {
    "Small": 56,
    "Medium": 72,
    "Large": 96,
    "Extra Large": 120,
}

ANIMATIONS = ("Fade In", "Slide Up", "Pop", "Drop In")
DEFAULT_SECONDS_FROM_END = 1.5
DEFAULT_LINE2_DELAY = 0.75
MIN_LINE2_DELAY = 0.5
MAX_LINE2_DELAY = 3.0
ANIMATION_DURATION = 0.45
LINE_GAP_RATIO = 0.38


@dataclass
class TextPromptSpec:
    text: str
    sound_effect_path: Optional[str] = None


@dataclass
class IntroBuildRequest:
    template_name: str
    output_path: str
    prompts: List[TextPromptSpec]
    seconds_from_end: float = DEFAULT_SECONDS_FROM_END
    line2_delay: float = DEFAULT_LINE2_DELAY
    font_style: str = "Arial Bold"
    font_size_label: str = "Large"
    animation: str = "Fade In"
    template_path: Optional[str] = None
    search_roots: Optional[List[str]] = None
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None


def _run(cmd: List[str], timeout: int = 300) -> Tuple[bool, str]:
    try:
        result = run_hidden(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, result.stdout or ""
        return False, (result.stderr or result.stdout or "FFmpeg failed").strip()
    except Exception as exc:
        return False, str(exc)


def resolve_ffmpeg_tools(search_roots: Optional[List[str]] = None) -> Tuple[str, str]:
    roots = list(search_roots or [])
    roots.append(os.path.dirname(os.path.abspath(__file__)))
    for root in roots:
        ff = os.path.join(root, "ffmpeg", "ffmpeg.exe")
        fp = os.path.join(root, "ffmpeg", "ffprobe.exe")
        if os.path.isfile(ff) and os.path.isfile(fp):
            return ff, fp
    import shutil

    return shutil.which("ffmpeg") or "", shutil.which("ffprobe") or ""


def resolve_template_path(name: str, search_roots: Optional[List[str]] = None) -> str:
    filename = f"{name}.mp4" if not name.lower().endswith(".mp4") else name
    stem = os.path.splitext(filename)[0]
    roots = list(search_roots or [])
    roots.append(os.path.dirname(os.path.abspath(__file__)))
    for root in roots:
        for sub in ("IntroTemplates", ""):
            for candidate in (
                os.path.join(root, sub, filename) if sub else os.path.join(root, filename),
                os.path.join(root, sub, f"{stem}.mp4") if sub else os.path.join(root, f"{stem}.mp4"),
            ):
                if os.path.isfile(candidate):
                    return candidate
    raise FileNotFoundError(f"Intro template not found: {name}")


def list_sound_effects(sound_effects_dir: str) -> List[str]:
    if not os.path.isdir(sound_effects_dir):
        return []
    return sorted(
        name
        for name in os.listdir(sound_effects_dir)
        if name.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"))
    )


def probe_media(ffprobe: str, path: str) -> dict:
    cmd = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    ok, out = _run(cmd, timeout=30)
    if not ok:
        raise RuntimeError(out or "ffprobe failed")
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or video.get("duration") or 0)
    return {
        "duration": duration,
        "width": int(video.get("width") or 1920),
        "height": int(video.get("height") or 1080),
        "has_audio": bool(audio),
    }


def _escape_drawtext(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace("%", "\\%")
    return escaped


def _font_path(font_style: str) -> str:
    path = FONT_STYLES.get(font_style) or FONT_STYLES["Arial Bold"]
    if os.path.isfile(path):
        return path.replace("\\", "/").replace(":", "\\:")
    for fallback in FONT_STYLES.values():
        if os.path.isfile(fallback):
            return fallback.replace("\\", "/").replace(":", "\\:")
    return ""


def _alpha_expr(t_start: float, anim_dur: float) -> str:
    ts = f"{t_start:.3f}"
    ad = f"{anim_dur:.3f}"
    end = f"{t_start + anim_dur:.3f}"
    return f"if(lt(t\\,{ts})\\,0\\,if(lt(t\\,{end})\\,(t-{ts})/{ad}\\,1))"


def _y_expr(base_y: float, t_start: float, anim: str, anim_dur: float) -> str:
    y = float(base_y)
    if anim not in ("Slide Up", "Drop In"):
        return f"{y:.1f}"
    ts = f"{t_start:.3f}"
    ad = f"{anim_dur:.3f}"
    end = f"{t_start + anim_dur:.3f}"
    y_start = y + 50.0 if anim == "Slide Up" else y - 50.0
    y0 = f"{y_start:.1f}"
    y1 = f"{y:.1f}"
    return (
        f"if(lt(t\\,{ts})\\,{y0}\\,"
        f"if(lt(t\\,{end})\\,{y0}*(1-(t-{ts})/{ad})+{y1}*((t-{ts})/{ad})\\,{y1}))"
    )


def _fontsize_expr(base_size: int, t_start: float, anim: str, anim_dur: float) -> str:
    bs = str(base_size)
    if anim != "Pop":
        return bs
    ts = f"{t_start:.3f}"
    ad = f"{anim_dur:.3f}"
    end = f"{t_start + anim_dur:.3f}"
    lo = int(base_size * 0.72)
    return f"if(lt(t\\,{ts})\\,{lo}\\,if(lt(t\\,{end})\\,{lo}+({bs}-{lo})*((t-{ts})/{ad})\\,{bs}))"


def _line_y_positions(line_count: int, font_size: int, height: int) -> List[float]:
    gap = font_size * LINE_GAP_RATIO
    block_height = font_size * line_count + gap * max(0, line_count - 1)
    top = (height - block_height) / 2
    return [top + index * (font_size + gap) for index in range(line_count)]


def intro_metadata_path(video_path: str) -> str:
    return f"{video_path}.meta.json"


def write_intro_metadata(
    video_path: str,
    visual_duration: float,
    audio_duration: float,
    template_name: Optional[str] = None,
) -> None:
    """Store template video length so compilation cuts on animation end, not SFX end."""
    payload = {
        "visual_duration": round(float(visual_duration), 4),
        "audio_duration": round(float(audio_duration), 4),
    }
    if template_name:
        payload["template_name"] = str(template_name)
    with open(intro_metadata_path(video_path), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def read_intro_metadata(video_path: str) -> Tuple[Optional[float], Optional[float]]:
    path = intro_metadata_path(video_path)
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        visual = float(data.get("visual_duration") or 0)
        audio = float(data.get("audio_duration") or 0)
        if visual <= 0:
            return None, None
        return visual, audio if audio > 0 else visual
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None, None


def read_intro_template_name(video_path: str) -> Optional[str]:
    path = intro_metadata_path(video_path)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        name = (data.get("template_name") or "").strip()
        return name or None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80] if cleaned else "CustomIntro"


def build_intro_video(request: IntroBuildRequest) -> Tuple[bool, str]:
    prompts = [p for p in request.prompts if (p.text or "").strip()]
    if not prompts:
        return False, "Enter at least one line of intro text."
    if len(prompts) > 2:
        return False, "At most two text lines are supported."

    ffmpeg, ffprobe = request.ffmpeg_path, request.ffprobe_path
    if not ffmpeg or not ffprobe:
        ffmpeg, ffprobe = resolve_ffmpeg_tools(request.search_roots)
    if not ffmpeg or not ffprobe:
        return False, "FFmpeg was not found."

    template_path = request.template_path or resolve_template_path(
        request.template_name, request.search_roots
    )
    if not os.path.isfile(template_path):
        return False, f"Template not found: {template_path}"

    font_path = _font_path(request.font_style)
    if not font_path:
        return False, "No Windows font file was found for the selected style."

    font_size = FONT_SIZES.get(request.font_size_label, FONT_SIZES["Large"])
    media = probe_media(ffprobe, template_path)
    duration = media["duration"]
    height = media["height"]
    if duration <= 0:
        return False, "Template video duration could not be read."

    appear_at = max(0.05, duration - float(request.seconds_from_end))
    line2_delay = max(MIN_LINE2_DELAY, min(MAX_LINE2_DELAY, float(request.line2_delay)))
    line_appear_times = [appear_at]
    if len(prompts) > 1:
        line_appear_times.append(appear_at + line2_delay)

    anim = request.animation if request.animation in ANIMATIONS else "Fade In"
    anim_dur = min(ANIMATION_DURATION, max(0.15, float(request.seconds_from_end) * 0.5))
    y_positions = _line_y_positions(len(prompts), font_size, height)

    filter_parts: List[str] = []
    last_v = "0:v"
    for index, prompt in enumerate(prompts):
        t_start = line_appear_times[index]
        text = _escape_drawtext(prompt.text.strip())
        alpha = _alpha_expr(t_start, anim_dur)
        y_expression = _y_expr(y_positions[index], t_start, anim, anim_dur)
        fs_expression = _fontsize_expr(font_size, t_start, anim, anim_dur)
        out_v = f"v{index + 1}"
        filter_parts.append(
            f"[{last_v}]drawtext=fontfile='{font_path}':text='{text}':"
            f"fontcolor=white:borderw=3:bordercolor=black@0.85:"
            f"x=(w-text_w)/2:y={y_expression}:fontsize={fs_expression}:"
            f"alpha='{alpha}'[{out_v}]"
        )
        last_v = out_v

    # Video always ends when the template ends (no frozen hold for long SFX).
    # Audio may run longer and continues over gameplay during compilation.
    audio_duration = duration
    for index, prompt in enumerate(prompts):
        if prompt.sound_effect_path and os.path.isfile(prompt.sound_effect_path):
            sfx_meta = probe_media(ffprobe, prompt.sound_effect_path)
            sfx_dur = float(sfx_meta.get("duration") or 0)
            audio_duration = max(audio_duration, line_appear_times[index] + sfx_dur)

    filter_parts.append(f"[{last_v}]trim=duration={duration:.3f},setpts=PTS-STARTPTS[vout]")

    audio_labels: List[str] = []
    if media["has_audio"]:
        filter_parts.append("[0:a]volume=0.35[basea]")
        audio_labels.append("[basea]")
    else:
        filter_parts.append(
            f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=0:{duration:.3f}[basea]"
        )
        audio_labels.append("[basea]")

    cmd = [ffmpeg, "-y", "-i", template_path]
    sfx_input_index = 1
    for index, prompt in enumerate(prompts):
        if not prompt.sound_effect_path or not os.path.isfile(prompt.sound_effect_path):
            continue
        cmd.extend(["-i", prompt.sound_effect_path])
        delay_ms = int(line_appear_times[index] * 1000)
        label = f"sfx{sfx_input_index}"
        filter_parts.append(f"[{sfx_input_index}:a]adelay={delay_ms}|{delay_ms},volume=1.0[{label}]")
        audio_labels.append(f"[{label}]")
        sfx_input_index += 1

    mix_inputs = "".join(audio_labels)
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(audio_labels)}:duration=longest:dropout_transition=0[a_mix]"
    )
    filter_parts.append(
        f"[a_mix]apad=whole_dur={audio_duration:.3f},atrim=0:{audio_duration:.3f}[aout]"
    )

    filter_complex = ";".join(filter_parts)
    os.makedirs(os.path.dirname(os.path.abspath(request.output_path)), exist_ok=True)
    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t:v",
            f"{duration:.3f}",
            "-t:a",
            f"{audio_duration:.3f}",
            "-metadata",
            f"visual_duration={duration:.4f}",
            "-metadata",
            f"template_name={request.template_name}",
            request.output_path,
        ]
    )

    ok, err = _run(cmd, timeout=600)
    if ok and os.path.isfile(request.output_path):
        try:
            write_intro_metadata(
                request.output_path,
                duration,
                audio_duration,
                template_name=request.template_name,
            )
        except OSError:
            pass
        return True, request.output_path
    return False, err or "Intro video was not created."


def default_output_name(line1: str) -> str:
    return f"{_sanitize_filename(line1)}.mp4"


def resolve_font_file(font_style: str) -> str:
    """Return a native font file path for PIL (unescaped)."""
    path = FONT_STYLES.get(font_style) or FONT_STYLES["Arial Bold"]
    if os.path.isfile(path):
        return path
    for fallback in FONT_STYLES.values():
        if os.path.isfile(fallback):
            return fallback
    return ""


def preview_timestamp(duration: float, seconds_from_end: float) -> float:
    """Time in the template to preview (text fully visible near the end)."""
    appear_at = max(0.05, duration - float(seconds_from_end))
    anim_dur = min(ANIMATION_DURATION, max(0.15, float(seconds_from_end) * 0.5))
    return min(max(0.0, duration - 0.05), appear_at + anim_dur + 0.05)


def extract_template_frame_image(
    template_name: str,
    seconds_from_end: float,
    search_roots: Optional[List[str]] = None,
    ffmpeg_path: Optional[str] = None,
    ffprobe_path: Optional[str] = None,
):
    """Extract one preview frame from a template as a PIL Image."""
    from PIL import Image

    ffmpeg, ffprobe = ffmpeg_path or "", ffprobe_path or ""
    if not ffmpeg or not ffprobe:
        ffmpeg, ffprobe = resolve_ffmpeg_tools(search_roots)
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg was not found.")

    template_path = resolve_template_path(template_name, search_roots)
    media = probe_media(ffprobe, template_path)
    duration = float(media["duration"] or 0)
    if duration <= 0:
        raise RuntimeError("Could not read template duration.")

    timestamp = preview_timestamp(duration, seconds_from_end)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        template_path,
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "pipe:1",
    ]
    try:
        result = run_hidden(
            cmd,
            capture_output=True,
            timeout=60,
        )
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
    if result.returncode != 0 or not result.stdout:
        err = (result.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(err or "Could not extract preview frame.")
    return Image.open(io.BytesIO(result.stdout)).convert("RGBA")


def render_intro_preview_image(
    frame_image,
    lines: List[str],
    font_style: str = "Arial Bold",
    font_size_label: str = "Large",
    preview_width: int = 480,
    placeholder: str = "Your text here",
):
    """Composite centered text on a template frame for GUI preview."""
    from PIL import Image, ImageDraw, ImageFont

    lines = [line.strip() for line in lines if line and line.strip()]
    if not lines:
        lines = [placeholder]

    font_size = FONT_SIZES.get(font_size_label, FONT_SIZES["Large"])
    font_file = resolve_font_file(font_style)

    source = frame_image.convert("RGBA")
    src_w, src_h = source.size
    scale = preview_width / max(src_w, 1)
    preview_h = max(1, int(src_h * scale))
    canvas = source.resize((preview_width, preview_h), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(canvas)

    scaled_font_size = max(12, int(font_size * scale))
    try:
        font = ImageFont.truetype(font_file, scaled_font_size) if font_file else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()

    y_positions = _line_y_positions(len(lines), scaled_font_size, preview_h)
    for index, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=max(2, int(3 * scale)))
        text_w = bbox[2] - bbox[0]
        x = (preview_width - text_w) / 2
        y = y_positions[index]
        stroke = max(2, int(3 * scale))
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke,
            stroke_fill=(0, 0, 0, 220),
        )

    return canvas.convert("RGB")
