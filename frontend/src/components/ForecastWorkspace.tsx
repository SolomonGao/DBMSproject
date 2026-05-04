import { useCallback, useEffect, useState } from 'react';
import { Calendar, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import type { ThpForecastResult, TimeSeriesPoint } from '../types';
import ComparePanel from './ComparePanel';
import ForecastPanel from './ForecastPanel';

type ForecastFocusMode = 'location' | 'actor';

function addDays(date: string, days: number) {
  const value = new Date(`${date}T00:00:00`);
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

function hasPairSeparator(value: string) {
  const lowered = value.toLowerCase();
  return [' and ', ' vs ', ' versus ', '/', ','].some((separator) => lowered.includes(separator));
}

export default function ForecastWorkspace() {
  const [forecastDate, setForecastDate] = useState('2024-01-31');
  const [forecastFocusMode, setForecastFocusMode] = useState<ForecastFocusMode>('location');
  const [forecastTarget, setForecastTarget] = useState('United States and Canada');
  const [forecastEventType, setForecastEventType] = useState('all');
  const [timeSeries, setTimeSeries] = useState<TimeSeriesPoint[]>([]);
  const [forecastResult, setForecastResult] = useState<ThpForecastResult | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const historyStartDate = addDays(forecastDate, -30);
  const historyEndDate = addDays(forecastDate, -1);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const trimmedTarget = forecastTarget.trim();
    const forecastTargetParams =
      forecastFocusMode === 'actor'
        ? hasPairSeparator(trimmedTarget)
          ? { region: trimmedTarget ? `actor_pair:${trimmedTarget}` : undefined }
          : { actor: trimmedTarget || undefined }
        : { region: trimmedTarget || undefined };
    try {
      const [forecastRes, healthRes] = await Promise.all([
        api.getForecast(historyStartDate, historyEndDate, {
          ...forecastTargetParams,
          event_type: forecastEventType,
          forecast_days: 7,
        }),
        api.health().catch(() => null),
      ]);
      setTimeSeries([]);
      if (forecastRes.ok && forecastRes.data?.ok !== false) {
        setForecastResult(forecastRes.data || null);
      } else {
        setForecastResult(null);
        setError(forecastRes.error || forecastRes.data?.error || 'Forecast failed');
      }
      if (healthRes) setHealth(healthRes);
    } catch (err: any) {
      setError(err.message || 'Forecast failed');
    } finally {
      setLoading(false);
    }
  }, [historyStartDate, historyEndDate, forecastFocusMode, forecastTarget, forecastEventType]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div>
      <div className="hero-panel">
        <div>
          <span className="eyebrow">Forecast Workspace</span>
          <h2>Risk Outlook & Scenario Compare</h2>
          <p>Select one forecast start date, then inspect the next seven projected days.</p>
        </div>
      </div>

      <div className="control-panel">
        <div className="date-control">
          <Calendar size={16} color="#666" />
          <span>Forecast start</span>
        <input type="date" value={forecastDate} onChange={(e) => setForecastDate(e.target.value)} />
        </div>
        <select
          className="compact-input"
          value={forecastFocusMode}
          onChange={(e) => setForecastFocusMode(e.target.value as ForecastFocusMode)}
          aria-label="Forecast target mode"
        >
          <option value="location">Location</option>
          <option value="actor">Actor</option>
        </select>
        <input
          className="compact-input"
          value={forecastTarget}
          onChange={(e) => setForecastTarget(e.target.value)}
          placeholder={
            forecastFocusMode === 'location'
              ? 'Location, e.g. Canada or United States and Canada'
              : 'Actor, e.g. POLICE or POLICE and GOVERNMENT'
          }
        />
        <select
          className="compact-input"
          value={forecastEventType}
          onChange={(e) => setForecastEventType(e.target.value)}
        >
          <option value="all">All events</option>
          <option value="conflict">Conflict</option>
          <option value="cooperation">Cooperation</option>
          <option value="protest">Protest</option>
        </select>
        <button className="primary-action" onClick={refresh} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <ForecastPanel
        data={timeSeries}
        forecastResult={forecastResult}
        health={health}
        forecastStartDate={forecastDate}
        historyStartDate={historyStartDate}
        historyEndDate={historyEndDate}
        title="THP Forecast Panel"
        sourceLabel={`Mode: ${forecastFocusMode}. Target: ${forecastTarget || 'Global'} | ${forecastEventType}. Input window: ${historyStartDate} to ${historyEndDate}.`}
      />
      <ComparePanel startDate={historyStartDate} endDate={historyEndDate} />
    </div>
  );
}
