import { FileUp, Link2, RotateCcw, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, loadProviderFields } from '../api/client';

export default function IngestPanel({ onToast, onIndexChanged, refreshKey }) {
  const [docs, setDocs] = useState([]);
  const [collection, setCollection] = useState(null);
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  const embFields = () => {
    const saved = loadProviderFields().embedding;
    return saved
      ? { provider_name: saved.provider_name, base_url: saved.base_url, model_name: saved.model_name }
      : {};
  };

  const reload = useCallback(async () => {
    try {
      const r = await api.ingest.index();
      setDocs(r.docs || []);
      setCollection(r.collection || null);
    } catch (e) {
      onToast?.(`index: ${e.message}`, true);
    }
  }, [onToast]);

  useEffect(() => { reload(); }, [reload, refreshKey]);

  async function doFile(file) {
    if (!file) return;
    setBusy(true);
    try {
      const r = await api.ingest.file(file, embFields());
      onToast?.(`Ingested "${r.ingested.name}" — ${r.ingested.chunks} chunks (+${r.structured_facts.chunks} facts)`);
      onIndexChanged?.();
    } catch (e) {
      onToast?.(e.message, true);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function doUrl() {
    if (!url.trim()) return;
    setBusy(true);
    try {
      const r = await api.ingest.url(url.trim(), embFields());
      onToast?.(`Fetched "${r.ingested.name}" — ${r.ingested.chunks} chunks`);
      setUrl('');
      onIndexChanged?.();
    } catch (e) {
      onToast?.(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function doDelete(name) {
    try {
      await api.ingest.delete(name, embFields());
      onToast?.(`Removed "${name}"`);
      onIndexChanged?.();
    } catch (e) {
      onToast?.(e.message, true);
    }
  }

  async function doReset() {
    if (!confirm('Reset the ENTIRE knowledge index (delete all chunks)?')) return;
    setBusy(true);
    try {
      await api.ingest.reset();
      onToast?.('Index reset');
      onIndexChanged?.();
    } catch (e) {
      onToast?.(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div
        className={'drop' + (dragOver ? ' over' : '')}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault(); setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) doFile(f);
        }}
      >
        <FileUp size={18} style={{ display: 'block', margin: '0 auto 6px' }} />
        {busy ? 'Working…' : 'Drop PDF/TXT/MD here, or click to choose'}
        <input
          ref={fileRef} type="file" accept=".pdf,.txt,.md" hidden
          onChange={(e) => doFile(e.target.files?.[0])}
        />
      </div>

      <div className="row" style={{ marginTop: 10 }}>
        <div className="flex field" style={{ marginBottom: 0 }}>
          <input value={url} onChange={(e) => setUrl(e.target.value)}
                 placeholder="https://… (fetch & ingest a web page)"
                 onKeyDown={(e) => e.key === 'Enter' && doUrl()} />
        </div>
        <button className="btn sm ghost" onClick={doUrl} disabled={busy || !url.trim()}>
          <Link2 size={13} /> Fetch
        </button>
      </div>

      {collection && collection.count !== undefined && (
        <div className="kv" style={{ marginTop: 10 }}>
          <span>Vector index</span>
          <span>{collection.count} chunks {collection.dim ? `· dim ${collection.dim}` : ''} {collection.model ? `· ${collection.model}` : ''}</span>
        </div>
      )}

      {docs.length > 0 && (
        <ul className="doc-list">
          {docs.map((d) => (
            <li key={d.name}>
              <span className="name" title={d.source}>{d.name}</span>
              <span className="meta">{d.kind} · {d.chunks} chunks</span>
              <button title="delete" onClick={() => doDelete(d.name)}><Trash2 size={13} /></button>
            </li>
          ))}
        </ul>
      )}

      {docs.length > 0 && (
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn sm ghost flex" onClick={reload}><RotateCcw size={13} /> Refresh</button>
          <button className="btn sm danger flex" onClick={doReset} disabled={busy}>Reset index</button>
        </div>
      )}
      <div className="small-note">
        Structured facts (quantified, cited rules) are auto-ingested with every upload.
        Switching embedding models with an existing index triggers a dimension guard.
      </div>
    </div>
  );
}
