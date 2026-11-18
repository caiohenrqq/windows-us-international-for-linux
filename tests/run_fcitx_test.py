import os
from pathlib import Path
import subprocess
import sys
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "tools"))
from install import Locations, install, plan, uninstall


with tempfile.TemporaryDirectory(prefix="windowsintl-fcitx-test-") as temporary:
    root = Path(temporary)
    env = dict(os.environ)
    for variable, directory in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                                ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache")):
        path = root / directory
        path.mkdir()
        env[variable] = str(path)
    config = root / "config/fcitx5"
    config.mkdir()
    (config / "profile").write_text(
        "[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=keyboard-us\n"
        "\n[Groups/0/Items/0]\nName=keyboard-us\n\n[GroupOrder]\n0=Default\n")
    (config / "config").write_text(
        "[Hotkey/AltTriggerKeys]\n\n[Hotkey/TriggerKeys]\n\n[Behavior]\nActiveByDefault=False\n")
    addon = root / "data/fcitx5/addon"
    addon.mkdir(parents=True)
    (addon / "windowsintltest.conf").write_text(
        "[Addon]\nName=Integration tests\nType=SharedLibrary\n"
        f"Library={PROJECT / 'build/libwindowsintltest'}\nCategory=Module\n"
        "OnDemand=False\n\n[Addon/Dependencies]\n0=core:5.1.23\n1=keyboard\n2=windowscompose\n")
    compose = root / "Compose"
    compose.write_text('include "%L"\n'
                       '<Multi_key> <m> <s> : "😄"\n'
                       '<Multi_key> <dead_acute> <e> : "custom"\n')
    original = compose.read_bytes()
    locations = Locations(root, root / "config", root / "data", root / "state", compose)
    installation = plan(locations)
    install(locations, installation)
    env["XCOMPOSEFILE"] = str(compose)
    result = subprocess.run(["fcitx5", "--disable", "all", "--enable",
                             "keyboard,windowscompose,windowsintltest"], env=env,
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    uninstall(locations)
    assert compose.read_bytes() == original
    assert not locations.backup.exists()
    for path in installation.files:
        if path != compose:
            assert not path.exists(), f"Installed file was not removed: {path}"
    print(result.stdout.strip())
    print("Real library installation, isolated loading and complete rollback: OK")
