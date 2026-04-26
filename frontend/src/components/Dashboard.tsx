import { useState, useEffect, useCallback } from 'react';
import { Calendar, RefreshCw, Search, Sparkles } from 'lucide-react';
import { api } from '../api/client';
import type { DashboardData, EventItem, GeoPoint, TimeSeriesPoint } from '../types';
import StatsCards from './StatsCards';
import TimeSeriesChart from './TimeSeriesChart';
import MapPanel from './MapPanel';
import EventDrawer from './EventDrawer';
import ReportExport from './ReportExport';

const MONTHS: Record<string, string> = {
  january: '01',
  february: '02',
  march: '03',
  april: '04',
  may: '05',
  june: '06',
  july: '07',
  august: '08',
  september: '09',
  october: '10',
  november: '11',
  december: '12',
};

const COUNTRY_HINTS = ['United States', 'Canada', 'Mexico', 'China', 'Russia', 'Israel', 'Ukraine'];

function monthNumber(monthName: string) {
  return MONTHS[monthName.toLowerCase()];
}

function formatDate(year: string, monthName: string, day: string) {
  const month = monthNumber(monthName);
  if (!month) return null;
  return `${year}-${month}-${day.padStart(2, '0')}`;
}

function parseNaturalDateRange(text: string) {
  const year = text.match(/20\d{2}/)?.[0] || '2024';
  const monthNames = Object.keys(MONTHS).join('|');
  const fullRange = new RegExp(
    `\\b(${monthNames})\\s+(\\d{1,2})(?:st|nd|rd|th)?\\s*,?\\s*(20\\d{2})?\\s+(?:to|through|until|-)\\s+(${monthNames})\\s+(\\d{1,2})(?:st|nd|rd|th)?\\s*,?\\s*(20\\d{2})?`,
    'i',
  );
  const sameMonthRange = new RegExp(
    `\\b(${monthNames})\\s+(\\d{1,2})(?:st|nd|rd|th)?\\s+(?:to|through|until|-)\\s+(\\d{1,2})(?:st|nd|rd|th)?\\s*,?\\s*(20\\d{2})?`,
    'i',
  );
  const singleDay = new RegExp(
    `\\b(${monthNames})\\s+(\\d{1,2})(?:st|nd|rd|th)?\\s*,?\\s*(20\\d{2})?`,
    'i',
  );

  const fullMatch = text.match(fullRange);
  if (fullMatch) {
    const start = formatDate(fullMatch[3] || year, fullMatch[1], fullMatch[2]);
    const end = formatDate(fullMatch[6] || fullMatch[3] || year, fullMatch[4], fullMatch[5]);
    if (start && end) return { start, end };
  }

  const sameMonthMatch = text.match(sameMonthRange);
  if (sameMonthMatch) {
    const start = formatDate(sameMonthMatch[4] || year, sameMonthMatch[1], sameMonthMatch[2]);
    const end = formatDate(sameMonthMatch[4] || year, sameMonthMatch[1], sameMonthMatch[3]);
    if (start && end) return { start, end };
  }

  const dayMatch = text.match(singleDay);
  if (dayMatch) {
    const date = formatDate(dayMatch[3] || year, dayMatch[1], dayMatch[2]);
    if (date) return { start: date, end: date };
  }

  const month = Object.entries(MONTHS).find(([name]) => text.includes(name));
  if (month) {
    const monthIndex = Number(month[1]);
    const lastDay = new Date(Number(year), monthIndex, 0).getDate();
    return {
      start: `${year}-${month[1]}-01`,
      end: `${year}-${month[1]}-${String(lastDay).padStart(2, '0')}`,
    };
  }

  return null;
}

function codedLabel(value: unknown, fallback: string) {
  const text = String(value || '').trim();
  return text && text.toLowerCase() !== 'unknown' ? text : fallback;
}

function eventActor(event: any) {
  return codedLabel(event.Actor1Name || event.actor1_name, 'Actor not coded');
}

function eventTarget(event: any) {
  return codedLabel(event.Actor2Name || event.actor2_name, 'No second actor coded');
}

function eventDate(event: any) {
  return event.SQLDATE || event.sql_date || '';
}

function eventGoldstein(event: any) {
  return event.GoldsteinScale ?? event.goldstein_scale ?? 'n/a';
}

function eventLocation(event: any) {
  return codedLabel(event.ActionGeo_FullName || event.action_geo_full_name, 'Location not coded');
}

function eventId(event: any) {
  return event.GlobalEventID || event.global_event_id;
}

export default function Dashboard() {
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-01-31');
  const [eventType, setEventType] = useState('any');
  const [focusMode, setFocusMode] = useState<'location' | 'actor'>('location');
  const [focusRegion, setFocusRegion] = useState('');
  const [naturalQuery, setNaturalQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [timeSeries, setTimeSeries] = useState<TimeSeriesPoint[]>([]);
  const [geoData, setGeoData] = useState<GeoPoint[]>([]);
  const [topEvents, setTopEvents] = useState<EventItem[]>([]);
  const [selectedHotspot, setSelectedHotspot] = useState<GeoPoint | null>(null);
  const [hotspotEvents, setHotspotEvents] = useState<EventItem[]>([]);
  const [hotspotLoading, setHotspotLoading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<any>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    const globalFilters = {
      region: focusRegion || undefined,
      focus_type: focusMode,
      event_type: eventType === 'any' ? undefined : eventType,
    };
    try {
      const [dashRes, tsRes, geoRes, topRes] = await Promise.all([
        api.getDashboard(startDate, endDate, globalFilters),
        api.getTimeSeries(startDate, endDate, 'day', globalFilters),
        api.getGeoHeatmap(startDate, endDate, 2, globalFilters),
        api.getTopEvents(startDate, endDate, {
          region: globalFilters.region,
          focus_type: globalFilters.focus_type,
          event_type: globalFilters.event_type,
          limit: 10,
        }),
      ]);

      if (dashRes.ok) setDashboard(dashRes.data || dashRes);
      else setError(dashRes.error || 'Dashboard failed');

      if (tsRes.ok) setTimeSeries(tsRes.data || []);
      if (geoRes.ok) {
        setGeoData(geoRes.data || []);
        setSelectedHotspot(null);
      }
      if (topRes.ok) setTopEvents(topRes.data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, focusRegion, focusMode, eventType]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      fetchAll();
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [fetchAll]);

  useEffect(() => {
    if (!selectedHotspot) {
      setHotspotEvents([]);
      setHotspotLoading(false);
      return;
    }

    let active = true;
    setHotspotEvents([]);
    setHotspotLoading(true);

    api.searchEvents(focusMode === 'actor' && focusRegion ? focusRegion : 'events', 8, {
      start: startDate,
      end: endDate,
      lat: selectedHotspot.lat,
      lng: selectedHotspot.lng,
      precision: 2,
      focus_type: focusMode,
      location_hint: selectedHotspot.sample_location || focusRegion || undefined,
      event_type: eventType === 'any' ? undefined : eventType,
    })
      .then((res) => {
        if (active) setHotspotEvents(res.ok ? res.data || [] : []);
      })
      .catch(() => {
        if (active) setHotspotEvents([]);
      })
      .finally(() => {
        if (active) setHotspotLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedHotspot, startDate, endDate, focusRegion, focusMode, eventType]);

  const applyNaturalFilter = () => {
    const text = naturalQuery.toLowerCase();
    const parsedDateRange = parseNaturalDateRange(text);
    if (parsedDateRange) {
      setStartDate(parsedDateRange.start);
      setEndDate(parsedDateRange.end);
    }
    if (text.includes('conflict')) setEventType('conflict');
    else if (text.includes('cooperation')) setEventType('cooperation');
    else if (text.includes('protest')) setEventType('protest');

    const country = COUNTRY_HINTS.find((item) => text.includes(item.toLowerCase()));
    if (country) {
      setFocusMode('location');
      setFocusRegion(country);
    }
  };

  const openEvent = async (event: EventItem) => {
    setSelectedEvent(event);
    setSelectedDetail(null);
    const id = event.fingerprint || `EVT-${eventDate(event)}-${eventId(event)}`;
    if (!id || id.includes('undefined')) return;
    try {
      const res = await api.getEventDetail(id);
      if (res.ok) setSelectedDetail(res.data);
    } catch {
      setSelectedDetail(null);
    }
  };

  return (
    <div>
      <div className="hero-panel">
        <div>
          <span className="eyebrow">Interactive Analysis</span>
          <h2>GDELT Event Intelligence</h2>
          <p>Filter, inspect, map, and export one dashboard workspace.</p>
        </div>
        <ReportExport
          dashboard={dashboard}
          timeSeries={timeSeries}
          events={topEvents}
          startDate={startDate}
          endDate={endDate}
          region={focusRegion ? `${focusMode}: ${focusRegion}` : ''}
          eventType={eventType}
        />
      </div>

      <div className="control-panel">
        <div className="date-control">
          <Calendar size={16} color="#666" />
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          <span>to</span>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>

        <select
          className="compact-input"
          value={focusMode}
          onChange={(e) => setFocusMode(e.target.value as 'location' | 'actor')}
          aria-label="Focus filter mode"
        >
          <option value="location">Location</option>
          <option value="actor">Actor</option>
        </select>

        <input
          className="compact-input"
          value={focusRegion}
          onChange={(e) => setFocusRegion(e.target.value)}
          placeholder={focusMode === 'location' ? 'Location, e.g. Canada' : 'Actor, e.g. POLICE'}
        />

        <select className="compact-input" value={eventType} onChange={(e) => setEventType(e.target.value)}>
          <option value="any">All events</option>
          <option value="conflict">Conflict</option>
          <option value="cooperation">Cooperation</option>
          <option value="protest">Protest</option>
        </select>

        <button className="primary-action" onClick={fetchAll} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <div className="natural-filter">
        <Search size={15} />
        <input
          value={naturalQuery}
          onChange={(e) => setNaturalQuery(e.target.value)}
          placeholder="Try: Canada conflict in January 15 2024 to January 20 2024"
        />
        <button onClick={applyNaturalFilter}>
          <Sparkles size={14} />
          Apply
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading && !dashboard ? (
        <div className="skeleton-grid">
          <div />
          <div />
          <div />
          <div />
        </div>
      ) : (
        <StatsCards data={dashboard} />
      )}

      <div className="dashboard-grid">
        <TimeSeriesChart data={timeSeries} title="Daily Events & Conflict Rate" />
        <MapPanel
          data={geoData}
          title="Geographic Distribution"
          onPointSelect={(point) => setSelectedHotspot(point)}
        />
      </div>

      {selectedHotspot && (
        <div className="panel hotspot-panel">
          <div className="section-title-row">
            <div>
              <h3>Map Hotspot Drilldown</h3>
              <p>
                {selectedHotspot.sample_location || `${selectedHotspot.lat}, ${selectedHotspot.lng}`} - intensity{' '}
                {selectedHotspot.intensity}
              </p>
            </div>
            <button className="ghost-action" onClick={() => setSelectedHotspot(null)}>Clear</button>
          </div>
          <div className="event-list compact">
            {hotspotLoading ? (
              <div className="empty-state hotspot-loading">
                <span className="mini-spinner" />
                Loading events for this marker...
              </div>
            ) : hotspotEvents.length === 0 ? (
              <div className="empty-state">No hotspot events returned for this marker.</div>
            ) : (
              hotspotEvents.map((event, index) => (
                <button key={`${eventId(event) || event.fingerprint || index}-${index}`} onClick={() => openEvent(event)}>
                  <strong>{eventActor(event)} / {eventTarget(event)}</strong>
                  <span>{eventDate(event)} - Goldstein {eventGoldstein(event)}</span>
                  <span>{eventLocation(event)}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}

      <div className="dashboard-grid" style={{ marginTop: 16 }}>
        <div className="panel">
          <h3>Top Actors</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Actor</th>
                <th>Events</th>
              </tr>
            </thead>
            <tbody>
              {(dashboard?.top_actors?.data || []).map((actor: any, i: number) => (
                <tr
                  key={i}
                  onClick={() => {
                    setFocusMode('actor');
                    setFocusRegion(actor.actor);
                  }}
                >
                  <td>{codedLabel(actor.actor, 'Actor not coded')}</td>
                  <td>{actor.event_count?.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h3>Representative Events</h3>
          <div className="event-list">
            {topEvents.length === 0 ? (
              <div className="empty-state">No representative events loaded.</div>
            ) : (
              topEvents.map((event) => (
                <button key={eventId(event)} onClick={() => openEvent(event)}>
                  <strong>{eventActor(event)} / {eventTarget(event)}</strong>
                  <span>{eventDate(event)} - {eventLocation(event)} - Goldstein {eventGoldstein(event)}</span>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="panel metadata-panel">
        <h3>Model & Data Metadata</h3>
        <div className="metadata-grid">
          <div><span>Dashboard Source</span><strong>FastAPI direct data API</strong></div>
          <div><span>Chat Source</span><strong>LangGraph tool calling</strong></div>
          <div><span>Map Drilldown</span><strong>Marker-driven event lookup</strong></div>
          <div><span>Event Detail</span><strong>Right-side inspection drawer</strong></div>
          <div><span>Report Export</span><strong>Markdown snapshot</strong></div>
          <div><span>Forecast & Compare</span><strong>Available in the Forecast tab</strong></div>
        </div>
      </div>

      <EventDrawer event={selectedEvent} detail={selectedDetail} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
