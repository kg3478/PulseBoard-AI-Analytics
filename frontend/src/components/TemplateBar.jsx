/**
 * TemplateBar.jsx — 10 startup metric quick-query templates.
 * One-click activation fills and submits the NL query bar.
 */

const TEMPLATES = [
  { label: 'MRR', query: 'Show me monthly recurring revenue over time' },
  { label: 'Churn', query: 'What is the churn rate trend over the last 30 days?' },
  { label: 'CAC', query: 'What is the average customer acquisition cost by channel?' },
  { label: 'LTV', query: 'Show me lifetime value by cohort' },
  { label: 'DAU', query: 'Show me daily active users over time' },
  { label: 'Activation', query: 'What is the activation rate by week?' },
  { label: 'Revenue', query: 'Show me revenue by city or region' },
  { label: 'Conversion', query: 'What is the conversion rate trend?' },
  { label: 'Retention', query: 'Show me week-1 and week-2 retention by cohort' },
  { label: 'Top 10', query: 'Show me the top 10 rows sorted by highest value' },
];

export default function TemplateBar({ onSelect, disabled }) {
  return (
    <div className="mt-4">
      <p className="text-xs text-slate-600 font-medium uppercase tracking-wider mb-2.5">
        Startup Metric Templates
      </p>
      <div className="flex flex-wrap gap-2">
        {TEMPLATES.map((t) => (
          <button
            key={t.label}
            id={`template-${t.label.toLowerCase()}`}
            onClick={() => !disabled && onSelect(t.query)}
            disabled={disabled}
            title={t.query}
            className={`
              text-xs font-semibold px-3 py-1.5 rounded-lg border transition-all duration-200
              ${disabled
                ? 'border-white/5 text-slate-700 cursor-not-allowed'
                : 'border-indigo-500/20 text-indigo-400 bg-indigo-500/5 hover:bg-indigo-500/15 hover:border-indigo-500/40 cursor-pointer'}
            `}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}
