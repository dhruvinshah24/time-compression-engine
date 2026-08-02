'use client';

import { motion } from 'framer-motion';
import {
  Download, PlayCircle, Share2, Sparkles, FileText,
  Loader2, AlertCircle, Zap, Timer
} from 'lucide-react';
import { useParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api/client';

interface SummaryData {
  video_id:   string;
  status:     string;
  filename?:  string;
  metadata?:  {
    duration_hms?: string;
    profile?: string;
    fps?: number;
    resolution?: string;
  };
  summary?:   Record<string, unknown> | string | null;
  events:     unknown[];
  stats: {
    event_count?:      number;
    total_duration_ms?: number;
    stages_completed?:  number;
  };
}

function formatMs(ms: number | undefined | null): string {
  if (!ms) return '—';
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = (s % 60).toFixed(0).padStart(2, '0');
  return `${m}m ${rem}s`;
}

export default function SummaryPage() {
  const params  = useParams<{ videoId: string }>();
  const videoId = params?.videoId ?? '';

  const [data, setData]       = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!videoId) return;
    let mounted = true;
    (api.summary(videoId) as Promise<SummaryData>)
      .then(res => { if (mounted) { setData(res); setLoading(false); } })
      .catch(err => { if (mounted) { setError(err.message); setLoading(false); } });
    return () => { mounted = false; };
  }, [videoId]);

  if (loading) return (
    <div className="h-full flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-accent animate-spin" />
    </div>
  );

  if (error) return (
    <div className="h-full flex flex-col items-center justify-center gap-3">
      <AlertCircle className="w-12 h-12 text-red-400" />
      <p className="text-white font-medium">Could not load summary</p>
      <p className="text-muted text-sm font-mono">{error}</p>
    </div>
  );

  // Pipeline not yet complete
  if (!data || data.status !== 'completed') return (
    <div className="h-full flex flex-col items-center justify-center gap-4 text-center">
      <Loader2 className="w-12 h-12 text-accent animate-spin" />
      <h3 className="text-xl font-semibold text-white">Processing not complete yet</h3>
      <p className="text-muted text-sm">Status: <span className="text-white font-mono">{data?.status ?? 'unknown'}</span></p>
      <Link href="/upload" className="text-accent text-sm hover:underline">← Back to uploads</Link>
    </div>
  );

  const summaryText = typeof data.summary === 'string'
    ? data.summary
    : data.summary
      ? JSON.stringify(data.summary, null, 2)
      : null;

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-slide-up">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-purple-400" />
            AI Summary &amp; Highlight
          </h1>
          <p className="text-muted mt-2">{data.filename ?? videoId}</p>
        </div>
        <div className="flex gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-surface border border-border rounded-lg text-sm text-white hover:bg-white/5 transition-colors">
            <Share2 className="w-4 h-4 text-muted" /> Share
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium text-white transition-colors glow-blue">
            <Download className="w-4 h-4" /> Download Report
          </button>
        </div>
      </div>

      {/* Compression hero */}
      <div className="glass-strong rounded-2xl border border-border p-8 text-center relative overflow-hidden">
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-accent/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-purple-500/20 rounded-full blur-3xl pointer-events-none" />

        <h2 className="text-xl font-medium text-white mb-8 relative z-10">Time Compression Result</h2>

        <div className="flex items-center justify-center gap-10 mb-8 relative z-10">
          <div className="text-right">
            <div className="text-4xl font-bold text-white mb-1">
              {data.metadata?.duration_hms ?? '—'}
            </div>
            <div className="text-sm text-muted">Original Duration</div>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="w-24 h-1 bg-gradient-to-r from-muted to-accent rounded-full" />
          </div>
          <div className="text-left">
            <div className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-accent to-purple-400 mb-1">
              {formatMs(data.stats.total_duration_ms)}
            </div>
            <div className="text-sm text-muted">Processing Time</div>
          </div>
        </div>

        <button className="relative z-10 flex items-center gap-2 mx-auto px-8 py-3 bg-white text-black hover:bg-gray-100 rounded-full font-semibold transition-transform hover:scale-105">
          <PlayCircle className="w-5 h-5" /> Play Highlight Video
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Narrative summary */}
        <div className="lg:col-span-2 glass rounded-xl border border-border p-8">
          <div className="flex items-center gap-2 mb-6">
            <FileText className="w-5 h-5 text-accent" />
            <h2 className="text-xl font-semibold text-white">Narrative Summary</h2>
          </div>
          {summaryText ? (
            <p className="text-gray-300 leading-relaxed text-base whitespace-pre-wrap">{summaryText}</p>
          ) : (
            <p className="text-muted text-sm">
              No narrative summary was generated. This is produced by the s11_summarize stage once real AI models are connected.
            </p>
          )}
        </div>

        {/* Stats sidebar */}
        <div className="space-y-4">
          <div className="glass rounded-xl border border-border p-6 space-y-4">
            <h3 className="text-sm font-semibold text-white">Pipeline Results</h3>
            {[
              { icon: Zap,   label: 'Events Detected',   value: data.stats.event_count ?? 0 },
              { icon: Timer, label: 'Stages Completed',  value: `${data.stats.stages_completed ?? 0} / 12` },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-muted text-sm">
                  <Icon className="w-4 h-4" /> {label}
                </div>
                <span className="text-white font-medium text-sm">{String(value)}</span>
              </div>
            ))}
          </div>

          {/* Metadata card */}
          {data.metadata && (
            <div className="glass rounded-xl border border-border p-6 space-y-3">
              <h3 className="text-sm font-semibold text-white">Video Info</h3>
              {[
                ['Duration',   data.metadata.duration_hms],
                ['Profile',    data.metadata.profile],
                ['FPS',        data.metadata.fps?.toFixed(2)],
                ['Resolution', data.metadata.resolution],
              ].filter(([, v]) => v).map(([label, value]) => (
                <div key={String(label)} className="flex justify-between text-sm">
                  <span className="text-muted">{label}</span>
                  <span className="text-white font-mono">{String(value)}</span>
                </div>
              ))}
            </div>
          )}

          {/* View timeline CTA */}
          <Link href={`/timeline/${data.video_id}`}>
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              className="w-full py-3 bg-surface border border-border text-white rounded-lg text-sm hover:bg-white/5 transition-colors"
            >
              View Timeline →
            </motion.button>
          </Link>
        </div>
      </div>
    </div>
  );
}
