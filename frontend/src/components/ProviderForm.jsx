import { Bot, CheckCircle2, Cpu, KeyRound, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, loadProviderFields, saveProviderFields } from '../api/client';

/** One provider block (LLM or Embeddings).
 *  Non-secret fields persist in localStorage; the API key goes to server memory only. */
export default function ProviderForm({ slot, title, status, onChanged, onToast }) {
  const saved = loadProviderFields()[slot] || {};
  const env = status?.env_defaults || {};
  const init = {
    provider_name: saved.provider_name ?? env.provider_name ?? '',
    base_url: saved.base_url ?? env.base_url ?? '',
    model_name: saved.model_name ?? env.model_name ?? '',
  };
  const [form, setForm] = useState({ ...init, api_key: '' });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  // Seed from env defaults when they arrive, and persist any values we filled
  // (so a refresh keeps them) — but never if the user already set them.
  useEffect(() => {
    const all = loadProviderFields();
    const s = all[slot] || {};
    const merged = {
      provider_name: s.provider_name ?? env.provider_name ?? '',
      base_url: s.base_url ?? env.base_url ?? '',
      model_name: s.model_name ?? env.model_name ?? '',
    };
    if (!s.provider_name && env.provider_name) {
      all[slot] = merged;
      saveProviderFields(all);   // persist env-seeded non-secret defaults
    }
    setForm({ ...merged, api_key: '' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.env_defaults?.provider_name, status?.env_defaults?.base_url, status?.env_defaults?.model_name]);

  const set = (k) => (e) => {
    const v = e.target.value;
    setForm((f) => {
      const next = { ...f, [k]: v };
      // persist non-secret fields immediately
      const all = loadProviderFields();
      all[slot] = { provider_name: next.provider_name, base_url: next.base_url, model_name: next.model_name };
      saveProviderFields(all);
      return next;
    });
  };

  async function saveAndTest(testOnly = false) {
    setTesting(true);
    setTestResult(null);
    try {
      if (form.api_key) await api.config.setKey(slot, form.api_key);
      const payload = {
        [slot]: {
          provider_name: form.provider_name,
          base_url: form.base_url,
          model_name: form.model_name,
        },
      };
      const res = await api.config.test(payload);
      setTestResult(res[slot] || null);
      if (!testOnly) setForm((f) => ({ ...f, api_key: '' })); // never keep key in the form
      onChanged?.();
      if (res[slot]?.ok) onToast?.(`${title} connection OK${res[slot]?.embedding_dim ? ` (dim ${res[slot].embedding_dim})` : ''}`);
      else onToast?.(`${title}: ${res[slot]?.error || 'connection failed'}`, true);
    } catch (e) {
      setTestResult({ ok: false, error: e.message });
      onToast?.(`${title}: ${e.message}`, true);
    } finally {
      setTesting(false);
    }
  }

  async function forgetKey() {
    await api.config.setKey(slot, '');   // clears by setting empty; server treats '' as cleared? -> use forget for all
    onChanged?.();
    onToast?.(`${title} key cleared for next requests (use "Forget all keys" below to wipe server memory)`);
  }

  const hasKey = status?.has_key;
  const Icon = slot === 'llm' ? Bot : Cpu;
  const keyPill = hasKey
    ? <span className={'pill ' + (status.key_source === 'env' ? 'warn' : 'ok')}>
        {status.key_source === 'env' ? 'env key' : status.key_tail}
      </span>
    : <span className="pill bad">no key</span>;
  return (
    <div className="provider-block">
      <div className="head">
        <b>{Icon}{title}</b>
        {keyPill}
      </div>

      <div className="field">
        <label>Provider name</label>
        <input value={form.provider_name} onChange={set('provider_name')} placeholder="openai / ollama / azure…" />
      </div>
      <div className="field">
        <label>Base URL</label>
        <input value={form.base_url} onChange={set('base_url')} placeholder="https://api.openai.com/v1 (or your endpoint)" />
      </div>
      <div className="field">
        <label>Model name</label>
        <input value={form.model_name} onChange={set('model_name')} placeholder={slot === 'llm' ? 'gpt-4o-mini' : 'text-embedding-3-small'} />
      </div>
      <div className="field">
        <label>API key {hasKey && <span style={{ color: 'var(--accent)' }}>({status.key_source})</span>}</label>
        <input
          type="password"
          value={form.api_key}
          onChange={set('api_key')}
          placeholder={hasKey ? 'key set — enter to replace' : 'paste key (memory only, never saved)'}
          autoComplete="off"
        />
        <div className="hint">Stored in server memory only; cleared on restart/inactivity. Non-secret fields persist in your browser.</div>
      </div>

      <div className="row">
        <button className="btn sm primary flex" onClick={() => saveAndTest(false)} disabled={testing}>
          <KeyRound size={13} /> Save & Test
        </button>
        <button className="btn sm ghost" onClick={forgetKey} disabled={!hasKey}>
          Clear key
        </button>
      </div>

      {testResult && (
        <div className="inline-status" style={{ color: testResult.ok ? 'var(--ok)' : 'var(--danger)' }}>
          {testResult.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
          <span>
            {testResult.ok
              ? `Connected${testResult.embedding_dim ? ` · embedding dim ${testResult.embedding_dim}` : ''}`
              : `Failed: ${testResult.error || 'unknown error'}`}
          </span>
        </div>
      )}
      <div className="small-note">
        Fallback env vars: <code>{slot === 'llm' ? 'LLM_PROVIDER_*' : 'EMBEDDING_PROVIDER_*'}</code>
      </div>
    </div>
  );
}
