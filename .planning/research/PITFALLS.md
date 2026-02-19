# Domain Pitfalls

**Domain:** Python Linux voice dictation app (system tray, .deb packaging)
**Researched:** 2026-02-18

---

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

---

### Pitfall 1: GNOME System Tray Is Not a Real System Tray

**What goes wrong:** GNOME removed the legacy system tray in GNOME Shell 3.26. There is no built-in AppIndicator/StatusNotifierItem support. Your tray icon simply does not appear on a stock GNOME installation -- including Pop!_OS and Ubuntu unless the user has manually installed and enabled the `gnome-shell-extension-appindicator` extension.

**Why it happens:** GNOME upstream considers system tray icons an anti-pattern and removed native support. Ubuntu and Pop!_OS ship the extension as a package (`gnome-shell-extension-appindicator`) but it is NOT enabled by default on all configurations. Pop!_OS requires manual install via `sudo apt install gnome-shell-extension-appindicator` and then enabling it in Extensions or GNOME Tweaks.

**Consequences:**
- App appears to not launch at all (no visible UI, no tray icon).
- Users file "app doesn't work" bugs that are actually a missing GNOME extension.
- GNOME 48 (shipping in 2025 distro updates) broke the extension entirely until version 59-3+ was released with compatibility fixes. Each major GNOME release risks breaking the extension again.

**Prevention:**
1. **Declare the dependency.** The .deb package MUST `Depends:` on `gnome-shell-extension-appindicator` and `gir1.2-ayatanaappindicator3-0.1` (or `gir1.2-appindicator3-0.1`).
2. **Handle both AppIndicator libraries.** Use a try/except import pattern:
   ```python
   import gi
   try:
       gi.require_version('AppIndicator3', '0.1')
       from gi.repository import AppIndicator3 as appindicator
   except (ValueError, ImportError):
       gi.require_version('AyatanaAppIndicator3', '0.1')
       from gi.repository import AyatanaAppIndicator3 as appindicator
   ```
   `AppIndicator3` is the old Canonical library (unmaintained for 8+ years). `AyatanaAppIndicator3` is the active fork. Different distro versions ship different ones.
3. **Detect missing extension at startup.** Check if the extension is enabled via `gnome-extensions list --enabled` and show a helpful dialog if missing, not a silent failure.
4. **Provide a fallback.** Consider also showing a regular GTK window that can be toggled, so the app is usable even without the tray extension.

**Detection:** Test on a fresh Pop!_OS/Ubuntu install without manually installing extensions. If you only test on a dev machine with extensions pre-installed, you will miss this.

**Phase:** Must be addressed in Phase 1 (system tray MVP). This is the #1 "app doesn't work" report waiting to happen.

**Confidence:** HIGH -- verified via System76 official docs, GNOME extension repo, Ubuntu Launchpad, and multiple GitHub issues.

---

### Pitfall 2: xdotool Text Injection Breaks on Unicode, Non-ASCII, and Special Characters

**What goes wrong:** `xdotool type` uses an internal character-to-keysym mapping. Characters outside basic ASCII fail in multiple ways: "Invalid multi-byte sequence encountered" errors, wrong characters output (`:` becomes `Q`), X server freezes on characters like `a-umlaut`, and complete crashes with accented characters in Spanish/French/Italian text.

**Why it happens:** xdotool maps characters to X11 keysyms, but X11 does not have keysyms for every Unicode character. The mapping depends on the current keyboard layout (`setxkbmap`), locale settings (`LANG`), and the target application's input handling. Non-English keyboard layouts are particularly broken. Firefox requires 500-700ms delays per character for Unicode to work at all.

**Consequences:**
- Dictated text containing any non-ASCII character (accents, umlauts, emoji, curly quotes, en-dashes) gets mangled or crashes the injection.
- Users with non-English keyboard layouts get random wrong characters.
- Performance is terrible: inserting characters like `a-umlaut` is orders of magnitude slower than ASCII and can freeze the display.

**Prevention:**
1. **Use clipboard-based injection instead of `xdotool type`.** The proven pattern is:
   ```bash
   # Save current clipboard
   old_clipboard=$(xclip -selection clipboard -o 2>/dev/null)
   # Set new text
   echo -n "$text" | xclip -selection clipboard
   # Paste via Ctrl+V
   xdotool key --clearmodifiers ctrl+v
   # Restore clipboard after delay
   sleep 0.3
   echo -n "$old_clipboard" | xclip -selection clipboard
   ```
2. **Always use `--clearmodifiers` flag.** Without it, if the user just released a hotkey, modifier keys may still be "held" and produce garbage.
3. **Use `--delay` between keystrokes** if you must use `type` for any reason (25-50ms minimum).
4. **Restore clipboard after paste.** But beware the race condition: if you restore too fast (< 300ms), the target app may not have finished processing the paste and you clobber the text. The OpenWhispr project found 200ms was too fast on Wayland.

**Detection:** Test with text containing: `e-acute`, `n-tilde`, curly quotes `""`, em-dash `--`, and emoji. Test with non-US keyboard layouts.

**Phase:** Must be addressed in Phase 1 (text injection). Using `xdotool type` for anything beyond proof-of-concept is a dead end. Start with clipboard paste from day one.

**Confidence:** HIGH -- confirmed via xdotool GitHub issues #154, #43, #49, #10, #97, nerd-dictation issue #43, and the OpenWhispr project.

---

### Pitfall 3: PortAudio/sounddevice Cannot See PulseAudio or PipeWire Devices on Debian/Ubuntu

**What goes wrong:** `sounddevice.query_devices()` returns empty or only shows raw ALSA devices. Bluetooth audio devices, USB microphones connected via PulseAudio/PipeWire, and the default system microphone may all be invisible. Recording fails or captures from the wrong device.

**Why it happens:** Debian (through Trixie/13) and Ubuntu ship PortAudio 19.6.0 from 2016. PulseAudio and PipeWire hostapi support was only added in PortAudio 19.7.0 (April 2021). Even 19.7.0 lacks full PipeWire support -- only unreleased PortAudio git builds have it. The system `libportaudio2` package is years behind, and pip-installed sounddevice may use its own bundled PortAudio that also lacks these backends.

**Consequences:**
- App cannot find the microphone on a stock Debian/Ubuntu system.
- Works on dev machine (maybe compiled PortAudio from source) but fails on user machines.
- Bluetooth headset microphones invisible even though they work in other apps.

**Prevention:**
1. **Do NOT use sounddevice/PyAudio for recording.** Use `pasimple` (PulseAudio Simple API wrapper) instead. It talks directly to PulseAudio/PipeWire without going through PortAudio, so it works on every modern Linux distro regardless of libportaudio2 version.
2. **Alternatively, use GStreamer** via `gi.repository.Gst` which handles PulseAudio/PipeWire natively and is already installed on GNOME systems.
3. **If you must use sounddevice**, the .deb package must bundle a newer PortAudio built from source, which massively complicates packaging.
4. **Test device enumeration on stock Ubuntu/Debian** before committing to an audio library.

**Detection:** Run `python3 -c "import sounddevice; print(sounddevice.query_devices())"` on a stock Ubuntu 24.04 system. If it shows no PulseAudio devices, you have this problem.

**Phase:** Must be addressed in Phase 1 (audio recording). Wrong library choice here causes a rewrite later.

**Confidence:** HIGH -- confirmed via python-sounddevice issue #609, PortAudio release notes, Debian package tracker.

---

### Pitfall 4: Python .deb Packaging and PEP 668 Externally Managed Environment

**What goes wrong:** Modern Debian 12+, Ubuntu 24.04+, and Pop!_OS enforce PEP 668 which marks the system Python as "externally managed." You cannot `pip install` into system Python. A .deb package that tries to install Python dependencies alongside system Python packages creates conflicts, or the package uses `--break-system-packages` which can corrupt the system Python.

**Why it happens:** PEP 668 was adopted to prevent pip from breaking OS package manager-installed Python packages. Debian/Ubuntu now place an `EXTERNALLY-MANAGED` marker in the system Python. Traditional Debian Python packaging (pybuild) only works for packages that use system-packaged dependencies. If your app depends on PyPI packages not in Debian repos (like `groq`, `pasimple`, etc.), pybuild cannot help.

**Consequences:**
- Package installs but app crashes because dependencies are missing.
- Package installation breaks system Python packages.
- Users cannot install via `pip install` without `--break-system-packages`.
- Traditional `stdeb` approach fails for apps with PyPI-only dependencies.

**Prevention:**
1. **Use dh-virtualenv (Spotify's tool)** to bundle a complete virtualenv inside the .deb package. It installs to `/opt/venvs/freeflow/` with all dependencies isolated from system Python. This is the proven approach used by Spotify, Sentry, and other production Python apps on Debian.
2. **Alternative: Use fpm with virtualenv source type** to create the .deb. fpm can bundle the virtualenv into `/opt/freeflow/` with a wrapper script in `/usr/bin/`.
3. **Declare system-level dependencies** (`gir1.2-ayatanaappindicator3-0.1`, `xdotool`, `xclip`, `libportaudio2`) as `Depends:` in the .deb control file so apt installs them.
4. **Never depend on pip being available** on the target system. The .deb must be fully self-contained.
5. **Pin the Python version** your venv was built against and add a `Depends:` on that exact `python3.X` package.

**Detection:** Try installing your .deb on a fresh Ubuntu 24.04 with no pip or virtualenv pre-installed. If the app fails to start, you have this problem.

**Phase:** Phase 2 (packaging). But the architecture decision (bundled venv vs system packages) must be made in Phase 1 because it affects how you structure imports and dependencies.

**Confidence:** HIGH -- PEP 668 is official Python policy, enforced in current Debian/Ubuntu releases. dh-virtualenv is documented by Spotify.

---

## Moderate Pitfalls

---

### Pitfall 5: Global Hotkey (F9) Grab Conflicts and Permissions on X11

**What goes wrong:** X11 global hotkeys use `XGrabKey` which is exclusive -- only one application can grab a given key combination. If another app (media player, accessibility tool, DE shortcut) already grabbed F9 or the chosen key, your grab fails with `BadAccess` error. pynput's `GlobalHotKeys` uses this mechanism and will silently fail or raise errors.

**Why it happens:** X11 key grabs are first-come-first-served at the X server level. GNOME Shell may grab function keys for its own shortcuts. Some laptop vendors map function keys to hardware controls (brightness, volume) making them unavailable for grabs.

**Prevention:**
1. **Use `evdev` for hotkey detection** instead of pynput's X11 backend. evdev reads `/dev/input/event*` at the kernel level, before X11 sees the events. This avoids grab conflicts entirely.
2. **If using evdev, handle permissions.** The user must be in the `input` group or you must ship a udev rule:
   ```
   # /etc/udev/rules.d/99-freeflow-input.rules
   KERNEL=="event*", SUBSYSTEM=="input", MODE="0660", GROUP="input"
   ```
   The .deb postinst script should add the user to the `input` group.
3. **Make the hotkey configurable.** F9 is arbitrary -- let users pick a different key if F9 conflicts.
4. **Detect grab failure gracefully.** If using pynput and the grab fails, show a clear error explaining which key failed and why, rather than silently not working.
5. **Use `--clearmodifiers` equivalent** when the hotkey triggers text injection, to avoid modifier key bleed-through.

**Detection:** Test with GNOME's built-in keyboard shortcuts panel open. Test on a laptop where F9 might be a hardware function key requiring Fn modifier.

**Phase:** Phase 1 (hotkey system). Architecture choice between pynput vs evdev must be made early.

**Confidence:** MEDIUM -- X11 XGrabKey behavior is well-documented in X.Org man pages. evdev permissions documented in Arch Wiki and multiple forums. Specific F9 conflicts are speculative (depends on user's DE configuration).

---

### Pitfall 6: Clipboard Restore Race Condition During Text Injection

**What goes wrong:** The clipboard-paste approach (save clipboard -> set text -> Ctrl+V -> restore clipboard) has a race condition. If the clipboard is restored before the target application finishes processing the paste event, the pasted text disappears or gets replaced with the old clipboard content. The OpenWhispr project documented this: "200ms restore delay was too fast, text flashes briefly then disappears."

**Why it happens:** Paste is asynchronous. `xdotool key ctrl+v` sends the key event and returns immediately. The target app then requests clipboard contents via X11 selection protocol, which takes variable time depending on app complexity, system load, and whether the app is X11-native or XWayland.

**Prevention:**
1. **Use a generous restore delay.** 500ms minimum, 1000ms for safety. OpenWhispr settled on a custom binary to avoid this entirely.
2. **Consider NOT restoring the clipboard.** Many dictation tools (including macOS's) simply leave the dictated text on the clipboard. Users expect this.
3. **If restoring, use X11 selection events** to detect when the target app has actually read the clipboard, rather than using a fixed timer.
4. **Ensure `--clearmodifiers` is used** on the `xdotool key ctrl+v` call so held modifier keys from the hotkey release don't interfere.

**Detection:** Test with Firefox (slowest to process paste), LibreOffice, and a terminal emulator. Paste a long string (1000+ chars). If the text appears then vanishes, your restore timing is too aggressive.

**Phase:** Phase 1 (text injection). Must be tested with real-world apps.

**Confidence:** HIGH -- documented in OpenWhispr issue #240 with reproduction steps and timing measurements.

---

### Pitfall 7: systemd User Service Missing DISPLAY, DBUS, and XDG Environment

**What goes wrong:** If FreeFlow is set up as a systemd user service (for autostart), it cannot access the X11 display, D-Bus session bus, or GNOME Shell extensions because systemd user services do not inherit desktop session environment variables (`DISPLAY`, `DBUS_SESSION_BUS_ADDRESS`, `XAUTHORITY`, `XDG_RUNTIME_DIR`).

**Why it happens:** systemd's user manager starts before the graphical session. Environment variables set by the display manager (GDM, etc.) are not propagated to systemd's activation environment unless explicitly imported.

**Prevention:**
1. **Do NOT use a systemd user service for autostart.** Use a `.desktop` file in `~/.config/autostart/` instead. This is the correct GNOME/freedesktop way to autostart GUI applications, and it inherits all session environment variables automatically.
2. **If you must use systemd,** the service file needs:
   ```ini
   [Service]
   Environment=DISPLAY=:0
   # Or better:
   ExecStartPre=/bin/bash -c 'systemctl --user import-environment DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR'
   ```
   But this is fragile -- DISPLAY is not always `:0`.
3. **Ship a .desktop file in the .deb package** installed to `/usr/share/applications/` for the app launcher and a separate copy to `/etc/xdg/autostart/` for autostart.

**Detection:** Enable the systemd service, reboot, check if the tray icon appears. If it does not, check `journalctl --user -u freeflow` for "Cannot open display" or "Failed to connect to D-Bus" errors.

**Phase:** Phase 2 (packaging/autostart). Use .desktop files, not systemd.

**Confidence:** HIGH -- well-documented in Arch Wiki, systemd GitHub issues, and multiple forums.

---

### Pitfall 8: Screenshot Capture Fails on Wayland or Requires User Confirmation

**What goes wrong:** X11 screenshot tools (`scrot`, `maim`, `import`) produce black images on Wayland. Even on X11, taking a screenshot immediately after a window focus change may capture the wrong window or a partially-rendered frame. On GNOME Wayland, the `xdg-desktop-portal` Screenshot API requires an interactive user confirmation dialog for each screenshot.

**Why it happens:** Wayland's security model prevents applications from reading other windows' pixels. The portal API is designed to require user consent. On X11, window compositing introduces timing between focus change and pixel readback.

**Prevention:**
1. **Use the xdg-desktop-portal Screenshot D-Bus API.** It works on both X11 and Wayland, in both sandboxed and unsandboxed environments:
   ```
   org.freedesktop.portal.Screenshot.Screenshot()
   ```
   However, on GNOME it shows a confirmation dialog. If you need non-interactive screenshots, this is a problem.
2. **On X11, add a delay** (200-500ms) after window focus change before taking a screenshot with `maim` or `scrot`.
3. **For non-interactive screenshots on X11,** use `maim` directly (no user confirmation needed on X11).
4. **Accept the limitation on Wayland.** Non-interactive screenshot capture is intentionally blocked by Wayland's security model. Consider whether the screenshot feature is essential to MVP or can be deferred.
5. **Depend on `maim` or `gnome-screenshot`** in the .deb package rather than bundling Python screenshot libraries.

**Detection:** Test on GNOME with Wayland session (default on Ubuntu 22.04+). If a dialog pops up asking for permission each time, the xdg-portal is working but may be too disruptive for the workflow.

**Phase:** Phase 2 or later (screenshot is likely not MVP for voice dictation). The X11 path is straightforward; Wayland requires architectural compromise.

**Confidence:** MEDIUM -- X11 behavior well-documented. Wayland portal behavior confirmed via GNOME Discourse and Arch Wiki. Whether GNOME allows non-interactive portal screenshots in future versions is unknown.

---

## Minor Pitfalls

---

### Pitfall 9: Audio Permissions in .deb Packaged Apps

**What goes wrong:** The app cannot access the microphone because PulseAudio/PipeWire denies access, or the user is not in the `audio` group.

**Prevention:**
1. **PulseAudio/PipeWire handles per-user audio access automatically** for logged-in desktop users. You do NOT need the `audio` group for normal desktop use. The `audio` group grants direct ALSA access and is actually discouraged for desktop users.
2. **If using the PulseAudio Simple API (pasimple)**, access is controlled by the PulseAudio server which runs per-user. No special permissions needed for the logged-in user.
3. **AppArmor profiles** (default on Ubuntu) can block audio access. If shipping an AppArmor profile with the .deb, include the `abstractions/audio` abstraction.
4. **Test in a fresh user account** on the target distro, not just the developer account.

**Detection:** `pactl info` succeeds as the target user. `pactl list sources short` shows microphone devices.

**Phase:** Phase 1 (audio recording). Usually a non-issue if using PulseAudio API correctly, but must be verified on target distros.

**Confidence:** MEDIUM -- PulseAudio per-user behavior is documented in Ubuntu Wiki. AppArmor interaction is less well-documented for custom apps.

---

### Pitfall 10: Fn Key vs Function Key on Laptops

**What goes wrong:** On many laptops, F9 is mapped as a secondary function requiring the `Fn` key to be held. The primary action of the F9 physical key might be "increase brightness" or "toggle display". The kernel sends a different keycode for the media function than for F9.

**Prevention:**
1. **Detect what keycode the key actually sends** at the evdev level. The user may think they're pressing F9 but the kernel sees `KEY_BRIGHTNESSUP`.
2. **Provide a key configuration UI** or first-run "press your hotkey" dialog.
3. **Document the Fn lock** (most laptops have Fn+Esc or a BIOS setting to swap function key behavior).

**Detection:** Test on a laptop with media keys as primary function key behavior.

**Phase:** Phase 1 (hotkey). Low effort to handle if planned for.

**Confidence:** MEDIUM -- based on general Linux laptop experience. Specific keycode mapping varies by vendor.

---

### Pitfall 11: xdotool Does Not Work in Terminal Emulators for Ctrl+V

**What goes wrong:** Terminal emulators use Ctrl+Shift+V for paste, not Ctrl+V. If the user is dictating into a terminal, `xdotool key ctrl+v` sends a literal `^V` (ASCII 22) instead of pasting.

**Prevention:**
1. **Detect the active window class** using `xdotool getactivewindow getwindowclassname`. If it matches known terminal emulators (`gnome-terminal`, `kitty`, `alacritty`, `xterm`, etc.), use `Ctrl+Shift+V` instead.
2. **Alternative: use `xdotool key shift+Insert`** which works as paste in both terminals and GUI apps on X11.
3. **Consider making the paste method configurable** (Ctrl+V, Ctrl+Shift+V, Shift+Insert, middle-click).

**Detection:** Test by dictating text while a terminal emulator is focused.

**Phase:** Phase 1 (text injection). Easy to handle if you detect window class.

**Confidence:** HIGH -- terminal paste behavior is universal and well-known.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| System tray | AppIndicator not available on stock GNOME (Pitfall 1) | Depend on extension package, detect at startup, fallback UI |
| Audio recording | sounddevice/PortAudio cannot see PulseAudio devices (Pitfall 3) | Use pasimple or GStreamer instead of sounddevice |
| Text injection | xdotool type breaks on Unicode (Pitfall 2) | Use clipboard paste from day one, never xdotool type |
| Text injection | Clipboard restore race condition (Pitfall 6) | 500ms+ delay or don't restore |
| Text injection | Terminal emulators need different paste key (Pitfall 11) | Detect window class, adjust paste shortcut |
| Global hotkey | F9 grab conflict or Fn key issue (Pitfalls 5, 10) | Use evdev, make key configurable |
| Packaging | PEP 668 blocks pip install on system Python (Pitfall 4) | Use dh-virtualenv to bundle venv in .deb |
| Autostart | systemd user service lacks display environment (Pitfall 7) | Use .desktop autostart file, not systemd |
| Screenshot | Wayland blocks non-interactive capture (Pitfall 8) | Use xdg-portal, accept dialog on Wayland, defer from MVP |
| Audio permissions | Usually fine but verify on fresh install (Pitfall 9) | Use PulseAudio API, test on fresh user |

---

## Architecture Decisions Forced by Pitfalls

These pitfalls collectively force specific architectural choices that must be made before writing code:

1. **Audio library:** pasimple (or GStreamer), NOT sounddevice/PyAudio
2. **Text injection:** Clipboard paste via xclip + xdotool key, NOT xdotool type
3. **Hotkey mechanism:** evdev (or pynput with graceful fallback), with configurable key
4. **Packaging:** dh-virtualenv or fpm bundled venv, NOT system pip install
5. **Tray library:** PyGObject with AppIndicator3/AyatanaAppIndicator3 try/except pattern
6. **Autostart:** .desktop file in /etc/xdg/autostart/, NOT systemd user service

---

## Sources

### GNOME System Tray / AppIndicator
- [System76 Pop!_OS Status Icons Guide](https://support.system76.com/articles/status-icons/) -- MEDIUM confidence
- [gnome-shell-extension-appindicator GitHub](https://github.com/ubuntu/gnome-shell-extension-appindicator) -- HIGH confidence
- [GNOME 48 compatibility issue #573](https://github.com/ubuntu/gnome-shell-extension-appindicator/issues/573) -- HIGH confidence
- [pystray AppIndicator3/AyatanaAppIndicator3 pattern](https://github.com/moses-palmer/pystray/blob/master/lib/pystray/_appindicator.py) -- HIGH confidence
- [libayatana-appindicator GitHub (OBSOLETE notice)](https://github.com/AyatanaIndicators/libayatana-appindicator) -- HIGH confidence

### xdotool Text Injection
- [xdotool Unicode issue #154](https://github.com/jordansissel/xdotool/issues/154) -- HIGH confidence
- [nerd-dictation special characters issue #43](https://github.com/ideasman42/nerd-dictation/issues/43) -- HIGH confidence
- [xdotool wrong characters issue #49](https://github.com/jordansissel/xdotool/issues/49) -- HIGH confidence
- [xdotool X server freeze issue #10](https://github.com/jordansissel/xdotool/issues/10) -- HIGH confidence
- [OpenWhispr clipboard race condition #240](https://github.com/OpenWhispr/openwhispr/issues/240) -- HIGH confidence

### Audio Capture
- [python-sounddevice PipeWire issue #609](https://github.com/spatialaudio/python-sounddevice/issues/609) -- HIGH confidence
- [pasimple PulseAudio Simple API wrapper](https://github.com/henrikschnor/pasimple) -- MEDIUM confidence
- [PipeWire ArchWiki](https://wiki.archlinux.org/title/PipeWire) -- HIGH confidence

### Python .deb Packaging
- [PEP 668 specification](https://peps.python.org/pep-0668/) -- HIGH confidence
- [dh-virtualenv by Spotify](https://github.com/spotify/dh-virtualenv) -- HIGH confidence
- [Debian Python/Pybuild Wiki](https://wiki.debian.org/Python/Pybuild) -- HIGH confidence
- [fpm virtualenv documentation](https://fpm.readthedocs.io/en/v1.9.3/source/virtualenv.html) -- MEDIUM confidence

### Global Hotkeys
- [pynput documentation](https://pynput.readthedocs.io/en/latest/keyboard.html) -- HIGH confidence
- [XGrabKey man page](https://www.x.org/releases/X11R7.5/doc/man/man3/XGrabKey.3.html) -- HIGH confidence
- [evdev permissions ArchWiki](https://bbs.archlinux.org/viewtopic.php?id=273094) -- MEDIUM confidence

### systemd / Autostart
- [dbus-update-activation-environment](https://dbus.freedesktop.org/doc/dbus-update-activation-environment.1.html) -- HIGH confidence
- [systemd DBUS_SESSION_BUS_ADDRESS issue #1600](https://github.com/systemd/systemd/issues/1600) -- HIGH confidence

### Screenshots
- [xdg-desktop-portal ArchWiki](https://wiki.archlinux.org/title/XDG_Desktop_Portal) -- HIGH confidence
- [Wayland screenshot tools broken - freedesktop bug #98672](https://bugs.freedesktop.org/show_bug.cgi?id=98672) -- HIGH confidence
