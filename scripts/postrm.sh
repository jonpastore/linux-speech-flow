#!/bin/sh
# fpm --after-remove: drop the wrapper and refresh the icon cache.
set -e
rm -f /usr/local/bin/linux-speech-flow
gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor 2>/dev/null || true
