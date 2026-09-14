'use client';

import { motion } from 'framer-motion';
import { Loader2, AlertCircle, Zap, Clock, TrendingUp, ArrowRight, Film, Activity, CheckCircle2 } from 'lucide-react';
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

  if (loading) return <div className="flex items-center justify-center py-32"><Loader2 className="w-6 h-6 text-indigo-400 animate-spin" /></div>;
  if (error) return <div className="flex flex-col items-center justify-center py-32 gap-3"><AlertCircle className="w-10 h-10 text-red-400" /><p className="text-white">{error}</p></div>;
  if (!data || data.status !== 'completed') return (
    <div className="flex flex-col items-center justify-center py-32 gap-3 text-center">
      <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
      <p className="text-white/60 text-sm">Processing not complete yet — status: {data?.status ?? 'unknown'}</p>
      <Link href="/" className="text-indigo-400 text-sm hover:text-indigo-300">← Back to Dashboard</Link>
    </div>
  );

  const durationS = data.metadata?.duration_seconds ?? 0;
  const compressionRatio = data.stats?.compression_ratio;
  const keptPct = compressionRatio ? Math.round(compressionRatio * 100) : null;
  const eventCount = data.stats?.event_count ?? data.events?.length ?? 0;

  // Event category breakdown
  const eventsByType: Record<string, number> = {};
  (data.events || []).forEach(e => {
    const t = (e.event_type ?? e.type ?? 'other').split('_').slice(0,2).join('_');
    eventsByType[t] = (eventsByType[t] || 0) + 1;
  });

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <Link href="/" className="text-white/30 hover:text-white/60 transition-colors">Dashboard</Link>
        <span className="text-white/20">›</span>
        <Link href={`/timeline/${videoId}`} className="text-white/30 hover:text-white/60 transition-colors">Timeline</Link>
        <span className="text-white/20">›</span>
        <span className="text-white/50">Summary</span>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-white">Analysis Summary</h1>
        <p className="text-white/40 text-sm mt-1">{data.filename?.replace('original.mp4','Video') ?? videoId}</p>
      </div>

      {/* Compression Hero */}
      {keptPct !== null && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          className="p-6 rounded-2xl bg-white/[0.03] border border-white/[0.08]"
        >
          <p className="text-xs text-white/30 uppercase tracking-wider mb-4">Time Compression Result</p>
          <div className="flex items-center gap-8 mb-4">
            <div className="text-center">
              <p className="text-3xl font-bold text-white/50">{durationS > 0 ? fmt(durationS) : '—'}</p>
              <p className="text-[11px] text-white/30 mt-1">Original Duration</p>
            </div>
            <div className="flex-1">
              <div className="h-2 bg-white/5 rounded-full overflow-hidden mb-1">
                <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${keptPct}%` }} />
              </div>
              <p className="text-center text-[10px] text-white/30">{keptPct}% retained</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-indigo-400">{durationS > 0 ? fmt(durationS * (compressionRatio ?? 1)) : '—'}</p>
              <p className="text-[11px] text-indigo-400/50 mt-1">TCE Summary</p>
            </div>
          </div>
          <p className="text-xs text-white/30 text-center">
            {eventCount} events preserved · {(1/(compressionRatio ?? 1)).toFixed(1)}× compression
          </p>
        </motion.div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { icon: Zap, label: 'Events', value: eventCount, color: 'text-indigo-400' },
          { icon: Clock, label: 'Duration', value: durationS > 0 ? fmt(durationS) : '—', color: 'text-cyan-400' },
          { icon: CheckCircle2, label: 'Stages', value: `${data.stats?.stages_completed ?? '—'}/12`, color: 'text-emerald-400' },
        ].map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.07] flex items-center gap-3">
            <div className={`w-8 h-8 rounded-xl bg-black/20 flex items-center justify-center ${color}`}><Icon size={15} /></div>
            <div>
              <p className="text-base font-bold text-white">{String(value)}</p>
              <p className="text-[11px] text-white/30">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Recent events */}
      {data.events?.length > 0 && (
        <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] overflow-hidden">
          <div className="px-4 py-3 border-b border-white/[0.05]">
            <p className="text-sm font-semibold text-white/60">Detected Events ({data.events.length})</p>
          </div>
          <div className="divide-y divide-white/[0.04] max-h-64 overflow-y-auto">
            {data.events.slice(0, 20).map((evt, i) => {
              const et = evt.event_type ?? evt.type ?? 'event';
              const conf = Math.round((evt.confidence ?? 0) * 100);
              const t = ((evt.start_ms ?? 0) / 1000);
              return (
                <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white/70 truncate">{et.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}</p>
                    {evt.person_label && <p className="text-[10px] text-violet-400">{evt.person_label}</p>}
                  </div>
                  <span className="text-[11px] text-white/30 font-mono">{fmt(t)}</span>
                  {conf > 0 && <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-white/5 text-white/40">{conf}%</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <Link href={`/timeline/${videoId}`} className="flex-1">
          <button className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2">
            <Activity size={15} /> Full Timeline <ArrowRight size={14} />
          </button>
        </Link>
        <a href={`${API_BASE}/summary/${videoId}`} target="_blank" rel="noopener noreferrer">
          <button className="px-5 py-2.5 rounded-xl border border-white/10 text-white/60 hover:bg-white/5 text-sm transition-colors">
            Raw Data
          </button>
        </a>
      </div>
    </div>
  );
}
