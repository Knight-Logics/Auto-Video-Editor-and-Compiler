# GitHub Auto-Update Setup Guide

## Overview
Your application now has automatic update checking! When users launch the app, it checks GitHub for new versions and prompts them to update automatically.

## Setup Steps

### 1. Confirm GitHub Repository

Current release repository:

`https://github.com/Knight-Logics/Auto-Video-Editor-and-Compiler`

### 2. Update Repository Name in Code

Open `UOVidCompiler_GUI.py` and change line ~41:
```python
GITHUB_REPO = "Knight-Logics/Auto-Video-Editor-and-Compiler"
```
This must match the repository where release assets are published.

### 3. Push Code to GitHub

```powershell
cd "E:\Auto Video Compiler"

# Add all files
git add .

# Commit
git commit -m "Release v1.2.1"

# Push to GitHub
git push origin main
```

If it asks for credentials, use a **Personal Access Token** (not password):
- Go to GitHub Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
- Generate new token with `repo` scope
- Use this token as your password

### 4. Create A Release

#### From VS Code Terminal:
```powershell
# Tag the current version
git tag -a v1.2.1 -m "Release v1.2.1"
git push origin v1.2.1
```

#### On GitHub Website:
1. Go to your repo → "Releases" tab
2. Click "Create a new release"
3. Tag: `v1.2.1` (should show as existing tag)
4. Title: `v1.2.1 - Stable Release`
5. Description (changelog):
   ```
   ## Fixes
   - Auto-update checks now point at the Knight Logics release repo
   - Selecting no trim no longer crashes direct compilation
   - Auto Clipper tab imports cleanly
   ```
6. **Attach the executable file**: Click "Attach binaries" and upload:
   - `dist\BMagic_AutoVidCompiler_PERFECT.exe`
7. Click "Publish release"

### 5. For Future Updates

When you make changes and want to push an update:

```powershell
# 1. Update VERSION in UOVidCompiler_GUI.py
# Example: VERSION = "1.2.1" to VERSION = "1.2.2"

# 2. Rebuild executable
python -m PyInstaller BMagic_AutoVidCompiler_PERFECT.spec --clean --noconfirm

# 3. Commit changes
git add .
git commit -m "Release v1.2.2 - Fixed XYZ issue"

# 4. Create tag
git tag -a v1.2.2 -m "Release v1.2.2"

# 5. Push code and tag
git push
git push origin v1.2.2

# 6. Create GitHub Release
# - Go to GitHub → Releases → "Draft a new release"
# - Select tag: v1.2.2
# - Add changelog
# - Upload new .exe file
# - Publish
```

## How Auto-Update Works

1. **On Startup**: App checks GitHub API for latest release
2. **Version Compare**: Compares user's version with latest on GitHub
3. **User Prompt**: If newer version exists, shows dialog with changelog
4. **Download**: User clicks "Yes" → downloads new .exe to temp folder
5. **Install**: Creates batch script that runs when app closes
6. **Auto-Restart**: Batch script replaces old .exe and restarts app

## Version Numbering

Use semantic versioning: `MAJOR.MINOR.PATCH`
- **MAJOR** (1.x.x): Breaking changes, major features
- **MINOR** (x.1.x): New features, non-breaking
- **PATCH** (x.x.1): Bug fixes, small improvements

Examples:
- `1.1.0` → `1.1.1` (bug fix)
- `1.1.1` → `1.2.0` (new feature)
- `1.2.0` → `2.0.0` (major rewrite)

## Testing Auto-Update

1. Build and release v1.2.1
2. Change VERSION to "1.2.2" in code
3. Build and release v1.2.2
4. Run the v1.2.1 executable
5. Should see update prompt automatically!

## Troubleshooting

**Update check fails silently**
- Check GITHUB_REPO is correct username/repo
- Verify GitHub repo is public or token has access
- Check internet connection

**Download fails**
- Ensure .exe file is attached to GitHub release
- Check file isn't too large (>100MB may be slow)

**Update doesn't apply**
- Check user has write permission in app directory
- Windows may block .exe downloads (need to allow)

## Distribution

Just share the GitHub Releases page URL:
`https://github.com/Knight-Logics/Auto-Video-Editor-and-Compiler/releases/latest`

Users download the .exe once, then auto-updates forever!

## Pro Tips

- Always test new version yourself before releasing
- Write clear changelogs so users know what changed
- Keep exe filename consistent: `BMagic_AutoVidCompiler_PERFECT.exe`
- Can delete old releases to save space (keep last 3-5)
- Tag format must match: `v1.2.1` (with 'v' prefix)
