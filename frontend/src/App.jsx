import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useRef } from 'react';
import UploadPage    from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import InsightsPage  from './pages/InsightsPage';
import EDAPage       from './pages/EDAPage';
import Navbar        from './components/Navbar';

/**
 * App.jsx — Root component.
 * v3.0: Added /eda route. Session now carries datasetType for child pages.
 */
export default function App() {
  const sessionRef = useRef(null);

  const [session, setSession] = useState(() => {
    try {
      const saved  = sessionStorage.getItem('pulseboard_session');
      const parsed = saved ? JSON.parse(saved) : null;
      if (parsed) sessionRef.current = parsed;
      return parsed;
    } catch {
      return null;
    }
  });

  const handleUploadSuccess = (sessionData) => {
    sessionRef.current = sessionData;
    sessionStorage.setItem('pulseboard_session', JSON.stringify(sessionData));
    setSession(sessionData);
  };

  const getSession = () => sessionRef.current || session;

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-navy-900">
        <Navbar session={getSession()} />
        <Routes>
          <Route path="/" element={<UploadPage onUploadSuccess={handleUploadSuccess} />} />
          <Route
            path="/dashboard"
            element={getSession() ? <DashboardPage session={getSession()} /> : <Navigate to="/" replace />}
          />
          <Route
            path="/insights"
            element={getSession() ? <InsightsPage session={getSession()} /> : <Navigate to="/" replace />}
          />
          <Route
            path="/eda"
            element={getSession() ? <EDAPage session={getSession()} /> : <Navigate to="/" replace />}
          />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
