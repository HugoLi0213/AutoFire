# AutoFire - Keyboard Automation Tool

> **⚠️ For Educational Purposes Only**  
> This tool is provided for learning and educational purposes. Users are responsible for ensuring compliance with applicable Terms of Service and local laws.

**Author:** Hugo  
**Last Updated:** 2025-10-06

A Windows keyboard automation tool that automatically repeats key presses while you hold a trigger key. Supports both **SendInput** (hardware-level, AHK-like) and **PostMessage** (message queue) methods.

🌐 **[繁體中文說明](README_TW.md)** | **[简体中文说明](README_CN.md)**

---

## 🛡️ Security & Safety

### Why This Tool is Safe

This application uses **legitimate Windows API calls** - the same APIs used by trusted software:

| What It Does | What It Does NOT Do |
|-------------|---------------------|
| ✅ Sends keyboard events via API | ❌ Does NOT read game memory |
| ✅ Uses standard Windows functions | ❌ Does NOT write to game memory |
| ✅ Operates outside game process | ❌ Does NOT inject DLLs |
| ✅ Same as AutoHotkey/RDP | ❌ Does NOT hook game functions |

### Legitimate Uses

This tool uses the **same technology** as:
- 🖥️ **Remote Desktop** (TeamViewer, Windows RDP)
- ♿ **Accessibility Tools** (Screen readers, voice control)
- 🤖 **Automation Software** (AutoHotkey, Selenium)
- 🎮 **Game Streaming** (Steam Remote Play)

### Important Notes

⚠️ **Always check game Terms of Service** - Some games prohibit ANY automation  
⚠️ **Use responsibly** - Games can still detect unusual behavior patterns  
⚠️ **Educational purpose** - Use at your own risk

---

## 🚀 Features

- 🎮 **Two Output Modes**: SendInput (hardware-level, DirectInput compatible) or PostMessage (safer)
- 🪟 **Auto-detect Windows**: Dropdown list of all open windows
- ⌨️ **Customizable Keys**: Set trigger and output keys
- ⚡ **Adjustable Speed**: Configure interval (1-1000ms)
- 🌐 **Multi-language UI**: English / 繁體中文 switchable interface
- 🔄 **Window Refresh**: Update window list on-the-fly
- 🎯 **Pass-through Mode**: Optional key blocking
- 💾 **Persistent Config**: Saves your settings automatically
- 🧪 **Fully Tested**: Comprehensive pytest test suite

---

## 📋 Quick Start

### Installation

1. **Install Python 3.8+** (if not already installed)
2. **Install dependencies:**
   ```cmd
   pip install keyboard
   ```

3. **Run as Administrator** (required for keyboard hooks):
   ```cmd
   python autofire_ui.py
   ```

### Basic Usage

1. **Select Target Window** - Choose from dropdown or type window title (click 🔄 to refresh)
2. **Set Trigger Key** - The key you'll hold (e.g., `e`)
3. **Set Output Key** - The key to auto-fire (e.g., `r`)
4. **Set Interval** - How fast to repeat in milliseconds (default: 100ms)
5. **Choose Mode** - ✅ Check "Use SendInput" for better game compatibility
6. **Click Start** - Hold trigger key to activate, release to stop

### 📸 Example Configuration

![AutoFire Configuration Example](docs/screenshot_tale_runner.png)

**Tale Runner Example Settings:**
- **Trigger Key:** `e` (hold this key)
- **Output Key:** `e` (this key will auto-fire)
- **Target Window:** `Tales Runner`
- **Interval:** `100ms` (fires 10 times per second)
- **SendInput:** ✅ Enabled (for DirectInput game compatibility)

**Result:** Hold `E` key → Auto-fires `E` every 100ms → Works with DirectInput games!

## 🎮 Output Modes Explained

### SendInput Mode (Recommended, Default)

**How it works:** Simulates hardware-level keyboard input using scan codes
- ✅ Works with **DirectInput games** (games that read directly from keyboard driver)
- ✅ Same method as **AutoHotkey**
- ✅ Better compatibility with modern games
- ⚠️ Slightly more detectable

**Use when:** Game ignores PostMessage (most modern games)

### PostMessage Mode (Alternative)

**How it works:** Sends messages to window's message queue
- ✅ **Safer** - lower detection risk
- ✅ Window-specific targeting
- ❌ Doesn't work with DirectInput games
- ❌ Some games ignore message queue input

**Use when:** You need safer method or target application reads message queue

## ⚙️ How It Works

```
1. You hold trigger key (e.g., "E")
   ↓
2. Keyboard hook detects press
   ↓
3. Background thread starts
   ↓
4. Validates target window exists
   ↓
5. Loop starts:
   - SendInput/PostMessage: KEY_DOWN
   - Wait 20ms
   - SendInput/PostMessage: KEY_UP
   - Wait [your interval]ms
   ↓
6. You release trigger → Loop stops
```

### Windows APIs Used

| API | Purpose | Safe? |
|-----|---------|-------|
| `SendInput()` | Hardware-level input simulation | ✅ Standard API |
| `PostMessageW()` | Message queue input | ✅ Standard API |
| `FindWindowW()` | Locate window by title | ✅ Read-only |
| `EnumWindows()` | List all windows | ✅ Read-only |
| `MapVirtualKeyW()` | Get scan codes | ✅ Read-only |

**No memory reading, no code injection, no DLL hooking.**

---

## 🧪 Testing

```cmd
pytest
```

All tests verify:
- UI functionality
- Thread safety  
- Configuration management
- Input simulation logic
- Error handling

---

## ❓ FAQ

**Q: Does this work with all games?**  
A: Use SendInput mode for best compatibility. PostMessage mode doesn't work with DirectInput games.

**Q: Will I get banned?**  
A: This uses legitimate Windows APIs like AutoHotkey. However, check your game's Terms of Service. Some games prohibit automation.

**Q: Why do I need Administrator privileges?**  
A: Windows requires admin rights for global keyboard hooks to detect your trigger key.

**Q: SendInput vs PostMessage - which should I use?**  
A: SendInput (default) works with more games. PostMessage is safer but less compatible.

**Q: How do I switch languages?**  
A: Click the "EN/繁中" button in the top-right corner of the app.

---

## 📝 Configuration File

Settings are automatically saved to `autofire.json`:

```json
{
  "trigger_key": "e",
  "output_key": "r",
  "interval_ms": 100,
  "window_title": "Tales Runner",
  "pass_through": false,
  "use_sendinput": true,
  "language": "en"
}
```

## 🧪 Testing

Run the test suite:
```cmd
pytest
```

All tests verify: UI functionality, thread safety, config management, and error handling.

---

## 🤝 Contributing

Contributions welcome! Please ensure:
- All tests pass (`pytest`)
- Code follows existing style
- Documentation is updated

---

## 📄 License & Disclaimer

**For Educational Purposes Only**

This project is provided as-is for educational and learning purposes. The author is not responsible for any misuse or violations of Terms of Service. Users must:
- ✅ Understand how Windows APIs work
- ✅ Respect software Terms of Service
- ✅ Use responsibly and ethically
- ⚠️ Accept all risks associated with use
In the future, we can develop more marco apps similar to razer so that more different keyboards can be used.
---

## � Additional Resources

- **[繁體中文完整說明](README_TW.md)** - Traditional Chinese documentation
- **[簡體中文完整說明](README_CN.md)** - Simplified Chinese documentation
- **[Security Details](SECURITY.md)** - Detailed security documentation

**Q: Will I get banned?**  
A: Depends on game rules. Safer than memory cheats, but automation may be prohibited.

**Q: Why doesn't it work in my game?**  
A: Some games use DirectInput or filter PostMessage events.

**Q: Can anti-cheat detect it?**  
A: Behavioral detection can flag patterns, but this doesn't use memory manipulation.

**Q: Why require Administrator?**  
A: For the keyboard hook to detect trigger keys globally.
