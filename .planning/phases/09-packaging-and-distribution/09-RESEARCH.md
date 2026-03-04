# Phase 9: Packaging & Distribution - Research

**Researched:** 2026-03-04
**Domain:** Python .deb packaging (fpm + bundled venv), setuptools-scm, PyPI trusted publishing
**Confidence:** HIGH (all critical decisions verified against official docs and multiple sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use **fpm** for .deb building (already wired in `.github/workflows/ci.yml`)
- No `debian/` directory — fpm builds from a staging directory with one command
- Staging layout: `/opt/linux-speech-flow/venv/` (bundled virtualenv) + `/usr/local/bin/linux-speech-flow` (wrapper binary)
- `python3 -m venv --copies` so the Python binary is embedded, not symlinked
- PyGObject installed in venv via `pip install PyGObject` (requires system `libgirepository1.0-dev` at build time only)
- fpm `--depends` covers runtime-only system libs: `libpulse0`, `gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1`
- **postinst**: run `gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor` after install
- **postrm**: run `gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor` after removal; remove `/usr/local/bin/linux-speech-flow`
- **Autostart .desktop is NOT managed by postinst** — app writes `~/.config/autostart/linux-speech-flow.desktop` at runtime
- Wrapper binary at `/usr/local/bin/linux-speech-flow`: `exec /opt/linux-speech-flow/venv/bin/linux-speech-flow "$@"`
- Use **setuptools-scm** — version derived from git tags, no manual `pyproject.toml` edits
- Remove hardcoded `version = "0.1.0"` from `[project]`, add `dynamic = ["version"]`
- Add `setuptools-scm` to `[build-system] requires` and `[tool.setuptools_scm]` section
- Publish wheel to PyPI via `pypa/gh-action-pypi-publish` with OIDC trusted publishing (already in CI)
- Package name: `linux-speech-flow`
- fpm `--depends`: `xdotool`, `xclip`, `libnotify-bin`, `libpulse0`, `gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1`

### Claude's Discretion
- Exact postinst/postrm script style (minimal bash)
- Whether to include an icon installed to `/usr/share/icons/hicolor/` or rely on bundled SVGs only
- Whether `linux-speech-flow.desktop` (app launcher, not autostart) is included in the .deb for application menus
- README formatting — follow existing conventions

### Deferred Ideas (OUT OF SCOPE)
- Wayland support — v2 requirement
- Snap/Flatpak packaging
- Auto-update mechanism
- `.desktop` app launcher entry (application menu) — not required by DIST-01–05; can add if trivial
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DIST-01 | App packaged as .deb installable via `apt install ./linux-speech-flow_*.deb` on Ubuntu 22.04+, Debian 12+, Pop!_OS 22.04+ | fpm dir→deb workflow; staging layout; postinst/postrm scripts |
| DIST-02 | .deb bundles Python virtualenv to avoid PEP 668 system Python conflicts | `python3 -m venv --copies`; pip install into staging venv; PyGObject pip-installed at build time |
| DIST-03 | .deb postinst installs XDG autostart .desktop entry for launch at login | CONTEXT decision: postinst does NOT handle autostart — app.py already does this at runtime. postinst only runs gtk-update-icon-cache |
| DIST-04 | App installable via pip from PyPI (`pip install linux-speech-flow`) | setuptools-scm versioning; `python -m build --wheel`; pypa/gh-action-pypi-publish OIDC |
| DIST-05 | README documents required system dependencies | System dep list for pip path vs .deb path; libgirepository1.0-dev required for pip-path build |
</phase_requirements>

---

## Summary

This phase produces two artifacts: a `.deb` package (bundled venv via fpm) and a PyPI wheel. The CI workflow in `.github/workflows/ci.yml` already exists and handles both. The implementation work is: (1) update `pyproject.toml` to use setuptools-scm instead of hardcoded version, (2) write `scripts/postinst.sh` and `scripts/postrm.sh`, (3) update the CI workflow to use setuptools-scm for version extraction rather than tomllib, (4) configure PyPI trusted publishing on pypi.org, and (5) update README with system dep documentation.

The critical technical risk is PyGObject version compatibility: PyGObject >= 3.51.0 requires `libgirepository-2.0-dev` which is NOT available on Ubuntu 22.04 (only on 24.04+). The CI runner is `ubuntu-24.04` which will pull PyGObject 3.56.0, but Ubuntu 22.04 target machines run Python 3.10 and need PyGObject <= 3.50.x built against `libgirepository1.0-dev`. This means pinning `PyGObject<3.51` in the bundled venv pip install command, OR building the .deb on Ubuntu 22.04 (not 24.04). The CI currently uses ubuntu-24.04 — this is a build-time problem because the venv is created on the runner, and `pip install PyGObject` on ubuntu-24.04 gets 3.56.0 which links against libgirepository-2.0. That .so will fail to load on Ubuntu 22.04 which doesn't have libgirepository-2.0 at runtime.

The `--copies` venv approach correctly handles the Python binary embedding. Shebangs in pip-installed entry point scripts inside the venv will contain absolute paths to `/opt/linux-speech-flow/venv/bin/python3` — this is correct and expected since the venv lives at that exact path after install.

**Primary recommendation:** Pin `PyGObject<3.51` in the venv pip install step OR switch build runner to ubuntu-22.04. Also configure PyPI trusted publisher before the first `v*` tag push.

---

## Standard Stack

### Core
| Tool/Library | Version | Purpose | Why Standard |
|---|---|---|---|
| fpm | latest gem (`gem install fpm --no-document`) | Build .deb from staging dir | No debian/ dir needed; single command; already in CI |
| setuptools-scm | >=8 | Version from git tags | Canonical Python SCM versioning; no manual version bumps |
| setuptools | >=80 | Build backend | Required by setuptools-scm >=8 |
| python3 venv --copies | stdlib | Bundled venv | --copies embeds Python binary; no symlink breakage on install |
| pypa/gh-action-pypi-publish | release/v1 | PyPI upload | Official action; OIDC trusted publishing; already in CI |

### Supporting
| Tool | Purpose | When to Use |
|---|---|---|
| `python -m build --wheel` | Build PyPI wheel | Always; part of CI build step |
| `git describe --tags --abbrev=0` | Get clean tag version for fpm | When setuptools-scm not used for .deb version extraction |
| `python -m setuptools_scm` | Get current version from git | Alternative to git describe in CI |
| lintian | Validate .deb package | Run after fpm to catch packaging errors |

### Installation (CI build step)
```bash
# Ruby gem (build machine only)
gem install fpm --no-document

# Build deps (build machine only, not runtime)
sudo apt-get install -y libgirepository1.0-dev libcairo2-dev pkg-config python3-dev libpulse-dev ruby

# pyproject.toml build system
pip install build setuptools-scm
```

---

## Architecture Patterns

### Staging Directory Layout
```
dist-deb/
├── opt/
│   └── linux-speech-flow/
│       └── venv/            # bundled virtualenv (--copies)
│           ├── bin/
│           │   ├── python3  # copied binary (not symlink)
│           │   └── linux-speech-flow  # entry point with shebang to /opt/...
│           └── lib/
│               └── python3.10/
│                   └── site-packages/
└── usr/
    └── local/
        └── bin/
            └── linux-speech-flow  # wrapper bash script
```

### Pattern 1: fpm dir→deb Build
**What:** Stage all files in a directory tree at their final install paths, then call fpm once to produce the .deb.
**When to use:** Always — this is the only fpm pattern used here.
**Example:**
```bash
# Create venv at final install path inside staging
mkdir -p dist-deb/opt/linux-speech-flow
python3 -m venv --copies dist-deb/opt/linux-speech-flow/venv

# Install app with pinned PyGObject (see pitfall #1)
dist-deb/opt/linux-speech-flow/venv/bin/pip install --quiet "PyGObject<3.51" .

# Create wrapper binary
mkdir -p dist-deb/usr/local/bin
printf '#!/bin/bash\nexec /opt/linux-speech-flow/venv/bin/linux-speech-flow "$@"\n' \
  > dist-deb/usr/local/bin/linux-speech-flow
chmod +x dist-deb/usr/local/bin/linux-speech-flow

# Build .deb
fpm -s dir -t deb \
  -n linux-speech-flow \
  -v "$VERSION" \
  --after-install scripts/postinst.sh \
  --after-remove scripts/postrm.sh \
  --depends xdotool \
  --depends xclip \
  --depends libnotify-bin \
  --depends libpulse0 \
  --depends "gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1" \
  --description "Speech-to-text Linux app — hold a key, speak, release, text appears" \
  -C dist-deb \
  .
```

### Pattern 2: setuptools-scm pyproject.toml Config
**What:** Replace hardcoded `version = "0.1.0"` with SCM-derived version from git tags.
**When to use:** Always — locked decision.
**Example:**
```toml
# Source: https://setuptools-scm.readthedocs.io/en/latest/config/
[build-system]
requires = ["setuptools>=80", "setuptools-scm>=8"]
build-backend = "setuptools.build_meta"

[project]
name = "linux-speech-flow"
# version = "0.1.0"  ← REMOVE THIS LINE
dynamic = ["version"]
requires-python = ">=3.10"
# ... rest of [project] unchanged

[tool.setuptools_scm]
fallback_version = "0.1.0"
```

Note: `write_to` is deprecated — do NOT use it. `version_file` is the replacement if a `_version.py` is needed. For this project, `fallback_version` alone is sufficient.

### Pattern 3: postinst / postrm Scripts
**What:** Minimal bash scripts passed to fpm via `--after-install` / `--after-remove`.
**When to use:** Always — fpm embeds these as Debian maintainer scripts.
**Example:**
```bash
# scripts/postinst.sh
#!/bin/bash
set -e
gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor 2>/dev/null || true
```

```bash
# scripts/postrm.sh
#!/bin/bash
set -e
gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor 2>/dev/null || true
rm -f /usr/local/bin/linux-speech-flow
```

The `|| true` guards prevent postinst from failing if `gtk-update-icon-cache` is absent (headless server install). fpm flag: `--after-install scripts/postinst.sh`, `--after-remove scripts/postrm.sh`.

### Pattern 4: PyPI Trusted Publishing (OIDC)
**What:** PyPI issues short-lived tokens via GitHub OIDC — no API token needed.
**When to use:** On first publish before `v*` tag is pushed.
**Setup steps (one-time, manual on pypi.org):**
1. Log in to pypi.org → "Your projects" → create project OR go to existing project → "Manage" → "Publishing"
2. Under "Add a new publisher", select GitHub Actions
3. Fill in: Repository owner (GitHub username/org), Repository name (`linux-speech-flow`), Workflow filename (`ci.yml`)
4. Optionally add a GitHub Actions environment name for extra restriction

**Workflow requirements (already correct in ci.yml):**
```yaml
permissions:
  id-token: write   # required for OIDC token exchange
  contents: write   # for GitHub Release creation
```

The `pypa/gh-action-pypi-publish@release/v1` step needs no username/password — OIDC handles it automatically.

**CRITICAL:** The project must exist on PyPI before configuring the trusted publisher. Either create it via the UI first, OR use PyPI's "pending publisher" feature to pre-configure before first upload.

### Anti-Patterns to Avoid
- **Using `--symlinks` venv (default):** The Python symlink breaks on install machines with different Python minor version. Use `--copies` always.
- **Using `--post-install` fpm flag:** Deprecated. Use `--after-install` instead.
- **Using `write_to` in setuptools-scm:** Deprecated since setuptools-scm 8. Use `version_file` if needed, or just `fallback_version`.
- **Extracting version via `tomllib` from pyproject.toml in CI:** After switching to setuptools-scm, `version` is no longer in pyproject.toml. Use `python -m setuptools_scm` or `git describe --tags --abbrev=0` for fpm version extraction.
- **Installing latest PyGObject on Ubuntu 22.04 targets:** PyGObject >= 3.51 requires libgirepository-2.0 not available on 22.04. Pin `PyGObject<3.51` in the bundled venv.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Version from git tags | Custom git tag parsing script | setuptools-scm | Handles dev versions, dirty working tree, no-tag fallback, sdist compatibility |
| .deb package structure | Custom `dpkg-deb` with DEBIAN/ dir | fpm | fpm handles control file, checksums, md5sums, data.tar, all tarball structure |
| PyPI upload | `twine upload` with API token | `pypa/gh-action-pypi-publish` OIDC | No secrets to rotate; token is ephemeral; official recommended approach |
| Wheel building | distutils bdist_wheel | `python -m build --wheel` | pypa/build is the official frontend; handles PEP 517/518 |

**Key insight:** fpm's `dir` source type is the correct approach — it lets you build the staging tree with normal filesystem tools (mkdir, pip, printf) and then package it in one command, avoiding all the complexity of native Debian packaging tools.

---

## Common Pitfalls

### Pitfall 1: PyGObject >= 3.51 Built on ubuntu-24.04 Fails on Ubuntu 22.04 Targets
**What goes wrong:** CI builds on ubuntu-24.04 runner. `pip install PyGObject` gets 3.56.0 which compiles against `libgirepository-2.0` (available on 24.04). The resulting `.so` in the bundled venv has a runtime dep on `libgirepository-2.0` which does NOT exist on Ubuntu 22.04 or Debian 12. .deb installs fine; app crashes at launch on 22.04/Debian 12.
**Why it happens:** PyGObject ships no wheels — always compiled from source. Build machine libs determine what the .so links against.
**How to avoid:** Either:
  - Option A (preferred): Pin `"PyGObject<3.51"` in the venv pip install step in CI. PyGObject 3.50.x compiles against `libgirepository-1.0` available on 22.04.
  - Option B: Switch CI build runner to `ubuntu-22.04`. Ensures .so links against system libs present on 22.04 targets.
**Warning signs:** `ImportError: libgirepository-2.0.so.0: cannot open shared object file` on launch.

### Pitfall 2: Version Extraction in CI After setuptools-scm Switch
**What goes wrong:** CI .deb build step currently extracts version via `python3 -c "import tomllib; ..."`. After switching to `dynamic = ["version"]`, pyproject.toml has no `version` key — this script errors.
**Why it happens:** setuptools-scm derives version at build time from git; it's not stored in pyproject.toml.
**How to avoid:** Replace the tomllib extraction with `git describe --tags --abbrev=0` (strips `v` prefix if needed) or `python -m setuptools_scm` after installing setuptools-scm.
**Correct CI pattern:**
```bash
pip install setuptools-scm
VERSION=$(python -m setuptools_scm)
# VERSION may be "0.2.0" on tag or "0.2.0.dev3+gabcdef" off-tag
# Strip dev suffix for .deb version if needed:
DEB_VERSION=$(echo "$VERSION" | sed 's/\.dev.*//')
```

### Pitfall 3: fpm Produces .deb with Wrong Install Path for Wrapper
**What goes wrong:** fpm `-C dist-deb .` packages everything relative to `dist-deb/`. If `usr/local/bin/linux-speech-flow` is created outside `dist-deb/`, it won't be included.
**Why it happens:** The `-C` flag changes fpm's working directory; all file paths must be inside that staging root.
**How to avoid:** Always create ALL staged files under `dist-deb/` before calling fpm. The staging must mirror final filesystem layout exactly.

### Pitfall 4: postinst Fails on Headless Install (gtk-update-icon-cache Missing)
**What goes wrong:** `gtk-update-icon-cache` may not be installed on minimal server systems. postinst fails, dpkg marks package as broken.
**Why it happens:** gtk-update-icon-cache is in the `libgtk-3-bin` package, not a dependency of the app itself.
**How to avoid:** Add `|| true` after the gtk-update-icon-cache call, or add `libgtk-3-bin` to fpm `--depends`. Prefer `|| true` to keep deps minimal.

### Pitfall 5: setuptools-scm Fails with LookupError in CI (No Tags)
**What goes wrong:** On push to a branch with no tags in shallow clone history, setuptools-scm throws `LookupError: setuptools-scm was unable to detect version`.
**Why it happens:** GitHub Actions does a shallow clone (`fetch-depth: 1`) by default. Tags may not be fetched.
**How to avoid:** Set `fallback_version = "0.1.0"` in `[tool.setuptools_scm]`. This allows the wheel build to succeed without git tags. For CI, also use `actions/checkout@v4` with `fetch-depth: 0` OR `fetch-tags: true` to get full tag history for correct version.

### Pitfall 6: PyPI Trusted Publisher Not Configured Before First Tag Push
**What goes wrong:** CI publish job runs on `v*` tag, calls `pypa/gh-action-pypi-publish`, fails with authentication error because PyPI doesn't know the GitHub repo yet.
**Why it happens:** Trusted publishing requires pre-configuration on pypi.org — it's not automatic.
**How to avoid:** Configure the trusted publisher on pypi.org BEFORE pushing the first `v*` tag. Use PyPI's "pending publisher" feature to configure before the project exists on PyPI.

### Pitfall 7: venv Entry Point Shebangs Are Absolute (This Is Correct)
**What seems wrong:** Entry point scripts in `/opt/linux-speech-flow/venv/bin/linux-speech-flow` have shebang `#!/opt/linux-speech-flow/venv/bin/python3` — this looks non-portable.
**Why it's actually fine:** The venv installs to exactly `/opt/linux-speech-flow/venv/` on the target machine. The shebang is correct for that path. The wrapper at `/usr/local/bin/linux-speech-flow` calls the venv entry point via `exec`, so users never need to know about the absolute path.
**The real problem to avoid:** Building the venv at a temp path (e.g., `/tmp/dist-deb/opt/...`) and then packaging it. fpm stages files for packaging — the venv is created AT `dist-deb/opt/linux-speech-flow/venv/` which maps to `/opt/linux-speech-flow/venv/` on install. Shebangs will contain `dist-deb/opt/...` if the temp path is different. The CI workflow already creates the venv at the correct relative path inside `dist-deb/`.

---

## Code Examples

Verified patterns from official sources:

### setuptools-scm pyproject.toml (Complete)
```toml
# Source: https://setuptools-scm.readthedocs.io/en/latest/config/
[build-system]
requires = ["setuptools>=80", "setuptools-scm>=8"]
build-backend = "setuptools.build_meta"

[project]
name = "linux-speech-flow"
dynamic = ["version"]
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31",
    "pulsectl>=24.0",
    "pynput>=1.8",
    "pasimple>=0.0.3",
    "groq>=1.0.0",
    "openai>=1.0.0",
    "google-genai",
    "trayer==0.1.1",
    "slack-sdk>=3.40.1",
    "numpy>=1.24",
]

[project.scripts]
linux-speech-flow = "linux_speech_flow.app:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
linux_speech_flow = ["sounds/*.wav", "icons/*.svg"]

[tool.setuptools_scm]
fallback_version = "0.1.0"
```

### CI Version Extraction (After setuptools-scm)
```bash
# Source: verified against setuptools-scm docs
pip install setuptools-scm
VERSION=$(python -m setuptools_scm)
# Strip dev/local suffix for clean .deb version
DEB_VERSION=$(python -m setuptools_scm | python3 -c "import sys; v=sys.stdin.read().strip(); print(v.split('+')[0].split('.dev')[0])")
```

### fpm Command with postinst/postrm
```bash
# Source: https://fpm.readthedocs.io/en/v1.14.0/cli-reference.html
fpm -s dir -t deb \
  -n linux-speech-flow \
  -v "$DEB_VERSION" \
  --after-install scripts/postinst.sh \
  --after-remove scripts/postrm.sh \
  --depends xdotool \
  --depends xclip \
  --depends libnotify-bin \
  --depends libpulse0 \
  --depends "gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1" \
  --description "Speech-to-text Linux app — hold a key, speak, release, text appears" \
  --url "https://github.com/OWNER/linux-speech-flow" \
  -C dist-deb \
  .
```

### postinst.sh (Minimal)
```bash
#!/bin/bash
set -e
gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor 2>/dev/null || true
```

### postrm.sh (Minimal)
```bash
#!/bin/bash
set -e
gtk-update-icon-cache --quiet --force /usr/share/icons/hicolor 2>/dev/null || true
rm -f /usr/local/bin/linux-speech-flow
```

### PyPI Trusted Publisher GitHub Actions (Already in ci.yml)
```yaml
# Source: https://docs.pypi.org/trusted-publishers/using-a-publisher/
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  # No username/password — OIDC handles auth automatically
  # Requires: permissions.id-token: write on the job
```

### actions/checkout with Full Tag History
```yaml
# Source: https://github.com/actions/checkout
- uses: actions/checkout@v4
  with:
    fetch-depth: 0  # full history for setuptools-scm
```

### Bundled Venv Build (Complete CI Step)
```bash
mkdir -p dist-deb/opt/linux-speech-flow
# Build-time: need libgirepository1.0-dev on builder (already in CI system deps step)
pip install "PyGObject<3.51"  # for building, not bundling
python3 -m venv --copies dist-deb/opt/linux-speech-flow/venv
dist-deb/opt/linux-speech-flow/venv/bin/pip install --quiet "PyGObject<3.51" .
mkdir -p dist-deb/usr/local/bin
printf '#!/bin/bash\nexec /opt/linux-speech-flow/venv/bin/linux-speech-flow "$@"\n' \
  > dist-deb/usr/local/bin/linux-speech-flow
chmod +x dist-deb/usr/local/bin/linux-speech-flow
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Hardcoded `version = "0.1.0"` in pyproject.toml | `dynamic = ["version"]` + setuptools-scm | setuptools-scm 8+ with setuptools>=80 | No manual version bumps; CI builds get correct version from git tags |
| `write_to` in setuptools-scm | `version_file` | setuptools-scm 8 | `write_to` broken for sdist; `version_file` replacement works correctly |
| `--post-install` fpm flag | `--after-install` | fpm 1.x | `--post-install` deprecated; `--after-install` is current |
| PyPI API token in CI secrets | OIDC trusted publishing | PyPI 2023 | No secrets to manage or rotate; tokens are ephemeral |
| `files.upload` Slack API | `files_upload_v2` | Slack Nov 2025 sunset | Already addressed in Phase 8 |

**Deprecated/outdated:**
- `write_to`: replaced by `version_file` in setuptools-scm >= 8
- `--post-install`, `--pre-install`, `--post-uninstall`, `--pre-uninstall` fpm flags: use `--after-install`, `--before-install`, `--after-remove`, `--before-remove`
- `twine` with API tokens for PyPI: superseded by OIDC trusted publishing for CI use

---

## Open Questions

1. **PyGObject version pinning vs build runner change**
   - What we know: PyGObject >= 3.51 requires libgirepository-2.0 (unavailable on Ubuntu 22.04). CI runs ubuntu-24.04.
   - What's unclear: Does the current CI workflow already pin PyGObject? (Current ci.yml has `pip install PyGObject` with no pin.)
   - Recommendation: Add `"PyGObject<3.51"` to the venv pip install in the CI .deb build step. This is a one-line fix. Alternatively switch the build job to `ubuntu-22.04`.

2. **DIST-03 vs CONTEXT.md decision conflict**
   - What we know: REQUIREMENTS.md says "postinst installs XDG autostart .desktop entry". CONTEXT.md says "postinst does NOT handle autostart — app owns it at runtime."
   - What's clear: CONTEXT.md overrides REQUIREMENTS.md (it's the locked decision from the discuss-phase). The app already implements this in app.py.
   - Recommendation: Document DIST-03 as "satisfied by existing runtime behavior in app.py" — no postinst autostart needed.

3. **Pending publisher vs project creation**
   - What we know: PyPI supports "pending publishers" — configure trusted publishing before project exists.
   - What's unclear: Whether to create the PyPI project manually first or let the first CI publish create it.
   - Recommendation: Use PyPI's pending publisher feature at `https://pypi.org/manage/account/publishing/` to pre-configure before the first tag push. This avoids the chicken-and-egg problem.

---

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest (installed in .venv, not in pyproject.toml deps) |
| Config file | none (no pytest.ini, no setup.cfg, no pyproject.toml [tool.pytest.ini_options]) |
| Quick run command | `pytest --tb=short -q` |
| Full suite command | `pytest --tb=short -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIST-01 | .deb builds without error | smoke | `bash -c 'gem install fpm --no-document && ... && fpm ...'` (CI) | CI only |
| DIST-01 | .deb installs on clean Ubuntu 22.04 | integration/manual | manual docker test | ❌ — manual only |
| DIST-02 | venv bundled at /opt/.../venv/ with --copies | smoke | `test -f dist-deb/opt/linux-speech-flow/venv/bin/python3` (CI) | CI only |
| DIST-03 | postinst does NOT create autostart | N/A | Requirement satisfied by existing app.py runtime behavior | ✅ existing |
| DIST-04 | wheel builds without error | smoke | `python -m build --wheel` (CI) | CI only |
| DIST-04 | PyPI publish succeeds on v* tag | integration | pypa/gh-action-pypi-publish (CI, tag-gated) | CI only |
| DIST-05 | README has system dep section | manual | code review | ❌ Wave 0 |

**Note:** Most DIST requirements are packaging/infrastructure concerns not amenable to unit tests. The existing 259-test suite covers app behavior. Packaging correctness is validated by the CI build job.

### Sampling Rate
- **Per task commit:** `pytest --tb=short -q` (existing suite, ~30s)
- **Per wave merge:** `pytest --tb=short -q`
- **Phase gate:** Full suite green + CI build job passes before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scripts/postinst.sh` — needs to be created (Wave 1, not a test gap)
- [ ] `scripts/postrm.sh` — needs to be created (Wave 1, not a test gap)
- [ ] `actions/checkout` in CI updated to `fetch-depth: 0` for setuptools-scm (Wave 1)
- None — existing pytest infrastructure covers all unit tests. Packaging validation is CI-only.

---

## Sources

### Primary (HIGH confidence)
- [setuptools-scm official config docs](https://setuptools-scm.readthedocs.io/en/latest/config/) — pyproject.toml config, fallback_version, version_file vs write_to deprecation
- [fpm CLI reference v1.14](https://fpm.readthedocs.io/en/v1.14.0/cli-reference.html) — --after-install, --after-remove, deprecated aliases
- [PyPI trusted publishing docs](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) — exact setup steps for existing project
- [pypa/gh-action-pypi-publish GitHub](https://github.com/pypa/gh-action-pypi-publish) — release/v1, id-token:write requirement
- [PyGObject PyPI page](https://pypi.org/project/PyGObject/) — source-only distribution, latest version 3.56.0

### Secondary (MEDIUM confidence)
- [PyGObject >= 3.51 libgirepository-2.0 issue](https://github.com/beeware/toga/issues/3143) — WebSearch verified with multiple corroborating issues
- [Solaar CI fix for PyGObject 3.52.1](https://github.com/pwr-Solaar/Solaar/issues/2857) — confirms PyGObject >= 3.52.1 breaks Ubuntu 22.04 CI
- [PyGObject getting started](https://pygobject.gnome.org/getting_started.html) — runtime vs build-time dep split

### Tertiary (LOW confidence)
- [venv relocatability discussion](https://discuss.python.org/t/q-what-stops-a-venv-from-being-relocatable/57166) — shebang absolute path behavior (verified independently by inspection)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools verified against official docs
- Architecture: HIGH — fpm -C pattern verified, setuptools-scm config from official docs
- Pitfalls: HIGH for PyGObject version (multiple independent sources confirm), HIGH for others (official docs)
- PyPI OIDC setup: HIGH — official PyPI docs

**Research date:** 2026-03-04
**Valid until:** 2026-06-04 (90 days — fpm, setuptools-scm, PyPI OIDC are stable)
