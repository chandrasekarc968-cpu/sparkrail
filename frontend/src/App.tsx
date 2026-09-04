import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { AppLayout } from './components/layout/AppLayout';

import { Overview } from './pages/Overview';
import { ThreeDNetwork } from './pages/ThreeDNetwork';
import { BlockPlanner } from './pages/BlockPlanner';
import { MaintenanceJobs } from './pages/MaintenanceJobs';
import { LiveOperations } from './pages/LiveOperations';
import { AssetHealth } from './pages/AssetHealth';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';

export default function App() {
  return (
    <AppProvider>
      <Router>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<Overview />} />
            <Route path="/3d" element={<ThreeDNetwork />} />
            <Route path="/planner" element={<BlockPlanner />} />
            <Route path="/jobs" element={<MaintenanceJobs />} />
            <Route path="/live" element={<LiveOperations />} />
            <Route path="/assets" element={<AssetHealth />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </AppLayout>
      </Router>
    </AppProvider>
  );
}
