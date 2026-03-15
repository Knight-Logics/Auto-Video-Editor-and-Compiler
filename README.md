# Auto Video Editor and Compiler

Auto Video Editor and Compiler is a Windows-based video automation tool that turns a folder of short clips into one compiled, YouTube-ready output video.

## What It Does

The application is built for workflows where many short highlight clips are captured over time, then combined into a single finished video with:

- optional intro video
- background music
- automatic end trimming per clip
- GUI-based path and asset selection
- FFmpeg-powered compilation

This makes it especially useful for gaming highlights, clipped moments, and recurring video recap workflows.

## Current Use Case

The current workflow is well suited for creators using short recorded clips such as Xbox Game Bar "Record That" captures or similar quick-capture tools.

## Core Features

- Windows GUI for input, output, intro, and music configuration
- End-trim selection to normalize clip lengths
- Bundled intro and music asset support
- FFmpeg-backed compilation pipeline
- Output-folder and log access from the app
- Packaged standalone distribution support
- Release-oriented repo structure for shipping bundled builds

## Technical Notes

The repository currently includes:

- Core compilation logic in `UOVidCompiler.py`
- GUI variants including `UOVidCompiler_GUI.py` and `UOVidCompiler_GUI_Tabbed.py`
- Workflow tabs in `tab_auto_clipper.py` and `tab_vid_compiler.py`
- Included asset folders for `Intros`, `Music`, `icons`, and `ffmpeg`
- Packaging files and release/distribution guidance

## Business Value

This project demonstrates Knight Logics capability in:

- media workflow automation
- Python desktop tooling
- FFmpeg pipeline integration
- packaging internal tools into end-user workflows
- reducing repetitive manual editing time

It is one of the clearest automation case studies for GitHub and Upwork because the outcome is easy to understand: fewer manual editing steps and faster content production.

## Installation

### Option 1: Release Build

Download the latest release bundle:

https://github.com/Knight-Logics/Auto-Video-Editor-and-Compiler/releases

The packaged build includes the executable plus required bundled assets.

### Option 2: Run From Source

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the GUI:

```bash
python UOVidCompiler_GUI.py
```

## Typical Workflow

1. Choose the folder containing captured clips
2. Choose trim duration from the end of each clip
3. Select optional intro video
4. Select music track or random music mode
5. Run the compiler
6. Review the final compiled output and logs

## Status

Operational and already useful in production-style clip compilation workflows. Future improvements are still possible, but the current version is a strong demonstration of practical automation engineering.

## License

MIT