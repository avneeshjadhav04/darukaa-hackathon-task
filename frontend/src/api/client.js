/* Thin API client. All provider non-secret fields live in localStorage;
   API keys are POSTed and live only in server-side process memory. */

export const API = '/api';

// ---------- provider config (localStorage, non-secret) ----------
const LS_KEY = 'dbc.providers.v1';

export function loadProviderFields() {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY)) || {};
  } catch {
    return {};
  }
}
export function saveProviderFields(fields) {
  // fields: {llm:{...}, embedding:{...}} — strip api keys before persisting
  localStorage.setItem(LS_KEY, JSON.stringify(fields));
}

// ---------- HTTP helpers ----------
async function j(r) {
  const text = await r.text();
  let body;
  try { body = JSON.parse(text); } catch { body = text; }
  if (!r.ok) {
    const msg = (body && (body.detail || body.error)) || `HTTP ${r.status}`;
    const e = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    e.status = r.status;
    e.body = body;
    throw e;
  }
  return body;
}

export const api = {
  config: {
    status: () => fetch(`${API}/config`).then(j),
    setKey: (slot, api_key) =>
      fetch(`${API}/config/key`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slot, api_key }),
      }).then(j),
    forget: () => fetch(`${API}/config/key`, { method: 'DELETE' }).then(j),
    test: (payload) =>
      fetch(`${API}/config/test`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).then(j),
  },
  ingest: {
    file: (file, embeddingFields) => {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('payload', JSON.stringify(embeddingFields || {}));
      return fetch(`${API}/ingest/file`, { method: 'POST', body: fd }).then(j);
    },
    url: (url, embeddingFields) =>
      fetch(`${API}/ingest/url`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, embedding: embeddingFields || null }),
      }).then(j),
    index: () => fetch(`${API}/ingest/index`).then(j),
    delete: (name, embeddingFields) =>
      fetch(`${API}/ingest/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, embedding: embeddingFields || null }),
      }).then(j),
    reset: () => fetch(`${API}/ingest/reset`, { method: 'POST' }).then(j),
  },
  chat: {
    history: () => fetch(`${API}/chat/history`).then(j),
    clear: () => fetch(`${API}/chat/clear`, { method: 'POST' }).then(j),
  },
};

// ---------- SSE chat ----------
export function streamChat({ message, structured, lat, lon, llm, embedding },
                           { onStart, onStatus, onDelta, onFinal, onError, signal }) {
  const ctrl = new AbortController();
  const outerSignal = signal;
  if (outerSignal) outerSignal.addEventListener('abort', () => ctrl.abort());

  (async () => {
    try {
      const r = await fetch(`${API}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, structured, lat, lon, llm, embedding }),
        signal: ctrl.signal,
      });
      if (!r.ok) {
        const text = await r.text();
        let msg = text;
        try { msg = JSON.parse(text).detail || text; } catch {}
        onError?.(`HTTP ${r.status}: ${typeof msg === 'string' ? msg : JSON.stringify(msg)}`);
        return;
      }
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          if (frame.startsWith('data: ')) {
            let evt;
            try { evt = JSON.parse(frame.slice(6)); } catch { continue; }
            if (evt.type === 'start') onStart?.();
            else if (evt.type === 'status') onStatus?.(evt.stage);
            else if (evt.type === 'delta') onDelta?.(evt.text);
            else if (evt.type === 'final') onFinal?.(evt);
            else if (evt.type === 'error') onError?.(evt.error);
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') onError?.(err.message || String(err));
    }
  })();

  return { abort: () => ctrl.abort() };
}
