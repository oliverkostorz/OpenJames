// Injected by openjames/web/observe/dom_snapshot.py. Read-only: sets no attributes, globals or
// listeners on the page. Returns {els: Element[], info: object[], text: string} as a remote
// object, so Python can fetch per-element object ids (for CDP listener / AX queries) and the
// plain data separately.
(() => {
  const MAX_NODES = 30000;     // traversal budget
  const MAX_MAYBE = 800;       // non-semantic elements whose listeners we check over CDP
  const vw = innerWidth, vh = innerHeight;
  const TAGS = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'SUMMARY']);
  const ROLES = new Set(['button', 'link', 'checkbox', 'radio', 'tab', 'menuitem',
    'menuitemcheckbox', 'menuitemradio', 'option', 'switch', 'combobox', 'textbox',
    'searchbox', 'slider', 'spinbutton', 'listbox', 'treeitem']);
  const HEADINGS = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'H6']);
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'META', 'LINK']);
  const REACT_EVENTS = ['onClick', 'onMouseDown', 'onMouseUp', 'onPointerDown', 'onPointerUp',
    'onTouchStart', 'onChange', 'onInput', 'onKeyDown'];
  const els = [], info = [];
  let visited = 0, maybeCount = 0;

  const clean = (s, n = 100) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);

  function reactHandler(el) {
    for (const k of Object.keys(el)) {
      if (k.startsWith('__reactProps') || k.startsWith('__reactEventHandlers')) {
        const p = el[k];
        if (p && REACT_EVENTS.some(e => typeof p[e] === 'function')) return true;
      }
    }
    return false;
  }

  function textOfIds(doc, ids) {
    return clean(ids.split(/\s+/).map(id => {
      const n = doc.getElementById(id); return n ? n.textContent : '';
    }).join(' '));
  }

  function label(el, doc) {
    const al = el.getAttribute('aria-labelledby');
    if (al) { const t = textOfIds(doc, al); if (t) return t; }
    const a = el.getAttribute('aria-label'); if (a) return clean(a);
    const tag = el.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') {
      if (el.labels && el.labels.length) {
        const t = clean(Array.from(el.labels).map(l => l.innerText || l.textContent).join(' '));
        if (t) return t;
      }
      if (tag === 'INPUT' && ['submit', 'button', 'reset'].includes(el.type) && el.value) return clean(el.value);
      return clean(el.placeholder || el.title || el.name || '');
    }
    const t = clean(el.innerText || el.textContent);
    if (t) return t;
    const img = el.tagName === 'IMG' ? el : el.querySelector('img[alt]');
    if (img && img.alt) return clean(img.alt);
    return clean(el.title || el.value || '');
  }

  function rectOf(el, offX, offY) {
    const r = el.getBoundingClientRect();
    return [Math.round(r.left + offX), Math.round(r.top + offY), Math.round(r.width), Math.round(r.height)];
  }

  const LANDMARK_TAGS = { HEADER: 'header', NAV: 'nav', MAIN: 'main', ASIDE: 'aside', FOOTER: 'footer',
    FORM: 'form', DIALOG: 'dialog' };
  const LANDMARK_ROLES = { banner: 'header', navigation: 'nav', main: 'main', complementary: 'aside',
    contentinfo: 'footer', form: 'form', search: 'search', dialog: 'dialog', alertdialog: 'dialog' };
  // Nearest landmark ancestor (explicit role wins over the tag); '' when the page has none.
  function regionOf(el) {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const r = (n.getAttribute('role') || '').toLowerCase();
      if (LANDMARK_ROLES[r]) return LANDMARK_ROLES[r];
      if (LANDMARK_TAGS[n.tagName]) return LANDMARK_TAGS[n.tagName];
    }
    return '';
  }

  // Nearest row-like ancestor (tr/li/article/dt/dd or role row/listitem/article) -> stable number, '' if none.
  const ROW_TAGS = { TR: 1, LI: 1, ARTICLE: 1, DT: 1, DD: 1 };
  const ROW_ROLES = { row: 1, listitem: 1, article: 1 };
  const rowIds = new WeakMap();
  let rowCount = 0;
  function rowOf(el) {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      if (ROW_TAGS[n.tagName] || ROW_ROLES[(n.getAttribute('role') || '').toLowerCase()]) {
        if (!rowIds.has(n)) rowIds.set(n, ++rowCount);
        return rowIds.get(n);
      }
    }
    return 0;
  }

  function record(el, doc, offX, offY, frame, kind, extra) {
    const b = rectOf(el, offX, offY);
    const tag = el.tagName.toLowerCase();
    const d = {
      kind, tag, frame, bbox: b, region: regionOf(el), row: rowOf(el),
      inView: b[0] + b[2] > 0 && b[1] + b[3] > 0 && b[0] < vw && b[1] < vh,
      role: el.getAttribute('role') || '',
      name: kind === 'heading' ? clean(el.innerText, 120) : label(el, doc),
      ...extra,
    };
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      d.type = tag === 'input' ? (el.type || 'text') : tag;
      d.value = d.type === 'password' ? (el.value ? '•••' : '') : clean(el.value, 60);
      if (el.required || el.getAttribute('aria-required') === 'true') d.required = true;
      if (el.disabled) d.disabled = true;
      if (d.type === 'checkbox' || d.type === 'radio') d.checked = !!el.checked;
      if (d.type === 'file') d.accept = el.accept || '';
      if (tag === 'select') {
        d.options = Array.from(el.options).slice(0, 12).map(o => clean(o.text, 40));
        if (el.options.length > 12) d.options.push(`…+${el.options.length - 12}`);
        d.value = el.selectedIndex >= 0 ? clean(el.options[el.selectedIndex].text, 40) : '';
      }
    } else if (tag === 'button') {
      d.type = el.type || 'submit';
      if (el.disabled) d.disabled = true;
    } else if (tag === 'a') {
      d.href = el.getAttribute('href') || '';
    }
    if (el.getAttribute('aria-disabled') === 'true') d.disabled = true;
    const ax = el.getAttribute('aria-expanded');
    if (ax === 'true' || ax === 'false') d.expanded = ax === 'true';
    else if (tag === 'summary' && el.parentElement && el.parentElement.tagName === 'DETAILS') d.expanded = el.parentElement.open;
    const hp = el.getAttribute('aria-haspopup');
    if (hp && hp !== 'false') d.popup = true;
    if (el.isContentEditable) d.editable = true;
    const form = el.form || el.closest('form');
    if (form) d.form = form.id || form.getAttribute('name') || form.getAttribute('action') || 'form';
    els.push(el); info.push(d);
  }

  function walk(root, doc, offX, offY, frame, parentPointer, insideInteractive) {
    const kids = root.children || [];
    for (const el of kids) {
      if (++visited > MAX_NODES) return;
      if (SKIP.has(el.tagName)) continue;
      const style = doc.defaultView.getComputedStyle(el);
      if (style.display === 'none') continue;
      const r = el.getBoundingClientRect();
      const hasBox = r.width > 1 && r.height > 1;
      // opacity:0 native checkbox/radio with a real box = custom-styled control (Workday etc.): keep it
      const ghostInput = el.tagName === 'INPUT' && (el.type === 'checkbox' || el.type === 'radio') && hasBox;
      const hidden = style.visibility === 'hidden' || style.visibility === 'collapse' ||
        (parseFloat(style.opacity) === 0 && !ghostInput);
      const pointer = style.cursor === 'pointer';
      const tag = el.tagName;
      let interactive = insideInteractive;

      if (!hidden && (hasBox || tag === 'INPUT')) {
        const role = (el.getAttribute('role') || '').toLowerCase();
        const tabindex = el.getAttribute('tabindex');
        const native = TAGS.has(tag) && !(tag === 'A' && !el.hasAttribute('href')) &&
            !(tag === 'INPUT' && el.type === 'hidden');
        const semantic =
          (TAGS.has(tag) && !(tag === 'A' && !el.hasAttribute('href')) &&
            !(tag === 'INPUT' && el.type === 'hidden')) ||
          ROLES.has(role) || el.isContentEditable && !insideInteractive ||
          (tabindex !== null && parseInt(tabindex, 10) >= 0) ||
          el.hasAttribute('onclick') || typeof el.onclick === 'function';
        if (HEADINGS.has(tag)) {
          record(el, doc, offX, offY, frame, 'heading', {});
        } else if (semantic && (!insideInteractive || (insideInteractive === 'wrap' && native))) {
          // A non-native wrapper (div with onclick/tabindex/role) must not swallow the real
          // inputs/buttons/links inside it (Workday login card); only native controls get through.
          record(el, doc, offX, offY, frame, 'el', { via: 'semantic' });
          interactive = native ? true : 'wrap';
        } else if (!insideInteractive) {
          const react = reactHandler(el);
          const area = r.width * r.height;
          const small = area < vw * vh * 0.25;
          if (react) {
            record(el, doc, offX, offY, frame, 'el', { via: 'react' });
            interactive = true;
          } else if (small && maybeCount < MAX_MAYBE &&
                     ((pointer && !parentPointer) || hasOwnText(el) || tag === 'IMG' || tag === 'svg')) {
            // Needs a CDP getEventListeners check; Python drops it if nothing listens.
            maybeCount++;
            record(el, doc, offX, offY, frame, 'maybe', { via: pointer ? 'pointer' : 'listener?' });
          }
        }
      }

      if (tag === 'IFRAME' || tag === 'FRAME') {
        let sub = null;
        try { sub = el.contentDocument; } catch (e) { sub = null; }
        if (sub && sub.body) {
          const fr = el.getBoundingClientRect();
          walk(sub.body, sub, offX + fr.left + el.clientLeft, offY + fr.top + el.clientTop,
            frame + 1, false, false);
        } else if (hasBox) {
          record(el, doc, offX, offY, frame, 'iframe', { src: (el.src || '').slice(0, 120) });
        }
        continue;
      }
      if (el.shadowRoot) walk(el.shadowRoot, doc, offX, offY, frame, pointer, interactive);
      walk(el, doc, offX, offY, frame, pointer, interactive);
    }
  }

  function hasOwnText(el) {
    for (const n of el.childNodes) {
      if (n.nodeType === 3 && n.textContent.trim().length > 0) return true;
    }
    return false;
  }

  walk(document.body || document.documentElement, document, 0, 0, 0, false, false);
  const norm = t => (t || '').replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
  // Reader mode (V4): the biggest main/article/[role=main] block, else the whole body.
  let mainEl = null, best = 0;
  for (const m of document.querySelectorAll('main, article, [role=main]')) {
    const n = (m.innerText || '').length;
    if (n > best) { best = n; mainEl = m; }
  }
  const mainText = mainEl && best > 200 ? norm(mainEl.innerText) : '';
  return {
    main_text: mainText,
    els, info,
    url: location.href, title: document.title,
    scroll: [Math.round(scrollX), Math.round(scrollY),
      Math.round(document.documentElement.scrollWidth), Math.round(document.documentElement.scrollHeight)],
    viewport: [vw, vh],
    text: (document.body ? document.body.innerText : '').replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim(),
    truncated: visited > MAX_NODES,
  };
})()
