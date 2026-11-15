# OpenJames

An open-source personal AI assistant you talk to over your own chat channels. It runs a small orchestrator whenever a message arrives, uses tools and skills, learns new ones on demand, keeps its own memory, and fixes its own bugs. Your data stays on your machine.

Status: early (v0.2). Nine channels are implemented; none needs a public URL, tunnel or webhook (everything is polled).

## Quick start (about 5 minutes)
Needs macOS or Linux, Python 3.12+ and [uv](https://docs.astral.sh/uv/). Chrome is only needed for the web tools.
```bash
git clone <this repo> && cd OpenJames
uv sync
uv run openjames init      # wizard: channels, backends + fallback order, your allowed id, secrets -> .env (mode 600)
uv run openjames doctor    # live-checks every credential
uv run openjames deploy    # renders a launchd/systemd unit; you review and install it
```
1. In `init`, pick **one** channel to start (Telegram is the quickest) and **one** backend you already have (a subscription CLI such as `claude`, or an OpenRouter key).
2. Message your bot from the account you allow-listed. The listener writes `inbox/*.md`, the orchestrator answers into `outbox/*.md`, and the listener sends it back.
3. Add more channels later by re-running `init`; secrets go only to `.env`.

## Channel matrix
All channels are polled: no public URL, tunnel or webhook.

| Channel | Secrets in `.env` | One-time human step | Headless-friendly |
|---|---|---|---|
| telegram | `TELEGRAM_BOT_TOKEN` | create bot with @BotFather, message it once | yes |
| matrix | `MATRIX_HOMESERVER`, `MATRIX_ACCESS_TOKEN` | bot account, invite to an unencrypted DM | yes |
| discord | `DISCORD_BOT_TOKEN` | create app + bot, share a server, DM it | yes |
| slack | `SLACK_BOT_TOKEN` | create app with scopes, install to workspace | yes |
| email | `EMAIL_*` (IMAP/SMTP hosts derived from address) | app password / 2-step verification | yes |
| sms | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` | Twilio account + number (paid) | yes |
| whatsapp | Twilio SID/token, `TWILIO_WHATSAPP_FROM` | join the Twilio sandbox from your phone | no |
| signal | `SIGNAL_NUMBER` | install `signal-cli`, link or register a number | no |
| imessage | none | macOS only, Full Disk Access for the job | no |

Status: all channels are covered by mocked tests; only some have run live (see CHANGELOG once it exists).

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
