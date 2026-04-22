import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState } from 'react';
import UploadPage from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import InsightsPage from './pages/InsightsPage';
import Navbar from './components/Navbar';

/**
 * App.jsx — Root component.
 * Session state (sessionId + schema) is lifted here and passed down via props.
 * Routes: / → Upload  |  /dashboard → Dashboard  |  /insights → Insights
 */
export default function App() {
  const [session, setSession] = useState(null);
  // session = { sessionId, schema, starterQuestions, filename, rowCount }

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-navy-900">
        <Navbar session={session} />
        <Routes>
          <Route path="/" element={<UploadPage onUploadSuccess={setSession} />} />
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
