import { MapVisualization, EventData } from './MapVisualization';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  events?: EventData[];
  timestamp?: string;
}

export function ChatMessage({ role, content, events, timestamp }: ChatMessageProps) {
  const isUser = role === 'user';

  return (
    <div className={`flex gap-4 p-6 ${isUser ? 'bg-transparent' : 'bg-gray-50'}`}>
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
        isUser ? 'bg-blue-600 text-white' : 'bg-purple-600 text-white'
      }`}>
        {isUser ? 'U' : 'AI'}
      </div>

      <div className="flex-1 space-y-4">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">
            {isUser ? 'You' : 'Assistant'}
          </span>
          {timestamp && (
            <span className="text-xs text-gray-500">{timestamp}</span>
          )}
        </div>

        <div className="prose prose-sm max-w-none">
          <p className="whitespace-pre-wrap">{content}</p>
        </div>

        {events && events.length > 0 && (
          <div className="mt-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm">Geographic Visualization</h3>
              <div className="flex items-center gap-4 text-xs text-gray-600">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <span>Severe Conflict</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                  <span>Mild Conflict</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                  <span>Cooperation</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <span>Strong Cooperation</span>
                </div>
              </div>
            </div>

            <div className="h-[500px]">
              <MapVisualization events={events} />
            </div>

            <div className="text-xs text-gray-600">
              Showing {events.length} event{events.length !== 1 ? 's' : ''} on the map
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
