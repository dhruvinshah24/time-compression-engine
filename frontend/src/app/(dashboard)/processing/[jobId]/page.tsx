'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2, XCircle, Loader2, Clock, AlertCircle,
  ChevronDown, ChevronUp, Terminal, Cpu, Zap, Film,
  Activity, Brain, Radio
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import DiagnosticsPanel from '@/components/DiagnosticsPanel';

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

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

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
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtElapsed(startMs: number): string {
  const s = Math.floor((Date.now() - startMs) / 1000);
  if (s < 60) return `${s}s elapsed`;
  return `${Math.floor(s/60)}m ${s%60}s elapsed`;
}

function StageRow({ stage, idx }: { stage: StageRecord; idx: number }) {
  const [expanded, setExpanded] = useState(false);
  const IconComp = getStageIcon(stage.name);
  const hasMetrics = Object.keys(stage.metrics ?? {}).length > 0;
  const isRunning = stage.status === 'running';
  const isDone = stage.status === 'success';
  const isFailed = stage.status === 'failed';

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.03 }}
      className={`relative flex items-start gap-4 px-4 py-3.5 border-l-2 transition-all ${
        isRunning ? 'border-indigo-500 bg-indigo-500/5' :
        isDone   ? 'border-emerald-500/40 bg-transparent' :
        isFailed ? 'border-red-500/60 bg-red-500/5' :
        'border-white/5 bg-transparent'
      }`}
    >
      {/* State icon */}
      <div className="pt-0.5 flex-shrink-0">
        {isRunning ? <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" /> :
         isDone   ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> :
         isFailed ? <XCircle className="w-5 h-5 text-red-400" /> :
                    <div className="w-5 h-5 rounded-full border border-white/15 flex items-center justify-center"><div className="w-1.5 h-1.5 rounded-full bg-white/20" /></div>}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-4">
          <span className={`text-sm font-medium ${
            stage.status === 'pending' ? 'text-white/30' :
            isRunning ? 'text-white' :
            isDone ? 'text-white/80' : 'text-red-300'
          }`}>
            {stage.label}
          </span>
          <span className="text-xs font-mono text-white/30 flex-shrink-0">
            {isRunning ? <span className="text-indigo-400 animate-pulse">running…</span> : fmtMs(stage.duration_ms)}
          </span>
        </div>

        {/* Key metrics */}
        {hasMetrics && (isDone || isRunning) && (
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1.5">
            {Object.entries(stage.metrics).slice(0, 5).map(([k, v]) => (
              <span key={k} className="text-[11px] text-white/30">
                {k.replace(/_/g, ' ')}: <span className="text-white/60">{String(v)}</span>
              </span>
            ))}
          </div>
        )}

        {stage.errors?.length > 0 && (
          <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs font-mono text-red-300">
            {stage.errors[0]}
          </div>
        )}
        {stage.warnings?.length > 0 && (
          <p className="mt-1 text-[11px] text-amber-400/80">⚠ {stage.warnings[0]}</p>
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
      const res = await fetch(`${API}/jobs/${jobId}`);
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
    <div className="max-w-2xl mx-auto py-20 text-center space-y-4">
      <AlertCircle className="w-12 h-12 text-red-400 mx-auto" />
      <h2 className="text-xl font-semibold text-white">Job not found</h2>
      <p className="text-white/40 text-sm font-mono">{error}</p>
      <button onClick={() => { setError(null); errCount.current = 0; fetchJob(); }}
        className="mt-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-white/60 text-sm hover:bg-white/10 transition-colors">
        Retry
      </button>
    </div>
  );

  if (!job) return (
    <div className="max-w-2xl mx-auto py-20 flex items-center justify-center gap-3 text-white/40">
      <Loader2 className="w-5 h-5 animate-spin" /> Loading job…
    </div>
  );

  const completedCount = job.stages.filter(s => s.status === 'success').length;
  const isTerminal = ['completed', 'failed', 'cancelled'].includes(job.status);

  return (
    <div className="max-w-2xl mx-auto space-y-6">

      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Link href="/" className="text-white/30 hover:text-white/60 text-sm transition-colors">Dashboard</Link>
          <span className="text-white/20">›</span>
          <span className="text-white/50 text-sm">Processing</span>
        </div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-white truncate flex-1">
            {job.filename?.replace('original.mp4', 'Video') || jobId}
          </h1>
          <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border flex-shrink-0 ${
            job.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
            job.status === 'failed'    ? 'bg-red-500/10 text-red-400 border-red-500/20' :
            job.status === 'running'   ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20' :
            'bg-white/5 text-white/40 border-white/10'
          }`}>{job.status}</span>
        </div>
        <p className="text-xs text-white/25 font-mono mt-1">{job.id}</p>
      </div>

      {/* Progress hero */}
      <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.07] space-y-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/50">
            {job.status === 'running' ? `Stage: ${job.current_stage_label || job.current_stage || '…'}` :
             job.status === 'completed' ? `All ${completedCount} stages complete` :
             job.status === 'failed' ? `Failed at: ${job.failed_stage || 'unknown'}` : 'Queued'}
          </span>
          <div className="flex items-center gap-3">
            {job.event_count > 0 && (
              <span className="flex items-center gap-1 text-indigo-400 text-xs">
                <Zap size={11} /> {job.event_count} events
              </span>
            )}
            <span className="font-mono text-white">{job.progress}%</span>
          </div>
        </div>
        <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
          <motion.div
            animate={{ width: `${job.progress}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className={`h-full rounded-full ${
              job.status === 'failed' ? 'bg-red-500' :
              job.status === 'completed' ? 'bg-emerald-500' : 'bg-indigo-500'
            }`}
          />
        </div>

        {/* Metadata + elapsed */}
        <div className="flex flex-wrap gap-2">
          {elapsed && !isTerminal && (
            <span className="text-[11px] text-white/30 flex items-center gap-1">
              <Clock size={10} /> {elapsed}
            </span>
          )}
          {job.video_metadata && [
            job.video_metadata.duration_hms as string,
            job.video_metadata.resolution as string,
            job.video_metadata.fps ? `${job.video_metadata.fps}fps` : null,
          ].filter(Boolean).map(v => (
            <span key={String(v)} className="text-[11px] px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-white/40">{v}</span>
          ))}
        </div>
      </div>

      {/* Stage pipeline */}
      <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.06]">
          <Cpu className="w-4 h-4 text-white/30" />
          <h2 className="text-sm font-semibold text-white/60">Pipeline</h2>
          <span className="text-xs text-white/25 ml-auto">{completedCount} / {job.stages.length} complete</span>
        </div>
        <div className="divide-y divide-white/[0.04]">
          {job.stages.map((stage, idx) => <StageRow key={stage.name} stage={stage} idx={idx} />)}
        </div>
      </div>

      {/* Error banner */}
      {job.status === 'failed' && job.error && (
        <div className="p-4 bg-red-500/8 border border-red-500/20 rounded-2xl">
          <p className="text-sm font-semibold text-red-300 mb-1 flex items-center gap-2">
            <XCircle className="w-4 h-4" /> Pipeline failed
          </p>
          <pre className="text-xs font-mono text-red-400/80 whitespace-pre-wrap">{job.error}</pre>
        </div>
      )}

      {/* Completion CTA */}
      <AnimatePresence>
        {job.status === 'completed' && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            className="p-5 rounded-2xl bg-emerald-500/8 border border-emerald-500/25"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="font-semibold text-emerald-300">Analysis complete</p>
                <p className="text-xs text-emerald-400/60">{job.event_count} events detected · Redirecting to timeline…</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => router.push(`/timeline/${job.video_id}`)}
                className="flex-1 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition-colors">
                View Timeline →
              </button>
              <button onClick={() => router.push(`/summary/${job.video_id}`)}
                className="px-5 py-2.5 rounded-xl border border-white/10 text-white/60 hover:bg-white/5 text-sm transition-colors">
                Summary
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* DiagnosticsPanel */}
      {job.status === 'completed' && (
        <DiagnosticsPanel jobId={jobId} />
      )}

      {/* Logs */}
      {job.logs?.length > 0 && (
        <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] overflow-hidden">
          <button onClick={() => setLogsOpen(x => !x)}
            className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.03] transition-colors">
            <Terminal className="w-4 h-4 text-white/25" />
            <span className="text-sm text-white/50">Stage Logs</span>
            <span className="text-xs text-white/25 ml-auto mr-2">{job.logs.length} entries</span>
            {logsOpen ? <ChevronUp className="w-4 h-4 text-white/25" /> : <ChevronDown className="w-4 h-4 text-white/25" />}
          </button>
          <AnimatePresence>
            {logsOpen && (
              <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
                <div className="border-t border-white/[0.05] bg-black/30 p-4 max-h-56 overflow-y-auto">
                  <pre className="text-[11px] font-mono text-emerald-300/70 whitespace-pre-wrap leading-5">{job.logs.join('\n')}</pre>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
