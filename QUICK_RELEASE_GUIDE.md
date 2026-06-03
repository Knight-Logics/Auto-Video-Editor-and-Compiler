# Quick Release Guide - GitHub Auto-Update

## First Time Setup (Do Once)

1. **Create GitHub repo** (if not already done)
2. **Confirm the updater points at the Knight Logics GitHub repo:**
   - Edit `UOVidCompiler_GUI.py` line ~41
   - Expected: `GITHUB_REPO = "Knight-Logics/Auto-Video-Editor-and-Compiler"`
3. **Push code** to GitHub (see GITHUB_UPDATE_SETUP.md for details)

## Every Time You Release an Update

### Step 1: Update Version Number
Edit `UOVidCompiler_GUI.py` line ~39:
```python
VERSION = "1.2.1"  # Change to new version
```

### Step 2: Rebuild Executable
```powershell
cd "E:\Auto Video Compiler"
python -m PyInstaller BMagic_AutoVidCompiler_PERFECT.spec --clean --noconfirm
```

### Step 3: Git Commit and Tag
```powershell
git add .
git commit -m "Release v1.2.1 - Brief description of changes"
git tag -a v1.2.1 -m "Release v1.2.1"
git push
git push origin v1.2.1
```

### Step 4: Create GitHub Release
1. Go to: `https://github.com/Knight-Logics/Auto-Video-Editor-and-Compiler/releases/new`
2. Select tag: `v1.2.1`
3. Title: `v1.2.1 - Short Title`
4. Description (example):
   ```markdown
   ## What's New
   - Fixed trim duration selector bug
   - Added audio format auto-conversion
   - Improved error handling
   
   ## Bug Fixes
   - Video compilation now respects user-selected trim duration
   - Music files in any format now work correctly
   ```
5. **Upload the .exe**: Drag from `dist/BMagic_AutoVidCompiler_PERFECT.exe`
6. Click **Publish release**

### Done! 
Users will automatically see update prompt next time they launch the app.

## Version Numbering Guide

- **Bug fix**: `1.1.0` → `1.1.1`
- **New feature**: `1.1.1` → `1.2.0`
- **Major change**: `1.2.0` → `2.0.0`

## Current Version
**v1.3.8** - Intro cuts on template animation end; long SFX continues over gameplay clips

## Next Release Checklist
- [ ] Update VERSION in UOVidCompiler_GUI.py
- [ ] Rebuild executable
- [ ] Test the new version
- [ ] Commit and push to GitHub
- [ ] Create tag
- [ ] Create GitHub Release
- [ ] Upload .exe file
- [ ] Publish!
