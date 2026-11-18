import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("keyboard_installer", ROOT / "tools/install.py")
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="keyboard-install-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        home = self.root / "home with spaces"
        home.mkdir()
        self.paths = installer.Locations(
            home, home / "config", home / "data", home / "state")
        self.project = self.root / "project"
        for relative, data in {
            "build/libwindowscompose.so": b"\x7fELFtest fixture",
            "data/compose/windows-us-intl": b'<dead_acute> <c> : "\xc3\xa7"\n',
            "data/xkb/symbols/us_windows_intl": b'partial xkb_symbols "basic" {};\n',
            "data/xkb/types/windows_us_intl": b'partial xkb_types "basic" {};\n',
            "data/xkb/rules/windows-us-intl": b'! layout[1] = types\n  us_windows_intl = +windows_us_intl\n',
        }.items():
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def plan(self, hyprland=False):
        return installer.plan(self.paths, hyprland, self.project)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def files(self):
        return {str(p.relative_to(self.paths.home)): p.read_bytes()
                for p in self.paths.home.rglob("*") if p.is_file()}

    def existing_configuration(self):
        self.main = self.write(self.paths.home / ".XCompose",
                               '# Existing shortcuts\ninclude "%L"\n<Multi_key> <m> <s> : "😄"\n')
        self.rules = self.write(self.paths.config / "xkb/rules/evdev",
                                "! include %S/evdev\n// Personal XKB rules\n")
        self.input = self.write(self.paths.config / "hypr/input.lua",
                                'hl.config({ input = { kb_layout = "us", kb_options = "compose:caps" } })\n')

    def test_plan_is_read_only(self):
        self.existing_configuration()
        before = self.files()
        plan = self.plan(True)
        self.assertEqual(before, self.files())
        self.assertFalse(self.paths.backup.exists())
        self.assertIn(b"compose:caps", plan.files[self.input])

    def test_round_trip_preserves_bytes_permissions_and_timestamps(self):
        self.existing_configuration()
        self.main.chmod(0o600)
        before = self.files()
        metadata = self.main.stat()
        installer.install(self.paths, self.plan(True))
        self.assertIn("Personal XKB rules", self.rules.read_text())
        self.assertIn("Existing shortcuts", self.main.read_text())
        self.assertIn("compose:caps", self.input.read_text())
        self.assertEqual(stat.S_IMODE(self.paths.backup.stat().st_mode), 0o700)
        installer.uninstall(self.paths)
        self.assertEqual(before, self.files())
        self.assertEqual(stat.S_IMODE(self.main.stat().st_mode), 0o600)
        self.assertEqual(self.main.stat().st_mtime_ns, metadata.st_mtime_ns)
        self.assertFalse(self.paths.backup.exists())
        self.assertFalse(list(self.paths.home.rglob(".windows-us-intl-*")))

    def test_fresh_install_is_removed_completely(self):
        installer.install(self.paths, self.plan())
        self.assertTrue((self.paths.home / ".XCompose").read_text().startswith('include "%L"'))
        installer.uninstall(self.paths)
        self.assertEqual(list(self.paths.home.iterdir()), [])

    def test_custom_xdg_paths_are_used_in_compose_and_addon(self):
        plan = self.plan()
        main = plan.files[self.paths.home / ".XCompose"].decode()
        addon = plan.files[self.paths.data / "fcitx5/addon/windowscompose.conf"].decode()
        self.assertIn(str(self.paths.config / "fcitx5/windowscompose/Compose"), main)
        self.assertIn(str(self.paths.data / "fcitx5/windowscompose/libwindowscompose"), addon)

    def test_unmanaged_owned_file_is_not_overwritten(self):
        path = self.write(self.paths.config / "fcitx5/windowscompose/Compose", "personal data")
        before = self.files()
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            self.plan()
        self.assertEqual(path.read_text(), "personal data")
        self.assertEqual(before, self.files())

    def test_compose_symlink_is_not_followed(self):
        external = self.write(self.root / "external-compose", "personal data")
        (self.paths.home / ".XCompose").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()
        self.assertEqual(external.read_text(), "personal data")

    def test_parent_symlink_is_not_followed(self):
        external = self.root / "outside"
        external.mkdir()
        self.paths.config.mkdir()
        (self.paths.config / "xkb").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()
        self.assertEqual(list(external.iterdir()), [])

    def test_existing_managed_marker_is_not_duplicated(self):
        self.write(self.paths.home / ".XCompose", "# BEGIN windows-us-intl\n")
        with self.assertRaisesRegex(ValueError, "block already exists"):
            self.plan()

    def test_second_install_is_refused(self):
        installer.install(self.paths, self.plan())
        before = self.files()
        with self.assertRaisesRegex(ValueError, "backup exists"):
            self.plan()
        self.assertEqual(before, self.files())

    def test_edits_after_plan_are_preserved(self):
        self.existing_configuration()
        plan = self.plan()
        self.main.write_text("a new user edit")
        before = self.files()
        with self.assertRaisesRegex(ValueError, "changed after"):
            installer.install(self.paths, plan)
        self.assertEqual(before, self.files())

    def test_uninstall_checks_all_files_before_restoring_any(self):
        self.existing_configuration()
        installer.install(self.paths, self.plan(True))
        self.input.write_text("a later user edit")
        before = self.files()
        with self.assertRaisesRegex(ValueError, "edited after installation"):
            installer.uninstall(self.paths)
        self.assertEqual(before, self.files())

    def test_modified_backup_is_not_restored(self):
        self.existing_configuration()
        installer.install(self.paths, self.plan())
        manifest = json.loads((self.paths.backup / "manifest.json").read_text())
        entry = next(e for e in manifest["files"] if e["original"] is not None)
        (self.paths.backup / "originals" / entry["original"]).write_text("corrupt")
        before = self.files()
        with self.assertRaisesRegex(ValueError, "backup was modified"):
            installer.uninstall(self.paths)
        self.assertEqual(before, self.files())

    def test_uninstall_keeps_unrelated_files_and_their_directories(self):
        installer.install(self.paths, self.plan())
        other = self.write(self.paths.config / "xkb/symbols/personal", "my layout")
        installer.uninstall(self.paths)
        self.assertEqual(other.read_text(), "my layout")
        self.assertEqual(self.files(), {str(other.relative_to(self.paths.home)): b"my layout"})

    def test_install_failure_rolls_back_and_leaves_no_staging_files(self):
        self.existing_configuration()
        before = self.files()
        real_write = installer.atomic_write
        failed = False

        def fail_once(path, *args, **kwargs):
            nonlocal failed
            if path == self.paths.config / "fcitx5/windowscompose/Compose" and not failed:
                failed = True
                raise OSError("simulated write failure")
            return real_write(path, *args, **kwargs)

        with patch.object(installer, "atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "simulated"):
                installer.install(self.paths, self.plan(True))
        self.assertEqual(before, self.files())
        self.assertFalse(self.paths.backup.exists())

    def test_partial_recovery_accepts_original_and_missing_files(self):
        self.existing_configuration()
        original = self.main.read_bytes()
        installer.install(self.paths, self.plan(True))
        self.main.write_bytes(original)
        (self.paths.data / "fcitx5/windowscompose/libwindowscompose.so").unlink()
        installer.uninstall(self.paths)
        self.assertEqual(self.main.read_bytes(), original)
        self.assertFalse(self.paths.backup.exists())

    def test_hyprland_flag_requires_existing_user_module(self):
        with self.assertRaisesRegex(ValueError, "existing hypr/input.lua"):
            self.plan(True)

    def test_xdg_compose_file_takes_precedence_without_becoming_a_directory(self):
        path = self.write(self.paths.config / "XCompose", 'include "%L"\n')
        before = path.read_bytes()
        plan = self.plan()
        self.assertIn(path, plan.files)
        self.assertNotIn(self.paths.home / ".XCompose", plan.files)
        installer.install(self.paths, plan)
        installer.uninstall(self.paths)
        self.assertEqual(path.read_bytes(), before)

    def test_explicit_compose_file_is_preserved(self):
        path = self.write(self.paths.home / "custom Compose", 'include "%L"\n')
        locations = replace(self.paths, compose=path)
        plan = installer.plan(locations, project=self.project)
        self.assertIn(path, plan.files)
        self.assertNotIn(self.paths.home / ".XCompose", plan.files)
        installer.install(locations, plan)
        installer.uninstall(locations)
        self.assertEqual(path.read_text(), 'include "%L"\n')

    def test_symlinked_backup_is_not_followed(self):
        self.existing_configuration()
        installer.install(self.paths, self.plan())
        manifest = json.loads((self.paths.backup / "manifest.json").read_text())
        entry = next(e for e in manifest["files"] if e["original"] is not None)
        source = self.paths.backup / "originals" / entry["original"]
        outside = self.root / "outside-backup"
        source.rename(outside)
        source.symlink_to(outside)
        before = self.files()
        with self.assertRaisesRegex(ValueError, "symlink"):
            installer.uninstall(self.paths)
        self.assertEqual(before, self.files())


if __name__ == "__main__":
    unittest.main()
