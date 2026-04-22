import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useRef } from 'react';
import UploadPage from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import InsightsPage from './pages/InsightsPage';
import Navbar from './components/Navbar';

export default function App() {
  const sessionRef = useRef(null);

  const [session, setSession] = useState(() => {
    try {
      const saved = sessionStorage.getItem('pulseboard_session');
      const parsed = saved ? JSON.parse(saved) : null;
      if (parsed) sessionRef.current = parsed;
      return parsed;
    } catch { return null; }
  });

  const handleUploadSuccess = (data) => {
    sessionRef.current = data;
    sessionStorage.setItem('pulseboard_session', JSON.stringify(data));
    setSession(data);
  };

  const getSession = () => sessionRef.current || session;

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-navy-900">
        <Navbar session={getSession()} />
        <Routes>
          <Route path="/" element={<UploadPage onUploadSuccess={handleUploadSuccess} />} />
          <Route path="/dashboard" element={
            getSession() ? <DashboardPage session={getSession()} /> : <Navigate to="/" replace />
          } />
          <Route path="/insights" element={
            getSession() ? <InsightsPage session={getSession()} /> : <Navigate to="/" replace />
          } />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
