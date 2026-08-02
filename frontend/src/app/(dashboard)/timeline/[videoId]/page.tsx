'use client';

import { motion } from 'framer-motion';
import {
  Search, Filter, Zap, Download, PlayCircle, Eye, Settings2,
  TrendingDown, Loader2, AlertCircle
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api/client';

interface EventRecord {
  id?: string;
  type?: string;
  event_type?: string;
  timestamp_ms?: number;
  confidence?: number;
  description?: string;
  objects?: string[];
  objects_involved?: unknown[];
}

interface TimelineData {
  video_id: string;
  filename?: string;
  job_id?: string;
  job_status?: string;
  metadata?: {
    duration_hms?: string;
    fps?: number;
    resolution?: string;
    profile?: string;
  };
  events: EventRecord[];
  event_count: number;
}

export default function TimelinePage() {
  const params = useParams<{ videoId: string }>();
  const videoId = params?.videoId ?? '';

  const [data, setData]           = useState<TimelineData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch]       = useState('');

  useEffect(() => {
    if (!videoId) return;
    let mounted = true;
    (api.timeline(videoId) as Promise<TimelineData>)
      .then(res => { if (mounted) { setData(res); setLoading(false); } })
      .catch(err => { if (mounted) { setError(err.message); setLoading(false); } });
    return () => { mounted = false; };
  }, [videoId]);

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) return (
    <div className="h-full flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-accent animate-spin" />
    </div>
  );

  // ── Error ──────────────────────────────────────────────────────────────────
  if (error) return (
    <div className="h-full flex flex-col items-center justify-center gap-3">
      <AlertCircle className="w-12 h-12 text-red-400" />
      <p className="text-white font-medium">Could not load timeline</p>
      <p className="text-muted text-sm font-mono">{error}</p>
      <Link href="/upload" className="text-accent text-sm hover:underline">← Upload a video</Link>
    </div>
  );

  // ── Still running ──────────────────────────────────────────────────────────
  if (data?.job_status === 'running') return (
    <div className="h-full flex flex-col items-center justify-center gap-4 text-center">
      <Loader2 className="w-12 h-12 text-accent animate-spin" />
      <h3 className="text-xl font-semibold text-white">Pipeline still running. Check back soon.</h3>
      {data.job_id && (
        <Link href={`/processing/${data.job_id}`} className="text-accent text-sm hover:underline">
          View Processing Status →
        </Link>
      )}
    </div>
  );

  // ── Empty ──────────────────────────────────────────────────────────────────
  if (!data || (data.events.length === 0 && data.job_status === 'completed')) return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-center">
      <Zap className="w-12 h-12 text-muted opacity-30" />
      <h3 className="text-xl font-semibold text-white">No events were detected in this video.</h3>
      <p className="text-muted text-sm max-w-xs">The pipeline completed but found no significant events above the confidence threshold.</p>
    </div>
  );

  const filtered = (data?.events ?? [])
    .filter(e => {
      const t = (e.type ?? e.event_type ?? '').toLowerCase();
      return t.includes(search.toLowerCase());
    })
    .sort((a, b) => (a.timestamp_ms ?? 0) - (b.timestamp_ms ?? 0));

  return (
    <div className="h-full flex flex-col animate-slide-up space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <h1 className="text-2xl font-bold text-white tracking-tight truncate">
            {data?.filename ?? videoId}
          </h1>
          {data?.metadata?.profile && (
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-emerald-400 text-xs font-medium flex-shrink-0">
              <TrendingDown className="w-3.5 h-3.5" />
              {data.metadata.profile}
            </div>
          )}
          {data?.metadata?.duration_hms && (
            <span className="text-sm text-muted flex-shrink-0">
              Duration: {data.metadata.duration_hms}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button className="flex items-center gap-2 px-4 py-2 bg-surface border border-border rounded-lg text-sm text-white hover:bg-white/5 transition-colors">
            <Download className="w-4 h-4 text-muted" /> Export JSON
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium text-white transition-colors glow-blue">
            <PlayCircle className="w-4 h-4" /> Play Highlight
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-4 p-4 bg-surface border border-border rounded-xl">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="Search events by type…"
            aria-label="Search events"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-background border border-border rounded-lg pl-9 pr-4 py-2 text-sm text-white focus:border-accent outline-none transition-colors"
          />
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 px-3 py-2 bg-background border border-border rounded-lg text-sm text-white hover:bg-white/5">
            <Filter className="w-4 h-4 text-muted" /> Type
          </button>
          <button className="flex items-center gap-2 px-3 py-2 bg-background border border-border rounded-lg text-sm text-white hover:bg-white/5">
            <Settings2 className="w-4 h-4 text-muted" /> Confidence &gt; 80%
          </button>
        </div>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto pr-2 space-y-4 relative">
        <div className="absolute left-8 top-0 bottom-0 w-px bg-border z-0" />

        {filtered.length === 0 ? (
          <div className="text-center py-12 text-muted text-sm">No events match your search.</div>
        ) : (
          filtered.map((event, idx) => {
            const key = event.id ?? String(idx);
            const isSelected = selectedId === key;
            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.04 }}
                className="relative z-10 flex gap-6"
                onClick={() => setSelectedId(isSelected ? null : key)}
              >
                {/* Timeline dot */}
                <div className="w-16 flex flex-col items-center pt-5 flex-shrink-0">
                  <div className="w-3 h-3 rounded-full bg-accent ring-4 ring-background mb-2" />
                  <div className="text-xs font-mono text-muted">
                    {event.timestamp_ms != null ? `${(event.timestamp_ms / 1000).toFixed(1)}s` : '—'}
                  </div>
                </div>

                {/* Event card */}
                <div className={`flex-1 glass rounded-xl border p-5 cursor-pointer transition-colors ${
                  isSelected ? 'border-accent bg-accent/5' : 'border-border hover:border-border/80'
                }`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-surface border border-border flex items-center justify-center flex-shrink-0">
                        <Zap className="w-5 h-5 text-accent" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-white">
                          {event.type ?? event.event_type ?? 'Event'}
                        </h3>
                        {event.description && (
                          <p className="text-sm text-muted">{event.description}</p>
                        )}
                      </div>
                    </div>
                    {event.confidence != null && (
                      <span className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded flex-shrink-0">
                        {Math.round(event.confidence * 100)}% conf
                      </span>
                    )}
                  </div>

                  {/* Object tags */}
                  {event.objects && event.objects.length > 0 && (
                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-border/50">
                      <div className="flex gap-2 flex-wrap">
                        {event.objects.map((obj) => (
                          <span key={obj} className="text-xs bg-surface border border-border px-2 py-1 rounded text-muted">
                            {obj}
                          </span>
                        ))}
                      </div>
                      <button className="text-xs text-accent hover:text-accent-hover flex items-center gap-1">
                        <Eye className="w-3 h-3" /> Preview
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}
