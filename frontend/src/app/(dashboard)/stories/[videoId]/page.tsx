'use client';

import { useEffect, useState, useMemo } from 'react';
import {
  Loader2, AlertCircle, User, Zap, Clock, ChevronRight,
  ArrowRight, Activity, Radio, BookOpen, Layers, Play,
  ChevronDown, ExternalLink, ShieldCheck, Eye, Sparkles
} from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { api, API_BASE, BACKEND_URL } from '@/lib/api/client';
import EventPreviewModal from '@/components/EventPreviewModal';
import { StoriesSkeleton } from '@/components/skeletons/StoriesSkeleton';

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

function fmtMs(ms: number): string {
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  const remS = Math.floor(s % 60);
  return `${String(m).padStart(2, '0')}:${String(remS).padStart(2, '0')}`;
}

function formatDuration(ms: number): string {
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${(s % 60).toFixed(0)}s` : `${s.toFixed(1)}s`;
}

function formatLabel(str: string): string {
  return str.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function StoriesPage() {
  const router = useRouter();
  const params = useParams();
  const videoId = params.videoId as string;

  const [data, setData] = useState<StoriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewEventId, setPreviewEventId] = useState<string | null>(null);
  const [selectedEventData, setSelectedEventData] = useState<SlimEvent | null>(null);
  const [activeStory, setActiveStory] = useState<StoryArc | null>(null);

  useEffect(() => {
    let mounted = true;
    (api.stories(videoId) as Promise<StoriesResponse>)
      .then((res) => {
        if (mounted) {
          setData(res);
          if (res.stories && res.stories.length > 0) {
            setActiveStory(res.stories[0]);
          }
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [videoId]);

  const totalDurationMs = useMemo(() => {
    if (!data?.stories?.length) return 60000;
    const maxEnd = Math.max(...data.stories.map((s) => s.end_ms), 60000);
    return Math.max(maxEnd, 60000);
  }, [data]);

  // Generate 5 calibration ruler points across duration
  const rulerTicks = useMemo(() => {
    const ticks = [];
    const count = 6;
    for (let i = 0; i <= count; i++) {
      const ms = Math.round((totalDurationMs / count) * i);
      ticks.push({ ms, pct: (i / count) * 100, label: fmtMs(ms) });
    }
    return ticks;
  }, [totalDurationMs]);

  if (loading) {
    return <StoriesSkeleton />;
  }

  if (error || !data) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div className="card" style={{ maxWidth: 440, margin: '0 auto', padding: 24 }}>
          <AlertCircle size={28} style={{ color: 'var(--warning)', margin: '0 auto 10px' }} />
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>Story Arcs Not Available</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>{error || 'No story arc telemetry generated for this recording.'}</p>
          <Link href="/" className="btn btn-secondary" style={{ textDecoration: 'none' }}>
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* ── Breadcrumb & Header ────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6
          }}>
            <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Dashboard</Link>
            <span>/</span>
            <Link href={`/timeline/${videoId}`} style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Forensic Timeline</Link>
            <span>/</span>
            <span style={{ color: 'var(--text-secondary)' }}>Temporal Sequencer</span>
          </div>

          <h1 style={{
            fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
            letterSpacing: '-0.02em', margin: 0
          }}>
            Actor Continuity & Story Sequencer
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2, marginBottom: 0 }}>
            DAW-style multi-track timeline tracking each actor&apos;s entry, dwell duration, object interactions, and trajectory exit.
          </p>
        </div>

        {/* Right Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Link href={`/timeline/${videoId}`} style={{ textDecoration: 'none' }}>
            <button className="btn btn-primary" style={{ fontSize: 12, padding: '8px 18px', fontWeight: 700 }}>
              <Play size={13} />
              <span>Launch Forensic Timeline</span>
            </button>
          </Link>
        </div>
      </div>

      {/* ── Summary Operational Metrics Strip ───────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
        <div className="card" style={{ padding: '16px 18px' }}>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Tracked Personas
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', marginTop: 4 }}>
            {data.total_stories} Identities
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Discrete re-identified tracks
          </div>
        </div>

        <div className="card" style={{ padding: '16px 18px' }}>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Causal Event Chains
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', marginTop: 4 }}>
            {data.total_events} Synthesized
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Inter-object interactions
          </div>
        </div>

        <div className="card" style={{ padding: '16px 18px' }}>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Total Surveillance Span
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--accent)', marginTop: 4 }}>
            {formatDuration(totalDurationMs)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Calibrated time axis
          </div>
        </div>
      </div>

      {/* ── Main DAW Timeline Sequencer Workspace ───────────────────────── */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', border: '1px solid var(--border)' }}>
        {/* Sequencer Toolbar & Shared Time Ruler */}
        <div style={{
          backgroundColor: 'var(--bg-raised)',
          borderBottom: '1px solid var(--border)',
          padding: '12px 18px',
          display: 'grid',
          gridTemplateColumns: '280px 1fr',
          gap: 16,
          alignItems: 'center'
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Layers size={14} style={{ color: 'var(--accent)' }} />
            <span>Actor Identity Tracks</span>
          </div>

          {/* Shared Time Ruler with Ticks */}
          <div style={{ position: 'relative', height: 24, display: 'flex', alignItems: 'center' }}>
            <div style={{ position: 'absolute', left: 0, right: 0, height: 1, backgroundColor: 'var(--border)' }} />
            {rulerTicks.map((tick, i) => (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: `${tick.pct}%`,
                  transform: 'translateX(-50%)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center'
                }}
              >
                <div style={{ width: 1, height: 6, backgroundColor: 'var(--border)' }} />
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
                  {tick.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Multi-Track Swimlanes List */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {data.stories.length === 0 ? (
            <div style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <Layers size={32} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>
                No Actor Story Arcs Detected
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, maxWidth: 420, margin: '4px auto 0' }}>
                Continuous tracks in this stream have not produced separated story arcs. Verify that actors are present and tracked across sufficient frame duration.
              </p>
            </div>
          ) : (
            data.stories.map((arc, idx) => {
            const startPct = Math.max(0, Math.min(100, (arc.start_ms / totalDurationMs) * 100));
            const endPct = Math.max(startPct + 3, Math.min(100, (arc.end_ms / totalDurationMs) * 100));
            const widthPct = Math.max(4, endPct - startPct);
            const isSelected = activeStory?.story_id === arc.story_id;

            return (
              <div
                key={arc.story_id || idx}
                onClick={() => setActiveStory(arc)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '280px 1fr',
                  gap: 16,
                  padding: '16px 18px',
                  borderBottom: idx === data.stories.length - 1 ? 'none' : '1px solid var(--border-dim)',
                  backgroundColor: isSelected ? 'var(--selected-surface)' : idx % 2 === 1 ? 'rgba(255,255,255,0.015)' : 'transparent',
                  transition: 'background-color 0.15s ease',
                  cursor: 'pointer'
                }}
              >
                {/* Left Track Identity Info */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: 5,
                    backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    overflow: 'hidden', flexShrink: 0
                  }}>
                    {arc.crop_url ? (
                      <img
                        src={arc.crop_url.startsWith('http') ? arc.crop_url : `${BACKEND_URL}${arc.crop_url}`}
                        alt={arc.person_label || 'Actor'}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    ) : (
                      <User size={18} style={{ color: 'var(--accent)' }} />
                    )}
                  </div>

                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {arc.person_label || `Actor (Track #${arc.track_id})`}
                      </span>
                      <span className="badge badge-accent" style={{ fontSize: 9 }}>
                        {arc.event_count} evts
                      </span>
                    </div>

                    <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
                      {fmtMs(arc.start_ms)} → {fmtMs(arc.end_ms)} ({formatDuration(arc.duration_ms)})
                    </div>

                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                      {arc.entry_direction ? `In: ${arc.entry_direction}` : ''}
                      {arc.exit_direction ? ` • Out: ${arc.exit_direction}` : ''}
                    </div>
                  </div>
                </div>

                {/* Right Swimlane Timeline Track */}
                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6 }}>
                  <div style={{
                    position: 'relative', height: 36,
                    backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-dim)',
                    borderRadius: 6, overflow: 'hidden'
                  }}>
                    {/* Active In-Scene Presence Span */}
                    <div
                      style={{
                        position: 'absolute',
                        left: `${startPct}%`,
                        width: `${widthPct}%`,
                        top: 4, bottom: 4,
                        backgroundColor: 'rgba(98, 221, 176, 0.15)',
                        border: '1px solid var(--accent-dim)',
                        borderRadius: 4,
                      }}
                    />

                    {/* Event Nodes plotted on the timeline */}
                    {arc.events.map((evt, eIdx) => {
                      const evtPos = Math.max(0, Math.min(100, (evt.start_ms / totalDurationMs) * 100));

                      return (
                        <div
                          key={evt.event_id || eIdx}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEventData(evt);
                            setPreviewEventId(evt.event_id);
                          }}
                          title={`${evt.display_name || formatLabel(evt.event_type)} at ${fmtMs(evt.start_ms)} (Click to inspect)`}
                          style={{
                            position: 'absolute',
                            left: `${evtPos}%`,
                            top: 6,
                            width: 10, height: 22,
                            borderRadius: 2,
                            backgroundColor: 'var(--accent)',
                            cursor: 'pointer',
                            transform: 'translateX(-50%)',
                            boxShadow: '0 0 8px rgba(98, 221, 176, 0.5)',
                            zIndex: 10,
                            transition: 'transform 0.1s ease',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateX(-50%) scale(1.25)')}
                          onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateX(-50%) scale(1.0)')}
                        />
                      );
                    })}
                  </div>

                  {/* Summary preview on selected */}
                  {isSelected && (
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      fontSize: 11, color: 'var(--text-secondary)', padding: '4px 6px'
                    }}>
                      <span>{arc.summary}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/timeline/${videoId}?time=${arc.start_ms}`);
                        }}
                        className="btn btn-secondary"
                        style={{ fontSize: 10, padding: '2px 8px', height: 22 }}
                      >
                        <span>Seek to Ingress ({fmtMs(arc.start_ms)})</span>
                        <ArrowRight size={10} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
        </div>
      </div>

      {/* ── Active Story Arc Inspector Drawer ───────────────────────────── */}
      {activeStory && (
        <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Sparkles size={16} style={{ color: 'var(--accent)' }} />
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                Identity Arc Dossier: {activeStory.person_label || `Actor #${activeStory.track_id}`}
              </div>
            </div>

            <button
              onClick={() => router.push(`/timeline/${videoId}?time=${activeStory.start_ms}`)}
              className="btn btn-primary"
              style={{ fontSize: 11, padding: '5px 12px' }}
            >
              <span>Play Arc in Timeline</span>
              <Play size={11} />
            </button>
          </div>

          <div className="card-inset" style={{ padding: 14 }}>
            <div style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-primary)' }}>
              {activeStory.summary}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
              Sequence of Causal Events in Arc ({activeStory.events.length})
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
              {activeStory.events.map((evt, i) => (
                <div
                  key={evt.event_id || i}
                  onClick={() => {
                    setSelectedEventData(evt);
                    setPreviewEventId(evt.event_id);
                  }}
                  className="card-inset"
                  style={{
                    padding: '8px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    cursor: 'pointer', transition: 'all 0.15s'
                  }}
                >
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {evt.display_name || formatLabel(evt.event_type)}
                    </div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent)', marginTop: 2 }}>
                      {fmtMs(evt.start_ms)}
                    </div>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      router.push(`/timeline/${videoId}?time=${evt.start_ms}`);
                    }}
                    className="btn btn-ghost"
                    style={{ fontSize: 10, padding: '2px 6px' }}
                    title="Seek to this timestamp in timeline"
                  >
                    <ArrowRight size={12} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Modal */}
      {previewEventId && (
        <EventPreviewModal
          eventId={previewEventId}
          eventType={selectedEventData?.event_type}
          confidence={selectedEventData?.confidence}
          startMs={selectedEventData?.start_ms}
          onClose={() => {
            setPreviewEventId(null);
            setSelectedEventData(null);
          }}
        />
      )}
    </div>
  );
}
