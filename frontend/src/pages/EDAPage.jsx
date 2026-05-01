import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart2, GitBranch, AlertOctagon, CheckCircle2,
  Loader2, RefreshCw, ChevronDown, ChevronUp, Table2
} from 'lucide-react';
import { getEDA } from '../api';

/**
 * EDAPage — Exploratory Data Analysis dashboard.
 * Shows: column profiler, correlation pairs, missing values, outliers.
 * All data is computed locally on the backend — no LLM needed.
 */
export default function EDAPage({ session }) {
  const { sessionId } = session;
  const [eda, setEda]         = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [expandedSections, setExpandedSections] = useState({
    profile: true, correlations: true, missing: false, outliers: false,
  });

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getEDA(sessionId);
      setEda(data);
    } catch (e) {
      setError(e.message || 'EDA failed.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [sessionId]);

  const toggle = (key) =>
    setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }));

  if (loading) return (
    <div className="max-w-5xl mx-auto px-6 py-16 flex flex-col items-center gap-4">
      <Loader2 size={32} className="text-indigo-400 animate-spin" />
      <p className="text-slate-400 text-sm">Running exploratory analysis…</p>
    </div>
  );

  if (error) return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="glass-card p-6 text-rose-400">{error}</div>
    </div>
  );

  if (!eda) return null;

  const { profile = [], correlations = [], missing = [], outliers = [], summary = {} } = eda;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between mb-1">
          <h1 className="text-2xl font-bold text-white">Exploratory Data Analysis</h1>
          <button
            onClick={load}
            disabled={loading}
            className="btn-ghost text-xs flex items-center gap-1.5"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
        <p className="text-slate-400 text-sm">
          Local analysis — no AI required. {summary.total_rows?.toLocaleString()} rows ·{' '}
          {summary.total_cols} columns · {summary.completeness_pct}% complete
        </p>
      </motion.div>

      {/* Summary Cards */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="grid grid-cols-2 sm:grid-cols-4 gap-3"
      >
        {[
          { label: 'Numeric Cols', value: summary.numeric_cols, color: 'text-emerald-400' },
          { label: 'Text Cols',    value: summary.text_cols,    color: 'text-indigo-400'  },
          { label: 'Date Cols',    value: summary.date_cols,    color: 'text-amber-400'   },
          { label: 'Nulls',        value: summary.total_nulls,  color: summary.total_nulls > 0 ? 'text-rose-400' : 'text-emerald-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="glass-card px-4 py-3">
            <p className="text-xs text-slate-500 font-medium">{label}</p>
            <p className={`text-xl font-bold mt-1 ${color}`}>{value ?? '—'}</p>
          </div>
        ))}
      </motion.div>

      {/* Column Profile */}
      <Section
        id="profile"
        icon={<Table2 size={16} className="text-indigo-400" />}
        title="Column Profile"
        badge={`${profile.length} cols`}
        expanded={expandedSections.profile}
        onToggle={() => toggle('profile')}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5">
                {['Column', 'Type', 'Null %', 'Unique', 'Min', 'Max', 'Mean'].map((h) => (
                  <th key={h} className="text-left text-slate-500 font-medium px-4 py-2.5 first:pl-5 last:pr-5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {profile.map((col, i) => (
                <tr key={col.name} className={`border-b border-white/5 last:border-0 ${i % 2 ? 'bg-white/[0.015]' : ''}`}>
                  <td className="px-5 py-3 font-mono text-slate-200 text-xs">{col.name}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium
                      ${col.type === 'numeric' ? 'bg-emerald-500/10 text-emerald-400' :
                        col.type === 'date'    ? 'bg-indigo-500/10 text-indigo-400' :
                                                 'bg-slate-700/50 text-slate-400'}`}>
                      {col.type}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-sm ${col.null_pct > 20 ? 'text-rose-400' : col.null_pct > 0 ? 'text-amber-400' : 'text-slate-500'}`}>
                    {col.null_pct}%
                  </td>
                  <td className="px-4 py-3 text-slate-400 text-sm">{col.unique?.toLocaleString() ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{col.min ?? (col.type === 'numeric' ? '—' : '')}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{col.max ?? (col.type === 'numeric' ? '—' : '')}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">
                    {col.mean != null ? Number(col.mean).toFixed(2) : (col.type === 'numeric' ? '—' : '')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Correlations */}
      {correlations.length > 0 && (
        <Section
          id="correlations"
          icon={<GitBranch size={16} className="text-violet-400" />}
          title="Top Correlations"
          badge={`${correlations.length} pairs`}
          expanded={expandedSections.correlations}
          onToggle={() => toggle('correlations')}
        >
          <div className="space-y-2 p-2">
            {correlations.slice(0, 12).map((c, i) => (
              <motion.div
                key={`${c.col_a}-${c.col_b}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="flex items-center gap-3"
              >
                <span className="text-xs text-slate-400 w-5 text-right flex-shrink-0">{i + 1}.</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-slate-300">{c.col_a}</span>
                    <span className="text-slate-600 text-xs">↔</span>
                    <span className="font-mono text-xs text-slate-300">{c.col_b}</span>
                    <span className={`ml-auto text-xs font-semibold ${
                      c.direction === 'positive' ? 'text-emerald-400' : 'text-rose-400'
                    }`}>
                      {c.r > 0 ? '+' : ''}{c.r}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${c.direction === 'positive' ? 'bg-emerald-500' : 'bg-rose-500'}`}
                      style={{ width: `${Math.abs(c.r) * 100}%`, opacity: 0.7 + c.abs_r * 0.3 }}
                    />
                  </div>
                </div>
                <span className={`text-xs flex-shrink-0 ${
                  c.abs_r >= 0.6 ? 'text-amber-400' : c.abs_r >= 0.4 ? 'text-slate-300' : 'text-slate-500'
                }`}>{c.strength}</span>
              </motion.div>
            ))}
          </div>
        </Section>
      )}

      {/* Missing Values */}
      {missing.length > 0 && (
        <Section
          id="missing"
          icon={<AlertOctagon size={16} className="text-amber-400" />}
          title="Missing Values"
          badge={`${missing.length} cols affected`}
          expanded={expandedSections.missing}
          onToggle={() => toggle('missing')}
        >
          <div className="space-y-2 px-5 py-3">
            {missing.map((m) => (
              <div key={m.column} className="flex items-center gap-3">
                <span className="font-mono text-xs text-slate-300 w-40 flex-shrink-0 truncate">{m.column}</span>
                <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${m.null_pct > 50 ? 'bg-rose-500' : 'bg-amber-500'}`}
                    style={{ width: `${m.null_pct}%` }}
                  />
                </div>
                <span className={`text-xs font-medium w-12 text-right ${m.null_pct > 50 ? 'text-rose-400' : 'text-amber-400'}`}>
                  {m.null_pct}%
                </span>
                <span className="text-xs text-slate-600 w-20 text-right">{m.null_count.toLocaleString()} rows</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Outliers */}
      {outliers.length > 0 && (
        <Section
          id="outliers"
          icon={<BarChart2 size={16} className="text-rose-400" />}
          title="Outlier Detection"
          badge={`${outliers.length} cols flagged`}
          expanded={expandedSections.outliers}
          onToggle={() => toggle('outliers')}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5">
                  {['Column', 'Outliers', '% of rows', 'Mean', 'Std Dev', 'Examples'].map((h) => (
                    <th key={h} className="text-left text-slate-500 font-medium px-5 py-2.5">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {outliers.map((o, i) => (
                  <tr key={o.column} className={`border-b border-white/5 last:border-0 ${i % 2 ? 'bg-white/[0.015]' : ''}`}>
                    <td className="px-5 py-3 font-mono text-xs text-slate-200">{o.column}</td>
                    <td className="px-5 py-3 text-rose-400 font-medium">{o.outlier_count}</td>
                    <td className="px-5 py-3 text-slate-400">{o.outlier_pct}%</td>
                    <td className="px-5 py-3 text-slate-400 text-xs">{Number(o.mean).toFixed(2)}</td>
                    <td className="px-5 py-3 text-slate-400 text-xs">±{Number(o.std).toFixed(2)}</td>
                    <td className="px-5 py-3 text-xs text-slate-500 font-mono">
                      {o.examples?.map((v) => Number(v).toFixed(2)).join(', ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* All Clear */}
      {missing.length === 0 && outliers.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass-card p-5 flex items-center gap-3"
        >
          <CheckCircle2 size={20} className="text-emerald-400 flex-shrink-0" />
          <div>
            <p className="text-white font-medium">Dataset looks clean!</p>
            <p className="text-slate-400 text-sm">No missing values or outliers detected.</p>
          </div>
        </motion.div>
      )}
    </div>
  );
}

/** Collapsible section wrapper */
function Section({ id, icon, title, badge, expanded, onToggle, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card overflow-hidden"
    >
      <button
        id={`eda-section-${id}`}
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-white/2 transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-white font-medium text-sm">{title}</span>
          {badge && <span className="badge-success text-xs">{badge}</span>}
        </div>
        {expanded ? <ChevronUp size={15} className="text-slate-500" /> : <ChevronDown size={15} className="text-slate-500" />}
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-white/5"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
