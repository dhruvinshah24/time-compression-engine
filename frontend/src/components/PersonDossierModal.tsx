'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  X, User, Clock, Eye, MapPin, Activity,
  ChevronRight, Target, Crosshair, ArrowRight,
  Shield, Film, BarChart2,
} from 'lucide-react';
import { useState } from 'react';

interface Person {
  person_label: string;
  first_seen_ms: number;
  last_seen_ms: number;
  observation_count: number;
  entry_direction?: string;
  crop_url?: string;
  context_url?: string;
  track_ids: number[];
}

interface EventRecord {
  id?: string;
  event_id?: string;
  event_type?: string;
  type?: string;
  start_ms?: number;
  end_ms?: number;
  timestamp_ms?: number;
  confidence?: number;
  person_label?: string;
  crop_url?: string;
  display_name?: string;
}

interface PersonDossierModalProps {
  person: Person | null;
  allEvents: EventRecord[];
  durationSeconds: number;
  onClose: () => void;
}

function fmtTimecode(ms: number) {
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  const msRem = ms % 1000;
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}:${String(msRem).padStart(3, '0')}`;
}

function DirectionArrow({ dir }: { dir?: string }) {
  const angles: Record<string, string> = {
    left: 'rotate-180', right: 'rotate-0', top: '-rotate-90', bottom: 'rotate-90',
  };
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-mono text-amber-400 uppercase tracking-wider">
      <ArrowRight size={12} className={`transition-transform ${angles[dir ?? 'right']}`} />
      {dir ?? 'unknown'}
    </span>
  );
}

const ACCENT_COLORS = [
  { border: 'border-cyan-400/50', bg: 'bg-cyan-400/10', text: 'text-cyan-400', hex: '#00d4ff' },
  { border: 'border-amber-400/50', bg: 'bg-amber-400/10', text: 'text-amber-400', hex: '#f59e0b' },
  { border: 'border-emerald-400/50', bg: 'bg-emerald-400/10', text: 'text-emerald-400', hex: '#10b981' },
  { border: 'border-violet-400/50', bg: 'bg-violet-400/10', text: 'text-violet-400', hex: '#a78bfa' },
  { border: 'border-rose-400/50', bg: 'bg-rose-400/10', text: 'text-rose-400', hex: '#fb7185' },
];

export default function PersonDossierModal({
  person, allEvents, durationSeconds, onClose,
}: PersonDossierModalProps) {
  const [view, setView] = useState<'portrait' | 'scene'>('portrait');
  const [imgError, setImgError] = useState(false);
  const [ctxError, setCtxError] = useState(false);

  if (!person) return null;

  const personEvents = allEvents
    .filter(e => e.person_label === person.person_label)
    .sort((a, b) => (a.start_ms ?? a.timestamp_ms ?? 0) - (b.start_ms ?? b.timestamp_ms ?? 0));

  const durationSec = (person.last_seen_ms - person.first_seen_ms) / 1000;
  const coverage = durationSeconds > 0 ? Math.min((durationSec / durationSeconds) * 100, 100) : 0;

  const personNum = parseInt(person.person_label.replace('Person ', '')) || 1;
  const accent = ACCENT_COLORS[(personNum - 1) % ACCENT_COLORS.length];

  return (
    <AnimatePresence>
      {/* Backdrop */}
      <motion.div
        key="dossier-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/85 backdrop-blur-lg flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Modal */}
        <motion.div
          key="dossier-modal"
          initial={{ opacity: 0, scale: 0.92, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ type: 'spring', stiffness: 380, damping: 28 }}
          onClick={e => e.stopPropagation()}
          className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl bg-[#0c0f17] border border-white/8 shadow-[0_0_80px_rgba(0,0,0,0.9)]"
          style={{ scrollbarWidth: 'thin' }}
        >
          {/* HUD corner brackets */}
          {[['top-3 left-3', 'border-t-2 border-l-2'], ['top-3 right-3', 'border-t-2 border-r-2'],
            ['bottom-3 left-3', 'border-b-2 border-l-2'], ['bottom-3 right-3', 'border-b-2 border-r-2']].map(([pos, borders], i) => (
            <div key={i} className={`absolute ${pos} w-5 h-5 ${borders} ${accent.border} opacity-50`} />
          ))}

          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg ${accent.bg} border ${accent.border} flex items-center justify-center ${accent.text}`}>
                <Shield size={15} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight">{person.person_label}</h2>
                <p className="text-[10px] font-mono text-white/25 uppercase tracking-[0.18em]">
                  Forensic Dossier · Visual Identity Record
                </p>
              </div>
              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded border ${accent.border} ${accent.bg} ${accent.text} tracking-[0.15em]`}>
                ID-{String(personNum).padStart(3, '0')}
              </span>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg bg-white/4 border border-white/8 flex items-center justify-center text-white/40 hover:text-white hover:bg-white/10 transition-all"
            >
              <X size={15} />
            </button>
          </div>

          {/* Body */}
          <div className="grid grid-cols-1 md:grid-cols-[1fr_300px]">
            {/* Left: Image viewer */}
            <div className="p-6 border-r border-white/5">
              {/* View toggle */}
              <div className="flex gap-1 mb-5 p-1 rounded-xl bg-black/50 border border-white/5 w-fit">
                {([['portrait', User, 'ID PORTRAIT'], ['scene', Target, 'IN-SCENE']] as const).map(([v, Icon, label]) => (
                  <button
                    key={v}
                    onClick={() => setView(v)}
                    className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-[11px] font-mono transition-all ${
                      view === v
                        ? `${accent.bg} border ${accent.border} ${accent.text} shadow-sm`
                        : 'text-white/30 hover:text-white/60'
                    }`}
                  >
                    <Icon size={12} />
                    {label}
                  </button>
                ))}
              </div>

              {/* Image frame */}
              <div
                className={`relative rounded-2xl overflow-hidden bg-[#07090e] border ${accent.border} min-h-[280px] flex items-center justify-center`}
                style={{ boxShadow: `0 0 30px ${accent.hex}18` }}
              >
                {/* Corner decorations inside frame */}
                {[['top-2 left-2', 'border-t border-l'], ['top-2 right-2', 'border-t border-r'],
                  ['bottom-2 left-2', 'border-b border-l'], ['bottom-2 right-2', 'border-b border-r']].map(([pos, borders], i) => (
                  <div key={i} className={`absolute ${pos} w-5 h-5 ${borders} ${accent.border} z-10 opacity-70`} />
                ))}

                {/* View label */}
                <div className="absolute top-3 inset-x-0 flex justify-center z-20">
                  <span className={`text-[9px] font-mono px-2 py-0.5 rounded border ${accent.border} ${accent.bg} ${accent.text} tracking-[0.2em] uppercase`}>
                    {view === 'portrait' ? '▪ ID PHOTO' : '⊕ IN-SCENE LOCATION'}
                  </span>
                </div>

                <AnimatePresence mode="wait">
                  {view === 'portrait' ? (
                    <motion.div key="portrait" initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 12 }} className="w-full flex justify-center p-6 pt-10">
                      {person.crop_url && !imgError ? (
                        <img src={person.crop_url} alt={person.person_label} className="max-h-[360px] object-contain rounded-xl" onError={() => setImgError(true)} />
                      ) : (
                        <div className="flex flex-col items-center gap-3 py-14">
                          <div className={`w-16 h-16 rounded-full border-2 border-dashed ${accent.border} flex items-center justify-center`}>
                            <User size={26} className={`${accent.text} opacity-60`} />
                          </div>
                          <p className="text-[11px] font-mono text-white/25">No portrait available</p>
                        </div>
                      )}
                    </motion.div>
                  ) : (
                    <motion.div key="scene" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} className="w-full flex justify-center p-4 pt-10">
                      {person.context_url && !ctxError ? (
                        <img src={person.context_url} alt={`${person.person_label} in scene`} className="max-h-[360px] w-full object-contain rounded-xl" onError={() => setCtxError(true)} />
                      ) : (
                        <div className="flex flex-col items-center gap-3 py-14">
                          <div className={`w-16 h-16 rounded-full border-2 border-dashed ${accent.border} flex items-center justify-center`}>
                            <Crosshair size={26} className={`${accent.text} opacity-40`} />
                          </div>
                          <p className="text-[11px] font-mono text-white/25">Context snapshot unavailable</p>
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Coverage bar */}
              <div className="mt-4">
                <div className="flex justify-between mb-1.5">
                  <span className="text-[10px] font-mono text-white/25 uppercase tracking-[0.15em]">Video Coverage</span>
                  <span className={`text-[10px] font-mono ${accent.text}`}>{coverage.toFixed(1)}%</span>
                </div>
                <div className="h-1 rounded-full bg-white/4 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${coverage}%` }}
                    transition={{ duration: 1, ease: 'easeOut' }}
                    className="h-full rounded-full"
                    style={{ background: `linear-gradient(90deg, ${accent.hex}40, ${accent.hex})` }}
                  />
                </div>
              </div>
            </div>

            {/* Right: Telemetry */}
            <div className="p-5 space-y-4">
              <p className="text-[10px] font-mono text-white/20 uppercase tracking-[0.2em]">Telemetry</p>

              {/* Duration — large */}
              <div className={`p-4 rounded-xl ${accent.bg} border ${accent.border}`}>
                <p className="text-[9px] font-mono text-white/30 uppercase tracking-[0.2em] mb-1">Active Duration</p>
                <p className="text-3xl font-mono font-bold text-amber-400">{durationSec.toFixed(1)}<span className="text-base text-amber-400/60">s</span></p>
              </div>

              {/* Grid stats */}
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'FIRST SEEN', value: fmtTimecode(person.first_seen_ms), icon: Film },
                  { label: 'LAST SEEN', value: fmtTimecode(person.last_seen_ms), icon: Film },
                  { label: 'OBS. FRAMES', value: `${person.observation_count}`, icon: Eye },
                  { label: 'ENTRY VEC.', value: person.entry_direction ?? '—', icon: MapPin },
                ].map(({ label, value, icon: Icon }) => (
                  <div key={label} className="p-2.5 rounded-lg bg-black/30 border border-white/5">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Icon size={10} className="text-white/25" />
                      <span className="text-[8px] font-mono text-white/25 uppercase tracking-wider">{label}</span>
                    </div>
                    <span className="text-[11px] font-mono text-white/70 capitalize">{value}</span>
                  </div>
                ))}
              </div>

              {/* Track IDs */}
              <div className="p-3 rounded-lg bg-black/30 border border-white/5">
                <p className="text-[9px] font-mono text-white/25 uppercase tracking-wider mb-2">Track Fragments</p>
                <div className="flex flex-wrap gap-1">
                  {person.track_ids.slice(0, 10).map(id => (
                    <span key={id} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-white/35">T#{id}</span>
                  ))}
                  {person.track_ids.length > 10 && (
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-white/25">+{person.track_ids.length - 10}</span>
                  )}
                </div>
              </div>

              {/* Linked events */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Activity size={11} className={accent.text} />
                  <p className="text-[10px] font-mono text-white/20 uppercase tracking-[0.15em]">Linked Events</p>
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${accent.bg} border ${accent.border} ${accent.text}`}>{personEvents.length}</span>
                </div>
                {personEvents.length === 0 ? (
                  <p className="text-[11px] text-white/20 font-mono text-center py-3">No linked events</p>
                ) : (
                  <div className="space-y-1 max-h-[160px] overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                    {personEvents.map((evt, i) => {
                      const t = (evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000;
                      const label = (evt.display_name ?? evt.event_type ?? '').replace(/_/g, ' ');
                      return (
                        <motion.div
                          key={evt.event_id ?? evt.id ?? i}
                          initial={{ opacity: 0, x: -6 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.02 }}
                          className="flex items-center gap-2 p-1.5 rounded-lg bg-black/20 border border-white/4 hover:border-white/10 transition-all"
                        >
                          <span className={`text-[9px] font-mono ${accent.text} w-9 flex-shrink-0`}>{t.toFixed(1)}s</span>
                          <span className="flex-1 text-[10px] text-white/55 capitalize truncate">{label}</span>
                          <ChevronRight size={10} className="text-white/15" />
                        </motion.div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Tech badge */}
              <div className="p-2.5 rounded-lg bg-black/30 border border-white/5">
                <div className="flex items-center gap-1.5">
                  <BarChart2 size={11} className="text-white/25" />
                  <p className="text-[9px] font-mono text-white/20 uppercase tracking-wider">YOLO11x · ReID · ByteTrack</p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
