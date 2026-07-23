# Contributing to Linux Speech Flow

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/jonpastore/linux-speech-flow.git
cd linux-speech-flow
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

System dependencies:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 libgirepository1.0-dev xdotool
```

## Running Tests

```bash
pytest --tb=short -q
```

## Code Style & Static Analysis

Install the pre-commit hooks once — they run ruff (lint + format) and bandit on the files you touch:

```bash
pip install pre-commit && pre-commit install
```

CI additionally hard-gates every push/PR with **bandit** (security static analysis) and **pip-audit**
(dependency vulnerabilities); a merge fails if either finds an issue.

- Follow existing code conventions
- No new dependencies without discussion
- All new behavior should have tests

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes with clear messages
4. Run the test suite and ensure it passes
5. Open a pull request

## Reporting Bugs

Use the [Bug Report template](https://github.com/jonpastore/linux-speech-flow/issues/new/choose).

## Questions

Open a [Discussion](https://github.com/jonpastore/linux-speech-flow/discussions) for questions
that aren't bugs or feature requests.
