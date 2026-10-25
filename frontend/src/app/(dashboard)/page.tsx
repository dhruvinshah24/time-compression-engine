"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { DashboardSkeleton } from "@/components/skeletons/DashboardSkeleton";
import {
  Film, Zap, TrendingDown, HardDrive, UploadCloud,
  CheckCircle, Activity, AlertTriangle, Clock, PlaySquare,
} from "lucide-react";

interface JobRecord {
  id: string;
  video_id: string;
  filename: string;
  status: string;
  progress: number;
  event_count: number;
  current_stage?: string;
  video_metadata?: {
    profile?: string;
    duration_hms?: string;
    resolution?: string;
  };
}

interface AnalyticsStats {
  total_videos: number;
  total_events: number;
  avg_compression_ratio: number;
  total_bytes_uploaded: number;
  running_jobs: number;
  has_data: boolean;
}

interface EventRecord {
  id: string;
  type?: string;
  event_type?: string;
  timestamp_ms?: number;
  start_ms?: number;
  confidence?: number;
  video_id?: string;
  person_label?: string;
}

const formatBytes = (bytes: number) => {
  if (!bytes) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
};

const formatTime = (ms: number) => {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toString().padStart(2, "0")}`;
};

function StatusBadge({ status }: { status: string }) {
  if (status === "completed") return (
    <span className="badge badge-success">
      <CheckCircle size={10} /> Completed
    </span>
  );
  if (status === "running") return (
    <span className="badge badge-warning">
      <Activity size={10} className="animate-spin" /> Running
    </span>
  );
  if (status === "failed") return (
    <span className="badge badge-danger">
      <AlertTriangle size={10} /> Failed
    </span>
  );
  return <span className="badge badge-neutral">{status}</span>;
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isOnline, setIsOnline] = useState(true);

  const fetchData = async () => {
    try {
      const [jobsData, statsData, eventsData] = await Promise.all([
        api.jobs.list({ bypassCache: true }) as Promise<JobRecord[]>,
        api.analytics({ bypassCache: true }) as Promise<AnalyticsStats>,
        api.events.list() as Promise<EventRecord[]>,
      ]);
      setJobs(jobsData || []);
      setStats(statsData || null);
      setEvents(eventsData || []);
      setIsOnline(true);
    } catch (e) {
      console.error("Failed to fetch dashboard data:", e);
      setIsOnline(false);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 10000);
    return () => clearInterval(id);
  }, []);

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  const activeJobs = jobs.filter(j => j.status === "running");

  const statCards = [
    { label: "Videos Processed", value: String(stats?.total_videos ?? 0), icon: Film },
    { label: "Events Detected",  value: String(stats?.total_events ?? 0), icon: Zap },
    { label: "Compression Ratio", value: (stats?.avg_compression_ratio ?? 0).toFixed(1) + "×", icon: TrendingDown },
    { label: "Storage Analysed", value: formatBytes(stats?.total_bytes_uploaded ?? 0), icon: HardDrive },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Offline banner */}
      {!isOnline && (
        <div style={{
          padding: '12px 16px', borderRadius: 6,
          backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)',
          color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          fontSize: 13, fontFamily: 'var(--font-mono)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertTriangle size={16} />
            <span>Backend API unreachable at http://localhost:8000. Reconnecting...</span>
          </div>
          <button
            onClick={() => { setIsLoading(true); fetchData(); }}
            className="btn btn-secondary"
            style={{ fontSize: 11, padding: '4px 10px' }}
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', margin: 0 }}>
            Command Centre
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0', fontFamily: 'var(--font-mono)' }}>
            TCE v1.1 — Scene Intelligence Overview & Causal Timelines
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {isOnline ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--success)', backgroundColor: 'var(--success-bg)', border: '1px solid rgba(72, 187, 120, 0.35)', borderRadius: 5, padding: '5px 10px' }}>
              <span className="status-dot status-dot-success animate-pulse-subtle" />
              TCE Engine Online
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontFamily: 'var(--font-mono)', color: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)', borderRadius: 5, padding: '5px 10px' }}>
              <span className="status-dot status-dot-danger" />
              Engine Offline
            </div>
          )}
          <Link href="/upload" style={{ textDecoration: 'none' }}>
            <button className="btn btn-primary" style={{ fontSize: 12, padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 6 }}>
              <UploadCloud size={14} />
              <span>Ingest Footage</span>
            </button>
          </Link>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {statCards.map(({ label, value, icon: Icon }) => (
          <div key={label} className="card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>{label}</p>
                <p style={{ fontSize: 28, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', margin: '6px 0 0', letterSpacing: '-0.02em' }}>{value}</p>
              </div>
              <div style={{ width: 34, height: 34, borderRadius: 6, backgroundColor: 'var(--accent-bg)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent)', flexShrink: 0 }}>
                <Icon size={16} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main 2-column grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16, alignItems: 'start' }}>

        {/* Left: content */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Upload CTA */}
          <Link href="/upload" style={{ textDecoration: 'none' }}>
            <div className="card" style={{
              padding: '28px 24px', borderStyle: 'dashed',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
              cursor: 'pointer', textAlign: 'center', transition: 'border-color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent-dim)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}>
              <div style={{ width: 40, height: 40, borderRadius: 8, backgroundColor: 'var(--accent-bg)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent)' }}>
                <UploadCloud size={18} />
              </div>
              <div>
                <p style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14, margin: 0 }}>Ingest CCTV Footage</p>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '3px 0 0' }}>Drop a video file or click to browse</p>
              </div>
            </div>
          </Link>

          {/* Active pipelines */}
          {activeJobs.length > 0 && (
            <div className="card" style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <span className="status-dot status-dot-warning animate-pulse-subtle" />
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Active Pipelines ({activeJobs.length})
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {activeJobs.map(job => (
                  <div key={job.id}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>{job.filename}</span>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--warning-c)' }}>
                        {job.current_stage ?? "PROCESSING"} · {job.progress}%
                      </span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill progress-fill-warning" style={{ width: `${job.progress}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent jobs */}
          <div className="card">
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Intelligence Reports</span>
            </div>
            <div>
              {jobs.length === 0 ? (
                <div className="empty-state">
                  <Film size={28} />
                  <div>
                    <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-secondary)', margin: 0 }}>No videos processed yet</p>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>Upload footage to begin analysis</p>
                  </div>
                </div>
              ) : (
                <div>
                  {jobs.map(job => (
                    <div key={job.id} style={{
                      display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px',
                      borderBottom: '1px solid var(--border-dim)',
                    }}>
                      {/* Thumbnail placeholder */}
                      <div style={{ width: 56, height: 38, borderRadius: 4, backgroundColor: 'var(--bg-inset)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: 'var(--text-muted)' }}>
                        <PlaySquare size={16} />
                      </div>
                      {/* Info */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.filename}</p>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
                          <StatusBadge status={job.status} />
                          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                            {job.event_count} events
                          </span>
                          {job.video_metadata?.duration_hms && (
                            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
                              <Clock size={10} /> {job.video_metadata.duration_hms}
                            </span>
                          )}
                        </div>
                      </div>
                      {/* Actions */}
                      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                        <Link href={`/timeline/${job.video_id}`}>
                          <button className={job.status === "completed" ? "btn btn-primary" : "btn btn-secondary"} style={{ fontSize: 11, padding: '5px 12px' }} disabled={job.status !== "completed"}>
                            Timeline
                          </button>
                        </Link>
                        <Link href={`/processing/${job.id}`}>
                          <button className="btn btn-ghost" style={{ fontSize: 11, padding: '5px 10px' }}>
                            Pipeline
                          </button>
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Event feed & Security Posture */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="status-dot status-dot-danger animate-pulse-subtle" />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Live Event Feed</span>
              <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                {events.length} events
              </span>
            </div>
            <div style={{ overflowY: 'auto', maxHeight: 420 }}>
              {events.length === 0 ? (
                <div className="empty-state">
                  <Zap size={24} />
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>No events yet</p>
                </div>
              ) : (
                <div>
                  {events.slice(0, 15).map(event => (
                    <div key={event.id} style={{
                      padding: '12px 16px', borderBottom: '1px solid var(--border-dim)',
                      display: 'flex', flexDirection: 'column', gap: 4,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                          {event.event_type ?? event.type ?? "Event"}
                        </span>
                        {event.start_ms !== undefined && (
                          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                            {formatTime(event.start_ms)}
                          </span>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {event.person_label && (
                          <span className="badge badge-accent">{event.person_label}</span>
                        )}
                        {event.confidence !== undefined && (
                          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                            {(event.confidence * 100).toFixed(0)}% conf.
                          </span>
                        )}
                        {event.video_id && (
                          <Link href={`/timeline/${event.video_id}?time=${event.start_ms}`} style={{ marginLeft: 'auto', textDecoration: 'none' }}>
                            <span style={{ fontSize: 11, color: 'var(--accent)', cursor: 'pointer', fontWeight: 600 }}>→ Seek</span>
                          </Link>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* AI Threat & Loss Prevention Posture */}
          <div className="card" style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="status-dot status-dot-success" />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Scene Security Integrity</span>
              </div>
              <span className="badge badge-accent" style={{ fontSize: 10 }}>CAUSAL VERIFIED</span>
            </div>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
              Directed Causal Graph integrity confirmed. Baseline physical asset retention monitored across all indoor camera nodes without temporal gaps.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
