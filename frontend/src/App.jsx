import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState } from 'react';
import UploadPage from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import InsightsPage from './pages/InsightsPage';
import Navbar from './components/Navbar';

/**
 * App.jsx — Root component.
 * Session state is lifted here and also persisted to sessionStorage
 * so that Vercel page refreshes and client-side navigation both work correctly.
 */
export default function App() {
  // Restore session from sessionStorage on initial load (handles Vercel refresh)
  const [session, setSession] = useState(() => {
    try {
      const saved = sessionStorage.getItem('pulseboard_session');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const handleUploadSuccess = (sessionData) => {
    setSession(sessionData);
  };

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-navy-900">
        <Navbar session={session} />
        <Routes>
          <Route path="/" element={<UploadPage onUploadSuccess={handleUploadSuccess} />} />
          <Route
            path="/dashboard"
            element={
              session
                ? <DashboardPage session={session} />
                : <Navigate to="/" replace />
            }
          />
          <Route
            path="/insights"
            element={
              session
                ? <InsightsPage session={session} />
                : <Navigate to="/" replace />
            }
          />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
