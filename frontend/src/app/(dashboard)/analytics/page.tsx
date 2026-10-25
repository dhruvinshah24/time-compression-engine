'use client';

import {
  BarChart as RechartsBarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import { useEffect, useState } from 'react';
import {
  Loader2, AlertCircle, BarChart3, Video, Zap,
  TrendingUp, CheckCircle2, Cpu, HardDrive, Play, ArrowUpRight,
  Clock, Activity, Layers, ArrowRight, ShieldCheck
} from 'lucide-react';
import { api } from '@/lib/api/client';
import Link from 'next/link';
import { AnalyticsSkeleton } from '@/components/skeletons/AnalyticsSkeleton';

interface AnalyticsData {
  total_videos: number;
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  running_jobs: number;
  total_events: number;
  avg_compression_ratio: number;
  total_bytes_uploaded: number;
  stage_averages: { stage: string; ms: number }[];
  has_data: boolean;
}

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; name: string }>;
  label?: string;
  unit?: string;
}

function ChartCustomTooltip({ active, payload, label, unit = 'ms' }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      backgroundColor: 'var(--bg-raised)',
      border: '1px solid var(--border)',
      borderRadius: 6,
      padding: '8px 12px',
      fontSize: 12,
      fontFamily: 'var(--font-mono)',
      boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
    }}>
      <p style={{ color: 'var(--text-muted)', marginBottom: 4, margin: 0 }}>{label}</p>
      <p style={{
        color: 'var(--text-primary)', fontWeight: 600, margin: 0,
        display: 'flex', alignItems: 'center', gap: 6
      }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
        <span>{payload[0].value.toLocaleString()} {unit}</span>
      </p>
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [jobsData, setJobsData] = useState<{ id: string; video_id: string; filename: string; event_count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      api.analytics() as Promise<AnalyticsData>,
      api.jobs.list().catch(() => []) as Promise<any[]>
    ])
      .then(([res, jobs]) => {
        if (mounted) {
          setData(res);
          setJobsData(
            (jobs || [])
              .filter((j: any) => j.status === 'completed')
              .map((j: any) => ({
                id: j.id,
                video_id: j.video_id,
                filename: (j.filename || 'Stream').replace('archive_', 'Vid-').slice(0, 14),
                event_count: j.event_count || 0
              }))
          );
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
  }, []);

  if (loading) {
    return <AnalyticsSkeleton />;
  }

  if (error) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div className="card" style={{ maxWidth: 440, margin: '0 auto', padding: 24 }}>
          <AlertCircle size={28} style={{ color: 'var(--danger)', margin: '0 auto 10px' }} />
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>Analytics Unavailable</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>{error}</p>
        </div>
      </div>
    );
  }

  const rawRatio = data?.avg_compression_ratio ? data.avg_compression_ratio : 1.0;
  const timeSavedPct = rawRatio >= 1
    ? Math.round((1 - 1 / rawRatio) * 100)
    : Math.round((1 - rawRatio) * 100);
  const timeSavedDisplay = `${Math.max(0, Math.min(99, timeSavedPct))}%`;
  const condensedPct = Math.max(1, 100 - timeSavedPct);
  const condensedMinutes = Math.round(60 * (condensedPct / 100));
  const condensedTimeStr = `00:${String(condensedMinutes).padStart(2, '0')}:00`;

  const statItems = [
    { label: 'Total Streams Ingested', value: data?.total_videos || 0, icon: Video, sub: 'Surveillance archives' },
    { label: 'Events Synthesized', value: data?.total_events || 0, icon: Zap, sub: 'Causal detections' },
    { label: 'Avg Compression Yield', value: timeSavedDisplay, icon: TrendingUp, sub: 'Footage time condensed' },
    { label: 'Raw Telemetry Ingested', value: formatBytes(data?.total_bytes_uploaded || 0), icon: HardDrive, sub: 'Analyzed stream volume' },
  ];

  const stageData = (data?.stage_averages || []).map((s) => ({
    name: s.stage.replace('s', 'S').replace(/_/g, ' '),
    ms: s.ms,
  }));

  const totalPipelineMs = stageData.reduce((acc, curr) => acc + curr.ms, 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6
          }}>
            <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Dashboard</Link>
            <span>/</span>
            <span style={{ color: 'var(--text-secondary)' }}>System Telemetry</span>
          </div>

          <h1 style={{
            fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
            letterSpacing: '-0.02em', margin: 0
          }}>
            System Performance & Pipeline Telemetry
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2, marginBottom: 0 }}>
            Operational metrics, stage-by-stage execution latency, and temporal compression yield across surveillance feeds.
          </p>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
          backgroundColor: 'var(--bg-raised)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '6px 12px'
        }}>
          <Activity size={12} style={{ color: 'var(--accent)' }} />
          <span>Real-time Telemetry Active</span>
        </div>
      </div>

      {/* ── Asymmetric Top Metrics Strip (Reference A inspired) ─────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12
      }}>
        {statItems.map((st, i) => (
          <div key={i} className="card" style={{ padding: '16px 18px', position: 'relative', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {st.label}
              </span>
              <st.icon size={15} style={{ color: 'var(--text-secondary)' }} />
            </div>
            <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
              {st.value}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              {st.sub}
            </div>
          </div>
        ))}
      </div>

      {/* ── Main Analytical Panels (Asymmetric Composition) ──────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        {/* Hero Chart: 12-Stage Execution Latency */}
        <div className="card" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                12-Stage Pipeline Latency Distribution
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                Average execution time per stage • Total average run: {(totalPipelineMs / 1000).toFixed(2)}s
              </div>
            </div>
            <span className="badge badge-accent" style={{ fontSize: 11 }}>
              S01 Ingest → S12 Export
            </span>
          </div>

          <div style={{ width: '100%', height: 280 }}>
            {stageData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <RechartsBarChart data={stageData} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                  <CartesianGrid stroke="var(--border-dim)" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                    angle={-30}
                    textAnchor="end"
                    interval={0}
                    stroke="var(--border-dim)"
                  />
                  <YAxis
                    tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                    stroke="var(--border-dim)"
                  />
                  <Tooltip content={<ChartCustomTooltip unit="ms" />} />
                  <Bar dataKey="ms" radius={[4, 4, 0, 0]}>
                    {stageData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.name.includes('04') || entry.name.includes('05') ? 'var(--accent)' : 'var(--border)'}
                      />
                    ))}
                  </Bar>
                </RechartsBarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                Awaiting pipeline execution to calibrate stage latencies.
              </div>
            )}
          </div>

          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            paddingTop: 10, borderTop: '1px solid var(--border-dim)'
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: 'var(--accent)' }} />
              Dominant bottlenecks: S04 Object Detection & S05 Multi-Object ReID
            </span>
            <span>CPU Inference Standard</span>
          </div>
        </div>

        {/* Side Panel: Temporal Efficiency & Compression Breakdown */}
        <div className="card" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
            Investigation Time Saved
          </div>

          <div className="card-inset" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Raw Footages</span>
              <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>01:00:00 (100%)</span>
            </div>
            <div className="progress-track" style={{ height: 6 }}>
              <div style={{ width: '100%', height: '100%', backgroundColor: 'var(--border)' }} />
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 4 }}>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>Condensed Timeline</span>
              <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent)' }}>{condensedTimeStr} ({condensedPct}%)</span>
            </div>
            <div className="progress-track" style={{ height: 6 }}>
              <div className="progress-fill" style={{ width: `${condensedPct}%` }} />
            </div>

            <div style={{
              fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5,
              marginTop: 6, paddingTop: 10, borderTop: '1px solid var(--border-dim)'
            }}>
              <strong>{timeSavedDisplay} of inactive surveillance footage pruned</strong> while preserving all causal actor interactions and spatial events.
            </div>
          </div>

          {/* Quick Stream Jump List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 'auto' }}>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Completed Video Streams
            </span>
            {jobsData.slice(0, 3).map((jb) => (
              <Link
                key={jb.id}
                href={`/timeline/${jb.video_id}`}
                style={{ textDecoration: 'none' }}
              >
                <div
                  className="card-inset"
                  style={{
                    padding: '8px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    cursor: 'pointer', transition: 'all 0.15s ease'
                  }}
                >
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{jb.filename}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{jb.event_count} events synthesized</div>
                  </div>
                  <ArrowRight size={13} style={{ color: 'var(--accent)' }} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* ── Bottom Section: Stream Event Yield ───────────────────────────── */}
      <div className="card" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              Stream Forensic Event Yield
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              Synthesized causal forensic events extracted per camera recording
            </div>
          </div>
          <span className="badge badge-neutral" style={{ fontSize: 11 }}>
            Indexed Archives
          </span>
        </div>

        <div style={{ width: '100%', height: 220 }}>
          {jobsData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <RechartsBarChart data={jobsData} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
                <CartesianGrid stroke="var(--border-dim)" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="filename"
                  tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                  stroke="var(--border-dim)"
                />
                <YAxis
                  tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                  stroke="var(--border-dim)"
                />
                <Tooltip content={<ChartCustomTooltip unit="events" />} />
                <Bar dataKey="event_count" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              </RechartsBarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{
              height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-muted)', fontSize: 12
            }}>
              Awaiting multiple stream completions to populate comparison.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
