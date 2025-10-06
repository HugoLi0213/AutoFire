# AutoFire - 自动连发工具

**作者:** Hugo  
**最后更新:** 2025-10-06

## 📋 简介

AutoFire 是一个 Windows 自动按键工具，可以在您按住触发键时自动重复发送指定的按键到目标窗口。

### ✨ 主要特性

- 🎮 **两种输出模式:**
  - **SendInput (推荐):** 硬件级模拟，兼容 DirectInput 游戏（类似 AutoHotkey）
  - **PostMessage:** 窗口消息队列模拟，更安全但兼容性较低
- 🪟 **窗口自动检测:** 自动列出所有可见窗口供选择
- ⌨️ **自定义按键:** 可自由设置触发键和输出键
- ⏱️ **可调间隔:** 1-1000 毫秒的重复间隔
- 🔄 **穿透模式:** 可选是否将触发键传递到目标窗口
- 💾 **配置保存:** 自动保存和加载配置

## 🚀 快速开始

### 1️⃣ 安装依赖

```cmd
pip install keyboard
```

### 2️⃣ 运行程序

**以管理员身份运行**（键盘钩子需要管理员权限）:

```cmd
python autofire_ui.py
```

### 3️⃣ 配置设置

1. **触发键 (Trigger key):** 输入您想用来激活自动连发的按键（例如：`e`）
2. **输出键 (Output key):** 输入要自动重复发送的按键（例如：`r`）
3. **目标窗口 (Target Window Title):** 
   - 点击 🔄 按钮刷新窗口列表
   - 从下拉菜单选择目标窗口
4. **间隔 (Interval):** 设置按键重复间隔（毫秒）
5. **穿透模式 (Pass-through):** 勾选则触发键也会发送到窗口，不勾选则只触发连发
6. **使用 SendInput (Use SendInput):** 
   - ✅ **勾选 (推荐):** 使用硬件级模拟，兼容 DirectInput 游戏
   - ⬜ **不勾选:** 使用消息队列模拟，更安全但可能不兼容某些游戏

### 4️⃣ 开始使用

1. 点击 **Start** 按钮
2. 切换到目标窗口
3. 按住触发键，程序将自动重复发送输出键
4. 松开触发键停止连发
5. 点击 **Stop** 按钮停止监听

## 🎮 输出模式说明

### SendInput 模式（默认，推荐）

**优点:**
- ✅ 兼容 DirectInput 游戏（直接从键盘驱动读取输入的游戏）
- ✅ 硬件级模拟，使用扫描码 (Scan Codes)
- ✅ 与 AutoHotkey 相同的工作原理
- ✅ 适用于大多数游戏

**工作原理:**
```
SendInput → 键盘驱动层 → DirectInput/游戏
```

**何时使用:** 当游戏忽略 PostMessage 时（大多数现代游戏）

### PostMessage 模式（可选）

**优点:**
- ✅ 更安全，检测风险更低
- ✅ 窗口特定目标（不会影响其他窗口）
- ✅ 常用于合法软件（远程桌面、辅助工具等）

**缺点:**
- ❌ 不兼容 DirectInput 游戏
- ❌ 某些游戏会忽略消息队列输入

**工作原理:**
```
PostMessage → 窗口消息队列 → 游戏（如果游戏读取消息队列）
```

**何时使用:** 当您需要更安全的方案或目标是读取消息队列的应用程序

## 🔧 支持的按键

常用按键包括:
- 字母键: `a`-`z`
- 数字键: `0`-`9`
- 功能键: `f1`-`f12`
- 特殊键: `space`, `enter`, `shift`, `ctrl`, `alt`, `tab`, `esc`
- 鼠标: `left`, `right`, `middle` (鼠标按钮)

**注意:** 按键名称不区分大小写

## ⚙️ 配置文件

配置自动保存到 `autofire.json`，格式如下:

```json
{
  "interval_ms": 50,
  "output_key": "r",
  "pass_through": false,
  "trigger_key": "e",
  "use_sendinput": true,
  "window_title": "Untitled - Notepad"
}
```

## 🛡️ 安全性说明

本应用使用 **合法的 Windows API 调用** 进行输入模拟:

### ✅ 标准输入模拟
- 使用 `SendInput()` 或 `PostMessageW()` API
- 与以下软件使用相同的机制:
  - 远程桌面软件 (TeamViewer, RDP)
  - 辅助功能工具 (屏幕阅读器、语音控制)
  - 宏工具和自动化软件

### ✅ 无内存干预
- **不** 读取或写入游戏内存
- **不** 钩取游戏内部函数或注入代码 (DLL)
- 完全在游戏进程外运行

### ✅ 降低检测风险
- 从操作系统角度看，这些 API 输入与合法软件生成的输入无法区分
- 反作弊系统不太可能封禁这些 API，因为这样会导致许多正常应用程序出现误报

### ✅ 非侵入性
- 仅发送键盘事件，不修改任何游戏文件或进程

**重要提示:** 虽然本工具使用合法 API，但某些游戏的服务条款可能禁止使用任何自动化工具。请自行承担使用风险并遵守游戏规则。

## 📝 使用示例

### 示例 1: 游戏自动连发攻击键
```
触发键: e
输出键: r
间隔: 50ms
目标窗口: MyGame.exe
穿透模式: ✅ 勾选
使用 SendInput: ✅ 勾选 (兼容 DirectInput 游戏)
```

**效果:** 按住 `E` 键时，每 50ms 自动发送 `R` 键到游戏窗口，同时 `E` 键也会被游戏接收

### 示例 2: 文本编辑器重复输入
```
触发键: f1
输出键: space
间隔: 100ms
目标窗口: Notepad
穿透模式: ⬜ 不勾选
使用 SendInput: ⬜ 不勾选 (PostMessage 足够)
```

**效果:** 按住 `F1` 时，每 100ms 自动在记事本中输入空格，`F1` 不会传递到记事本

## ❓ 常见问题

### Q: 为什么需要管理员权限？
A: Windows 的全局键盘钩子 (keyboard hook) 需要管理员权限才能监听按键事件。

### Q: 某些游戏不工作怎么办？
A: 确保勾选 "Use SendInput (AHK-like, better game compatibility)" 复选框。SendInput 兼容 DirectInput 游戏，而 PostMessage 不兼容。

### Q: SendInput 和 PostMessage 有什么区别？
A:
- **SendInput:** 硬件级模拟，兼容 DirectInput 游戏，与 AutoHotkey 相同
- **PostMessage:** 消息队列模拟，更安全但某些游戏会忽略

### Q: 会被反作弊系统检测吗？
A: 本工具使用合法的 Windows API（SendInput/PostMessage），与远程桌面、AutoHotkey 等软件相同。但某些游戏可能仍会检测到自动化行为。请自行评估风险。

### Q: 配置保存在哪里？
A: 配置自动保存在与程序相同目录的 `autofire.json` 文件中。

### Q: 支持哪些按键？
A: 支持大多数常用按键。请参阅上方的"支持的按键"部分。键名来自 Python `keyboard` 库。

## 🔍 故障排除

### 程序无法启动
- 确保以管理员身份运行
- 检查是否安装了 `keyboard` 库: `pip install keyboard`

### 按键没有响应
- 确认目标窗口标题正确（点击 🔄 刷新窗口列表）
- 检查触发键和输出键是否正确
- 尝试切换 SendInput/PostMessage 模式

### 游戏忽略输入
- ✅ 勾选 "Use SendInput" 复选框
- 确保游戏窗口在前台且有焦点
- 某些游戏可能有输入保护，无法绕过

## 📄 许可证

本项目为教育和个人使用目的。请遵守您所使用的游戏或应用程序的服务条款。

## 👤 作者

**Hugo**  
项目仓库: [github.com/HugoLi0213/Marcoapp](https://github.com/HugoLi0213/Marcoapp)

---

**最后更新:** 2025年10月6日
