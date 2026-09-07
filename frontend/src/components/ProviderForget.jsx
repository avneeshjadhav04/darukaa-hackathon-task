import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api/client';

export default function ProviderForget({ onForgot }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      className="btn sm danger"
      style={{ width: '100%', justifyContent: 'center' }}
      disabled={busy}
      onClick={async () => {
        if (!confirm('Forget all API keys held in server memory?')) return;
        setBusy(true);
        try {
          await api.config.forget();
          onForgot?.('All API keys forgotten');
        } catch (e) {
          onForgot?.(e.message, true);
        } finally {
          setBusy(false);
        }
      }}
    >
      <Trash2 size={13} /> Forget all keys
    </button>
  );
}
