import { NavLink, useNavigate } from 'react-router-dom';
import { BarChart2, Sparkles, Upload, Zap } from 'lucide-react';

export default function Navbar({ session }) {
  const navigate = useNavigate();

  return (
    <nav className="sticky top-0 z-50 border-b border-white/5 bg-navy-900/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2.5 group"
        >
          <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center glow-indigo group-hover:scale-110 transition-transform duration-200">
            <Zap size={16} className="text-white" />
          </div>
          <span className="text-lg font-bold text-gradient">PulseBoard</span>
        </button>

        {/* Nav Links — only shown after upload */}
        {session && (
          <div className="flex items-center gap-1">
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                `nav-link flex items-center gap-2 px-4 py-2 rounded-xl ${isActive ? 'active bg-indigo-500/10' : ''}`
              }
            >
              <BarChart2 size={15} />
              Dashboard
            </NavLink>
            <NavLink
              to="/insights"
              className={({ isActive }) =>
                `nav-link flex items-center gap-2 px-4 py-2 rounded-xl ${isActive ? 'active bg-indigo-500/10' : ''}`
              }
            >
              <Sparkles size={15} />
              AI Insights
            </NavLink>
          </div>
        )}

        {/* Right Side */}
        <div className="flex items-center gap-3">
          {session ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-slow" />
              <span className="hidden sm:block truncate max-w-[160px]">{session.filename}</span>
              <span className="text-slate-600">·</span>
              <span>{session.rowCount?.toLocaleString()} rows</span>
            </div>
          ) : (
            <span className="text-xs text-slate-600 font-mono">v1.0</span>
          )}
        </div>
      </div>
    </nav>
  );
}
