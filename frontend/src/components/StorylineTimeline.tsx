import { useState } from 'react';
import { Calendar, MapPin, Users, ChevronDown, ChevronUp, Star } from 'lucide-react';
import type { StorylineData, TimelineEventItem } from '../types';

interface Props {
  storyline: StorylineData;
}

function getEventTypeColor(label?: string): string {
  if (!label) return '#6b7280';
  const l = label.toLowerCase();
  if (l.includes('conflict') || l.includes('viol') || l.includes('attack')) return '#dc2626';
  if (l.includes('cooper') || l.includes('agree') || l.includes('aid')) return '#059669';
  if (l.includes('protest') || l.includes('demonstr')) return '#d97706';
  return '#6b7280';
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function TimelineNode({ event, isLast }: { event: TimelineEventItem; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const color = getEventTypeColor(event.event_type);

  return (
    <div style={{ display: 'flex', gap: 16, position: 'relative' }}>
      {/* Timeline line */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div
          style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: color,
            border: '3px solid #fff',
            boxShadow: `0 0 0 2px ${color}40`,
            flexShrink: 0,
            marginTop: 4,
          }}
        />
        {!isLast && (
          <div
            style={{
              width: 2,
              flex: 1,
              background: 'linear-gradient(to bottom, #e2e8f0, #f1f5f9)',
              marginTop: 4,
              marginBottom: 4,
            }}
          />
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, paddingBottom: 20 }}>
        <div
          className="panel"
          style={{
            padding: 16,
            borderLeft: `3px solid ${color}`,
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <Calendar size={13} color="#888" />
                <span style={{ fontSize: 12, color: '#888', fontWeight: 500 }}>
                  {formatDate(event.date)}
                </span>
                {event.significance_score >= 7 && (
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      fontSize: 11,
                      color: '#f59e0b',
                      background: '#fffbeb',
                      padding: '2px 6px',
                      borderRadius: 10,
                    }}
                  >
                    <Star size={10} />
                    Major
                  </span>
                )}
              </div>
              <h4 style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', margin: '0 0 6px 0', lineHeight: 1.4 }}>
                {event.title}
              </h4>
              <p style={{ fontSize: 13, color: '#666', margin: 0, lineHeight: 1.5 }}>
                {event.description}
              </p>
            </div>
            <div style={{ color: '#aaa', marginLeft: 8 }}>
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>
          </div>

          {/* Meta row */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 16px', marginTop: 10 }}>
            {event.location && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#888' }}>
                <MapPin size={12} />
                {event.location}
              </span>
            )}
            {event.actors.length > 0 && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#888' }}>
                <Users size={12} />
                {event.actors.join(', ')}
              </span>
            )}
            {event.event_type && (
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: 0.5,
                  color,
                  background: `${color}12`,
                  padding: '2px 8px',
                  borderRadius: 10,
                }}
              >
                {event.event_type}
              </span>
            )}
          </div>

          {/* Expanded details */}
          {expanded && (
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 12 }}>
                {event.goldstein_scale !== undefined && event.goldstein_scale !== null && (
                  <div style={{ textAlign: 'center', padding: '8px 12px', background: '#f8fafc', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>Goldstein</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: event.goldstein_scale < -5 ? '#dc2626' : event.goldstein_scale > 5 ? '#059669' : '#6b7280' }}>
                      {event.goldstein_scale.toFixed(1)}
                    </div>
                  </div>
                )}
                {event.num_articles !== undefined && event.num_articles !== null && (
                  <div style={{ textAlign: 'center', padding: '8px 12px', background: '#f8fafc', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>Articles</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: '#2563eb' }}>{event.num_articles}</div>
                  </div>
                )}
                {event.avg_tone !== undefined && event.avg_tone !== null && (
                  <div style={{ textAlign: 'center', padding: '8px 12px', background: '#f8fafc', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>Tone</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: event.avg_tone < 0 ? '#dc2626' : '#059669' }}>
                      {event.avg_tone > 0 ? '+' : ''}{event.avg_tone.toFixed(2)}
                    </div>
                  </div>
                )}
                <div style={{ textAlign: 'center', padding: '8px 12px', background: '#f8fafc', borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>Significance</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: event.significance_score >= 7 ? '#f59e0b' : '#6b7280' }}>
                    {event.significance_score}/10
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function StorylineTimeline({ storyline }: Props) {
  const { timeline, entity_evolution, theme_evolution, narrative_arc } = storyline;
  const [activeTab, setActiveTab] = useState<'timeline' | 'entities' | 'themes'>('timeline');

  const events = timeline.events || [];
  const period = timeline.period || {};

  return (
    <div className="panel">
      <h3 style={{ fontSize: 16, fontWeight: 700, color: '#1a1a1a', marginBottom: 4 }}>
        Event Storyline
      </h3>
      {period.start && period.end && (
        <p style={{ fontSize: 12, color: '#888', marginBottom: 16 }}>
          {formatDate(period.start)} — {formatDate(period.end)}
          {period.duration_days > 0 && ` (${period.duration_days} days)`}
        </p>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid #e2e8f0' }}>
        {(['timeline', 'entities', 'themes'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 16px',
              fontSize: 13,
              fontWeight: 600,
              border: 'none',
              background: 'none',
              color: activeTab === tab ? '#2563eb' : '#888',
              borderBottom: activeTab === tab ? '2px solid #2563eb' : '2px solid transparent',
              cursor: 'pointer',
              textTransform: 'capitalize',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Timeline Tab */}
      {activeTab === 'timeline' && (
        <div>
          {events.length === 0 ? (
            <p style={{ color: '#888', fontSize: 14 }}>No timeline events available.</p>
          ) : (
            events.map((event, i) => (
              <TimelineNode key={event.event_id || i} event={event} isLast={i === events.length - 1} />
            ))
          )}
        </div>
      )}

      {/* Entities Tab */}
      {activeTab === 'entities' && (
        <div>
          <h4 style={{ fontSize: 13, color: '#555', marginBottom: 12 }}>Key Actors</h4>
          {entity_evolution.actors.length === 0 ? (
            <p style={{ color: '#888', fontSize: 14 }}>No actor data available.</p>
          ) : (
            <div style={{ display: 'grid', gap: 8 }}>
              {entity_evolution.actors.slice(0, 10).map((actor, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 14px',
                    background: '#f8fafc',
                    borderRadius: 8,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a' }}>{actor.name}</div>
                    <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>
                      {actor.event_count} events · {actor.role}
                      {actor.avg_goldstein !== undefined && ` · Goldstein: ${actor.avg_goldstein}`}
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: '#888', textAlign: 'right' }}>
                    <div>{actor.first_seen}</div>
                    <div style={{ fontSize: 11 }}>to {actor.last_seen}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <h4 style={{ fontSize: 13, color: '#555', marginTop: 20, marginBottom: 12 }}>Key Locations</h4>
          {entity_evolution.locations.length === 0 ? (
            <p style={{ color: '#888', fontSize: 14 }}>No location data available.</p>
          ) : (
            <div style={{ display: 'grid', gap: 8 }}>
              {entity_evolution.locations.slice(0, 8).map((loc, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 14px',
                    background: '#f8fafc',
                    borderRadius: 8,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a' }}>{loc.name}</div>
                    <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>
                      {loc.event_count} events
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: '#888' }}>
                    {loc.first_seen} — {loc.last_seen}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Themes Tab */}
      {activeTab === 'themes' && (
        <div>
          {theme_evolution.dominant_themes.length === 0 ? (
            <p style={{ color: '#888', fontSize: 14 }}>No theme data available. GKG data may not be configured.</p>
          ) : (
            <>
              <h4 style={{ fontSize: 13, color: '#555', marginBottom: 12 }}>Dominant Themes</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
                {theme_evolution.dominant_themes.map((t, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: 12,
                      fontWeight: 500,
                      color: '#2563eb',
                      background: '#eff6ff',
                      padding: '4px 12px',
                      borderRadius: 20,
                    }}
                  >
                    {t.theme} ({t.count})
                  </span>
                ))}
              </div>

              {theme_evolution.emerging_themes.length > 0 && (
                <>
                  <h4 style={{ fontSize: 13, color: '#555', marginBottom: 12 }}>Emerging Themes</h4>
                  <div style={{ display: 'grid', gap: 8, marginBottom: 20 }}>
                    {theme_evolution.emerging_themes.slice(0, 5).map((t, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: '#f0fdf4', borderRadius: 8 }}>
                        <span style={{ fontSize: 13, color: '#166534' }}>{t.theme}</span>
                        <span style={{ fontSize: 12, color: '#16a34a', fontWeight: 600 }}>+{t.growth_ratio}x</span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {theme_evolution.declining_themes.length > 0 && (
                <>
                  <h4 style={{ fontSize: 13, color: '#555', marginBottom: 12 }}>Declining Themes</h4>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {theme_evolution.declining_themes.slice(0, 5).map((t, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: '#fef2f2', borderRadius: 8 }}>
                        <span style={{ fontSize: 13, color: '#991b1b' }}>{t.theme}</span>
                        <span style={{ fontSize: 12, color: '#dc2626', fontWeight: 600 }}>-{t.decline_ratio}x</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
