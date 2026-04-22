import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, AlertTriangle, Zap } from 'lucide-react';

/**
 * AnomalyCard.jsx — Displays a single Z-score anomaly alert.
 * Severity: critical (red) | warning (amber)
 */
export default function AnomalyCard({ alert }) {
  const isCritical = alert.severity === 'critical';

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className={`glass-card p-4 border-l-2 ${isCritical ? 'border-rose-500' : 'border-amber-400'}`}
    >
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
          ${isCritical ? 'bg-rose-500/10' : 'bg-amber-400/10'}`}>
          {isCritical
            ? <Zap size={18} className="text-rose-400" />
            : <AlertTriangle size={18} className="text-amber-400" />}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm text-white font-semibold truncate">{alert.column}</span>
            <span className={isCritical ? 'badge-critical' : 'badge-warning'}>
              {isCritical ? 'Critical' : 'Warning'}
            </span>
          </div>
          <p className="text-slate-400 text-sm leading-snug">{alert.message}</p>

          {/* Stats row */}
          <div className="flex items-center gap-4 mt-2.5">
            <div className="flex items-center gap-1.5">
              {alert.direction === 'spike'
                ? <TrendingUp size={13} className="text-rose-400" />
                : <TrendingDown size={13} className="text-rose-400" />}
              <span className="text-xs text-slate-500">
                Current: <span className="text-white font-medium">{alert.current_value?.toLocaleString()}</span>
              </span>
            </div>
            <span className="text-slate-700">|</span>
            <span className="text-xs text-slate-500">
              Baseline: <span className="text-slate-300">{alert.baseline_mean?.toLocaleString()}</span>
            </span>
            <span className="text-slate-700">|</span>
            <span className={`text-xs font-semibold ${isCritical ? 'text-rose-400' : 'text-amber-400'}`}>
              Z = {alert.z_score > 0 ? '+' : ''}{alert.z_score}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
