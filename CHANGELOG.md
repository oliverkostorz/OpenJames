# Changelog

## 0.1.0 (2026-11-15)

### Added
- Channels: Telegram, Discord, Slack, Matrix, Twilio SMS/WhatsApp, Signal, iMessage, email, and ntfy (two topics, no account).
- Orchestrator with API tool-calling loop, `delegate` tool with expert agents, and tool-first rule.
- Built-in tools: notify/ask principal, timers, credential vault, `http_get`, web toolkit with agent, `subagent`.
- Voice memos and attachments (speech-to-text via whisper.cpp, openai-whisper or OpenAI API).
- Init wizard (Gmail signup, 2-step verification, app password capture), `doctor` checks, `deploy` rendering of launchd units.
- CI (GitHub Actions, Python 3.12/3.13) and `make check`.
- README quickstart and channel matrix.

### Fixed
- `python -m openjames.orchestrator` now runs (missing `__main__` guard; found by dogfooding the ntfy listener).

## v0.1 release checklist
- [x] CI green config + `make check`
- [x] README quickstart + channel matrix
- [x] ntfy channel live-tested (check/poll/dedupe/chunked send)
- [x] End-to-end dogfood: ntfy -> listener -> orchestrator -> outbox
- [x] `doctor` and `deploy` render verified in a clean copy
- [x] Oliver reviews local commits
- [x] Push to GitHub (CI result: see Actions)
- [ ] Live send-back of outbox reply via listener (covered only by mocks)
- [x] Tag v0.1.0
