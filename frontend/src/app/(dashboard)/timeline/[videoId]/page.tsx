'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Dna, Users, Play, Clock, Eye, AlertTriangle, ShieldCheck, Tag,
  Activity, Sun, Car, Box, Search, Zap, UserCheck, ChevronDown, ChevronUp,
  Maximize2, PlayCircle, ShieldAlert, Sparkles, Filter, Package, Laptop, Smartphone,
  Armchair, Tv, Monitor, FileText, CheckCircle2, ChevronRight
} from 'lucide-react';
import { api, API_BASE } from '@/lib/api/client';
import EventPreviewModal from '@/components/EventPreviewModal';
import PersonDossierModal from '@/components/PersonDossierModal';
import CinemaVideoPlayer from '@/components/CinemaVideoPlayer';
import Link from 'next/link';

// --- Data Types matching FastAPI Backend ---

export interface DetectedObject {
  class_name: string;
  display_name: string;
  class_id: number;
  category: string;
  instance_count: number;
  max_confidence: number;
  first_seen_ms: number;
}

export interface Person {
  person_label: string;
  description?: string;
  first_seen_ms: number;
  last_seen_ms: number;
  observation_count: number;
  entry_direction?: string;
  crop_url?: string;
  context_url?: string;
  track_ids: number[];
}

export interface EventRecord {
  id?: string;
  event_id?: string;
  event_type?: string;
  type?: string;
  start_ms?: number;
  end_ms?: number;
  timestamp_ms?: number;
  confidence?: number;
  rule_name?: string;
  evidence?: Record<string, any>;
  person_label?: string;
  crop_url?: string;
  display_name?: string;
  direction?: string;
}

export interface TimelineData {
  video_id: string;
  filename?: string;
  job_id?: string;
  job_status?: string;
  metadata?: { duration_hms?: string; fps?: number; resolution?: string; duration_seconds?: number };
  detected_objects: DetectedObject[];
  events: EventRecord[];
  event_count: number;
  events_by_category: Record<string, number>;
  activity_events: EventRecord[];
  lighting_events: EventRecord[];
  interaction_events: EventRecord[];
  vehicle_events: EventRecord[];
  persons: Person[];
  unique_persons: number;
  summary?: {
    overview?: string;
    narrative?: string;
    key_milestones?: Array<{ time: string; event: string; actor: string }>;
    total_kept_events?: number;
    compression_ratio?: number;
    actors_count?: number;
    security_status?: string;
  };
}

// --- Design Tokens & Color Palettes ---

const PERSON_ACCENTS = [
  { text: 'text-amber-400',   border: 'border-amber-400/40',   bg: 'bg-amber-400/10',   hex: '#f59e0b', tag: 'PRIMARY SUBJECT' },
  { text: 'text-cyan-400',    border: 'border-cyan-400/40',    bg: 'bg-cyan-400/10',    hex: '#00d4ff', tag: 'CO-ACTOR · CORRIDOR' },
  { text: 'text-emerald-400', border: 'border-emerald-400/40', bg: 'bg-emerald-400/10', hex: '#10b981', tag: 'WORKSTATION A' },
  { text: 'text-violet-400',  border: 'border-violet-400/40',  bg: 'bg-violet-400/10',  hex: '#a78bfa', tag: 'WORKSTATION B' },
  { text: 'text-rose-400',    border: 'border-rose-400/40',    bg: 'bg-rose-400/10',    hex: '#fb7185', tag: 'REAR WORKSPACE' },
];

const getAccent = (index: number) => PERSON_ACCENTS[index % PERSON_ACCENTS.length];

const getEventTime = (e: EventRecord) => (e.start_ms ?? e.timestamp_ms ?? 0) / 1000;
const getEventType = (e: EventRecord) => e.event_type ?? e.type ?? '';

const formatTime = (ms: number) => {
  const totalSeconds = Math.floor(ms / 1000);
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const fmtTimeSec = (sec: number) => {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(1);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};

// --- Detection & Anomaly Rules ---

const isAnomalyEvent = (e: EventRecord) => {
  const t = getEventType(e).toLowerCase();
  return (
    t.includes('theft') ||
    t.includes('stolen') ||
    t.includes('pocketed') ||
    t.includes('picked_up') ||
    t.includes('unattended') ||
    t.includes('disappeared') ||
    t.includes('package_left') ||
    t.includes('tampering')
  );
};

// --- Visual Components ---

function ConfidenceRing({ value, color = '#00d4ff' }: { value: number; color?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  const radius = 13;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (pct / 100) * circ;

  return (
    <div className="relative flex items-center justify-center w-9 h-9 shrink-0">
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 34 34">
        <circle cx="17" cy="17" r={radius} fill="none" stroke="currentColor" strokeWidth="2.5" className="text-white/10" />
        <motion.circle
          cx="17" cy="17" r={radius} fill="none" stroke={color} strokeWidth="2.5"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </svg>
      <span className="absolute text-[9px] font-mono font-bold text-white/90">{pct}%</span>
    </div>
  );
}

const LoadingScreen = () => (
  <div className="flex flex-col items-center justify-center h-screen w-full bg-[#07090e]">
    <div className="relative flex items-center justify-center w-48 h-48 mb-8">
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
        className="absolute inset-0 rounded-full border border-cyan-500/20"
        style={{ borderTopColor: '#00d4ff', borderRightColor: '#00d4ff' }}
      />
      <motion.div
        animate={{ rotate: -360 }}
        transition={{ duration: 7, repeat: Infinity, ease: "linear" }}
        className="absolute inset-4 rounded-full border border-amber-500/20"
        style={{ borderBottomColor: '#f59e0b', borderLeftColor: '#f59e0b' }}
      />
      <div className="flex flex-col items-center justify-center z-10 font-mono text-cyan-400">
        <Dna className="w-10 h-10 animate-pulse mb-2 text-[#00d4ff]" />
        <span className="text-[10px] tracking-widest text-white/40">TCE WORKSTATION</span>
      </div>
    </div>
    <motion.h2
      initial={{ opacity: 0.3 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 1.2, repeat: Infinity, repeatType: "reverse" }}
      className="text-cyan-400 font-mono text-sm tracking-[0.25em]"
    >
      INITIALIZING FORENSIC INTELLIGENCE...
    </motion.h2>
  </div>
);

// --- Top Intelligence Banner ---

function IntelligenceBanner({ data, anomaliesCount }: { data: TimelineData; anomaliesCount: number }) {
  return (
    <div className="w-full relative overflow-hidden bg-[#0a0e14]/95 backdrop-blur-xl border-b border-cyan-500/25 px-6 py-3 shrink-0 shadow-[0_4px_25px_rgba(0,0,0,0.6)]">
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-80" />
      
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 font-mono">
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-emerald-500/10 border border-emerald-500/30">
            <div className="w-2 h-2 rounded-full bg-emerald-400 live-pulse shadow-[0_0_8px_#10b981]" />
            <span className="text-emerald-400 font-bold tracking-wider">ANALYSIS COMPLETE</span>
          </div>

          <div className="h-4 w-px bg-white/10 hidden sm:block" />

          <div className="text-white/60">
            RECORD: <span className="text-cyan-300 font-bold">{data.filename || data.video_id}</span>
          </div>

          <div className="h-4 w-px bg-white/10 hidden sm:block" />

          <div className="flex items-center gap-1.5 text-white/70">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>{data.metadata?.duration_hms || `${data.metadata?.duration_seconds?.toFixed(1) || 0}s`}</span>
          </div>

          <span className="text-[10px] px-2 py-0.5 rounded bg-white/5 border border-white/10 text-white/40">
            {data.metadata?.resolution || '1080p'} · {data.metadata?.fps ? `${data.metadata.fps}fps` : '30fps'}
          </span>
        </div>

        <div className="flex items-center gap-5 text-xs">
          <div className="flex items-center gap-1.5">
            <Zap className="w-4 h-4 text-amber-400" />
            <span className="text-white font-bold">{data.event_count}</span>
            <span className="text-white/40">EVENTS</span>
          </div>

          <div className="flex items-center gap-1.5">
            <Users className="w-4 h-4 text-cyan-400" />
            <span className="text-white font-bold">{data.unique_persons}</span>
            <span className="text-white/40">ACTORS</span>
          </div>

          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded border ${
            anomaliesCount > 0
              ? 'bg-rose-500/15 border-rose-500/40 text-rose-300 shadow-[0_0_12px_rgba(244,63,94,0.25)]'
              : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
          }`}>
            <AlertTriangle className={`w-3.5 h-3.5 ${anomaliesCount > 0 ? 'text-rose-400' : 'text-emerald-400'}`} />
            <span className="font-bold">{anomaliesCount}</span>
            <span className="text-[10px] tracking-wider">{anomaliesCount === 1 ? 'ANOMALY FLAG' : 'ANOMALIES'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Main Timeline Workstation Page ---

export default function TimelinePage() {
  const params = useParams();
  const videoId = params.videoId as string;

  const [data, setData] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
  const [personFilter, setPersonFilter] = useState<string | null>(null);
  const [previewEventId, setPreviewEventId] = useState<string | null>(null);
  const [objectSearch, setObjectSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [seekTime, setSeekTime] = useState<number | null>(null);

  // Tab mode: 'timeline' vs 'summary'
  const [viewMode, setViewMode] = useState<'timeline' | 'summary'>('timeline');

  const fetchTimeline = useCallback(async () => {
    try {
      const result = await api.timeline(videoId) as TimelineData;
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  if (loading) return <LoadingScreen />;
  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#07090e] flex items-center justify-center p-6">
        <div className="surface-card p-8 rounded-2xl border border-rose-500/30 text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-rose-400 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-white mb-2">Workstation Stream Error</h2>
          <p className="text-white/50 text-xs font-mono">{error || 'Failed to retrieve timeline data'}</p>
        </div>
      </div>
    );
  }

  const durationSeconds = data.metadata?.duration_seconds ?? 0;
  const allEvents = [...data.events].sort((a, b) => getEventTime(a) - getEventTime(b));

  // Anomalies / Object Removal (Theft) detection
  const anomalyEvents = allEvents.filter(isAnomalyEvent);
  const anomaliesCount = anomalyEvents.length;

  // Filter events by person if selected
  const displayEvents = personFilter
    ? allEvents.filter(e => e.person_label === personFilter)
    : allEvents;

  // Detected Objects filtering
  const objectCategories = Array.from(new Set(data.detected_objects.map(o => o.category)));
  const filteredObjects = data.detected_objects.filter(o => {
    const matchSearch = o.display_name.toLowerCase().includes(objectSearch.toLowerCase()) ||
                        o.category.toLowerCase().includes(objectSearch.toLowerCase());
    const matchCat = !selectedCategory || o.category === selectedCategory;
    return matchSearch && matchCat;
  });

  // Safe seek handler that forces state update
  const handleSeek = (sec: number) => {
    setSeekTime(sec + Math.random() * 0.0001);
  };

  return (
    <div className="min-h-screen bg-[#07090e] text-white flex flex-col font-sans">
      {/* ── TOP BANNER ─────────────────────────────────────────────────── */}
      <IntelligenceBanner data={data} anomaliesCount={anomaliesCount} />

      {/* ── 3-PANEL FORENSIC WORKSTATION ─────────────────────────────────── */}
      <div className="flex-1 flex flex-col lg:flex-row w-full max-w-[1920px] mx-auto p-4 gap-4 h-full">

        {/* ── LEFT PANEL: FORENSIC ACTOR REGISTRY (280px) ───────────────── */}
        <aside className="w-full lg:w-[280px] shrink-0 flex flex-col bg-[#0b0f16]/90 backdrop-blur-xl border border-white/[0.08] rounded-2xl overflow-hidden shadow-2xl">
          {/* Header */}
          <div className="p-4 border-b border-white/[0.08] flex items-center justify-between bg-black/30">
            <div className="flex items-center gap-2.5 text-cyan-400 font-mono text-xs font-bold tracking-widest">
              <Dna className="w-4 h-4 text-cyan-400 animate-pulse" />
              <span>ACTOR REGISTRY</span>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-cyan-400/10 border border-cyan-400/30 text-[10px] font-mono text-cyan-300 font-bold">
              {data.persons.length} IDENTIFIED
            </span>
          </div>

          {/* Actor Filter Reset */}
          {personFilter && (
            <div className="px-3 py-2 bg-cyan-500/10 border-b border-cyan-500/20 flex items-center justify-between">
              <span className="text-[10px] font-mono text-cyan-300">Filtering: {personFilter}</span>
              <button
                onClick={() => setPersonFilter(null)}
                className="text-[10px] font-mono text-white/50 hover:text-white underline transition-colors"
              >
                Clear Filter
              </button>
            </div>
          )}

          {/* Scrollable Person Cards */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
            {data.persons.map((person, idx) => {
              const accent = getAccent(idx);
              const isSelected = personFilter === person.person_label;
              const durationSec = ((person.last_seen_ms - person.first_seen_ms) / 1000);
              const pEvts = allEvents.filter(e => e.person_label === person.person_label).length;

              const cropSrc = person.crop_url
                ? (person.crop_url.startsWith('http') ? person.crop_url : `http://localhost:8000${person.crop_url}`)
                : null;

              return (
                <div
                  key={person.person_label}
                  onClick={() => setPersonFilter(isSelected ? null : person.person_label)}
                  className={`relative p-3 rounded-xl border cursor-pointer transition-all duration-300 overflow-hidden group ${
                    isSelected
                      ? `bg-white/[0.06] border-cyan-400/60 shadow-[0_0_20px_rgba(0,212,255,0.2)]`
                      : 'bg-black/40 border-white/[0.06] hover:border-cyan-400/30 hover:bg-white/[0.02]'
                  }`}
                >
                  <div className={`absolute top-0 left-0 w-1 h-full ${accent.bg} ${isSelected ? 'opacity-100' : 'opacity-40'}`} />

                  <div className="flex gap-3">
                    {/* Portrait Crop with HUD Reticle */}
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedPerson(person);
                      }}
                      className="relative w-16 h-20 rounded-lg overflow-hidden shrink-0 bg-black/60 border border-white/10 group/thumb shadow-md"
                    >
                      <div className="absolute top-1 left-1 w-2 h-2 border-t border-l border-cyan-400/70 z-10" />
                      <div className="absolute top-1 right-1 w-2 h-2 border-t border-r border-cyan-400/70 z-10" />
                      <div className="absolute bottom-1 left-1 w-2 h-2 border-b border-l border-cyan-400/70 z-10" />
                      <div className="absolute bottom-1 right-1 w-2 h-2 border-b border-r border-cyan-400/70 z-10" />

                      {cropSrc ? (
                        <img
                          src={cropSrc}
                          alt={person.person_label}
                          className="w-full h-full object-cover group-hover/thumb:scale-110 transition-transform duration-500"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-white/30">
                          <Users size={20} />
                        </div>
                      )}

                      <motion.div
                        className="absolute left-0 right-0 h-[1.5px] bg-cyan-400/60 z-20 shadow-[0_0_6px_#00d4ff]"
                        animate={{ top: ['0%', '100%'] }}
                        transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }}
                      />

                      <div className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-emerald-400 z-30 shadow-[0_0_6px_#10b981]" />
                    </div>

                    {/* Person Metadata */}
                    <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
                      <div>
                        <div className="flex items-center justify-between">
                          <span className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded border uppercase tracking-wider ${accent.text} ${accent.border} ${accent.bg}`}>
                            {person.person_label}
                          </span>
                          <span className="text-[10px] font-mono text-cyan-300 font-bold">{pEvts} evts</span>
                        </div>
                        <p className="text-[11px] text-white/70 font-medium truncate mt-1">
                          {person.description || accent.tag}
                        </p>
                      </div>

                      <div className="grid grid-cols-2 gap-1 text-[9px] font-mono text-white/40 border-t border-white/5 pt-1.5 mt-1">
                        <div>DUR: <span className="text-white/80 font-bold">{durationSec.toFixed(1)}s</span></div>
                        <div>FRAMES: <span className="text-white/80 font-bold">{person.observation_count}f</span></div>
                      </div>

                      <div className="flex items-center gap-1.5 mt-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSeek(person.first_seen_ms / 1000);
                          }}
                          className="flex-1 flex items-center justify-center gap-1 py-1 rounded bg-cyan-400/10 border border-cyan-400/30 text-cyan-300 hover:bg-cyan-400/20 text-[9px] font-mono transition-colors"
                          title="Seek video to entry"
                        >
                          <Play size={9} />
                          TRACK
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedPerson(person);
                          }}
                          className="flex items-center justify-center gap-1 px-2 py-1 rounded bg-white/5 border border-white/10 text-white/70 hover:text-white hover:bg-white/10 text-[9px] font-mono transition-colors"
                        >
                          <Maximize2 size={9} />
                          DOSSIER
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="p-3 border-t border-white/[0.08] bg-black/40 text-[10px] font-mono text-white/40 flex items-center justify-between">
            <span>ReID Model: MobileNetV3 L2</span>
            <span className="text-emerald-400">NORM VERIFIED</span>
          </div>
        </aside>

        {/* ── CENTER PANEL: VIDEO PLAYER + TIMELINE TELEMETRY ───────────── */}
        <main className="flex-1 flex flex-col min-w-0 gap-4 overflow-y-auto custom-scrollbar">

          {/* Forensic Cinema Video Player with HUD */}
          <div className="w-full">
            <CinemaVideoPlayer
              videoId={videoId}
              durationSeconds={durationSeconds}
              persons={data.persons}
              events={allEvents}
              seekTimestamp={seekTime}
              onPersonSelect={setSelectedPerson}
            />
          </div>

          {/* Chronological Narrative Sequence (Story Strip) */}
          <div className="hud-card p-4 rounded-2xl border border-white/[0.08]">
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-mono font-bold text-white/90 uppercase tracking-wider">
                  Chronological Narrative Sequence
                </h3>
              </div>
              <span className="text-[10px] font-mono text-white/40">Click any keypoint to jump in player</span>
            </div>

            <div className="overflow-x-auto pb-2 scrollbar-thin">
              <div className="flex items-center gap-2 min-w-max px-1 py-1">
                {allEvents.map((evt, i) => {
                  const t = getEventTime(evt);
                  const isAnomaly = isAnomalyEvent(evt);
                  return (
                    <motion.div
                      key={evt.event_id ?? evt.id ?? i}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => handleSeek(t)}
                      className={`flex flex-col items-center gap-1.5 p-2 rounded-xl border cursor-pointer transition-all ${
                        isAnomaly
                          ? 'bg-rose-950/40 border-rose-500/60 text-rose-300 shadow-[0_0_12px_rgba(244,63,94,0.3)]'
                          : 'bg-[#0d1218]/90 border-white/10 hover:border-cyan-400/50 text-white/80'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${isAnomaly ? 'bg-rose-400 animate-ping' : 'bg-cyan-400'}`} />
                        <span className="text-[10px] font-mono text-cyan-300">{fmtTimeSec(t)}</span>
                      </div>
                      <span className="text-[10px] font-medium max-w-[120px] truncate text-center">
                        {evt.display_name || evt.evidence?.description || getEventType(evt).replace(/_/g, ' ')}
                      </span>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* View Mode Toggle: Interactive Timeline vs Text Narrative Summary */}
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewMode('timeline')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition-all ${
                  viewMode === 'timeline'
                    ? 'bg-cyan-500/20 border border-cyan-400/50 text-cyan-300 shadow-[0_0_15px_rgba(0,212,255,0.2)]'
                    : 'text-white/40 hover:text-white bg-white/5 border border-white/5'
                }`}
              >
                <Activity size={14} />
                <span>Pivotal Milestone Timeline ({displayEvents.length})</span>
              </button>

              <button
                onClick={() => setViewMode('summary')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition-all ${
                  viewMode === 'summary'
                    ? 'bg-amber-500/20 border border-amber-400/50 text-amber-300 shadow-[0_0_15px_rgba(245,158,11,0.2)]'
                    : 'text-white/40 hover:text-white bg-white/5 border border-white/5'
                }`}
              >
                <FileText size={14} />
                <span>Text Summary & Executive Dossier</span>
              </button>

              <Link
                href={`/stories/${videoId}`}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-bold text-purple-300 hover:text-white bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/20 transition-all shadow-[0_0_10px_rgba(168,85,247,0.15)]"
              >
                <Sparkles size={14} className="text-purple-400" />
                <span>Story Arcs Studio</span>
              </Link>
            </div>

            <span className="text-[10px] font-mono text-white/40 hidden sm:inline">
              Patent Formulation: 24-Hour CCTV → Condensed Timeline Narrative
            </span>
          </div>

          {/* View Content: Option A (Milestone Timeline) */}
          {viewMode === 'timeline' ? (
            <div className="hud-card p-5 rounded-2xl border border-white/[0.08] flex-1 flex flex-col">
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/[0.06]">
                <div className="flex items-center gap-2 text-cyan-400 font-mono text-xs font-bold tracking-widest">
                  <Activity className="w-4 h-4" />
                  <span>CORE MILESTONE TIMELINE ({displayEvents.length})</span>
                </div>
                <span className="text-[10px] font-mono text-white/40">Clean, human-interpretable event milestones</span>
              </div>

              <div className="space-y-2.5">
                {displayEvents.map((evt, i) => {
                  const t = getEventTime(evt);
                  const conf = evt.confidence ?? 0.88;
                  const isAnomaly = isAnomalyEvent(evt);
                  const description = evt.display_name || evt.evidence?.description || getEventType(evt).replace(/_/g, ' ');

                  return (
                    <div
                      key={evt.event_id ?? evt.id ?? i}
                      className={`flex items-center gap-3.5 p-3.5 rounded-xl border transition-all ${
                        isAnomaly
                          ? 'bg-rose-950/20 border-rose-500/40 hover:border-rose-500/60'
                          : 'bg-[#090d14]/70 border-white/[0.04] hover:border-cyan-400/30'
                      }`}
                    >
                      {/* Play Jump Button */}
                      <button
                        onClick={() => handleSeek(t)}
                        className="w-8 h-8 rounded-lg bg-cyan-400/10 border border-cyan-400/30 text-cyan-300 hover:bg-cyan-400/20 flex items-center justify-center shrink-0 transition-colors"
                        title="Play moment in video player"
                      >
                        <Play size={12} className="ml-0.5" />
                      </button>

                      {/* Event Details */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          {evt.person_label && (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-amber-400/40 bg-amber-400/10 text-amber-300 font-bold">
                              {evt.person_label}
                            </span>
                          )}
                          <span className="text-xs font-bold text-white tracking-tight truncate">
                            {description}
                          </span>
                          {isAnomaly && (
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold">
                              ⚠ ANOMALY / REMOVAL
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-[10px] font-mono text-white/40">
                          <span>TIMECODE: <span className="text-cyan-300 font-bold">{fmtTimeSec(t)}</span></span>
                          <span>ACTION: {getEventType(evt).replace(/_/g, ' ').toUpperCase()}</span>
                        </div>
                      </div>

                      {/* Confidence Ring */}
                      <ConfidenceRing value={conf} color={isAnomaly ? '#fb7185' : '#00d4ff'} />

                      {/* Evidence inspection modal button */}
                      <button
                        onClick={() => setPreviewEventId(evt.event_id ?? evt.id ?? null)}
                        className="px-2.5 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/20 text-[10px] font-mono flex items-center gap-1.5 transition-colors shrink-0"
                        title="View forensic frame captures"
                      >
                        <Eye size={12} />
                        <span>EVIDENCE</span>
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* View Content: Option B (Executive Text Summary Dossier) */
            <div className="hud-card p-6 rounded-2xl border border-white/[0.08] flex-1 flex flex-col space-y-6">
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
                <div className="flex items-center gap-2 text-amber-400 font-mono text-xs font-bold tracking-widest">
                  <FileText className="w-4 h-4" />
                  <span>EXECUTIVE INTELLIGENCE SUMMARY & NARRATIVE</span>
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                  {data.summary?.security_status || 'SECURE'}
                </span>
              </div>

              {/* Textual Narrative Breakdown */}
              <div className="bg-black/40 border border-white/[0.06] rounded-xl p-5 space-y-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Sparkles size={16} className="text-cyan-400" />
                  <span>Plain Language Scene Narrative</span>
                </h3>
                <p className="text-xs text-white/80 leading-relaxed font-sans">
                  {data.summary?.narrative || (
                    displayEvents.length > 0 ? (
                      `Scene timeline for ${data.filename || videoId}: detected ${data.event_count} key chronological events across ${data.unique_persons || (data.persons?.length || 0)} tracked actors and ${data.detected_objects?.length || 0} object classes. Key sequence begins with ${displayEvents[0]?.display_name || displayEvents[0]?.event_type?.replace(/_/g, ' ')} at ${fmtTimeSec(getEventTime(displayEvents[0]))}s, spanning a compressed duration of ${data.metadata?.duration_hms || `${durationSeconds.toFixed(1)}s`}.`
                    ) : (
                      "No critical anomalies or human activities were observed in this video stream."
                    )
                  )}
                </p>
              </div>

              {/* Chronological Table of Milestones */}
              <div>
                <h4 className="text-xs font-mono font-bold text-white/60 uppercase tracking-wider mb-3">
                  Chronological Milestone Sequence
                </h4>
                <div className="divide-y divide-white/[0.04] border border-white/[0.06] rounded-xl overflow-hidden bg-black/30">
                  {((data.summary?.key_milestones && data.summary.key_milestones.length > 0)
                    ? data.summary.key_milestones
                    : displayEvents.slice(0, 15).map((evt) => ({
                        time: fmtTimeSec(getEventTime(evt)),
                        event: evt.display_name || evt.event_type?.replace(/_/g, ' ') || 'Event',
                        actor: evt.person_label || (evt.evidence?.person_label) || 'Scene'
                      }))
                  ).map((m, idx) => (
                    <div key={idx} className="p-3 flex items-center justify-between text-xs font-mono hover:bg-white/[0.02] transition-colors">
                      <div className="flex items-center gap-3">
                        <span className="text-cyan-300 font-bold w-16">{m.time}</span>
                        <span className="text-white/90">{m.event}</span>
                      </div>
                      <span className="text-[10px] text-white/40 bg-white/5 px-2 py-0.5 rounded">{m.actor}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

        </main>

        {/* ── RIGHT PANEL: AI THREAT ASSESSMENT & OBJECT INVENTORY (320px) ─ */}
        <aside className="w-full lg:w-[320px] shrink-0 flex flex-col gap-4">

          {/* Section 1: Intelligence Summary Metrics (2x2 grid) */}
          <div className="hud-card p-4 rounded-2xl border border-white/[0.08]">
            <div className="text-[10px] font-mono font-bold text-white/50 mb-3 tracking-widest border-b border-white/[0.06] pb-2 uppercase">
              SCENE METRICS
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <div className="bg-black/40 border border-white/[0.05] rounded-xl p-3 flex flex-col items-center justify-center text-center">
                <Zap className="w-5 h-5 text-amber-400 mb-1" />
                <div className="text-xl font-bold font-mono text-white">{data.event_count}</div>
                <div className="text-[9px] text-white/40 font-mono uppercase mt-0.5">Total Events</div>
              </div>

              <div className="bg-black/40 border border-white/[0.05] rounded-xl p-3 flex flex-col items-center justify-center text-center">
                <UserCheck className="w-5 h-5 text-cyan-400 mb-1" />
                <div className="text-xl font-bold font-mono text-white">{data.unique_persons}</div>
                <div className="text-[9px] text-white/40 font-mono uppercase mt-0.5">Unique Actors</div>
              </div>

              <div className="bg-black/40 border border-white/[0.05] rounded-xl p-3 flex flex-col items-center justify-center text-center">
                <Clock className="w-5 h-5 text-emerald-400 mb-1" />
                <div className="text-sm font-bold font-mono text-white">{data.metadata?.duration_hms || `${durationSeconds.toFixed(0)}s`}</div>
                <div className="text-[9px] text-white/40 font-mono uppercase mt-0.5">Timeline Span</div>
              </div>

              <div className="bg-black/40 border border-white/[0.05] rounded-xl p-3 flex flex-col items-center justify-center text-center">
                <Eye className="w-5 h-5 text-violet-400 mb-1" />
                <div className="text-xl font-bold font-mono text-white">{data.detected_objects.length}</div>
                <div className="text-[9px] text-white/40 font-mono uppercase mt-0.5">Object Classes</div>
              </div>
            </div>
          </div>

          {/* Section 2: Anomaly / Theft / Removal Feed */}
          <div className="hud-card p-4 rounded-2xl border border-white/[0.08] flex flex-col">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5 mb-3">
              <div className="flex items-center gap-2 text-rose-400 font-mono text-xs font-bold tracking-wider">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <span>AI THREAT / THEFT FEED</span>
              </div>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${
                anomaliesCount > 0 ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'bg-emerald-500/10 text-emerald-400'
              }`}>
                {anomaliesCount} FLAGS
              </span>
            </div>

            <div className="space-y-2.5 max-h-[220px] overflow-y-auto custom-scrollbar">
              {anomaliesCount === 0 ? (
                <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-center flex flex-col items-center justify-center">
                  <ShieldCheck className="w-8 h-8 text-emerald-400 mb-2 opacity-80" />
                  <div className="text-xs font-mono font-bold text-emerald-400 tracking-wider">SCENE SECURE</div>
                  <div className="text-[10px] text-white/40 mt-1">
                    Zero object disappearance or theft patterns flagged.
                  </div>
                </div>
              ) : (
                anomalyEvents.map((anomaly, idx) => {
                  const t = getEventTime(anomaly);
                  return (
                    <div
                      key={anomaly.event_id ?? idx}
                      className="p-3 rounded-xl bg-rose-950/30 border border-rose-500/40 hover:border-rose-400 transition-all flex flex-col gap-2"
                    >
                      <div className="flex items-start justify-between">
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold border border-rose-500/30">
                          THEFT / REMOVAL
                        </span>
                        <span className="text-[10px] font-mono text-cyan-300 font-bold">{fmtTimeSec(t)}</span>
                      </div>
                      <div className="text-xs font-bold text-white truncate">
                        {anomaly.display_name || getEventType(anomaly).replace(/_/g, ' ')}
                      </div>
                      <div className="flex items-center justify-between text-[10px] font-mono">
                        <span className="text-white/50">{anomaly.person_label || 'Unassigned Actor'}</span>
                        <button
                          onClick={() => handleSeek(t)}
                          className="px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-white flex items-center gap-1 transition-colors"
                        >
                          <Play size={10} /> REVIEW
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Section 3: Scene Object Inventory */}
          <div className="hud-card p-4 rounded-2xl border border-white/[0.08] flex-1 flex flex-col">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5 mb-3">
              <div className="flex items-center gap-2 text-emerald-400 font-mono text-xs font-bold tracking-wider">
                <Tag className="w-4 h-4" />
                <span>SCENE INVENTORY</span>
              </div>
              <span className="text-[10px] font-mono text-white/40">{filteredObjects.length} ITEMS</span>
            </div>

            {/* Search Input */}
            <div className="relative mb-3">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/30" />
              <input
                type="text"
                placeholder="Search detected items..."
                value={objectSearch}
                onChange={e => setObjectSearch(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-xl py-2 pl-8 pr-3 text-xs text-white placeholder-white/30 outline-none focus:border-cyan-400/50 transition-colors font-mono"
              />
            </div>

            {/* Object Category Pills */}
            {objectCategories.length > 1 && (
              <div className="flex flex-wrap gap-1 mb-3">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={`text-[9px] font-mono px-2 py-0.5 rounded border transition-colors ${
                    !selectedCategory ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300' : 'bg-white/5 border-white/10 text-white/40'
                  }`}
                >
                  ALL
                </button>
                {objectCategories.map(cat => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                    className={`text-[9px] font-mono px-2 py-0.5 rounded border capitalize transition-colors ${
                      selectedCategory === cat ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300' : 'bg-white/5 border-white/10 text-white/40'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            )}

            {/* Object List */}
            <div className="flex-1 overflow-y-auto space-y-2 custom-scrollbar pr-1 max-h-[300px]">
              {filteredObjects.length === 0 ? (
                <div className="text-center text-white/30 text-xs py-6 font-mono">No matching objects found.</div>
              ) : (
                filteredObjects.map((obj, i) => (
                  <div
                    key={`${obj.class_name}-${i}`}
                    onClick={() => handleSeek(obj.first_seen_ms / 1000)}
                    className="flex items-center gap-3 p-2.5 rounded-xl bg-black/30 border border-white/[0.05] hover:border-cyan-400/30 transition-all cursor-pointer group"
                  >
                    <div className="w-8 h-8 rounded-lg bg-black/50 border border-white/10 flex items-center justify-center shrink-0 text-cyan-400 group-hover:scale-105 transition-transform">
                      <Box size={14} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold text-white/90 truncate">{obj.display_name}</span>
                        <span className="text-[9px] font-mono px-1 rounded bg-white/5 text-white/40">{obj.instance_count}×</span>
                      </div>
                      <div className="text-[10px] font-mono text-white/40 capitalize">{obj.category} · @ {fmtTimeSec(obj.first_seen_ms / 1000)}</div>
                    </div>
                    <ConfidenceRing value={obj.max_confidence} color="#10b981" />
                  </div>
                ))
              )}
            </div>
          </div>

        </aside>

      </div>

      {/* ── MODALS ─────────────────────────────────────────────────────── */}
      <PersonDossierModal
        person={selectedPerson}
        allEvents={allEvents}
        durationSeconds={durationSeconds}
        onClose={() => setSelectedPerson(null)}
      />

      {previewEventId && (
        <EventPreviewModal
          eventId={previewEventId}
          onClose={() => setPreviewEventId(null)}
        />
      )}
    </div>
  );
}
