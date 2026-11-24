# Momodora II v041 简体中文补丁

当前独立发布 **v0.1.0 测试版 one-click 安装器**，不与其他 Momodora 项目混用。

## 下载与使用

- Release ZIP：`Momodora2ZH_OneClick_v0.1.0_win64.zip`
- 单文件安装器：`Momodora2ZH_Setup.exe`（Windows 10/11 x64，无需安装 Python 或联网）
- SHA-256：`edd307e638d00a5873b4b9309b3485e0d8d120ba75f51690e32351576fe1a5d0`
- 发布 ZIP SHA-256：`5734778e5160fe598aa6a4bd5fc634d3cc13d8588457f7ee0eb55bdc85c0c5bb`
- [安装说明](Momo2_041_Chinese_Patch/一键安装说明.md)
- [文本补丁说明](Momo2_041_Chinese_Patch/README.txt)

下载并解压 one-click ZIP，双击 `Momodora2ZH_Setup.exe`，选择含原版 `momodora2.exe` 的游戏目录，点击“一键安装汉化”。成功后安装器不自动启动游戏；请在游戏目录手动运行 `momodora2_zh.exe`。GUI 也提供“检查原版”“卸载补丁”和“打开游戏目录”功能。

本工具只支持原版 Momodora II v041 `momodora2.exe`，SHA-256 为：

```text
a836f7b90daefe5f603663cdf65ddd10dda8a4eddf086d8c71e02fe71e563af3
```

安装器只新增汉化 EXE、中文图集、布局数据和安装回执；不覆盖原版游戏文件或存档。未知同名目标文件会导致安装中止。卸载时也会拒绝删除校验不匹配的文件。安装器无数字签名，SmartScreen 可能提示未知发布者，请从本仓库 Releases 下载并核对哈希。

## 项目范围

包含 v041 补丁源码、翻译表及其素材。**不包含原版游戏 EXE、原版图片或完整游戏**。本补丁只面向 Momodora II v041。

## 测试状态

构建/回包及目标哈希检查通过；真实 GUI 已在临时游戏克隆中点击“一键安装汉化”，验证成功弹窗、汉化 EXE 和全部图集哈希，并确认原版 EXE、原始资源、存档映射未更改。另有 42 项隔离文件安全测试通过。目标环境 PATH 中无 Python 或 Git，安装器仍完成全部流程。GUI 测试不启动游戏本体。之前单独用源码在隔离克隆验证过启动场景、存档菜单、暂停、操作说明页及游戏初始场景。

**尚未**完成完整流程、全部剧情对白、所有首领/结局、多分辨率和存档读写回归，故此为测试版。

## 源码构建

64 位 Windows 上使用 Python 3.12.6、PyInstaller 6.22.3 和 zlib 1.3.1：

```powershell
cd Momo2_041_Chinese_Patch
.\build_launcher.ps1
```

安装器内含 CPython/Tcl/Tk 运行时；第三方运行时许可在 EXE 内的“运行时许可”页和随 ZIP 的 `Licenses/` 目录中。
