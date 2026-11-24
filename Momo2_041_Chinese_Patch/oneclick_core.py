"""Transactional, stdlib-only core for the standalone Windows patch installer."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

PATCH_DIR = Path(__file__).resolve().parent
TOOLS_DIR = PATCH_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(PATCH_DIR) not in sys.path:
    sys.path.insert(0, str(PATCH_DIR))
import apply_patch as engine


def sha(data):
    return hashlib.sha256(data).hexdigest()


def resources(patch_dir=None):
    base = Path(patch_dir or PATCH_DIR).resolve()
    m = json.loads((base / "patch.json").read_text(encoding="utf-8"))
    engine.need(m.get("format") == "momodora2-041-zh-source-v1", "补丁清单格式不受支持。")
    engine.need(m.get("original_sha256") == engine.ORIGINAL, "补丁清单与游戏版本不匹配。")
    expected = {"momo2_zh_text.png", "momo2_zh_ctrl.png", "atlas_layout.json"}
    engine.need(set(m.get("assets", {})) == expected, "补丁资源列表不完整。")
    assets = {}
    for name, digest in m["assets"].items():
        assets[name] = (base / "assets" / name).read_bytes()
        engine.need(sha(assets[name]) == digest, "补丁资源校验失败：" + name + "。请重新下载安装器。")
    return m, assets


def check(game_dir, patch_dir=None):
    root = Path(game_dir).expanduser().resolve()
    m, _ = resources(patch_dir)
    source = root / "momodora2.exe"
    engine.need(source.is_file(), "所选文件夹中没有 momodora2.exe，请选择游戏根目录。")
    engine.need(sha(source.read_bytes()) == engine.ORIGINAL,
                "原版 SHA-256 不匹配；请使用未修改的 Momodora II v041。未写入任何文件。")
    engine.need((root / "data/graphics/misc").is_dir(), "缺少 data\\graphics\\misc，请选择完整游戏目录。")
    return {"result": "valid", "game_dir": str(root)}


def _stage(folder, filename, data):
    fd, temp_name = tempfile.mkstemp(prefix="." + filename + ".", suffix=".tmp", dir=folder)
    path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def _targets(root, manifest):
    graphic = root / "data/graphics/misc"
    return [(root / engine.OUTPUT, manifest["target_sha256"])] + [
        (graphic / name, digest) for name, digest in manifest["assets"].items()]


def _receipt_ok(receipt, manifest):
    return (receipt.get("format") == manifest["format"] and
            receipt.get("exe_sha256") == manifest["target_sha256"] and
            receipt.get("assets") == manifest["assets"])


def install(game_dir, patch_dir=None):
    root = Path(game_dir).expanduser().resolve()
    check(root, patch_dir)
    manifest, assets = resources(patch_dir)
    source = root / "momodora2.exe"
    original = source.read_bytes()
    targets = _targets(root, manifest)
    receipt_path = root / "data/graphics/misc" / engine.RECEIPT
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        engine.need(_receipt_ok(receipt, manifest), "现有安装记录不属于本补丁版本，未修改文件。")
        for path, expected in targets:
            engine.need(path.is_file(), "安装记录存在但文件缺失：" + path.name + "。请先卸载残缺补丁。")
            engine.need(sha(path.read_bytes()) == expected, "现有汉化文件已被更改：" + path.name + "。为保护文件，未覆盖。")
        return {"result": "already-installed", "game_dir": str(root), "exe": str(targets[0][0])}
    for path, _ in targets:
        engine.need(not path.exists(), "发现无安装记录的同名文件：" + path.name + "。请核实后手动移走，未覆盖。")
    patched = engine.make_patched(original, manifest)
    engine.need(sha(patched) == manifest["target_sha256"], "补丁输出与已验证哈希不一致；未写入任何文件。")
    engine.need(sha(source.read_bytes()) == engine.ORIGINAL, "原版在处理中发生变化；已停止。")
    record = {"format": manifest["format"], "version": manifest["version"],
              "exe_sha256": sha(patched), "assets": manifest["assets"]}
    data = [(targets[0][0], patched)] + [(path, assets[path.name]) for path, _ in targets[1:]]
    data.append((receipt_path, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")))
    staged = []
    installed = []
    try:
        for path, value in data:
            staged.append((_stage(path.parent, path.name, value), path))
        for temp, destination in staged:
            # Windows rename is no-clobber; fail if a concurrent writer created a target.
            os.rename(temp, destination)
            installed.append(destination)
    except Exception:
        for temp, _ in staged:
            temp.unlink(missing_ok=True)
        for path in reversed(installed):
            path.unlink(missing_ok=True)
        raise
    return {"result": "installed", "game_dir": str(root), "exe": str(targets[0][0]),
            "exe_sha256": sha(patched), "original_preserved": True}


def remove(game_dir, patch_dir=None):
    root = Path(game_dir).expanduser().resolve()
    manifest, _ = resources(patch_dir)
    receipt_path = root / "data/graphics/misc" / engine.RECEIPT
    engine.need(receipt_path.is_file(), "找不到汉化安装记录，没有可安全卸载的补丁。")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    engine.need(_receipt_ok(receipt, manifest), "安装记录不匹配；未删除任何文件。")
    targets = _targets(root, manifest)
    for path, expected in targets:
        if path.exists():
            engine.need(path.is_file() and sha(path.read_bytes()) == expected,
                        "检测到已修改的文件：" + path.name + "。为保护文件，未删除。")
    removed = []
    for path in [p for p, _ in targets] + [receipt_path]:
        if path.exists():
            path.unlink()
            removed.append(path.name)
    return {"result": "removed", "removed": removed, "original_preserved": True}
