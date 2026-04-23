import { useState, useEffect, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import type { DashboardData, TimeSeriesPoint, GeoPoint, EventItem, GeoEventPoint, FilterState } from '../types';
import type { GeoEventPoint as GeoEventPointType } from '../types';
import StatsCards from './StatsCards';
import TimeSeriesChart from './TimeSeriesChart';
import MapPanel from './MapPanel';
import FilterBar from './FilterBar';
import EventTimeline from './EventTimeline';

export default function Dashboard() {
  const today = '2024-01-31';
  const thirtyDaysAgo = '2024-01-01';

  const [filters, setFilters] = useState<FilterState>({
    startDate: thirtyDaysAgo,
    endDate: today,
    location: '',
    locationExact: '',
    actor: '',
    actorExact: '',
    eventType: 'any',
    keyword: '',
  });

  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [timeSeries, setTimeSeries] = useState<TimeSeriesPoint[]>([]);
  const [geoData, setGeoData] = useState<GeoPoint[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [geoEvents, setGeoEvents] = useState<GeoEventPoint[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Default dashboard fetch (heatmap + stats)
  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashRes, tsRes, geoRes] = await Promise.all([
        api.getDashboard(filters.startDate, filters.endDate),
        api.getTimeSeries(filters.startDate, filters.endDate, 'day'),
        api.getGeoHeatmap(filters.startDate, filters.endDate, 2),
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
  }, [filters.startDate, filters.endDate]);

  // Search events with filters
  const searchEvents = useCallback(async () => {
    setSearchLoading(true);
    setError(null);
    try {
      const [eventsRes, geoEventsRes] = await Promise.all([
        api.searchEvents(
          filters.keyword || undefined,
          filters.startDate,
          filters.endDate,
          filters.location || undefined,
          filters.locationExact || undefined,
          filters.eventType,
          filters.actor || undefined,
          filters.actorExact || undefined,
          50
        ),
        api.getGeoEvents(
          filters.startDate,
          filters.endDate,
          filters.location || undefined,
          filters.locationExact || undefined,
          filters.eventType,
          filters.actor || undefined,
          filters.actorExact || undefined,
          100
        ),
      ]);

      if (eventsRes.ok) {
        setEvents(eventsRes.data || []);
      } else {
        setError(eventsRes.error || 'Event search failed');
        setEvents([]);
      }

      if (geoEventsRes.ok) {
        setGeoEvents(geoEventsRes.data || []);
      } else {
        setGeoEvents([]);
      }

      setHasSearched(true);
      setSelectedEvent(null);
    } catch (err: any) {
      setError(err.message || 'Failed to search events');
      setEvents([]);
      setGeoEvents([]);
    } finally {
      setSearchLoading(false);
    }
  }, [filters]);

  // Initial load
  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const handleSelectEvent = useCallback((ev: EventItem) => {
    setSelectedEvent(ev);
  }, []);

  // Determine map mode: if user has searched and we have geo events, show event points
  const showEventPoints = hasSearched && geoEvents.length > 0;

  return (
    <div>
      {/* Filter Bar */}
      <FilterBar
        filters={filters}
        onChange={setFilters}
        onSearch={searchEvents}
        loading={searchLoading}
      />

      {/* Action Bar */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        <button
          onClick={fetchDashboard}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 14px',
            background: '#f3f4f6',
            color: '#374151',
            border: '1px solid #e5e7eb',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          Refresh Dashboard
        </button>

        {hasSearched && (
          <span style={{ fontSize: 12, color: '#8b5cf6', fontWeight: 500 }}>
            {events.length} events matched
          </span>
        )}

        {dashboard?._meta && (
          <span style={{ fontSize: 12, color: '#888' }}>
            Dashboard in {dashboard._meta.elapsed_ms}ms
          </span>
        )}
      </div>

      {error && (
        <div className="error-banner" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      {/* Stats */}
      <StatsCards data={dashboard} />

      {/* Charts Grid */}
      <div className="dashboard-grid">
        <TimeSeriesChart data={timeSeries} title="Daily Events & Conflict Rate" />
        <MapPanel
          data={showEventPoints ? undefined : geoData}
          eventPoints={showEventPoints ? geoEvents : undefined}
          title={showEventPoints ? `Event Locations (${geoEvents.length})` : 'Geographic Distribution'}
          selectedEventId={selectedEvent?.GlobalEventID}
          onEventSelect={(gp: GeoEventPointType) => {
            const found = events.find(e => e.GlobalEventID === gp.GlobalEventID);
            if (found) setSelectedEvent(found);
          }}
        />
      </div>

      {/* Event Timeline + Detail */}
      {hasSearched && (
        <div className="dashboard-grid" style={{ marginTop: 16 }}>
          <EventTimeline
            events={events}
            selectedEventId={selectedEvent?.GlobalEventID}
            onSelectEvent={handleSelectEvent}
          />

          {/* Event Detail Panel */}
          <div className="panel" style={{ maxHeight: 600, overflow: 'auto' }}>
            {selectedEvent ? (
              <div>
                <h3 style={{ marginBottom: 12 }}>Event Detail</h3>
                <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                  <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8, color: '#1f2937' }}>
                    {selectedEvent.headline || `${selectedEvent.Actor1Name || 'Unknown'} vs ${selectedEvent.Actor2Name || 'Unknown'}`}
                  </div>
                  <div style={{ color: '#6b7280', marginBottom: 12 }}>
                    ID: {selectedEvent.GlobalEventID} | Date: {selectedEvent.SQLDATE}
                  </div>

                  <DetailRow label="Actor 1" value={selectedEvent.Actor1Name} />
                  <DetailRow label="Actor 2" value={selectedEvent.Actor2Name} />
                  <DetailRow label="Location" value={selectedEvent.ActionGeo_FullName} />
                  <DetailRow label="Country" value={selectedEvent.ActionGeo_CountryCode} />
                  <DetailRow label="Event Code" value={selectedEvent.EventCode} />
                  <DetailRow label="Event Type" value={selectedEvent.event_type_label} />
                  <DetailRow label="Goldstein Scale" value={selectedEvent.GoldsteinScale?.toFixed(2)} />
                  <DetailRow label="Avg Tone" value={selectedEvent.AvgTone?.toFixed(2)} />
                  <DetailRow label="Articles" value={selectedEvent.NumArticles?.toLocaleString()} />
                  <DetailRow label="Fingerprint" value={selectedEvent.fingerprint} />

                  {selectedEvent.summary && (
                    <div style={{ marginTop: 12, padding: 10, background: '#f9fafb', borderRadius: 6 }}>
                      <div style={{ fontWeight: 600, marginBottom: 4, color: '#374151' }}>Summary</div>
                      <div style={{ color: '#4b5563' }}>{selectedEvent.summary}</div>
                    </div>
                  )}

                  {selectedEvent.ActionGeo_Lat && selectedEvent.ActionGeo_Long && (
                    <div style={{ marginTop: 12, fontSize: 12, color: '#6b7280' }}>
                      Coordinates: {selectedEvent.ActionGeo_Lat.toFixed(4)}, {selectedEvent.ActionGeo_Long.toFixed(4)}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>
                <p>Select an event from the timeline to view details.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Default Top Actors & Event Types (only when no search active) */}
      {!hasSearched && (
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
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | number | null }) {
  if (value === undefined || value === null || value === '') return null;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f3f4f6' }}>
      <span style={{ color: '#6b7280' }}>{label}</span>
      <span style={{ color: '#1f2937', fontWeight: 500 }}>{value}</span>
    </div>
  );
}
