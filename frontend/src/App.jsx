import { AlertCircle, CheckCircle2, Database, Globe, Settings } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import './App.css';
import { api, loadAutofetchPref, saveAutofetchPref } from './api/client';
import ChatWindow from './components/ChatWindow';
import IngestPanel from './components/IngestPanel';
import ProviderForget from './components/ProviderForget';
import ProviderForm from './components/ProviderForm';
import Section from './components/Section';

export default function App() {
  const [status, setStatus] = useState(null);
  const [toast, setToast] = useState(null);
  const [indexRefresh, setIndexRefresh] = useState(0);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [autofetch, setAutofetch] = useState(loadAutofetchPref);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const toastTimer = useRef(null);

  const showToast = useCallback((msg, isErr = false) => {
    setToast({ msg, isErr });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 6000);
  }, []);

  const refreshStatus = useCallback(async () => {
    try { setStatus(await api.config.status()); }
    catch (e) { showToast(`config: ${e.message}`, true); }
  }, [showToast]);

  useEffect(() => { refreshStatus(); }, [refreshStatus]);

  const llmReady = !!status?.llm?.has_key;
  const embReady = !!status?.embedding?.has_key;
  const providersReady = llmReady;   // chat requires LLM; embeddings optional (works without index)

  return (
    <div className={'app' + (sidebarOpen ? ' sidebar-open' : '')}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true" />
          <div>
            <h1>AI Environmental Scientist</h1>
            <p>Darukaa.Earth · biodiversity intelligence</p>
          </div>
        </div>

        <Section title="Ingest Documents" icon={Database}
                 badge={<span className="badge ok">RAG</span>}>
          <IngestPanel
            onToast={showToast}
            onIndexChanged={() => setIndexRefresh((k) => k + 1)}
            refreshKey={indexRefresh}
          />
        </Section>

        <Section title="Web-Fetch Fallback" icon={Globe}>
          <label className="pref-row">
            <input
              type="checkbox"
              checked={autofetch}
              onChange={(e) => { setAutofetch(e.target.checked); saveAutofetchPref(e.target.checked); }}
            />
            <span className="pref-text">
              <b>Let the AI fetch web sources on its own</b>
              <span>
                When the knowledge index has no relevant evidence, the agent proposes and
                ingests up to 2 public web pages (FAO/IPCC/IPBES-style sources) before
                answering. First answer may take a few seconds longer.
              </span>
            </span>
          </label>
          <p className="small-note">
            Same as "Fetch" in the Ingest section — paste any URL (FAO/IPCC/IPBES page, report
            landing page, etc.) and its readable text will be chunked, embedded and indexed.
            Use it when your local corpus is thin on a topic.
          </p>
          <p className="small-note">
            Tip: the chat will also tell you when the index is too thin to support a claim.
          </p>
        </Section>

        <Section title="Provider Config" icon={Settings}
                 badge={providersReady
                   ? <span className="badge ok">ready</span>
                   : <span className="badge bad">setup</span>}>
          <ProviderForm slot="llm" title="LLM (chat)" status={status?.llm}
                        onChanged={refreshStatus} onToast={showToast} />
          <ProviderForm slot="embedding" title="Embeddings" status={status?.embedding}
                        onChanged={refreshStatus} onToast={showToast} />
          <ProviderForget onForgot={(m, e) => { showToast(m, e); refreshStatus(); }} />
          {!providersReady && (
            <p className="small-note" style={{ marginTop: 10 }}>
              Chat is disabled until an LLM key is set (UI or <code>LLM_PROVIDER_API_KEY</code> env).
            </p>
          )}
        </Section>
      </aside>

      {sidebarOpen && <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />}

      <ChatWindow providersReady={providersReady} onToast={showToast} refreshKey={historyRefresh}
                  autofetch={autofetch} onMenuClick={() => setSidebarOpen(true)} />

      {toast && (
        <div className={'toast' + (toast.isErr ? ' err' : '')}>
          {toast.isErr ? <AlertCircle size={15} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: 1 }} />
                        : <CheckCircle2 size={15} style={{ color: 'var(--ok)', flexShrink: 0, marginTop: 1 }} />}
          <span>{toast.msg}</span>
        </div>
      )}
    </div>
  );
}
