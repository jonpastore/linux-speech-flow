import os
import subprocess


def get_active_window_info(app_categories: dict | None = None) -> dict:
    """Detect active window and classify app category.

    Returns dict: {
        "window_id": str | None,  # X11 window ID (for --window flag at paste time)
        "title": str,
        "wm_class": str,
        "category": str,          # "terminal", "editor", or "other"
        "session": str,           # "x11" or "wayland"
    }

    On Wayland or detection failure, returns safe defaults with empty strings.
    Capture this at the START of the pipeline (before API calls) to avoid
    focus theft from notifications stealing the window ID.
    """
    session = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
    default = {"window_id": None, "title": "", "wm_class": "", "category": "other", "session": session}

    if session == "wayland":
        return default

    if not os.environ.get("DISPLAY"):
        return default

    try:
        win_id = subprocess.check_output(
            ["xdotool", "getactivewindow"], text=True, timeout=2
        ).strip()
        title = subprocess.check_output(
            ["xdotool", "getwindowname", win_id], text=True, timeout=2
        ).strip()
        xprop_out = subprocess.check_output(
            ["xprop", "-id", win_id, "WM_CLASS"], text=True, timeout=2
        )
        parts = xprop_out.split("=")[-1].strip().strip('"').split('", "')
        wm_class = parts[-1].rstrip('"').lower() if parts else ""
        category = _classify(wm_class, app_categories or {})
        return {"window_id": win_id, "title": title, "wm_class": wm_class, "category": category, "session": session}
    except Exception:
        return default


def _classify(wm_class: str, app_categories: dict) -> str:
    """Map wm_class to a category using the user-configurable app_categories dict."""
    terminals = [t.lower() for t in app_categories.get("terminals", [])]
    editors = [e.lower() for e in app_categories.get("editors", [])]
    wm = wm_class.lower()
    if any(t in wm for t in terminals):
        return "terminal"
    if any(e in wm for e in editors):
        return "editor"
    return "other"
