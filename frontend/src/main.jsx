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

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
