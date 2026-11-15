# OpenJames

An open-source personal AI assistant you talk to over your own chat channels. It runs a small orchestrator whenever a message arrives, uses tools and skills, learns new ones on demand, keeps its own memory, and fixes its own bugs. Your data stays on your machine.

Status: early (v0.2). Nine channels are implemented; none needs a public URL, tunnel or webhook (everything is polled).

## Quick start
```bash
uv sync
uv run openjames init      # wizard: pick channels, backends and fallback order, allowed principal, secrets
uv run openjames doctor    # check the setup
uv run openjames deploy    # render launchd/systemd unit; you review and install it
```

## How it works
`listener` (always on, no model calls) polls your active channels, accepts only allow-listed senders, writes `inbox/*.md`, and starts the `orchestrator`, which runs one task through your backend chain (first working backend in your priority order) and writes `outbox/*.md`, which the listener sends back.

- **Channels** (pick any, all polling, no webhook): telegram (id auto-detected in the wizard), email (IMAP/SMTP hosts derived from your address, DMARC-checked), discord, slack, matrix, whatsapp + sms (one Twilio account), signal (signal-cli), imessage (macOS). `doctor` live-checks each credential.
- **Backends** (pick any, order = fallback): claude_code, codex, gemini (subscription CLIs), openrouter, anthropic_api (paid keys)
- **Tools**: auto-discovered from `openjames/tools/`; the `create_tool` tool lets it write new ones. Built in, so a fresh install needs no self-teaching:
  `notify_principal`, `ask_principal` (question queue), `timer` (one-off/recurring reminders and follow-ups), `gen_password` / `store_secret` / `secret_use` (credential vault in `private/`, values never echoed),
  `http_get` (safe read-only fetch), `web_observe` / `web_act` / `web_task` (real Chrome via CDP with human-like input, submit gate and domain/rate guards; drives your installed Chrome),
  `subagent`, voice memos (Telegram voice/audio/video notes are transcribed via whisper.cpp, openai-whisper or OPENAI_API_KEY; see `openjames/media.py`), `delegate` (experts: researcher, memory-curator, web-operator), `memory`, `list_tools`, `create_tool`.

## Privacy
Secrets live only in `.env` (mode 600), choices in `config.toml`; both and all runtime dirs are gitignored. Outbound text is secret-scanned, unknown senders are dropped, external content is treated as untrusted. No telemetry.

## Contributing
Read `AGENTS.md` and `docs/CONVENTIONS.md`. MIT licensed.
