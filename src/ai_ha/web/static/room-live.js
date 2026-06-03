// room-live.js — single-room page: live event stream + entity last_seen updates.

(() => {
  const areaIdEl = document.querySelector('[data-area-id]');
  if (!areaIdEl) return;
  const myAreaId = areaIdEl.dataset.areaId;

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
      if (m.type === 'state_changed' && m.area_id === myAreaId) {
        prependEvent(m);
      }
    };
    ws.onclose = () => {
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    };
  }
  connect();

  function prependEvent(m) {
    const list = document.querySelector('#room-events-tbody');
    if (!list) return;
    const tr = document.createElement('tr');
    const tdT = document.createElement('td');
    tdT.textContent = new Date(m.ts || Date.now()).toISOString();
    const tdE = document.createElement('td');
    tdE.textContent = String(m.entity_id || '');
    const tdY = document.createElement('td');
    tdY.textContent = String(m.event_type || '');
    tr.appendChild(tdT); tr.appendChild(tdE); tr.appendChild(tdY);
    list.prepend(tr);
    while (list.children.length > 50) list.removeChild(list.lastChild);
  }
})();
