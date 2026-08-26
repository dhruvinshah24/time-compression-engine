'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Video, Zap, HardDrive, Plus, Clock, CheckCircle2,
  XCircle, Loader2, UploadCloud, Activity, Eye, ArrowRight,
  Sparkles, Play, ChevronRight, Brain, Cpu, Circle,
  Lightbulb, User, Smartphone, Laptop, Coffee, Package,
  BarChart3, Film, TrendingUp, Layers,
  AlertTriangle, Users, Car, DoorOpen, Shield,
  Backpack, PersonStanding, Luggage, MonitorPlay, BookOpen,
} from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api/client';

// ── Types ─────────────────────────────────────────────────────────────────────
interface JobRecord {
  id: string;
  video_id: string;
  filename: string;
  status: string;
  progress: number;
  event_count: number;
  current_stage?: string;
  video_metadata?: { profile?: string; duration_hms?: string; resolution?: string };
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
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function getEventLabel(et: string): { label: string; icon: React.ElementType; color: string } {
  const map: Record<string, { label: string; icon: React.ElementType; color: string }> = {
    // Person motion
    person_entered_scene:       { label: 'Person Entered',       icon: User,           color: 'text-green-400' },
    person_left_scene:          { label: 'Person Left',           icon: User,           color: 'text-red-400' },
    person_walking:             { label: 'Walking',               icon: Activity,       color: 'text-blue-400' },
    person_running:             { label: 'Running',               icon: Activity,       color: 'text-rose-400' },
    person_loitering:           { label: 'Loitering',             icon: Clock,          color: 'text-amber-500' },
    // Person posture
    person_sitting:             { label: 'Sat Down',              icon: Activity,       color: 'text-amber-400' },
    person_standing_up:         { label: 'Stood Up',              icon: Activity,       color: 'text-indigo-400' },
    person_crouching:           { label: 'Crouching',             icon: Activity,       color: 'text-orange-400' },
    person_fallen:              { label: '⚠ Person Fallen',       icon: AlertTriangle,  color: 'text-red-500' },
    // Person gestures
    person_reaching_up:         { label: 'Reached Up',            icon: Zap,            color: 'text-yellow-400' },
    person_carrying:            { label: 'Carrying Object',        icon: Package,        color: 'text-purple-400' },
    // Devices
    person_using_phone:         { label: 'Using Phone',            icon: Smartphone,     color: 'text-cyan-400' },
    person_using_laptop:        { label: 'Using Laptop',           icon: Laptop,         color: 'text-sky-400' },
    person_watching_screen:     { label: 'Watching Screen',        icon: MonitorPlay,    color: 'text-sky-300' },
    person_drinking:            { label: 'Drinking',               icon: Coffee,         color: 'text-emerald-400' },
    person_reading:             { label: 'Reading',                icon: BookOpen,       color: 'text-orange-400' },
    person_pocketed_object:     { label: 'Pocketed Object',        icon: Package,        color: 'text-violet-400' },
    // Security events
    unattended_bag:             { label: '⚠ Unattended Bag',      icon: AlertTriangle,  color: 'text-red-400' },
    package_left:               { label: '⚠ Package Left',        icon: AlertTriangle,  color: 'text-orange-500' },
    person_running_toward:      { label: '⚠ Running Toward Cam',  icon: AlertTriangle,  color: 'text-rose-500' },
    // Group events
    group_gathering:            { label: 'Group Gathering',        icon: Users,          color: 'text-violet-400' },
    group_dispersing:           { label: 'Group Dispersing',       icon: Users,          color: 'text-slate-400' },
    // Lighting
    light_turned_on:            { label: 'Light Turned On',        icon: Lightbulb,      color: 'text-yellow-300' },
    light_turned_off:           { label: 'Light Turned Off',       icon: Lightbulb,      color: 'text-slate-400' },
    // Door
    door_opened:                { label: 'Door Opened',            icon: DoorOpen,       color: 'text-teal-400' },
    door_closed:                { label: 'Door Closed',            icon: DoorOpen,       color: 'text-slate-400' },
    // Vehicle
    vehicle_approaching:        { label: 'Vehicle Approaching',    icon: Car,            color: 'text-blue-400' },
    vehicle_receding:           { label: 'Vehicle Receding',       icon: Car,            color: 'text-slate-400' },
    vehicle_stationary:         { label: 'Vehicle Parked',         icon: Car,            color: 'text-amber-400' },
    vehicle_stopped:            { label: 'Vehicle Stopped',        icon: Car,            color: 'text-orange-400' },
  };
  if (et.startsWith('person_picked_up_')) {
    const obj = et.replace('person_picked_up_', '').replace(/_/g, ' ');
    return { label: `Picked Up ${obj}`, icon: Package, color: 'text-fuchsia-400' };
  }
  if (et.startsWith('person_placed_')) {
    const obj = et.replace('person_placed_', '').replace(/_/g, ' ');
    return { label: `Put Down ${obj}`, icon: Package, color: 'text-lime-400' };
  }
  return map[et] ?? {
    label: et.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    icon: Zap,
    color: 'text-slate-400',
  };
}

function getStatusBadge(status: string) {
  // BUG-04 FIX: API returns 'running', UI expected 'processing'
  const normalized = status === 'running' ? 'processing' : status;
  switch (normalized) {
    case 'completed': return { label: 'Done',       cls: 'bg-green-500/15 text-green-400 border-green-500/25',   dot: 'bg-green-400' };
    case 'failed':    return { label: 'Failed',     cls: 'bg-red-500/15 text-red-400 border-red-500/25',         dot: 'bg-red-400' };
    case 'processing':return { label: 'Processing', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/25',      dot: 'bg-blue-400 animate-pulse' };
    case 'queued':    return { label: 'Queued',     cls: 'bg-amber-500/15 text-amber-400 border-amber-500/25',   dot: 'bg-amber-400' };
    default:          return { label: normalized,   cls: 'bg-white/5 text-white/40 border-white/10',             dot: 'bg-white/30' };
  }
}

// ── Empty State ───────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-28 text-center">
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 200 }}
        className="relative mb-8"
      >
        <div className="w-24 h-24 rounded-3xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
          <Brain size={40} className="text-indigo-400" />
        </div>
        <div className="absolute -top-2 -right-2 w-8 h-8 rounded-xl bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
          <Sparkles size={14} className="text-violet-400" />
        </div>
      </motion.div>
      <motion.div initial={{ y: 10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.1 }}>
        <h2 className="text-2xl font-bold text-white mb-3">Ready for Intelligence</h2>
        <p className="text-white/40 text-sm leading-relaxed max-w-md mb-8">
          Upload any video — TCE will detect every person, object, and activity using
          <span className="text-indigo-300 font-semibold"> YOLO-World AI </span>
          (200+ classes) and build a precise event timeline.
        </p>
        <div className="flex flex-wrap justify-center gap-2 mb-8">
          {['Person Tracking','Light Detection','Object Recognition','Interaction AI','194 Classes'].map(tag => (
            <span key={tag} className="text-xs px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-white/50">
              {tag}
            </span>
          ))}
        </div>
        <Link href="/upload">
          <motion.button
            whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
            className="inline-flex items-center gap-2.5 bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-2xl font-semibold transition-colors shadow-lg shadow-indigo-500/25"
          >
            <UploadCloud size={18} /> Upload Your First Video
          </motion.button>
        </Link>
      </motion.div>
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, color, delay = 0 }: {
  label: string; value: string | number; icon: React.ElementType; color: string; delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.07] hover:bg-white/[0.05] hover:border-white/[0.12] transition-all group"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-white/40 uppercase tracking-wider mb-2">{label}</p>
          <p className="text-3xl font-bold text-white">{value}</p>
        </div>
        <div className={`w-10 h-10 rounded-xl bg-black/20 flex items-center justify-center ${color} group-hover:scale-110 transition-transform`}>
          <Icon size={18} />
        </div>
      </div>
    </motion.div>
  );
}

// ── Event Feed Row ────────────────────────────────────────────────────────────
function EventFeedRow({ evt, index }: { evt: EventRecord; index: number }) {
  const et = evt.event_type ?? evt.type ?? '';
  const { label, icon: Icon, color } = getEventLabel(et);
  const t = ((evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000).toFixed(1);
  const conf = Math.round((evt.confidence ?? 0) * 100);

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/[0.04] transition-colors group"
    >
      <div className={`w-8 h-8 rounded-lg bg-black/20 flex items-center justify-center flex-shrink-0 ${color}`}>
        <Icon size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white/80 font-medium truncate">{label}</p>
        <p className="text-xs text-white/30 font-mono">{t}s</p>
      </div>
      {conf > 0 && (
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-white/40 flex-shrink-0">
          {conf}%
        </span>
      )}
      {evt.video_id && (
        <Link href={`/timeline/${evt.video_id}`} className="opacity-0 group-hover:opacity-100 transition-opacity">
          <ChevronRight size={14} className="text-white/30" />
        </Link>
      )}
    </motion.div>
  );
}

// ── Job Card ──────────────────────────────────────────────────────────────────
function JobCard({ job, index }: { job: JobRecord; index: number }) {
  const badge = getStatusBadge(job.status);
  // BUG-04 FIX: API returns 'running', not 'processing'
  const isProcessing = job.status === 'processing' || job.status === 'running';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
    >
      <Link href={job.status === 'completed' && job.video_id ? `/timeline/${job.video_id}` : `/processing/${job.id}`}>
        <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.07] hover:bg-white/[0.06] hover:border-white/[0.14] transition-all group cursor-pointer">
          <div className="flex items-start gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
              job.status === 'completed' ? 'bg-green-500/10' :
              job.status === 'failed' ? 'bg-red-500/10' : 'bg-blue-500/10'
            }`}>
              {job.status === 'completed' ? <CheckCircle2 size={16} className="text-green-400" /> :
               job.status === 'failed'    ? <XCircle size={16} className="text-red-400" /> :
               isProcessing               ? <Loader2 size={16} className="text-blue-400 animate-spin" /> :
                                            <Clock size={16} className="text-amber-400" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <p className="text-sm font-semibold text-white/80 truncate group-hover:text-white transition-colors">
                  {job.filename?.replace('original.mp4', 'Video') ?? job.id}
                </p>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border flex-shrink-0 ${badge.cls}`}>
                  {badge.label}
                </span>
              </div>
              {job.video_metadata?.duration_hms && (
                <p className="text-xs text-white/30 mb-2">
                  {job.video_metadata.duration_hms} · {job.video_metadata.resolution ?? '—'}
                </p>
              )}
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${job.progress}%` }}
                    transition={{ duration: 0.6 }}
                    className={`h-full rounded-full ${
                      job.status === 'completed' ? 'bg-green-500' :
                      job.status === 'failed' ? 'bg-red-500' : 'bg-blue-500'
                    }`}
                  />
                </div>
                <span className="text-[10px] text-white/30 font-mono flex-shrink-0">{job.progress}%</span>
              </div>
              {job.event_count > 0 && (
                <p className="text-[10px] text-white/30 mt-1.5 flex items-center gap-1">
                  <Zap size={10} className="text-indigo-400" />
                  {job.event_count} events detected
                </p>
              )}
            </div>
            <ChevronRight size={14} className="text-white/20 group-hover:text-white/50 transition-colors mt-1 flex-shrink-0" />
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [stats, setStats]   = useState<AnalyticsStats | null>(null);
  const [jobs, setJobs]     = useState<JobRecord[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [deviceInfo, setDeviceInfo] = useState<{
    cuda_available?: boolean; gpu_name?: string; vram_gb?: number;
    device?: string; torch_version?: string;
  } | null>(null);
  const [activeModel, setActiveModel] = useState<string>('yolo11x');

  useEffect(() => {
    const load = async () => {
      try {
        const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';
        const [s, j, e, h] = await Promise.all([
          api.analytics() as Promise<AnalyticsStats>,
          api.jobs.list()  as Promise<JobRecord[]>,
          api.events.list({ limit: '8' }) as Promise<EventRecord[]>,
          fetch(`${API}/health`).then(r => r.json()).catch(() => null),
        ]);
        setStats(s);
        setJobs(Array.isArray(j) ? j : []);
        setEvents(Array.isArray(e) ? e : []);
        if (h?.device_info) setDeviceInfo(h.device_info);
        if (h?.experiment_config?.detection_model) setActiveModel(h.experiment_config.detection_model);
        setBackendError(null);
      } catch (err) {
        setBackendError('Cannot reach the backend. Make sure the server is running on port 8000.');
      } finally {
        setLoading(false);
      }
    };
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, []);


  if (loading) return (
    <div className="flex items-center justify-center py-32 gap-3 text-white/30">
      <Loader2 size={18} className="animate-spin" />
      <span className="text-sm">Loading intelligence dashboard…</span>
    </div>
  );

  const isEmpty = !backendError && !stats?.has_data && jobs.length === 0;
  if (isEmpty) return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-white/30 text-sm mt-1">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>
        {/* GPU/CPU device badge */}
        {deviceInfo && (
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-mono ${
            deviceInfo.cuda_available
              ? 'bg-green-500/10 border-green-500/20 text-green-400'
              : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${
              deviceInfo.cuda_available ? 'bg-green-400 animate-pulse' : 'bg-amber-400'
            }`} />
            <span>{deviceInfo.cuda_available ? 'CUDA' : 'CPU'}</span>
            {deviceInfo.gpu_name && <span className="text-white/40">· {deviceInfo.gpu_name.replace('NVIDIA ', '').replace(' Laptop GPU', '')}</span>}
            {deviceInfo.vram_gb && <span className="text-white/30">· {deviceInfo.vram_gb}GB</span>}
            <span className="text-white/20">· {activeModel}</span>
          </div>
        )}
      </div>
      <EmptyState />
    </div>
  );


  // BUG-02 FIX: Replace fake Objects Tracked (total_events*3) with real avg_compression_ratio
  const compressionDisplay = stats?.avg_compression_ratio
    ? `${(stats.avg_compression_ratio * 100).toFixed(0)}%`
    : '—';

  const statCards = [
    { label: 'Videos Processed', value: stats?.total_videos ?? 0,   icon: Film,       color: 'text-blue-400',    delay: 0 },
    { label: 'Events Detected',  value: stats?.total_events ?? 0,   icon: Zap,        color: 'text-violet-400',  delay: 0.05 },
    { label: 'Compression',      value: compressionDisplay,          icon: TrendingUp, color: 'text-cyan-400',    delay: 0.1 },
    { label: 'Data Processed',   value: formatBytes(stats?.total_bytes_uploaded ?? 0), icon: HardDrive, color: 'text-emerald-400', delay: 0.15 },
  ];

  // BUG-04 FIX: Handle 'running' API status in sort order
  const sortedJobs = [...jobs].sort((a, b) => {
    const order: Record<string, number> = { running: 0, processing: 0, queued: 1, completed: 2, failed: 3 };
    return (order[a.status] ?? 4) - (order[b.status] ?? 4);
  });

  const completedJobs = sortedJobs.filter(j => j.status === 'completed');
  const activeJobs    = sortedJobs.filter(j => j.status !== 'completed' && j.status !== 'failed');

  return (
    <div className="space-y-8">
      {/* BUG-01 FIX: Backend error banner — shown instead of fake empty state */}
      {backendError && (
        <div className="flex items-center gap-3 p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm">
          <XCircle size={18} className="flex-shrink-0 text-red-400" />
          <span>{backendError}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-white/30 text-sm mt-1">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* GPU / CPU live badge — always visible */}
          {deviceInfo && (
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-mono ${
              deviceInfo.cuda_available
                ? 'bg-green-500/10 border-green-500/20 text-green-400'
                : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
            }`}>
              <span className={`w-2 h-2 rounded-full ${
                deviceInfo.cuda_available ? 'bg-green-400 animate-pulse' : 'bg-amber-400'
              }`} />
              <span>{deviceInfo.cuda_available ? 'CUDA' : 'CPU'}</span>
              {deviceInfo.gpu_name && <span className="text-white/50">· {deviceInfo.gpu_name.replace('NVIDIA ', '').replace(' Laptop GPU', '')}</span>}
              {deviceInfo.vram_gb && <span className="text-white/30">· {deviceInfo.vram_gb}GB</span>}
              <span className="text-white/20">· {activeModel}</span>
            </div>
          )}
          <Link href="/upload">
            <motion.button
              whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-indigo-500/20"
            >
              <Plus size={16} /> New Upload
            </motion.button>
          </Link>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(s => <StatCard key={s.label} {...s} />)}
      </div>

      {/* Active Jobs Banner */}
      <AnimatePresence>
        {activeJobs.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className="p-4 rounded-2xl bg-blue-500/5 border border-blue-500/20 flex items-center gap-3"
          >
            <div className="w-8 h-8 rounded-xl bg-blue-500/15 flex items-center justify-center flex-shrink-0">
              <Cpu size={16} className="text-blue-400 animate-pulse" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-blue-300">
                {activeJobs.length} job{activeJobs.length > 1 ? 's' : ''} running · {activeModel} on {deviceInfo?.cuda_available ? `RTX GPU` : 'CPU'}
              </p>
              <p className="text-xs text-blue-400/60 mt-0.5">
                SAHI tiling · per-class confidence · adaptive frame skip · {deviceInfo?.vram_gb ?? '?'}GB VRAM
              </p>
            </div>
            <Link href={`/processing/${activeJobs[0]?.id}`} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors">
              View <ChevronRight size={12} />
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* Event Feed (3/5 wide) */}
        <div className="lg:col-span-3 space-y-3">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <BarChart3 size={15} className="text-white/30" />
              <h2 className="text-sm font-semibold text-white/50 uppercase tracking-wider">Recent Events</h2>
            </div>
            <Link href="/events" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors">
              View all <ArrowRight size={11} />
            </Link>
          </div>
          <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.06] space-y-1">
            {events.length === 0 ? (
              <div className="py-10 text-center">
                <Zap size={28} className="mx-auto text-white/10 mb-3" />
                <p className="text-white/25 text-sm">Events appear here after processing</p>
              </div>
            ) : (
              events.map((evt, i) => <EventFeedRow key={evt.id} evt={evt} index={i} />)
            )}
          </div>
        </div>

        {/* Jobs Panel (2/5 wide) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <Layers size={15} className="text-white/30" />
              <h2 className="text-sm font-semibold text-white/50 uppercase tracking-wider">All Analyses</h2>
            </div>
            <span className="text-xs text-white/25 font-mono">{jobs.length} total</span>
          </div>

          <div className="space-y-2">
            {sortedJobs.length === 0 ? (
              <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] text-center">
                <Clock size={24} className="mx-auto text-white/10 mb-2" />
                <p className="text-white/25 text-sm">No jobs yet</p>
              </div>
            ) : (
              sortedJobs.slice(0, 5).map((job, i) => <JobCard key={job.id} job={job} index={i} />)
            )}
          </div>

          <Link href="/upload" className="block">
            <div className="p-4 rounded-2xl border border-dashed border-white/[0.10] hover:border-indigo-500/40 hover:bg-indigo-500/5 transition-all text-center group cursor-pointer">
              <Plus size={16} className="mx-auto text-white/20 group-hover:text-indigo-400 mb-1 transition-colors" />
              <p className="text-xs text-white/25 group-hover:text-indigo-400 transition-colors">Add new video</p>
            </div>
          </Link>
        </div>
      </div>

      {/* Completed Timelines */}
      {completedJobs.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp size={15} className="text-white/30" />
              <h2 className="text-sm font-semibold text-white/50 uppercase tracking-wider">Completed Timelines</h2>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {completedJobs.map((job, i) => (
              <motion.div key={job.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <Link href={`/timeline/${job.video_id}`}>
                  <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.07] hover:bg-white/[0.06] hover:border-indigo-500/25 transition-all group cursor-pointer">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-9 h-9 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                        <Film size={16} className="text-indigo-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-white/80 group-hover:text-white transition-colors truncate">
                          {job.filename?.replace('original.mp4','Video') ?? 'Video'}
                        </p>
                        {job.video_metadata?.duration_hms && (
                          <p className="text-xs text-white/30">{job.video_metadata.duration_hms}</p>
                        )}
                      </div>
                      <ArrowRight size={14} className="text-white/20 group-hover:text-indigo-400 transition-colors flex-shrink-0" />
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-green-500/10 border border-green-500/20">
                        <Circle size={6} className="text-green-400 fill-green-400" />
                        <span className="text-[10px] text-green-400 font-semibold">Complete</span>
                      </div>
                      {job.event_count > 0 && (
                        <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/5">
                          <Zap size={10} className="text-violet-400" />
                          <span className="text-[10px] text-white/40">{job.event_count} events</span>
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Model Badge */}
      <div className="flex items-center justify-center gap-3 py-2 border-t border-white/[0.05] mt-4">
        <Brain size={12} className="text-indigo-400" />
        <p className="text-xs text-white/20">
        <p className="text-xs text-white/20">
          Active model: <span className="text-indigo-300/70 font-medium">{activeModel}</span> ·
          {deviceInfo?.cuda_available
            ? <span className="text-green-400/70 font-medium"> CUDA ({deviceInfo?.gpu_name?.replace('NVIDIA ', '').replace(' Laptop GPU', '') ?? 'GPU'}) </span>
            : <span className="text-amber-400/70 font-medium"> CPU mode </span>
          }
          · Quality analyzer · Low-light preprocessing · ROI zone detection
        </p>
      </div>
    </div>
  );
}
