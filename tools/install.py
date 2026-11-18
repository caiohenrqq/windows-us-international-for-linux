#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from dataclasses import dataclass


PROJECT = Path(__file__).resolve().parents[1]
NAME = "fcitx5-windows-us-intl"
BLOCK = "windows-us-intl"


@dataclass(frozen=True)
class Locations:
    home: Path
    config: Path
    data: Path
    state: Path
    compose: Path | None = None

    @classmethod
    def current(cls):
        home = Path.home()
        override = os.environ.get("XCOMPOSEFILE")
        compose = Path(override) if override else None
        if compose is not None and not compose.is_absolute():
            raise ValueError("XCOMPOSEFILE must be an absolute path")
        return cls(home, xdg("XDG_CONFIG_HOME", home / ".config"),
                   xdg("XDG_DATA_HOME", home / ".local/share"),
                   xdg("XDG_STATE_HOME", home / ".local/state"), compose)

    @property
    def backup(self):
        return self.state / NAME

    @property
    def compose_file(self):
        if self.compose is not None:
            return self.compose
        xdg_compose = self.config / "XCompose"
        if xdg_compose.is_symlink() or xdg_compose.is_file():
            return xdg_compose
        return self.home / ".XCompose"


@dataclass(frozen=True)
class InstallationPlan:
    files: dict
    original_hashes: dict


def xdg(variable, fallback):
    value = Path(os.environ[variable]) if os.environ.get(variable) else fallback
    return value if value.is_absolute() else fallback


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular_file(path):
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError(f"Refusing to write through a symlink: {parent}")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"Refusing to replace a symlink or non-file: {path}")


def append_block(original, body, comment):
    start = f"{comment} BEGIN {BLOCK}"
    end = f"{comment} END {BLOCK}"
    if start in original or end in original:
        raise ValueError("A managed keyboard block already exists")
    separator = "" if not original or original.endswith("\n\n") else "\n"
    if original and not original.endswith("\n"):
        separator = "\n\n"
    return original + separator + start + "\n" + body + "\n" + end + "\n"


def atomic_write(path, data, mode=0o644):
    descriptor, temporary = tempfile.mkstemp(prefix=".windows-us-intl-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def make_parents(path, created):
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"Expected a directory, not a symlink: {path}")
    for directory in reversed(missing):
        directory.mkdir()
        created.append(str(directory))


def quote_compose(path):
    return str(path).replace("\\", "\\\\").replace('"', '\\"')


def plan(locations, configure_hyprland=False, project=PROJECT):
    if locations.backup.exists():
        raise ValueError(f"An installation or recovery backup exists: {locations.backup}")
    library = locations.data / "fcitx5/windowscompose/libwindowscompose.so"
    addon = locations.data / "fcitx5/addon/windowscompose.conf"
    compose = locations.config / "fcitx5/windowscompose/Compose"
    symbols = locations.config / "xkb/symbols/us_windows_intl"
    types = locations.config / "xkb/types/windows_us_intl"
    owned = {
        library: (project / "build/libwindowscompose.so").read_bytes(),
        addon: (
            "[Addon]\nName=Windows US-International dead keys\n"
            f"Type=SharedLibrary\nLibrary={library.with_suffix('')}\n"
            "Category=Module\nVersion=0.1.0\nOnDemand=False\nConfigurable=False\n"
            "\n[Addon/Dependencies]\n0=core:5.1.23\n1=keyboard\n"
        ).encode(),
        compose: (project / "data/compose/windows-us-intl").read_bytes(),
        symbols: (project / "data/xkb/symbols/us_windows_intl").read_bytes(),
        types: (project / "data/xkb/types/windows_us_intl").read_bytes(),
    }
    for path in owned:
        regular_file(path)
        if path.exists():
            raise ValueError(f"An unmanaged file already exists: {path}")
    original_hashes = {path: None for path in owned}

    def read_original(path, default=""):
        regular_file(path)
        original = path.read_bytes() if path.exists() else None
        original_hashes[path] = digest(original) if original is not None else None
        return original.decode() if original is not None else default

    main = locations.compose_file
    rules = locations.config / "xkb/rules/evdev"
    regular_file(main)
    regular_file(rules)
    base = read_original(main, 'include "%L"\n')
    owned[main] = append_block(
        base, f'include "{quote_compose(compose)}"', "#").encode()
    base = read_original(rules)
    if not rules.exists():
        upstream = "/etc/xkb/rules/evdev" if Path("/etc/xkb/rules/evdev").is_file() else "%S/evdev"
        base = f"! include {upstream}\n"
    owned[rules] = append_block(
        base, (project / "data/xkb/rules/windows-us-intl").read_text().rstrip("\n"), "//").encode()
    if configure_hyprland:
        path = locations.config / "hypr/input.lua"
        regular_file(path)
        if not path.is_file():
            raise ValueError("--hyprland requires an existing hypr/input.lua")
        owned[path] = append_block(read_original(path),
                                  'hl.config({ input = { kb_layout = "us_windows_intl", kb_variant = "" } })',
                                  "--").encode()
    for path in owned:
        regular_file(path)
        parent = path.parent
        while not parent.exists():
            parent = parent.parent
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError(f"Expected a regular parent directory: {parent}")
    return InstallationPlan(owned, original_hashes)


def install(locations, installation_plan):
    files = installation_plan.files
    for path, expected in installation_plan.original_hashes.items():
        regular_file(path)
        actual = digest(path.read_bytes()) if path.exists() else None
        if actual != expected:
            raise ValueError(f"A file changed after the installation plan was prepared: {path}")
    created = []
    make_parents(locations.backup.parent, created)
    locations.backup.mkdir(mode=0o700)
    originals = locations.backup / "originals"
    originals.mkdir()
    manifest = {"version": 1, "status": "installing", "files": [],
                "created_directories": created}
    try:
        for index, (path, data) in enumerate(files.items()):
            regular_file(path)
            entry = {"path": str(path), "installed_sha256": digest(data), "original": None}
            if path.exists():
                original = str(index)
                shutil.copy2(path, originals / original)
                entry["original"] = original
                entry["original_sha256"] = digest(path.read_bytes())
            manifest["files"].append(entry)
        planned_directories = set()
        for path in files:
            parent = path.parent
            while not parent.exists():
                planned_directories.add(parent)
                parent = parent.parent
        created.extend(str(path) for path in sorted(planned_directories, key=lambda p: len(p.parts)))
        # Persist originals and recovery instructions before changing any file.
        save_manifest(locations, manifest)
        for path, data in files.items():
            make_parents(path.parent, [])
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
            atomic_write(path, data, mode)
        manifest["status"] = "installed"
        save_manifest(locations, manifest)
    except BaseException:
        if (locations.backup / "manifest.json").exists():
            uninstall(locations)
        else:
            shutil.rmtree(locations.backup)
            remove_empty(created)
        raise


def save_manifest(locations, manifest):
    atomic_write(locations.backup / "manifest.json",
                 (json.dumps(manifest, indent=2) + "\n").encode(), 0o600)


def remove_empty(directories):
    for name in reversed(directories):
        path = Path(name)
        try:
            path.rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            if path.exists() and (not path.is_dir() or not any(path.iterdir())):
                raise


def uninstall(locations):
    manifest_path = locations.backup / "manifest.json"
    regular_file(manifest_path)
    if not manifest_path.is_file():
        raise ValueError(f"No recovery manifest found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("version") != 1:
        raise ValueError("Unsupported recovery manifest version")
    originals = locations.backup / "originals"
    for entry in manifest["files"]:
        path = Path(entry["path"])
        regular_file(path)
        if entry["original"] is not None:
            original = originals / entry["original"]
            regular_file(original)
            if digest(original.read_bytes()) != entry["original_sha256"]:
                raise ValueError(f"The backup was modified: {original}")
        if path.exists():
            allowed = {entry["installed_sha256"], entry.get("original_sha256")}
            if digest(path.read_bytes()) not in allowed:
                raise ValueError(f"A file was edited after installation; nothing was changed: {path}")
    for entry in reversed(manifest["files"]):
        path = Path(entry["path"])
        if entry["original"] is None:
            path.unlink(missing_ok=True)
        else:
            source = originals / entry["original"]
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
            shutil.copystat(source, path)
    for entry in manifest["files"]:
        if entry["original"] is not None:
            (originals / entry["original"]).unlink()
    originals.rmdir()
    manifest_path.unlink()
    locations.backup.rmdir()
    remove_empty(manifest["created_directories"])


def main():
    parser = argparse.ArgumentParser(description="Install Windows-style dead keys for the current user.")
    parser.add_argument("command", choices=("install", "uninstall", "status"))
    parser.add_argument("--hyprland", action="store_true", help="append the layout override to hypr/input.lua")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command != "install" and (args.hyprland or args.dry_run):
        parser.error("--hyprland and --dry-run are supported for install only")
    if os.geteuid() == 0:
        parser.exit(1, "Run this command as your desktop user, without sudo.\n")
    try:
        locations = Locations.current()
        if args.command == "install":
            files = plan(locations, args.hyprland)
            for path in files.files:
                print(f"{'update' if path.exists() else 'create'} {path}")
            if not args.dry_run:
                install(locations, files)
                print(f"Backup: {locations.backup}")
                print("Restart Fcitx5 and reload your compositor configuration to activate.")
        elif args.command == "uninstall":
            uninstall(locations)
            print("Original files restored; installed files and backup removed.")
            print("Restart Fcitx5 and reload your compositor configuration.")
        else:
            path = locations.backup / "manifest.json"
            print(json.loads(path.read_text())["status"] if path.exists() else "not installed")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
