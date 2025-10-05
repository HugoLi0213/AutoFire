# AutoFire - AutoHotkey Version

This folder now includes `autofire.ahk`, an AutoHotkey v2 script that replicates the Python AutoFire behavior with better in-game compatibility.

## Why AutoHotkey?

AutoHotkey's `Send` command uses a different input method that works in many games where Python's keyboard injection is blocked. It's widely used by gamers and generally has better compatibility with DirectInput and Raw Input games.

## Setup

1. **Download and install AutoHotkey v2**
   - Visit: https://www.autohotkey.com/
   - Download the v2.0 installer (not v1.1)
   - Run the installer (default settings are fine)

2. **Run the script**
   - Double-click `autofire.ahk`
   - You'll see a green "H" icon in your system tray
   - A tooltip will show "AutoFire AHK loaded"

3. **Test it**
   - Open Notepad or any text field
   - Hold the `` ` `` (backtick) key
   - You should see `e` repeating every 100ms
   - Release the backtick to stop

4. **Use in game**
   - Launch your game
   - The script runs in the background
   - Hold your trigger key when needed
   - Press `Ctrl+Alt+Esc` for emergency stop

## Configuration

Open `autofire.ahk` in any text editor and modify these lines:

```ahk
TriggerKey := "``"          ; The key you hold (`` = backtick)
OutputKey := "e"            ; The key that gets spammed
IntervalMs := 100           ; Time between each press (milliseconds)
PassThrough := false        ; true = trigger also reaches game
```

**Common key names:**
- Letters: `"a"`, `"b"`, `"c"`, etc.
- Numbers: `"1"`, `"2"`, `"3"`, etc.
- Function keys: `"F1"`, `"F2"`, etc.
- Special: `"Space"`, `"Enter"`, `"Tab"`
- Mouse: `"LButton"`, `"RButton"`, `"MButton"`

Save the file and double-click it again to reload with new settings.

## Advantages over Python version

✅ Works in more games (different input method)  
✅ Lower CPU usage  
✅ No Python installation required  
✅ Industry-standard tool (less likely to be flagged)  
✅ Very small memory footprint  
✅ Can bind to mouse buttons easily  

## Important Notes

⚠️ **Use responsibly**
- Many online/competitive games prohibit automation
- Even if it works technically, it may violate Terms of Service
- Use only where permitted (offline, single-player, or with explicit allowance)

⚠️ **Anti-cheat detection**
- AutoHotkey is detectable by some anti-cheat systems
- Some games may kick you if AHK is running
- Always check the game's policy before using

## Troubleshooting

**Script won't start:**
- Make sure you installed AutoHotkey v2 (not v1.1)
- Right-click the .ahk file → Properties → Unblock (if button exists)

**Doesn't work in game:**
- Try running the script as Administrator
- Try running the game in windowed/borderless mode
- Some games actively block all automation (no workaround)

**Want to stop the script:**
- Right-click the green "H" icon in system tray → Exit
- Or press Ctrl+Alt+Esc for emergency stop + exit

## Going back to Python

The Python version is still here and fully functional. Use `python app.py` if you prefer the Tk GUI or need the advanced features. The AHK script is just an alternative with better game compatibility.
