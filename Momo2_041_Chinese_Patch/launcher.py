"""Self-contained graphical one-click installer for Momodora II v041 ZH patch."""
from __future__ import annotations
import json
import os
import queue
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from oneclick_core import install, remove, check, engine

APP_NAME = "Momodora 2 简体中文汉化补丁"
APP_VERSION = "0.1.0"
PATCH_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
QUEUE: queue.Queue = queue.Queue()


def _resource(name: str) -> Path:
    return PATCH_DIR / name


def _worker(action: str, game_dir: str) -> None:
    try:
        if action == "install":
            result = install(game_dir, PATCH_DIR)
        elif action == "remove":
            result = remove(game_dir, PATCH_DIR)
        elif action == "check":
            result = check(game_dir, PATCH_DIR)
        else:
            raise ValueError("未知操作")
        QUEUE.put(("success", action, result))
    except Exception as exc:
        QUEUE.put(("error", action, str(exc), traceback.format_exc()))


def _emit_result(result: dict) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if sys.stdout is not None:
        print(text)


def _report_cli_error(text: str) -> None:
    if sys.stderr is not None:
        print("ERROR:", text, file=sys.stderr)
    # Windowed CLI invocations are for automation; report by exit code, never block on a dialog.


def _cli(args: list[str]) -> int:
    if len(args) != 2 or args[0] not in ("--cli-install", "--cli-remove", "--cli-check"):
        _report_cli_error("用法：Momodora2ZH_Setup.exe --cli-install|--cli-remove|--cli-check 游戏目录")
        return 2
    action = {"--cli-install": "install", "--cli-remove": "remove", "--cli-check": "check"}[args[0]]
    game_dir = str(Path(args[1]).expanduser().resolve())
    if action == "install":
        result = install(game_dir, PATCH_DIR)
    elif action == "remove":
        result = remove(game_dir, PATCH_DIR)
    else:
        result = check(game_dir, PATCH_DIR)
    _emit_result(result)
    return 0


class Patcher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} - v{APP_VERSION}")
        self.root.geometry("720x480")
        self.root.minsize(640, 440)
        self.root.configure(bg="#171923")
        self.messages: queue.Queue = QUEUE
        self.worker_thread: threading.Thread | None = None
        self.busy = False
        self.root.protocol("WM_DELETE_WINDOW", self._request_close)
        self.directory = tk.StringVar(value=self._default_game_dir())
        self.status = tk.StringVar(value="请选择 Momodora II v041 游戏文件夹。")
        self._style()
        self._build()
        self.root.after(100, self._poll)

    @staticmethod
    def _default_game_dir() -> str:
        # In one-file builds __file__ lives in PyInstaller's temporary _MEI folder.
        # Prefer the installer EXE's directory only when it is itself the game root.
        candidates = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent)
        candidates.append(Path.cwd())
        for candidate in candidates:
            if (candidate / "momodora2.exe").is_file():
                return str(candidate)
        return ""

    def _style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#171923")
        style.configure("TLabel", background="#171923", foreground="#e6e8f0", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"), foreground="#f7dba7")
        style.configure("Sub.TLabel", foreground="#abb2c4", font=("Microsoft YaHei UI", 9))
        style.configure("TEntry", fieldbackground="#242838", foreground="#f2f2f6", insertcolor="#ffffff")
        style.configure("TButton", padding=(14, 9), font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Accent.TButton", background="#e2a862", foreground="#181818")
        style.map("Accent.TButton", background=[("disabled", "#625344"), ("active", "#f0bd7a")])
        style.configure("Secondary.TButton", background="#30364a", foreground="#e8ebf5")
        style.configure("TSeparator", background="#3a4154")

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=(28, 22, 28, 18))
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Momodora 2", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="简体中文汉化补丁 · v0.1 测试版", style="Sub.TLabel").pack(anchor="w", pady=(2, 15))
        ttk.Separator(outer).pack(fill="x", pady=(0, 17))

        ttk.Label(outer, text="第一步 · 选择游戏根目录").pack(anchor="w", pady=(0, 7))
        path_row = ttk.Frame(outer)
        path_row.pack(fill="x")
        self.path_entry = ttk.Entry(path_row, textvariable=self.directory)
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(path_row, text="浏览…", command=self._browse, style="Secondary.TButton").pack(side="left", padx=(9, 0))

        ttk.Label(outer, text="目录里必须有 momodora2.exe 和 data\\graphics\\misc 文件夹。只支持经校验的 Momodora II v041 原版。", style="Sub.TLabel").pack(anchor="w", pady=(7, 18))
        button_row = ttk.Frame(outer)
        button_row.pack(fill="x")
        self.install_button = ttk.Button(button_row, text="一键安装汉化", command=lambda: self._start("install"), style="Accent.TButton")
        self.install_button.pack(side="left")
        self.check_button = ttk.Button(button_row, text="检查原版", command=lambda: self._start("check"), style="Secondary.TButton")
        self.check_button.pack(side="left", padx=9)
        self.remove_button = ttk.Button(button_row, text="卸载补丁", command=self._confirm_remove, style="Secondary.TButton")
        self.remove_button.pack(side="left")
        self.folder_button = ttk.Button(button_row, text="打开游戏目录", command=self._open_folder, style="Secondary.TButton")
        self.folder_button.pack(side="right")

        ttk.Separator(outer).pack(fill="x", pady=(19, 13))
        ttk.Label(outer, textvariable=self.status, wraplength=640).pack(anchor="w", pady=(0, 7))
        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 13))

        note = (
            "安全说明\n"
            "• 原版文件不会被覆盖；汉化版另存为 momodora2_zh.exe。\n"
            "• 仅生成中文图集和汉化副本；不会改动存档、系统区域、字体或打印机。\n"
            "• 不含游戏本体。请保留原版游戏完整文件，并自行备份存档。\n"
            "• 游戏及原素材权利归原作者；本工具不是官方发布。"
        )
        ttk.Label(outer, text=note, style="Sub.TLabel", justify="left", wraplength=640).pack(anchor="w", pady=(4, 7))
        ttk.Label(outer, text="检查通过后点“一键安装汉化”；完成后从游戏目录启动 momodora2_zh.exe。", style="Sub.TLabel").pack(anchor="w", side="bottom")
        links = ttk.Frame(outer)
        links.pack(fill="x", pady=(5, 0))
        licenses = ttk.Label(links, text="第三方运行时许可", style="Sub.TLabel", cursor="hand2")
        licenses.pack(side="left")
        licenses.bind("<Button-1>", lambda _event: self._show_licenses())
        issue = ttk.Label(links, text="授权 / 反馈问题", style="Sub.TLabel", cursor="hand2")
        issue.pack(side="right")
        issue.bind("<Button-1>", lambda _event: webbrowser.open("https://github.com/hhnhhw/momodora2-v041-zh-patch/issues"))

    def _show_licenses(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("第三方运行时许可")
        window.geometry("800x560")
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", font=("Consolas", 10))
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        names = ("python-LICENSE.txt", "pyinstaller-COPYING.txt", "pyinstaller-hooks-LICENSE.txt", "tcl-tk-license.terms")
        for name in names:
            path = _resource("Licenses") / name
            text.insert("end", "\n" + "=" * 72 + "\n" + name + "\n" + "=" * 72 + "\n")
            if path.is_file():
                text.insert("end", path.read_text(encoding="utf-8", errors="replace"))
            else:
                text.insert("end", "许可文件缺失，请从项目仓库获取完整分发包。\n")
        text.configure(state="disabled")

    def _browse(self) -> None:
        picked = filedialog.askdirectory(title="选择包含 momodora2.exe 的游戏根目录", mustexist=True)
        if picked:
            self.directory.set(picked)
            self.status.set("已选择文件夹；安装前仍会验证 EXE 版本与 SHA-256。")

    def _current_dir(self) -> str | None:
        value = self.directory.get().strip().strip('"')
        if not value:
            messagebox.showwarning("尚未选择目录", "请先选择 Momodora II v041 游戏根目录。", parent=self.root)
            return None
        path = Path(value).expanduser()
        if not path.is_dir():
            messagebox.showerror("目录不存在", "该游戏目录不存在，请重新选择。", parent=self.root)
            return None
        return str(path.resolve())

    def _set_busy(self, value: bool) -> None:
        self.busy = value
        state = "disabled" if value else "normal"
        for button in (self.install_button, self.check_button, self.remove_button, self.folder_button):
            button.configure(state=state)
        if value:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _start(self, action: str) -> None:
        if self.busy:
            return
        game_dir = self._current_dir()
        if not game_dir:
            return
        self._set_busy(True)
        self.status.set({"install": "正在校验原版并制作汉化副本，请稍候…", "check": "正在校验游戏版本…", "remove": "正在检查汉化文件并卸载…"}[action])
        self.worker_thread = threading.Thread(target=_worker, args=(action, game_dir), daemon=False)
        self.worker_thread.start()

    def _request_close(self) -> None:
        if self.busy:
            messagebox.showinfo("请等待操作完成", "正在写入或校验文件，请等待本次操作结束后再关闭安装器。", parent=self.root)
            return
        self.root.destroy()

    def _confirm_remove(self) -> None:
        if messagebox.askyesno("卸载汉化", "只删除校验匹配的汉化 EXE 和中文图集，不删除原版或存档。继续吗？", parent=self.root):
            self._start("remove")

    def _open_folder(self) -> None:
        path = self._current_dir()
        if path:
            try:
                os.startfile(path)
            except OSError as exc:
                messagebox.showerror("无法打开目录", str(exc), parent=self.root)

    def _poll(self) -> None:
        try:
            while True:
                item = self.messages.get_nowait()
                self._set_busy(False)
                if item[0] == "error":
                    action, error = item[1], item[2]
                    self.status.set("操作未完成；原版游戏与存档保持不变。")
                    messagebox.showerror("汉化未完成", error, parent=self.root)
                else:
                    action, result = item[1], item[2]
                    if action == "install":
                        if result["result"] == "already-installed":
                            self.status.set("已安装：" + result["exe"])
                            messagebox.showinfo("汉化已安装", "检测到完整的相同版本汉化，无需重复写入。", parent=self.root)
                        else:
                            self.status.set("安装成功：" + result["exe"])
                            messagebox.showinfo("汉化完成", "一键汉化成功！\n\n请在游戏目录启动 momodora2_zh.exe。\n原版 momodora2.exe 和存档未改动。", parent=self.root)
                    elif action == "remove":
                        self.status.set("卸载完成；原版与存档保留。")
                        messagebox.showinfo("卸载完成", "汉化副本和图集已安全移除。运行原版 EXE 即可。", parent=self.root)
                    else:
                        self.status.set("原版与图集校验通过；可安全安装。")
                        messagebox.showinfo("版本检查通过", "这是支持的原版 Momodora II v041，补丁图集也通过校验。", parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1].startswith("--cli-"):
        try:
            return _cli(sys.argv[1:])
        except Exception as exc:
            _report_cli_error(str(exc))
            return 1
    if sys.platform != "win32":
        print("This GUI installer supports Windows only.", file=sys.stderr)
        return 1
    root = tk.Tk()
    Patcher(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
