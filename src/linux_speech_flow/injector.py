import logging
import os
import subprocess
import time

logger = logging.getLogger(__name__)


def paste_text(text: str, window_info: dict) -> None:
    """Write text to clipboard and send paste keystroke to the target window.

    On Wayland: writes to wl-copy clipboard, sends notification to paste manually
    (ydotoold daemon not required). On X11: xclip writes clipboard, xdotool sends
    keystroke to the captured window_id (not current focus -- avoids focus-theft bugs).

    The window_id in window_info must be captured BEFORE API calls start.
    """
    session = window_info.get("session", "x11")
    if session == "wayland":
        _wayland_paste(text)
        return

    _x11_paste(text, window_info)


def _x11_paste(text: str, window_info: dict) -> None:
    logger.info("_x11_paste called DISPLAY=%r", os.environ.get("DISPLAY"))

    display = os.environ.get("DISPLAY")
    if not display:
        logger.warning("no DISPLAY env var — cannot paste on X11")
        return

    # Write to CLIPBOARD (ctrl+v in most apps) and PRIMARY (shift+Insert / middle-click).
    # Do NOT use communicate() — xclip forks a background server that keeps the pipe
    # open indefinitely, causing communicate() to block until another app claims it.
    for selection in ("clipboard", "primary"):
        proc = subprocess.Popen(
            ["xclip", "-selection", selection],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
    time.sleep(0.05)

    window_id = window_info.get("window_id")
    category = window_info.get("category", "other")
    wm_class = window_info.get("wm_class", "")
    is_vim = "vim" in wm_class

    logger.info(
        "paste: window_id=%s category=%s wm_class=%s is_vim=%s text_len=%d",
        window_id, category, wm_class, is_vim, len(text),
    )

    # Activate the target window first (makes GTK4 apps accept synthetic keystrokes;
    # xdotool key --window uses XSendEvent which GTK4 rejects for security).
    if window_id:
        activate = subprocess.run(
            ["xdotool", "windowactivate", "--sync", window_id],
            check=False, capture_output=True, text=True, timeout=3,
        )
        logger.info("windowactivate rc=%d %s", activate.returncode, activate.stderr.strip())
        time.sleep(0.05)

    if is_vim:
        # gvim insert mode: F9 keypresses leaked through pynput as literal '<F9>'
        # text (5 chars each). Delete them before pasting.
        leaked = window_info.get("leaked_f9_count", 1)
        backspace_count = leaked * 4  # <F9> is 4 chars: <, F, 9, >
        logger.info("vim: deleting %d chars (%d leaked F9s) then shift+Insert", backspace_count, leaked)
        if backspace_count:
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers",
                 "--repeat", str(backspace_count), "--repeat-delay", "10", "BackSpace"],
                check=False, capture_output=True, text=True, timeout=5,
            )
            time.sleep(0.05)
        # shift+Insert pastes from PRIMARY selection in vim/gvim.
        result = subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "shift+Insert"],
            check=False, capture_output=True, text=True, timeout=3,
        )
    elif category == "terminal":
        result = subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+shift+v"],
            check=False, capture_output=True, text=True, timeout=3,
        )
    else:
        result = subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
            check=False, capture_output=True, text=True, timeout=3,
        )

    if result.returncode != 0:
        logger.warning("xdotool key returned %d: %s", result.returncode, result.stderr.strip())
    else:
        logger.info("paste complete")


def copy_to_clipboard(text: str) -> None:
    """Write text to clipboard only — no paste keystroke.

    X11: xclip writes both CLIPBOARD and PRIMARY selections.
    Wayland: wl-copy writes the clipboard.
    """
    session = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
    if session == "wayland":
        try:
            proc = subprocess.Popen(
                ["wl-copy"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            proc.communicate(text.encode("utf-8"))
        except FileNotFoundError:
            logger.warning("wl-copy not found; clipboard copy failed")
        return

    for selection in ("clipboard", "primary"):
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", selection],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            proc.stdin.write(text.encode("utf-8"))
            proc.stdin.close()
        except FileNotFoundError:
            logger.warning("xclip not found; clipboard copy failed")
            break
    logger.info("transcript copied to clipboard (%d chars)", len(text))


def _wayland_paste(text: str) -> None:
    try:
        proc = subprocess.Popen(
            ["wl-copy"],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate(text.encode("utf-8"))
    except FileNotFoundError:
        pass
