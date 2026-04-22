import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Loader2, TrendingUp, TrendingDown, ThumbsUp, ThumbsDown, RefreshCw, AlertTriangle } from 'lucide-react';
import { getInsights, getAnomalies } from '../api';
import AnomalyCard from '../components/AnomalyCard';

/**
 * InsightsPage — Weekly AI insights + anomaly alerts.
 */
export default function InsightsPage({ session }) {
  const { sessionId } = session;

  const [insights, setInsights] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(true);
  const [anomaliesLoading, setAnomaliesLoading] = useState(true);
  const [insightsError, setInsightsError] = useState('');
  const [feedback, setFeedback] = useState({}); // bullet index → 'up' | 'down'

  const loadInsights = async () => {
    setInsightsLoading(true);
    setInsightsError('');
    try {
      const data = await getInsights(sessionId);
      setInsights(data);
    } catch (e) {
      setInsightsError(e.message);
    } finally {
      setInsightsLoading(false);
    }
  };

  const loadAnomalies = async () => {
    setAnomaliesLoading(true);
    try {
      const data = await getAnomalies(sessionId);
      setAnomalies(data);
    } catch (e) {
      setAnomalies({ alerts: [], total: 0 });
    } finally {
      setAnomaliesLoading(false);
    }
  };

  useEffect(() => {
    loadInsights();
    loadAnomalies();
  }, [sessionId]);

  const handleFeedback = (i, type) => {
    setFeedback((prev) => ({ ...prev, [i]: type }));
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white mb-1">AI Insights & Alerts</h1>
        <p className="text-slate-400 text-sm">Weekly metric summary + anomaly detection powered by Gemini</p>
      </motion.div>

      {/* Anomaly Alerts */}
      <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle size={16} className="text-amber-400" />
          <h2 className="text-base font-semibold text-white">Anomaly Alerts</h2>
          {anomalies && (
            <span className={`ml-auto text-xs font-semibold px-2 py-0.5 rounded-md
              ${anomalies.total === 0 ? 'badge-success' : anomalies.alerts.some(a => a.severity === 'critical') ? 'badge-critical' : 'badge-warning'}`}>
              {anomalies.total === 0 ? 'All Clear' : `${anomalies.total} Alert${anomalies.total > 1 ? 's' : ''}`}
            </span>
          )}
        </div>

        {anomaliesLoading ? (
          <div className="space-y-3">
            {[1, 2].map(i => <div key={i} className="shimmer h-20 rounded-xl" />)}
          </div>
        ) : anomalies?.alerts?.length === 0 ? (
          <div className="glass-card p-5 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <TrendingUp size={20} className="text-emerald-400" />
            </div>
            <div>
              <p className="text-white font-medium">No anomalies detected</p>
              <p className="text-slate-400 text-sm">All metrics are within 2 standard deviations of the 30-day baseline.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {anomalies?.alerts?.map((alert, i) => (
              <AnomalyCard key={i} alert={alert} />
            ))}
          </div>
        )}
      </motion.section>

      {/* Metric Deltas Table */}
      {insights?.deltas && Object.keys(insights.deltas).length > 0 && (
        <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
          <h2 className="text-base font-semibold text-white mb-4">Week-over-Week Metrics</h2>
          <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left text-slate-500 font-medium px-5 py-3">Metric</th>
                    <th className="text-right text-slate-500 font-medium px-5 py-3">This Week</th>
                    <th className="text-right text-slate-500 font-medium px-5 py-3">Last Week</th>
                    <th className="text-right text-slate-500 font-medium px-5 py-3">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(insights.deltas).map(([col, vals], i) => {
                    const pct = vals.pct_change;
                    const isPositive = pct !== null && pct > 0;
                    const isNegative = pct !== null && pct < 0;
                    return (
                      <tr key={col} className={`border-b border-white/5 last:border-0 ${i % 2 === 0 ? '' : 'bg-white/[0.015]'}`}>
                        <td className="px-5 py-3.5 font-mono text-slate-300 text-xs">{col}</td>
                        <td className="px-5 py-3.5 text-right text-white font-medium">{vals.this_week?.toLocaleString()}</td>
                        <td className="px-5 py-3.5 text-right text-slate-400">{vals.last_week?.toLocaleString()}</td>
                        <td className="px-5 py-3.5 text-right">
                          {pct !== null ? (
                            <span className={`flex items-center justify-end gap-1 font-medium
                              ${isPositive ? 'text-emerald-400' : isNegative ? 'text-rose-400' : 'text-slate-400'}`}>
                              {isPositive ? <TrendingUp size={13} /> : isNegative ? <TrendingDown size={13} /> : null}
                              {pct !== null ? `${pct > 0 ? '+' : ''}${pct}%` : '—'}
                            </span>
                          ) : <span className="text-slate-600">—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </motion.section>
      )}

      {/* Weekly Insights Bullets */}
      <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={16} className="text-indigo-400" />
          <h2 className="text-base font-semibold text-white">Weekly AI Summary</h2>
          <button
            id="refresh-insights-btn"
            onClick={loadInsights}
            disabled={insightsLoading}
            className="ml-auto btn-ghost text-xs flex items-center gap-1.5"
          >
            <RefreshCw size={12} className={insightsLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {insightsLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => <div key={i} className="shimmer h-14 rounded-xl" />)}
          </div>
        ) : insightsError ? (
          <div className="glass-card p-5 text-rose-400 text-sm">{insightsError}</div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {insights?.bullets?.map((bullet, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.08 }}
                  className="glass-card px-5 py-4 flex items-start justify-between gap-4 group"
                >
                  <p className="text-slate-200 text-sm leading-relaxed flex-1">{bullet}</p>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                    <button
                      onClick={() => handleFeedback(i, 'up')}
                      className={`p-1.5 rounded-lg transition-colors ${feedback[i] === 'up' ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-600 hover:text-slate-400'}`}
                      title="Useful"
                    >
                      <ThumbsUp size={13} />
                    </button>
                    <button
                      onClick={() => handleFeedback(i, 'down')}
                      className={`p-1.5 rounded-lg transition-colors ${feedback[i] === 'down' ? 'text-rose-400 bg-rose-500/10' : 'text-slate-600 hover:text-slate-400'}`}
                      title="Not useful"
                    >
                      <ThumbsDown size={13} />
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </motion.section>
    </div>
  );
}
