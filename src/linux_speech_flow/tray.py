import logging
import importlib.resources
import shutil
import subprocess
from pathlib import Path

import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from trayer import TrayIcon

logger = logging.getLogger(__name__)

RECORDING_FRAMES = ['linux-speech-flow-recording-1', 'linux-speech-flow-recording-2', 'linux-speech-flow-recording-3']
PROCESSING_FRAMES = ['linux-speech-flow-processing-1', 'linux-speech-flow-processing-2', 'linux-speech-flow-processing-3']
RECORDING_INTERVAL_MS = 500
PROCESSING_INTERVAL_MS = 400
CONV_RECORDING_FRAMES = [
    'linux-speech-flow-conv-recording-1',
    'linux-speech-flow-conv-recording-2',
    'linux-speech-flow-conv-recording-3',
]

ICON_NAMES = [
    'linux-speech-flow-idle',
    'linux-speech-flow-recording-1', 'linux-speech-flow-recording-2', 'linux-speech-flow-recording-3',
    'linux-speech-flow-processing-1', 'linux-speech-flow-processing-2', 'linux-speech-flow-processing-3',
    'linux-speech-flow-error',
    'linux-speech-flow-conv-recording-1',
    'linux-speech-flow-conv-recording-2',
    'linux-speech-flow-conv-recording-3',
]


def install_icons():
    dest_dir = Path.home() / '.local' / 'share' / 'icons' / 'hicolor' / 'scalable' / 'status'
    dest_dir.mkdir(parents=True, exist_ok=True)
    old_icon_stems = [
        'freeflow-idle', 'freeflow-error',
        'freeflow-recording-1', 'freeflow-recording-2', 'freeflow-recording-3',
        'freeflow-processing-1', 'freeflow-processing-2', 'freeflow-processing-3',
    ]
    for old_stem in old_icon_stems:
        (dest_dir / f'{old_stem}.svg').unlink(missing_ok=True)
    for name in ICON_NAMES:
        filename = f'{name}.svg'
        ref = importlib.resources.files('linux_speech_flow.icons').joinpath(filename)
        with importlib.resources.as_file(ref) as src:
            dest = dest_dir / filename
            shutil.copy2(src, dest)
            logger.debug('Installed icon: %s', dest)
    hicolor_dir = Path.home() / '.local' / 'share' / 'icons' / 'hicolor'
    try:
        subprocess.run(
            ['gtk-update-icon-cache', '-f', '-t', str(hicolor_dir)],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass


class TrayManager:
    def __init__(self, app, on_settings, on_debug_log, on_reprocess, on_history=None):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        self._reprocess_item = {
            'type': 'item',
            'label': 'Reprocess Failed (0)',
            'callback': on_reprocess,
            'enabled': False,
            'visible': True,
        }
        self._tray = TrayIcon(
            app_id='com.github.linux-speech-flow',
            title='Linux Speech Flow',
            icon_name='linux-speech-flow-idle',
        )
        self._tray.menu_items = [
            {'type': 'item', 'label': 'Transcription History', 'callback': on_history, 'enabled': True, 'visible': True},
            {'type': 'item', 'label': 'Settings', 'callback': on_settings, 'enabled': True, 'visible': True},
            {'type': 'item', 'label': 'Open Debug Log', 'callback': on_debug_log, 'enabled': True, 'visible': True},
            self._reprocess_item,
            {'type': 'item', 'label': 'Quit', 'callback': app.quit, 'enabled': True, 'visible': True},
        ]
        self._tray.set_left_click(on_settings)

        self._anim_source_id = None
        self._anim_frames = []
        self._anim_frame_idx = 0

    def setup(self):
        self._tray.icon_theme_path = str(Path.home() / '.local' / 'share' / 'icons')
        self._tray.setup()

    def set_state(self, state: str):
        if state == 'recording':
            self._start_animation(RECORDING_FRAMES, RECORDING_INTERVAL_MS)
        elif state == 'processing':
            self._start_animation(PROCESSING_FRAMES, PROCESSING_INTERVAL_MS)
        elif state == 'idle':
            self._stop_animation()
            self._tray.change_icon('linux-speech-flow-idle')
        elif state == 'conv_recording':
            self._start_animation(CONV_RECORDING_FRAMES, RECORDING_INTERVAL_MS)
        elif state == 'error':
            self._stop_animation()
            self._tray.change_icon('linux-speech-flow-error')

    def update_failed_count(self, count: int) -> bool:
        self._reprocess_item['label'] = f'Reprocess Failed ({count})'
        self._reprocess_item['enabled'] = count > 0
        self._tray.update_menu()
        return False

    def _start_animation(self, frames, interval_ms):
        self._stop_animation()
        self._anim_frames = frames
        self._anim_frame_idx = 0
        self._tray.change_icon(frames[0])
        self._anim_source_id = GLib.timeout_add(interval_ms, self._advance_frame)

    def _stop_animation(self):
        if self._anim_source_id is not None:
            GLib.source_remove(self._anim_source_id)
            self._anim_source_id = None

    def _advance_frame(self) -> bool:
        self._anim_frame_idx = (self._anim_frame_idx + 1) % len(self._anim_frames)
        self._tray.change_icon(self._anim_frames[self._anim_frame_idx])
        return True
