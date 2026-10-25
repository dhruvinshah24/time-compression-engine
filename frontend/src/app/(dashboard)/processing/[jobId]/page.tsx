'use client';

import {
  CheckCircle2, XCircle, Loader2, Clock, AlertCircle,
  Terminal, Cpu, Zap, Film, Activity, Play, ShieldCheck,
  RefreshCw, ArrowRight, FileText, Check, Copy, Eye, Timer
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
  unique_persons?: number;
  video_metadata: Record<string, unknown>;
}

const STAGE_DESCRIPTIONS: Record<string, string> = {
  s01_upload: 'Validating container stream integrity, ffprobe extraction, resolution & framerate indexing.',
  s02_extract: 'Adaptive motion-aware keyframe extraction (MOG2 background subtractor gating).',
  s03_scene_detect: 'HSV histogram correlation and content-aware cut boundary detection.',
  s04_object_detect: 'YOLO neural detection & keypoint pose estimation across candidate keyframes.',
  s05_track: 'ByteTrack multi-object tracking and cosine feature ReID vector association.',
  s06_motion_analyze: 'Lucas-Kanade optical flow vector calculation & camera shake compensation.',
  s07_event_understand: 'Deterministic finite state machines: posture, interaction, and scene entry rules.',
  s08_confidence_fuse: 'Multi-modal Bayesian evidence fusion across visual, motion, and temporal priors.',
  s09_story_build: 'Constructing directed acyclic event graph and causal preservation arcs.',
  s10_rank: 'Information density scoring and narrative criticality weighting.',
  s11_summarize: 'Knapsack dynamic programming compression policy optimization.',
  s12_export: 'Generating forensic evidence thumbnails, highlight clips, and JSON audit dossier.',
};

const DEFAULT_STAGES: StageRecord[] = [
  { name: 's01_upload', label: 'Ingest & Probe', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's02_extract', label: 'Keyframe Extraction', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's03_scene_detect', label: 'Scene Detection', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's04_object_detect', label: 'Object & Pose Detection', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's05_track', label: 'Actor Tracking (ByteTrack)', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's06_motion_analyze', label: 'Motion & Optical Flow', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's07_event_understand', label: 'Causal Event Engine', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's08_confidence_fuse', label: 'Confidence Fusion', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's09_story_build', label: 'Story Arc Preservation', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's10_rank', label: 'Event Ranking', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's11_summarize', label: 'Compression Policy', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
  { name: 's12_export', label: 'Export & Manifest', status: 'pending', duration_ms: null, metrics: {}, errors: [], warnings: [] },
];

function fmtMs(ms: number | null): string {
  if (ms === null || ms === undefined) return '';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtSec(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function ProcessingPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = (params?.jobId as string) || '';

  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showLogs, setShowLogs] = useState(true);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [copied, setCopied] = useState(false);

  // Real-time timers
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const startTimeRef = useRef<number>(Date.now());
  const logsContainerRef = useRef<HTMLDivElement>(null);

  // Elapsed timer tick
  useEffect(() => {
    startTimeRef.current = Date.now();
    const timer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [jobId]);

  // Polling pipeline state
  useEffect(() => {
    if (!jobId) return;
    let isMounted = true;
    let pollInterval: NodeJS.Timeout | null = null;

    const fetchJob = async () => {
      try {
        const res = await fetch(`${API_BASE}/jobs/${jobId}`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (isMounted) {
          setJob(data);
          setError(null);
          if (data.status === 'completed' && data.total_duration_ms) {
            setElapsedSeconds(Math.round(data.total_duration_ms / 1000));
            if (pollInterval) clearInterval(pollInterval);
          }
        }
      } catch (err) {
        console.warn('Job sync waiting for worker...', err);
      }
    };

    fetchJob();
    pollInterval = setInterval(fetchJob, 1000);

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [jobId]);

  // Auto-scroll logs
  useEffect(() => {
    if (showLogs && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [job?.logs, showLogs]);

  const handleReprocess = async () => {
    if (!jobId || reprocessing) return;
    setReprocessing(true);
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}/reprocess`, { method: 'POST' });
      if (!res.ok) throw new Error('Reprocess request failed');
      startTimeRef.current = Date.now();
      setElapsedSeconds(0);
    } catch (err) {
      console.error(err);
    } finally {
      setReprocessing(false);
    }
  };

  const handleCopyLogs = () => {
    if (!job?.logs?.length) return;
    navigator.clipboard.writeText(job.logs.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isCompleted = job?.status === 'completed';
  const isFailed = job?.status === 'failed';
  const isRunning = job?.status === 'running';

  // True progress from backend
  const progress = isCompleted ? 100 : (job ? job.progress : 0);

  // Stages from backend (fallback to default only during initial mount)
  const stages: StageRecord[] = (job?.stages && job.stages.length > 0)
    ? job.stages
    : DEFAULT_STAGES.map((s, idx) => ({
        ...s,
        status: idx === 0 ? 'running' : 'pending',
      }));

  const completedCount = stages.filter((s) => s.status === 'success').length;
  const currentRunningStage = stages.find((s) => s.status === 'running') || (isCompleted ? null : stages[0]);
  const currentStageName = job?.current_stage || currentRunningStage?.name || 's01_upload';
  const currentStageLabel = job?.current_stage_label || currentRunningStage?.label || (job ? 'Initializing' : 'Connecting to Stream');
  const stageDescription = STAGE_DESCRIPTIONS[currentStageName] || 'Executing multi-stage forensic analysis.';

  // Dynamic ETA Calculation
  let etaText = 'Calculating...';
  if (isCompleted) {
    etaText = 'Complete';
  } else if (!job) {
    etaText = 'Connecting to engine...';
  } else if (progress > 4 && elapsedSeconds > 2) {
    const totalEstSeconds = (elapsedSeconds / progress) * 100;
    const remaining = Math.max(1, Math.round(totalEstSeconds - elapsedSeconds));
    etaText = remaining < 60 ? `~${remaining}s remaining` : `~${Math.ceil(remaining / 60)}m remaining`;
  } else {
    etaText = '~20s - 45s remaining';
  }

  const videoId = job?.video_id || '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1200, margin: '0 auto', width: '100%' }}>
      {/* ── Breadcrumb & Top Header ────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6
          }}>
            <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Dashboard</Link>
            <span>/</span>
            <Link href="/upload" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Ingestion</Link>
            <span>/</span>
            <span style={{ color: 'var(--text-secondary)' }}>Live Telemetry</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1 style={{
              fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
              letterSpacing: '-0.02em', margin: 0
            }}>
              Live 12-Stage Pipeline Tracker
            </h1>
            <span className={`badge ${isCompleted ? 'badge-success' : isFailed ? 'badge-danger' : 'badge-accent'}`} style={{ fontSize: 11 }}>
              {isCompleted ? 'PIPELINE COMPLETE' : isFailed ? 'INTERRUPTED' : 'PROCESSING ACTIVE'}
            </span>
          </div>
          <p style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 4, marginBottom: 0 }}>
            {job?.filename || 'Surveillance Stream'} • Reference: <strong style={{ color: 'var(--text-primary)' }}>{jobId}</strong>
          </p>
        </div>

        {/* Header Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {isCompleted && videoId && (
            <>
              <Link href={`/timeline/${videoId}`} style={{ textDecoration: 'none' }}>
                <button className="btn btn-primary" style={{ fontSize: 12, padding: '8px 18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Play size={13} />
                  <span>Launch Forensic Timeline</span>
                </button>
              </Link>

              <Link href={`/summary/${videoId}`} style={{ textDecoration: 'none' }}>
                <button className="btn btn-secondary" style={{ fontSize: 12, padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <FileText size={13} />
                  <span>View Executive Summary</span>
                </button>
              </Link>
            </>
          )}

          <button
            onClick={() => setShowDiagnostics(!showDiagnostics)}
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Activity size={13} />
            <span>Diagnostics</span>
          </button>
        </div>
      </div>

      {/* ── Completion Hero Announcement Banner ─────────────────────────── */}
      {isCompleted && videoId && (
        <div className="card" style={{
          padding: '20px 24px',
          borderColor: 'var(--accent)',
          backgroundColor: 'rgba(98, 221, 176, 0.08)',
          boxShadow: '0 4px 20px rgba(98, 221, 176, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%',
              backgroundColor: 'var(--accent)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#0F1915', flexShrink: 0
            }}>
              <CheckCircle2 size={24} strokeWidth={2.5} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
                Surveillance Footage Fully Processed & Causally Verified
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                12 stages validated in {fmtSec(elapsedSeconds)} • {job?.event_count || 0} forensic events indexed • ReID complete
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Link href={`/timeline/${videoId}`} style={{ textDecoration: 'none' }}>
              <button className="btn btn-primary" style={{ fontSize: 13, padding: '10px 20px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>Open Forensic Timeline</span>
                <ArrowRight size={14} />
              </button>
            </Link>

            <Link href={`/summary/${videoId}`} style={{ textDecoration: 'none' }}>
              <button className="btn btn-secondary" style={{ fontSize: 13, padding: '10px 18px' }}>
                <span>Executive Dossier</span>
              </button>
            </Link>
          </div>
        </div>
      )}

      {/* ── Real-Time Hero Progress & ETA Card ───────────────────────────── */}
      <div className="card" style={{ padding: '22px 26px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: 8 }}>
              {!isCompleted && (
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--accent)', animation: 'pulse 1.2s infinite' }} />
              )}
              {isCompleted ? 'Pipeline Complete' : 'Active Multi-Stage Execution'}
            </div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginTop: 4 }}>
              {isCompleted
                ? 'All 12 Forensic Stages Validated'
                : `Executing: ${currentStageLabel}`}
            </div>
          </div>

          {/* Time & ETA Badges */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {/* ETA Countdown Badge */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 6,
              backgroundColor: isCompleted ? 'rgba(72, 187, 120, 0.15)' : 'rgba(98, 221, 176, 0.12)',
              border: `1px solid ${isCompleted ? 'var(--success)' : 'var(--accent-dim)'}`,
              color: isCompleted ? 'var(--success)' : 'var(--accent)',
              fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700
            }}>
              <Timer size={14} />
              <span>ETA: {etaText}</span>
            </div>

            {/* Elapsed Time Badge */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 6,
              backgroundColor: 'var(--bg-inset)', border: '1px solid var(--border)',
              fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)'
            }}>
              <Clock size={14} />
              <span>Elapsed: {fmtSec(elapsedSeconds)}</span>
            </div>

            {/* Stage Counter */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 6,
              backgroundColor: 'var(--bg-inset)', border: '1px solid var(--border)',
              fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)'
            }}>
              <Cpu size={14} />
              <span>{completedCount} / 12 Stages</span>
            </div>
          </div>
        </div>

        {/* Dynamic Glowing Progress Bar */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontFamily: 'var(--font-mono)', marginBottom: 6 }}>
            <span style={{ color: 'var(--text-muted)' }}>
              Overall Processing Pipeline
            </span>
            <span style={{ color: 'var(--accent)', fontWeight: 700, fontSize: 14 }}>
              {progress}%
            </span>
          </div>
          <div className="progress-track" style={{ height: 10, borderRadius: 5, overflow: 'hidden' }}>
            <div
              className="progress-fill"
              style={{
                width: `${progress}%`,
                transition: 'width 0.4s ease',
                boxShadow: '0 0 12px var(--accent)',
              }}
            />
          </div>
        </div>

        {/* Active Stage Description Callout */}
        <div className="card-inset" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, borderLeft: '3px solid var(--accent)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {!isCompleted ? (
              <Loader2 size={16} className="spin" style={{ color: 'var(--accent)', flexShrink: 0 }} />
            ) : (
              <CheckCircle2 size={16} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            )}
            <div>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                {isCompleted ? 'Final Summary & Export Ready' : currentStageLabel}
              </span>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>
                {isCompleted ? 'All evidence thumbnails, highlight cuts, and narrative timelines compiled.' : stageDescription}
              </p>
            </div>
          </div>

          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Stage Key: <strong style={{ color: 'var(--accent)' }}>{currentStageName}</strong>
          </div>
        </div>
      </div>

      {/* ── Failure Banner (if failed) ─────────────────────────────────── */}
      {isFailed && (
        <div className="card" style={{
          padding: '16px 20px',
          borderColor: 'rgba(239, 68, 68, 0.4)',
          backgroundColor: 'rgba(239, 68, 68, 0.06)',
          display: 'flex',
          flexDirection: 'column',
          gap: 12
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <AlertCircle size={22} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: 2 }} />
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--danger)' }}>
                  Pipeline Interrupted at {job?.failed_stage || currentStageName}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5, maxWidth: 680 }}>
                  {job?.error || 'A processing stage encountered an error during frame extraction or model inference.'}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button
                onClick={handleReprocess}
                disabled={reprocessing}
                className="btn btn-secondary"
                style={{ fontSize: 12, padding: '7px 16px', display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <RefreshCw size={12} className={reprocessing ? 'spin' : ''} />
                <span>{reprocessing ? 'Restarting...' : 'Retry Pipeline'}</span>
              </button>
              <Link href="/upload" style={{ textDecoration: 'none' }}>
                <button className="btn btn-secondary" style={{ fontSize: 12, padding: '7px 16px' }}>
                  <span>Upload Different Stream</span>
                </button>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* ── 12-Stage Visual Stepper Grid ───────────────────────────────── */}
      <div className="card" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              12-Stage Forensic Execution Matrix
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              Deterministic temporal compression architecture (S01 through S12)
            </div>
          </div>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
            {completedCount} of 12 Validated
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10 }}>
          {stages.map((stage, idx) => {
            const isDone = stage.status === 'success';
            const isRunning = stage.status === 'running';
            const isFailedStage = stage.status === 'failed';

            return (
              <div
                key={stage.name}
                className="card-inset"
                style={{
                  padding: '12px 14px',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  backgroundColor: isRunning ? 'var(--accent-bg)' : isDone ? 'var(--bg-raised)' : undefined,
                  borderColor: isRunning ? 'var(--accent)' : isDone ? 'var(--border)' : 'var(--border-dim)',
                  boxShadow: isRunning ? '0 0 10px rgba(98, 221, 176, 0.15)' : undefined,
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {isDone ? (
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%',
                      backgroundColor: 'rgba(98, 221, 176, 0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: 'var(--accent)', flexShrink: 0
                    }}>
                      <CheckCircle2 size={16} />
                    </div>
                  ) : isRunning ? (
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%',
                      border: '2px solid var(--accent-dim)', borderTopColor: 'var(--accent)',
                      animation: 'spin 0.8s linear infinite', flexShrink: 0
                    }} />
                  ) : isFailedStage ? (
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%',
                      backgroundColor: 'rgba(239, 68, 68, 0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: 'var(--danger)', flexShrink: 0
                    }}>
                      <XCircle size={16} />
                    </div>
                  ) : (
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%',
                      border: '1px solid var(--border)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                      flexShrink: 0
                    }}>
                      {idx + 1}
                    </div>
                  )}

                  <div>
                    <div style={{
                      fontSize: 12, fontWeight: 600,
                      color: isRunning ? 'var(--accent)' : isDone ? 'var(--text-primary)' : 'var(--text-muted)'
                    }}>
                      {stage.label}
                    </div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {stage.name}
                    </div>
                  </div>
                </div>

                {stage.duration_ms !== null && stage.duration_ms !== undefined && (
                  <span style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)',
                    color: isRunning ? 'var(--accent)' : 'var(--text-secondary)',
                    backgroundColor: 'var(--bg-inset)', padding: '2px 6px', borderRadius: 4
                  }}>
                    {fmtMs(stage.duration_ms)}
                  </span>
                )}
                {isRunning && (
                  <span style={{
                    fontSize: 9, fontFamily: 'var(--font-mono)',
                    color: 'var(--accent)', fontWeight: 700,
                    backgroundColor: 'var(--accent-bg)', padding: '2px 6px', borderRadius: 4,
                    border: '1px solid var(--accent-dim)'
                  }}>
                    ACTIVE
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Terminal Execution Log Console ─────────────────────────────── */}
      <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Terminal size={14} style={{ color: 'var(--accent)' }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
              Live Execution Output Console
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              onClick={handleCopyLogs}
              className="btn btn-ghost"
              style={{ fontSize: 11, padding: '3px 8px', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              {copied ? <Check size={12} style={{ color: 'var(--accent)' }} /> : <Copy size={12} />}
              <span>{copied ? 'Copied' : 'Copy Logs'}</span>
            </button>

            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              Auto-scroll enabled
            </span>
          </div>
        </div>

        <div
          ref={logsContainerRef}
          style={{
            backgroundColor: '#070A0B',
            borderRadius: 6,
            border: '1px solid var(--border)',
            padding: 16,
            maxHeight: 280,
            overflowY: 'auto',
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            lineHeight: 1.7,
            color: 'var(--text-secondary)'
          }}
        >
          {(!job?.logs || job.logs.length === 0) ? (
            <div style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Loader2 size={12} className="spin" style={{ color: 'var(--accent)' }} />
              <span>Initializing pipeline worker... Streaming stage execution output...</span>
            </div>
          ) : (
            job.logs.map((log, i) => (
              <div
                key={i}
                style={{
                  color: log.includes('error') || log.includes('ERR') || log.includes('FAILED')
                    ? 'var(--danger)'
                    : log.includes('SUCCESS') || log.includes('Complete') || log.includes('Passed')
                    ? 'var(--accent)'
                    : log.includes('Stage:') || log.includes('Starting')
                    ? '#7BE7BE'
                    : 'var(--text-secondary)'
                }}
              >
                {log}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Diagnostics Drawer */}
      {showDiagnostics && (
        <DiagnosticsPanel jobId={jobId} onClose={() => setShowDiagnostics(false)} />
      )}
    </div>
  );
}
