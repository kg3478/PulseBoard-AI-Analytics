import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Upload, FileSpreadsheet, CheckCircle, AlertCircle, Sparkles, ArrowRight, Database, Zap, Brain } from 'lucide-react';
import { uploadCSV } from '../api';

/**
 * UploadPage — Landing page with drag-and-drop CSV upload.
 * Shows schema preview + 5 AI starter questions after upload.
 */
export default function UploadPage({ onUploadSuccess }) {
  const navigate = useNavigate();
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [uploadResult, setUploadResult] = useState(null);

  const handleFile = useCallback(async (file) => {
    if (!file || !file.name.endsWith('.csv')) {
      setError('Please upload a CSV file.');
      return;
    }
    setError('');
    setUploading(true);
    try {
      const result = await uploadCSV(file);
      setUploadResult(result);
      onUploadSuccess({
        sessionId: result.session_id,
        schema: result.schema,
        starterQuestions: result.starter_questions,
        filename: result.filename,
        rowCount: result.schema.row_count,
      });
    } catch (e) {
      setError(e.message || 'Upload failed. Is the backend running?');
    } finally {
      setUploading(false);
    }
  }, [onUploadSuccess]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  }, [handleFile]);

  const onFileInput = (e) => handleFile(e.target.files[0]);

  const features = [
    { icon: <Brain size={18} />, label: 'NL-to-SQL', desc: 'Ask in plain English' },
    { icon: <Zap size={18} />, label: 'Instant Charts', desc: 'Auto chart selection' },
    { icon: <Sparkles size={18} />, label: 'AI Insights', desc: 'Weekly summaries' },
    { icon: <Database size={18} />, label: 'Anomaly Alerts', desc: 'Z-score detection' },
  ];

  return (
    <div className="min-h-[calc(100vh-64px)] flex flex-col">
      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-16">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center max-w-2xl mx-auto mb-12"
        >
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-indigo-500/10 border border-indigo-500/30 rounded-full px-4 py-1.5 text-indigo-400 text-sm font-medium mb-6">
            <Sparkles size={14} />
            AI-Powered Analytics · Under 4 Minutes
          </div>

          <h1 className="text-5xl font-bold mb-4 leading-tight">
            Ask questions of your data
            <br />
            <span className="text-gradient">in plain English.</span>
          </h1>
          <p className="text-slate-400 text-lg leading-relaxed">
            Upload your CSV. Type a question. Get a chart instantly.
            <br />
            No SQL. No setup. No analyst required.
          </p>
        </motion.div>

        {/* Feature pills */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="flex flex-wrap justify-center gap-3 mb-10"
        >
          {features.map((f) => (
            <div key={f.label} className="flex items-center gap-2 bg-navy-800 border border-white/5 rounded-xl px-4 py-2 text-sm">
              <span className="text-indigo-400">{f.icon}</span>
              <span className="font-medium text-white">{f.label}</span>
              <span className="text-slate-500">·</span>
              <span className="text-slate-400">{f.desc}</span>
            </div>
          ))}
        </motion.div>

        {/* Upload Zone */}
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.5 }}
          className="w-full max-w-xl"
        >
          {!uploadResult ? (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              className={`relative glass-card gradient-border p-10 text-center transition-all duration-300 cursor-pointer group
                ${dragOver ? 'border-indigo-500/60 bg-indigo-500/5 scale-[1.02]' : 'hover:border-white/10'}
                ${uploading ? 'pointer-events-none' : ''}`}
              onClick={() => document.getElementById('csv-input').click()}
              role="button"
              aria-label="Upload CSV file"
            >
              <input
                id="csv-input"
                type="file"
                accept=".csv"
                className="hidden"
                onChange={onFileInput}
              />

              {uploading ? (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-14 h-14 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
                  <div>
                    <p className="text-white font-semibold">Analyzing your data...</p>
                    <p className="text-slate-400 text-sm mt-1">Detecting schema · Generating questions</p>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <div className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-all duration-300
                    ${dragOver ? 'bg-indigo-500/20 scale-110' : 'bg-navy-700 group-hover:bg-indigo-500/10'}`}>
                    <Upload size={28} className={`transition-colors duration-300 ${dragOver ? 'text-indigo-400' : 'text-slate-400 group-hover:text-indigo-400'}`} />
                  </div>
                  <div>
                    <p className="text-white font-semibold text-lg">
                      {dragOver ? 'Drop it here!' : 'Drop your CSV here'}
                    </p>
                    <p className="text-slate-400 text-sm mt-1">or click to browse · Max 50MB</p>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-600 mt-2">
                    <FileSpreadsheet size={12} />
                    <span>Stripe exports · Google Sheets · Airtable · Shopify reports</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Upload Success — Schema Preview */
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card gradient-border p-6"
            >
              <div className="flex items-center gap-3 mb-5">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                  <CheckCircle size={20} className="text-emerald-400" />
                </div>
                <div>
                  <p className="font-semibold text-white">{uploadResult.filename}</p>
                  <p className="text-slate-400 text-sm">{uploadResult.schema.row_count?.toLocaleString()} rows · {uploadResult.schema.columns?.length} columns detected</p>
                </div>
              </div>

              {/* Column Tags */}
              <div className="flex flex-wrap gap-2 mb-5">
                {uploadResult.schema.columns?.map((col) => (
                  <span key={col.name} className={`text-xs px-2.5 py-1 rounded-lg border font-mono
                    ${col.type === 'numeric' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                      col.type === 'date' ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400' :
                      'bg-slate-700/50 border-white/10 text-slate-400'}`}>
                    {col.name} <span className="opacity-60">·{col.type[0].toUpperCase()}</span>
                  </span>
                ))}
              </div>

              {/* Starter Questions */}
              <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-3">Suggested questions for your data</p>
              <div className="space-y-2 mb-5">
                {uploadResult.starter_questions?.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => navigate('/dashboard')}
                    className="w-full text-left chip flex items-center gap-2 group"
                  >
                    <Sparkles size={12} className="text-indigo-400 flex-shrink-0" />
                    <span>{q}</span>
                  </button>
                ))}
              </div>

              <button
                id="start-analyzing-btn"
                onClick={() => navigate('/dashboard')}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                Start Analyzing
                <ArrowRight size={16} />
              </button>
            </motion.div>
          )}

          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 mt-4 text-rose-400 text-sm bg-rose-500/5 border border-rose-500/20 rounded-xl px-4 py-3"
            >
              <AlertCircle size={16} />
              {error}
            </motion.div>
          )}
        </motion.div>
      </div>

      {/* Footer */}
      <div className="text-center py-6 text-slate-700 text-xs">
        PulseBoard · Built for non-technical founders · NL-to-SQL powered by Gemini
      </div>
    </div>
  );
}
