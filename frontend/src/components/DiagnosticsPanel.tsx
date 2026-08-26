'use client';

/**
 * DiagnosticsPanel
 *
 * Collapsible panel showing job diagnostics from:
 *   GET /api/v1/jobs/{jobId}/diagnostics
 *
 * Sections:
 *  - Frame Statistics   (s02 metrics)
 *  - Detection Stats    (s04 metrics)
 *  - Event Statistics   (s07 metrics)
 *  - Stage Timing       (stages[] array)
 *  - Export             (s12 metrics)
 *
 * Rules:
 *  - Null / undefined field → show "—", never "null" or "0"
 *  - 404 → "Diagnostics unavailable for this job"
 *  - No mock data
 */

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown, ChevronUp, Loader2, AlertCircle,
  Activity, Eye, Layers, Clock, Package,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

// ── Types ─────────────────────────────────────────────────────────────────────

interface StageTimingRow {
  name: string;
  label: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  duration_ms: number | null;
}

interface FrameStats {
  frames_extracted?: number | null;
  total_video_frames?: number | null;
  frame_reduction_ratio?: number | null;
  adaptive_skip_enabled?: boolean | null;
  sampling_ratio?: number | null;
  skip_source?: string | null;
}

interface DetectionStats {
  total_detections?: number | null;
  low_light_frames?: number | null;
  unusable_frames_skipped?: number | null;
  frames_preprocessed_clahe?: number | null;
}

interface EventStats {
  total_events?: number | null;
  events_by_type?: Record<string, number> | null;
  roi_events?: number | null;
  pose_temporal_events?: number | null;
}

interface ExportStats {
  thumbnails_generated?: number | null;
  clips_generated?: number | null;
  ffmpeg_available?: boolean | null;
}

interface DiagnosticsData {
  job_id: string;
  frame_stats?: FrameStats | null;
  detection_stats?: DetectionStats | null;
  event_stats?: EventStats | null;
  stage_timing?: StageTimingRow[] | null;
  export_stats?: ExportStats | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Display a value: null/undefined → "—" */
function D(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function stageStatusColor(status: StageTimingRow['status']): string {
  switch (status) {
    case 'success': return 'text-emerald-400';
    case 'failed':  return 'text-red-400';
    case 'running': return 'text-indigo-400';
    default:        return 'text-white/30';
  }
}

// ── Sub-sections ──────────────────────────────────────────────────────────────

function Section({ icon: Icon, title, children }: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] text-white/40 uppercase tracking-wider flex items-center gap-1.5">
        <Icon className="w-3 h-3" /> {title}
      </p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-baseline gap-4 text-xs">
      <span className="text-white/40 shrink-0">{label}</span>
      <span className="font-mono text-white/75 text-right">{value}</span>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export interface DiagnosticsPanelProps {
  jobId: string;
  /** Poll interval in ms. Default 3000. Pass 0 to disable polling. */
  refreshInterval?: number;
}

export default function DiagnosticsPanel({
  jobId,
  refreshInterval = 3000,
}: DiagnosticsPanelProps) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<DiagnosticsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchDiagnostics = useCallback(async () => {
    if (!jobId) return;
    try {
      const res = await fetch(`${API}/jobs/${jobId}/diagnostics`);
      if (res.status === 404) {
        setUnavailable(true);
        setLoading(false);
        return;
      }
      if (!res.ok) {
        setFetchError(`Diagnostics fetch failed (${res.status})`);
        setLoading(false);
        return;
      }
      const json: DiagnosticsData = await res.json();
      setData(json);
      setUnavailable(false);
      setFetchError(null);
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : 'Network error');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  // Load data when panel first opens, then poll
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetchDiagnostics();

    if (refreshInterval <= 0) return;
    const id = setInterval(fetchDiagnostics, refreshInterval);
    return () => clearInterval(id);
  }, [open, fetchDiagnostics, refreshInterval]);

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] overflow-hidden">
      {/* Toggle button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.04] transition-colors"
      >
        <Activity className="w-4 h-4 text-white/40" />
        <span className="text-sm font-medium text-white/70">Diagnostics</span>
        {loading && open && (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-white/30 ml-1" />
        )}
        <span className="ml-auto">
          {open
            ? <ChevronUp className="w-4 h-4 text-white/30" />
            : <ChevronDown className="w-4 h-4 text-white/30" />}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/[0.06] p-4 space-y-5">

              {/* Loading state */}
              {loading && !data && !unavailable && !fetchError && (
                <div className="flex items-center gap-2 text-white/30 text-sm py-4 justify-center">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Loading diagnostics…</span>
                </div>
              )}

              {/* 404 / unavailable */}
              {unavailable && (
                <div className="flex items-center gap-2 text-white/30 text-sm py-2">
                  <AlertCircle className="w-4 h-4 text-white/20" />
                  Diagnostics unavailable for this job.
                </div>
              )}

              {/* Fetch error (non-404) */}
              {fetchError && !unavailable && (
                <div className="flex items-center gap-2 text-red-400/60 text-xs font-mono py-2">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {fetchError}
                </div>
              )}

              {/* Data sections */}
              {data && !unavailable && (
                <>
                  {/* 1. Frame Statistics */}
                  {data.frame_stats && (
                    <Section icon={Eye} title="Frame Statistics">
                      <Row label="Frames extracted"
                        value={D(data.frame_stats.frames_extracted)} />
                      <Row label="Total video frames"
                        value={D(data.frame_stats.total_video_frames)} />
                      <Row label="Frame reduction ratio"
                        value={
                          data.frame_stats.frame_reduction_ratio != null
                            ? `${(data.frame_stats.frame_reduction_ratio * 100).toFixed(1)}%`
                            : '—'
                        }
                      />
                      <Row label="Adaptive skip"
                        value={D(data.frame_stats.adaptive_skip_enabled)} />
                      {data.frame_stats.adaptive_skip_enabled && (
                        <Row label="Sampling ratio"
                          value={
                            data.frame_stats.sampling_ratio != null
                              ? data.frame_stats.sampling_ratio.toFixed(3)
                              : '—'
                          }
                        />
                      )}
                      <Row label="Skip source" value={D(data.frame_stats.skip_source)} />
                    </Section>
                  )}

                  {/* 2. Detection Statistics */}
                  {data.detection_stats && (
                    <Section icon={Activity} title="Detection Statistics">
                      <Row label="Total detections"
                        value={D(data.detection_stats.total_detections)} />
                      <Row label="Low-light frames"
                        value={D(data.detection_stats.low_light_frames)} />
                      <Row label="Unusable frames skipped"
                        value={D(data.detection_stats.unusable_frames_skipped)} />
                      <Row label="Frames preprocessed (CLAHE)"
                        value={D(data.detection_stats.frames_preprocessed_clahe)} />
                    </Section>
                  )}

                  {/* 3. Event Statistics */}
                  {data.event_stats && (
                    <Section icon={Layers} title="Event Statistics">
                      <Row label="Total events"
                        value={D(data.event_stats.total_events)} />
                      {data.event_stats.events_by_type &&
                        Object.keys(data.event_stats.events_by_type).length > 0 && (
                          <div className="pl-2 space-y-1 border-l border-white/[0.06] ml-1">
                            {Object.entries(data.event_stats.events_by_type).map(([k, v]) => (
                              <Row key={k}
                                label={k.replace(/_/g, ' ')}
                                value={String(v)}
                              />
                            ))}
                          </div>
                        )}
                      <Row label="ROI events" value={D(data.event_stats.roi_events)} />
                      <Row label="Pose / temporal events"
                        value={D(data.event_stats.pose_temporal_events)} />
                    </Section>
                  )}

                  {/* 4. Stage Timing */}
                  {data.stage_timing && data.stage_timing.length > 0 && (
                    <Section icon={Clock} title="Stage Timing">
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-white/25 uppercase tracking-wider">
                              <th className="text-left pb-1.5 pr-4 font-normal">Stage</th>
                              <th className="text-left pb-1.5 pr-4 font-normal">Status</th>
                              <th className="text-right pb-1.5 font-normal">Duration</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/[0.04]">
                            {data.stage_timing.map((s) => (
                              <tr key={s.name}>
                                <td className="py-1 pr-4 text-white/60 font-mono">{s.label || s.name}</td>
                                <td className={`py-1 pr-4 font-medium ${stageStatusColor(s.status)}`}>
                                  {s.status}
                                </td>
                                <td className="py-1 text-right font-mono text-white/50">
                                  {fmtMs(s.duration_ms)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </Section>
                  )}

                  {/* 5. Export */}
                  {data.export_stats && (
                    <Section icon={Package} title="Export">
                      <Row label="Thumbnails generated"
                        value={D(data.export_stats.thumbnails_generated)} />
                      <Row label="Clips generated"
                        value={D(data.export_stats.clips_generated)} />
                      <Row label="FFmpeg available"
                        value={D(data.export_stats.ffmpeg_available)} />
                    </Section>
                  )}

                  {/* Nothing returned at all */}
                  {!data.frame_stats &&
                    !data.detection_stats &&
                    !data.event_stats &&
                    !data.export_stats &&
                    (!data.stage_timing || data.stage_timing.length === 0) && (
                      <p className="text-xs text-white/25 text-center py-2">
                        No diagnostic data returned by the backend.
                      </p>
                    )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
