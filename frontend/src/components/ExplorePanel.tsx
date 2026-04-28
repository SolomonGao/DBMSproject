import { useState, useEffect } from 'react';
import { Search, Loader2, Zap, CheckCircle, FileText, MessageSquareWarning, Calendar, MapPin, Users, Brain, Terminal, Sparkles } from 'lucide-react';
import { api } from '../api/client';
import type { AnalyzeResponse, ReportResult, EventItem } from '../types';
import EventDetailCard from './EventDetailCard';
import SimilarEventCards from './SimilarEventCards';
import ReportPanel from './ReportPanel';

// Compact event card for search results
function CompactEventCard({ event, onClick }: { event: EventItem; onClick: () => void }) {
  const headline = event.headline || `${event.Actor1Name || 'Unknown'} vs ${event.Actor2Name || 'Unknown'}`;
  return (
    <div
      onClick={onClick}
      style={{
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
        borderRadius: 10,
        padding: '12px 16px',
        cursor: 'pointer',
        transition: 'all 0.15s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = '#cbd5e1';
        e.currentTarget.style.background = '#f1f5f9';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = '#e2e8f0';
        e.currentTarget.style.background = '#f8fafc';
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a', marginBottom: 6, lineHeight: 1.4 }}>
        {headline}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', alignItems: 'center' }}>
        {event.SQLDATE && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 12, color: '#6b7280' }}>
            <Calendar size={11} />
            {event.SQLDATE}
          </span>
        )}
        {event.ActionGeo_FullName && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 12, color: '#6b7280' }}>
            <MapPin size={11} />
            {event.ActionGeo_FullName}
          </span>
        )}
        {(event.Actor1Name || event.Actor2Name) && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 12, color: '#6b7280' }}>
            <Users size={11} />
            {event.Actor1Name || '?'}
            {event.Actor2Name ? ` vs ${event.Actor2Name}` : ''}
          </span>
        )}
        {event.NumArticles !== undefined && (
          <span style={{ fontSize: 11, color: '#f97316', fontWeight: 600 }}>
            {event.NumArticles} articles
          </span>
        )}
      </div>
    </div>
  );
}

export default function ExplorePanel() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Typing animation for thinking
  const [thinkingText, setThinkingText] = useState('');
  const [thinkingDone, setThinkingDone] = useState(false);
  const [showData, setShowData] = useState(false);

  // Report delayed load state
  const [report, setReport] = useState<ReportResult | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  // Typing effect for AI thinking
  useEffect(() => {
    if (result?.plan?.thinking) {
      const fullText = result.plan.thinking;
      setThinkingText('');
      setThinkingDone(false);
      setShowData(false);
      let i = 0;
      const interval = setInterval(() => {
        i++;
        setThinkingText(fullText.slice(0, i));
        if (i >= fullText.length) {
          clearInterval(interval);
          setThinkingDone(true);
          setTimeout(() => setShowData(true), 400);
        }
      }, 12);
      return () => clearInterval(interval);
    }
  }, [result]);

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

  // Extract data from result by type
  const getDataByType = (type: string) => {
    if (!result) return null;
    for (const key of Object.keys(result.data)) {
      const item = result.data[key];
      if (item.type === type && !item.error) return item.data;
    }
    return null;
  };

  const vizes = result?.plan?.visualizations || [];
  const isOffTopic = result?.plan?.intent === 'off_topic';

  // Get event detail data
  const eventDetail = getDataByType('event_detail');
  const similarEvents = getDataByType('similar_events');
  const searchEvents = getDataByType('events') || getDataByType('top_events') || getDataByType('hot_events');

  // When user clicks a search result or similar event, load its detail
  const handleEventClick = (evt: EventItem) => {
    // Construct EVT query from GlobalEventID
    const gid = evt.GlobalEventID;
    if (!gid) return;
    // Use a simple query that the planner will recognize as an event lookup
    // Format: EVT-YYYY-MM-DD-ID
    const date = evt.SQLDATE || '2024-01-01';
    const formattedDate = date.includes('-') ? date : `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
    const evtQuery = `EVT-${formattedDate}-${gid}`;
    setQuery(evtQuery);
    // Trigger search
    setTimeout(() => {
      api.analyze(evtQuery).then((res) => {
        if (res.ok !== false) {
          setResult(res);
          setReport(null);
        }
      }).catch(console.error);
    }, 0);
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Sparkles size={22} color="#2563eb" />
          AI Explore
        </h2>
        <p style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>
          Ask natural language questions about events, actors, and trends.
        </p>
      </div>

      {/* Search Input */}
      <div className="search-box">
        <Search size={20} color="#888" style={{ flexShrink: 0 }} />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search an event by keyword, fingerprint, or ask about a specific incident..."
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
          <h3 style={{ color: '#475569', marginBottom: 8 }}>I&apos;m a GDELT event analyst</h3>
          <p style={{ color: '#64748b', fontSize: 14 }}>
            Ask me about specific geopolitical events, incidents, or search by event ID.
            <br />
            For example: &quot;What happened with US-20240101-VIR-MASS-1149261787?&quot; or &quot;Show me protests in Washington DC.&quot;
          </p>
        </div>
      )}

      {/* Results */}
      {result && !isOffTopic && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* AI Thinking */}
          {result.plan.thinking && (
            <div
              style={{
                background: '#f0f9ff',
                border: '1px solid #bae6fd',
                borderRadius: 12,
                padding: '14px 18px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Brain size={16} color="#0284c7" />
                <span style={{ fontSize: 13, fontWeight: 600, color: '#0369a1' }}>
                  AI Decision
                </span>
                <span style={{ fontSize: 11, color: '#7dd3fc', marginLeft: 'auto' }}>
                  {result.elapsed_ms}ms
                </span>
              </div>
              <p style={{ fontSize: 14, color: '#0c4a6e', lineHeight: 1.6, margin: 0, minHeight: 22 }}>
                {thinkingText}
                {!thinkingDone && <span style={{ display: 'inline-block', width: 2, height: 16, background: '#0284c7', marginLeft: 2, verticalAlign: 'middle', animation: 'blink 1s infinite' }} />}
              </p>
              {/* Tool execution status */}
              {thinkingDone && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, paddingTop: 10, borderTop: '1px solid #bae6fd' }}>
                  <Terminal size={13} color="#0284c7" />
                  <span style={{ fontSize: 12, color: '#0369a1', fontFamily: 'monospace' }}>
                    {result.plan.steps.map(s => s.type).join(' → ')}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Data loading state */}
          {thinkingDone && !showData && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px', background: '#fafafa', borderRadius: 10, border: '1px dashed #e2e8f0' }}>
              <Loader2 size={16} className="spinning" color="#888" />
              <span style={{ fontSize: 14, color: '#888' }}>
                Executing {result.plan.steps.length} tool{result.plan.steps.length > 1 ? 's' : ''}...
              </span>
            </div>
          )}

          {/* Data content — fades in after thinking completes */}
          {showData && (
            <>
              {/* AI Report — manual trigger */}
              {vizes.includes('report') && result?.plan?.report_prompt && !report && !reportLoading && (
                <div style={{ marginBottom: 16 }}>
                  <button
                    onClick={() => loadReport(result.data, result.plan.report_prompt!)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: 6,
                      border: '1px solid #2563eb',
                      background: '#fff',
                      color: '#2563eb',
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <FileText size={14} />
                    Generate AI Report
                  </button>
                </div>
              )}
              {reportLoading && (
                <div className="panel" style={{ background: '#fafafa', animation: 'fadeIn 0.5s ease' }}>
                  <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <FileText size={18} color="#2563eb" />
                    AI Report
                  </h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#888', fontSize: 14 }}>
                    <Loader2 size={16} className="spinning" />
                    Generating summary...
                  </div>
                </div>
              )}
              {report && <div style={{ animation: 'fadeIn 0.5s ease' }}><ReportPanel report={report} /></div>}

              {/* Event Detail Card */}
              {eventDetail && (
                <div style={{ animation: 'fadeIn 0.5s ease' }}>
                  <EventDetailCard event={eventDetail} />
                </div>
              )}

              {/* Similar Events */}
              {similarEvents && (
                <div style={{ animation: 'fadeIn 0.6s ease' }}>
                  <SimilarEventCards events={similarEvents} onEventClick={handleEventClick} />
                </div>
              )}

              {/* Search Results */}
              {searchEvents && Array.isArray(searchEvents) && searchEvents.length > 0 && !eventDetail && (
                <div className="panel" style={{ animation: 'fadeIn 0.6s ease' }}>
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: '#555', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 16 }}>
                    Search Results <span style={{ fontSize: 12, color: '#888', fontWeight: 400 }}>({searchEvents.length})</span>
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {searchEvents.slice(0, 10).map((evt: EventItem, i: number) => (
                      <CompactEventCard key={i} event={evt} onClick={() => handleEventClick(evt)} />
                    ))}
                    {searchEvents.length > 10 && (
                      <p style={{ textAlign: 'center', color: '#888', fontSize: 12, marginTop: 4 }}>
                        + {searchEvents.length - 10} more events
                      </p>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
