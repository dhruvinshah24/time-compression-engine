'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2, XCircle, Loader2, Clock, AlertCircle,
  ChevronDown, ChevronUp, Terminal, Cpu, Zap, Film,
  Activity, Brain, Radio, ArrowRight
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import DiagnosticsPanel from '@/components/DiagnosticsPanel';
import { API_BASE } from '@/lib/api/client';

interface StageRecord {
  name: string;
  label: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  duration_ms: number | null;
  metrics: Record<string, unknown>;
  errors: string[];
  warnings: string[];
}

interface JobRecord {
  id: string;
  video_id: string;
  filename: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_stage: string | null;
  current_stage_label: string | null;
  failed_stage: string | null;
  error: string | null;
  stages: StageRecord[];
  logs: string[];
  event_count: number;
  video_metadata: Record<string, unknown>;
}

const STAGE_ICONS: Record<string, React.ElementType> = {
  s01_upload: Film,
  s02_extract: Film,
  s03_scene: Brain,
  s04_detect: Cpu,
  s05_track: Activity,
  s06_motion: Activity,
  s07_event: Zap,
  s08_story: Brain,
  s09_narrative: Brain,
  s10_rank: Radio,
  s11_export: CheckCircle2,
  s12_validate: CheckCircle2,
};

function getStageIcon(name: string): React.ElementType {
  for (const [k, v] of Object.entries(STAGE_ICONS)) {
    if (name.toLowerCase().includes(k.replace('s0', 's').replace('s1', 's').split('_')[1] ?? '')) return v;
  }
  return Cpu;
}

function fmtMs(ms: number | null): string {
  if (ms === null) return '';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function fmtElapsed(startMs: number): string {
  const s = Math.floor((Date.now() - startMs) / 1000);
  if (s < 60) return `${s}s elapsed`;
  return `${Math.floor(s/60)}m ${s%60}s elapsed`;
}

function StageRow({ stage, idx }: { stage: StageRecord; idx: number }) {
  const IconComp = getStageIcon(stage.name);
  const hasMetrics = Object.keys(stage.metrics ?? {}).length > 0;
  const isRunning = stage.status === 'running';
  const isDone = stage.status === 'success';
  const isFailed = stage.status === 'failed';

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.02 }}
      className={`relative flex items-start gap-4 px-5 py-4 border-l-2 transition-all ${
        isRunning ? 'border-indigo-500 bg-indigo-500/10' :
        isDone   ? 'border-emerald-500/50 bg-transparent' :
        isFailed ? 'border-rose-500/60 bg-rose-500/5' :
        'border-white/5 bg-transparent opacity-60'
      }`}
    >
      {/* State icon */}
      <div className="pt-0.5 flex-shrink-0">
        {isRunning ? <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" /> :
         isDone   ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> :
         isFailed ? <XCircle className="w-5 h-5 text-rose-400" /> :
                    <div className="w-5 h-5 rounded-full border border-white/20 flex items-center justify-center"><div className="w-1.5 h-1.5 rounded-full bg-white/20" /></div>}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-semibold tracking-tight ${
              stage.status === 'pending' ? 'text-white/40' :
              isRunning ? 'text-white' :
              isDone ? 'text-white/90' : 'text-rose-300'
            }`}>
              {stage.label}
            </span>
          </div>
          <span className="text-xs font-mono text-white/40 flex-shrink-0">
            {isRunning ? (
              <span className="text-indigo-400 animate-pulse font-semibold">EXECUTING…</span>
            ) : (
              fmtMs(stage.duration_ms)
            )}
          </span>
        </div>

        {/* Stage metrics chip list */}
        {hasMetrics && (isDone || isRunning) && (
          <div className="flex flex-wrap gap-x-3.5 gap-y-1 mt-2">
            {Object.entries(stage.metrics).slice(0, 5).map(([k, v]) => (
              <span key={k} className="text-[10px] font-mono text-white/40 bg-white/[0.02] px-2 py-0.5 rounded border border-white/5">
                {k.replace(/_/g, ' ')}: <span className="text-white/80">{String(v)}</span>
              </span>
            ))}
          </div>
        )}

        {stage.errors?.length > 0 && (
          <div className="mt-2.5 p-3 surface-inset border border-rose-500/30 rounded-xl text-xs font-mono text-rose-300">
            {stage.errors[0]}
          </div>
        )}
        {stage.warnings?.length > 0 && (
          <p className="mt-1 text-[11px] text-amber-400/80 font-mono">⚠ {stage.warnings[0]}</p>
        )}
      </div>
    </motion.div>
  );
}

export default function ProcessingPage() {
  const router = useRouter();
  const params = useParams<{ jobId: string }>();
  const jobId = params?.jobId ?? '';
  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logsOpen, setLogsOpen] = useState(false);
  const [startMs] = useState(Date.now());
  const [elapsed, setElapsed] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const errCount = useRef(0);

  const fetchJob = async () => {
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}`);
      if (!res.ok) { setError(`Job not found (${res.status})`); return; }
      const data: JobRecord = await res.json();
      setJob(data); setError(null); errCount.current = 0;
      if (data.status === 'completed' && data.video_id) {
        if (pollRef.current) clearInterval(pollRef.current);
        setTimeout(() => router.push(`/timeline/${data.video_id}`), 2000);
      } else if (['failed', 'cancelled'].includes(data.status)) {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    } catch {
      errCount.current++;
      if (errCount.current >= 3) setError('Cannot reach backend after 3 retries.');
    }
  };

  useEffect(() => {
    if (!jobId) return;
    fetchJob();
    pollRef.current = setInterval(fetchJob, 2000);
    const ticker = setInterval(() => setElapsed(fmtElapsed(startMs)), 1000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      clearInterval(ticker);
    };
  }, [jobId]); // eslint-disable-line

  if (error) return (
    <div className="max-w-3xl mx-auto py-20 text-center space-y-4">
      <div className="w-14 h-14 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 mx-auto">
        <AlertCircle size={28} />
      </div>
      <h2 className="text-xl font-bold text-white">Pipeline Execution Unreachable</h2>
      <p className="text-white/40 text-xs font-mono">{error}</p>
      <button onClick={() => { setError(null); errCount.current = 0; fetchJob(); }}
        className="mt-2 px-4 py-2 rounded-xl surface-card border text-xs text-white/80 hover:text-white transition-colors">
        Re-establish Connection
      </button>
    </div>
  );

  if (!job) return (
    <div className="max-w-3xl mx-auto py-24 flex flex-col items-center justify-center gap-3 text-white/40">
      <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
      <span className="text-xs font-mono uppercase tracking-widest animate-pulse">Connecting to pipeline engine…</span>
    </div>
  );

  const completedCount = job.stages.filter(s => s.status === 'success').length;
  const isTerminal = ['completed', 'failed', 'cancelled'].includes(job.status);

  return (
    <div className="max-w-3xl mx-auto space-y-7 animate-slide-up">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/5">
        <div>
          <div className="flex items-center gap-2 mb-1.5 text-xs">
            <Link href="/" className="text-white/40 hover:text-white/70 transition-colors">Dashboard</Link>
            <span className="text-white/20">›</span>
            <span className="text-indigo-400 font-medium">Pipeline Monitor</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
            {job.filename?.replace('original.mp4', 'Video Feed') || jobId}
          </h1>
          <p className="text-xs text-white/30 font-mono mt-1">{job.id}</p>
        </div>

        <div className="flex items-center gap-2.5">
          <span className={`px-3 py-1 rounded-full text-xs font-semibold border flex items-center gap-1.5 ${
            job.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
            job.status === 'failed'    ? 'bg-rose-500/10 text-rose-400 border-rose-500/30' :
            job.status === 'running'   ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30' :
            'bg-white/5 text-white/40 border-white/10'
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${job.status === 'running' ? 'bg-indigo-400 animate-pulse' : job.status === 'completed' ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            {job.status}
          </span>
        </div>
      </div>

      {/* Hero Progress Surface */}
      <div className="surface-card p-6 rounded-3xl border space-y-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/70 font-medium">
            {job.status === 'running' ? `Active: ${job.current_stage_label || job.current_stage || 'Processing…'}` :
             job.status === 'completed' ? `Pipeline completed (${completedCount}/12 stages)` :
             job.status === 'failed' ? `Pipeline stopped at: ${job.failed_stage || 'unknown'}` : 'Queued'}
          </span>
          <div className="flex items-center gap-3">
            {job.event_count > 0 && (
              <span className="flex items-center gap-1.5 text-indigo-300 text-xs font-mono bg-indigo-500/10 px-2.5 py-0.5 rounded-md border border-indigo-500/20">
                <Zap size={11} /> {job.event_count} events
              </span>
            )}
            <span className="font-mono text-white font-bold">{job.progress}%</span>
          </div>
        </div>

        <div className="h-2.5 w-full surface-inset rounded-full overflow-hidden border border-white/5">
          <motion.div
            animate={{ width: `${job.progress}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className={`h-full rounded-full relative overflow-hidden ${
              job.status === 'failed' ? 'bg-rose-500' :
              job.status === 'completed' ? 'bg-emerald-500' : 'bg-gradient-to-r from-indigo-500 via-violet-500 to-indigo-500'
            }`}
          >
            {job.status === 'running' && (
              <div className="absolute inset-0 bg-white/20 animate-pulse" />
            )}
          </motion.div>
        </div>

        {/* Telemetry chips */}
        <div className="flex flex-wrap gap-2 pt-1 font-mono text-xs">
          {elapsed && !isTerminal && (
            <span className="text-[11px] text-indigo-300/80 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-0.5 rounded-full flex items-center gap-1.5">
              <Clock size={11} /> {elapsed}
            </span>
          )}
          {job.video_metadata && [
            job.video_metadata.duration_hms as string,
            job.video_metadata.resolution as string,
            job.video_metadata.fps ? `${job.video_metadata.fps} fps` : null,
          ].filter(Boolean).map(v => (
            <span key={String(v)} className="text-[11px] px-2.5 py-0.5 rounded-full surface-inset border border-white/5 text-white/50">{v}</span>
          ))}
        </div>
      </div>

      {/* 12-Stage Pipeline List */}
      <div className="surface-card rounded-3xl border overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 surface-inset border-b border-white/10">
          <Cpu className="w-4 h-4 text-indigo-400" />
          <h2 className="text-xs font-semibold text-white/70 uppercase tracking-wider font-mono">
            Pipeline Architecture (12 Stages)
          </h2>
          <span className="text-xs font-mono text-white/30 ml-auto">{completedCount} / {job.stages.length} done</span>
        </div>
        <div className="divide-y divide-white/[0.04]">
          {job.stages.map((stage, idx) => <StageRow key={stage.name} stage={stage} idx={idx} />)}
        </div>
      </div>

      {/* Failure Box */}
      {job.status === 'failed' && job.error && (
        <div className="p-5 surface-inset border border-rose-500/30 rounded-2xl">
          <p className="text-sm font-bold text-rose-300 mb-1.5 flex items-center gap-2">
            <XCircle className="w-4 h-4" /> Pipeline Exception
          </p>
          <pre className="text-xs font-mono text-rose-400/80 whitespace-pre-wrap">{job.error}</pre>
        </div>
      )}

      {/* Completion CTA banner */}
      <AnimatePresence>
        {job.status === 'completed' && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            className="p-6 rounded-3xl surface-card border border-emerald-500/30 shadow-[0_0_20px_rgba(16,185,129,0.15)]"
          >
            <div className="flex items-center gap-3.5 mb-4">
              <div className="w-11 h-11 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <CheckCircle2 size={24} />
              </div>
              <div>
                <p className="font-bold text-white text-base">Pipeline Completed Successfully</p>
                <p className="text-xs text-white/50">{job.event_count} events synthesized · Transitioning to timeline…</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => router.push(`/timeline/${job.video_id}`)}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold text-xs shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all"
              >
                Inspect Visual Timeline <ArrowRight size={14} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Diagnostics Panel */}
      {job.status === 'completed' && (
        <DiagnosticsPanel jobId={jobId} />
      )}

      {/* Logs Accordion */}
      {job.logs?.length > 0 && (
        <div className="surface-card rounded-2xl border overflow-hidden">
          <button
            onClick={() => setLogsOpen(x => !x)}
            className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-white/[0.02] transition-colors"
          >
            <Terminal className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-mono uppercase tracking-wider text-white/60">Execution Trace Logs</span>
            <span className="text-xs font-mono text-white/30 ml-auto mr-2">{job.logs.length} lines</span>
            {logsOpen ? <ChevronUp size={16} className="text-white/40" /> : <ChevronDown size={16} className="text-white/40" />}
          </button>
          <AnimatePresence>
            {logsOpen && (
              <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
                <div className="border-t border-white/5 surface-inset p-4 max-h-64 overflow-y-auto scrollbar-thin">
                  <pre className="text-[11px] font-mono text-emerald-300/80 whitespace-pre-wrap leading-5">{job.logs.join('\n')}</pre>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
