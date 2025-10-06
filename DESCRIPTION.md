# AutoFire - Keyboard Automation Tool

## Short Description

A Windows keyboard automation tool that automatically repeats key presses while you hold a trigger key. Features dual output modes (SendInput/PostMessage), multi-language UI, and DirectInput game compatibility.

## Detailed Description

AutoFire is a lightweight, educational keyboard automation tool for Windows that enables rapid-fire key repetition through a simple hold-and-release mechanism. Designed with both safety and compatibility in mind, it offers two distinct input simulation methods to work with a wide range of applications and games.

### Key Features

**🎮 Dual Output Modes**
- **SendInput Mode (Default):** Hardware-level input simulation using scan codes, compatible with DirectInput games that read directly from keyboard drivers. Works like AutoHotkey.
- **PostMessage Mode:** Message queue-based simulation for safer, window-specific targeting. Ideal for applications that process standard Windows messages.

**🪟 Smart Window Detection**
- Auto-detect and list all visible windows
- Dropdown selection for easy targeting
- Real-time window list refresh
- Manual window title input support

**⌨️ Flexible Configuration**
- Customizable trigger key (key you hold)
- Customizable output key (key that auto-fires)
- Adjustable repeat interval (1-1000ms)
- Pass-through mode (optional trigger key blocking)

**🌐 Multi-Language Support**
- English interface
- Traditional Chinese (繁體中文)
- Simplified Chinese (简体中文)
- One-click language switching

**💾 User-Friendly Design**
- Persistent configuration (auto-save/load)
- Intuitive GUI with clear status indicators
- No complex setup required
- Portable executable available

### How It Works

1. **You hold** a trigger key (e.g., "E")
2. **System detects** the key press via Windows keyboard hook
3. **Background thread** validates target window and starts loop
4. **Key simulation** sends repeated keypresses at your configured interval
5. **You release** the trigger key to stop

### Technical Highlights

- Built with Python and Tkinter
- Uses legitimate Windows APIs (SendInput, PostMessage, FindWindowW)
- Thread-safe architecture with proper synchronization
- Comprehensive test suite (pytest)
- No memory reading/writing
- No code injection or DLL hooking
- Operates entirely outside target process

### Use Cases

**Educational & Learning:**
- Understanding Windows API functionality
- Learning input simulation techniques
- Exploring keyboard hook mechanisms

**Accessibility:**
- Reduce repetitive strain from button mashing
- Assist users with mobility limitations
- Customize input patterns for accessibility needs

**Testing & Automation:**
- UI testing and automation
- Application stress testing
- Input pattern validation

### System Requirements

- **OS:** Windows Vista or later (7/8/10/11)
- **Python:** 3.8+ (for source) or standalone .exe
- **Privileges:** Administrator (required for keyboard hooks)
- **Dependencies:** `keyboard` library (included in .exe)

### Safety & Compliance

⚠️ **For Educational Purposes Only**

This tool uses standard Windows APIs identical to those used by:
- Remote Desktop software (TeamViewer, RDP)
- Accessibility tools (screen readers, voice control)
- Automation software (AutoHotkey, Selenium)
- Game streaming services (Steam Remote Play)

**Important Notes:**
- Does NOT inject code into applications
- Does NOT read or modify memory
- Does NOT hook into application functions
- Always check application Terms of Service before use
- Some games prohibit automation tools
- Use responsibly and at your own risk

### What Makes AutoFire Different

**Compared to AutoHotkey:**
- Simpler, focused interface for rapid-fire functionality
- Visual window selection dropdown
- Built-in multi-language support
- Dual mode selection (SendInput/PostMessage)

**Compared to generic macro tools:**
- Lightweight and purpose-built
- No complex scripting required
- Clear safety documentation
- Educational code structure

**Compared to PostMessage-only tools:**
- SendInput mode for DirectInput compatibility
- Works with modern games that ignore message queues
- Hardware-level scan code simulation

### Architecture

```
┌─────────────────────────────────────────┐
│          Tkinter GUI Layer              │
│  (Config, Status, Language Selection)   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       AutoFire Engine Core              │
│  (Thread Management, State Control)     │
└──────────┬──────────────┬───────────────┘
           │              │
    ┌──────▼──────┐  ┌───▼──────────────┐
    │  Keyboard   │  │  Output Handler  │
    │    Hook     │  │  (SendInput/     │
    │  (Trigger)  │  │   PostMessage)   │
    └─────────────┘  └──────────────────┘
```

### Version History

**v1.0.0 (2025-10-06)**
- Initial release
- SendInput and PostMessage support
- Multi-language UI (EN/繁中/简中)
- Window auto-detection
- Comprehensive test coverage
- Standalone executable distribution

### License & Disclaimer

This project is provided for educational and learning purposes. The author is not responsible for any misuse or violations of Terms of Service. Users must understand how Windows APIs work, respect software Terms of Service, and use the tool responsibly and ethically.

### Links

- **GitHub Repository:** https://github.com/HugoLi0213/AutoFire
- **Documentation:** See README.md files (EN/繁中/简中)
- **Security Details:** See SECURITY.md
- **Download:** Check Releases for standalone executable

### Author

**Hugo**  
Contact: Via GitHub Issues  
Last Updated: October 6, 2025

---

## Quick Description Variants

### GitHub About (Short)
```
Windows keyboard automation tool with dual input modes (SendInput/PostMessage), multi-language UI, and DirectInput compatibility. For educational purposes.
```

### One-Line Description
```
Lightweight Windows keyboard auto-fire tool with hardware-level input simulation and multi-language support.
```

### Marketing Description
```
AutoFire transforms repetitive key pressing into a simple hold-and-release action. With both hardware-level (SendInput) and message-based (PostMessage) simulation, it works with virtually any Windows application or game. Features an intuitive GUI with multi-language support (English/繁中/简中) and smart window detection. Perfect for accessibility, testing, or understanding Windows input APIs. Educational tool with comprehensive safety documentation.
```

### Tags/Keywords
```
keyboard automation, input simulation, windows api, sendinput, postmessage, 
directinput, autohotkey alternative, macro tool, rapid fire, auto clicker,
educational software, accessibility tool, tkinter gui, python windows,
multi-language, open source
```
