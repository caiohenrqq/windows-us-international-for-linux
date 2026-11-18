import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KeyboardMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="windowsintl-xkb-test-")
        cls.directory = Path(cls.temporary.name)
        shutil.copytree(ROOT / "data/xkb", cls.directory, dirs_exist_ok=True)
        rules = cls.directory / "rules"
        rules.mkdir(exist_ok=True)
        upstream = "/etc/xkb/rules/evdev" if Path("/etc/xkb/rules/evdev").is_file() else "%S/evdev"
        (rules / "evdev").write_text(
            f"! include {upstream}\n" + (rules / "windows-us-intl").read_text())
        cls.lib = ctypes.CDLL("libxkbcommon.so.0")
        pointer = ctypes.c_void_p
        number = ctypes.c_uint32
        signatures = (
            ("xkb_context_new", [ctypes.c_int], pointer),
            ("xkb_context_unref", [pointer], None),
            ("xkb_keymap_new_from_string", [pointer, ctypes.c_char_p, ctypes.c_int, ctypes.c_int], pointer),
            ("xkb_keymap_unref", [pointer], None),
            ("xkb_keymap_key_by_name", [pointer, ctypes.c_char_p], number),
            ("xkb_keymap_mod_get_index", [pointer, ctypes.c_char_p], number),
            ("xkb_state_new", [pointer], pointer),
            ("xkb_state_unref", [pointer], None),
            ("xkb_state_update_mask", [pointer, number, number, number, number, number, number], ctypes.c_int),
            ("xkb_state_key_get_one_sym", [pointer, number], number),
            ("xkb_keysym_from_name", [ctypes.c_char_p, ctypes.c_int], number),
        )
        for name, arguments, result in signatures:
            function = getattr(cls.lib, name)
            function.argtypes = arguments
            function.restype = result

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def compile(self, layout, staged=True, options=""):
        command = ["xkbcli", "compile-keymap"]
        if staged:
            command += ["--include", str(self.directory), "--include-defaults"]
        command += ["--layout", layout, "--options", options]
        return subprocess.run(command, capture_output=True, text=True, check=True).stdout

    def test_plain_us_and_brazilian_maps_are_unchanged(self):
        for layout in ("us", "br"):
            with self.subTest(layout=layout):
                self.assertEqual(self.compile(layout), self.compile(layout, staged=False))

    def test_windows_types_are_loaded_in_each_layout_slot(self):
        for slot in range(4):
            layouts = ["br"] * 4
            layouts[slot] = "us_windows_intl"
            with self.subTest(slot=slot):
                compiled = self.compile(",".join(layouts))
                self.assertIn('type "WINDOWS_US_INTL_SEMIALPHABETIC"', compiled)
                context = self.lib.xkb_context_new(0)
                keymap = self.lib.xkb_keymap_new_from_string(context, compiled.encode(), 1, 0)
                state = self.lib.xkb_state_new(keymap)
                try:
                    altgr = 1 << self.lib.xkb_keymap_mod_get_index(keymap, b"Mod5")
                    lock = 1 << self.lib.xkb_keymap_mod_get_index(keymap, b"Lock")
                    self.lib.xkb_state_update_mask(state, altgr, 0, lock, 0, 0, slot)
                    actual = self.lib.xkb_state_key_get_one_sym(
                        state, self.lib.xkb_keymap_key_by_name(keymap, b"AC02"))
                    self.assertEqual(actual, self.lib.xkb_keysym_from_name(b"ssharp", 0))
                finally:
                    self.lib.xkb_state_unref(state)
                    self.lib.xkb_keymap_unref(keymap)
                    self.lib.xkb_context_unref(context)

    def test_windows_dead_keys_altgr_and_caps_lock(self):
        context = self.lib.xkb_context_new(0)
        keymap = self.lib.xkb_keymap_new_from_string(context, self.compile("us_windows_intl").encode(), 1, 0)
        self.assertTrue(keymap)
        state = self.lib.xkb_state_new(keymap)
        modifiers = {name: 1 << self.lib.xkb_keymap_mod_get_index(keymap, name.encode())
                     for name in ("Shift", "Lock", "Mod5")}
        cases = (
            ("AC11", "", "", "dead_acute"),
            ("AC11", "Shift", "", "dead_diaeresis"),
            ("TLDE", "", "", "dead_grave"),
            ("TLDE", "Shift", "", "dead_tilde"),
            ("AE06", "Shift", "", "dead_circumflex"),
            ("AC11", "Mod5", "", "acute"),
            ("AC11", "Shift+Mod5", "", "diaeresis"),
            ("AD03", "Mod5", "", "eacute"),
            ("AD03", "Shift+Mod5", "", "Eacute"),
            ("AC02", "Mod5", "Lock", "ssharp"),
            ("AC02", "Shift+Mod5", "Lock", "section"),
            ("AB07", "Mod5", "Lock", "mu"),
            ("AB08", "Mod5", "", "ccedilla"),
            ("AB08", "Mod5", "Lock", "Ccedilla"),
            ("AB08", "Shift+Mod5", "Lock", "ccedilla"),
            ("AB08", "", "Lock", "comma"),
            ("AC01", "", "Lock", "A"),
            ("AC01", "Shift", "Lock", "a"),
            ("AE02", "Shift+Mod5", "", "VoidSymbol"),
            ("AC04", "Mod5", "", "VoidSymbol"),
        )
        try:
            for key, pressed, locked, expected in cases:
                with self.subTest(key=key, pressed=pressed, locked=locked):
                    mask = sum(modifiers[name] for name in pressed.split("+") if name)
                    locks = sum(modifiers[name] for name in locked.split("+") if name)
                    self.lib.xkb_state_update_mask(state, mask, 0, locks, 0, 0, 0)
                    actual = self.lib.xkb_state_key_get_one_sym(
                        state, self.lib.xkb_keymap_key_by_name(keymap, key.encode()))
                    self.assertEqual(actual, self.lib.xkb_keysym_from_name(expected.encode(), 0))
        finally:
            self.lib.xkb_state_unref(state)
            self.lib.xkb_keymap_unref(keymap)
            self.lib.xkb_context_unref(context)

    @unittest.skipUnless(Path("/etc/xkb/symbols/omarchy").exists(), "Omarchy is not installed")
    def test_omarchy_compose_option_still_compiles(self):
        self.assertIn("Multi_key", self.compile("us_windows_intl", options="omarchy:shift_caps_compose"))


if __name__ == "__main__":
    unittest.main()
