import { Eraser, Leaf, Menu, User } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, loadProviderFields, streamChat } from '../api/client';
import Composer from './Composer';
import Markdown from './Markdown';
import RecCard from './RecCard';

const SUGGESTIONS = [
  'Biodiversity is declining on my land',
  'How do I raise soil carbon in a dry field?',
  'My monoculture wheat yields are falling',
];

export default function ChatWindow({ providersReady, onToast, refreshKey, autofetch = true, onMenuClick }) {
  const [messages, setMessages] = useState([]);
  const [slots, setSlots] = useState({});
  const [busy, setBusy] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [stage, setStage] = useState(null);
  const [prompt, setPrompt] = useState(null);
  const bottomRef = useRef(null);
  const accRef = useRef('');
  const flushTimer = useRef(null);
  const dirtyRef = useRef(false);

  const STAGE_LABELS = {
    extracting: 'Extracting context variables…',
    clarifying: 'Formulating clarifying questions…',
    retrieving: 'Retrieving evidence…',
    auto_fetching: 'Fetching web evidence…',
    reasoning: 'Reasoning across variables…',
    structuring: 'Structuring recommendations…',
  };

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
    setStage(null);
    setMessages((m) => [...m, { role: 'user', content: message || '[payload]', structured: structured ? { preview: true } : null }]);
    setStreamingText('');
    accRef.current = '';
    dirtyRef.current = false;
    // flush accumulated deltas to state at most every 80ms — keeps markdown
    // re-parsing off the hot path during fast token streams
    const flush = () => {
      flushTimer.current = null;
      if (!dirtyRef.current) return;
      dirtyRef.current = false;
      setStreamingText(accRef.current);
    };
    streamChat(
      { message, structured, lat, lon, autofetch, ...providerPayload() },
      {
        onStatus: (s) => setStage(s),
        onDelta: (t) => {
          accRef.current += t;
          dirtyRef.current = true;
          if (!flushTimer.current) flushTimer.current = setTimeout(flush, 80);
        },
        onFinal: (evt) => {
          if (flushTimer.current) { clearTimeout(flushTimer.current); flushTimer.current = null; }
          setBusy(false);
          setStage(null);
          setStreamingText('');
          setMessages((m) => [...m, { role: 'assistant', content: accRef.current, structured: evt.kind === 'answer' ? evt.data : null }]);
          if (evt.slots) setSlots(evt.slots);
        },
        onError: (err) => {
          if (flushTimer.current) { clearTimeout(flushTimer.current); flushTimer.current = null; }
          setBusy(false);
          setStage(null);
          setStreamingText('');
          setMessages((m) => [...m, { role: 'assistant', content: err, structured: { error: true } }]);
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
        <button className="menu-btn" aria-label="Open menu" onClick={onMenuClick}>
          <Menu size={18} />
        </button>
        <div className="title">
          <span className={'dot' + (providersReady ? ' on' : '')} />
          Biodiversity Intelligence
          {known > 0 && <span className="chip green">{known} context vars</span>}
        </div>
        <button className="btn sm ghost" onClick={clearAll}>
          <Eraser size={13} /> Clear chat
        </button>
      </div>

      <div className="transcript">
        {messages.length === 0 && !busy && (
          <div className="empty-state">
            <div className="empty-mark"><Leaf size={18} /></div>
            <div>
              <h2>AI Environmental Scientist</h2>
              <p className="sub">
                Describe a biodiversity problem, paste soil &amp; climate metrics, or send structured JSON.
                The system gathers what it needs, reasons across ≥3 variables, and returns
                evidence-backed, quantified recommendations with citations.
              </p>
            </div>
            <div className="suggest">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => setPrompt(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={'msg ' + m.role}>
            <div className="avatar">{m.role === 'user' ? <User size={16} /> : <Leaf size={16} />}</div>
            <div className="bubble">
              {m.role === 'assistant' && m.structured?.error
                ? <>{<b>⚠️ </b>}{m.content}</>
                : m.role === 'assistant'
                  ? <Markdown text={m.content} />
                  : m.content}
              {m.role === 'assistant' && m.structured?.analysis && <AnalysisBlock data={m.structured} />}
              {m.role === 'assistant' && m.structured?.recommendations && (
                <div>{m.structured.recommendations.map((r, j) => <RecCard key={j} rec={r} />)}</div>
              )}
              {m.role === 'assistant' && m.structured?.kind === 'clarify' && m.structured?.questions && (
                <div className="meta">Awaiting your answers ({m.structured.known}/{m.structured.needed} vars known).</div>
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="msg assistant">
            <div className="avatar"><Leaf size={16} /></div>
            <div className="bubble">
              {streamingText
                ? <><Markdown text={streamingText} /><span className="stream-cursor" /></>
                : <span className="stage-line"><span className="typing"><i /><i /><i /></span>{STAGE_LABELS[stage] || 'Thinking…'}</span>}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <Composer disabled={!providersReady || busy} onSend={send} initialPrompt={prompt} />
    </div>
  );
}

function AnalysisBlock({ data }) {
  const a = data.analysis;
  return (
    <div className="rec-card rec-analysis">
      <div className="conn">
        {a.variables_connected?.map((v, i) => (
          <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span className="conn-var">{v}</span>
            {i < a.variables_connected.length - 1 && <span style={{ color: 'var(--warn)' }}>↔</span>}
          </span>
        ))}
      </div>
      <div className="row">{a.causal_chain}</div>
      {a.clarifying_notes && <div className="row"><b>Notes:</b> {a.clarifying_notes}</div>}
      {data.overall_confidence && (
        <div className="src-line">
          <span>Overall confidence:</span>
          <span className="src-chip">{data.overall_confidence}</span>
        </div>
      )}
    </div>
  );
}
