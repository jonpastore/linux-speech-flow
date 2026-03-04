# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

To report a vulnerability, use GitHub's private vulnerability reporting:

1. Go to the [Security tab](https://github.com/jonpastore/linux-speech-flow/security/advisories/new) of this repository
2. Click "Report a vulnerability"
3. Fill in the details

You can expect an acknowledgment within 48 hours and a fix timeline within 14 days for
confirmed vulnerabilities.

## Privacy Notes

This application sends audio to Groq's API servers for transcription. API keys are stored
locally at `~/.config/linux-speech-flow/config.json` with mode 0600. No data is stored by
the app beyond your local config and conversation files.
