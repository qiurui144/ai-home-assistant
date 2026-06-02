(() => {
  const list = document.getElementById('events');
  if (!list) return;
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/api/v1/stream/events';
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (msg) => {
    let e;
    try { e = JSON.parse(msg.data); } catch (_) { return; }
    const tr = document.createElement('tr');
    const tdTime = document.createElement('td');
    tdTime.textContent = new Date(e.ts || Date.now()).toISOString();
    const tdEntity = document.createElement('td');
    tdEntity.textContent = String(e.entity_id || '');
    const tdType = document.createElement('td');
    tdType.textContent = String(e.event_type || '');
    tr.appendChild(tdTime);
    tr.appendChild(tdEntity);
    tr.appendChild(tdType);
    list.prepend(tr);
    while (list.children.length > 200) list.removeChild(list.lastChild);
  };
  ws.onclose = () => { setTimeout(() => location.reload(), 2000); };
})();
