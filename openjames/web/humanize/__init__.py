"""Human-like input for the web agent (M6 P2): persona, cursor paths, timing, mouse, keyboard, scroll.

Everything talks to Chrome through a raw CDP session (`cdp.send(method, params)`), so the
events are `isTrusted` and no page script is involved. Usable on its own, e.g.
`Mouse(cdp, Persona.new()).click(x, y)`.

The persona is seeded once per daemon session, so speed, precision and typo rate stay
consistent within a run but differ between sessions. A daemon that runs stale code is replaced by
`openjames.web.client`; this module changing is enough to trigger that.
"""
