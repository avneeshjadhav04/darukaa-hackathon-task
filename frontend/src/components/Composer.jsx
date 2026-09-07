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
  const hasGeoInput = showGeo && (lat.trim() !== '' || lon.trim() !== '');

  // consume a suggestion prompt if the parent hands one down
  useEffect(() => {
    if (initialPrompt) setText(initialPrompt);
  }, [initialPrompt]);

  function geoValue() {
    if (!showGeo) return null;
    const hasLat = lat.trim() !== '';
    const hasLon = lon.trim() !== '';
    if (!hasLat && !hasLon) return null;
    if (!hasLat || !hasLon) return { error: 'Enter both latitude and longitude.' };
    const la = parseFloat(lat);
    const lo = parseFloat(lon);
    if (isNaN(la) || isNaN(lo)) return { error: 'Latitude and longitude must be numbers.' };
    if (la < -90 || la > 90) return { error: 'Latitude must be between -90 and 90.' };
    if (lo < -180 || lo > 180) return { error: 'Longitude must be between -180 and 180.' };
    return { lat: la, lon: lo };
  }

  function send() {
    const geo = geoValue();
    if (geo?.error) { alert(geo.error); return; }
    const hasText = !!text.trim();
    const hasStructured = showStructured && !!structured.trim();
    if (!hasText && !hasStructured && !geo) return;
    let s = null;
    if (hasStructured) {
      try { s = JSON.parse(structured); }
      catch { alert('Structured input is not valid JSON'); return; }
    }
    const fallback = s && geo ? '[structured + geo input provided]'
      : s ? '[structured input provided]'
      : '[geo coordinates provided]';
    onSend({ message: text.trim() || fallback, structured: s, ...(geo || {}) });
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
              <input type="number" step="any" min="-90" max="90" value={lat}
                     onChange={(e) => setLat(e.target.value)} placeholder="latitude (-90…90, e.g. 28.61)" />
            </div>
            <div className="field flex" style={{ marginBottom: 0 }}>
              <input type="number" step="any" min="-180" max="180" value={lon}
                     onChange={(e) => setLon(e.target.value)} placeholder="longitude (-180…180, e.g. 77.20)" />
            </div>
          </div>
          <div className="hint" style={{ marginTop: 5 }}>
            Optional. Coordinates fill the region context — you can send geo alone, with a message, or with structured JSON.
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
        <button className="send-btn" onClick={send}
                disabled={disabled || (!text.trim() && !showStructured && !hasGeoInput)}
                title="Send">
          <SendHorizonal size={19} />
        </button>
      </div>
    </div>
  );
}
