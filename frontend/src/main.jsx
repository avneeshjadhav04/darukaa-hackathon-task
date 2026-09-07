import { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './App.css'

class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      const splash = document.getElementById('splash');
      if (splash) splash.remove();
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#ffffff', color: '#111111', fontFamily: 'Inter, system-ui, sans-serif',
          padding: 24,
        }}>
          <div style={{ maxWidth: 560, width: '100%' }}>
            <h2 style={{ color: '#c53030', marginTop: 0 }}>Something went wrong</h2>
            <pre style={{
              background: '#f7f7f4', border: '1px solid #e0e0da', padding: 14,
              fontSize: 12, overflow: 'auto', color: '#4a4a4a',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {String(this.state.error?.message || this.state.error)}
              {'\n\n'}{this.state.error?.stack || ''}
            </pre>
            <button
              onClick={() => location.reload()}
              style={{
                marginTop: 12, background: '#0a7d42', color: '#fff', border: 'none',
                padding: '9px 16px', fontWeight: 600, cursor: 'pointer',
              }}
            >
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// splash must stay visible at least this long, even on fast loads
const MIN_SPLASH_MS = 1000;

function dismissSplash() {
  const el = document.getElementById('splash');
  if (!el) return;
  const elapsed = performance.now() - (window.__splashShownAt || 0);
  const wait = Math.max(0, MIN_SPLASH_MS - elapsed);
  setTimeout(() => {
    el.classList.add('hide');
    setTimeout(() => el.remove(), 350);
  }, wait);
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)

// React has rendered — fade the splash out (covers bundle-parse + first-mount gap)
requestAnimationFrame(() => requestAnimationFrame(dismissSplash));
