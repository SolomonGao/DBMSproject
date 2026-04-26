import { ExternalLink, X } from 'lucide-react';
import type { EventItem } from '../types';

interface Props {
  event: EventItem | null;
  detail?: any;
  onClose: () => void;
}

export default function EventDrawer({ event, detail, onClose }: Props) {
  if (!event) return null;
  const detailData = detail?.event_data || detail?.data || detail || {};
  const sourceUrl = event.SOURCEURL || detailData.SOURCEURL;

  return (
    <aside className="event-drawer">
      <div className="drawer-header">
        <div>
          <span>Event Detail</span>
          <h2>{event.headline || `${event.Actor1Name || 'Unknown'} / ${event.Actor2Name || 'Unknown'}`}</h2>
        </div>
        <button onClick={onClose} aria-label="Close event detail">
          <X size={18} />
        </button>
      </div>

      <div className="drawer-grid">
        <div><span>Date</span><strong>{event.SQLDATE}</strong></div>
        <div><span>Event Code</span><strong>{event.EventCode || detailData.EventCode || 'n/a'}</strong></div>
        <div><span>Goldstein</span><strong>{event.GoldsteinScale ?? detailData.GoldsteinScale ?? 'n/a'}</strong></div>
        <div><span>Tone</span><strong>{event.AvgTone ?? detailData.AvgTone ?? 'n/a'}</strong></div>
        <div><span>Articles</span><strong>{event.NumArticles ?? detailData.NumArticles ?? 'n/a'}</strong></div>
        <div><span>Sources</span><strong>{event.NumSources ?? detailData.NumSources ?? 'n/a'}</strong></div>
      </div>

      <section>
        <h4>Actors</h4>
        <p>{event.Actor1Name || detailData.Actor1Name || 'Unknown'} vs {event.Actor2Name || detailData.Actor2Name || 'Unknown'}</p>
      </section>

      <section>
        <h4>Location</h4>
        <p>{event.ActionGeo_FullName || detailData.ActionGeo_FullName || 'Unknown location'}</p>
      </section>

      {(event.summary || detail?.summary) && (
        <section>
          <h4>Summary</h4>
          <p>{event.summary || detail.summary}</p>
        </section>
      )}

      {sourceUrl && (
        <a className="source-link" href={sourceUrl} target="_blank" rel="noreferrer">
          Open source article <ExternalLink size={13} />
        </a>
      )}
    </aside>
  );
}
