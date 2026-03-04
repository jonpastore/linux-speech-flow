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

## Code Style

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
