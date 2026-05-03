import { FileText, Lightbulb, BookOpen, Network } from 'lucide-react';
import type { EnhancedReportResult, EventItem } from '../types';
import StorylineTimeline from './StorylineTimeline';
import GKGInsightCards from './GKGInsightCards';

interface Props {
  report: EnhancedReportResult;
  event?: EventItem;
}

export default function EventReportPanel({ report, event }: Props) {
  if (!report) return null;

  const hasStoryline = !!report.storyline;
  const hasGKG = !!report.gkg_insights;

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      {/* Report Header */}
      <div className="panel" style={{ background: '#fafafa' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <FileText size={20} color="#2563eb" />
          <span style={{ fontSize: 18, fontWeight: 700, color: '#1a1a1a' }}>
            Event Report
          </span>
          {report.generated_at && (
            <span style={{ fontSize: 11, color: '#aaa', marginLeft: 'auto' }}>
              Generated {new Date(report.generated_at).toLocaleString()}
            </span>
          )}
        </h3>

        {/* Summary */}
        {report.summary && (
          <div style={{ lineHeight: 1.7, color: '#374151', fontSize: 14, marginBottom: 16 }}>
            {report.summary.split('\n').map((para, i) => (
              <p key={i} style={{ marginBottom: 10 }}>{para}</p>
            ))}
          </div>
        )}

        {/* Key Findings */}
        {report.key_findings && report.key_findings.length > 0 && (
          <div>
            <h4 style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#555', marginBottom: 10 }}>
              <Lightbulb size={14} color="#f59e0b" />
              Key Findings
            </h4>
            <ul style={{ paddingLeft: 18, margin: 0 }}>
              {report.key_findings.map((finding, i) => (
                <li key={i} style={{ marginBottom: 8, fontSize: 13, color: '#4b5563', lineHeight: 1.6 }}>
                  {finding}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Data Source Indicators */}
        <div style={{ display: 'flex', gap: 12, marginTop: 16, paddingTop: 12, borderTop: '1px solid #e2e8f0' }}>
          {hasStoryline && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#2563eb', background: '#eff6ff', padding: '4px 10px', borderRadius: 10 }}>
              <BookOpen size={12} />
              Storyline
            </span>
          )}
          {hasGKG && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#7c3aed', background: '#f5f3ff', padding: '4px 10px', borderRadius: 10 }}>
              <Network size={12} />
              GKG Insights
            </span>
          )}
        </div>
      </div>

      {/* Storyline */}
      {hasStoryline && report.storyline && (
        <div style={{ marginTop: 16 }}>
          <StorylineTimeline storyline={report.storyline} />
        </div>
      )}

      {/* GKG Insights */}
      {report.gkg_insights && (
        <div style={{ marginTop: 16 }}>
          <GKGInsightCards insights={report.gkg_insights} />
        </div>
      )}
    </div>
  );
}
