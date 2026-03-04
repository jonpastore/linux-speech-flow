# Phase 9: Packaging & Distribution - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Produce a `.deb` package installable via `apt install ./linux-speech-flow_*.deb` on Ubuntu 22.04+, Debian 12+, Pop!_OS 22.04+, with a bundled Python virtualenv. Also publish a wheel to PyPI so `pip install linux-speech-flow` works for power users. The GitHub Actions CI/CD workflow (already created) handles automated build and publish. This phase implements the packaging scripts, postinst/postrm, setuptools-scm versioning, and README system dep documentation. No new app features.

</domain>

<decisions>
## Implementation Decisions

### .deb build tool
- Use **fpm** (already wired in `.github/workflows/ci.yml`)
- No `debian/` directory — fpm builds from a staging directory with one command
- Staging layout: `/opt/linux-speech-flow/venv/` (bundled virtualenv) + `/usr/local/bin/linux-speech-flow` (wrapper binary)
- `python3 -m venv --copies` so the Python binary is embedded, not symlinked — works across system Python version differences

### venv bundling
- Install path: `/opt/linux-speech-flow/venv/`
- Use `--copies` flag on venv creation so the Python binary is self-contained
- PyGObject must be installed in the venv via `pip install PyGObject` (requires system `libgirepository1.0-dev` at build time only — not at install time)
- fpm `--depends` covers runtime-only system libs: `libpulse0`, `gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1`

### postinst / postrm scripts
- **postinst**: run `gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor` after install
- **postrm**: run `gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor` after removal; remove `/usr/local/bin/linux-speech-flow` wrapper
- **Autostart .desktop is NOT managed by postinst** — the app already writes `~/.config/autostart/linux-speech-flow.desktop` at runtime (Phase 4). postinst does not duplicate this; it is per-user and the app owns it.
- wrapper binary at `/usr/local/bin/linux-speech-flow` is a simple bash script: `exec /opt/linux-speech-flow/venv/bin/linux-speech-flow "$@"`

### PyPI publishing
- Publish the wheel to PyPI on `v*` git tags (already in CI workflow via `pypa/gh-action-pypi-publish` with OIDC trusted publishing — no API token)
- `pip install linux-speech-flow` works for developers/power users; they must install system deps first
- README must list required system deps prominently before the pip install command
- System deps for pip path: `libgirepository1.0-dev gir1.2-gtk-3.0 libpulse-dev xdotool xclip libnotify-bin`

### Version management
- Use **setuptools-scm** — version derived automatically from git tags, no manual `pyproject.toml` edits
- Remove hardcoded `version = "0.1.0"` from `[project]` in `pyproject.toml`
- Add `setuptools-scm` to `[build-system] requires` and `[tool.setuptools_scm]` section
- Release workflow: `git tag v0.2.0 && git push --tags` → CI builds and publishes automatically
- Development installs get version `0.2.0.devN+gABCDEF` from setuptools-scm

### fpm .deb metadata
- Package name: `linux-speech-flow`
- fpm `--depends`: `xdotool`, `xclip`, `libnotify-bin`, `libpulse0`, `gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1`
- fpm `--description`: "Speech-to-text Linux app — hold a key, speak, release, text appears"
- Version read from `git describe --tags --abbrev=0` (or setuptools-scm) in CI step

### Claude's Discretion
- Exact postinst/postrm script style (minimal bash)
- Whether to include an icon installed to `/usr/share/icons/hicolor/` or rely on bundled SVGs only
- Whether `linux-speech-flow.desktop` (app launcher, not autostart) is included in the .deb for application menus
- README formatting — follow existing conventions

</decisions>

<specifics>
## Specific Ideas

- CI workflow `.github/workflows/ci.yml` already created: tests on Python 3.10+3.12, builds .deb + wheel on every push, publishes to GitHub Releases + PyPI on `v*` tags
- The `--copies` flag on venv creation is critical — without it, the symlinked Python binary breaks after install on machines with a different Python version
- PyGObject `pip install PyGObject` at build time requires `libgirepository1.0-dev` on the CI runner — already in the workflow's system deps step

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml`: already has `linux-speech-flow` entry point, setuptools build backend, package-data globs for sounds/*.wav and icons/*.svg — mostly ready, just needs setuptools-scm substituted for hardcoded version
- `.github/workflows/ci.yml`: already created — tests, fpm .deb build, wheel build, GitHub Release + PyPI publish on tags
- XDG autostart: already implemented in `app.py` (Phase 4) — writes `~/.config/autostart/` at runtime, postinst does NOT need to duplicate

### Established Patterns
- System dep try/except pattern: `try: gi.require_version('AppIndicator3') except: gi.require_version('AyatanaAppIndicator3')` — fpm `--depends` should mirror this with `|` alternative
- Per-call pulsectl connection pattern — no daemon threads holding PulseAudio open, safe for venv install

### Integration Points
- `pyproject.toml` → needs setuptools-scm version config
- `.github/workflows/ci.yml` → needs `build-deb.sh` script or inline fpm command (already inlined)
- `README.md` → needs system dep documentation added

</code_context>

<deferred>
## Deferred Ideas

- Wayland support (.deb for Wayland text injection) — v2 requirement, out of scope for Phase 9
- Snap/Flatpak packaging — not in requirements; would need sandboxing investigation
- Auto-update mechanism — explicitly out of scope (REQUIREMENTS.md)
- `.desktop` app launcher entry (application menu) — not required by DIST-01–05; can add if trivial during implementation

</deferred>

---

*Phase: 09-packaging-and-distribution*
*Context gathered: 2026-03-04*
