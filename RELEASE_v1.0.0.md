# AutoFire v1.0.0 - Initial Release

> **⚠️ For Educational Purposes Only**

## 🎉 First Release!

This is the first official release of AutoFire - a Windows keyboard automation tool with dual input modes, multi-language support, and DirectInput compatibility.

## 📦 What's Included

**Download:** `AutoFire_v1.0.0_Release.zip`

The release package contains:
- ✅ `AutoFire.exe` - Standalone executable (no Python installation required)
- 📖 `README.md` - English documentation
- 📖 `README_TW.md` - Traditional Chinese documentation (繁體中文)
- 📖 `README_CN.md` - Simplified Chinese documentation (简体中文)
- 🛡️ `SECURITY.md` - Security and safety information
- 📋 `RELEASE_NOTES.txt` - Quick start guide

## ✨ Key Features

### 🎮 Dual Output Modes
- **SendInput Mode (Default):** Hardware-level input simulation with scan codes
  - ✅ Compatible with DirectInput games
  - ✅ Works like AutoHotkey
  - ✅ Best game compatibility
  
- **PostMessage Mode:** Message queue-based simulation
  - ✅ Safer, lower detection risk
  - ✅ Window-specific targeting
  - ⚠️ May not work with DirectInput games

### 🪟 Smart Window Detection
- Auto-detect all visible windows
- Dropdown selection with search
- Real-time window list refresh
- Manual title input support

### 🌐 Multi-Language UI
- English interface
- Traditional Chinese (繁體中文)
- Simplified Chinese (简体中文)
- One-click language switching (EN/繁中 button)

### ⚙️ Flexible Configuration
- Customizable trigger key (key you hold)
- Customizable output key (key that auto-fires)
- Adjustable interval: 1-1000ms
- Pass-through mode option
- Auto-save/load settings

## 🚀 Quick Start

1. **Download** `AutoFire_v1.0.0_Release.zip`
2. **Extract** all files to a folder
3. **Right-click** `AutoFire.exe` → **Run as Administrator**
4. **Configure:**
   - Select target window from dropdown
   - Set trigger key (e.g., `e`)
   - Set output key (e.g., `r`)
   - Set interval (e.g., `100ms`)
   - Check "Use SendInput" for games
5. **Click Start** and hold trigger key!

## 📋 System Requirements

- **OS:** Windows Vista or later (7/8/10/11)
- **Privileges:** Administrator (required for keyboard hooks)
- **Size:** ~11 MB (standalone, includes all dependencies)

## 🛡️ Safety & Security

This tool uses **legitimate Windows APIs** identical to:
- Remote Desktop (TeamViewer, RDP)
- Accessibility tools (screen readers)
- Automation software (AutoHotkey, Selenium)
- Game streaming (Steam Remote Play)

**What it does NOT do:**
- ❌ Read or write game memory
- ❌ Inject code into applications
- ❌ Hook into application functions
- ❌ Modify game files

**Important:**
- Always check application Terms of Service
- Some games prohibit automation tools
- Use responsibly and ethically
- For educational purposes

## 🔍 Technical Details

- **Built with:** Python 3.13.3 + Tkinter
- **APIs Used:** SendInput, PostMessage, FindWindowW, EnumWindows
- **Architecture:** Thread-safe with proper synchronization
- **Testing:** Comprehensive pytest suite (8 passed, 1 skipped)
- **Packaging:** PyInstaller (single executable)

## 📝 What's New in v1.0.0

Initial release includes:
- ✅ SendInput mode for DirectInput compatibility
- ✅ PostMessage mode for message queue simulation
- ✅ Multi-language UI (EN/繁中/简中)
- ✅ Window auto-detection dropdown
- ✅ Configurable trigger and output keys
- ✅ Adjustable repeat interval (1-1000ms)
- ✅ Pass-through mode option
- ✅ Persistent configuration
- ✅ Comprehensive documentation
- ✅ Full test coverage

## 📖 Documentation

- **English:** [README.md](https://github.com/HugoLi0213/AutoFire/blob/main/README.md)
- **繁體中文:** [README_TW.md](https://github.com/HugoLi0213/AutoFire/blob/main/README_TW.md)
- **简体中文:** [README_CN.md](https://github.com/HugoLi0213/AutoFire/blob/main/README_CN.md)
- **Security:** [SECURITY.md](https://github.com/HugoLi0213/AutoFire/blob/main/SECURITY.md)
- **Description:** [DESCRIPTION.md](https://github.com/HugoLi0213/AutoFire/blob/main/DESCRIPTION.md)

## 🐛 Known Issues

None reported yet. Please open an issue if you encounter problems!

## 💬 Support

- **Issues:** [GitHub Issues](https://github.com/HugoLi0213/AutoFire/issues)
- **Discussions:** [GitHub Discussions](https://github.com/HugoLi0213/AutoFire/discussions)

## 📜 License & Disclaimer

This project is provided for **educational and learning purposes only**. 

The author is not responsible for any misuse or violations of Terms of Service. Users must:
- ✅ Understand how Windows APIs work
- ✅ Respect software Terms of Service
- ✅ Use responsibly and ethically
- ⚠️ Accept all risks associated with use

---

**Author:** Hugo  
**Release Date:** October 6, 2025  
**Tag:** `1.0`  
**Commit:** [View on GitHub](https://github.com/HugoLi0213/AutoFire/tree/1.0)

## 📥 Downloads

- **Windows Executable:** `AutoFire_v1.0.0_Release.zip` (11.3 MB)
- **Source Code:** Available in repository

Thank you for using AutoFire! 🎉
