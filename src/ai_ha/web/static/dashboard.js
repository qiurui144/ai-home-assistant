// dashboard.js — drives /dashboard live updates via WS + periodic health polls.
// XSS-safe: only textContent / createElement, never innerHTML with server data.

(() => {
  const island = document.getElementById('dashboard-initial');
  if (!island) return;

  let state = { health: {}, rooms: [], recent_events: [] };
  try { state = JSON.parse(island.textContent); } catch (_) {}

  // ----- WS connection -----
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/api/v1/stream/events';
  let ws;
  let backoff = 1000;
  function connect() {
    ws = new WebSocket(wsUrl);
    document.getElementById('chip-ws').textContent = '○';
    ws.onopen = () => {
      document.getElementById('chip-ws').textContent = '●';
      backoff = 1000;
    };
    ws.onmessage = (msg) => {
      let m;
      try { m = JSON.parse(msg.data); } catch (_) { return; }
      if (m.type === 'state_changed') {
        prependEvent(m);
      } else if (m.type === 'room_state') {
        updateRoomCard(m);
      }
    };
    ws.onclose = () => {
      document.getElementById('chip-ws').textContent = '○';
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    };
  }
  connect();

  // ----- DOM updaters (XSS-safe) -----
  function prependEvent(m) {
    const list = document.getElementById('event-stream');
    if (!list) return;
    const li = document.createElement('li');
    li.className = 'event-row';
    li.dataset.ts = String(m.ts || Date.now());

    const t = document.createElement('span');
    t.className = 'event-time';
    t.textContent = new Date(m.ts || Date.now()).toISOString().slice(11, 19);

    const e = document.createElement('span');
    e.className = 'event-entity';
    e.textContent = String(m.entity_id || '');

    li.appendChild(t);
    li.appendChild(e);
    if (m.area_id) {
      const a = document.createElement('span');
      a.className = 'event-area';
      a.textContent = String(m.area_id);
      li.appendChild(a);
    }
    list.prepend(li);
    while (list.children.length > 50) list.removeChild(list.lastChild);
  }

  function updateRoomCard(m) {
    const card = document.querySelector(`.room-card[data-area-id="${cssEscape(m.area_id)}"]`);
    if (!card) return;
    if (m.active) {
      card.classList.add('active');
      const dot = card.querySelector('.status-dot');
      if (dot) { dot.textContent = '●'; dot.classList.remove('idle'); dot.classList.add('active'); }
    }
  }

  function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, c => '\\' + c.charCodeAt(0).toString(16) + ' ');
  }

  // ----- 30s health polling -----
  setInterval(async () => {
    try {
      const r = await fetch('/api/health', { credentials: 'same-origin' });
      if (!r.ok) return;
      const h = await r.json();
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = String(v); };
      set('chip-entities', h.events_per_hour ?? '—');
      set('chip-events', h.events_per_hour ?? 0);
      set('chip-drops', h.hidden_event_count ?? 0);
      set('chip-uptime', formatUptime(h.uptime_seconds ?? 0));
    } catch (_) {}
  }, 30000);

  function formatUptime(sec) {
    if (sec < 60) return sec + 's';
    if (sec < 3600) return Math.floor(sec / 60) + 'm';
    if (sec < 86400) return Math.floor(sec / 3600) + 'h';
    return Math.floor(sec / 86400) + 'd';
  }
})();
