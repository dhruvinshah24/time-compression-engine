'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Video, Zap, TrendingDown, HardDrive, Plus, Clock, CheckCircle2, Play, Loader2, UploadCloud } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api/client';

interface JobRecord {
  id: string;
  video_id: string;
  filename: string;
  status: string;
  progress: number;
  event_count: number;
  video_metadata?: { profile?: string };
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
  confidence?: number;
  video_id?: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function EmptyDashboard() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center space-y-6">
      <div className="w-20 h-20 rounded-2xl bg-accent/10 flex items-center justify-center">
        <UploadCloud className="w-10 h-10 text-accent opacity-60" />
      </div>
      <div>
        <h2 className="text-xl font-semibold text-white mb-2">No videos uploaded yet</h2>
        <p className="text-muted max-w-sm text-sm leading-relaxed">
          Upload your first video to start building a timeline. The TCE pipeline will detect events, track objects, and generate a compressed summary.
        </p>
      </div>
      <Link href="/upload">
        <motion.button
          whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
          className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white px-6 py-3 rounded-lg font-medium transition-colors glow-blue"
        >
          <Plus className="w-5 h-5" /> Upload First Video
        </motion.button>
      </Link>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats]   = useState<AnalyticsStats | null>(null);
  const [jobs, setJobs]     = useState<JobRecord[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, j, e] = await Promise.all([
          api.analytics() as Promise<AnalyticsStats>,
          api.jobs.list()  as Promise<JobRecord[]>,
          api.events.list({ limit: '6' }) as Promise<EventRecord[]>,
        ]);
        setStats(s);
        setJobs(j);
        setEvents(e);
      } catch {
        // Backend unreachable — leave nulls, show empty state
      } finally {
        setLoading(false);
      }
    };
    load();
    // Refresh every 5s while jobs are running
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center py-32 gap-3 text-muted">
      <Loader2 className="w-5 h-5 animate-spin" /> Loading dashboard…
    </div>
  );

  const isEmpty = !stats?.has_data && jobs.length === 0;
  if (isEmpty) return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Welcome</h1>
          <p className="text-muted mt-1">Today is {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>
      </div>
      <EmptyDashboard />
    </div>
  );

  const statCards = [
    { label: 'Total Videos',    value: stats?.total_videos ?? 0,       icon: Video,       color: 'text-blue-400',   bg: 'bg-blue-400/10' },
    { label: 'Events Detected', value: stats?.total_events ?? 0,       icon: Zap,         color: 'text-purple-400', bg: 'bg-purple-400/10' },
    { label: 'Avg Compression', value: stats?.avg_compression_ratio ? `${stats.avg_compression_ratio}:1` : '—',
                                                                        icon: TrendingDown, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { label: 'Data Uploaded',   value: formatBytes(stats?.total_bytes_uploaded ?? 0), icon: HardDrive, color: 'text-amber-400', bg: 'bg-amber-400/10' },
  ];

  const recentJobs = jobs.slice(0, 3);

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Dashboard</h1>
          <p className="text-muted mt-1">Today is {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>
        <Link href="/upload">
          <motion.button
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white px-5 py-2.5 rounded-lg font-medium transition-colors glow-blue"
          >
            <Plus className="w-5 h-5" /> New Upload
          </motion.button>
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, i) => (
          <motion.div
            key={i} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="glass-strong rounded-xl p-6 hover:-translate-y-1 transition-transform duration-300"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted font-medium mb-1">{stat.label}</p>
                <h3 className="text-3xl font-bold text-white">{String(stat.value)}</h3>
              </div>
              <div className={`w-12 h-12 rounded-full ${stat.bg} ${stat.color} flex items-center justify-center`}>
                <stat.icon className="w-6 h-6" />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Recent events feed */}
        <div className="col-span-2 space-y-6">
          <div className="glass rounded-xl border border-border p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-white">Recent Events</h2>
              <Link href="/events" className="text-sm text-accent hover:text-accent-hover">View all</Link>
            </div>
            {events.length === 0 ? (
              <div className="py-10 text-center text-muted text-sm">
                <Zap className="w-8 h-8 mx-auto mb-3 opacity-20" />
                No events detected yet. Events appear here after a video is processed.
              </div>
            ) : (
              <div className="space-y-3">
                {events.map((evt) => (
                  <div key={evt.id} className="flex items-center gap-4 p-4 rounded-lg bg-surface border border-border/50 hover:border-border transition-colors">
                    <div className="text-xs font-mono text-muted">{evt.timestamp_ms != null ? `${(evt.timestamp_ms / 1000).toFixed(1)}s` : '—'}</div>
                    <div className="w-2 h-2 rounded-full bg-accent flex-shrink-0" />
                    <div className="flex-1 font-medium text-white text-sm truncate">{evt.type ?? evt.event_type ?? 'Event'}</div>
                    {evt.confidence != null && (
                      <span className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded flex-shrink-0">
                        {Math.round(evt.confidence * 100)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Processing queue */}
        <div className="col-span-1">
          <div className="glass rounded-xl border border-border p-6 h-full">
            <h2 className="text-xl font-semibold text-white mb-6">Processing Queue</h2>
            {recentJobs.length === 0 ? (
              <div className="py-10 text-center text-muted text-sm">
                <Clock className="w-8 h-8 mx-auto mb-3 opacity-20" />
                No jobs running.
              </div>
            ) : (
              <div className="space-y-5">
                {recentJobs.map((job) => (
                  <Link key={job.id} href={`/processing/${job.id}`} className="block space-y-2 group">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        {job.status === 'completed'
                          ? <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0" />
                          : job.status === 'failed'
                          ? <span className="w-4 h-4 text-red-400 flex-shrink-0 text-xs">✗</span>
                          : <Play className="w-4 h-4 text-muted flex-shrink-0" />}
                        <span className="text-sm font-medium text-white truncate group-hover:text-accent transition-colors">
                          {job.filename}
                        </span>
                      </div>
                      <span className="text-xs font-mono text-muted flex-shrink-0">{job.progress}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-surface rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${job.progress}%` }}
                        transition={{ duration: 0.8 }}
                        className={`h-full rounded-full ${
                          job.status === 'completed' ? 'bg-success' :
                          job.status === 'failed'    ? 'bg-red-400' : 'bg-accent'
                        }`}
                      />
                    </div>
                  </Link>
                ))}
              </div>
            )}

            <Link href="/upload">
              <button className="w-full mt-8 py-2.5 rounded-lg border border-border text-sm text-white hover:bg-white/5 transition-colors">
                + New Upload
              </button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
