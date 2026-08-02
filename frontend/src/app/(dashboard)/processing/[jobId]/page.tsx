'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2, XCircle, Loader2, Clock, AlertCircle,
  ChevronDown, ChevronUp, Terminal, BarChart3
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';

// ── Types ────────────────────────────────────────────────────────────────────

interface StageRecord {
  name:        string;
  label:       string;
  status:      'pending' | 'running' | 'success' | 'failed';
  duration_ms: number | null;
  metrics:     Record<string, unknown>;
  errors:      string[];
  warnings:    string[];
}

interface JobRecord {
  id:                  string;
  video_id:            string;
  filename:            string;
  status:              'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress:            number;
  current_stage:       string | null;
  current_stage_label: string | null;
  failed_stage:        string | null;
  error:               string | null;
  stages:              StageRecord[];
  logs:                string[];
  event_count:         number;
  video_metadata:      Record<string, unknown>;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

function fmtMs(ms: number | null): string {
  if (ms === null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function StageIcon({ status }: { status: StageRecord['status'] }) {
  if (status === 'success')  return <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />;
  if (status === 'failed')   return <XCircle      className="w-5 h-5 text-red-400 flex-shrink-0" />;
  if (status === 'running')  return <Loader2      className="w-5 h-5 text-accent flex-shrink-0 animate-spin" />;
  return <Clock className="w-5 h-5 text-muted/40 flex-shrink-0" />;
}

function stageBorderClass(status: StageRecord['status']): string {
  if (status === 'success') return 'border-emerald-400/20 bg-emerald-400/5';
  if (status === 'failed')  return 'border-red-400/30 bg-red-400/5';
  if (status === 'running') return 'border-accent/30 bg-accent/5';
  return 'border-border/30';
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function ProcessingPage() {
  const router   = useRouter();
  const params   = useParams<{ jobId: string }>();
  const jobId    = params?.jobId ?? '';

  const [job, setJob]           = useState<JobRecord | null>(null);
  const [error, setError]       = useState<string | null>(null);
  const [logsOpen, setLogsOpen] = useState(false);
  const pollRef                 = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJob = async () => {
    try {
      const res = await fetch(`${API}/jobs/${jobId}`);
      if (!res.ok) { setError(`Job not found (${res.status})`); return; }
      const data: JobRecord = await res.json();
      setJob(data);

      // Stop polling once terminal state reached
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    } catch (e) {
      setError('Could not reach the backend. Is it running?');
    }
  };

  useEffect(() => {
    if (!jobId) return;
    fetchJob();
    pollRef.current = setInterval(fetchJob, 2000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Error state ────────────────────────────────────────────────────────────
  if (error) return (
    <div className="max-w-3xl mx-auto py-20 text-center space-y-4">
      <AlertCircle className="w-12 h-12 text-red-400 mx-auto" />
      <h2 className="text-xl font-semibold text-white">Job not found</h2>
      <p className="text-muted text-sm font-mono">{error}</p>
      <Link href="/upload" className="inline-block mt-4 text-accent text-sm hover:underline">← Upload a video</Link>
    </div>
  );

  if (!job) return (
    <div className="max-w-3xl mx-auto py-20 flex items-center justify-center gap-3 text-muted">
      <Loader2 className="w-5 h-5 animate-spin" /> Loading job…
    </div>
  );

  const isTerminal = ['completed', 'failed', 'cancelled'].includes(job.status);
  const completedCount = job.stages.filter(s => s.status === 'success').length;

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-slide-up">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-2xl font-bold text-white tracking-tight truncate">
            {job.filename || jobId}
          </h1>
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
            job.status === 'completed' ? 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20' :
            job.status === 'failed'    ? 'bg-red-400/10 text-red-400 border-red-400/20' :
            job.status === 'running'   ? 'bg-accent/10 text-accent border-accent/20' :
            'bg-surface text-muted border-border'
          }`}>
            {job.status}
          </span>
        </div>
        <p className="text-xs text-muted font-mono">{job.id}</p>
      </div>

      {/* ── Progress bar ───────────────────────────────────────────────── */}
      <div className="glass rounded-xl border border-border p-5 space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-muted">
            {job.status === 'running'
              ? `Running: ${job.current_stage_label ?? job.current_stage ?? '…'}`
              : job.status === 'completed' ? `All ${completedCount} stages complete`
              : job.status === 'failed'    ? `Failed at: ${job.failed_stage ?? 'unknown'}`
              : 'Queued'}
          </span>
          <span className="text-white font-mono">{job.progress}%</span>
        </div>
        <div className="h-2 w-full bg-surface rounded-full overflow-hidden">
          <motion.div
            animate={{ width: `${job.progress}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className={`h-full rounded-full ${
              job.status === 'failed' ? 'bg-red-400' :
              job.status === 'completed' ? 'bg-emerald-400' : 'bg-accent'
            }`}
          />
        </div>

        {/* Video metadata pills */}
        {job.video_metadata && (
          <div className="flex flex-wrap gap-2 pt-1">
            {[
              job.video_metadata.duration_hms as string,
              job.video_metadata.resolution as string,
              `${job.video_metadata.fps as number}fps`,
              job.video_metadata.profile as string,
            ].filter(Boolean).map((v) => (
              <span key={v} className="text-xs text-muted bg-surface border border-border px-2 py-0.5 rounded">
                {v}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Pipeline Inspector ─────────────────────────────────────────── */}
      <div className="glass rounded-xl border border-border overflow-hidden">
        <div className="flex items-center gap-3 p-4 border-b border-border">
          <BarChart3 className="w-4 h-4 text-muted" />
          <h2 className="text-sm font-semibold text-white">Pipeline Inspector</h2>
          <span className="text-xs text-muted ml-auto">{completedCount} / {job.stages.length} stages</span>
        </div>

        <div className="divide-y divide-border/30">
          {job.stages.map((stage, idx) => (
            <motion.div
              key={stage.name}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: idx * 0.03 }}
              className={`flex items-start gap-4 px-4 py-3 border-l-2 ${stageBorderClass(stage.status)}`}
            >
              <div className="pt-0.5"><StageIcon status={stage.status} /></div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-4">
                  <span className={`text-sm font-medium ${
                    stage.status === 'pending' ? 'text-muted/50' : 'text-white'
                  }`}>
                    {stage.label}
                  </span>
                  <span className="text-xs font-mono text-muted flex-shrink-0">
                    {stage.status === 'running' ? '…' : fmtMs(stage.duration_ms)}
                  </span>
                </div>

                {/* Metrics row */}
                {Object.keys(stage.metrics ?? {}).length > 0 && (
                  <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
                    {Object.entries(stage.metrics).slice(0, 6).map(([k, v]) => (
                      <span key={k} className="text-xs text-muted">
                        {k}=<span className="text-white">{String(v)}</span>
                      </span>
                    ))}
                  </div>
                )}

                {/* Error message */}
                {stage.errors?.length > 0 && (
                  <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded text-xs font-mono text-red-300">
                    {stage.errors.join('\n')}
                  </div>
                )}

                {/* Warnings */}
                {stage.warnings?.length > 0 && (
                  <div className="mt-1 text-xs text-amber-400/80">
                    ⚠ {stage.warnings[0]}
                    {stage.warnings.length > 1 && ` (+${stage.warnings.length - 1} more)`}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── Job-level error ────────────────────────────────────────────── */}
      <AnimatePresence>
        {job.status === 'failed' && job.error && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl"
          >
            <p className="text-sm font-semibold text-red-300 mb-1 flex items-center gap-2">
              <XCircle className="w-4 h-4" /> Pipeline failed
            </p>
            <pre className="text-xs font-mono text-red-400 whitespace-pre-wrap">{job.error}</pre>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Debug log panel ────────────────────────────────────────────── */}
      {job.logs?.length > 0 && (
        <div className="glass rounded-xl border border-border overflow-hidden">
          <button
            onClick={() => setLogsOpen(!logsOpen)}
            className="w-full flex items-center gap-3 p-4 text-left hover:bg-white/5 transition-colors"
          >
            <Terminal className="w-4 h-4 text-muted" />
            <span className="text-sm font-medium text-white">Stage Logs</span>
            <span className="text-xs text-muted ml-auto mr-2">{job.logs.length} entries</span>
            {logsOpen ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
          </button>
          <AnimatePresence>
            {logsOpen && (
              <motion.div
                initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
                className="overflow-hidden"
              >
                <div className="border-t border-border bg-black/30 p-4 max-h-64 overflow-y-auto">
                  <pre className="text-xs font-mono text-emerald-300/80 whitespace-pre-wrap leading-5">
                    {job.logs.join('\n')}
                  </pre>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* ── CTA on completion ──────────────────────────────────────────── */}
      <AnimatePresence>
        {job.status === 'completed' && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={() => router.push(`/timeline/${job.video_id}`)}
              className="flex-1 bg-accent hover:bg-accent-hover text-white py-3 rounded-lg font-semibold glow-blue"
            >
              View Timeline ({job.event_count} events) →
            </motion.button>
            <button
              onClick={() => router.push(`/summary/${job.video_id}`)}
              className="px-6 py-3 rounded-lg border border-border text-white hover:bg-white/5 transition-colors text-sm"
            >
              Summary
            </button>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
