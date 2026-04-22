import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Loader2, ChevronDown, ChevronUp, Code2, AlertCircle, HelpCircle, RefreshCw, TrendingUp } from 'lucide-react';
import { runQuery, getRootCause } from '../api';
import Chart from '../components/Chart';
import TemplateBar from '../components/TemplateBar';

/**
 * DashboardPage — Core NL query interface.
 * Shows: query bar → SQL (collapsible) → chart → root cause button.
 */
export default function DashboardPage({ session }) {
  const { sessionId, schema, starterQuestions, csvContent } = session;

  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [sqlExpanded, setSqlExpanded] = useState(false);
  const [rootCauseLoading, setRootCauseLoading] = useState(false);
  const [rootCauseText, setRootCauseText] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const submitQuery = async (q) => {
    const trimmed = (q || question).trim();
    if (!trimmed) return;

    setLoading(true);
    setError('');
    setResult(null);
    setRootCauseText('');
    setSqlExpanded(false);
    setQuestion(trimmed);

    try {
      const data = await runQuery(sessionId, trimmed, csvContent, schema);
      setResult(data);
    } catch (e) {
      setError(e.message || 'Query failed. Try rephrasing your question.');
    } finally {
      setLoading(false);
    }
  };

  const handleRootCause = async () => {
    if (!result) return;
    setRootCauseLoading(true);
    setRootCauseText('');
    try {
      const col = result.result?.columns?.[1]?.name || result.result?.columns?.[0]?.name || '';
      const data = await getRootCause(sessionId, col, csvContent);
      setRootCauseText(data.analysis);
    } catch (e) {
      setRootCauseText('Root cause analysis failed. Make sure your GEMINI_API_KEY is set.');
    } finally {
      setRootCauseLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Query Input */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <label className="block text-slate-400 text-sm font-medium mb-2 ml-1">
          Ask anything about your data
        </label>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <input
              ref={inputRef}
              id="nl-query-input"
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submitQuery()}
              placeholder="e.g. Show me revenue by city last month"
              className="input-field pr-12 text-base"
              disabled={loading}
            />
            {loading && (
              <div className="absolute right-4 top-1/2 -translate-y-1/2">
                <Loader2 size={18} className="text-indigo-400 animate-spin" />
              </div>
            )}
          </div>
          <button
            id="run-query-btn"
            onClick={() => submitQuery()}
            disabled={loading || !question.trim()}
            className="btn-primary flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:transform-none"
          >
            <Send size={16} />
            Ask
          </button>
        </div>
      </motion.div>

      {/* Template Bar */}
      <TemplateBar
        onSelect={(q) => { setQuestion(q); submitQuery(q); }}
        disabled={loading}
      />

      {/* Starter Questions */}
      {!result && !loading && !error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="mt-6"
        >
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-3">Suggested for your data</p>
          <div className="flex flex-wrap gap-2">
            {starterQuestions?.map((q, i) => (
              <button
                key={i}
                onClick={() => { setQuestion(q); submitQuery(q); }}
                className="chip text-sm"
              >
                {q}
              </button>
            ))}
          </div>
        </motion.div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 space-y-3">
          <div className="shimmer h-5 w-48 rounded-lg" />
          <div className="shimmer h-72 w-full rounded-2xl" />
        </motion.div>
      )}

      {/* Error */}
      <AnimatePresence>
        {error && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-6 flex items-start gap-3 bg-rose-500/5 border border-rose-500/20 rounded-xl px-5 py-4"
          >
            <AlertCircle size={18} className="text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-rose-400 font-medium">Query failed</p>
              <p className="text-slate-400 text-sm mt-1">{error}</p>
              <button
                onClick={() => submitQuery()}
                className="flex items-center gap-1.5 text-indigo-400 text-sm mt-2 hover:text-indigo-300 transition-colors"
              >
                <RefreshCw size={13} /> Try again
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Result */}
      <AnimatePresence>
        {result && !loading && (
          <motion.div
            key={result.question}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-4"
          >
            {/* Meta row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <TrendingUp size={16} className="text-emerald-400" />
                <span className="text-white font-medium">{result.question}</span>
                {result.attempts === 2 && (
                  <span className="badge-warning">corrected</span>
                )}
              </div>
              <span className="text-slate-500 text-sm">{result.result?.row_count} rows</span>
            </div>

            {/* Chart */}
            <div className="glass-card p-6">
              <Chart
                columns={result.result?.columns || []}
                rows={result.result?.rows || []}
                chartType={result.result?.chart_type || 'bar'}
              />
            </div>

            {/* SQL Transparency Block */}
            <div className="glass-card overflow-hidden">
              <button
                id="toggle-sql-btn"
                onClick={() => setSqlExpanded(!sqlExpanded)}
                className="w-full flex items-center justify-between px-5 py-3.5 text-sm hover:bg-white/2 transition-colors"
              >
                <div className="flex items-center gap-2 text-slate-400">
                  <Code2 size={15} />
                  <span>Generated SQL</span>
                  <span className="badge-success ml-1">verified</span>
                </div>
                {sqlExpanded ? <ChevronUp size={15} className="text-slate-500" /> : <ChevronDown size={15} className="text-slate-500" />}
              </button>

              <AnimatePresence>
                {sqlExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="px-5 pb-4">
                      <pre className="code-block text-xs whitespace-pre-wrap break-all">{result.sql}</pre>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Root Cause Button */}
            <div className="flex justify-end">
              <button
                id="root-cause-btn"
                onClick={handleRootCause}
                disabled={rootCauseLoading}
                className="btn-ghost flex items-center gap-2 text-sm border border-white/5"
              >
                {rootCauseLoading
                  ? <><Loader2 size={14} className="animate-spin" /> Analyzing...</>
                  : <><HelpCircle size={14} /> Why did this happen?</>}
              </button>
            </div>

            {/* Root Cause Result */}
            <AnimatePresence>
              {rootCauseText && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="glass-card p-5 border-l-2 border-indigo-500"
                >
                  <p className="text-xs text-indigo-400 font-medium uppercase tracking-wider mb-2">Root Cause Analysis</p>
                  <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">{rootCauseText}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
