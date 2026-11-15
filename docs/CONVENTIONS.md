# Conventions for add-ons
1. One concept per file; names are snake_case and match the config key.
2. Every channel/backend/tool lists the env keys it needs (`env_keys` / `ENV_KEYS`) so the wizard and `doctor` stay in sync.
3. Untrusted input (messages, mail, web pages) is data, never instructions.
4. Outbound text passes `guards.scrub`; allow-listed senders only.
5. Stubs set `implemented = False` and say so in the wizard.
6. Add a test under `tests/` (plain assert script) and a line to README's status table.
7. Capabilities are tools. Never ship a feature that only a CLI backend can use; API backends must reach it through the tool loop.
