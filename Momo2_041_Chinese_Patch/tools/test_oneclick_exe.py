"""Black-box safety tests for the shipped Momodora 2 one-file installer.

Run explicitly after packaging, from an interactive Windows session::

    python tools/test_oneclick_exe.py --source-exe <original-momodora2.exe>

Only the packaged installer is exercised; no patch implementation is imported,
no game is launched, and all game mutations are confined to a temporary clone
under PATCH.parent. The supplied source executable is opened read-only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PATCH = Path(__file__).resolve().parents[1]
REPO = PATCH.parent
EXE = PATCH / "Momodora2ZH_Setup.exe"
REPORT = PATCH / "oneclick_exe_test_report.json"
GAME = "momodora2.exe"
OUTPUT = "momodora2_zh.exe"
GRAPHICS = Path("data/graphics/misc")
RECEIPT = GRAPHICS / "momo2_zh_install.json"
ASSETS = {"momo2_zh_text.png", "momo2_zh_ctrl.png", "atlas_layout.json"}


def need(condition, message):
    # Do not use assert: running Python with -O must not disable a safety check.
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


def snapshot(root):
    """Detect any created/deleted/rewritten file, including staged leftovers."""
    result = {}
    for path in sorted(root.rglob("*")):
        key = path.relative_to(root).as_posix()
        if path.is_file():
            stat = path.stat()
            result[key] = ("file", sha(path.read_bytes()), stat.st_size, stat.st_mtime_ns)
        elif path.is_dir():
            result[key] = ("directory",)
        else:
            raise RuntimeError("Unexpected filesystem object in isolated clone: " + key)
    return result


def same_tree(root, before, context):
    after = snapshot(root)
    changed = sorted(key for key in before.keys() | after.keys()
                     if before.get(key) != after.get(key))
    need(not changed, context + " modified files/directories: " + repr(changed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-exe", type=Path, required=True,
                        help="Read-only path to the supported original momodora2.exe")
    args = parser.parse_args()
    source = args.source_exe.expanduser().resolve()
    tests = []
    invocations = []
    report = {
        "success": False, "passed": tests, "count": 0,
        "invocations": invocations, "target_python_required": False,
        "target_git_required": False, "game_launched": False,
        "test_scope": "isolated temporary game clone under the second-game workspace; "
                      "no live user saves copied or modified",
    }
    original_sha = None
    exe_sha = None
    error = None
    try:
        need(sys.platform == "win32", "The shipped Windows EXE test requires Windows")
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
        targets = [Path(OUTPUT)] + [GRAPHICS / name for name in sorted(ASSETS)]
        with tempfile.TemporaryDirectory(prefix="momo2-oneclick-exe-test-", dir=REPO) as temp:
            root = Path(temp) / "游戏副本 with spaces"
            (root / GRAPHICS).mkdir(parents=True)
            (root / GAME).write_bytes(original)
            # Realistic save names, plus unrelated original resources and root files.
            sentinels = {
                "data/saves/slot1/save.ini": b"[save]\r\nKEEP-ORIGINAL-SAVE-1\r\n",
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
            pristine = snapshot(root)

            def protected():
                for relative in [GAME] + list(sentinels):
                    if relative not in pristine:
                        # The missing-original case temporarily renames GAME.
                        continue
                    path = root / relative
                    expected = pristine[Path(relative).as_posix()]
                    need(path.is_file(), "Original/save deleted: " + relative)
                    stat = path.stat()
                    actual = ("file", sha(path.read_bytes()), stat.st_size, stat.st_mtime_ns)
                    need(actual == expected, "Original/save rewritten: " + relative)

            def run(action, ok=True):
                command = [str(EXE), action, str(root)]
                result = subprocess.run(
                    command, cwd=PATCH, env=clean_env(), stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=180, check=False)
                invocations.append({"action": action, "expected_success": ok,
                                    "returncode": result.returncode})
                need((result.returncode == 0) == ok,
                     f"{action} returned {result.returncode}; expected success={ok}")
                protected()

            def refused(action, label):
                before = snapshot(root)
                run(action, ok=False)
                same_tree(root, before, label)

            def installed():
                need(sha((root / OUTPUT).read_bytes()) == manifest["target_sha256"],
                     "Unexpected patched EXE SHA-256")
                for name, digest in manifest["assets"].items():
                    need(sha((root / GRAPHICS / name).read_bytes()) == digest,
                         "Unexpected installed asset SHA-256: " + name)
                record = json.loads((root / RECEIPT).read_text(encoding="utf-8"))
                need(record.get("format") == manifest["format"], "Receipt format mismatch")
                need(record.get("version") == manifest["version"], "Receipt version mismatch")
                need(record.get("exe_sha256") == manifest["target_sha256"], "Receipt EXE mismatch")
                need(record.get("assets") == manifest["assets"], "Receipt asset map mismatch")
                allowed = set(pristine) | {p.as_posix() for p in targets + [RECEIPT]}
                need(set(snapshot(root)) == allowed, "Install created unexpected files")
                protected()

            before = snapshot(root)
            run("--cli-check")
            same_tree(root, before, "Check-only mode")
            tests.append("embedded-manifest-and-three-assets-check-with-zero-game-writes")

            run("--cli-install")
            installed()
            tests.append("onefile-install-verifies-target-and-all-three-resource-sha256")
            tests.append("receipt-format-version-exe-and-complete-assets-verified")
            tests.append("original-resources-and-existing-save-map-files-preserved")
            good = {p: (root / p).read_bytes() for p in targets + [RECEIPT]}

            before = snapshot(root)
            run("--cli-install")
            same_tree(root, before, "Same-version install")
            tests.append("same-version-install-idempotent-without-rewriting-files")
            before = snapshot(root)
            run("--cli-check")
            same_tree(root, before, "Check on installed clone")
            tests.append("check-after-install-is-read-only")

            # A receipt never permits silently repairing any missing target.
            for relative in targets:
                (root / relative).unlink()
                refused("--cli-install", "Partial receipt: " + relative.name)
                tests.append("partial-receipt-missing-" + relative.name + "-rejected")
                (root / relative).write_bytes(good[relative])

            # Preflight the complete target set before any unlink or overwrite.
            for relative in targets:
                (root / relative).write_bytes(b"USER-MODIFIED:" + relative.name.encode("ascii"))
                refused("--cli-install", "Modified install target: " + relative.name)
                tests.append("modified-" + relative.name + "-not-overwritten")
                refused("--cli-remove", "Modified uninstall target: " + relative.name)
                tests.append("modified-" + relative.name + "-blocks-entire-uninstall")
                (root / relative).write_bytes(good[relative])

            # Refuse all malformed, incomplete, foreign and forged receipt variants.
            record = json.loads(good[RECEIPT].decode("utf-8"))
            missing_asset = dict(record, assets=dict(record["assets"]))
            missing_asset["assets"].pop("atlas_layout.json")
            bad_records = {
                "empty": {},
                "missing-assets": {k: v for k, v in record.items() if k != "assets"},
                "partial-assets-map": missing_asset,
                "foreign-format": dict(record, format="foreign-patch"),
                "wrong-exe-hash": dict(record, exe_sha256="0" * 64),
                "wrong-asset-hash": dict(record, assets={**record["assets"],
                                                        "momo2_zh_ctrl.png": "0" * 64}),
                "malformed-json": None,
            }
            for name, value in bad_records.items():
                data = b"{not valid json" if value is None else json.dumps(value).encode("utf-8")
                (root / RECEIPT).write_bytes(data)
                refused("--cli-install", "Bad receipt install: " + name)
                refused("--cli-remove", "Bad receipt uninstall: " + name)
                tests.append("receipt-" + name + "-blocks-install-and-uninstall")
            (root / RECEIPT).write_bytes(good[RECEIPT])

            (root / RECEIPT).unlink()
            refused("--cli-install", "Matching files without receipt")
            refused("--cli-remove", "Unowned files without receipt")
            tests.append("even-matching-unowned-files-require-valid-receipt")
            (root / RECEIPT).write_bytes(good[RECEIPT])
            run("--cli-remove")
            same_tree(root, pristine, "Safe complete uninstall")
            tests.append("safe-uninstall-removes-only-owned-files-preserves-original-and-saves")
            refused("--cli-remove", "Second uninstall without receipt")
            tests.append("uninstall-without-receipt-is-read-only-refusal")

            # Every destination, including the receipt, is tested independently.
            # Directory collisions also must not leave other resources installed.
            for relative in targets + [RECEIPT]:
                collision = root / relative
                collision.write_bytes(b"KEEP-UNKNOWN-SAME-NAME")
                refused("--cli-install", "Unknown same-name file: " + relative.name)
                tests.append("unknown-same-name-file-" + relative.name + "-protected")
                collision.unlink()
                collision.mkdir()
                (collision / "keep.txt").write_bytes(b"KEEP-UNKNOWN-DIRECTORY")
                refused("--cli-install", "Unknown same-name directory: " + relative.name)
                tests.append("unknown-same-name-directory-" + relative.name + "-protected")
                (collision / "keep.txt").unlink()
                collision.rmdir()

            game = root / GAME
            game.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            # The intentional fixture mutation is not an installer modification.
            pristine[GAME] = snapshot(root)[GAME]
            refused("--cli-check", "Modified original check")
            refused("--cli-install", "Modified original install")
            tests.append("wrong-version-or-modified-original-rejected-without-writing")
            game.write_bytes(original)
            pristine[GAME] = snapshot(root)[GAME]

            absent = root / "original-read-only-fixture.bin"
            game.rename(absent)
            expected_game = pristine.pop(GAME)
            refused("--cli-check", "Missing original check")
            refused("--cli-install", "Missing original install")
            tests.append("missing-original-exe-rejected-without-writing")
            absent.rename(game)
            pristine[GAME] = expected_game

            graphics = root / GRAPHICS
            moved = graphics.with_name("misc-preserved-fixture")
            graphics.rename(moved)
            # Exclude the relocated resource only from per-invocation protection;
            # the full-tree refusal snapshot still protects its exact bytes.
            resource_key = "data/graphics/misc/tiles1.png"
            resource_data = sentinels.pop(resource_key)
            try:
                refused("--cli-check", "Missing graphics directory check")
                refused("--cli-install", "Missing graphics directory install")
            finally:
                sentinels[resource_key] = resource_data
                moved.rename(graphics)
            tests.append("incomplete-game-missing-graphics-directory-rejected")

            # A valid receipt can safely remove an otherwise unmodified partial
            # installation, as promised by the core's missing-file recovery path.
            run("--cli-install")
            installed()
            (root / GRAPHICS / "momo2_zh_text.png").unlink()
            run("--cli-remove")
            same_tree(root, pristine, "Uninstall of missing-file partial installation")
            tests.append("receipt-owned-partial-install-can-be-safely-uninstalled")
            protected()
        report["success"] = True
    except Exception as exc:
        error = exc
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if original_sha is not None:
            try:
                report["original_unchanged"] = sha(source.read_bytes()) == original_sha
                if not report["original_unchanged"]:
                    raise RuntimeError("Supplied source executable changed during test")
                if exe_sha is not None:
                    report["installer_unchanged"] = sha(EXE.read_bytes()) == exe_sha
                    need(report["installer_unchanged"], "Packaged installer changed during test")
            except Exception as exc:
                error = exc
                report["error"] = f"{type(exc).__name__}: {exc}"
                report["success"] = False
        report["count"] = len(tests)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if sys.stdout is not None:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
    if error is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
