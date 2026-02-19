import pulsectl


def list_sinks() -> list[dict]:
    """Return available PulseAudio/PipeWire output sinks.

    Returns list of dicts: [{"name": str, "description": str}, ...]
    "name" is the PulseAudio sink name (used as config value).
    "description" is the human-readable label (shown in UI).

    Returns empty list (does not raise) if PulseAudio is unreachable,
    so callers can degrade gracefully (use system default sink).
    """
    try:
        with pulsectl.Pulse("linux-speech-flow") as pulse:
            sinks = pulse.sink_list()
        return [
            {"name": s.name, "description": s.description}
            for s in sinks
        ]
    except pulsectl.PulseError:
        return []


def list_microphones() -> list[dict]:
    """Return available microphone sources, excluding monitor (loopback) sources.

    Returns list of dicts: [{"name": str, "description": str}, ...]
    "name" is the PulseAudio source name (used as config value).
    "description" is the human-readable label (shown in UI).

    Raises pulsectl.PulseError if PulseAudio/PipeWire is unreachable
    (e.g., pipewire-pulse not installed). Callers must handle this.
    """
    with pulsectl.Pulse("linux-speech-flow") as pulse:
        sources = pulse.source_list()
    return [
        {"name": s.name, "description": s.description}
        for s in sources
        if not s.name.endswith(".monitor")
    ]
