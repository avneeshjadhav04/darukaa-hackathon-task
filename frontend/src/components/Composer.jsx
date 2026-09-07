import { Braces, MapPin, SendHorizonal } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function Composer({ disabled, onSend, initialPrompt }) {
  const [text, setText] = useState('');
  const [showStructured, setShowStructured] = useState(false);
  const [showGeo, setShowGeo] = useState(false);
  const [structured, setStructured] = useState(JSON.stringify({
    soil_organic_carbon_pct: '0.3',
    rainfall: 'low',
    crop: 'monoculture wheat',
    region: 'semi-arid',
  }, null, 2));
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');

  // consume a suggestion prompt if the parent hands one down
  useEffect(() => {
    if (initialPrompt) setText(initialPrompt);
  }, [initialPrompt]);

  function send() {
    if (!text.trim() && !showStructured) return;
    let s = null;
    if (showStructured && structured.trim()) {
      try { s = JSON.parse(structured); }
      catch { alert('Structured input is not valid JSON'); return; }
    }
    const g = (showGeo && lat && lon) ? { lat: parseFloat(lat), lon: parseFloat(lon) } : {};
    if (showGeo && (isNaN(g.lat) || isNaN(g.lon))) { alert('lat/lon must be numbers'); return; }
    onSend({ message: text.trim() || (s ? '[structured input provided]' : ''), structured: s, ...g });
    setText('');
  }

  return (
    <div className="composer">
      {showStructured && (
        <div className="details-panel">
          <textarea value={structured} onChange={(e) => setStructured(e.target.value)} spellCheck={false} />
          <div className="hint" style={{ marginTop: 5 }}>
            JSON object of environmental variables — soil_organic_carbon_pct, rainfall, land_use, crop, region…
          </div>
        </div>
      )}
      {showGeo && (
        <div className="details-panel">
          <div className="geo">
            <div className="field flex" style={{ marginBottom: 0 }}>
              <input value={lat} onChange={(e) => setLat(e.target.value)} placeholder="latitude (e.g. 28.61)" />
            </div>
            <div className="field flex" style={{ marginBottom: 0 }}>
              <input value={lon} onChange={(e) => setLon(e.target.value)} placeholder="longitude (e.g. 77.20)" />
            </div>
          </div>
        </div>
      )}

      <div className="row">
        <div className="composer-box">
          <textarea
            placeholder={disabled ? 'Configure providers in the sidebar to start…' : 'Describe your land problem, or paste metrics…'}
            value={text}
            disabled={disabled}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          />
          <div className="toggles">
            <label className={'toggle-chip' + (showStructured ? ' active' : '')}>
              <input type="checkbox" checked={showStructured} onChange={(e) => setShowStructured(e.target.checked)} />
              <Braces size={13} /> structured
            </label>
            <label className={'toggle-chip' + (showGeo ? ' active' : '')}>
              <input type="checkbox" checked={showGeo} onChange={(e) => setShowGeo(e.target.checked)} />
              <MapPin size={13} /> geo
            </label>
          </div>
        </div>
        <button className="send-btn" onClick={send} disabled={disabled || (!text.trim() && !showStructured)}
                title="Send">
          <SendHorizonal size={19} />
        </button>
      </div>
    </div>
  );
}
