# 运行时许可证 / Runtime Licenses

`Momodora2ZH_Setup.exe` 是面向 Windows x64 的单文件安装器，随 `Momodora2ZH_OneClick_v0.1.0_win64.zip` 发布，使用以下运行时组件构建：64-bit CPython 3.12.6、PyInstaller 6.22.3、PyInstaller Community Hooks（pyinstaller-hooks-contrib）2026.10，以及 Tcl/Tk 8.6。安装器为 GUI 程序，提供“第三方运行时许可”查看入口；单文件安装器与发布包均应包含这些许可证文本。

- [CPython 3.12 PSF License 及随 Windows 运行时发布的第三方许可](python-LICENSE.txt)
- [PyInstaller 6.22.3 许可、Bootloader Exception 和运行时组件许可信息](pyinstaller-COPYING.txt)
- [PyInstaller Community Hooks 许可声明](pyinstaller-hooks-LICENSE.txt)
- [Tcl/Tk 8.6 许可条款](tcl-tk-license.terms)

PyInstaller 6.22.3 的[许可说明](https://pyinstaller.org/en/v6.22.3/license.html)说明，在遵守所含组件各自适用许可证的前提下，可以分发由 PyInstaller 生成的可执行文件。Bootloader Exception、PyInstaller 运行时钩子及 Community Hooks 的具体许可范围，以随附原文为准。本项目未修改这些工具链组件的源码。

以上许可仅适用于相应运行时组件，不授予 Momodora 游戏、游戏程序与素材、汉化文本或图集中字体字形的权利；其权利仍归各自权利人所有，并受各自适用条款约束。

构建记录显示正式安装器为 64 位单文件程序，构建环境为 CPython 3.12.6 和 PyInstaller 6.22.3。
