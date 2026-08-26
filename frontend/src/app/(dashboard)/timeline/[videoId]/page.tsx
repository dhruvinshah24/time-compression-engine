'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  Loader2, AlertCircle, Clock, Film, Zap,
  User, Armchair, Laptop, Smartphone, Coffee, Book,
  Package, Lightbulb, LightbulbOff, Car, Activity,
  PersonStanding, UserCheck, UserX, Tv,
  Keyboard, Monitor, Camera, ShoppingBag,
  Briefcase, Wallet, Lock, Shield, ChevronDown, ChevronRight,
  Eye, Tag, Layers, Star, TrendingUp, Map,
  BarChart3, Circle, Minus, PlayCircle,
} from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api/client';
import EventPreviewModal from '@/components/EventPreviewModal';


// ── Types ─────────────────────────────────────────────────────────────────────
interface DetectedObject {
  class_name: string;
  display_name: string;
  class_id: number;
  category: string;
  instance_count: number;
  max_confidence: number;
  first_seen_ms: number;
}

interface Person {
  person_label: string;          // "Person 1", "Person 2"
  first_seen_ms: number;
  last_seen_ms: number;
  observation_count: number;
  entry_direction?: string;      // "left", "right", "top", "bottom"
  crop_url?: string;             // URL to JPEG thumbnail
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
  rule_name?: string;
  evidence?: Record<string, unknown>;
  // Phase 7 enriched fields
  person_label?: string;         // "Person 1" set by narrative builder
  crop_url?: string;             // thumbnail URL
  display_name?: string;         // human-readable description
  direction?: string;            // entry/exit direction
}

interface TimelineData {
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
  object_events: EventRecord[];
  // Phase 7 person identity
  persons: Person[];
  unique_persons: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const getEventTime = (e: EventRecord) =>
  (e.start_ms ?? e.timestamp_ms ?? 0) / 1000;

const fmtTime = (s: number) => {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(1);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
};

const getEventType = (e: EventRecord) => e.event_type ?? e.type ?? '';

// ── Object icon map ───────────────────────────────────────────────────────────
// Maps YOLO-World class names to Lucide icons for the object panel
function ObjectIcon({ className, size = 20 }: { className: string; size?: number }) {
  const map: Record<string, React.ElementType> = {
    // People
    person: User, man: User, woman: User, child: User,
    // Furniture
    chair: Armchair, 'office_chair': Armchair, sofa: Armchair, couch: Armchair, bed: Armchair,
    // Electronics
    laptop: Laptop, 'notebook_computer': Laptop, computer: Monitor, monitor: Monitor,
    phone: Smartphone, smartphone: Smartphone, 'mobile_phone': Smartphone, 'cell_phone': Smartphone,
    keyboard: Keyboard, mouse: Keyboard,
    tv: Tv, television: Tv, screen: Monitor, projector: Monitor,
    camera: Camera, webcam: Camera, 'security_camera': Shield, 'cctv_camera': Shield,
    // Books / docs
    book: Book, notebook: Book, document: Book,
    // Drinkware (Coffee = generic cup icon)
    bottle: Coffee, glass: Coffee, 'wine_glass': Coffee, cup: Coffee, mug: Coffee, 'coffee_mug': Coffee,
    // Bags
    backpack: ShoppingBag, handbag: ShoppingBag, bag: ShoppingBag, 'shopping_bag': ShoppingBag,
    briefcase: Briefcase, suitcase: Briefcase,
    // Security / valuables
    wallet: Wallet, purse: Wallet,
    safe: Lock, vault: Lock, 'safe_box': Lock, padlock: Lock,
  };
  const Icon = map[className.toLowerCase()] ?? Package;
  return <Icon size={size} />;
}

// ── Category config ───────────────────────────────────────────────────────────
const CATEGORY_CONFIG: Record<string, { gradient: string; border: string; text: string; badge: string }> = {
  people:      { gradient: 'from-violet-500/25 to-purple-600/10', border: 'border-violet-500/40', text: 'text-violet-300', badge: 'bg-violet-500/20 text-violet-300 border-violet-500/30' },
  furniture:   { gradient: 'from-amber-500/25 to-orange-600/10',  border: 'border-amber-500/40',  text: 'text-amber-300',  badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
  electronics: { gradient: 'from-cyan-500/25 to-sky-600/10',      border: 'border-cyan-500/40',   text: 'text-cyan-300',   badge: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' },
  drinkware:   { gradient: 'from-emerald-500/25 to-green-600/10', border: 'border-emerald-500/40',text: 'text-emerald-300', badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
  documents:   { gradient: 'from-orange-500/25 to-red-600/10',    border: 'border-orange-500/40', text: 'text-orange-300', badge: 'bg-orange-500/20 text-orange-300 border-orange-500/30' },
  bag:         { gradient: 'from-pink-500/25 to-rose-600/10',     border: 'border-pink-500/40',   text: 'text-pink-300',   badge: 'bg-pink-500/20 text-pink-300 border-pink-500/30' },
  stationery:  { gradient: 'from-yellow-500/25 to-amber-600/10',  border: 'border-yellow-500/40', text: 'text-yellow-300', badge: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30' },
  kitchen:     { gradient: 'from-lime-500/25 to-green-600/10',    border: 'border-lime-500/40',   text: 'text-lime-300',   badge: 'bg-lime-500/20 text-lime-300 border-lime-500/30' },
  security:    { gradient: 'from-red-500/25 to-rose-600/10',      border: 'border-red-500/40',    text: 'text-red-300',    badge: 'bg-red-500/20 text-red-300 border-red-500/30' },
  vehicle:     { gradient: 'from-blue-500/25 to-indigo-600/10',   border: 'border-blue-500/40',   text: 'text-blue-300',   badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
  animal:      { gradient: 'from-rose-500/25 to-pink-600/10',     border: 'border-rose-500/40',   text: 'text-rose-300',   badge: 'bg-rose-500/20 text-rose-300 border-rose-500/30' },
  home:        { gradient: 'from-teal-500/25 to-cyan-600/10',     border: 'border-teal-500/40',   text: 'text-teal-300',   badge: 'bg-teal-500/20 text-teal-300 border-teal-500/30' },
  clothing:    { gradient: 'from-fuchsia-500/25 to-purple-600/10',border: 'border-fuchsia-500/40',text: 'text-fuchsia-300',badge: 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500/30' },
  object:      { gradient: 'from-slate-500/25 to-gray-600/10',    border: 'border-slate-500/40',  text: 'text-slate-300',  badge: 'bg-slate-500/20 text-slate-300 border-slate-500/30' },
};
const getCat = (cat: string) => CATEGORY_CONFIG[cat] ?? CATEGORY_CONFIG.object;

// ── Event config ──────────────────────────────────────────────────────────────
interface EventConfig { icon: React.ElementType; label: string; color: string; dotColor: string }
function getEventConfig(eventType: string): EventConfig {
  const map: Record<string, EventConfig> = {
    // Activity
    person_entered_scene:     { icon: UserCheck,      label: 'Person Entered',        color: 'text-green-400',   dotColor: 'bg-green-400' },
    person_left_scene:        { icon: UserX,          label: 'Person Left',           color: 'text-red-400',     dotColor: 'bg-red-400' },
    person_walking:           { icon: Activity,       label: 'Walking',               color: 'text-blue-400',    dotColor: 'bg-blue-400' },
    person_sitting:           { icon: Armchair,       label: 'Sat on Chair',          color: 'text-amber-400',   dotColor: 'bg-amber-400' },
    person_standing:          { icon: PersonStanding, label: 'Standing',              color: 'text-purple-400',  dotColor: 'bg-purple-400' },
    person_standing_up:       { icon: PersonStanding, label: 'Stood Up',              color: 'text-indigo-400',  dotColor: 'bg-indigo-400' },
    person_reaching_up:       { icon: Zap,            label: 'Reached Up',            color: 'text-yellow-400',  dotColor: 'bg-yellow-400' },
    person_loitering:         { icon: Clock,          label: 'Loitering',             color: 'text-orange-400',  dotColor: 'bg-orange-400' },
    person_running:           { icon: Activity,       label: 'Running',               color: 'text-rose-400',    dotColor: 'bg-rose-400' },
    // Lighting
    light_turned_on:          { icon: Lightbulb,      label: 'Light Turned On',       color: 'text-yellow-300',  dotColor: 'bg-yellow-300' },
    light_turned_off:         { icon: LightbulbOff,   label: 'Light Turned Off',      color: 'text-slate-400',   dotColor: 'bg-slate-400' },
    // Interactions — person + object
    person_using_phone:       { icon: Smartphone,     label: 'Using Phone',           color: 'text-cyan-400',    dotColor: 'bg-cyan-400' },
    person_using_laptop:      { icon: Laptop,         label: 'Using Laptop',          color: 'text-sky-400',     dotColor: 'bg-sky-400' },
    person_drinking:          { icon: Coffee,         label: 'Drinking',              color: 'text-emerald-400', dotColor: 'bg-emerald-400' },
    person_reading:           { icon: Book,           label: 'Reading',               color: 'text-orange-400',  dotColor: 'bg-orange-400' },
    person_watching_screen:   { icon: Monitor,        label: 'Watching Screen',       color: 'text-blue-300',    dotColor: 'bg-blue-300' },
    person_pocketed_object:   { icon: Wallet,         label: 'Pocketed Object',       color: 'text-violet-400',  dotColor: 'bg-violet-400' },
    person_near_screen:       { icon: Tv,             label: 'Near Screen',           color: 'text-blue-300',    dotColor: 'bg-blue-300' },
    person_at_desk:           { icon: Monitor,        label: 'At Desk',               color: 'text-teal-400',    dotColor: 'bg-teal-400' },
    vehicle_approaching:      { icon: Car,            label: 'Vehicle Approaching',   color: 'text-blue-400',    dotColor: 'bg-blue-400' },
  };
  // Dynamic pick-up / place events (event_type = person_picked_up_bottle etc.)
  if (eventType.startsWith('person_picked_up_')) {
    const obj = eventType.replace('person_picked_up_', '').replace(/_/g, ' ');
    return { icon: Package, label: `Picked Up ${obj.replace(/\b\w/g, c => c.toUpperCase())}`, color: 'text-fuchsia-400', dotColor: 'bg-fuchsia-400' };
  }
  if (eventType.startsWith('person_placed_')) {
    const obj = eventType.replace('person_placed_', '').replace(/_/g, ' ');
    return { icon: Package, label: `Put Down ${obj.replace(/\b\w/g, c => c.toUpperCase())}`, color: 'text-pink-400', dotColor: 'bg-pink-400' };
  }
  return map[eventType] ?? {
    icon: Minus,
    label: eventType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    color: 'text-slate-400',
    dotColor: 'bg-slate-400',
  };
}

// ── Story Strip ───────────────────────────────────────────────────────────────
function StoryStrip({ events }: { events: EventRecord[] }) {
  const sorted = [...events].sort((a, b) => getEventTime(a) - getEventTime(b));
  const activityTypes = new Set([
    'person_entered_scene','person_left_scene','person_walking','person_sitting',
    'person_standing','person_standing_up','person_reaching_up','person_running',
    'light_turned_on','light_turned_off',
  ]);
  const keyEvents = sorted.filter(e => activityTypes.has(getEventType(e)));

  if (keyEvents.length === 0) return null;

  return (
    <div className="relative overflow-x-auto pb-2">
      <div className="flex items-center gap-0 min-w-max px-2">
        {keyEvents.map((evt, i) => {
          const cfg = getEventConfig(getEventType(evt));
          const Icon = cfg.icon;
          const t = getEventTime(evt);
          return (
            <div key={evt.event_id ?? evt.id ?? i} className="flex items-center gap-0">
              <motion.div
                initial={{ opacity: 0, scale: 0.8, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="flex flex-col items-center gap-1.5 group cursor-default"
              >
                <div className={`
                  w-12 h-12 rounded-2xl flex items-center justify-center
                  bg-white/5 border border-white/10 group-hover:border-white/30
                  group-hover:bg-white/10 transition-all duration-200 ${cfg.color}
                `}>
                  <Icon size={20} />
                </div>
                <span className="text-[10px] text-slate-400 group-hover:text-slate-200 transition-colors text-center leading-tight max-w-[56px]">
                  {fmtTime(t)}
                </span>
                <span className="text-[9px] text-slate-500 group-hover:text-slate-300 transition-colors text-center leading-tight max-w-[64px]">
                  {cfg.label}
                </span>
              </motion.div>
              {i < keyEvents.length - 1 && (
                <div className="flex items-center px-1 mb-6">
                  <div className="h-px w-6 bg-gradient-to-r from-white/20 to-white/5" />
                  <ChevronRight size={10} className="text-white/20 -ml-1" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Confidence Ring ───────────────────────────────────────────────────────────
function ConfidenceRing({ confidence, color }: { confidence: number; color: string }) {
  const pct = Math.round(confidence * 100);
  const r = 18;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;

  return (
    <div className="relative w-12 h-12 flex-shrink-0">
      <svg width="48" height="48" viewBox="0 0 48 48" className="-rotate-90">
        <circle cx="24" cy="24" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
        <circle
          cx="24" cy="24" r={r} fill="none"
          stroke="currentColor" strokeWidth="3"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          className={color}
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white/80">
        {pct}%
      </span>
    </div>
  );
}

// ── Object Card ───────────────────────────────────────────────────────────────
function ObjectCard({ obj, index }: { obj: DetectedObject; index: number }) {
  const cat = getCat(obj.category);
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={`
        relative flex items-center gap-3 p-3.5 rounded-2xl
        bg-gradient-to-br ${cat.gradient} border ${cat.border}
        backdrop-blur-sm hover:scale-[1.02] transition-all duration-200 group
      `}
    >
      {/* Category accent bar */}
      <div className={`absolute left-0 top-3 bottom-3 w-0.5 rounded-full ${cat.border} opacity-60`} />

      <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-black/20 ${cat.text} flex-shrink-0`}>
        <ObjectIcon className={obj.class_name} size={20} />
      </div>

      <div className="flex-1 min-w-0">
        <p className={`text-sm font-semibold ${cat.text} leading-tight truncate`}>
          {obj.display_name}
        </p>
        <p className="text-[11px] text-white/40 mt-0.5 capitalize">{obj.category}</p>
        <div className="flex items-center gap-1 mt-1">
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${cat.badge}`}>
            {fmtTime(obj.first_seen_ms / 1000)}
          </span>
        </div>
      </div>

      <ConfidenceRing confidence={obj.max_confidence} color={cat.text} />
    </motion.div>
  );
}

// ── Event Row ─────────────────────────────────────────────────────────────────
function EventRow({ evt, index, total, durationSeconds, onPreview }: {
  evt: EventRecord; index: number; total: number; durationSeconds: number;
  onPreview?: (eventId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const cfg = getEventConfig(getEventType(evt));
  const Icon = cfg.icon;
  const t = getEventTime(evt);
  const conf = evt.confidence ?? 0;
  const src = evt.rule_name ?? '';
  const evidence = evt.evidence ?? {};
  const hasEvidence = Object.keys(evidence).length > 0;
  const personLabel = evt.person_label || (evidence.person_label as string) || null;
  const cropUrl     = evt.crop_url || (evidence.crop_url as string) || null;
  const displayName = evt.display_name || (evidence.description as string) || null;
  const direction   = evt.direction || (evidence.direction as string) || (evidence.entry_direction as string) || null;
  const eventId     = evt.event_id ?? evt.id;

  // Person color palette: stable color per person number
  const PERSON_COLORS = [
    'bg-violet-500/20 text-violet-300 border-violet-500/30',
    'bg-blue-500/20 text-blue-300 border-blue-500/30',
    'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    'bg-orange-500/20 text-orange-300 border-orange-500/30',
    'bg-pink-500/20 text-pink-300 border-pink-500/30',
    'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  ];
  const personColorIdx = personLabel
    ? (parseInt(personLabel.replace(/\D/g, '') || '1') - 1) % PERSON_COLORS.length
    : 0;
  const personColor = PERSON_COLORS[personColorIdx];

  const DIRECTION_ARROWS: Record<string, string> = {
    left: '←', right: '→', top: '↑', bottom: '↓',
  };

  // Timeline position indicator
  const pct = durationSeconds > 0 ? Math.min((t / durationSeconds) * 100, 100) : 0;

  const srcLabel: Record<string, string> = {
    activity_state_machine: 'State Machine',
    brightness_analysis:    'Brightness AI',
    pose_estimation:        'Pose AI',
    rule_object_appeared:   'Object Rules',
    rule_object_disappeared:'Object Rules',
    narrative_builder:      'ReID + Activity',
    interaction_detector:   'Interaction AI',
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      className="relative"
    >
      {/* Timeline spine connector */}
      {index < total - 1 && (
        <div className="absolute left-[19px] top-[52px] bottom-0 w-px bg-gradient-to-b from-white/15 to-transparent z-0" />
      )}

      <div
        className={`
          relative z-10 flex items-start gap-3 p-3.5 rounded-2xl
          bg-white/[0.03] border border-white/[0.07] hover:bg-white/[0.06]
          hover:border-white/15 transition-all duration-200 cursor-pointer
          ${expanded ? 'bg-white/[0.06] border-white/15' : ''}
        `}
        onClick={() => hasEvidence && setExpanded(x => !x)}
      >
        {/* Icon dot */}
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-black/30 flex-shrink-0 ${cfg.color}`}>
          <Icon size={18} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Person label badge with color */}
            {personLabel && (
              <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium flex items-center gap-1 ${personColor}`}>
                <User size={9} />
                {personLabel}
                {direction && <span className="opacity-70">{DIRECTION_ARROWS[direction] || ''}</span>}
              </span>
            )}
            {/* Display name (narrative description) or fallback to event type label */}
            <span className="text-sm font-semibold text-white/90">
              {displayName || cfg.label}
            </span>
            <span className="text-xs text-white/30">·</span>
            <span className="text-xs text-white/50 font-mono">{fmtTime(t)}</span>
            {srcLabel[src] && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-white/40">
                {srcLabel[src]}
              </span>
            )}
          </div>

          {/* Mini timeline bar */}
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${cfg.dotColor} opacity-60`}
                style={{ width: `${pct}%` }}
              />
              <div
                className={`h-full w-1.5 rounded-full ${cfg.dotColor} -mt-1`}
                style={{ marginLeft: `calc(${pct}% - 3px)`, position: 'relative', top: '-4px' }}
              />
            </div>
            <span className="text-[10px] text-white/30 font-mono flex-shrink-0">{pct.toFixed(0)}%</span>
          </div>

          {/* Confidence */}
          <div className="mt-1.5 flex items-center gap-2">
            <div className="flex-1 h-0.5 bg-white/5 rounded-full overflow-hidden">
              <div
                className={`h-full ${cfg.dotColor} opacity-70`}
                style={{ width: `${Math.round(conf * 100)}%` }}
              />
            </div>
            <span className="text-[10px] text-white/30">{Math.round(conf * 100)}% conf</span>
          </div>
        </div>

        {hasEvidence && (
          <div className="text-white/30 mt-1 flex-shrink-0">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </div>
        )}
        {/* Preview button — opens before/event/after modal */}
        {eventId && onPreview && (
          <button
            onClick={e => { e.stopPropagation(); onPreview(eventId); }}
            className="ml-1 p-1.5 rounded-lg hover:bg-indigo-500/20 text-white/20 hover:text-indigo-400 transition-all flex-shrink-0"
            title="Preview event frames"
          >
            <PlayCircle size={14} />
          </button>
        )}
      </div>

      {/* Evidence panel */}
      <AnimatePresence>
        {expanded && hasEvidence && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="ml-12 mr-0 mt-1 mb-1 p-3 rounded-xl bg-black/20 border border-white/5">
              <p className="text-[10px] text-white/30 uppercase tracking-widest mb-2">Evidence</p>
              <div className="grid grid-cols-2 gap-1.5">
                {Object.entries(evidence).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between gap-2">
                    <span className="text-[10px] text-white/40 capitalize">{k.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] text-white/70 font-mono">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Category Section ──────────────────────────────────────────────────────────
function CategorySection({
  title, events, icon: Icon, color, defaultOpen, durationSeconds, onPreview,
}: {
  title: string; events: EventRecord[]; icon: React.ElementType;
  color: string; defaultOpen?: boolean; durationSeconds: number;
  onPreview?: (eventId: string) => void;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const sorted = [...events].sort((a, b) => getEventTime(a) - getEventTime(b));

  if (events.length === 0) return null;

  return (
    <div className="rounded-2xl border border-white/[0.08] overflow-hidden">
      <button
        onClick={() => setOpen(x => !x)}
        className="w-full flex items-center gap-3 p-4 hover:bg-white/[0.04] transition-colors"
      >
        <div className={`w-8 h-8 rounded-xl flex items-center justify-center bg-black/20 ${color}`}>
          <Icon size={16} />
        </div>
        <span className="text-sm font-semibold text-white/80 flex-1 text-left">{title}</span>
        <span className={`text-xs px-2.5 py-0.5 rounded-full bg-white/5 border border-white/10 ${color}`}>
          {events.length}
        </span>
        <div className={`text-white/30 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>
          <ChevronDown size={16} />
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 flex flex-col gap-2">
              {sorted.map((evt, i) => (
                <EventRow
                  key={evt.event_id ?? evt.id ?? i}
                  evt={evt} index={i} total={sorted.length}
                  durationSeconds={durationSeconds}
                  onPreview={onPreview}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: React.ElementType; color: string }) {
  return (
    <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-white/[0.03] border border-white/[0.07]">
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center bg-black/20 ${color}`}>
        <Icon size={16} />
      </div>
      <div>
        <p className="text-lg font-bold text-white leading-none">{value}</p>
        <p className="text-[11px] text-white/40 mt-0.5">{label}</p>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function TimelinePage() {
  const { videoId } = useParams<{ videoId: string }>();
  const [data, setData] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [objectSearch, setObjectSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [previewEventId, setPreviewEventId] = useState<string | null>(null);

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

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-[#08080f]">
      <div className="flex flex-col items-center gap-4">
        <div className="relative w-16 h-16">
          <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20" />
          <div className="absolute inset-0 rounded-full border-2 border-t-indigo-500 animate-spin" />
          <div className="absolute inset-2 rounded-full border-2 border-t-violet-500 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '0.8s' }} />
        </div>
        <p className="text-white/40 text-sm animate-pulse">Loading timeline intelligence…</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-[#08080f]">
      <div className="flex flex-col items-center gap-4 text-center p-8 max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <AlertCircle size={28} className="text-red-400" />
        </div>
        <h2 className="text-xl font-bold text-white">Timeline Error</h2>
        <p className="text-white/50 text-sm">{error}</p>
        <Link href="/" className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white/70 hover:bg-white/10 transition-colors">
          ← Back to Dashboard
        </Link>
      </div>
    </div>
  );

  if (!data) return (
    <div className="min-h-screen flex items-center justify-center bg-[#08080f]">
      <div className="flex flex-col items-center gap-4 text-center p-8 max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
          <Clock size={28} className="text-white/40" />
        </div>
        <h2 className="text-xl font-bold text-white">No Timeline Data</h2>
        <p className="text-white/50 text-sm">This video has not been processed yet, or no events were detected.</p>
        <Link href="/" className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white/70 hover:bg-white/10 transition-colors">
          ← Back to Dashboard
        </Link>
      </div>
    </div>
  );

  const durationSeconds = data.metadata?.duration_seconds ?? 0;
  const allEvents = [...data.events].sort((a, b) => getEventTime(a) - getEventTime(b));

  // BUG-08 FIX: Use Set-based ID comparison instead of Array.includes() reference equality.
  // API returns new array instances from JSON parsing — reference equality always fails,
  // causing every event to land in otherEvts and render in multiple sections.
  const activityEvts = data.activity_events?.length ? data.activity_events
    : allEvents.filter(e => ['person_entered_scene','person_left_scene','person_walking',
      'person_sitting','person_standing','person_standing_up','person_reaching_up',
      'person_running','person_loitering'].includes(getEventType(e)));

  const lightingEvts = data.lighting_events?.length ? data.lighting_events
    : allEvents.filter(e => ['light_turned_on','light_turned_off'].includes(getEventType(e)));

  const interactionEvts = data.interaction_events?.length ? data.interaction_events
    : allEvents.filter(e => {
        const t = getEventType(e);
        return t.startsWith('person_using_') || t.startsWith('person_picked_up_')
          || t.startsWith('person_placed_') || t.startsWith('person_pocketed_')
          || t.startsWith('person_near_') || t.includes('watching_') || t === 'person_drinking'
          || t === 'person_reading' || t === 'person_at_desk';
      });

  const vehicleEvts = data.vehicle_events?.length ? data.vehicle_events
    : allEvents.filter(e => getEventType(e).startsWith('vehicle_'));

  // Build ID sets for deduplication
  const categorisedIds = new Set([
    ...activityEvts, ...lightingEvts, ...interactionEvts, ...vehicleEvts,
  ].map(e => e.event_id ?? e.id));

  const otherEvts = allEvents.filter(e => !categorisedIds.has(e.event_id ?? e.id));

  // Filtered objects
  const categories = Array.from(new Set(data.detected_objects.map(o => o.category)));
  const filteredObjects = data.detected_objects.filter(o => {
    const matchSearch = o.display_name.toLowerCase().includes(objectSearch.toLowerCase()) ||
      o.category.toLowerCase().includes(objectSearch.toLowerCase());
    const matchCat = !selectedCategory || o.category === selectedCategory;
    return matchSearch && matchCat;
  });

  return (
    <>
    <div className="min-h-screen bg-[#08080f] text-white">
      {/* Background glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-indigo-600/8 rounded-full blur-3xl" />
        <div className="absolute top-1/3 -right-40 w-80 h-80 bg-violet-600/8 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-1/3 w-72 h-72 bg-cyan-600/5 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-6xl mx-auto px-4 py-8 space-y-8">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Link href="/" className="text-white/30 hover:text-white/60 transition-colors text-sm">Dashboard</Link>
              <ChevronRight size={12} className="text-white/20" />
              <span className="text-white/50 text-sm">Timeline</span>
            </div>
            <h1 className="text-2xl font-bold text-white">
              {data.filename?.replace('original.mp4', 'Video Analysis') ?? 'Video Timeline'}
            </h1>
            <p className="text-white/40 text-sm mt-1 font-mono">{videoId}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1.5 rounded-xl text-xs font-semibold border ${
              data.job_status === 'completed'
                ? 'bg-green-500/10 border-green-500/30 text-green-400'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
            }`}>
              {data.job_status ?? 'completed'}
            </span>
          </div>
        </div>

        {/* ── Stats Row ───────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Events Detected" value={data.event_count} icon={Zap} color="text-indigo-400" />
          <StatCard label="Persons Identified" value={data.unique_persons ?? 0} icon={UserCheck} color="text-violet-400" />
          <StatCard label="Duration" value={data.metadata?.duration_hms ?? '—'} icon={Clock} color="text-cyan-400" />
          <StatCard label="Objects Found" value={data.detected_objects.length} icon={Eye} color="text-emerald-400" />
        </div>

        {/* ── Persons Detected Panel ──────────────────────────────────────── */}
        {data.persons && data.persons.length > 0 && (
          <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.08]">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
                <User size={14} className="text-violet-400" />
              </div>
              <h2 className="text-sm font-semibold text-white/80">People Detected</h2>
              <span className="text-[10px] text-white/30 ml-1">— persistent identity tracking</span>
            </div>
            <div className="flex flex-wrap gap-3">
              {data.persons.map((person, idx) => {
                const PERSON_COLORS_BG = [
                  'border-violet-500/30 bg-violet-500/10',
                  'border-blue-500/30 bg-blue-500/10',
                  'border-emerald-500/30 bg-emerald-500/10',
                  'border-orange-500/30 bg-orange-500/10',
                  'border-pink-500/30 bg-pink-500/10',
                  'border-cyan-500/30 bg-cyan-500/10',
                ];
                const PERSON_COLORS_TEXT = [
                  'text-violet-300', 'text-blue-300', 'text-emerald-300',
                  'text-orange-300', 'text-pink-300', 'text-cyan-300',
                ];
                const colorBg   = PERSON_COLORS_BG[idx % PERSON_COLORS_BG.length];
                const colorText = PERSON_COLORS_TEXT[idx % PERSON_COLORS_TEXT.length];
                const DIRECTION_ARROWS: Record<string, string> = {
                  left: '← from left', right: 'from right →',
                  top: '↑ from top', bottom: '↓ from bottom',
                };
                const durationSec = ((person.last_seen_ms - person.first_seen_ms) / 1000).toFixed(0);
                return (
                  <motion.div
                    key={person.person_label}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: idx * 0.08 }}
                    className={`flex items-center gap-3 px-4 py-3 rounded-2xl border ${colorBg}`}
                  >
                    {/* Thumbnail or avatar */}
                    <div className="w-12 h-16 rounded-xl overflow-hidden bg-white/5 border border-white/10 flex-shrink-0 flex items-center justify-center">
                      {person.crop_url ? (
                        <img
                          src={`http://localhost:8000/api/v1${person.crop_url}`}
                          alt={person.person_label}
                          className="w-full h-full object-cover"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                        />
                      ) : (
                        <User size={20} className={colorText} />
                      )}
                    </div>
                    <div>
                      <p className={`text-sm font-bold ${colorText}`}>{person.person_label}</p>
                      {person.entry_direction && (
                        <p className="text-[10px] text-white/40 mt-0.5">
                          {DIRECTION_ARROWS[person.entry_direction] || person.entry_direction}
                        </p>
                      )}
                      <p className="text-[10px] text-white/30 mt-0.5">
                        Seen for {durationSec}s
                      </p>
                      <p className="text-[10px] text-white/25">
                        {person.observation_count} frames
                      </p>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Activity Story Strip ────────────────────────────────────────── */}
        <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.08] backdrop-blur-sm">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
              <Map size={14} className="text-indigo-400" />
            </div>
            <h2 className="text-sm font-semibold text-white/80">Activity Story</h2>
            <span className="text-[10px] text-white/30 ml-1">— chronological narrative</span>
          </div>
          {allEvents.length > 0
            ? <StoryStrip events={allEvents} />
            : <p className="text-white/30 text-sm text-center py-4">No events detected</p>
          }
        </div>

        {/* ── Main Content: Objects + Events ──────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">

          {/* Events column */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 size={16} className="text-white/40" />
              <h2 className="text-sm font-semibold text-white/60 uppercase tracking-wider">Event Log</h2>
            </div>

            <CategorySection
              title="Activity & Motion"
              events={activityEvts}
              icon={Activity}
              color="text-indigo-400"
              defaultOpen={true}
              durationSeconds={durationSeconds}
              onPreview={setPreviewEventId}
            />
            <CategorySection
              title="Lighting Changes"
              events={lightingEvts}
              icon={Lightbulb}
              color="text-yellow-400"
              defaultOpen={lightingEvts.length > 0}
              durationSeconds={durationSeconds}
              onPreview={setPreviewEventId}
            />
            <CategorySection
              title="Object Interactions"
              events={interactionEvts}
              icon={Package}
              color="text-fuchsia-400"
              defaultOpen={interactionEvts.length > 0}
              durationSeconds={durationSeconds}
              onPreview={setPreviewEventId}
            />
            {otherEvts.length > 0 && (
              <CategorySection
                title="Other Events"
                events={otherEvts}
                icon={Star}
                color="text-slate-400"
                defaultOpen={false}
                durationSeconds={durationSeconds}
                onPreview={setPreviewEventId}
              />
            )}

            {data.event_count === 0 && (
              <div className="flex flex-col items-center gap-3 py-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                  <AlertCircle size={24} className="text-white/20" />
                </div>
                <p className="text-white/30 text-sm">No events detected in this video</p>
              </div>
            )}
          </div>

          {/* Objects column */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <Tag size={16} className="text-white/40" />
              <h2 className="text-sm font-semibold text-white/60 uppercase tracking-wider">
                Detected Objects
              </h2>
              <span className="ml-auto text-xs text-white/30">{data.detected_objects.length} found</span>
            </div>

            {/* Search */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search objects…"
                value={objectSearch}
                onChange={e => setObjectSearch(e.target.value)}
                className="w-full px-4 py-2.5 pl-9 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-white/80 placeholder-white/20 focus:outline-none focus:border-white/20 transition-colors"
              />
              <Eye size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/25" />
            </div>

            {/* Category filter pills */}
            {categories.length > 1 && (
              <div className="flex flex-wrap gap-1.5">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                    !selectedCategory
                      ? 'bg-white/10 border-white/20 text-white'
                      : 'bg-transparent border-white/10 text-white/40 hover:border-white/20'
                  }`}
                >
                  All
                </button>
                {categories.map(cat => {
                  const cfg = getCat(cat);
                  return (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                      className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors capitalize ${
                        selectedCategory === cat ? cfg.badge : 'bg-transparent border-white/10 text-white/40 hover:border-white/20'
                      }`}
                    >
                      {cat}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Object cards */}
            <div className="space-y-2.5">
              {filteredObjects.map((obj, i) => (
                <ObjectCard key={obj.class_name} obj={obj} index={i} />
              ))}
              {filteredObjects.length === 0 && (
                <p className="text-white/25 text-sm text-center py-6">
                  {objectSearch ? 'No objects match your search' : 'No objects detected'}
                </p>
              )}
            </div>

            {/* Model info badge */}
            <div className="flex items-center gap-2 p-3 rounded-xl bg-indigo-500/5 border border-indigo-500/15 mt-4">
              <TrendingUp size={13} className="text-indigo-400 flex-shrink-0" />
              <p className="text-[11px] text-indigo-300/70">
                YOLO11x detection · Quality analyzer · Low-light preprocessing · ROI zone detection
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-center gap-2 py-4 border-t border-white/5">
          <Circle size={6} className="text-indigo-500 fill-indigo-500" />
          <p className="text-xs text-white/20">Time Compression Engine · AI-powered video intelligence</p>
        </div>

      </div>
    </div>

    {/* Event Preview Modal */}
    {previewEventId && (
      <EventPreviewModal
        eventId={previewEventId}
        onClose={() => setPreviewEventId(null)}
      />
    )}
    </>
  );
}
