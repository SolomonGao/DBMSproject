import { Network, Tag, TrendingUp, AlertCircle } from 'lucide-react';
import type { GKGInsightData } from '../types';

interface Props {
  insights: GKGInsightData;
}

export default function GKGInsightCards({ insights }: Props) {
  const cooccur = insights.cooccurring;
  const themes = insights.themes;
  const toneTimeline = insights.tone_timeline || [];

  const hasAnyData = cooccur || themes || toneTimeline.length > 0;

  if (!hasAnyData) {
    return (
      <div className="panel" style={{ background: '#fafafa' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <Network size={18} color="#888" />
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#888', margin: 0 }}>
            GKG Insights
          </h3>
        </div>
        <p style={{ fontSize: 13, color: '#aaa', margin: 0 }}>
          <AlertCircle size={14} style={{ display: 'inline', marginRight: 4, verticalAlign: 'text-bottom' }} />
          GKG BigQuery data not available. Configure GCP credentials to enable media knowledge graph insights.
        </p>
      </div>
    );
  }

  return (
    <div className="panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Network size={18} color="#7c3aed" />
        <h3 style={{ fontSize: 16, fontWeight: 700, color: '#1a1a1a', margin: 0 }}>
          Media Knowledge Graph
        </h3>
      </div>

      {/* Related People */}
      {cooccur && cooccur.top_persons && cooccur.top_persons.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h4 style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#555', marginBottom: 10 }}>
            <TrendingUp size={14} color="#7c3aed" />
            Related People in Media
          </h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {cooccur.top_persons.slice(0, 10).map((p: any, i: number) => (
              <span
                key={i}
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: '#7c3aed',
                  background: '#f5f3ff',
                  padding: '4px 12px',
                  borderRadius: 20,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                {p.name}
                <span style={{ fontSize: 10, color: '#a78bfa' }}>({p.count})</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Related Organizations */}
      {cooccur && cooccur.top_organizations && cooccur.top_organizations.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h4 style={{ fontSize: 13, color: '#555', marginBottom: 10 }}>Related Organizations</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {cooccur.top_organizations.slice(0, 6).map((o: any, i: number) => (
              <span
                key={i}
                style={{
                  fontSize: 12,
                  color: '#555',
                  background: '#f3f4f6',
                  padding: '4px 12px',
                  borderRadius: 20,
                }}
              >
                {o.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Themes */}
      {themes && themes.top_themes && themes.top_themes.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h4 style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#555', marginBottom: 10 }}>
            <Tag size={14} color="#059669" />
            Media Themes
          </h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {themes.top_themes.slice(0, 12).map((t: any, i: number) => (
              <span
                key={i}
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: '#059669',
                  background: '#f0fdf4',
                  padding: '4px 12px',
                  borderRadius: 20,
                }}
              >
                {t.theme}
                <span style={{ fontSize: 10, color: '#86efac', marginLeft: 4 }}>{t.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tone Timeline Mini Chart */}
      {toneTimeline.length > 0 && (
        <div>
          <h4 style={{ fontSize: 13, color: '#555', marginBottom: 10 }}>Media Tone Trend</h4>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 60, padding: '8px 0' }}>
            {toneTimeline.map((t: any, i: number) => {
              const tone = t.avg_tone || 0;
              const height = Math.min(Math.abs(tone) * 20 + 10, 50);
              const color = tone < 0 ? '#dc2626' : '#059669';
              return (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
                  <div
                    style={{
                      width: '100%',
                      height: `${height}px`,
                      background: color,
                      borderRadius: '4px 4px 0 0',
                      opacity: 0.7,
                      minWidth: 20,
                    }}
                    title={`${t.date}: tone=${tone.toFixed(2)}, mentions=${t.mention_count}`}
                  />
                  <span style={{ fontSize: 9, color: '#aaa', marginTop: 2 }}>
                    {t.date?.slice(5) || ''}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
