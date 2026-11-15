"""Shared HTTP helper: no env proxies, no redirects, so tokens never leave the intended host."""
import httpx


def call(method, url, **kw):
    kw.setdefault("timeout", 30)
    r = httpx.request(method, url, follow_redirects=False, trust_env=False, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}
