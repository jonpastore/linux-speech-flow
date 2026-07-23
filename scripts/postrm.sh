#!/bin/sh
# fpm --after-remove: refresh the icon cache.
# NOTE: the /usr/local/bin/linux-speech-flow wrapper is packaged and owned by
# dpkg, so dpkg removes it on uninstall. Do NOT rm it here — on an *upgrade*
# dpkg runs the OLD package's postrm after unpacking the NEW files, so removing
# it would delete the freshly-installed wrapper.
set -e
gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor 2>/dev/null || true
