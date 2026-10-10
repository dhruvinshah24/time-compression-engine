'use client';

import {
  BarChart as RechartsBarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts';
import { useEffect, useState } from 'react';
import {
  Loader2, AlertCircle, BarChart3, Video, Zap,
  TrendingUp, CheckCircle2, Cpu, HardDrive, Play, ArrowUpRight
} from 'lucide-react';
import { api } from '@/lib/api/client';
import Link from 'next/link';

interface AnalyticsData {
  total_videos:          number;
  total_jobs:            number;
  completed_jobs:        number;
  failed_jobs:           number;
  running_jobs:          number;
  total_events:          number;
  avg_compression_ratio: number;
  total_bytes_uploaded:  number;
  stage_averages:        { stage: string; ms: number }[];
  has_data:              boolean;
}

function formatBytes(bytes: number): string {
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
    <div className="backdrop-blur-xl bg-[#090b10]/95 border border-white/10 rounded-xl p-3 shadow-2xl min-w-[140px]">
      <p className="text-white/60 text-xs font-mono mb-1">{label}</p>
      <p className="text-white font-bold text-sm font-mono flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-indigo-400" />
        {payload[0].value.toLocaleString()} {unit}
      </p>
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData]         = useState<AnalyticsData | null>(null);
  const [jobsData, setJobsData] = useState<{ filename: string; event_count: number }[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      api.analytics() as Promise<AnalyticsData>,
      api.jobs.list().catch(() => []) as Promise<any[]>
    ])
      .then(([res, jobs]) => {
        if (mounted) {
          setData(res);
          setJobsData(jobs.filter(j => j.status === 'completed').map(j => ({
            filename: j.filename.replace('original.mp4', 'Stream').replace('archive_', 'Vid-'),
            event_count: j.event_count
          })));
          setLoading(false);
        }
      })
      .catch(err => { if (mounted) { setError(err.message); setLoading(false); } });
    return () => { mounted = false; };
  }, []);

  if (loading) return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
        <p className="text-white/40 text-xs font-mono uppercase tracking-widest animate-pulse">Aggregating system telemetry…</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center p-8 max-w-md surface-card rounded-3xl border border-red-500/20">
        <AlertCircle className="w-12 h-12 text-red-400" />
        <h2 className="text-lg font-bold text-white">Analytics Unavailable</h2>
        <p className="text-white/50 text-xs">{error}</p>
      </div>
    </div>
  );

  if (!data?.has_data) return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-8">
      <div className="surface-card p-12 rounded-3xl border max-w-md flex flex-col items-center gap-4">
        <div className="w-16 h-16 rounded-2xl surface-inset flex items-center justify-center text-white/30">
          <BarChart3 size={32} />
        </div>
        <h3 className="text-lg font-semibold text-white">Zero Analytics Records</h3>
        <p className="text-white/40 text-xs leading-relaxed">
          Process video footage through the 12-stage engine to populate duration benchmarks and event retention metrics.
        </p>
        <Link href="/upload">
          <button className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-xl font-medium text-xs shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all">
            Upload Video Stream
          </button>
        </Link>
      </div>
    </div>
  );

  const statCards = [
    {
      icon: Video,
      label: 'Ingested Streams',
      value: data.total_videos,
      color: 'text-blue-400',
      glow: 'shadow-[0_0_15px_rgba(59,130,246,0.2)]',
      sub: 'Verified video archives'
    },
    {
      icon: Zap,
      label: 'Synthesized Events',
      value: data.total_events,
      color: 'text-violet-400',
      glow: 'shadow-[0_0_15px_rgba(168,85,247,0.2)]',
      sub: 'Cross-stage detections'
    },
    {
      icon: TrendingUp,
      label: 'Footage Retained',
      value: data.avg_compression_ratio ? `${(data.avg_compression_ratio * 100).toFixed(0)}%` : '—',
      color: 'text-emerald-400',
      glow: 'shadow-[0_0_15px_rgba(16,185,129,0.2)]',
      sub: 'Synthesized condensed cut'
    },
    {
      icon: CheckCircle2,
      label: 'Completed Pipelines',
      value: data.completed_jobs,
      color: 'text-amber-400',
      glow: 'shadow-[0_0_15px_rgba(245,158,11,0.2)]',
      sub: 'Zero pipeline drops'
    },
  ];

  const stageChartData = data.stage_averages.map(s => ({
    name: s.stage.replace('s0', 'S').replace('s1', 'S').replace(/_/g, ' '),
    ms: s.ms,
  }));

  return (
    <div className="space-y-7 animate-slide-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/5">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">System Performance Analytics</h1>
          <p className="text-white/40 text-xs mt-1 font-mono">
            Pipeline telemetry across RTX 5050 GPU tensor hardware
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full w-fit">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Telemetric Collector Active
        </div>
      </div>

      {/* Primary 4 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ icon: Icon, label, value, color, glow, sub }) => (
          <div key={label} className="surface-card p-5 rounded-2xl border relative overflow-hidden">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-white/40 font-medium mb-1">{label}</p>
                <p className="text-3xl font-mono font-bold text-white tracking-tight">{String(value)}</p>
                <p className="text-[10px] text-white/30 font-mono mt-1.5">{sub}</p>
              </div>
              <div className={`w-11 h-11 rounded-xl bg-black/40 border border-white/10 ${color} ${glow} flex items-center justify-center flex-shrink-0`}>
                <Icon size={20} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Secondary Telemetry Strip */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="surface-card p-4 rounded-xl border flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl surface-inset flex items-center justify-center text-cyan-400 flex-shrink-0">
            <HardDrive size={18} />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider text-white/40">Raw Data Ingested</p>
            <p className="text-lg font-mono font-semibold text-white mt-0.5">{formatBytes(data.total_bytes_uploaded)}</p>
          </div>
        </div>

        <div className="surface-card p-4 rounded-xl border flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl surface-inset flex items-center justify-center text-indigo-400 flex-shrink-0">
            <Cpu size={18} />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider text-white/40">Active Worker Threads</p>
            <p className="text-lg font-mono font-semibold text-white mt-0.5">{data.running_jobs} running</p>
          </div>
        </div>

        <div className="surface-card p-4 rounded-xl border flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl surface-inset flex items-center justify-center text-rose-400 flex-shrink-0">
            <AlertCircle size={18} />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider text-white/40">Pipeline Failures</p>
            <p className={`text-lg font-mono font-semibold mt-0.5 ${data.failed_jobs > 0 ? 'text-rose-400' : 'text-white'}`}>
              {data.failed_jobs} aborts
            </p>
          </div>
        </div>
      </div>

      {/* Stage Execution Duration Chart */}
      {stageChartData.length > 0 && (
        <div className="surface-card rounded-2xl border p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider font-mono">
                Stage Execution Latency Profile
              </h2>
              <p className="text-xs text-white/40 mt-0.5 font-mono">Average wall-clock milliseconds per pipeline stage</p>
            </div>
            <span className="text-[10px] font-mono text-indigo-400 px-2.5 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20">
              12 Stages Profiled
            </span>
          </div>

          <div className="h-[300px] w-full surface-inset p-3 rounded-xl">
            <ResponsiveContainer width="100%" height="100%">
              <RechartsBarChart data={stageChartData} margin={{ left: -15, right: 10, top: 10, bottom: 25 }}>
                <defs>
                  <linearGradient id="latencyBarGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#818cf8" stopOpacity={0.9} />
                    <stop offset="100%" stopColor="#4f46e5" stopOpacity={0.3} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis
                  dataKey="name"
                  stroke="rgba(255,255,255,0.4)"
                  fontSize={10}
                  fontFamily="monospace"
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                  height={45}
                />
                <YAxis
                  stroke="rgba(255,255,255,0.4)"
                  fontSize={10}
                  fontFamily="monospace"
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                  content={<ChartCustomTooltip unit="ms" />}
                />
                <Bar
                  dataKey="ms"
                  fill="url(#latencyBarGradient)"
                  radius={[5, 5, 0, 0]}
                />
              </RechartsBarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Events per Video Ingest */}
      {jobsData.length > 0 && (
        <div className="surface-card rounded-2xl border p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider font-mono">
                Event Density by Video Ingest
              </h2>
              <p className="text-xs text-white/40 mt-0.5 font-mono">Synthesized timeline events discovered per processed stream</p>
            </div>
          </div>

          <div className="h-[280px] w-full surface-inset p-3 rounded-xl">
            <ResponsiveContainer width="100%" height="100%">
              <RechartsBarChart data={jobsData} margin={{ left: -15, right: 10, top: 10, bottom: 25 }}>
                <defs>
                  <linearGradient id="eventDensityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#c084fc" stopOpacity={0.9} />
                    <stop offset="100%" stopColor="#9333ea" stopOpacity={0.3} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis
                  dataKey="filename"
                  stroke="rgba(255,255,255,0.4)"
                  fontSize={10}
                  fontFamily="monospace"
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                  interval={0}
                  angle={-20}
                  textAnchor="end"
                  height={45}
                />
                <YAxis
                  stroke="rgba(255,255,255,0.4)"
                  fontSize={10}
                  fontFamily="monospace"
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                  content={<ChartCustomTooltip unit="events" />}
                />
                <Bar
                  dataKey="event_count"
                  fill="url(#eventDensityGradient)"
                  radius={[5, 5, 0, 0]}
                />
              </RechartsBarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
