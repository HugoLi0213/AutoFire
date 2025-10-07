# AutoFire v2.1.0 Release Notes

**Release Date:** October 7, 2025

## 🎨 Major UI Improvements

### Clearer, More Intuitive Labels
We've completely revamped the UI labels to replace technical jargon with plain, user-friendly language:

- **"Press This Key ▼"** (was "Trigger key") - More action-oriented
- **"To Fire This Key ▶"** (was "Output key") - Shows the flow clearly
- **"🔓 Allow Original Key (Mix Mode)"** (was "Pass-through trigger key") - Explains what it does
- **"⚡ Hardware Mode (Best for Games)"** (was "Use SendInput") - Shows the benefit
- **"Speed (ms) - Lower = Faster"** (was "Interval (ms)") - Clarifies the relationship

### Visual Enhancements
- 💡 **Guide text at top** - Helpful instructions right where you need them
- **Emoji icons throughout** - ▶, ⏹, ➕, ➖, ✓, ⚡, 🔓 for better visual clarity
- **Simplified button labels** - "Add New", "Delete" instead of verbose text
- **Better organized layout** - Clearer visual hierarchy

### Language Support
- Full support for **English** and **繁體中文 (Traditional Chinese)**
- All improved labels translated in both languages
- One-click language switching maintained

## ⚡ Multi-Slot Features (from v2.0.0)

- Configure multiple trigger→output key pairs simultaneously
- Each slot runs independently with its own thread
- Individual enable/disable per slot
- Per-slot settings (interval, window, mode)
- Real-time status showing active slots

## 🧪 Testing & Quality

- ✅ **21/23 tests passing** (1 skipped, 1 environment issue)
- Comprehensive test coverage for multi-slot functionality
- Tests updated to match new UI labels and status format

## 🔧 Technical Details

- **Architecture:** Per-slot threading for true simultaneous execution
- **Backward Compatibility:** Config files from v1.x automatically upgraded
- **Status Display:** Clear "Active: Q, E" format showing which slots are running
- **Thread Safety:** Proper locking and state management

## 📝 What Changed

### UI Translation Updates
- Simplified Chinese removed (keeping English + Traditional Chinese only)
- All labels now use clear, descriptive text with visual indicators
- Guide text added to help users understand the tool

### Code Quality
- Refactored AutoFireEngine for multi-slot simultaneous operation
- Improved status callback mechanism
- Better error handling and logging

## 🚀 Upgrade Notes

- Config files from v2.0.0 are fully compatible
- No breaking changes to existing functionality
- UI improvements are purely cosmetic - all features work the same

## 📦 Download

Get the latest release from: [GitHub Releases](https://github.com/HugoLi0213/AutoFire/releases/latest)

---

**Author:** Hugo  
**Last Updated:** October 7, 2025
