#!/bin/sh
# fpm --after-install: refresh the icon cache so the app icon appears.
set -e
gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor 2>/dev/null || true
