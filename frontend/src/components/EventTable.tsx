import { Calendar, MapPin, Flame } from 'lucide-react';

interface Props {
  data: any[];
  title?: string;
}

export default function EventTable({ data, title = 'Events' }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="panel">
        <h3>{title}</h3>
        <p style={{ color: '#888', fontSize: 14 }}>No events found.</p>
      </div>
    );
  }

  return (
    <div className="panel">
      <h3>{title} <span style={{ fontSize: 12, color: '#888', fontWeight: 400 }}>({data.length})</span></h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
              <th style={{ padding: '8px 6px' }}>Date</th>
              <th style={{ padding: '8px 6px' }}>Actors</th>
              <th style={{ padding: '8px 6px' }}>Location</th>
              <th style={{ padding: '8px 6px', textAlign: 'right' }}>Heat</th>
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 20).map((evt: any, i: number) => (
              <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '8px 6px', whiteSpace: 'nowrap' }}>
                  <Calendar size={12} style={{ verticalAlign: 'middle', marginRight: 4, color: '#888' }} />
                  {evt.SQLDATE || evt.sql_date || 'N/A'}
                </td>
                <td style={{ padding: '8px 6px' }}>
                  <span style={{ fontWeight: 500 }}>{evt.Actor1Name || evt.actor1_name || 'Unknown'}</span>
                  {evt.Actor2Name || evt.actor2_name ? (
                    <span style={{ color: '#888' }}> vs {evt.Actor2Name || evt.actor2_name}</span>
                  ) : null}
                </td>
                <td style={{ padding: '8px 6px', color: '#666' }}>
                  <MapPin size={12} style={{ verticalAlign: 'middle', marginRight: 4, color: '#888' }} />
                  {evt.ActionGeo_FullName || evt.action_geo_full_name || 'Unknown'}
                </td>
                <td style={{ padding: '8px 6px', textAlign: 'right', fontWeight: 600 }}>
                  <Flame size={12} style={{ verticalAlign: 'middle', marginRight: 4, color: '#f97316' }} />
                  {evt.NumArticles || evt.num_articles || 0}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.length > 20 && (
          <p style={{ textAlign: 'center', color: '#888', fontSize: 12, marginTop: 8 }}>
            + {data.length - 20} more events
          </p>
        )}
      </div>
    </div>
  );
}
