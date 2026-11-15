// Injected by openjames/web/observe/labels.py via Runtime.callFunctionOn on ONE element
// (`this` = the widget). Read-only: sets no attributes, globals or listeners.
// Returns the question/context label of a widget whose own text is only a placeholder
// ("Select…"), or '' when there is none. Used for react-select & co., where the visible
// name is the placeholder and the real question lives elsewhere.
function () {
  const el = this;
  const doc = el.ownerDocument || document;
  const clean = (s, n = 100) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const textOfIds = ids => clean((ids || '').split(/\s+/)
    .map(id => { const n = doc.getElementById(id); return n ? n.textContent : ''; }).join(' '));

  // 1) A nested real control usually carries the accessible name
  //    (react-select puts the question's id in the inner input's aria-labelledby).
  const inner = el.querySelector('input, select, textarea, [aria-labelledby], [aria-label]');
  if (inner) {
    let t = textOfIds(inner.getAttribute('aria-labelledby'));
    if (t) return t;
    t = clean(inner.getAttribute('aria-label'));
    if (t) return t;
    if (inner.labels && inner.labels.length) {
      t = clean(Array.from(inner.labels).map(l => l.innerText || l.textContent).join(' '));
      if (t) return t;
    }
  }

  // 2) The nearest preceding <label>/<legend>, but only if no other control sits
  //    between it and this widget (otherwise it labels the field before us).
  let best = null;
  for (const lab of doc.querySelectorAll('label, legend')) {
    if (el.contains(lab)) continue;
    if (!(lab.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
    if (!best || (best.compareDocumentPosition(lab) & Node.DOCUMENT_POSITION_FOLLOWING)) best = lab;
  }
  if (best) {
    const t = clean(best.innerText || best.textContent);
    if (t && !controlBetween(best, el)) return t;
  }
  return '';

  function controlBetween(label, widget) {
    const ctrls = doc.querySelectorAll(
      'input:not([type=hidden]), select, textarea, [role="combobox"], [role="listbox"],' +
      '[role="textbox"], [role="spinbutton"], [contenteditable="true"]');
    for (const c of ctrls) {
      if (c === widget || widget.contains(c) || label.contains(c)) continue;
      if ((label.compareDocumentPosition(c) & Node.DOCUMENT_POSITION_FOLLOWING) &&
          (c.compareDocumentPosition(widget) & Node.DOCUMENT_POSITION_FOLLOWING)) return true;
    }
    return false;
  }
}
