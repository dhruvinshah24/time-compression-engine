'use client';

/**
 * Stories Page — /stories/[videoId]
 *
 * Visualizes multi-track story arcs per person/track detected by the TCE pipeline.
 * Precision-styled as a video/audio DAW sequencer interface.
 * Real data only — strictly bound to GET /api/v1/stories/{videoId}.
 */

import { useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Loader2, AlertCircle, User, Zap, Clock, ChevronRight,
  ArrowRight, Activity, Radio, BookOpen, Layers, Sparkles, Play
} from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { API_BASE } from '@/lib/api/client';
import EventPreviewModal from '@/components/EventPreviewModal';

// ── Types ─────────────────────────────────────────────────────────────────────
interface SlimEvent {
  event_id: string;
  event_type: string;
  start_ms: number;
  end_ms?: number;
  confidence?: number;
  rule_name?: string;
  display_name: string;
}

interface StoryArc {
  story_id: string;
  person_label: string | null;
  track_id: number | string | null;
  key: string;
  events: SlimEvent[];
  event_count: number;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  start_formatted: string;
  end_formatted: string;
  summary: string;
  avg_confidence: number;
  entry_direction: string | null;
  exit_direction: string | null;
  crop_url: string | null;
}

interface StoriesResponse {
  video_id: string;
  filename?: string;
  status: string;
  stories: StoryArc[];
  total_stories: number;
  total_events: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtMs(ms: number): string {
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${(s % 60).toFixed(0)}s` : `${s.toFixed(1)}s`;
}

function confColor(c: number): string {
  if (c >= 0.9) return 'bg-emerald-400';
  if (c >= 0.7) return 'bg-indigo-400';
  if (c >= 0.5) return 'bg-amber-400';
  return 'bg-rose-400';
}

function eventDotConfig(eventType: string): { bg: string; ring: string; glow: string } {
  if (eventType.includes('enter') || eventType.includes('entered'))
    return { bg: 'bg-emerald-400', ring: 'ring-emerald-400/40', glow: 'shadow-[0_0_10px_rgba(16,185,129,0.4)]' };
  if (eventType.includes('left') || eventType.includes('exit'))
    return { bg: 'bg-rose-400', ring: 'ring-rose-400/40', glow: 'shadow-[0_0_10px_rgba(244,63,94,0.4)]' };
  if (eventType.includes('run'))
    return { bg: 'bg-pink-400', ring: 'ring-pink-400/40', glow: 'shadow-[0_0_10px_rgba(236,72,153,0.4)]' };
  if (eventType.includes('loiter'))
    return { bg: 'bg-amber-400', ring: 'ring-amber-400/40', glow: 'shadow-[0_0_10px_rgba(245,158,11,0.4)]' };
  if (eventType.includes('phone') || eventType.includes('laptop'))
    return { bg: 'bg-cyan-400', ring: 'ring-cyan-400/40', glow: 'shadow-[0_0_10px_rgba(6,182,212,0.4)]' };
  if (eventType.includes('light'))
    return { bg: 'bg-yellow-400', ring: 'ring-yellow-400/40', glow: 'shadow-[0_0_10px_rgba(234,179,8,0.4)]' };
  return { bg: 'bg-indigo-400', ring: 'ring-indigo-400/40', glow: 'shadow-[0_0_10px_rgba(99,102,241,0.4)]' };
}

// ── Multi-track Story Arc Row ──────────────────────────────────────────────────
function StoryArcRow({
  arc, totalDurationMs, onEventClick, idx,
}: {
  arc: StoryArc;
  totalDurationMs: number;
  onEventClick: (eventId: string, eventType: string, startMs: number, confidence?: number) => void;
  idx: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const isScene = arc.key.startsWith('scene:');

  const spanLeftPct = totalDurationMs > 0 ? (arc.start_ms / totalDurationMs) * 100 : 0;
  const spanWidthPct = totalDurationMs > 0 ? Math.max(1, (arc.duration_ms / totalDurationMs) * 100) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.04 }}
      className={`
        surface-card rounded-2xl border transition-all duration-300 overflow-hidden
        ${expanded ? 'border-indigo-500/40 bg-[#0c0e16]' : 'hover:border-white/20'}
      `}
    >
      {/* Header bar */}
      <div
        className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-white/[0.02] transition-colors select-none"
        onClick={() => setExpanded(x => !x)}
      >
        {/* Avatar or Icon */}
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 relative overflow-hidden ${
          isScene ? 'bg-white/5 border border-white/10' : 'bg-violet-500/10 border border-violet-500/25'
        }`}>
          {arc.crop_url ? (
            <img
              src={arc.crop_url.startsWith('http') ? arc.crop_url : `${API_BASE}${arc.crop_url}`}
              alt={arc.person_label ?? 'Actor'}
              className="w-full h-full object-cover"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          ) : isScene ? (
            <Radio size={18} className="text-white/40" />
          ) : (
            <User size={18} className="text-violet-400" />
          )}
          <div className="absolute top-1 right-1 w-2 h-2 rounded-full bg-indigo-400 ring-2 ring-[#08090d]" />
        </div>

        {/* Identity & summary */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5">
            <span className="text-sm font-bold text-white tracking-tight">
              {arc.person_label ?? (arc.track_id != null ? `Track #${arc.track_id}` : 'Scene Global')}
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-white/40">
              {arc.story_id}
            </span>
            {arc.entry_direction && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
                in: {arc.entry_direction}
              </span>
            )}
            {arc.exit_direction && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-300">
                out: {arc.exit_direction}
              </span>
            )}
          </div>
          <p className="text-xs text-white/50 truncate mt-1">{arc.summary}</p>
        </div>

        {/* Sequence Metrics */}
        <div className="hidden sm:flex items-center gap-5 flex-shrink-0">
          <div className="text-right">
            <p className="text-xs font-mono text-white/80 font-medium">{arc.start_formatted} → {arc.end_formatted}</p>
            <p className="text-[10px] font-mono text-white/30">{fmtMs(arc.duration_ms)} active span</p>
          </div>

          <div className="text-right">
            <p className="text-sm font-mono font-bold text-white">{arc.event_count}</p>
            <p className="text-[10px] text-white/30 uppercase tracking-wider">events</p>
          </div>

          {arc.avg_confidence > 0 && (
            <div className="flex items-center gap-2">
              <div className="w-14 h-1.5 bg-black/40 rounded-full overflow-hidden border border-white/5">
                <div
                  className={`h-full rounded-full ${confColor(arc.avg_confidence)}`}
                  style={{ width: `${Math.round(arc.avg_confidence * 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-white/50 font-mono font-medium">
                {Math.round(arc.avg_confidence * 100)}%
              </span>
            </div>
          )}
        </div>

        <div className="text-white/30 hover:text-white transition-colors flex-shrink-0 ml-1">
          <ChevronRight
            size={16}
            className={`transition-transform duration-300 ${expanded ? 'rotate-90' : ''}`}
          />
        </div>
      </div>

      {/* Expanded Sequencer Track view */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/5 px-5 py-5 space-y-5 surface-inset">

              {/* Horizontal DAW Multi-track Sequencer */}
              {totalDurationMs > 0 && arc.events.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-[10px] font-mono text-white/40 uppercase tracking-wider">
                    <span>Sequencer Track</span>
                    <span>Span: {fmtMs(arc.duration_ms)}</span>
                  </div>

                  <div className="relative h-10 bg-[#090b10] rounded-xl overflow-visible border border-white/10 p-1 flex items-center">
                    {/* Background grid notches */}
                    <div className="absolute inset-0 flex justify-between px-2 pointer-events-none opacity-20">
                      {[...Array(11)].map((_, i) => (
                        <div key={i} className="h-full w-[1px] bg-white/20" />
                      ))}
                    </div>

                    {/* Active span region */}
                    <div
                      className="absolute top-1 bottom-1 bg-gradient-to-r from-indigo-500/20 via-violet-500/25 to-indigo-500/20 rounded-lg border border-indigo-500/40 shadow-[0_0_15px_rgba(99,102,241,0.15)]"
                      style={{
                        left: `${spanLeftPct}%`,
                        width: `${spanWidthPct}%`,
                      }}
                    />

                    {/* Interactive Event Nodes */}
                    {arc.events.map((evt) => {
                      const cfg = eventDotConfig(evt.event_type);
                      const leftPos = (evt.start_ms / totalDurationMs) * 100;
                      return (
                        <button
                          key={evt.event_id}
                          title={`${evt.display_name} @ ${fmtMs(evt.start_ms)}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onEventClick(evt.event_id, evt.event_type, evt.start_ms, evt.confidence);
                          }}
                          className={`
                            absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full
                            ring-2 ring-offset-1 ring-offset-[#090b10]
                            hover:scale-150 transition-all z-20 cursor-pointer
                            ${cfg.bg} ${cfg.ring} ${cfg.glow}
                          `}
                          style={{ left: `calc(${leftPos}% - 7px)` }}
                        />
                      );
                    })}
                  </div>

                  <div className="flex justify-between text-[9px] font-mono text-white/30 px-1">
                    <span>0:00</span>
                    <span>{fmtMs(totalDurationMs)}</span>
                  </div>
                </div>
              )}

              {/* Event Stream List */}
              <div className="space-y-1.5 pt-1">
                <p className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-2">Event Sequence</p>
                {arc.events.map((evt) => {
                  const cfg = eventDotConfig(evt.event_type);
                  return (
                    <button
                      key={evt.event_id}
                      onClick={() => onEventClick(evt.event_id, evt.event_type, evt.start_ms, evt.confidence)}
                      className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl surface-card hover:border-indigo-500/40 hover:bg-[#121622] transition-all text-left group border border-white/5"
                    >
                      <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${cfg.bg} ${cfg.glow}`} />
                      <span className="text-xs font-medium text-white/80 group-hover:text-white flex-1 truncate">
                        {evt.display_name}
                      </span>
                      <span className="text-[10px] font-mono text-white/40">{fmtMs(evt.start_ms)}</span>
                      {evt.confidence !== undefined && (
                        <span className="text-[10px] font-mono text-indigo-300/70 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20">
                          {Math.round(evt.confidence * 100)}%
                        </span>
                      )}
                      <div className="p-1 rounded bg-white/5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 text-white/60">
                        <Play size={10} />
                      </div>
                    </button>
                  );
                })}
              </div>

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function StoriesPage() {
  const { videoId } = useParams<{ videoId: string }>();
  const [data, setData] = useState<StoriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalEvent, setModalEvent] = useState<{
    id: string; type: string; startMs: number; confidence?: number;
  } | null>(null);

  useEffect(() => {
    if (!videoId) return;
    let mounted = true;
    fetch(`${API_BASE}/stories/${videoId}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { if (mounted) { setData(d); setLoading(false); } })
      .catch(e => { if (mounted) { setError(e.message); setLoading(false); } });
    return () => { mounted = false; };
  }, [videoId]);

  const totalDurationMs = useMemo(() => {
    if (!data?.stories.length) return 0;
    return Math.max(...data.stories.map(s => s.end_ms));
  }, [data]);

  const handleEventClick = (id: string, type: string, startMs: number, confidence?: number) => {
    setModalEvent({ id, type, startMs, confidence });
  };

  if (loading) return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
        <p className="text-white/40 text-xs font-mono uppercase tracking-widest animate-pulse">Constructing story arcs…</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center p-8 max-w-md surface-card rounded-3xl border border-red-500/20">
        <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400">
          <AlertCircle size={26} />
        </div>
        <h2 className="text-lg font-bold text-white">Story Arcs Inaccessible</h2>
        <p className="text-white/50 text-xs">{error}</p>
        <Link href={`/timeline/${videoId}`} className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-white/80 hover:bg-white/10 transition-colors">
          Return to Timeline
        </Link>
      </div>
    </div>
  );

  return (
    <div className="space-y-7 animate-slide-up">
      {/* Header & Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/5">
        <div>
          <div className="flex items-center gap-2 mb-1.5 text-xs">
            <Link href="/" className="text-white/40 hover:text-white/70 transition-colors">Dashboard</Link>
            <span className="text-white/20">›</span>
            <Link href={`/timeline/${videoId}`} className="text-white/40 hover:text-white/70 transition-colors">Timeline</Link>
            <span className="text-white/20">›</span>
            <span className="text-indigo-400 font-medium">Story Studio</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
            Multi-Track Story Arcs
            <span className="text-xs font-mono font-normal px-2.5 py-1 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
              {videoId}
            </span>
          </h1>
        </div>

        {data && data.total_stories > 0 && (
          <div className="flex items-center gap-3">
            <div className="surface-card px-4 py-2 rounded-xl border text-center">
              <p className="text-lg font-mono font-bold text-white">{data.total_stories}</p>
              <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono">Tracks</p>
            </div>
            <div className="surface-card px-4 py-2 rounded-xl border text-center">
              <p className="text-lg font-mono font-bold text-indigo-400">{data.total_events}</p>
              <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono">Total Events</p>
            </div>
          </div>
        )}
      </div>

      {/* Guide Banner */}
      {data && data.total_stories > 0 && (
        <div className="p-4 rounded-2xl surface-card border border-indigo-500/20 flex items-center gap-3 text-xs text-indigo-300/80">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 flex-shrink-0">
            <Layers size={16} />
          </div>
          <p className="leading-relaxed">
            Each timeline channel corresponds to a distinct tracked person or global scene entity.
            Nodes indicate discrete detected actions. Expand any channel to inspect chronological event progression and inspect raw visual frames.
          </p>
        </div>
      )}

      {/* Zero stories state */}
      {data && data.total_stories === 0 && (
        <div className="surface-card p-12 rounded-3xl border flex flex-col items-center justify-center text-center gap-3">
          <BookOpen className="w-12 h-12 text-white/20 mb-2" />
          <h3 className="text-base font-semibold text-white">Zero Story Arcs Formed</h3>
          <p className="text-xs text-white/40 max-w-sm">
            No person tracking tracks or discrete activity events were synthesized for this video feed.
          </p>
          <Link href={`/timeline/${videoId}`} className="mt-2 text-xs text-indigo-400 hover:text-indigo-300">
            ← View Raw Timeline
          </Link>
        </div>
      )}

      {/* Multi-Track Channel Arcs */}
      {data && data.stories.length > 0 && (
        <div className="space-y-3.5">
          {data.stories.map((arc, idx) => (
            <StoryArcRow
              key={arc.story_id}
              arc={arc}
              totalDurationMs={totalDurationMs}
              onEventClick={handleEventClick}
              idx={idx}
            />
          ))}
        </div>
      )}

      {/* Modal */}
      {modalEvent && (
        <EventPreviewModal
          eventId={modalEvent.id}
          eventType={modalEvent.type}
          startMs={modalEvent.startMs}
          confidence={modalEvent.confidence}
          onClose={() => setModalEvent(null)}
        />
      )}
    </div>
  );
}
