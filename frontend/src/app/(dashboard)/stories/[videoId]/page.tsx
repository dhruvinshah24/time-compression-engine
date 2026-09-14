'use client';

/**
 * Stories Page — /stories/[videoId]
 *
 * Visualizes story arcs per person/track detected by the TCE pipeline.
 * Each row is one actor (person or track). Events are shown as dots on
 * a horizontal time axis. Click any event dot to open EventPreviewModal.
 *
 * Data: GET /api/v1/stories/{videoId}
 * Real data only — no fake arcs, no mock events.
 */

import { useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Loader2, AlertCircle, User, Zap, Clock, ChevronRight,
  ArrowRight, Activity, Radio, BookOpen,
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
  if (c >= 0.9) return 'bg-emerald-500';
  if (c >= 0.7) return 'bg-indigo-500';
  if (c >= 0.5) return 'bg-amber-500';
  return 'bg-red-500';
}

function eventDotColor(eventType: string): string {
  if (eventType.includes('enter') || eventType.includes('entered')) return 'bg-emerald-400 ring-emerald-400/30';
  if (eventType.includes('left') || eventType.includes('exit')) return 'bg-red-400 ring-red-400/30';
  if (eventType.includes('run')) return 'bg-rose-400 ring-rose-400/30';
  if (eventType.includes('loiter')) return 'bg-amber-400 ring-amber-400/30';
  if (eventType.includes('phone') || eventType.includes('laptop')) return 'bg-cyan-400 ring-cyan-400/30';
  if (eventType.includes('light')) return 'bg-yellow-400 ring-yellow-400/30';
  return 'bg-indigo-400 ring-indigo-400/30';
}

// ── Story Arc Row ─────────────────────────────────────────────────────────────
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.04 }}
      className="rounded-2xl bg-white/[0.025] border border-white/[0.07] overflow-hidden"
    >
      {/* Header row */}
      <div
        className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-white/[0.03] transition-colors"
        onClick={() => setExpanded(x => !x)}
      >
        {/* Avatar */}
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
          isScene ? 'bg-white/5 border border-white/10' : 'bg-violet-500/15 border border-violet-500/25'
        }`}>
          {arc.crop_url ? (
            <img
              src={arc.crop_url.startsWith('http') ? arc.crop_url : `${API_BASE}${arc.crop_url}`}
              alt={arc.person_label ?? 'Actor'}
              className="w-full h-full object-cover rounded-xl"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          ) : isScene ? (
            <Radio size={16} className="text-white/30" />
          ) : (
            <User size={16} className="text-violet-400" />
          )}
        </div>

        {/* Label + summary */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white">
              {arc.person_label ?? (arc.track_id != null ? `Track ${arc.track_id}` : 'Scene Events')}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-white/30">
              {arc.story_id}
            </span>
          </div>
          <p className="text-xs text-white/40 truncate mt-0.5">{arc.summary}</p>
        </div>

        {/* Stats */}
        <div className="hidden sm:flex items-center gap-4 flex-shrink-0">
          <div className="text-right">
            <p className="text-xs font-mono text-white/60">{arc.start_formatted} → {arc.end_formatted}</p>
            <p className="text-[10px] text-white/25">{fmtMs(arc.duration_ms)} span</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-bold text-white">{arc.event_count}</p>
            <p className="text-[10px] text-white/25">events</p>
          </div>
          {arc.avg_confidence > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-12 h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${confColor(arc.avg_confidence)}`}
                  style={{ width: `${Math.round(arc.avg_confidence * 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-white/30 font-mono">
                {Math.round(arc.avg_confidence * 100)}%
              </span>
            </div>
          )}
        </div>

        <ChevronRight
          size={14}
          className={`text-white/25 flex-shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
        />
      </div>

      {/* Timeline + event list */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/[0.05] px-5 py-4 space-y-4">

              {/* Entry / exit info */}
              {(arc.entry_direction || arc.exit_direction) && (
                <div className="flex items-center gap-3 text-xs text-white/40">
                  {arc.entry_direction && (
                    <span className="flex items-center gap-1">
                      <span className="text-emerald-400">↓</span> Entered {arc.entry_direction}
                    </span>
                  )}
                  {arc.entry_direction && arc.exit_direction && <span className="text-white/15">·</span>}
                  {arc.exit_direction && (
                    <span className="flex items-center gap-1">
                      <span className="text-red-400">↑</span> Exited {arc.exit_direction}
                    </span>
                  )}
                </div>
              )}

              {/* Horizontal time axis with event dots */}
              {totalDurationMs > 0 && arc.events.length > 0 && (
                <div className="relative">
                  <div className="text-[10px] text-white/20 uppercase tracking-wider mb-2">Timeline</div>
                  <div className="relative h-6 bg-white/[0.03] rounded-full overflow-visible border border-white/[0.06]">
                    {/* Arc span bar */}
                    <div
                      className="absolute top-0 h-full bg-indigo-500/15 rounded-full"
                      style={{
                        left: `${(arc.start_ms / totalDurationMs) * 100}%`,
                        width: `${Math.max(0.5, (arc.duration_ms / totalDurationMs) * 100)}%`,
                      }}
                    />
                    {/* Event dots */}
                    {arc.events.map((evt) => (
                      <button
                        key={evt.event_id}
                        title={`${evt.display_name} @ ${fmtMs(evt.start_ms)}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          onEventClick(evt.event_id, evt.event_type, evt.start_ms, evt.confidence);
                        }}
                        className={`absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full ring-2 ring-offset-1 ring-offset-[#09090b] transition-transform hover:scale-150 z-10 ${eventDotColor(evt.event_type)}`}
                        style={{ left: `calc(${(evt.start_ms / totalDurationMs) * 100}% - 6px)` }}
                      />
                    ))}
                  </div>
                  <div className="flex justify-between text-[9px] text-white/15 mt-1">
                    <span>0:00</span>
                    <span>{fmtMs(totalDurationMs)}</span>
                  </div>
                </div>
              )}

              {/* Event list */}
              <div className="space-y-1">
                {arc.events.map((evt, i) => (
                  <button
                    key={evt.event_id}
                    onClick={() => onEventClick(evt.event_id, evt.event_type, evt.start_ms, evt.confidence)}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/[0.04] transition-colors text-left group"
                  >
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${eventDotColor(evt.event_type).split(' ')[0]}`} />
                    <span className="text-xs text-white/70 flex-1 truncate">{evt.display_name}</span>
                    <span className="text-[10px] text-white/25 font-mono">{fmtMs(evt.start_ms)}</span>
                    {evt.confidence !== undefined && (
                      <span className="text-[10px] text-white/25 font-mono">
                        {Math.round(evt.confidence * 100)}%
                      </span>
                    )}
                    <ArrowRight size={11} className="text-white/15 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                  </button>
                ))}
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

  // Total video duration for timeline axis
  const totalDurationMs = useMemo(() => {
    if (!data?.stories.length) return 0;
    return Math.max(...data.stories.map(s => s.end_ms));
  }, [data]);

  const handleEventClick = (id: string, type: string, startMs: number, confidence?: number) => {
    setModalEvent({ id, type, startMs, confidence });
  };

  if (loading) return (
    <div className="flex items-center justify-center py-32">
      <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center justify-center py-32 gap-3 text-center">
      <AlertCircle className="w-10 h-10 text-red-400" />
      <p className="text-white font-medium">Could not load stories</p>
      <p className="text-white/40 text-sm">{error}</p>
      <Link href={`/timeline/${videoId}`} className="text-indigo-400 text-sm hover:text-indigo-300 mt-2">
        ← Back to Timeline
      </Link>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <Link href="/" className="text-white/30 hover:text-white/60 transition-colors">Dashboard</Link>
        <span className="text-white/20">›</span>
        <Link href={`/timeline/${videoId}`} className="text-white/30 hover:text-white/60 transition-colors">Timeline</Link>
        <span className="text-white/20">›</span>
        <span className="text-white/50">Stories</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Story Arcs</h1>
          <p className="text-white/30 text-sm mt-1">
            {data?.filename?.replace('original.mp4', 'Video') ?? videoId}
          </p>
        </div>
        {data && data.total_stories > 0 && (
          <div className="flex gap-3">
            <div className="text-center">
              <p className="text-2xl font-bold text-white">{data.total_stories}</p>
              <p className="text-[10px] text-white/30">Story Arcs</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-indigo-400">{data.total_events}</p>
              <p className="text-[10px] text-white/30">Total Events</p>
            </div>
          </div>
        )}
      </div>

      {/* Not processed yet */}
      {data && data.status !== 'completed' && (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
          <p className="text-white/50 text-sm">Pipeline not complete — status: {data.status}</p>
          <Link href="/" className="text-indigo-400 text-sm hover:text-indigo-300">← Dashboard</Link>
        </div>
      )}

      {/* Empty state */}
      {data && data.status === 'completed' && data.total_stories === 0 && (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-2">
            <BookOpen className="w-8 h-8 text-white/15" />
          </div>
          <p className="text-white font-medium">No story arcs found</p>
          <p className="text-white/35 text-sm max-w-sm">
            Story arcs require at least one detected event attributed to a person or track.
            Process a video with person detections to generate stories.
          </p>
          <Link href={`/timeline/${videoId}`} className="text-indigo-400 text-sm hover:text-indigo-300 mt-2">
            View Timeline →
          </Link>
        </div>
      )}

      {/* Intro explanation (only when data exists) */}
      {data && data.total_stories > 0 && (
        <div className="p-4 rounded-2xl bg-indigo-500/5 border border-indigo-500/15 text-sm text-indigo-300/70">
          Each row is one identified actor. Dots on the timeline axis represent individual events.
          Click a dot or expand a row to inspect events and open the frame preview.
        </div>
      )}

      {/* Story arcs */}
      {data && data.stories.length > 0 && (
        <div className="space-y-3">
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

      {/* Event Preview Modal */}
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
