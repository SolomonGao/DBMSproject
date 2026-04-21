import { useState, useEffect, useCallback } from 'react';
import { Calendar, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import type { DashboardData, TimeSeriesPoint, GeoPoint } from '../types';
import StatsCards from './StatsCards';
import TimeSeriesChart from './TimeSeriesChart';
import MapPanel from './MapPanel';

export default function Dashboard() {
  const today = '2024-01-31';
  const thirtyDaysAgo = '2024-01-01';

  const [startDate, setStartDate] = useState(thirtyDaysAgo);
  const [endDate, setEndDate] = useState(today);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [timeSeries, setTimeSeries] = useState<TimeSeriesPoint[]>([]);
  const [geoData, setGeoData] = useState<GeoPoint[]>([]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashRes, tsRes, geoRes] = await Promise.all([
        api.getDashboard(startDate, endDate),
        api.getTimeSeries(startDate, endDate, 'day'),
        api.getGeoHeatmap(startDate, endDate, 2),
      ]);

      if (dashRes.ok) setDashboard(dashRes.data || dashRes);
      else setError(dashRes.error || 'Dashboard failed');

      if (tsRes.ok) setTimeSeries(tsRes.data || []);

      if (geoRes.ok) setGeoData(geoRes.data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return (
    <div>
      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'white', padding: '8px 12px', borderRadius: 8 }}>
          <Calendar size={16} color="#666" />
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            style={{ border: 'none', outline: 'none', fontSize: 14 }}
          />
          <span style={{ color: '#999' }}>to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            style={{ border: 'none', outline: 'none', fontSize: 14 }}
          />
        </div>

        <button
          onClick={fetchAll}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 16px',
            background: '#2563eb',
            color: 'white',
            border: 'none',
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 500,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          {loading ? 'Loading...' : 'Refresh'}
        </button>

        {dashboard?._meta && (
          <span style={{ fontSize: 12, color: '#888' }}>
            Fetched in {dashboard._meta.elapsed_ms}ms
          </span>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* Stats */}
      <StatsCards data={dashboard} />

      {/* Charts Grid */}
      <div className="dashboard-grid">
        <TimeSeriesChart data={timeSeries} title="Daily Events & Conflict Rate" />
        <MapPanel data={geoData} title="Geographic Distribution" />
      </div>

      {/* Top Actors & Event Types */}
      <div className="dashboard-grid" style={{ marginTop: 16 }}>
        <div className="panel">
          <h3>Top Actors</h3>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e5e7eb', textAlign: 'left' }}>
                <th style={{ padding: '8px 0' }}>Actor</th>
                <th style={{ padding: '8px 0', textAlign: 'right' }}>Events</th>
              </tr>
            </thead>
            <tbody>
              {(dashboard?.top_actors?.data || []).map((actor: any, i: number) => (
                <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '6px 0' }}>{actor.actor || 'Unknown'}</td>
                  <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 600 }}>
                    {actor.event_count?.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h3>Event Types</h3>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e5e7eb', textAlign: 'left' }}>
                <th style={{ padding: '8px 0' }}>Type</th>
                <th style={{ padding: '8px 0', textAlign: 'right' }}>Count</th>
              </tr>
            </thead>
            <tbody>
              {(dashboard?.event_types?.data || []).map((et: any, i: number) => (
                <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '6px 0' }}>{et.event_type}</td>
                  <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 600 }}>
                    {et.event_count?.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
