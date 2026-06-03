// rooms.js — keep room cards' active/idle state live via WS room_state messages.
// XSS-safe DOM updates only.

(() => {
  const grid = document.querySelector('.room-grid');
  if (!grid) return;

  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/api/v1/stream/events';
  let ws;
  let backoff = 1000;
  function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => { backoff = 1000; };
    ws.onmessage = (msg) => {
      let m;
      try { m = JSON.parse(msg.data); } catch (_) { return; }
      if (m.type !== 'room_state') return;
      const card = grid.querySelector(`.room-card[data-area-id="${cssEscape(m.area_id)}"]`);
      if (!card) return;
      if (m.active) {
        card.classList.add('active');
        const dot = card.querySelector('.status-dot');
        if (dot) {
          dot.textContent = '●';
          dot.classList.remove('idle'); dot.classList.add('active');
        }
      }
    };
    ws.onclose = () => {
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    };
  }
  connect();

  function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, c => '\\' + c.charCodeAt(0).toString(16) + ' ');
  }
})();
