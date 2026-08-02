'use client';

import {
  BarChart as RechartsBarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts';
import { useEffect, useState } from 'react';
import { Loader2, AlertCircle, BarChart3, Video, Zap, TrendingDown, CheckCircle2 } from 'lucide-react';
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

export default function AnalyticsPage() {
  const [data, setData]       = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (api.analytics() as Promise<AnalyticsData>)
      .then(res => { if (mounted) { setData(res); setLoading(false); } })
      .catch(err => { if (mounted) { setError(err.message); setLoading(false); } });
    return () => { mounted = false; };
  }, []);

  if (loading) return (
    <div className="h-full flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-accent animate-spin" />
    </div>
  );

  if (error) return (
    <div className="h-full flex flex-col items-center justify-center gap-3">
      <AlertCircle className="w-12 h-12 text-red-400" />
      <p className="text-white font-medium">Error loading analytics</p>
      <p className="text-muted text-sm">{error}</p>
    </div>
  );

  if (!data?.has_data) return (
    <div className="h-full flex flex-col items-center justify-center text-center space-y-4">
      <BarChart3 className="w-16 h-16 text-muted opacity-30" />
      <h3 className="text-xl font-semibold text-white">No analytics data yet</h3>
      <p className="text-muted text-sm max-w-sm">
        Process a video to see performance metrics across all 12 pipeline stages.
      </p>
      <Link href="/upload">
        <button className="mt-2 px-6 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-colors text-sm">
          Upload First Video
        </button>
      </Link>
    </div>
  );

  const statCards = [
    { icon: Video,       label: 'Total Videos',     value: data.total_videos,       color: 'text-blue-400',   bg: 'bg-blue-400/10' },
    { icon: Zap,         label: 'Total Events',      value: data.total_events,       color: 'text-purple-400', bg: 'bg-purple-400/10' },
    { icon: TrendingDown,label: 'Avg Compression',   value: data.avg_compression_ratio ? `${data.avg_compression_ratio.toFixed(1)}:1` : '—',
                                                                                      color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { icon: CheckCircle2,label: 'Jobs Completed',    value: data.completed_jobs,     color: 'text-amber-400',  bg: 'bg-amber-400/10' },
  ];

  const stageChartData = data.stage_averages.map(s => ({
    name: s.stage.replace('s0', 'S').replace('s1', 'S').replace('_', ' '),
    ms: s.ms,
  }));

  return (
    <div className="space-y-6 animate-slide-up">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">System Analytics</h1>
        <p className="text-muted mt-1">Performance and compression metrics across all processed jobs.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ icon: Icon, label, value, color, bg }) => (
          <div key={label} className="glass rounded-xl border border-border p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted mb-1">{label}</p>
                <p className="text-2xl font-bold text-white">{String(value)}</p>
              </div>
              <div className={`w-10 h-10 rounded-full ${bg} ${color} flex items-center justify-center`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Secondary stats row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass rounded-xl border border-border p-5">
          <p className="text-sm text-muted mb-1">Data Uploaded</p>
          <p className="text-xl font-semibold text-white">{formatBytes(data.total_bytes_uploaded)}</p>
        </div>
        <div className="glass rounded-xl border border-border p-5">
          <p className="text-sm text-muted mb-1">Jobs Running</p>
          <p className="text-xl font-semibold text-white">{data.running_jobs}</p>
        </div>
        <div className="glass rounded-xl border border-border p-5">
          <p className="text-sm text-muted mb-1">Jobs Failed</p>
          <p className={`text-xl font-semibold ${data.failed_jobs > 0 ? 'text-red-400' : 'text-white'}`}>
            {data.failed_jobs}
          </p>
        </div>
      </div>

      {/* Stage timing bar chart */}
      {stageChartData.length > 0 && (
        <div className="glass rounded-xl border border-border p-6">
          <h2 className="text-lg font-semibold text-white mb-6">Average Stage Duration (ms)</h2>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <RechartsBarChart data={stageChartData} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis
                  dataKey="name"
                  stroke="#71717a"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  interval={0}
                  angle={-30}
                  textAnchor="end"
                  height={50}
                />
                <YAxis stroke="#71717a" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: '#27272a', opacity: 0.5 }}
                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', color: '#fff', borderRadius: 8 }}
                  formatter={(v: number) => [`${v}ms`, 'Avg Duration']}
                />
                <Bar dataKey="ms" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </RechartsBarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
