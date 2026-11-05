'use client';

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import {
  Activity, Play, CheckCircle2, AlertCircle, Clock, Search,
  ArrowRight, Loader2, RefreshCw, Layers, ShieldCheck
} from 'lucide-react';
import { api } from '@/lib/api/client';

export default function ProcessingIndexPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = () => {
    setLoading(true);
    api.jobs.list({ bypassCache: true })
      .then((data) => {
        setJobs(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to fetch processing jobs');
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(() => {
      api.jobs.list({ bypassCache: true })
        .then((data) => {
          if (Array.isArray(data)) setJobs(data);
        })
        .catch(() => {});
    }, 8000);
    return () => clearInterval(interval);
  }, []);

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      const matchesSearch =
        !search.trim() ||
        job.id?.toLowerCase().includes(search.toLowerCase()) ||
        job.filename?.toLowerCase().includes(search.toLowerCase()) ||
        job.video_id?.toLowerCase().includes(search.toLowerCase());

      const matchesStatus =
        statusFilter === 'all' || job.status?.toLowerCase() === statusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });
  }, [jobs, search, statusFilter]);

  const statusBadge = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={10} />
            Completed
          </span>
        );
      case 'running':
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono font-medium bg-[var(--accent-bg)] text-[var(--accent)] border border-[var(--accent-dim)]">
            <Loader2 size={10} className="animate-spin" />
            In Progress
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <AlertCircle size={10} />
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono font-medium bg-white/5 text-[var(--text-muted)] border border-white/10">
            <Clock size={10} />
            {status || 'Pending'}
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border)] pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-[var(--text-muted)] mb-1">
            <Link href="/" className="hover:text-[var(--accent)] text-[var(--text-muted)] no-underline">Dashboard</Link>
            <span>/</span>
            <span className="text-[var(--text-secondary)]">Pipeline Execution</span>
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight m-0">
            Pipeline Processing Jobs
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-1 max-w-2xl leading-relaxed">
            Real-time telemetry and execution monitors for 12-stage video intelligence jobs.
          </p>
        </div>

        {/* Search & Refresh */}
        <div className="flex items-center gap-2">
          <div className="relative min-w-[200px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
            <input
              type="text"
              id="processing-search-input"
              name="processing-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter jobs or files..."
              className="w-full bg-[var(--bg-inset)] border border-[var(--border)] rounded-md pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] font-mono"
            />
          </div>
          <button
            onClick={fetchJobs}
            title="Refresh jobs"
            className="btn btn-secondary p-2 text-xs flex items-center justify-center"
          >
            <RefreshCw size={14} className={loading ? "animate-spin text-[var(--accent)]" : ""} />
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2">
        {['all', 'completed', 'running', 'failed'].map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`px-3 py-1.5 rounded text-xs font-mono capitalize transition-colors cursor-pointer border ${
              statusFilter === st
                ? 'bg-[var(--accent-bg)] border-[var(--accent)] text-[var(--accent)] font-semibold'
                : 'bg-[var(--bg-panel)] border-[var(--border-dim)] text-[var(--text-secondary)] hover:border-[var(--border)]'
            }`}
          >
            {st} ({st === 'all' ? jobs.length : jobs.filter((j) => j.status?.toLowerCase() === st).length})
          </button>
        ))}
      </div>

      {/* Jobs List */}
      {loading && jobs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-[var(--text-muted)]">
          <Loader2 size={24} className="animate-spin text-[var(--accent)]" />
          <span className="text-xs font-mono">Loading pipeline jobs...</span>
        </div>
      ) : error ? (
        <div className="card p-6 border border-red-500/30 text-center">
          <p className="text-xs text-red-400 font-mono">{error}</p>
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="card p-12 text-center flex flex-col items-center justify-center gap-3">
          <Activity size={32} className="text-[var(--text-muted)] opacity-40" />
          <p className="text-sm font-semibold text-[var(--text-secondary)]">No processing jobs found</p>
          <p className="text-xs text-[var(--text-muted)] max-w-md">
            {search ? 'No jobs match your filter criteria.' : 'No processing jobs currently recorded in the engine.'}
          </p>
          <Link href="/upload" className="btn btn-primary text-xs mt-2 no-underline">
            Submit New Video
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filteredJobs.map((job) => {
            const progress = typeof job.progress === 'number' ? job.progress : (job.status === 'completed' ? 100 : 0);
            const currentStage = job.current_stage_label || job.current_stage || (job.status === 'completed' ? 'S12 Export Completed' : 'Pending');

            return (
              <div
                key={job.id}
                className="card border border-[var(--border)] hover:border-[var(--accent-dim)] p-4 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1.5 flex-wrap">
                    <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
                      {job.id}
                    </span>
                    {statusBadge(job.status)}
                    <span className="text-[11px] font-mono text-[var(--text-muted)]">
                      Video: {job.video_id}
                    </span>
                  </div>

                  <div className="text-xs text-[var(--text-secondary)] font-medium truncate mb-2">
                    {job.filename}
                  </div>

                  {/* Progress bar & stage */}
                  <div className="flex items-center gap-3 max-w-md">
                    <div className="flex-1 bg-[var(--bg-inset)] h-1.5 rounded-full overflow-hidden border border-[var(--border-dim)]">
                      <div
                        className="h-full bg-[var(--accent)] transition-all duration-300"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <span className="font-mono text-[10px] text-[var(--text-muted)] shrink-0">
                      {currentStage} · {progress}%
                    </span>
                  </div>
                </div>

                {/* Action button */}
                <div className="flex items-center gap-2 shrink-0">
                  <Link
                    href={`/processing/${job.id}`}
                    className="btn btn-primary text-xs py-2 px-3 no-underline flex items-center gap-1.5 font-medium"
                  >
                    <span>Pipeline Monitor</span>
                    <ArrowRight size={13} />
                  </Link>
                  {job.status === 'completed' && (
                    <Link
                      href={`/timeline/${job.video_id}`}
                      className="btn btn-secondary text-xs py-2 px-3 no-underline flex items-center gap-1.5"
                      title="Inspect Timeline"
                    >
                      <Clock size={13} />
                      <span className="hidden md:inline">Timeline</span>
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

