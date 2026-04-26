import { useState } from 'react';
import { GitCompare, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import type { CompareResult } from '../types';

interface Props {
  startDate: string;
  endDate: string;
}

export default function ComparePanel({ startDate, endDate }: Props) {
  const [left, setLeft] = useState('United States');
  const [right, setRight] = useState('Canada');
  const [eventType, setEventType] = useState('any');
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runCompare = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.compareEntities(startDate, endDate, left, right, eventType);
      if (res.ok) setResult(res.data);
      else setError(res.error || 'Compare failed');
    } catch (err: any) {
      setError(err.message || 'Compare failed');
    } finally {
      setLoading(false);
    }
  };

  const maxTotal = Math.max(1, result?.left.total_events || 0, result?.right.total_events || 0);

  return (
    <section className="panel compare-panel">
      <div className="section-title-row">
        <div>
          <h3>Compare Mode</h3>
          <p>Compare countries, actors, or keywords over the selected date range.</p>
        </div>
        <GitCompare size={18} color="#2563eb" />
      </div>

      <div className="compare-controls">
        <input value={left} onChange={(e) => setLeft(e.target.value)} placeholder="First entity" />
        <input value={right} onChange={(e) => setRight(e.target.value)} placeholder="Second entity" />
        <select value={eventType} onChange={(e) => setEventType(e.target.value)}>
          <option value="any">All events</option>
          <option value="conflict">Conflict</option>
          <option value="cooperation">Cooperation</option>
          <option value="protest">Protest</option>
        </select>
        <button onClick={runCompare} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          Compare
        </button>
      </div>

      {error && <div className="inline-error">{error}</div>}

      {result ? (
        <div className="compare-results">
          {[result.left, result.right].map((side) => (
            <div className="compare-card" key={side.label}>
              <div className="compare-card-header">
                <strong>{side.label}</strong>
                <span>{side.rows.length} active days</span>
              </div>
              <div className="compare-total">{side.total_events.toLocaleString()}</div>
              <div className="compare-bar-track">
                <div
                  className="compare-bar-fill"
                  style={{ width: `${(side.total_events / maxTotal) * 100}%` }}
                />
              </div>
              <small>Avg Goldstein {side.avg_goldstein?.toFixed?.(2) ?? 'n/a'}</small>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">Run a comparison to see bilateral or actor-level trends.</div>
      )}
    </section>
  );
}
