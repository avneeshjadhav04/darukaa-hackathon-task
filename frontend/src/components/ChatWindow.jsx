import { Eraser } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, loadProviderFields, streamChat } from '../api/client';
import Composer from './Composer';
import RecCard from './RecCard';

export default function ChatWindow({ providersReady, onToast, refreshKey }) {
  const [messages, setMessages] = useState([]);   // {role, content, structured}
  const [slots, setSlots] = useState({});
  const [busy, setBusy] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.chat.history();
        setMessages(r.messages || []);
        setSlots(r.slots || {});
      } catch (e) { onToast?.(`history: ${e.message}`, true); }
    })();
  }, [onToast, refreshKey]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  function providerPayload() {
    const saved = loadProviderFields();
    const pick = (k) => (saved[k] ? { provider_name: saved[k].provider_name, base_url: saved[k].base_url, model_name: saved[k].model_name } : null);
    return { llm: pick('llm'), embedding: pick('embedding') };
  }

  function send({ message, structured, lat, lon }) {
    if (busy) return;
    setBusy(true);
    setMessages((m) => [...m, { role: 'user', content: message || '[payload]', structured: structured ? { preview: true } : null }]);
    setStreamingText('');
    let acc = '';
    streamChat(
      { message, structured, lat, lon, ...providerPayload() },
      {
        onDelta: (t) => { acc += t; setStreamingText(acc); },
        onFinal: (evt) => {
          setBusy(false);
          setStreamingText('');
          setMessages((m) => [...m, { role: 'assistant', content: acc, structured: evt.kind === 'answer' ? evt.data : null }]);
          if (evt.slots) setSlots(evt.slots);
        },
        onError: (err) => {
          setBusy(false);
          setStreamingText('');
          setMessages((m) => [...m, { role: 'assistant', content: `⚠️ ${err}`, structured: { error: true } }]);
          onToast?.(err, true);
        },
      },
    );
  }

  async function clearAll() {
    if (!confirm('Clear the entire chat thread? This cannot be undone.')) return;
    await api.chat.clear();
    setMessages([]);
    setSlots({});
    onToast?.('Chat cleared');
  }

  const known = Object.values(slots).filter(Boolean).length;

  return (
    <div className="main">
      <div className="chat-head">
        <div className="title">
          <span className={'dot' + (providersReady ? ' on' : '')} />
          Biodiversity Intelligence
          {known > 0 && <span className="badge ok">{known} context vars known</span>}
        </div>
        <button className="btn sm ghost" onClick={clearAll}>
          <Eraser size={13} /> Clear chat
        </button>
      </div>

      <div className="transcript">
        {messages.length === 0 && !busy && (
          <div className="empty-state">
            <b>AI Environmental Scientist</b><br />
            Describe a biodiversity problem on your land, paste soil/climate metrics,
            or send structured JSON. The system will ask for any missing variables it needs
            (it reasons across ≥3), then produce evidence-backed recommendations with citations
            from your knowledge base.
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={'msg ' + m.role}>
            <div className="bubble">
              {m.content}
              {m.role === 'assistant' && m.structured?.analysis && (
                <AnalysisBlock data={m.structured} />
              )}
              {m.role === 'assistant' && m.structured?.recommendations && (
                <div>{m.structured.recommendations.map((r, j) => <RecCard key={j} rec={r} />)}</div>
              )}
              {m.structured?.kind === 'clarify' && m.structured?.questions && (
                <div className="meta">Awaiting your answers to proceed ({m.structured.known}/{m.structured.needed} vars known).</div>
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="msg assistant">
            <div className="bubble">
              {streamingText ? streamingText : <span className="typing"><i /><i /><i /></span>}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <Composer disabled={!providersReady || busy} onSend={send} />
    </div>
  );
}

function AnalysisBlock({ data }) {
  const a = data.analysis;
  return (
    <div className="rec-card" style={{ borderLeftColor: 'var(--warn)' }}>
      <div className="row"><b>Connects:</b> {a.variables_connected.join(' ↔ ')}</div>
      <div className="row">{a.causal_chain}</div>
      {a.clarifying_notes && <div className="row"><b>Notes:</b> {a.clarifying_notes}</div>}
      {data.overall_confidence && <div className="src-line">Overall confidence: {data.overall_confidence}</div>}
    </div>
  );
}
