# OpenJames

An open-source personal AI assistant you talk to over your own chat channels. It runs a small orchestrator whenever a message arrives, uses tools and skills, learns new ones on demand, keeps its own memory, and fixes its own bugs. Your data stays on your machine.

Status: early scaffold (v0.1). Telegram and email work in principle; WhatsApp, iMessage, SMS and Signal are stubs awaiting contributions.

## Quick start
```bash
uv sync
uv run openjames init      # wizard: pick channels, backends and fallback order, allowed principal, secrets
uv run openjames doctor    # check the setup
uv run openjames deploy    # render launchd/systemd unit; you review and install it
```

## How it works
`listener` (always on, no model calls) polls your active channels, accepts only allow-listed senders, writes `inbox/*.md`, and starts the `orchestrator`, which runs one task through your backend chain (first working backend in your priority order) and writes `outbox/*.md`, which the listener sends back.

- **Channels** (pick any): telegram, email, whatsapp*, imessage* (macOS), sms*, signal* (*stub)
- **Backends** (pick any, order = fallback): claude_code, codex, gemini (subscription CLIs), openrouter, anthropic_api (paid keys)
- **Tools**: auto-discovered from `openjames/tools/`; the `create_tool` tool lets it write new ones.

## Privacy
Secrets live only in `.env` (mode 600), choices in `config.toml`; both and all runtime dirs are gitignored. Outbound text is secret-scanned, unknown senders are dropped, external content is treated as untrusted. No telemetry.

## Contributing
Read `AGENTS.md` and `docs/CONVENTIONS.md`. MIT licensed.
