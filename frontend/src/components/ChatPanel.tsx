import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Wrench } from 'lucide-react';
import { api } from '../api/client';
import type { ChatMessage, ThinkingStep } from '../types';

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg: ChatMessage = { role: 'user', content: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const history = messages.slice(-10).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await api.chat(userMsg.content, history, sessionId);

      if (res.ok) {
        const assistantMsg: ChatMessage = {
          role: 'assistant',
          content: res.reply,
          thinking_steps: res.thinking_steps,
          tools_used: res.tools_used,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        if (res.session_id) setSessionId(res.session_id);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: `Error: ${res.error || 'Unknown error'}` },
        ]);
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#888', padding: 40 }}>
            <Bot size={48} color="#ccc" style={{ marginBottom: 12 }} />
            <p style={{ fontSize: 16, fontWeight: 500, marginBottom: 4 }}>
              GDELT Analyst
            </p>
            <p style={{ fontSize: 13 }}>
              Ask about events, trends, or regional analysis.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <div className={`chat-message ${msg.role}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, fontSize: 12, opacity: 0.7 }}>
                {msg.role === 'user' ? <User size={12} /> : <Bot size={12} />}
                {msg.role === 'user' ? 'You' : 'Analyst'}
              </div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
            </div>

            {msg.role === 'assistant' && msg.tools_used && msg.tools_used.length > 0 && (
              <div style={{ marginLeft: 8, marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {msg.tools_used.map((tool) => (
                  <span
                    key={tool}
                    style={{
                      fontSize: 11,
                      padding: '2px 8px',
                      background: '#e0e7ff',
                      color: '#4338ca',
                      borderRadius: 12,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Wrench size={10} />
                    {tool}
                  </span>
                ))}
              </div>
            )}

            {msg.role === 'assistant' && msg.thinking_steps && msg.thinking_steps.length > 0 && (
              <details className="thinking-box" style={{ marginLeft: 8 }}>
                <summary>Thinking process ({msg.thinking_steps.length} steps)</summary>
                <div style={{ marginTop: 8 }}>
                  {msg.thinking_steps.map((step: ThinkingStep, j: number) => (
                    <div key={j} className="thinking-step">
                      <span className="badge">{step.type}</span>
                      <span>{step.content || JSON.stringify(step.data)}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        ))}

        {loading && (
          <div className="chat-message assistant" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className="spinner" />
            <span style={{ fontSize: 13, color: '#666' }}>Analyzing...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about events, trends, or regions..."
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()}>
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
