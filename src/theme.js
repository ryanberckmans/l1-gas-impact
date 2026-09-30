// Resolve before styles load; storage denial must not prevent rendering.
(() => {
  'use strict';
  const key = 'l1-gas-theme';
  const valid = value => ['system', 'light', 'dark'].includes(value) ? value : 'system';
  const media = typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  let mode = 'system';
  try { mode = valid(localStorage.getItem(key)); } catch {}
  function apply() {
    const theme = mode === 'system' ? (media?.matches ? 'dark' : 'light') : mode;
    document.documentElement.dataset.theme = theme;
    const tint = document.querySelector('meta[name="theme-color"]');
    if (tint) tint.setAttribute('content', theme === 'dark' ? '#111827' : '#ffffff');
    const selector = document.getElementById('theme');
    if (selector) selector.value = mode;
  }
  window.GAS_THEME = {
    get mode() { return mode; },
    set(value) {
      mode = valid(value);
      try { localStorage.setItem(key, mode); } catch {}
      apply();
    }
  };
  if (media?.addEventListener) media.addEventListener('change', apply);
  else if (media?.addListener) media.addListener(apply);
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) {
      mode = valid(event.newValue);
      apply();
    }
  });
  apply();
})();
