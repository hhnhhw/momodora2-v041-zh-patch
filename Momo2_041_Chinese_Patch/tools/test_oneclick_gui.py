"""Drive the packaged Momodora 2 ttk GUI with a real Windows mouse click.

Run explicitly after packaging on an unlocked interactive Windows desktop::

    python tools/test_oneclick_gui.py --source-exe <original-momodora2.exe>

The installer starts without CLI arguments, with cwd set to an isolated clone
under PATCH.parent, so clicking Install also tests automatic game-dir discovery.
Only Install and the success dialog's OK are clicked; the game is never started.
This script uses only Python's standard library, not pywinauto or local Tk hooks.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

PATCH = Path(__file__).resolve().parents[1]
EXE = PATCH / "Momodora2ZH_Setup.exe"
REPORT = PATCH / "oneclick_gui_test_report.json"
GRAPHICS = Path("data/graphics/misc")
RECEIPT = GRAPHICS / "momo2_zh_install.json"
GAME = "momodora2.exe"
OUTPUT = "momodora2_zh.exe"
ASSETS = {"momo2_zh_text.png", "momo2_zh_ctrl.png", "atlas_layout.json"}
WM_CLOSE = 0x0010
u = k = CB = None


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clean_env():
    env = os.environ.copy()
    windows = Path(env.get("SystemRoot", r"C:\Windows"))
    env["PATH"] = os.pathsep.join((str(windows / "System32"), str(windows)))
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX"):
        env.pop(name, None)
    return env


class PROCESS(c.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("pid", w.DWORD),
                ("heap", c.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
                ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD),
                ("name", w.WCHAR * 260)]


def init_win32():
    global u, k, CB
    need(sys.platform == "win32", "Real GUI mouse tests require interactive Windows")
    u = c.WinDLL("user32", use_last_error=True)
    k = c.WinDLL("kernel32", use_last_error=True)
    CB = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    signatures = {
        "EnumWindows": ([CB, w.LPARAM], w.BOOL),
        "EnumChildWindows": ([w.HWND, CB, w.LPARAM], w.BOOL),
        "GetWindowThreadProcessId": ([w.HWND, c.POINTER(w.DWORD)], w.DWORD),
        "IsWindowVisible": ([w.HWND], w.BOOL),
        "IsWindowEnabled": ([w.HWND], w.BOOL),
        "IsWindow": ([w.HWND], w.BOOL),
        "IsChild": ([w.HWND, w.HWND], w.BOOL),
        "GetWindowTextW": ([w.HWND, w.LPWSTR, c.c_int], c.c_int),
        "GetClassNameW": ([w.HWND, w.LPWSTR, c.c_int], c.c_int),
        "GetWindowRect": ([w.HWND, c.POINTER(w.RECT)], w.BOOL),
        "PostMessageW": ([w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
        "GetCursorPos": ([c.POINTER(w.POINT)], w.BOOL),
        "SetCursorPos": ([c.c_int, c.c_int], w.BOOL),
        "GetAncestor": ([w.HWND, w.UINT], w.HWND),
        "SetForegroundWindow": ([w.HWND], w.BOOL),
        "GetForegroundWindow": ([], w.HWND),
        "WindowFromPoint": ([w.POINT], w.HWND),
        "ShowWindow": ([w.HWND, c.c_int], w.BOOL),
        "mouse_event": ([w.DWORD, w.DWORD, w.DWORD, w.DWORD, c.c_size_t], None),
        "SetProcessDPIAware": ([], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(u, name)
        function.argtypes = args
        function.restype = result
    k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    k.CreateToolhelp32Snapshot.restype = w.HANDLE
    k.Process32FirstW.argtypes = [w.HANDLE, c.POINTER(PROCESS)]
    k.Process32FirstW.restype = w.BOOL
    k.Process32NextW.argtypes = [w.HANDLE, c.POINTER(PROCESS)]
    k.Process32NextW.restype = w.BOOL
    k.CloseHandle.argtypes = [w.HANDLE]
    k.CloseHandle.restype = w.BOOL
    # Keep physical cursor, window rectangle and hit-test coordinates consistent.
    u.SetProcessDPIAware()


def processes():
    handle = k.CreateToolhelp32Snapshot(2, 0)
    need(handle not in (None, c.c_void_p(-1).value), "Cannot enumerate GUI process tree")
    row = PROCESS()
    row.dwSize = c.sizeof(row)
    result = []
    try:
        more = k.Process32FirstW(handle, c.byref(row))
        while more:
            result.append({"pid": int(row.pid), "parent": int(row.parent), "name": row.name})
            more = k.Process32NextW(handle, c.byref(row))
    finally:
        k.CloseHandle(handle)
    return result


def descendants(pid, rows):
    found = {pid}
    while True:
        expanded = found | {row["pid"] for row in rows if row["parent"] in found}
        if expanded == found:
            return found
        found = expanded


def window(hwnd):
    pid = w.DWORD()
    u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    text = c.create_unicode_buffer(2048)
    cls = c.create_unicode_buffer(128)
    rect = w.RECT()
    u.GetWindowTextW(hwnd, text, len(text))
    u.GetClassNameW(hwnd, cls, len(cls))
    need(u.GetWindowRect(hwnd, c.byref(rect)), "Cannot read GUI window rectangle")
    return {"hwnd": int(hwnd), "pid": pid.value, "title": text.value,
            "cls": cls.value, "x": rect.left, "y": rect.top,
            "w": rect.right - rect.left, "h": rect.bottom - rect.top}


def windows(pids, parent=None):
    result = []
    @CB
    def visit(hwnd, _):
        pid = w.DWORD()
        u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        if pid.value in pids and u.IsWindowVisible(hwnd):
            result.append(window(hwnd))
        return True
    if parent is not None:
        u.EnumChildWindows(parent, visit, 0)
    else:
        u.EnumWindows(visit, 0)
    return result


def until(fn, label, seconds=30, tick=None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if tick is not None:
            tick()
        value = fn()
        if value:
            return value
        time.sleep(0.12)
    raise RuntimeError("Timed out waiting for " + label)


def click(win):
    """A bounded real pointer click, never BM_CLICK or fabricated Tk messages."""
    hwnd = win["hwnd"]
    need(u.IsWindow(hwnd) and u.IsWindowVisible(hwnd) and u.IsWindowEnabled(hwnd),
         "Click target is no longer visible/enabled")
    previous = w.POINT()
    need(u.GetCursorPos(c.byref(previous)), "Cannot read desktop cursor; unlock the desktop")
    top = u.GetAncestor(hwnd, 2)
    u.ShowWindow(top, 9)  # SW_RESTORE
    u.SetForegroundWindow(top)
    time.sleep(0.2)
    need(u.GetForegroundWindow() == top, "Cannot foreground test window; no click sent")
    current = window(hwnd)
    point = w.POINT(current["x"] + current["w"] // 2,
                    current["y"] + current["h"] // 2)
    down = False
    try:
        need(u.SetCursorPos(point.x, point.y), "Cannot position mouse on the target")
        time.sleep(0.15)
        hit = u.WindowFromPoint(point)
        need(hit == hwnd or u.IsChild(hwnd, hit), "Click target is obscured; no click sent")
        # ttk checks actual pointer containment. Preserve the validated first-game
        # approach: physical mouse movement and down/up events, not PostMessage.
        u.mouse_event(0x0002, 0, 0, 0, 0)
        down = True
        time.sleep(0.1)
        u.mouse_event(0x0004, 0, 0, 0, 0)
        down = False
        time.sleep(0.15)
    finally:
        if down:
            u.mouse_event(0x0004, 0, 0, 0, 0)
        u.SetCursorPos(previous.x, previous.y)


def action_buttons(controls, main):
    # ttk uses TkChild HWNDs without retrievable button captions. The first-game
    # verified fallback identifies the unique row of four button-sized controls.
    scale = 1.0
    if hasattr(u, "GetDpiForWindow"):
        u.GetDpiForWindow.argtypes = [w.HWND]
        u.GetDpiForWindow.restype = w.UINT
        scale = (u.GetDpiForWindow(main["hwnd"]) or 96) / 96.0
    candidates = [item for item in controls
                  if item["cls"].startswith("Tk")
                  and 65 * scale <= item["w"] <= 245 * scale
                  and 27 * scale <= item["h"] <= 65 * scale]
    groups = []
    for item in sorted(candidates, key=lambda v: (v["y"], v["x"])):
        group = next((row for row in groups
                      if abs(row[0]["y"] - item["y"]) <= 3 * scale
                      and abs(row[0]["h"] - item["h"]) <= 3 * scale), None)
        if group is None:
            groups.append([item])
        else:
            group.append(item)
    rows = [sorted(row, key=lambda item: item["x"]) for row in groups if len(row) == 4]
    need(len(rows) == 1, "Cannot uniquely identify four-action ttk row: " + repr(controls))
    actions = rows[0]
    need(all(a["x"] + a["w"] <= b["x"] for a, b in zip(actions, actions[1:])),
         "Ambiguous or overlapping action button geometry")
    captions = ["一键安装汉化", "检查原版", "卸载补丁", "打开游戏目录"]
    for item, caption in zip(actions, captions):
        if item["title"]:
            need(item["title"] == caption, "Unexpected action caption: " + item["title"])
    return actions


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            stat = path.stat()
            result[relative] = (sha(path.read_bytes()), stat.st_size, stat.st_mtime_ns)
        elif path.is_dir():
            result[relative] = ("directory",)
        else:
            raise RuntimeError("Unexpected filesystem object: " + relative)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-exe", type=Path, required=True,
                        help="Read-only path to the supported original momodora2.exe")
    args = parser.parse_args()
    source = args.source_exe.expanduser().resolve()
    checks = []
    report = {"success": False, "checks": checks, "count": 0,
              "gui_button_test": False, "target_python_required": False,
              "target_git_required": False, "game_launched": False,
              "scope": "real packaged GUI mouse click on isolated temporary game clone; "
                       "no live user saves copied or modified"}
    original_sha = exe_sha = None
    error = None
    try:
        init_win32()
        need(EXE.is_file(), "Built installer not found: " + str(EXE))
        manifest = json.loads((PATCH / "patch.json").read_text(encoding="utf-8"))
        need(manifest.get("format") == "momodora2-041-zh-source-v1", "Wrong manifest format")
        need(set(manifest.get("assets", {})) == ASSETS, "Unexpected manifest.assets")
        original = source.read_bytes()
        original_sha = sha(original)
        need(original_sha == manifest["original_sha256"], "Source EXE SHA-256 mismatch")
        exe_sha = sha(EXE.read_bytes())
        report.update(exe_sha256=exe_sha, exe_size_bytes=EXE.stat().st_size,
                      original_sha256=original_sha, target_sha256=manifest["target_sha256"],
                      assets=manifest["assets"], cli_path=clean_env()["PATH"])
        with tempfile.TemporaryDirectory(prefix="momo2-oneclick-gui-test-", dir=PATCH.parent) as tmp:
            root = Path(tmp) / "游戏副本 with spaces"
            (root / GRAPHICS).mkdir(parents=True)
            (root / GAME).write_bytes(original)
            sentinels = {
                "data/saves/slot1/save.ini": b"KEEP-ORIGINAL-SAVE-1\r\n",
                "data/saves/slot1/savemap.ini": b"KEEP-ORIGINAL-MAP-1\x00\xff",
                "data/saves/slot2/save.ini": b"KEEP-ORIGINAL-SAVE-2",
                "data/saves/slot2/savemap.ini": b"KEEP-ORIGINAL-MAP-2",
                "data/graphics/misc/tiles1.png": b"KEEP-ORIGINAL-RESOURCE",
                "original-readme.txt": b"KEEP-UNRELATED-FILE",
            }
            for relative, data in sentinels.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            before = snapshot(root)
            proc = subprocess.Popen(
                [str(EXE)], cwd=root, env=clean_env(), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            target = None
            known_pids = {proc.pid}
            process_names = {}

            def watch():
                rows = processes()
                known_pids.update(descendants(proc.pid, rows))
                for row in rows:
                    if row["pid"] in known_pids:
                        process_names[row["pid"]] = row["name"]
                        if row["name"].lower() in (GAME, OUTPUT):
                            report["game_launched"] = True
                            raise RuntimeError("Installer unexpectedly started a game process")

            try:
                def find_main():
                    mains = [v for v in windows(known_pids)
                             if v["cls"] == "TkTopLevel" and v["w"] > 500
                             and "Momodora 2" in v["title"]]
                    need(len(mains) <= 1, "More than one matching GUI main window")
                    return mains[0] if mains else None

                target = until(find_main, "Momodora 2 packaged GUI", seconds=60, tick=watch)
                report["window_title"] = target["title"]
                checks.append("packaged-Momodora-2-GUI-visible-with-no-Python-or-Git-PATH")
                controls = windows(known_pids, target["hwnd"])
                report["controls"] = controls
                actions = action_buttons(controls, target)
                report["action_buttons"] = actions
                checks.append("unique-four-action-ttk-row-found")
                need(snapshot(root) == before, "Opening GUI unexpectedly wrote game files")
                checks.append("GUI-startup-is-read-only")

                # No entry editing, browse dialog, CLI shortcut or direct Tk invoke:
                # installation must use the default cwd and the real Install button.
                click(actions[0])
                report["gui_button_test"] = True
                checks.append("actual-mouse-click-on-install-button")

                def find_result_dialog():
                    dialogs = [v for v in windows(known_pids) if v["cls"] == "#32770"]
                    if not dialogs:
                        return None
                    need(len(dialogs) == 1, "Ambiguous result dialogs: " + repr(dialogs))
                    dialog = dialogs[0]
                    child = windows(known_pids, dialog["hwnd"])
                    report["result_dialog"] = {"window": dialog, "controls": child}
                    need(dialog["title"] == "汉化完成",
                         "Install did not show Chinese success dialog: " + repr(dialog) + repr(child))
                    return dialog, child

                dialog, children = until(find_result_dialog, "Chinese install success dialog",
                                         seconds=180, tick=watch)
                checks.append("Chinese-install-success-dialog-shown")
                patched = root / OUTPUT
                need(patched.is_file(), "GUI did not create patched EXE in cwd")
                need(sha(patched.read_bytes()) == manifest["target_sha256"], "Patched EXE hash mismatch")
                checks.append("cwd-default-game-dir-used-and-target-exe-sha256-verified")
                for name, digest in manifest["assets"].items():
                    need(sha((root / GRAPHICS / name).read_bytes()) == digest,
                         "Installed asset hash mismatch: " + name)
                checks.append("all-three-assets-installed-under-data-graphics-misc-and-verified")
                record = json.loads((root / RECEIPT).read_text(encoding="utf-8"))
                need(record.get("format") == manifest["format"]
                     and record.get("version") == manifest["version"]
                     and record.get("exe_sha256") == manifest["target_sha256"]
                     and record.get("assets") == manifest["assets"], "Receipt mismatch")
                checks.append("complete-momo2-install-receipt-verified")
                after = snapshot(root)
                for relative, expected in before.items():
                    need(after.get(relative) == expected, "GUI modified original/save: " + relative)
                allowed = set(before) | {OUTPUT, RECEIPT.as_posix()} | {
                    (GRAPHICS / name).as_posix() for name in ASSETS}
                need(set(after) == allowed, "GUI left unexpected files or staging artifacts")
                checks.append("original-exe-resources-and-existing-save-map-files-preserved")
                checks.append("no-unexpected-files-or-staged-leftovers")
                ok_buttons = [v for v in children if v["cls"] == "Button"]
                need(len(ok_buttons) == 1, "Ambiguous success-dialog OK button")
                click(ok_buttons[0])
                until(lambda: not u.IsWindow(dialog["hwnd"]), "success dialog dismissal", tick=watch)
                checks.append("actual-mouse-click-dismisses-success-dialog")
                watch()
                u.PostMessageW(target["hwnd"], WM_CLOSE, 0, 0)
                proc.wait(timeout=20)
                need(proc.returncode == 0, "GUI did not close cleanly: " + str(proc.returncode))
                watch()
                need(snapshot(root) == after, "Closing GUI changed installed game files")
                checks.append("clean-GUI-exit-without-launching-game")
                report["observed_processes"] = process_names
            finally:
                # WM_CLOSE first; taskkill only descendants owned by this test.
                if target is not None and u.IsWindow(target["hwnd"]):
                    u.PostMessageW(target["hwnd"], WM_CLOSE, 0, 0)
                if proc.poll() is None:
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                rows = processes()
                known_pids.update(descendants(proc.pid, rows))
                active = {row["pid"] for row in rows}
                taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/taskkill.exe"
                for pid in sorted(known_pids & active):
                    if pid != os.getpid():
                        subprocess.run(
                            [str(taskkill), "/PID", str(pid), "/T", "/F"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=15, check=False)
                if proc.poll() is None:
                    proc.wait(timeout=10)
        report["success"] = True
    except Exception as exc:
        error = exc
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if original_sha is not None:
            try:
                report["original_unchanged"] = sha(source.read_bytes()) == original_sha
                need(report["original_unchanged"], "Supplied source executable changed during test")
                if exe_sha is not None:
                    report["installer_unchanged"] = sha(EXE.read_bytes()) == exe_sha
                    need(report["installer_unchanged"], "Packaged installer changed during test")
            except Exception as exc:
                error = exc
                report["error"] = f"{type(exc).__name__}: {exc}"
                report["success"] = False
        report["count"] = len(checks)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if sys.stdout is not None:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
    if error is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
