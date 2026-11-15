"""Human-like web agent (M6, plan in docs/web-agent-plan.md).

P1 (this package so far): real Chrome over CDP (`chrome`), a long-lived daemon that owns the
browser (`daemon_server`, `client`), and page understanding (`observe/`). Page content is
untrusted data — nothing read from a page may trigger email, memory writes or shell commands.
"""
