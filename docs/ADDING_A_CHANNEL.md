# Adding a channel
Copy `openjames/channels/telegram.py`, implement `poll()` (new messages from any sender; allow-listing happens in the listener) and `send(to, text)`, set `env_keys`, add the name to `CHANNELS` in `config.py`, and add a test with a fake transport.
