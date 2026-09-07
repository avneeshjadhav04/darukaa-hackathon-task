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
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#080c0a', color: '#e9f0ea', fontFamily: 'Inter, system-ui, sans-serif',
          padding: 24,
        }}>
          <div style={{ maxWidth: 560, width: '100%' }}>
            <h2 style={{ color: '#fb7185', marginTop: 0 }}>Something went wrong</h2>
            <pre style={{
              background: '#111815', border: '1px solid #223028', borderRadius: 10,
              padding: 14, fontSize: 12, overflow: 'auto', color: '#b9c6bc',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {String(this.state.error?.message || this.state.error)}
              {'\n\n'}{this.state.error?.stack || ''}
            </pre>
            <button
              onClick={() => location.reload()}
              style={{
                marginTop: 12, background: '#34d399', color: '#06251b', border: 'none',
                padding: '9px 16px', borderRadius: 10, fontWeight: 600, cursor: 'pointer',
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

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
