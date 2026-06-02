(() => {
  const form = document.getElementById('privacy-form');
  if (!form) return;
  const msg = document.getElementById('msg');
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const text = form.elements.hide_entities_pattern.value;
    const patterns = text.split('\n').map(s => s.trim()).filter(Boolean);
    const r = await fetch('/api/v1/settings/privacy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hide_entities_pattern: patterns }),
      credentials: 'same-origin',
    });
    msg.textContent = '';
    if (r.ok) {
      msg.textContent = 'Saved.';
    } else {
      const body = await r.json().catch(() => ({}));
      msg.textContent = 'Error: ' + (body.detail && body.detail.detail || r.status);
    }
  });
})();
