"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import {
  Film,
  Zap,
  TrendingDown,
  HardDrive,
  UploadCloud,
  CheckCircle,
  Activity,
  AlertTriangle,
  Clock,
  PlaySquare,
  Server,
  ActivitySquare,
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

const formatBytes = (bytes: number, decimals = 2) => {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
};

const formatTime = (ms: number) => {
  const seconds = Math.floor(ms / 1000);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
};

export default function DashboardPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [jobsData, statsData, eventsData] = await Promise.all([
        api.jobs.list() as Promise<JobRecord[]>,
        api.analytics() as Promise<AnalyticsStats>,
        api.events.list() as Promise<EventRecord[]>,
      ]);
      setJobs(jobsData || []);
      setStats(statsData || null);
      setEvents(eventsData || []);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const intervalId = setInterval(fetchData, 30000);
    return () => clearInterval(intervalId);
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#07090e]">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-10 w-10 animate-pulse text-[#00d4ff]" />
          <p className="font-mono text-sm tracking-wider text-cyan-400">
            INITIALIZING COMMAND CENTER...
          </p>
        </div>
      </div>
    );
  }

  const activeJobs = jobs.filter((j) => j.status === "running");

  return (
    <div className="min-h-screen bg-[#07090e] p-6 font-sans text-slate-300">
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes subtle-gradient {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        .animate-gradient {
          background-size: 200% 200%;
          animation: subtle-gradient 10s ease infinite;
        }
      `}} />

      {/* HERO BANNER */}
      <section className="animate-gradient relative mb-8 overflow-hidden rounded-xl border border-white/5 bg-gradient-to-r from-cyan-900/20 via-blue-900/20 to-emerald-900/20 p-8 shadow-2xl backdrop-blur-xl">
        <div className="absolute left-0 top-0 h-full w-full bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-white/5 via-transparent to-transparent opacity-30"></div>
        <div className="relative flex flex-col items-start justify-between gap-6 lg:flex-row lg:items-center">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-cyan-500/20 ring-1 ring-cyan-500/50">
              <ActivitySquare className="h-6 w-6 text-cyan-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                SCENE INTELLIGENCE COMMAND
              </h1>
              <p className="font-mono text-sm text-cyan-400">
                TCE // TIME COMPRESSION ENGINE
              </p>
            </div>
          </div>

          <div className="flex flex-1 justify-center gap-8 px-8">
            <div className="text-center">
              <div className="font-mono text-3xl font-bold text-white">
                {stats?.total_videos || 0}
              </div>
              <div className="text-xs tracking-widest text-slate-400">
                TOTAL VIDEOS
              </div>
            </div>
            <div className="h-10 w-px bg-white/10" />
            <div className="text-center">
              <div className="font-mono text-3xl font-bold text-white">
                {stats?.total_events || 0}
              </div>
              <div className="text-xs tracking-widest text-slate-400">
                TOTAL EVENTS
              </div>
            </div>
            <div className="h-10 w-px bg-white/10" />
            <div className="text-center">
              <div className="font-mono text-3xl font-bold text-white">
                {activeJobs.length}
              </div>
              <div className="text-xs tracking-widest text-slate-400">
                ACTIVE JOBS
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-2">
            <span className="relative flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500"></span>
            </span>
            <span className="font-mono text-sm font-medium text-emerald-400">
              SYSTEM ONLINE
            </span>
          </div>
        </div>
        <div className="absolute bottom-0 left-0 h-[2px] w-full bg-gradient-to-r from-cyan-500/0 via-cyan-500 to-cyan-500/0"></div>
      </section>

      {/* ANALYTICS STRIP */}
      <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: "Total Videos Processed",
            value: stats?.total_videos || 0,
            icon: Film,
            color: "text-blue-400",
            bg: "bg-blue-400/10",
            border: "border-blue-400/20",
          },
          {
            label: "Total Events Detected",
            value: stats?.total_events || 0,
            icon: Zap,
            color: "text-cyan-400",
            bg: "bg-cyan-400/10",
            border: "border-cyan-400/20",
          },
          {
            label: "Avg Compression Ratio",
            value: (stats?.avg_compression_ratio || 0).toFixed(1) + "x",
            icon: TrendingDown,
            color: "text-emerald-400",
            bg: "bg-emerald-400/10",
            border: "border-emerald-400/20",
          },
          {
            label: "Storage Analyzed",
            value: formatBytes(stats?.total_bytes_uploaded || 0),
            icon: HardDrive,
            color: "text-amber-400",
            bg: "bg-amber-400/10",
            border: "border-amber-400/20",
          },
        ].map((stat, i) => (
          <div
            key={i}
            className={`relative overflow-hidden rounded-xl border border-white/5 bg-[rgba(13,18,24,0.8)] p-6 backdrop-blur-xl transition-colors hover:bg-white/[0.03]`}
          >
            <div className="relative z-10 flex items-start justify-between">
              <div>
                <div className="font-mono text-3xl font-bold text-white">
                  {stat.value}
                </div>
                <div className="mt-1 text-sm font-medium text-slate-400">
                  {stat.label}
                </div>
              </div>
              <div
                className={`rounded-lg ${stat.bg} ${stat.border} border p-3`}
              >
                <stat.icon className={`h-6 w-6 ${stat.color}`} />
              </div>
            </div>
            {/* Subtle background icon */}
            <stat.icon
              className={`absolute -right-4 -top-4 z-0 h-24 w-24 opacity-5 ${stat.color}`}
            />
          </div>
        ))}
      </section>

      {/* MAIN GRID */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* LEFT COLUMN: 60% */}
        <div className="flex flex-col gap-8 lg:col-span-7 xl:col-span-8">
          
          {/* QUICK UPLOAD */}
          <Link href="/upload">
            <div className="group relative cursor-pointer overflow-hidden rounded-xl border border-dashed border-white/20 bg-white/5 p-8 text-center transition-all hover:border-cyan-500/50 hover:bg-cyan-500/5">
              <div className="flex flex-col items-center justify-center space-y-4">
                <div className="rounded-full bg-cyan-500/10 p-4 transition-transform group-hover:scale-110">
                  <UploadCloud className="h-8 w-8 text-cyan-400" />
                </div>
                <div>
                  <h3 className="text-lg font-medium text-white">
                    Drop CCTV footage to analyze
                  </h3>
                  <p className="mt-1 text-sm text-slate-400">
                    Or click to browse files
                  </p>
                </div>
              </div>
              {/* Animated corner reticles */}
              <div className="absolute left-0 top-0 h-4 w-4 border-l-2 border-t-2 border-cyan-400/0 transition-all group-hover:border-cyan-400/60" />
              <div className="absolute right-0 top-0 h-4 w-4 border-r-2 border-t-2 border-cyan-400/0 transition-all group-hover:border-cyan-400/60" />
              <div className="absolute bottom-0 left-0 h-4 w-4 border-b-2 border-l-2 border-cyan-400/0 transition-all group-hover:border-cyan-400/60" />
              <div className="absolute bottom-0 right-0 h-4 w-4 border-b-2 border-r-2 border-cyan-400/0 transition-all group-hover:border-cyan-400/60" />
            </div>
          </Link>

          {/* ACTIVE PIPELINES */}
          {activeJobs.length > 0 && (
            <div className="rounded-xl border border-amber-500/20 bg-[rgba(13,18,24,0.8)] p-6 backdrop-blur-xl">
              <div className="mb-4 flex items-center gap-3">
                <div className="relative flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex h-3 w-3 rounded-full bg-amber-500"></span>
                </div>
                <h2 className="text-lg font-semibold tracking-wide text-white">
                  ACTIVE PIPELINES
                </h2>
              </div>
              <div className="space-y-4">
                {activeJobs.map((job) => (
                  <div key={job.id} className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium text-slate-300">
                        {job.filename}
                      </span>
                      <span className="font-mono text-amber-400">
                        {job.current_stage || "PROCESSING"} {job.progress}%
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="h-full bg-amber-500 transition-all duration-500 ease-in-out"
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* RECENT INTELLIGENCE REPORTS */}
          <div className="rounded-xl border border-white/5 bg-[rgba(13,18,24,0.8)] backdrop-blur-xl">
            <div className="border-b border-white/5 p-6">
              <h2 className="text-lg font-semibold tracking-wide text-white">
                RECENT INTELLIGENCE REPORTS
              </h2>
            </div>
            <div className="divide-y divide-white/5 p-2">
              {jobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 text-center">
                  <Film className="mb-4 h-12 w-12 text-slate-600" />
                  <p className="text-lg font-medium text-slate-300">
                    No videos processed yet.
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    Upload your first CCTV footage to begin.
                  </p>
                </div>
              ) : (
                jobs.map((job) => (
                  <div
                    key={job.id}
                    className="flex flex-col gap-4 p-4 transition-colors hover:bg-white/[0.02] sm:flex-row sm:items-center"
                  >
                    <div className="flex h-16 w-24 shrink-0 items-center justify-center rounded border border-white/10 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgZmlsbD0iIzIyMiIgLz4KPHJlY3QgeD0iMCIgeT0iMCIgd2lkdGg9IjUiIGhlaWdodD0iMTAiIGZpbGw9IiMzMzMiIC8+CjxyZWN0IHg9IjM1IiB5PSIwIiB3aWR0aD0iNSIgaGVpZ2h0PSIxMCIgZmlsbD0iIzMzMyIgLz4KPC9zdmc+')] bg-repeat-y text-slate-500">
                      <PlaySquare className="h-6 w-6" />
                    </div>
                    
                    <div className="flex-1 space-y-1">
                      <h4 className="font-medium text-white line-clamp-1">
                        {job.filename}
                      </h4>
                      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                        {job.status === "completed" && (
                          <span className="flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 font-medium text-emerald-400">
                            <CheckCircle className="h-3 w-3" />
                            COMPLETED
                          </span>
                        )}
                        {job.status === "running" && (
                          <span className="flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 font-medium text-amber-400">
                            <Activity className="h-3 w-3 animate-spin" />
                            RUNNING
                          </span>
                        )}
                        {job.status === "failed" && (
                          <span className="flex items-center gap-1 rounded bg-rose-500/10 px-2 py-0.5 font-medium text-rose-400">
                            <AlertTriangle className="h-3 w-3" />
                            FAILED
                          </span>
                        )}
                        
                        <span className="flex items-center gap-1">
                          <Zap className="h-3 w-3 text-cyan-500" />
                          {job.event_count} Events
                        </span>
                        
                        {job.video_metadata?.duration_hms && (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {job.video_metadata.duration_hms}
                          </span>
                        )}
                        {job.video_metadata?.profile && (
                          <span className="rounded bg-white/10 px-1.5 py-0.5 uppercase">
                            {job.video_metadata.profile}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex shrink-0 gap-2">
                      <Link href={`/timeline/${job.video_id}`}>
                        <button
                          disabled={job.status !== "completed"}
                          className="rounded border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-400 transition-colors hover:bg-cyan-500/20 disabled:opacity-50"
                        >
                          View Timeline
                        </button>
                      </Link>
                      <Link href={`/processing/${job.id}`}>
                        <button className="rounded border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10">
                          Inspect Pipeline
                        </button>
                      </Link>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>

        {/* RIGHT COLUMN: 40% */}
        <div className="flex flex-col gap-8 lg:col-span-5 xl:col-span-4">
          
          {/* LIVE EVENT FEED */}
          <div className="flex h-full flex-col rounded-xl border border-white/5 bg-[rgba(13,18,24,0.8)] backdrop-blur-xl">
            <div className="flex items-center justify-between border-b border-white/5 p-6">
              <h2 className="flex items-center gap-3 text-lg font-semibold tracking-wide text-white">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-rose-500"></span>
                </span>
                LIVE INTELLIGENCE FEED
              </h2>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4">
              {events.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center p-8 text-center">
                  <Zap className="mb-4 h-10 w-10 text-slate-600" />
                  <p className="text-sm text-slate-500">
                    No recent events detected.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {events.slice(0, 10).map((event) => (
                    <div
                      key={event.id}
                      className="group relative flex gap-4 rounded-lg border border-transparent p-3 transition-colors hover:border-white/5 hover:bg-white/[0.02]"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-slate-800">
                        <Zap className="h-5 w-5 text-cyan-400" />
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-start justify-between">
                          <p className="font-medium text-slate-200">
                            {event.event_type || event.type || "Unknown Event"}
                          </p>
                          <span className="font-mono text-xs text-slate-500">
                            {event.start_ms !== undefined
                              ? formatTime(event.start_ms)
                              : ""}
                          </span>
                        </div>
                        {event.person_label && (
                          <span className="inline-block rounded bg-indigo-500/20 px-2 py-0.5 text-xs text-indigo-300">
                            {event.person_label}
                          </span>
                        )}
                        <div className="flex justify-between pt-1">
                          {event.video_id && (
                            <Link
                              href={`/timeline/${event.video_id}?time=${event.start_ms}`}
                              className="text-xs text-cyan-500 opacity-0 transition-opacity hover:underline group-hover:opacity-100"
                            >
                              Jump to Event &rarr;
                            </Link>
                          )}
                          {event.confidence !== undefined && (
                            <span className="font-mono text-xs text-slate-500">
                              {(event.confidence * 100).toFixed(0)}% CONF
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}

