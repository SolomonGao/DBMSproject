import { Search, MapPin, User, Tag, Sparkles } from 'lucide-react';
import type { FilterState } from '../types';

interface Props {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onSearch: () => void;
  loading?: boolean;
}

export default function FilterBar({ filters, onChange, onSearch, loading }: Props) {
  const update = (key: keyof FilterState, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        alignItems: 'center',
        flexWrap: 'wrap',
        background: 'white',
        padding: '10px 14px',
        borderRadius: 10,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        marginBottom: 12,
      }}
    >
      {/* Date Range */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <input
          type="date"
          value={filters.startDate}
          onChange={(e) => update('startDate', e.target.value)}
          style={inputStyle}
        />
        <span style={{ color: '#999', fontSize: 13 }}>to</span>
        <input
          type="date"
          value={filters.endDate}
          onChange={(e) => update('endDate', e.target.value)}
          style={inputStyle}
        />
      </div>

      {/* Location */}
      <div style={fieldWrapStyle}>
        <MapPin size={14} color="#666" />
        <input
          type="text"
          placeholder="Region / Location"
          value={filters.location}
          onChange={(e) => update('location', e.target.value)}
          style={{ ...inputStyle, width: 140 }}
        />
      </div>

      {/* Actor */}
      <div style={fieldWrapStyle}>
        <User size={14} color="#666" />
        <input
          type="text"
          placeholder="Actor name"
          value={filters.actor}
          onChange={(e) => update('actor', e.target.value)}
          style={{ ...inputStyle, width: 140 }}
        />
      </div>

      {/* Event Type */}
      <div style={fieldWrapStyle}>
        <Tag size={14} color="#666" />
        <select
          value={filters.eventType}
          onChange={(e) => update('eventType', e.target.value)}
          style={{ ...inputStyle, width: 120, cursor: 'pointer' }}
        >
          <option value="any">Any Type</option>
          <option value="conflict">Conflict</option>
          <option value="cooperation">Cooperation</option>
          <option value="protest">Protest</option>
        </select>
      </div>

      {/* AI Search / Keyword */}
      <div style={{ ...fieldWrapStyle, flex: 1, minWidth: 160 }}>
        <Sparkles size={14} color="#8b5cf6" />
        <input
          type="text"
          placeholder="Keyword (sorting only)..."
          value={filters.keyword}
          onChange={(e) => update('keyword', e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearch()}
          style={{ ...inputStyle, flex: 1, minWidth: 120 }}
        />
      </div>

      {/* Search Button */}
      <button
        onClick={onSearch}
        disabled={loading}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '7px 16px',
          background: loading ? '#c4b5fd' : '#8b5cf6',
          color: 'white',
          border: 'none',
          borderRadius: 8,
          fontSize: 13,
          fontWeight: 600,
          cursor: loading ? 'not-allowed' : 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        <Search size={14} />
        {loading ? 'Searching...' : 'Search Events'}
      </button>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 6,
  padding: '6px 10px',
  fontSize: 13,
  outline: 'none',
  color: '#374151',
};

const fieldWrapStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  background: '#f9fafb',
  padding: '4px 8px',
  borderRadius: 6,
  border: '1px solid #e5e7eb',
};
