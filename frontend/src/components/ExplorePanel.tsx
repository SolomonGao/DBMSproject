import { useState } from 'react';
import { Search, Loader2, Zap, CheckCircle, FileText, MessageSquareWarning } from 'lucide-react';
import { api } from '../api/client';
import type { AnalyzeResponse, GeoPoint, TimeSeriesPoint, ReportResult } from '../types';
import StatsCards from './StatsCards';
import TimeSeriesChart from './TimeSeriesChart';
import MapPanel from './MapPanel';
import EventTable from './EventTable';
import ReportPanel from './ReportPanel';

export default function ExplorePanel() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Report delayed load state
  const [report, setReport] = useState<ReportResult | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  const handleSubmit = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setReport(null);

    try {
      const res = await api.analyze(query.trim());
      if (res.ok === false) {
        setError(res.error || 'Analysis failed');
      } else {
        setResult(res);
        // Delayed report load
        if (res.plan.visualizations.includes('report') && res.plan.report_prompt) {
          loadReport(res.data, res.plan.report_prompt);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  const loadReport = async (data: any, prompt: string) => {
    setReportLoading(true);
    try {
      const res = await api.generateReport(data, prompt);
      setReport(res);
    } catch (err: any) {
      console.error('Report load failed:', err);
    } finally {
      setReportLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Extract data from result for visualizations
  const getDataByType = (type: string) => {
    if (!result) return null;
    for (const key of Object.keys(result.data)) {
      const item = result.data[key];
      if (item.type === type) return item.data;
    }
    return null;
  };

  const vizes = result?.plan?.visualizations || [];
  const isOffTopic = result?.plan?.intent === 'off_topic';

  // Helper: get event_detail data (single event) and wrap as array for EventTable
  const getEventDetailData = () => {
    if (!result) return null;
    for (const key of Object.keys(result.data)) {
      const item = result.data[key];
      if (item.type === 'event_detail' && item.data) {
        // event_detail returns a single object; wrap as array
        const d = item.data;
        const eventData = d.event_data || {};
        return [{
          GlobalEventID: eventData.GlobalEventID,
          SQLDATE: eventData.SQLDATE,
          Actor1Name: eventData.Actor1Name || d.key_actors,
          Actor2Name: eventData.Actor2Name,
          ActionGeo_FullName: eventData.ActionGeo_FullName || d.location_name,
          ActionGeo_Lat: eventData.ActionGeo_Lat,
          ActionGeo_Long: eventData.ActionGeo_Long,
          NumArticles: eventData.NumArticles,
          GoldsteinScale: eventData.GoldsteinScale,
          EventCode: eventData.EventCode,
          fingerprint: d.fingerprint,
          headline: d.headline,
          summary: d.summary,
          event_type_label: d.event_type_label,
          severity_score: d.severity_score,
        }];
      }
    }
    return null;
  };

  return (
    <div>
      {/* Search Input */}
      <div className="search-box">
        <Search size={20} color="#888" style={{ flexShrink: 0 }} />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about geopolitical events... e.g. 'What happened in Washington DC in February 2024?'"
          className="search-input"
        />
        <button
          onClick={handleSubmit}
          disabled={loading || !query.trim()}
          className="search-btn"
        >
          {loading ? <Loader2 size={18} className="spinning" /> : <Zap size={18} />}
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="loading-plan">
          <Loader2 size={20} className="spinning" />
          <span>AI Planner is thinking...</span>
        </div>
      )}

      {/* Error */}
      {error && <div className="error-banner">{error}</div>}

      {/* Off-topic */}
      {isOffTopic && (
        <div style={{ padding: 24, background: '#f8fafc', borderRadius: 12, textAlign: 'center' }}>
          <MessageSquareWarning size={40} color="#64748b" style={{ marginBottom: 12 }} />
          <h3 style={{ color: '#475569', marginBottom: 8 }}>I&apos;m a GDELT data analyst</h3>
          <p style={{ color: '#64748b', fontSize: 14 }}>
            Ask me about geopolitical events, regional trends, or specific incidents.
            <br />
            For example: &quot;What happened in DC in Feb 2024?&quot; or &quot;Show me conflict trends in Q1 2024.&quot;
          </p>
        </div>
      )}

      {/* Results */}
      {result && !isOffTopic && (
        <div>
          {/* Query Plan Badge */}
          <div className="plan-badge">
            <CheckCircle size={14} color="#059669" />
            <span>
              <strong>Intent:</strong> {result.plan.intent} &middot; {' '}
              <strong>Steps:</strong> {result.plan.steps.length} &middot; {' '}
              <strong>Time:</strong> {result.elapsed_ms}ms
            </span>
          </div>

          {/* Dynamic Visualizations */}
          <div className="viz-grid">
            {/* Stats Cards */}
            {(vizes.includes('stats_cards') || vizes.includes('dashboard')) && (
              <div className="viz-full">
                <StatsCards data={getDataByType('dashboard')} />
              </div>
            )}

            {/* Timeline Chart */}
            {(vizes.includes('timeline') || vizes.includes('timeseries')) && (
              <div className="viz-half">
                <TimeSeriesChart
                  data={(getDataByType('timeseries') || []) as TimeSeriesPoint[]}
                  title="Event Trends"
                />
              </div>
            )}

            {/* Map */}
            {(vizes.includes('map') || vizes.includes('heatmap') || vizes.includes('geo')) && (
              <div className="viz-half">
                <MapPanel
                  data={(getDataByType('geo') || []) as GeoPoint[]}
                  title="Geographic Distribution"
                />
              </div>
            )}

            {/* Event Table */}
            {(vizes.includes('event_table') || vizes.includes('events') || vizes.includes('top_events') || vizes.includes('hot_events')) && (
              <div className="viz-full">
                <EventTable
                  data={
                    getDataByType('top_events') ||
                    getDataByType('hot_events') ||
                    getDataByType('events') ||
                    getEventDetailData() ||
                    []
                  }
                  title="Key Events"
                />
              </div>
            )}

            {/* Report */}
            {vizes.includes('report') && (
              <div className="viz-full">
                {reportLoading ? (
                  <div className="panel" style={{ background: '#fafafa' }}>
                    <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <FileText size={18} color="#2563eb" />
                      AI Report
                    </h3>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#888', fontSize: 14 }}>
                      <Loader2 size={16} className="spinning" />
                      Generating summary...
                    </div>
                  </div>
                ) : report ? (
                  <ReportPanel report={report} />
                ) : null}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
