# Momodora II v041 简体中文补丁

本仓库只发布 **Momodora II v041** 简体中文补丁，不包含原版游戏程序或原始游戏图片。

## 一键下载安装包

- [下载 Windows x64 one-click 完整包（约 11 MB）](https://github.com/hhnhhw/momodora2-v041-zh-patch/releases/latest/download/Momodora2ZH_OneClick_v0.1.0_win64.zip)
- 安装器：`Momodora2ZH_Setup.exe`
- 版本：v0.1.0 测试版
- Windows 10/11 x64；目标电脑无需安装 Python、无需联网。
- SHA-256: `edd307e638d00a5873b4b9309b3485e0d8d120ba75f51690e32351576fe1a5d0`
- ZIP SHA-256: `24c6b2981c9c124692b795623e8001fc1a8cca93ed7a07f6e2233b5f4dfb06a7`
- [一键安装说明](Momo2_041_Chinese_Patch/一键安装说明.md) · [补丁及测试说明](Momo2_041_Chinese_Patch/README.txt)

解压下载包后双击 `Momodora2ZH_Setup.exe`，选择含原版 `momodora2.exe` 的游戏目录，按“一键安装汉化”。成功后安装器**不会自动启动游戏**，请手动启动游戏目录中的 `momodora2_zh.exe`。GUI 同时提供原版检查、卸载和打开游戏目录功能。安装不会覆盖原版 EXE、游戏原始资源或存档；遇到不匹配的同名目标文件会停止。安装器未做代码签名，SmartScreen 可能显示未知发布者警告。

仅支持未经修改的 Momodora II v041 原版，EXE SHA-256：

```text
a836f7b90daefe5f603663cdf65ddd10dda8a4eddf086d8c71e02fe71e563af3
```

## 补丁范围及状态

翻译菜单、序章、剧情对白、道具提示、片尾、操作说明，以及动态地图加载文字。**测试版，尚未完整回归全部流程、所有对白、首领/结局、多分辨率和存档读写。**

已通过一键 GUI 的真实按钮隔离测试（12项检查）和冻结 EXE 安全测试（42项检查）。目标环境 PATH 中不包含 Python 或 Git；测试均使用临时副本，不启动游戏本体、不修改用户存档。原版 EXE 哈希在测试前后保持一致。

## 源码构建

在 64-bit Windows、Python 3.12.6、PyInstaller 6.22.3、zlib 1.3.1 环境中：

```powershell
cd Momo2_041_Chinese_Patch
.\build_launcher.ps1
```

安装器中包含 Python/Tcl/Tk 运行时；第三方许可随安装器和 ZIP 提供。详细见 `Momo2_041_Chinese_Patch/Licenses/`。
