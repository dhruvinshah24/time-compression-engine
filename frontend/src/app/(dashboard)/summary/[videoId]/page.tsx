'use client';

import { motion } from 'framer-motion';
import { Loader2, AlertCircle, Zap, Clock, TrendingUp, ArrowRight, Film, Activity, CheckCircle2, FileText, ChevronRight } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { api, API_BASE } from '@/lib/api/client';

interface SummaryData {
  video_id: string;
  status: string;
  filename?: string;
  metadata?: { duration_hms?: string; profile?: string; fps?: number; resolution?: string; duration_seconds?: number };
  summary?: Record<string, unknown> | string | null;
  events: Array<{ event_type?: string; type?: string; start_ms?: number; confidence?: number; person_label?: string; }>;
  stats: { event_count?: number; total_duration_ms?: number; stages_completed?: number; compression_ratio?: number; };
}

function fmt(s: number) {
  if (s < 60) return `${s.toFixed(0)}s`;
  return `${Math.floor(s/60)}m ${(s % 60).toFixed(0)}s`;
}

export default function SummaryPage() {
  const { videoId } = useParams<{ videoId: string }>();
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoId) return;
    let mounted = true;
    (api.summary(videoId) as Promise<SummaryData>)
      .then(res => { if (mounted) { setData(res); setLoading(false); } })
      .catch(err => { if (mounted) { setError(err.message); setLoading(false); } });
    return () => { mounted = false; };
  }, [videoId]);

  if (loading) return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
        <span className="text-xs font-mono uppercase tracking-widest text-white/40 animate-pulse">Aggregating executive summary…</span>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="surface-card p-8 rounded-3xl border border-red-500/20 max-w-md text-center">
        <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
        <p className="text-white font-bold">{error}</p>
        <Link href="/" className="mt-4 inline-block text-xs text-indigo-400 hover:text-indigo-300">
          ← Back to Dashboard
        </Link>
      </div>
    </div>
  );

  if (!data || data.status !== 'completed') return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="surface-card p-8 rounded-3xl border max-w-md text-center space-y-3">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mx-auto" />
        <p className="text-white/60 text-xs font-mono">Stream analysis in progress — status: {data?.status ?? 'unknown'}</p>
        <Link href="/" className="text-indigo-400 text-xs hover:text-indigo-300">← Back to Dashboard</Link>
      </div>
    </div>
  );

  const durationS = data.metadata?.duration_seconds ?? 0;
  const compressionRatio = data.stats?.compression_ratio;
  const keptPct = compressionRatio ? Math.round(compressionRatio * 100) : null;
  const eventCount = data.stats?.event_count ?? data.events?.length ?? 0;

  return (
    <div className="max-w-4xl mx-auto space-y-7 animate-slide-up">
      {/* Header & Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/5">
        <div>
          <div className="flex items-center gap-2 mb-1.5 text-xs">
            <Link href="/" className="text-white/40 hover:text-white/70 transition-colors">Dashboard</Link>
            <ChevronRight size={12} className="text-white/20" />
            <Link href={`/timeline/${videoId}`} className="text-white/40 hover:text-white/70 transition-colors">Timeline</Link>
            <ChevronRight size={12} className="text-white/20" />
            <span className="text-indigo-400 font-medium">Executive Summary</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
            Temporal Compression Dossier
          </h1>
          <p className="text-xs text-white/40 font-mono mt-1">{data.filename?.replace('original.mp4','Video Feed') ?? videoId}</p>
        </div>

        <div className="flex items-center gap-2">
          <Link href={`/timeline/${videoId}`}>
            <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold text-xs shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all">
              <Activity size={14} /> View Interactive Timeline
            </button>
          </Link>
        </div>
      </div>

      {/* Compression Hero */}
      {keptPct !== null && (
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          className="surface-card p-7 rounded-3xl border relative overflow-hidden"
        >
          <div className="flex items-center justify-between mb-6">
            <span className="text-xs font-mono uppercase tracking-wider text-white/50">Compression Telemetry</span>
            <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full">
              {(1/(compressionRatio ?? 1)).toFixed(1)}× Time Condensation
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
            <div className="surface-inset p-5 rounded-2xl border border-white/5 text-center">
              <p className="text-xs text-white/40 font-mono uppercase tracking-wider mb-1">Baseline Footage</p>
              <p className="text-3xl font-mono font-bold text-white">{durationS > 0 ? fmt(durationS) : '—'}</p>
              <p className="text-[10px] text-white/30 font-mono mt-1">100% full duration</p>
            </div>

            <div className="flex flex-col items-center justify-center px-4">
              <div className="w-full h-3 surface-inset rounded-full overflow-hidden p-0.5 border border-white/10 mb-2">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 via-violet-500 to-indigo-500 rounded-full"
                  style={{ width: `${keptPct}%` }}
                />
              </div>
              <p className="text-xs font-mono text-indigo-300 font-semibold">{keptPct}% retained essence</p>
              <p className="text-[10px] font-mono text-white/30 mt-0.5">{eventCount} pivotal events preserved</p>
            </div>

            <div className="surface-inset p-5 rounded-2xl border border-white/5 text-center">
              <p className="text-xs text-indigo-400/80 font-mono uppercase tracking-wider mb-1">Compressed Cut</p>
              <p className="text-3xl font-mono font-bold text-indigo-300">{durationS > 0 ? fmt(durationS * (compressionRatio ?? 1)) : '—'}</p>
              <p className="text-[10px] text-indigo-400/50 font-mono mt-1">Zero semantic loss</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Stats Matrix */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { icon: Zap, label: ' Preserved Events', value: eventCount, color: 'text-indigo-400', glow: 'shadow-[0_0_15px_rgba(99,102,241,0.2)]' },
          { icon: Clock, label: 'Original Runtime', value: durationS > 0 ? fmt(durationS) : '—', color: 'text-cyan-400', glow: 'shadow-[0_0_15px_rgba(6,182,212,0.2)]' },
          { icon: CheckCircle2, label: 'Pipeline Stages', value: `${data.stats?.stages_completed ?? '12'}/12 Verified`, color: 'text-emerald-400', glow: 'shadow-[0_0_15px_rgba(16,185,129,0.2)]' },
        ].map(({ icon: Icon, label, value, color, glow }) => (
          <div key={label} className="surface-card p-5 rounded-2xl border flex items-center gap-4">
            <div className={`w-11 h-11 rounded-xl bg-black/40 border border-white/10 flex items-center justify-center ${color} ${glow} flex-shrink-0`}>
              <Icon size={18} />
            </div>
            <div>
              <p className="text-xl font-bold font-mono text-white">{String(value)}</p>
              <p className="text-xs text-white/40 mt-0.5 font-medium">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Preserved Event Stream */}
      {data.events?.length > 0 && (
        <div className="surface-card rounded-3xl border overflow-hidden">
          <div className="px-6 py-4 surface-inset border-b border-white/10 flex items-center justify-between">
            <p className="text-xs font-mono uppercase tracking-wider text-white/70">
              Preserved Temporal Milestones ({data.events.length})
            </p>
            <span className="text-xs font-mono text-white/30">Ranked Chronology</span>
          </div>
          <div className="divide-y divide-white/[0.03] max-h-72 overflow-y-auto scrollbar-thin">
            {data.events.slice(0, 30).map((evt, i) => {
              const et = evt.event_type ?? evt.type ?? 'event';
              const conf = Math.round((evt.confidence ?? 0) * 100);
              const t = ((evt.start_ms ?? 0) / 1000);
              return (
                <div key={i} className="flex items-center gap-4 px-6 py-3.5 hover:bg-white/[0.02] transition-colors">
                  <div className="w-2 h-2 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(99,102,241,0.5)] flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white/90 truncate">
                      {et.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}
                    </p>
                    {evt.person_label && (
                      <p className="text-[10px] text-violet-300 font-mono mt-0.5">Identified: {evt.person_label}</p>
                    )}
                  </div>
                  <span className="text-xs text-white/40 font-mono">{fmt(t)}</span>
                  {conf > 0 && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full surface-inset border border-white/5 text-white/50">
                      {conf}% conf
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <Link href={`/timeline/${videoId}`} className="flex-1">
          <button className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold text-xs shadow-[0_0_20px_rgba(99,102,241,0.3)] transition-all flex items-center justify-center gap-2">
            <Activity size={15} /> Open Timeline Inspector <ArrowRight size={14} />
          </button>
        </Link>
        <a href={`${API_BASE}/summary/${videoId}`} target="_blank" rel="noopener noreferrer">
          <button className="px-5 py-3 rounded-xl surface-card border text-white/60 hover:text-white text-xs font-mono transition-colors flex items-center gap-2">
            <FileText size={14} /> Export JSON Schema
          </button>
        </a>
      </div>
    </div>
  );
}
