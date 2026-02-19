import subprocess


def send_notification(
    summary: str,
    body: str = "",
    replace_id: int | None = None,
) -> int | None:
    """Send a desktop notification via notify-send.

    Tries with -p (print-id) first to capture the notification ID for
    replace support. Falls back to running without -p if unsupported
    (libnotify < 0.7.9).

    Args:
        summary: Notification title.
        body: Optional notification body text.
        replace_id: If provided, replaces an existing notification with this ID.

    Returns:
        Notification ID as int, or None if unavailable or -p not supported.
    """
    base = ["notify-send"]
    if replace_id is not None:
        base += ["-r", str(replace_id)]
    if body:
        args = [summary, body]
    else:
        args = [summary]

    try:
        result = subprocess.run(
            base + ["-p"] + args, capture_output=True, text=True, timeout=2
        )
        stripped = result.stdout.strip()
        if result.returncode == 0 and stripped:
            return int(stripped)
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError, OSError):
        return None

    try:
        subprocess.run(base + args, timeout=2)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None
