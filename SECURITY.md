# Security Documentation

## Overview

This application is designed with security and legitimacy as core principles. Unlike invasive cheat software, this tool uses only standard, legitimate Windows API calls.

---

## 🛡️ Security Guarantees

### What This Application DOES

✅ **Uses Legitimate Windows APIs**
- `PostMessage()` - Standard message passing API
- `FindWindowW()` - Window enumeration (read-only)
- `GetWindowTextW()` - Window title reading (read-only)
- `EnumWindows()` - Window listing (read-only)

✅ **Monitors Keyboard Input**
- Uses `keyboard` library (user-mode hooks)
- Only monitors configured trigger key
- Can be toggled on/off at any time

✅ **Sends Window Messages**
- Sends `WM_KEYDOWN` and `WM_KEYUP` to target window
- Messages go through Windows' standard message queue
- Same method used by remote desktop and accessibility software

---

## 🚫 What This Application DOES NOT Do

### Memory Safety

❌ **Does NOT read game memory**
- No memory scanning
- No pattern matching in memory
- No data extraction from game process

❌ **Does NOT write to game memory**
- No value modification
- No cheat injection
- No memory patching

### Process Safety

❌ **Does NOT inject code**
- No DLL injection
- No code cave injection
- No shellcode execution

❌ **Does NOT hook game functions**
- No API hooking
- No function detours
- No import address table (IAT) modification

### System Safety

❌ **Does NOT install drivers**
- No kernel-mode drivers
- No system-level hooks
- No boot-time modifications

❌ **Does NOT hide processes**
- No rootkit behavior
- No process cloaking
- No anti-debugging tricks

---

## 🔍 Why Anti-Cheat Systems Are Unlikely to Block This

### 1. **Legitimate API Usage**

`PostMessage()` is used by countless legitimate applications:

```
Remote Desktop Software:
├─ TeamViewer
├─ Windows Remote Desktop (RDP)
├─ Chrome Remote Desktop
└─ AnyDesk

Accessibility Tools:
├─ Windows Narrator
├─ JAWS Screen Reader
├─ Dragon NaturallySpeaking
└─ Windows On-Screen Keyboard

Automation Software:
├─ AutoHotkey
├─ Selenium (UI testing)
├─ UiPath (RPA)
└─ Blue Prism

Game Streaming:
├─ Steam Remote Play
├─ Xbox Game Streaming
├─ GeForce NOW
└─ Parsec
```

**Blocking `PostMessage` would break all of these**, causing massive false positives and breaking legitimate use cases.

### 2. **No Memory Signature**

Anti-cheat systems primarily scan for:
- Known cheat signatures in memory
- Suspicious memory patterns
- Modified game code
- Injected DLLs

**This application has none of these** because it operates entirely outside the game process.

### 3. **OS-Level Legitimacy**

From Windows' perspective, this application is doing nothing suspicious:
- Standard window enumeration ✅
- Standard message passing ✅
- Standard keyboard monitoring ✅
- No privileged operations (beyond keyboard hook) ✅

### 4. **False Positive Risk**

Anti-cheat developers must balance detection vs. false positives:

```
If they block PostMessage:
├─ Remote workers can't access games ❌
├─ Accessibility users locked out ❌ (legal issues)
├─ UI automation breaks ❌
└─ Corporate tools affected ❌

Risk = Too high, won't implement
```

---

## ⚠️ Limitations & Honest Disclosure

### What Can Still Be Detected

1. **Behavioral Patterns**
   - Perfectly timed inputs (inhuman precision)
   - Sustained high-speed inputs (superhuman speed)
   - Predictable patterns (no variation)

2. **Server-Side Validation**
   - MMO servers tracking actions per second
   - Competitive games logging input timing
   - Anti-cheat analyzing input statistics

3. **Message Queue Analysis**
   - Some games may detect messages not from foreground process
   - May implement message filtering
   - May validate message source

### Games That May Not Work

- **DirectInput-only games**: Only listen to DirectInput, ignore PostMessage
- **Message-filtered games**: Implement custom message filtering
- **Server-validated games**: Server-side checks override client inputs

---

## 🎯 Best Practices for Safe Use

### 1. **Add Randomization** (Future Enhancement)

Instead of:
```python
time.sleep(0.05)  # Fixed 50ms
```

Use:
```python
import random
time.sleep(random.uniform(0.045, 0.055))  # 45-55ms variation
```

### 2. **Respect Game Rules**

Always check:
- Game Terms of Service (ToS)
- End User License Agreement (EULA)
- Community guidelines

### 3. **Use Responsibly**

- ✅ Single-player games (your own experience)
- ✅ Testing/development
- ✅ Accessibility assistance
- ❌ Competitive multiplayer (unfair advantage)
- ❌ Ranked matches
- ❌ Professional esports

### 4. **Monitor for Updates**

Games may update their anti-cheat. If you receive warnings:
- Stop using immediately
- Check for game ToS changes
- Consult community forums

---

## 🔬 Technical Comparison

### This Tool vs. Memory Cheats

| Security Aspect | This Tool | Memory Cheats |
|----------------|-----------|---------------|
| **Detection Method** | Behavioral only | Signature + Memory |
| **Memory Access** | None | Full read/write |
| **Code Injection** | None | Yes (DLLs) |
| **Anti-Cheat Risk** | 🟢 Low | 🔴 Very High |
| **Ban Risk** | 🟡 Moderate¹ | 🔴 Certain |
| **Legal Status** | ✅ Legitimate tool | ❌ ToS violation |
| **System Safety** | ✅ Safe | ⚠️ Risky |

¹ Depends on game's stance on automation, not on technical detection

---

## 📊 Transparency Report

### What Data is Collected

**By this application**: 
- ❌ None. No telemetry, no analytics, no network calls.

**Configuration file** (`autofire.json`):
- Stores your preferences locally
- Not transmitted anywhere
- Plain JSON format (human-readable)

### Network Activity

This application makes **zero network connections**:
- No "phone home" behavior
- No update checks
- No usage statistics
- No crash reports

Verify with:
```cmd
netstat -ano | findstr "python.exe"
```
(Should show nothing related to this app)

---

## 🔐 Code Audit

### Security Checklist

- [x] No obfuscated code
- [x] All source code available
- [x] No binary dependencies (except Python stdlib + keyboard)
- [x] No network calls
- [x] No privilege escalation attempts
- [x] No file system access (except config.json)
- [x] No registry modifications
- [x] No process enumeration (except window listing)
- [x] No memory manipulation
- [x] Comprehensive test suite

### Third-Party Dependencies

```
keyboard==0.13.5
└─ Uses: Windows hooks for key detection
└─ Risk: Low (popular, open-source library)
└─ GitHub: https://github.com/boppreh/keyboard
```

All other dependencies are Python standard library (no risk).

---

## 📞 Responsible Disclosure

If you discover a security issue:

1. **Do NOT** open a public issue
2. Email: [create a security contact in your repo]
3. Include:
   - Description of the issue
   - Steps to reproduce
   - Impact assessment
   - Suggested fix (if any)

---

## 📝 Changelog of Security Updates

### v2.0 (2025-10-06)
- ✅ Removed AutoHotkey dependency (external process risk)
- ✅ Direct PostMessage implementation (more transparent)
- ✅ Added comprehensive test suite
- ✅ Enhanced documentation of security model

### v1.0 (Initial)
- Used AutoHotkey for input simulation
- Basic security model

---

## 🏛️ Legal Compliance

### GDPR Compliance
- ✅ No personal data collected
- ✅ No data processing
- ✅ No data storage (except local config)

### Accessibility Standards
- ✅ Designed for legitimate accessibility use cases
- ✅ Compatible with assistive technologies
- ✅ Follows Windows accessibility guidelines

### Software Standards
- ✅ Uses only documented Windows APIs
- ✅ No reverse engineering of games
- ✅ No circumvention of copy protection
- ✅ No violation of DMCA

---

## 🎓 Educational Purpose

This tool is also an educational resource demonstrating:
- Proper Windows API usage
- Thread-safe GUI programming
- Safe input automation techniques
- Responsible software design

Feel free to study the code to learn about:
- `ctypes` for Windows API access
- Tkinter GUI development
- Background thread management
- Configuration management
- Pytest testing strategies

---

## ⚖️ Disclaimer

This tool is provided for legitimate purposes only. Users are responsible for:
- Compliance with applicable laws
- Adherence to game Terms of Service
- Respectful use in online communities

**The authors do not endorse:**
- Cheating in competitive games
- Violating game ToS
- Creating unfair advantages
- Disrupting online communities

**Use at your own risk. The authors are not liable for:**
- Game bans or suspensions
- ToS violations
- Any consequences of use

---

*Last Updated: October 6, 2025*
