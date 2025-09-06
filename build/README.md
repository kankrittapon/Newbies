# 🏗️ Build Guide - NewbiesBot

## ✅ BUILD SUCCESS!

NewbiesBot has been successfully built!

## Quick Build (Recommended)

```bash
build\build_simple.bat
```

## Alternative Build Options

### 1. Minimal Build
```bash
build\build_minimal.bat
```

### 2. Build with Icon
```bash
build\build_with_icon.bat
```

### 3. Full Build
```bash
build\setup.bat
build\build.bat
```

## Deploy

```bash
build\deploy.bat
```

## Requirements
- **Python 3.12** (use `py -3.12`)
- Windows 10/11
- Nuitka compiler

## Output
- `NewbiesBot.exe` - Single executable (~50-80MB)
- No dependencies required
- Ready to distribute

## Troubleshooting

### Python 3.12 Not Found
```bash
py -0  # Check available versions
py -3.12 --version  # Test Python 3.12
```

### Build Failed
```bash
# Clean and retry
del NewbiesBot.exe
build\build_simple.bat
```

---
**🎉 Build system is working perfectly!**