import { useState, useEffect } from 'react';
import { Activity, Database } from 'lucide-react';

interface RealTimeIndicatorProps {
  status: 'online' | 'offline' | 'checking';
  lastUpdate?: Date;
}

export function RealTimeIndicator({ status, lastUpdate }: RealTimeIndicatorProps) {
  const [pulse, setPulse] = useState(true);

  useEffect(() => {
    if (status === 'online') {
      const interval = setInterval(() => {
        setPulse(prev => !prev);
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [status]);

  const getStatusColor = () => {
    switch (status) {
      case 'online':
        return 'bg-green-500';
      case 'offline':
        return 'bg-red-500';
      case 'checking':
        return 'bg-yellow-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'online':
        return 'Real-time GDELT';
      case 'offline':
        return 'Offline';
      case 'checking':
        return 'Connecting...';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-gray-800 rounded-lg text-xs">
      <div className="relative">
        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`}></div>
        {status === 'online' && pulse && (
          <div className={`absolute inset-0 w-2 h-2 rounded-full ${getStatusColor()} animate-ping`}></div>
        )}
      </div>

      <div className="flex items-center gap-1.5">
        <Database className="w-3.5 h-3.5 text-gray-400" />
        <span className="text-gray-300">{getStatusText()}</span>
      </div>

      {lastUpdate && status === 'online' && (
        <div className="flex items-center gap-1 text-gray-500 border-l border-gray-700 pl-2 ml-1">
          <Activity className="w-3 h-3" />
          <span>Updated {formatRelativeTime(lastUpdate)}</span>
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(date: Date): string {
  const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);

  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
