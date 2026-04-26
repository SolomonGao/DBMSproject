import { lazy, Suspense, useState } from 'react';
import { LayoutDashboard, MessageSquare, Activity, TrendingUp } from 'lucide-react';

const Dashboard = lazy(() => import('./components/Dashboard'));
const ChatPanel = lazy(() => import('./components/ChatPanel'));
const ForecastWorkspace = lazy(() => import('./components/ForecastWorkspace'));

type Tab = 'dashboard' | 'forecast' | 'chat';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  return (
    <div className="app-layout">
      <header className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Activity size={22} color="#3b82f6" />
          <h1>GDELT Analysis Platform</h1>
        </div>

        <div className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
            Dashboard
          </button>
          <button
            className={`nav-tab ${activeTab === 'forecast' ? 'active' : ''}`}
            onClick={() => setActiveTab('forecast')}
          >
            <TrendingUp size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
            Forecast
          </button>
          <button
            className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <MessageSquare size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
            Analyst Chat
          </button>
        </div>
      </header>

      <main className="app-body">
        <Suspense fallback={<div className="page-loader">Loading workspace...</div>}>
          {activeTab === 'dashboard' && <Dashboard />}
          {activeTab === 'forecast' && <ForecastWorkspace />}
          {activeTab === 'chat' && <ChatPanel />}
        </Suspense>
      </main>
    </div>
  );
}
