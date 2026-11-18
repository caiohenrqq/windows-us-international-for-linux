# Windows US-International for Linux

Windows-style **US-International typing** on Linux, using Fcitx5 and XKB.

Fixes unexpected `ć`, `ḿ` and `ś` combinations. Keeps accents, hides the highlighted `´` preview and lets the first arrow key work after a pending accent. Does not add another daemon.

| Type in sequence | Result |
| --- | --- |
| `'` then `e` | é |
| `'` then `c` | ç |
| `'` then `m` | `'m` |
| `'` then `s` | `'s` |
| `~` then `a` | ã |
| `"` then `u` | ü |
| Backtick then `e` | è |
| `'` then Space | `'` |

All five accents remain dead keys. Pressing an accent alone waits for the next key; it does not insert punctuation immediately.

## Requirements

- Linux with XKB and **Fcitx5 5.1.23 or later**, already working in your session.
- A C++20 compiler, Make, pkg-config and Python 3.10 or later.
- libxkbcommon, xkeyboard-config, `xkbcli` and the Fcitx5 development headers.
- For automatic Hyprland configuration: Omarchy with a Lua `~/.config/hypr/input.lua` file.

On Arch Linux, these packages provide the build dependencies:

```sh
sudo pacman -S --needed base-devel pkgconf python fcitx5 libxkbcommon xkeyboard-config
```

Other distributions may package development headers separately, usually in `-dev` or `-devel` packages.

## Install

From the repository directory:

```sh
make
make check
python3 tools/install.py install --hyprland --dry-run
python3 tools/install.py install --hyprland
```

Run the installer **without sudo**. The `--dry-run` option only lists the planned changes.

On Omarchy, activate the installed files:

```sh
omarchy restart xcompose
hyprctl reload
hyprctl configerrors
```

If an older map with the same name remains cached, log out and back in to reload everything. The installer does not close applications or restart services automatically.

### Other compositors

Install without `--hyprland`:

```sh
python3 tools/install.py install
```

Then select the `us_windows_intl` XKB layout in your compositor and restart Fcitx5 using your session's usual method. The installer does not configure input-method integration for applications.

## Use

Type normally. Your Compose key and existing shortcuts, including Omarchy's emoji sequences, remain available.

- Arrow keys, Home, End, Tab, Enter and Escape cancel a pending accent and pass through to the application.
- Backspace cancels a pending accent without deleting the previous character.
- Switching fields or using a shortcut with Ctrl, Alt or Super cancels a pending accent.
- AltGr follows Microsoft's published US-International key levels.

To check the behavior, type into an empty field:

```text
é ç ã õ ê ü
i'm it's don't i'll we'd we're
```

Your browser needs working Fcitx5 integration. Changing the XKB layout alone does not enable it. Chromium versions with working text-input-v3 support do not need to be forced onto XWayland.

## What the installer changes

All files are installed for the current user. The installer:

- Installs the Fcitx5 addon and XKB layout.
- Appends a block to the active Compose file, usually `~/.XCompose`, preserving its existing contents.
- Preserves existing XKB rules and adds the types needed by the layout.
- With `--hyprland`, appends an override to `input.lua` without replacing the file.
- Saves the originals in `~/.local/state/fcitx5-windows-us-intl`.

The installer respects `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME` and `XCOMPOSEFILE`. It also recognizes an existing `$XDG_CONFIG_HOME/XCompose` file. It refuses to overwrite existing addon or layout files and rejects symbolic links.

## Uninstall

From the same repository directory:

```sh
python3 tools/install.py uninstall
omarchy restart xcompose
hyprctl reload
hyprctl configerrors
```

Outside Omarchy, restart Fcitx5 and reload your compositor as usual.

Uninstalling restores the originals and removes added files, newly empty directories and the backup. If any managed file has changed since installation, it stops before restoring any files. Preserve your edits and use the backup to merge them; do not delete the backup to bypass the check.

To update this version, uninstall the previous installation, run `make clean`, rebuild and install again. An earlier manual installation must be removed using its own rollback before using this installer.

An incompatible Fcitx5 update may require rebuilding the addon.

## Known limitations

- The Compose rules and addon apply across the user's `keyboard-*` input methods, rather than being restricted to one layout. Common Brazilian Portuguese input was exercised with the original implementation, but some special combinations follow Windows rules.
- Sequences containing different dead keys still depend on the existing Compose table.
- Arrow-key cancellation was tested on Linux, without a side-by-side comparison with Windows.
- Applications that bypass Fcitx5 or receive keys directly may behave differently.
- Full Windows parity and compatibility with every distribution are not guaranteed.

See [behavior and testing](docs/testing.md) for details. Licensed under [MIT](LICENSE).
