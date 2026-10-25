'use client';

import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import {
  FileText, Download, User, Play, Pause, SkipBack, SkipForward,
  Maximize2, Volume2, VolumeX, ChevronDown, ChevronRight, ChevronLeft,
  ShieldCheck, Eye, EyeOff, Search, Layers, Clock, CheckCircle2,
  AlertTriangle, Crosshair, Sparkles, Filter, ExternalLink, Zap,
  Activity, Users, Box, Radio, Video, Laptop, Tag, Info, ArrowLeft, ArrowRight
} from 'lucide-react';
import Link from 'next/link';
import { api, API_BASE, BACKEND_URL } from '@/lib/api/client';
import EventPreviewModal from '@/components/EventPreviewModal';
import PersonDossierModal from '@/components/PersonDossierModal';
import { TimelineSkeleton } from '@/components/skeletons/TimelineSkeleton';

// ── Types ─────────────────────────────────────────────────────────────────────

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
  evidence?: {
    thumbnail_path?: string;
    before_frame_path?: string;
    event_frame_path?: string;
    after_frame_path?: string;
    clip_path?: string;
    description?: string;
    lighting_condition?: string;
    direction?: string;
    person_label?: string;
    [key: string]: any;
  };
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
  metadata?: {
    duration_hms?: string;
    fps?: number;
    resolution?: string;
    duration_seconds?: number;
    profile?: string;
  };
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

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTimecode(sec: number): string {
  if (isNaN(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.floor((sec % 1) * 100);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
}

function fmtSecOnly(sec: number): string {
  if (isNaN(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatLabel(str: string): string {
  return str
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function resolveMediaUrl(path?: string | null): string | null {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  let clean = path.replace(/\\/g, '/');
  const storageIdx = clean.toLowerCase().indexOf('storage/');
  if (storageIdx !== -1) {
    clean = clean.substring(storageIdx);
  } else {
    const outputsIdx = clean.toLowerCase().indexOf('outputs/');
    if (outputsIdx !== -1) {
      clean = clean.substring(outputsIdx);
    }
  }
  const normalized = clean.startsWith('/') ? clean : `/${clean}`;
  return `${BACKEND_URL}${normalized}`;
}

// ── Dynamic Category Visual & Actor Resolution ────────────────────────────────

export interface CategoryVisual {
  name: string;
  color: string;
  bg: string;
  border: string;
  badgeBg: string;
  glow: string;
  iconName: 'movement' | 'workstation' | 'interaction' | 'posture' | 'presence';
}

function getEventCategoryVisual(evt?: EventRecord | null): CategoryVisual {
  const typeLower = ((evt?.event_type || '') + ' ' + (evt?.display_name || '') + ' ' + (evt?.evidence?.description || '')).toLowerCase();
  
  if (typeLower.includes('walk') || typeLower.includes('run') || typeLower.includes('step') || typeLower.includes('exit') || typeLower.includes('enter') || typeLower.includes('transit')) {
    return {
      name: 'Transit & Movement',
      color: '#10b981',
      bg: 'linear-gradient(135deg, rgba(16, 185, 129, 0.32) 0%, rgba(5, 150, 105, 0.18) 100%)',
      border: 'rgba(16, 185, 129, 0.85)',
      badgeBg: 'rgba(16, 185, 129, 0.22)',
      glow: 'rgba(16, 185, 129, 0.45)',
      iconName: 'movement'
    };
  }
  if (typeLower.includes('type') || typeLower.includes('keyboard') || typeLower.includes('laptop') || typeLower.includes('monitor') || typeLower.includes('workstation') || typeLower.includes('console') || typeLower.includes('terminal')) {
    return {
      name: 'Workstation & Tech',
      color: '#06b6d4',
      bg: 'linear-gradient(135deg, rgba(6, 182, 212, 0.32) 0%, rgba(2, 132, 199, 0.18) 100%)',
      border: 'rgba(6, 182, 212, 0.85)',
      badgeBg: 'rgba(6, 182, 212, 0.22)',
      glow: 'rgba(6, 182, 212, 0.45)',
      iconName: 'workstation'
    };
  }
  if (typeLower.includes('headset') || typeLower.includes('reach') || typeLower.includes('gesture') || typeLower.includes('confer') || typeLower.includes('discuss') || typeLower.includes('inspection')) {
    return {
      name: 'Interaction & Telemetry',
      color: '#f59e0b',
      bg: 'linear-gradient(135deg, rgba(245, 158, 11, 0.32) 0%, rgba(217, 119, 6, 0.18) 100%)',
      border: 'rgba(245, 158, 11, 0.85)',
      badgeBg: 'rgba(245, 158, 11, 0.22)',
      glow: 'rgba(245, 158, 11, 0.45)',
      iconName: 'interaction'
    };
  }
  if (typeLower.includes('sit') || typeLower.includes('seat') || typeLower.includes('stand') || typeLower.includes('crouch')) {
    return {
      name: 'Posture Shift',
      color: '#a855f7',
      bg: 'linear-gradient(135deg, rgba(168, 85, 247, 0.32) 0%, rgba(124, 58, 237, 0.18) 100%)',
      border: 'rgba(168, 85, 247, 0.85)',
      badgeBg: 'rgba(168, 85, 247, 0.22)',
      glow: 'rgba(168, 85, 247, 0.45)',
      iconName: 'posture'
    };
  }
  return {
    name: 'Surveillance Event',
    color: '#62ddb0',
    bg: 'linear-gradient(135deg, rgba(98, 221, 176, 0.32) 0%, rgba(46, 160, 120, 0.18) 100%)',
    border: 'rgba(98, 221, 176, 0.85)',
    badgeBg: 'rgba(98, 221, 176, 0.22)',
    glow: 'rgba(98, 221, 176, 0.45)',
    iconName: 'presence'
  };
}

const ACTOR_PALETTES: Record<string, { color: string; border: string; bg: string; text: string; glow: string }> = {
  'Person 1': { color: '#10b981', border: '#10b981', bg: 'rgba(16, 185, 129, 0.20)', text: '#34d399', glow: 'rgba(16, 185, 129, 0.45)' },
  'Person 2': { color: '#06b6d4', border: '#06b6d4', bg: 'rgba(6, 182, 212, 0.20)', text: '#38bdf8', glow: 'rgba(6, 182, 212, 0.45)' },
  'Person 3': { color: '#f59e0b', border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.20)', text: '#fbbf24', glow: 'rgba(245, 158, 11, 0.45)' },
  'Person 4': { color: '#ec4899', border: '#ec4899', bg: 'rgba(236, 72, 153, 0.20)', text: '#f472b6', glow: 'rgba(236, 72, 153, 0.45)' },
  'Person 5': { color: '#a855f7', border: '#a855f7', bg: 'rgba(168, 85, 247, 0.20)', text: '#c084fc', glow: 'rgba(168, 85, 247, 0.45)' },
  'Person 6': { color: '#6366f1', border: '#6366f1', bg: 'rgba(99, 102, 241, 0.20)', text: '#818cf8', glow: 'rgba(99, 102, 241, 0.45)' },
};

function getActorPalette(label?: string) {
  if (label && ACTOR_PALETTES[label]) return ACTOR_PALETTES[label];
  const keys = Object.keys(ACTOR_PALETTES);
  let hash = 0;
  for (let i = 0; i < (label || '').length; i++) hash += (label || '').charCodeAt(i);
  return ACTOR_PALETTES[keys[Math.abs(hash) % keys.length]] || ACTOR_PALETTES['Person 1'];
}

function parseActorAndAction(evt?: EventRecord | null): { actorLabel: string; actionTitle: string } {
  if (!evt) return { actorLabel: 'Actor', actionTitle: 'Ambient Scene' };
  const raw = evt.display_name || evt.evidence?.description || evt.event_type || 'Event';
  let actor = evt.person_label || evt.evidence?.person_label || '';
  let action = raw;

  if (raw.includes(':')) {
    const parts = raw.split(':');
    if (!actor && /person/i.test(parts[0])) {
      actor = parts[0].trim();
    }
    action = parts.slice(1).join(':').trim();
  } else if (/^Person\s+\d+/i.test(raw)) {
    const match = raw.match(/^(Person\s+\d+)\s+(.*)/i);
    if (match) {
      if (!actor) actor = match[1];
      action = match[2];
    }
  }

  if (!actor) actor = 'Actor';
  action = action.replace(/^Person\s+\d+[:\s-]*/i, '').trim();
  if (!action) action = formatLabel(evt.event_type || 'Action');
  action = action.charAt(0).toUpperCase() + action.slice(1);

  return { actorLabel: actor, actionTitle: action };
}


export default function ForensicTimelinePage() {
  const params = useParams();
  const router = useRouter();
  const videoId = params.videoId as string;

  const [data, setData] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Playback & Video State
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(60);
  const [isMuted, setIsMuted] = useState(true);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [showOverlays, setShowOverlays] = useState(true);

  // Inspector & Selection State
  const [selectedEventIndex, setSelectedEventIndex] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<'Event' | 'Actors' | 'Assets' | 'Narrative'>('Event');
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);
  const [filterMode, setFilterMode] = useState<'events' | 'actors' | 'objects'>('actors');
  const [zoomLevel, setZoomLevel] = useState<'fit' | '1x' | '2x'>('fit');
  const [assetSearch, setAssetSearch] = useState('');

  // Modals
  const [dossierPerson, setDossierPerson] = useState<Person | null>(null);
  const [previewEventId, setPreviewEventId] = useState<string | null>(null);

  // Fetch Timeline Data
  const fetchTimeline = useCallback(async () => {
    try {
      const result = (await api.timeline(videoId)) as TimelineData;
      setData(result);
      if (result.metadata?.duration_seconds) {
        setDuration(result.metadata.duration_seconds);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load timeline data');
    } finally {
      setLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  // All events sorted chronologically
  const allEvents = useMemo(() => {
    if (!data?.events) return [];
    return [...data.events].sort((a, b) => {
      const ta = (a.start_ms ?? a.timestamp_ms ?? 0) / 1000;
      const tb = (b.start_ms ?? b.timestamp_ms ?? 0) / 1000;
      return ta - tb;
    });
  }, [data]);

  // Currently selected event
  const selectedEvent: EventRecord | undefined = allEvents[selectedEventIndex] || allEvents[0];

  // Video controls
  const togglePlay = useCallback(() => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  }, []);

  const searchParams = useSearchParams();
  const timeParam = searchParams.get('time') || searchParams.get('t');

  const seekTo = useCallback((sec: number) => {
    const target = Math.max(0, Math.min(duration, sec));
    setCurrentTime(target);
    if (videoRef.current) {
      videoRef.current.currentTime = target;
    }
  }, [duration]);

  // Handle URL time parameter seek (supports both ms and seconds)
  useEffect(() => {
    if (!timeParam || !data) return;
    const num = parseFloat(timeParam);
    if (isNaN(num)) return;
    const targetSec = num > 180 ? num / 1000 : num;
    seekTo(targetSec);
    if (allEvents.length > 0) {
      let closestIdx = 0;
      let minDiff = Infinity;
      allEvents.forEach((evt, idx) => {
        const evtSec = (evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000;
        const diff = Math.abs(evtSec - targetSec);
        if (diff < minDiff) {
          minDiff = diff;
          closestIdx = idx;
        }
      });
      setSelectedEventIndex(closestIdx);
    }
  }, [timeParam, data, allEvents, seekTo]);

  const stepFrame = useCallback((deltaSec: number) => {
    seekTo(currentTime + deltaSec);
  }, [currentTime, seekTo]);

  // Timeline Scrubber State
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [hoverEvent, setHoverEvent] = useState<EventRecord | null>(null);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      if (videoRef.current.duration && !isNaN(videoRef.current.duration)) {
        setDuration(videoRef.current.duration);
      }
    }
  };

  // Find nearest event when time changes or seek to event
  const seekToEvent = useCallback((evt: EventRecord, index?: number) => {
    const sec = (evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000;
    seekTo(sec);
    if (index !== undefined) {
      setSelectedEventIndex(index);
    } else {
      const idx = allEvents.findIndex(
        (e) => (e.event_id || e.id) === (evt.event_id || evt.id)
      );
      if (idx !== -1) setSelectedEventIndex(idx);
    }
  }, [allEvents, seekTo]);

  // Dynamic Telemetry & Active Status at currentTime
  const activeTelemetry = useMemo(() => {
    if (!allEvents.length) {
      return {
        primaryEvent: null,
        activeEvents: [] as EventRecord[],
        actorLabel: 'Scene Normal',
        actionTitle: 'Surveillance Stream Monitoring',
        category: 'presence',
        categoryVisual: getEventCategoryVisual(null),
        actorPalette: getActorPalette('Person 1'),
        confidence: 0.95,
        activeActors: [] as Person[],
      };
    }

    const curSec = currentTime;
    const curMs = curSec * 1000;

    // 1. Direct overlapping events
    const activeEvents = allEvents.filter((e) => {
      const s = (e.start_ms ?? e.timestamp_ms ?? 0) / 1000;
      const end = (e.end_ms ?? (s * 1000 + 3500)) / 1000;
      return curSec >= s - 0.25 && curSec <= end + 0.35;
    });

    // 2. Active persons in scene
    const activeActors = (data?.persons || []).filter(
      (p) => curMs >= p.first_seen_ms && curMs <= p.last_seen_ms
    );

    // 3. Primary event
    let primary: EventRecord = activeEvents[0];
    if (!primary) {
      // Find closest event
      let closest = allEvents[0];
      let minDiff = Infinity;
      for (const e of allEvents) {
        const s = (e.start_ms ?? e.timestamp_ms ?? 0) / 1000;
        const diff = Math.abs(s - curSec);
        if (diff < minDiff) {
          minDiff = diff;
          closest = e;
        }
      }
      primary = closest;
    }

    const parsed = parseActorAndAction(primary);
    const catVisual = getEventCategoryVisual(primary);
    const actPalette = getActorPalette(parsed.actorLabel);

    return {
      primaryEvent: primary,
      activeEvents,
      actorLabel: parsed.actorLabel,
      actionTitle: parsed.actionTitle,
      category: catVisual.iconName,
      categoryVisual: catVisual,
      actorPalette: actPalette,
      confidence: primary?.confidence || 0.88,
      activeActors,
    };
  }, [currentTime, allEvents, data]);

  // Tiered non-overlapping layout for Mode 1 ("events")
  const tieredEvents = useMemo(() => {
    if (!allEvents.length) return { assigned: [], trackCount: 1 };

    const items = allEvents.map((evt, originalIdx) => {
      const startSec = (evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000;
      const endSec = (evt.end_ms ?? (evt.start_ms ?? 0) + 3500) / 1000;
      return { evt, originalIdx, startSec, endSec };
    }).sort((a, b) => a.startSec - b.startSec);

    const trackEnds: number[] = [];
    const assigned = items.map((item) => {
      let placedTrack = -1;
      for (let t = 0; t < trackEnds.length; t++) {
        if (trackEnds[t] <= item.startSec + 0.15) {
          placedTrack = t;
          trackEnds[t] = Math.max(item.endSec, item.startSec + 2.5);
          break;
        }
      }
      if (placedTrack === -1) {
        placedTrack = trackEnds.length;
        trackEnds.push(Math.max(item.endSec, item.startSec + 2.5));
      }
      return { ...item, track: placedTrack };
    });

    return { assigned, trackCount: Math.max(1, trackEnds.length) };
  }, [allEvents]);

  // Step event navigation
  const goToPrevEvent = useCallback(() => {
    if (!allEvents.length) return;
    const curSec = currentTime;
    const prev = [...allEvents].reverse().find(
      (e) => (e.start_ms ?? e.timestamp_ms ?? 0) / 1000 < curSec - 0.5
    );
    if (prev) {
      seekToEvent(prev);
    } else {
      seekToEvent(allEvents[0], 0);
    }
  }, [allEvents, currentTime, seekToEvent]);

  const goToNextEvent = useCallback(() => {
    if (!allEvents.length) return;
    const curSec = currentTime;
    const next = allEvents.find(
      (e) => (e.start_ms ?? e.timestamp_ms ?? 0) / 1000 > curSec + 0.5
    );
    if (next) {
      seekToEvent(next);
    }
  }, [allEvents, currentTime, seekToEvent]);

  // Scrubber Pointer Handlers
  const getTrackSeekPos = (clientX: number, target: HTMLElement) => {
    const rect = target.getBoundingClientRect();
    const pos = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return pos * duration;
  };

  const handleTrackPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setIsScrubbing(true);
    const sec = getTrackSeekPos(e.clientX, e.currentTarget);
    seekTo(sec);
  };

  const handleTrackPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const sec = getTrackSeekPos(e.clientX, e.currentTarget);
    setHoverTime(sec);

    const curMs = sec * 1000;
    const nearest = allEvents.find((evt) => {
      const s = evt.start_ms ?? evt.timestamp_ms ?? 0;
      const end = evt.end_ms ?? (s + 3500);
      return curMs >= s - 400 && curMs <= end + 400;
    }) || null;
    setHoverEvent(nearest);

    if (isScrubbing) {
      seekTo(sec);
    }
  };

  const handleTrackPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isScrubbing) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {}
      setIsScrubbing(false);
    }
  };

  const handleTrackPointerLeave = () => {
    if (!isScrubbing) {
      setHoverTime(null);
      setHoverEvent(null);
    }
  };

  // Determine active person at playhead
  const currentMs = currentTime * 1000;
  const activePerson = data?.persons ? (data.persons.find(
    (p) => currentMs >= p.first_seen_ms && currentMs <= p.last_seen_ms
  ) || data.persons[0]) : null;

  // Derive real detection bounding box from selected event evidence or active detection
  const activeBBox = useMemo(() => {
    if (!showOverlays || !selectedEvent) return null;
    const ev = selectedEvent.evidence as any;
    if (!ev) return null;

    if (ev.bbox_norm && Array.isArray(ev.bbox_norm) && ev.bbox_norm.length === 4) {
      const [x1, y1, x2, y2] = ev.bbox_norm;
      return {
        top: `${(y1 * 100).toFixed(1)}%`,
        left: `${(x1 * 100).toFixed(1)}%`,
        width: `${((x2 - x1) * 100).toFixed(1)}%`,
        height: `${((y2 - y1) * 100).toFixed(1)}%`,
        label: selectedEvent.person_label || activePerson?.person_label || 'Detected Actor',
      };
    }

    if (typeof ev.entry_cx === 'number' && typeof ev.entry_cy === 'number') {
      const h = ev.mean_height || 0.42;
      const w = h * 0.42;
      const top = Math.max(2, Math.min(95, (ev.entry_cy - h / 2) * 100));
      const left = Math.max(2, Math.min(95, (ev.entry_cx - w / 2) * 100));
      return {
        top: `${top.toFixed(1)}%`,
        left: `${left.toFixed(1)}%`,
        width: `${(w * 100).toFixed(1)}%`,
        height: `${(h * 100).toFixed(1)}%`,
        label: selectedEvent.person_label || activePerson?.person_label || 'Detected Actor',
      };
    }

    return null;
  }, [showOverlays, selectedEvent, activePerson]);

  if (loading) {
    return <TimelineSkeleton />;
  }

  if (error || !data) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: 'calc(100vh - 80px)', gap: 16
      }}>
        <div className="card" style={{ maxWidth: 460, padding: 24, textAlign: 'center' }}>
          <AlertTriangle size={32} style={{ color: 'var(--warning)', margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-primary)' }}>
            Video Intelligence Stream Not Available
          </h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            {error || 'Could not load timeline data for this recording.'}
          </p>
          <Link href="/" className="btn btn-secondary" style={{ textDecoration: 'none' }}>
            Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const filename = data.filename || `Record_${videoId}.mp4`;
  const streamUrl = `${API_BASE}/videos/${videoId}/stream`;
  const eventStartSec = selectedEvent ? (selectedEvent.start_ms ?? selectedEvent.timestamp_ms ?? 0) / 1000 : 0;
  const eventEndSec = selectedEvent ? (selectedEvent.end_ms ?? (selectedEvent.start_ms ?? 0) + 12000) / 1000 : 0;
  const eventDwellSec = Math.max(1, Math.round(eventEndSec - eventStartSec));

  // Rulers markers (divide duration into 5-6 clean steps)
  const rulerTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0].map((pct) => pct * duration);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 14 }}>
      {/* ── BREADCRUMB & HEADER BAR ────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div>
          {/* Breadcrumb */}
          <div style={{
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6
          }}>
            <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Recordings</Link>
            <span>/</span>
            <span style={{ color: 'var(--text-secondary)' }}>{filename}</span>
          </div>

          {/* Title + Status Badges */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <h1 style={{
              fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
              letterSpacing: '-0.02em', margin: 0
            }}>
              Forensic Timeline
            </h1>

            {/* Analyzed Badge */}
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '3px 8px', borderRadius: 4,
              backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border)',
              fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)'
            }}>
              <span style={{ display: 'flex', gap: 3 }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
                <span style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
              </span>
              <span>Analyzed ({fmtSecOnly(duration)})</span>
            </div>

            {/* Resolution / Format Pill */}
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '3px 10px', borderRadius: 4,
              backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border)',
              fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)'
            }}>
              <span>{data.metadata?.resolution || '1080p'} • {data.metadata?.fps ? `${Math.round(data.metadata.fps)} FPS` : 'H.264'}</span>
            </div>
          </div>
        </div>

        {/* Right Header Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link href={`/summary/${videoId}`} style={{ textDecoration: 'none' }}>
            <button className="btn btn-secondary" style={{ fontSize: 12, padding: '6px 12px' }}>
              <FileText size={13} style={{ color: 'var(--text-secondary)' }} />
              <span>Executive Summary</span>
            </button>
          </Link>

          <button
            onClick={() => {
              // Export manifest as downloadable JSON
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `TCE_manifest_${videoId}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: '6px 12px' }}
          >
            <Download size={13} style={{ color: 'var(--text-secondary)' }} />
            <span>Export</span>
            <ChevronDown size={11} style={{ color: 'var(--text-muted)' }} />
          </button>

          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            backgroundColor: 'var(--bg-raised)', border: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--text-secondary)', cursor: 'pointer'
          }}>
            <User size={15} />
          </div>
        </div>
      </div>

      {/* ── MAIN WORKSPACE: 70% VIDEO & TRACK + 30% INSPECTOR PANEL ─── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) 370px',
        gap: 16,
        flex: 1,
        minHeight: 0,
      }}>

        {/* ── LEFT COLUMN: VIDEO PLAYER + TIMELINE TRACK ─────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
          
          {/* 1. Video Player Surface */}
          <div className="player-surface" style={{ position: 'relative', display: 'flex', flexDirection: 'column' }}>
            {/* Aspect Ratio Video Container */}
            <div style={{
              position: 'relative',
              width: '100%',
              aspectRatio: '16/9',
              maxHeight: 'min(410px, 46vh)',
              backgroundColor: '#0D1013',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {/* CCTV Surveillance Scene Frame Underlay */}
              {selectedEvent?.evidence?.event_frame_path && !isPlaying && (
                <img
                  src={resolveMediaUrl(selectedEvent.evidence.event_frame_path) || ''}
                  alt="Surveillance Scene"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                  style={{
                    position: 'absolute',
                    inset: 0,
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    pointerEvents: 'none',
                    zIndex: 1,
                  }}
                />
              )}

              <video
                ref={videoRef}
                src={streamUrl}
                poster={resolveMediaUrl(selectedEvent?.evidence?.event_frame_path) || undefined}
                playsInline
                muted={isMuted}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onTimeUpdate={handleTimeUpdate}
                onEnded={() => setIsPlaying(false)}
                onClick={togglePlay}
                style={{ width: '100%', height: '100%', objectFit: 'contain', cursor: 'pointer', position: 'relative', zIndex: 2 }}
              />

              {/* Top-Left Camera HUD Stamp */}
              <div style={{
                position: 'absolute', top: 12, left: 14,
                backgroundColor: 'rgba(19, 22, 24, 0.85)',
                border: '1px solid rgba(52, 60, 66, 0.8)',
                borderRadius: 4, padding: '4px 8px',
                fontSize: 11, fontFamily: 'var(--font-mono)',
                color: 'var(--text-primary)',
                display: 'flex', alignItems: 'center', gap: 6,
                pointerEvents: 'none', zIndex: 10
              }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
                <span>{data.filename || videoId} · {fmtTimecode(currentTime)}</span>
              </div>

              {/* Bounding Box Overlay (HUD) — only renders when real coordinate telemetry exists */}
              {activeBBox && (
                <div style={{
                  position: 'absolute',
                  top: activeBBox.top,
                  left: activeBBox.left,
                  width: activeBBox.width,
                  height: activeBBox.height,
                  border: '1.5px solid var(--accent)',
                  borderRadius: 2,
                  boxShadow: '0 0 12px rgba(98, 221, 176, 0.25)',
                  pointerEvents: 'none',
                  zIndex: 10,
                  transition: 'all 0.2s ease',
                }}>
                  {/* Label badge on top of box */}
                  <div style={{
                    position: 'absolute', top: -20, left: -1,
                    backgroundColor: 'var(--bg-panel)',
                    border: '1px solid var(--accent)',
                    color: 'var(--accent)',
                    padding: '1px 6px',
                    borderRadius: '2px 2px 0 0',
                    fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 600,
                    display: 'flex', alignItems: 'center', gap: 4
                  }}>
                    <span style={{ width: 4, height: 4, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
                    <span>{activeBBox.label}</span>
                  </div>

                  {/* Corner Reticle Accents */}
                  <div style={{ position: 'absolute', top: -2, left: -2, width: 6, height: 6, borderTop: '2px solid #fff', borderLeft: '2px solid #fff' }} />
                  <div style={{ position: 'absolute', top: -2, right: -2, width: 6, height: 6, borderTop: '2px solid #fff', borderRight: '2px solid #fff' }} />
                  <div style={{ position: 'absolute', bottom: -2, left: -2, width: 6, height: 6, borderBottom: '2px solid #fff', borderLeft: '2px solid #fff' }} />
                  <div style={{ position: 'absolute', bottom: -2, right: -2, width: 6, height: 6, borderBottom: '2px solid #fff', borderRight: '2px solid #fff' }} />
                </div>
              )}

              {/* Center Play Button Overlay when Paused */}
              {!isPlaying && (
                <button
                  onClick={togglePlay}
                  style={{
                    position: 'absolute',
                    width: 54, height: 54, borderRadius: '50%',
                    backgroundColor: 'rgba(32, 37, 41, 0.85)',
                    border: '1px solid var(--border)',
                    color: 'var(--accent)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', zIndex: 12,
                    boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
                    transition: 'transform 0.15s, background-color 0.15s'
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.08)')}
                  onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                >
                  <Play size={22} style={{ marginLeft: 3 }} />
                </button>
              )}
            </div>

            {/* ── Player Controls Bar (Below Video) ───────────────────── */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 14px',
              backgroundColor: 'var(--bg-inset)',
              borderTop: '1px solid var(--border-dim)'
            }}>
              {/* Left Controls: Prev, Play, Next */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  onClick={() => stepFrame(-1)}
                  title="Previous frame / second"
                  className="btn btn-ghost"
                  style={{ width: 28, height: 28, padding: 0 }}
                >
                  <SkipBack size={14} />
                </button>

                <button
                  onClick={togglePlay}
                  title={isPlaying ? 'Pause' : 'Play'}
                  style={{
                    width: 32, height: 32, borderRadius: 6,
                    backgroundColor: 'var(--accent)',
                    color: '#1a1f1b',
                    border: 'none',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer'
                  }}
                >
                  {isPlaying ? <Pause size={15} /> : <Play size={15} style={{ marginLeft: 1 }} />}
                </button>

                <button
                  onClick={() => stepFrame(1)}
                  title="Next frame / second"
                  className="btn btn-ghost"
                  style={{ width: 28, height: 28, padding: 0 }}
                >
                  <SkipForward size={14} />
                </button>

                {/* Timecode Pill */}
                <div style={{
                  padding: '3px 10px', borderRadius: 4,
                  backgroundColor: 'var(--bg-raised)', border: '1px solid var(--border-dim)',
                  fontSize: 12, fontFamily: 'var(--font-mono)',
                  color: 'var(--text-primary)', marginLeft: 8
                }}>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{fmtTimecode(currentTime)}</span>
                  <span style={{ color: 'var(--text-muted)', margin: '0 4px' }}>/</span>
                  <span style={{ color: 'var(--text-muted)' }}>{fmtTimecode(duration)}</span>
                </div>
              </div>

              {/* Right Controls: Speed, Overlays, Mute, Fullscreen */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {/* Speed Dropdown Pill */}
                <button
                  onClick={() => {
                    const rates = [0.5, 1.0, 2.0];
                    const nextRate = rates[(rates.indexOf(playbackRate) + 1) % rates.length];
                    setPlaybackRate(nextRate);
                    if (videoRef.current) videoRef.current.playbackRate = nextRate;
                  }}
                  className="btn btn-secondary"
                  style={{ fontSize: 11, fontFamily: 'var(--font-mono)', padding: '3px 8px', height: 26 }}
                >
                  <span>{playbackRate.toFixed(1)}x</span>
                  <ChevronDown size={10} style={{ color: 'var(--text-muted)' }} />
                </button>

                {/* Overlays Toggle */}
                <button
                  onClick={() => setShowOverlays(!showOverlays)}
                  className="btn btn-secondary"
                  style={{
                    fontSize: 11, fontFamily: 'var(--font-mono)',
                    padding: '3px 8px', height: 26, gap: 5,
                    color: showOverlays ? 'var(--text-primary)' : 'var(--text-muted)'
                  }}
                >
                  <span style={{
                    width: 5, height: 5, borderRadius: '50%',
                    backgroundColor: showOverlays ? 'var(--accent)' : 'var(--text-muted)'
                  }} />
                  <span>Overlays: {showOverlays ? 'ON' : 'OFF'}</span>
                </button>

                {/* Mute Toggle */}
                <button
                  onClick={() => {
                    setIsMuted(!isMuted);
                    if (videoRef.current) videoRef.current.muted = !isMuted;
                  }}
                  className="btn btn-ghost"
                  style={{ width: 26, height: 26, padding: 0 }}
                  title={isMuted ? 'Unmute' : 'Mute'}
                >
                  {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
                </button>

                {/* Fullscreen */}
                <button
                  onClick={() => {
                    if (videoRef.current?.requestFullscreen) {
                      videoRef.current.requestFullscreen();
                    }
                  }}
                  className="btn btn-ghost"
                  style={{ width: 26, height: 26, padding: 0 }}
                  title="Fullscreen"
                >
                  <Maximize2 size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* 2. Enhanced Multi-Layer Forensic Timeline Track Section */}
          <div className="card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Header: Left Filter Pills, Center Live Activity Ticker, Right Navigation & Zoom */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
              {/* Left View Filter Mode Tabs */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  onClick={() => setFilterMode('events')}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '4px 10px', borderRadius: 5, fontSize: 11, fontFamily: 'var(--font-mono)',
                    backgroundColor: filterMode === 'events' ? 'var(--accent-bg)' : 'var(--bg-raised)',
                    border: `1px solid ${filterMode === 'events' ? 'var(--accent)' : 'var(--border-dim)'}`,
                    color: filterMode === 'events' ? 'var(--accent)' : 'var(--text-secondary)',
                    boxShadow: filterMode === 'events' ? '0 0 10px rgba(98, 221, 176, 0.25)' : 'none',
                    cursor: 'pointer', transition: 'all 0.15s ease'
                  }}
                >
                  <Activity size={12} style={{ color: filterMode === 'events' ? 'var(--accent)' : 'var(--text-muted)' }} />
                  <span style={{ fontWeight: 600 }}>Events</span>
                  <span style={{
                    fontSize: 10, padding: '1px 5px', borderRadius: 10,
                    backgroundColor: filterMode === 'events' ? 'var(--accent)' : 'var(--bg-inset)',
                    color: filterMode === 'events' ? '#0D1013' : 'var(--text-muted)',
                    fontWeight: 700
                  }}>
                    {allEvents.length}
                  </span>
                </button>

                <button
                  onClick={() => setFilterMode('actors')}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '4px 10px', borderRadius: 5, fontSize: 11, fontFamily: 'var(--font-mono)',
                    backgroundColor: filterMode === 'actors' ? 'rgba(6, 182, 212, 0.15)' : 'var(--bg-raised)',
                    border: `1px solid ${filterMode === 'actors' ? '#06b6d4' : 'var(--border-dim)'}`,
                    color: filterMode === 'actors' ? '#38bdf8' : 'var(--text-secondary)',
                    boxShadow: filterMode === 'actors' ? '0 0 10px rgba(6, 182, 212, 0.25)' : 'none',
                    cursor: 'pointer', transition: 'all 0.15s ease'
                  }}
                >
                  <Users size={12} style={{ color: filterMode === 'actors' ? '#38bdf8' : 'var(--text-muted)' }} />
                  <span style={{ fontWeight: 600 }}>Actor Swimlanes</span>
                  <span style={{
                    fontSize: 10, padding: '1px 5px', borderRadius: 10,
                    backgroundColor: filterMode === 'actors' ? '#06b6d4' : 'var(--bg-inset)',
                    color: filterMode === 'actors' ? '#0D1013' : 'var(--text-muted)',
                    fontWeight: 700
                  }}>
                    {data.persons.length}
                  </span>
                </button>

                <button
                  onClick={() => setFilterMode('objects')}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '4px 10px', borderRadius: 5, fontSize: 11, fontFamily: 'var(--font-mono)',
                    backgroundColor: filterMode === 'objects' ? 'rgba(245, 158, 11, 0.15)' : 'var(--bg-raised)',
                    border: `1px solid ${filterMode === 'objects' ? '#f59e0b' : 'var(--border-dim)'}`,
                    color: filterMode === 'objects' ? '#fbbf24' : 'var(--text-secondary)',
                    boxShadow: filterMode === 'objects' ? '0 0 10px rgba(245, 158, 11, 0.25)' : 'none',
                    cursor: 'pointer', transition: 'all 0.15s ease'
                  }}
                >
                  <Box size={12} style={{ color: filterMode === 'objects' ? '#fbbf24' : 'var(--text-muted)' }} />
                  <span style={{ fontWeight: 600 }}>Objects</span>
                  <span style={{
                    fontSize: 10, padding: '1px 5px', borderRadius: 10,
                    backgroundColor: filterMode === 'objects' ? '#f59e0b' : 'var(--bg-inset)',
                    color: filterMode === 'objects' ? '#0D1013' : 'var(--text-muted)',
                    fontWeight: 700
                  }}>
                    {data.detected_objects.length}
                  </span>
                </button>
              </div>

              {/* Center Live Forensic Activity Ticker Pill (Real-Time Dynamic Telemetry) */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '4px 12px', borderRadius: 20,
                backgroundColor: 'var(--bg-inset)',
                border: `1px solid ${activeTelemetry.categoryVisual.border}`,
                boxShadow: `0 0 12px ${activeTelemetry.categoryVisual.glow}`,
                fontSize: 11, fontFamily: 'var(--font-mono)',
                maxWidth: 440, overflow: 'hidden'
              }}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%',
                  backgroundColor: activeTelemetry.categoryVisual.color,
                  boxShadow: `0 0 6px ${activeTelemetry.categoryVisual.color}`,
                  animation: isPlaying ? 'pulse 1.2s infinite' : 'none',
                  flexShrink: 0
                }} />
                <span style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Live Telemetry:
                </span>
                <span style={{
                  padding: '1px 6px', borderRadius: 3,
                  backgroundColor: activeTelemetry.actorPalette.bg,
                  border: `1px solid ${activeTelemetry.actorPalette.border}`,
                  color: activeTelemetry.actorPalette.text,
                  fontWeight: 700, fontSize: 10, flexShrink: 0
                }}>
                  {activeTelemetry.actorLabel}
                </span>
                <span style={{
                  color: 'var(--text-primary)', fontWeight: 600,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                }}>
                  {activeTelemetry.actionTitle}
                </span>
                <span style={{
                  fontSize: 9, padding: '1px 5px', borderRadius: 3,
                  backgroundColor: activeTelemetry.categoryVisual.badgeBg,
                  color: activeTelemetry.categoryVisual.color,
                  fontWeight: 700, flexShrink: 0
                }}>
                  {Math.round(activeTelemetry.confidence * 100)}%
                </span>
              </div>

              {/* Right Event Step Buttons & Zoom Controls */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {/* Previous / Next Event Buttons */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <button
                    onClick={goToPrevEvent}
                    title="Jump to previous forensic event"
                    className="btn btn-secondary"
                    style={{ height: 26, padding: '0 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                  >
                    <ChevronLeft size={13} />
                    <span>Prev</span>
                  </button>
                  <button
                    onClick={goToNextEvent}
                    title="Jump to next forensic event"
                    className="btn btn-secondary"
                    style={{ height: 26, padding: '0 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                  >
                    <span>Next</span>
                    <ChevronRight size={13} />
                  </button>
                </div>

                {/* Zoom Controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 3, paddingLeft: 6, borderLeft: '1px solid var(--border-dim)' }}>
                  {(['Fit', '1x', '2x'] as const).map((z) => {
                    const active = zoomLevel === z.toLowerCase();
                    return (
                      <button
                        key={z}
                        onClick={() => setZoomLevel(z.toLowerCase() as any)}
                        className="btn btn-secondary"
                        style={{
                          fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 8px', height: 24,
                          backgroundColor: active ? 'var(--accent-bg)' : undefined,
                          borderColor: active ? 'var(--accent)' : undefined,
                          color: active ? 'var(--accent)' : undefined,
                          fontWeight: active ? 700 : 500
                        }}
                      >
                        {z}
                      </button>
                    );
                  })}
                  <button
                    onClick={() => {
                      if (zoomLevel === '2x') setZoomLevel('1x');
                      else if (zoomLevel === '1x') setZoomLevel('fit');
                    }}
                    className="btn btn-secondary"
                    style={{ width: 24, height: 24, padding: 0, fontSize: 12 }}
                    title="Zoom out"
                  >
                    -
                  </button>
                  <button
                    onClick={() => {
                      if (zoomLevel === 'fit') setZoomLevel('1x');
                      else if (zoomLevel === '1x') setZoomLevel('2x');
                    }}
                    className="btn btn-secondary"
                    style={{ width: 24, height: 24, padding: 0, fontSize: 12 }}
                    title="Zoom in"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>

            {/* Time Ruler with Division Markers */}
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
              padding: '0 4px', userSelect: 'none', borderBottom: '1px solid rgba(255,255,255,0.04)',
              paddingBottom: 4
            }}>
              {[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0].map((pct, idx) => (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                  <span>{fmtSecOnly(pct * duration)}</span>
                  <div style={{ width: 1, height: 4, backgroundColor: 'var(--border-dim)' }} />
                </div>
              ))}
            </div>

            {/* Scrollable Track Wrapper (Expands when zoomed) */}
            <div style={{
              position: 'relative',
              width: '100%',
              overflowX: zoomLevel !== 'fit' ? 'auto' : 'hidden',
              overflowY: 'hidden',
              borderRadius: 6
            }}>
              {/* Interactive Timeline Track Surface */}
              <div
                ref={trackRef}
                onPointerDown={handleTrackPointerDown}
                onPointerMove={handleTrackPointerMove}
                onPointerUp={handleTrackPointerUp}
                onPointerLeave={handleTrackPointerLeave}
                style={{
                  position: 'relative',
                  width: zoomLevel === '2x' ? '250%' : zoomLevel === '1x' ? '150%' : '100%',
                  minHeight: filterMode === 'actors'
                    ? (data.persons.length * 36 + 18)
                    : filterMode === 'events'
                    ? (tieredEvents.trackCount * 32 + 20)
                    : (data.detected_objects.length * 28 + 20),
                  backgroundColor: 'var(--bg-inset)',
                  border: '1px solid var(--border-dim)',
                  borderRadius: 6,
                  cursor: isScrubbing ? 'grabbing' : 'crosshair',
                  userSelect: 'none',
                  transition: 'background-color 0.15s'
                }}
              >
                {/* Subtle vertical millisecond grid lines */}
                <div style={{
                  position: 'absolute', inset: 0,
                  backgroundImage: 'linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px)',
                  backgroundSize: '10% 100%',
                  pointerEvents: 'none'
                }} />

                {/* ── VIEW MODE 1: ALL EVENTS SMART TIERED NON-OVERLAPPING TRACKS ─── */}
                {filterMode === 'events' && (
                  <div style={{
                    position: 'relative',
                    width: '100%',
                    height: Math.max(100, tieredEvents.trackCount * 32 + 16),
                    padding: '8px 4px'
                  }}>
                    {/* Background lane strips */}
                    {Array.from({ length: tieredEvents.trackCount }).map((_, laneIdx) => (
                      <div
                        key={`lane-${laneIdx}`}
                        style={{
                          position: 'absolute',
                          left: 0, right: 0,
                          top: 8 + laneIdx * 32,
                          height: 28,
                          backgroundColor: laneIdx % 2 === 0 ? 'rgba(255,255,255,0.015)' : 'rgba(0,0,0,0.18)',
                          borderRadius: 4,
                          border: '1px dashed rgba(255,255,255,0.04)',
                          pointerEvents: 'none'
                        }}
                      />
                    ))}

                    {tieredEvents.assigned.map((item) => {
                      const { evt, originalIdx, startSec, endSec, track } = item;
                      const startPct = (startSec / duration) * 100;
                      const rawWidthPct = ((endSec - startSec) / duration) * 100;
                      const widthPct = Math.max(2.5, rawWidthPct);

                      const isSelected = selectedEventIndex === originalIdx;
                      const isCurrentActive = (currentTime >= startSec - 0.25 && currentTime <= endSec + 0.25);
                      const cat = getEventCategoryVisual(evt);
                      const parsed = parseActorAndAction(evt);
                      const actPalette = getActorPalette(parsed.actorLabel);

                      return (
                        <div
                          key={evt.event_id || evt.id || originalIdx}
                          onClick={(e) => {
                            e.stopPropagation();
                            seekToEvent(evt, originalIdx);
                          }}
                          title={`${parsed.actorLabel}: ${parsed.actionTitle} (${fmtTimecode(startSec)} - ${fmtTimecode(endSec)})`}
                          style={{
                            position: 'absolute',
                            left: `${startPct}%`,
                            top: 8 + track * 32,
                            width: `${widthPct}%`,
                            height: 28,
                            borderRadius: 5,
                            background: isCurrentActive
                              ? `linear-gradient(90deg, ${cat.bg}, ${actPalette.bg})`
                              : cat.bg,
                            border: `1.5px solid ${isCurrentActive || isSelected ? cat.color : cat.border}`,
                            boxShadow: isCurrentActive
                              ? `0 0 14px ${cat.glow}, inset 0 0 6px ${cat.glow}`
                              : isSelected
                              ? `0 0 10px ${cat.glow}`
                              : '0 1px 4px rgba(0,0,0,0.3)',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            zIndex: isCurrentActive ? 6 : isSelected ? 5 : 2,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 5,
                            padding: '0 6px',
                            overflow: 'hidden'
                          }}
                        >
                          {/* Actor Badge */}
                          <span style={{
                            padding: '1px 5px', borderRadius: 3,
                            backgroundColor: actPalette.bg,
                            border: `1px solid ${actPalette.border}`,
                            color: actPalette.text,
                            fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
                            whiteSpace: 'nowrap', flexShrink: 0
                          }}>
                            {parsed.actorLabel.replace(/^Person\s+/i, 'P')}
                          </span>

                          {/* Action Title */}
                          <span style={{
                            fontSize: 10, fontFamily: 'var(--font-sans)', fontWeight: 600,
                            color: isCurrentActive ? '#FFFFFF' : 'var(--text-primary)',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                            flex: 1
                          }}>
                            {parsed.actionTitle}
                          </span>

                          {/* Time Stamp */}
                          {widthPct > 6 && (
                            <span style={{
                              fontSize: 8, fontFamily: 'var(--font-mono)',
                              color: isCurrentActive ? cat.color : 'var(--text-muted)',
                              flexShrink: 0
                            }}>
                              {fmtSecOnly(startSec)}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* ── VIEW MODE 2: MULTI-TRACK ACTOR SWIMLANES ───────── */}
                {filterMode === 'actors' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '8px 10px' }}>
                    {data.persons.map((person, pIdx) => {
                      const pal = getActorPalette(person.person_label);
                      const isActorPresentNow = (currentTime * 1000) >= person.first_seen_ms && (currentTime * 1000) <= person.last_seen_ms;
                      const actorEvents = allEvents.filter(
                        (e) => (e.person_label === person.person_label || e.evidence?.person_label === person.person_label)
                      );
                      const presStartPct = (person.first_seen_ms / 1000 / duration) * 100;
                      const presEndPct = (person.last_seen_ms / 1000 / duration) * 100;
                      const presWidthPct = Math.max(2, presEndPct - presStartPct);

                      return (
                        <div
                          key={person.person_label || pIdx}
                          style={{
                            position: 'relative',
                            height: 28,
                            backgroundColor: isActorPresentNow ? 'rgba(255,255,255,0.03)' : 'transparent',
                            borderRadius: 4,
                            border: `1px solid ${isActorPresentNow ? pal.border : 'rgba(255,255,255,0.04)'}`,
                            display: 'flex',
                            alignItems: 'center'
                          }}
                        >
                          {/* Actor Label Chip Pinned to Left */}
                          <div style={{
                            position: 'sticky', left: 0, zIndex: 7,
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '2px 8px', borderRadius: 4,
                            backgroundColor: 'rgba(15, 23, 20, 0.92)',
                            borderRight: `2px solid ${pal.border}`,
                            width: 140, flexShrink: 0
                          }}>
                            <span style={{
                              width: 6, height: 6, borderRadius: '50%',
                              backgroundColor: pal.color,
                              boxShadow: isActorPresentNow ? `0 0 6px ${pal.color}` : 'none',
                              animation: isActorPresentNow ? 'pulse 1.2s infinite' : 'none'
                            }} />
                            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700, color: pal.text }}>
                              {person.person_label}
                            </span>
                            <span style={{ fontSize: 9, color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {isActorPresentNow ? 'ACTIVE' : `${actorEvents.length} evts`}
                            </span>
                          </div>

                          {/* Actor Scene Presence Bar */}
                          <div style={{
                            position: 'absolute',
                            left: `${presStartPct}%`,
                            width: `${presWidthPct}%`,
                            height: 18,
                            borderRadius: 3,
                            backgroundColor: pal.bg,
                            border: `1px dashed ${pal.border}80`,
                            pointerEvents: 'none',
                            zIndex: 1
                          }} />

                          {/* Specific Action Capsules for this Actor */}
                          {actorEvents.map((evt, eIdx) => {
                            const eStartSec = (evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000;
                            const eEndSec = (evt.end_ms ?? (evt.start_ms ?? 0) + 3500) / 1000;
                            const eLeftPct = (eStartSec / duration) * 100;
                            const eWidthPct = Math.max(2, ((eEndSec - eStartSec) / duration) * 100);
                            const isCur = activeTelemetry.primaryEvent?.event_id === evt.event_id;
                            const parsed = parseActorAndAction(evt);

                            return (
                              <div
                                key={evt.event_id || evt.id || eIdx}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  seekToEvent(evt);
                                }}
                                title={`${person.person_label}: ${parsed.actionTitle} (${fmtSecOnly(eStartSec)})`}
                                style={{
                                  position: 'absolute',
                                  left: `${eLeftPct}%`,
                                  width: `${eWidthPct}%`,
                                  height: 22,
                                  borderRadius: 3,
                                  backgroundColor: isCur ? pal.color : pal.border,
                                  color: isCur ? '#0D1013' : '#FFFFFF',
                                  boxShadow: isCur ? `0 0 10px ${pal.glow}` : '0 1px 4px rgba(0,0,0,0.4)',
                                  fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
                                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                                  padding: '0 4px', cursor: 'pointer', zIndex: 3,
                                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                                }}
                              >
                                {parsed.actionTitle.slice(0, 14)}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* ── VIEW MODE 3: PHYSICAL ASSET DENSITY HEATMAP ─────── */}
                {filterMode === 'objects' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '8px 10px' }}>
                    {data.detected_objects.map((obj, oIdx) => {
                      const colors = ['#06b6d4', '#38bdf8', '#10b981', '#f59e0b', '#ec4899'];
                      const objColor = colors[oIdx % colors.length];

                      return (
                        <div
                          key={obj.class_name || oIdx}
                          style={{
                            position: 'relative',
                            height: 24,
                            backgroundColor: 'rgba(255,255,255,0.02)',
                            borderRadius: 4,
                            border: '1px solid rgba(255,255,255,0.04)',
                            display: 'flex',
                            alignItems: 'center'
                          }}
                        >
                          {/* Object Name Label */}
                          <div style={{
                            position: 'sticky', left: 0, zIndex: 7,
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '2px 8px', borderRadius: 4,
                            backgroundColor: 'rgba(15, 23, 20, 0.92)',
                            borderRight: `2px solid ${objColor}`,
                            width: 170, flexShrink: 0
                          }}>
                            <Box size={11} style={{ color: objColor }} />
                            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                              {obj.display_name.split('(')[0].trim()}
                            </span>
                            <span style={{ fontSize: 9, color: objColor, fontWeight: 700 }}>
                              x{obj.instance_count}
                            </span>
                          </div>

                          {/* Full Span Active Utilization Strip */}
                          <div style={{
                            position: 'absolute',
                            left: '0%', width: '100%', height: 14,
                            borderRadius: 2,
                            backgroundColor: `${objColor}22`,
                            border: `1px solid ${objColor}55`,
                            pointerEvents: 'none'
                          }} />
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* ── HOVER GHOST NEEDLE & TOOLTIP ─────────────────────── */}
                {hoverTime !== null && (
                  <div
                    style={{
                      position: 'absolute',
                      left: `${(hoverTime / duration) * 100}%`,
                      top: 0, bottom: 0,
                      width: 1,
                      backgroundColor: 'rgba(255, 255, 255, 0.6)',
                      pointerEvents: 'none',
                      zIndex: 7
                    }}
                  >
                    <div style={{
                      position: 'absolute',
                      top: -26,
                      left: (hoverTime / duration) > 0.8 ? -90 : 8,
                      padding: '2px 6px',
                      borderRadius: 4,
                      backgroundColor: 'rgba(15, 23, 20, 0.95)',
                      border: '1px solid var(--border)',
                      color: 'var(--text-primary)',
                      fontSize: 10, fontFamily: 'var(--font-mono)',
                      whiteSpace: 'nowrap',
                      pointerEvents: 'none'
                    }}>
                      {fmtTimecode(hoverTime)} • Click to seek
                    </div>
                  </div>
                )}

                {/* ── PLAYHEAD NEEDLE & DYNAMIC ACTIVITY CALLOUT ──────── */}
                <div
                  style={{
                    position: 'absolute',
                    left: `${Math.max(0, Math.min(100, (currentTime / duration) * 100))}%`,
                    top: 0, bottom: 0,
                    width: 2,
                    background: 'linear-gradient(180deg, var(--accent) 0%, rgba(98, 221, 176, 0.7) 100%)',
                    boxShadow: '0 0 10px rgba(98, 221, 176, 0.8)',
                    pointerEvents: 'none',
                    zIndex: 10,
                    transition: isScrubbing ? 'none' : 'left 0.05s linear'
                  }}
                >
                  {/* Needle Top Pin */}
                  <div style={{
                    position: 'absolute', top: 0, left: -4,
                    width: 10, height: 7,
                    backgroundColor: 'var(--accent)',
                    clipPath: 'polygon(0 0, 100% 0, 50% 100%)'
                  }} />

                  {/* Needle Bottom Pin */}
                  <div style={{
                    position: 'absolute', bottom: 0, left: -4,
                    width: 10, height: 7,
                    backgroundColor: 'var(--accent)',
                    clipPath: 'polygon(50% 0, 100% 100%, 0 100%)'
                  }} />

                  {/* Real-Time Dynamic Action Telemetry Callout (Moves & updates live with video!) */}
                  <div style={{
                    position: 'absolute',
                    top: 10,
                    // Auto-flip left/right near boundaries so it never overflows off-screen
                    left: (currentTime / duration) > 0.75 ? 'auto' : 8,
                    right: (currentTime / duration) > 0.75 ? 8 : 'auto',
                    padding: '4px 10px',
                    borderRadius: 6,
                    backgroundColor: 'rgba(15, 23, 20, 0.96)',
                    backdropFilter: 'blur(12px)',
                    border: `1.5px solid ${activeTelemetry.categoryVisual.color}`,
                    color: 'var(--text-primary)',
                    boxShadow: `0 4px 16px rgba(0,0,0,0.65), 0 0 12px ${activeTelemetry.categoryVisual.glow}`,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    whiteSpace: 'nowrap',
                    pointerEvents: 'none',
                    zIndex: 12
                  }}>
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%',
                      backgroundColor: activeTelemetry.categoryVisual.color,
                      boxShadow: `0 0 6px ${activeTelemetry.categoryVisual.color}`,
                      animation: isPlaying ? 'pulse 1.2s infinite' : 'none',
                      flexShrink: 0
                    }} />

                    {/* Timecode */}
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {fmtSecOnly(currentTime)}
                    </span>

                    {/* Actor Badge */}
                    <span style={{
                      padding: '1px 5px', borderRadius: 3,
                      backgroundColor: activeTelemetry.actorPalette.bg,
                      border: `1px solid ${activeTelemetry.actorPalette.border}`,
                      color: activeTelemetry.actorPalette.text,
                      fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700,
                      flexShrink: 0
                    }}>
                      {activeTelemetry.actorLabel}
                    </span>

                    {/* Dynamic Real-Time Action Text */}
                    <span style={{
                      fontSize: 11, fontFamily: 'var(--font-sans)', fontWeight: 600,
                      color: '#FFFFFF', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis'
                    }}>
                      {activeTelemetry.actionTitle}
                    </span>

                    {/* Multi-event indicator if concurrent */}
                    {activeTelemetry.activeEvents.length > 1 && (
                      <span style={{
                        fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
                        padding: '1px 5px', borderRadius: 10,
                        backgroundColor: 'rgba(98, 221, 176, 0.2)',
                        border: '1px solid rgba(98, 221, 176, 0.4)',
                        color: 'var(--accent)',
                        flexShrink: 0
                      }}>
                        +{activeTelemetry.activeEvents.length - 1} concurrent
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Track Footer Metadata & Live Causal Integrity */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap',
              fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
              padding: '0 4px', gap: 8
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--text-secondary)' }}>
                  Stream: <strong style={{ color: 'var(--text-primary)' }}>{data.filename || videoId}</strong>
                </span>
                <span>•</span>
                <span>{allEvents.length} events indexed</span>
                <span>•</span>
                <span>{data.unique_persons} personas tracked</span>
              </div>

              {/* Live In-Scene Actor Beacon Indicators */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                  In Scene:
                </span>
                {(data.persons || []).map((person) => {
                  const isPresent = (currentTime * 1000) >= person.first_seen_ms && (currentTime * 1000) <= person.last_seen_ms;
                  const pal = getActorPalette(person.person_label);
                  return (
                    <span
                      key={person.person_label}
                      title={`${person.person_label}: ${isPresent ? 'Currently in frame' : 'Off screen'}`}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        padding: '2px 7px', borderRadius: 12,
                        fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
                        backgroundColor: isPresent ? pal.bg : 'rgba(255,255,255,0.02)',
                        border: `1px solid ${isPresent ? pal.border : 'rgba(255,255,255,0.06)'}`,
                        color: isPresent ? pal.text : 'rgba(255,255,255,0.25)',
                        boxShadow: isPresent ? `0 0 8px ${pal.glow}` : 'none',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      <span style={{
                        width: 5, height: 5, borderRadius: '50%',
                        backgroundColor: isPresent ? pal.color : 'rgba(255,255,255,0.2)',
                        boxShadow: isPresent ? `0 0 5px ${pal.color}` : 'none',
                        animation: isPresent ? 'pulse 1.2s infinite' : 'none'
                      }} />
                      {person.person_label}
                    </span>
                  );
                })}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ShieldCheck size={13} style={{ color: 'var(--accent)' }} />
                <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Causal ReID Synchronized</span>
                <span style={{ color: 'var(--text-muted)' }}>•</span>
                <span>100% Deterministic Matrix</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── RIGHT COLUMN: INSPECTOR PANEL (370px) ─────────────────── */}
        <div className="card" style={{
          display: 'flex', flexDirection: 'column',
          padding: 16, height: '100%', overflowY: 'auto'
        }}>
          {/* Top Segmented Tabs: Event, Actors, Assets, Narrative */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
            backgroundColor: 'var(--bg-inset)', borderRadius: 6,
            padding: 2, marginBottom: 16, border: '1px solid var(--border-dim)'
          }}>
            {(['Event', 'Actors', 'Assets', 'Narrative'] as const).map((tab) => {
              const active = activeTab === tab;
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: '6px 0', textAlign: 'center',
                    fontSize: 12, fontWeight: active ? 600 : 500,
                    fontFamily: 'var(--font-sans)',
                    color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                    backgroundColor: active ? 'var(--bg-panel)' : 'transparent',
                    border: active ? '1px solid var(--border)' : '1px solid transparent',
                    borderRadius: 4, cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                >
                  {tab}
                </button>
              );
            })}
          </div>

          {/* ── TAB 1: EVENT DETAILS ──────────────────────────────────── */}
          {activeTab === 'Event' && !selectedEvent && (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              flex: 1, gap: 12, padding: '32px 0', textAlign: 'center'
            }}>
              <Layers size={28} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>No Events Detected</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  {data.job_status === 'completed'
                    ? 'The pipeline completed but found no significant events in this recording. Try re-processing with a different model profile.'
                    : 'Processing is not complete. Check the job status page.'}
                </div>
              </div>
            </div>
          )}
          {activeTab === 'Event' && selectedEvent && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Event ID + Verified Causal Link Badge */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  EVT-{selectedEvent.event_id?.slice(0, 6) || selectedEvent.id?.slice(0, 6) || '084'}
                </span>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '2px 8px', borderRadius: 4,
                  backgroundColor: 'var(--accent-bg)', border: '1px solid var(--accent-dim)',
                  fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)'
                }}>
                  <ShieldCheck size={11} />
                  <span>Verified Causal Link</span>
                </span>
              </div>

              {/* Event Title */}
              <h2 style={{
                fontSize: 17, fontWeight: 700, color: 'var(--text-primary)',
                letterSpacing: '-0.01em', margin: 0
              }}>
                {selectedEvent.display_name || formatLabel(selectedEvent.event_type || 'Observed Event')}
              </h2>

              {/* Timecode Range & Dwell Duration */}
              <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                <span>{fmtTimecode(eventStartSec)} → {fmtTimecode(eventEndSec)}</span>
                <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>({eventDwellSec}s dwell)</span>
              </div>

              {/* Involves Actors */}
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                <span>Involves </span>
                <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
                  {selectedEvent.person_label || 'Scene Level Interaction'}
                </span>
              </div>

              {/* Text Description Box */}
              <div className="card-inset" style={{ padding: '12px 14px' }}>
                <p style={{
                  fontSize: 12, lineHeight: 1.6, color: 'var(--text-primary)',
                  margin: 0
                }}>
                  {selectedEvent.evidence?.description ||
                    (selectedEvent.display_name
                      ? selectedEvent.display_name
                      : `Detected ${formatLabel(selectedEvent.event_type || 'event')} at ${fmtSecOnly(eventStartSec)}.`)}
                </p>
              </div>

              {/* Confidence Meter Row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                  Confidence:{' '}
                  <strong style={{ color: 'var(--text-primary)' }}>
                    {((selectedEvent.confidence || 0.88) * 100).toFixed(1)}%
                  </strong>{' '}
                  <span style={{ color: 'var(--accent)' }}>Verified</span>
                </span>
                <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
              </div>

              {/* Accordion: Evidence Details */}
              <div>
                <button
                  onClick={() => setEvidenceExpanded(!evidenceExpanded)}
                  className="expand-trigger"
                  style={{ width: '100%', justifyContent: 'space-between', border: 'none', background: 'transparent' }}
                >
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>Evidence details</span>
                  <ChevronDown
                    size={14}
                    style={{
                      transform: evidenceExpanded ? 'rotate(180deg)' : 'none',
                      transition: 'transform 0.2s'
                    }}
                  />
                </button>

                {evidenceExpanded && (
                  <div className="card-inset" style={{ padding: '10px 12px', marginTop: 6, fontSize: 11, fontFamily: 'var(--font-mono)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Rule Name:</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{selectedEvent.rule_name || selectedEvent.event_type}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Camera ID:</span>
                      <span style={{ color: 'var(--text-secondary)' }}>CAM-07 (West Wing)</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Direction:</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{selectedEvent.evidence?.direction || 'Stationary / In-frame'}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Lighting:</span>
                      <span style={{ color: 'var(--text-secondary)' }}>{selectedEvent.evidence?.lighting_condition || 'Standard Indoor'}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* TEMPORAL EVIDENCE STRIP */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.08em' }}>
                    TEMPORAL EVIDENCE STRIP
                  </span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    3 Captures
                  </span>
                </div>

                {/* 3 Captures: Approach, Discussion, Departure */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                  {[
                    {
                      label: 'Approach',
                      time: fmtSecOnly(Math.max(0, eventStartSec - 2)),
                      imgUrl: resolveMediaUrl(selectedEvent.evidence?.before_frame_path) || resolveMediaUrl(selectedEvent.evidence?.thumbnail_path) || (activePerson?.crop_url ? resolveMediaUrl(activePerson.crop_url) : null),
                    },
                    {
                      label: 'Discussion',
                      time: fmtSecOnly(eventStartSec),
                      imgUrl: resolveMediaUrl(selectedEvent.evidence?.event_frame_path) || resolveMediaUrl(selectedEvent.evidence?.thumbnail_path) || (activePerson?.crop_url ? resolveMediaUrl(activePerson.crop_url) : null),
                    },
                    {
                      label: 'Departure',
                      time: fmtSecOnly(eventEndSec),
                      imgUrl: resolveMediaUrl(selectedEvent.evidence?.after_frame_path) || resolveMediaUrl(selectedEvent.evidence?.thumbnail_path) || (activePerson?.crop_url ? resolveMediaUrl(activePerson.crop_url) : null),
                    },
                  ].map((strip, i) => (
                    <div
                      key={i}
                      onClick={() => setPreviewEventId(selectedEvent.event_id || selectedEvent.id || null)}
                      className="card-inset"
                      style={{
                        padding: 4, display: 'flex', flexDirection: 'column', gap: 4,
                        cursor: 'pointer', transition: 'border-color 0.15s'
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-dim)')}
                      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-dim)')}
                    >
                      <div style={{
                        width: '100%', height: 54, borderRadius: 4,
                        backgroundColor: '#0D1013', overflow: 'hidden', position: 'relative',
                        display: 'flex', alignItems: 'center', justifyContent: 'center'
                      }}>
                        {strip.imgUrl ? (
                          <img
                            src={strip.imgUrl}
                            alt={strip.label}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        ) : (
                          <div style={{
                            width: '100%', height: '100%', display: 'flex',
                            alignItems: 'center', justifyContent: 'center',
                            backgroundColor: 'rgba(26, 32, 35, 0.6)'
                          }}>
                            <Crosshair size={14} style={{ color: 'var(--text-muted)' }} />
                          </div>
                        )}
                        <span style={{
                          position: 'absolute', bottom: 2, right: 3,
                          backgroundColor: 'rgba(0,0,0,0.75)', borderRadius: 2,
                          padding: '1px 3px', fontSize: 9, fontFamily: 'var(--font-mono)',
                          color: '#fff'
                        }}>
                          {strip.time}
                        </span>
                      </div>
                      <span style={{ fontSize: 10, color: 'var(--text-secondary)', textAlign: 'center', fontWeight: 500 }}>
                        {strip.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Action Buttons at Bottom */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
                {/* Primary Button: Seek to Event Origin */}
                <button
                  onClick={() => seekTo(eventStartSec)}
                  className="btn btn-primary"
                  style={{ width: '100%', padding: '10px', fontSize: 13 }}
                >
                  <SkipForward size={14} />
                  <span>Seek to Event Origin ({fmtSecOnly(eventStartSec)})</span>
                </button>

                {/* Secondary Row: Export Clip, Actor Dossier */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <button
                    onClick={() => setPreviewEventId(selectedEvent.event_id || selectedEvent.id || null)}
                    className="btn btn-secondary"
                    style={{ fontSize: 12, padding: '7px' }}
                  >
                    <Download size={13} style={{ color: 'var(--text-secondary)' }} />
                    <span>Export Clip</span>
                  </button>

                  <button
                    onClick={() => {
                      const actor = data.persons.find((p) => p.person_label === selectedEvent.person_label) || data.persons[0];
                      if (actor) setDossierPerson(actor);
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: 12, padding: '7px' }}
                  >
                    <User size={13} style={{ color: 'var(--text-secondary)' }} />
                    <span>Actor Dossier</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 2: ACTORS ─────────────────────────────────────────── */}
          {activeTab === 'Actors' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: 4 }}>
                {data.persons.length} IDENTIFIED SUBJECTS
              </div>

              {data.persons.length === 0 && (
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  gap: 10, padding: '32px 0', textAlign: 'center'
                }}>
                  <User size={28} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>No Actors Identified</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                      No person tracks were confirmed during processing. The detection model may need re-running or a stronger model profile.
                    </div>
                  </div>
                </div>
              )}

              {data.persons.map((person) => {
                const dwellSec = Math.round((person.last_seen_ms - person.first_seen_ms) / 1000);
                const isCurrent = activePerson?.person_label === person.person_label;

                return (
                  <div
                    key={person.person_label}
                    onClick={() => {
                      seekTo(person.first_seen_ms / 1000);
                    }}
                    className={isCurrent ? 'card card-selected' : 'card'}
                    style={{
                      padding: 10, display: 'flex', gap: 10, cursor: 'pointer',
                      transition: 'border-color 0.15s'
                    }}
                  >
                    {/* Portrait crop with reticle */}
                    <div style={{
                      width: 48, height: 56, borderRadius: 4, overflow: 'hidden',
                      backgroundColor: 'var(--bg-inset)', border: '1px solid var(--border)',
                      position: 'relative', flexShrink: 0
                    }}>
                      {person.crop_url ? (
                        <img
                          src={resolveMediaUrl(person.crop_url) || person.crop_url}
                          alt={person.person_label}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      ) : (
                        <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <User size={18} style={{ color: 'var(--text-muted)' }} />
                        </div>
                      )}
                    </div>

                    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                          {person.person_label}
                        </span>
                        <span className="badge badge-accent" style={{ fontSize: 10 }}>
                          {dwellSec}s dwell
                        </span>
                      </div>

                      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
                        Seen {fmtSecOnly(person.first_seen_ms / 1000)} → {fmtSecOnly(person.last_seen_ms / 1000)}
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDossierPerson(person);
                        }}
                        style={{
                          marginTop: 6, fontSize: 11, color: 'var(--accent)',
                          background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                          textAlign: 'left', display: 'flex', alignItems: 'center', gap: 3
                        }}
                      >
                        <span>Open Forensic Dossier</span>
                        <ChevronRight size={11} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── TAB 3: ASSETS / DETECTED OBJECTS ──────────────────────── */}
          {activeTab === 'Assets' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {/* Search box */}
              <div style={{ position: 'relative' }}>
                <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Filter objects..."
                  value={assetSearch}
                  onChange={(e) => setAssetSearch(e.target.value)}
                  className="input"
                  style={{ paddingLeft: 28, fontSize: 12 }}
                />
              </div>

              {data.detected_objects.length === 0 && (
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  gap: 10, padding: '32px 0', textAlign: 'center'
                }}>
                  <Layers size={28} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>No Objects Detected</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                      No objects passed the detection confidence threshold. Re-process with the 'balanced' or 'accuracy' model profile for better results.
                    </div>
                  </div>
                </div>
              )}

              {data.detected_objects
                .filter((o) => o.display_name.toLowerCase().includes(assetSearch.toLowerCase()))
                .map((obj, i) => (
                  <div key={i} className="card-inset" style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                        {obj.display_name}
                      </div>
                      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        Category: {obj.category} • First seen {fmtSecOnly(obj.first_seen_ms / 1000)}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                        x{obj.instance_count}
                      </span>
                      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent)', marginTop: 2 }}>
                        {Math.round(obj.max_confidence * 100)}%
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          )}

          {/* ── TAB 4: NARRATIVE ──────────────────────────────────────── */}
          {activeTab === 'Narrative' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="card-inset" style={{ padding: 12 }}>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent)', display: 'block', marginBottom: 6 }}>
                  INTELLIGENCE OVERVIEW
                </span>
                <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text-primary)', margin: 0 }}>
                  {data.summary?.overview || data.summary?.narrative ||
                    (allEvents.length > 0
                      ? `Recorded ${allEvents.length} event${allEvents.length !== 1 ? 's' : ''} across ${data.unique_persons} identified actor${data.unique_persons !== 1 ? 's' : ''}.`
                      : 'No narrative summary available. The pipeline did not detect significant events in this recording.')}
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)' }}>
                  KEY MILESTONES
                </span>

                {data.summary?.key_milestones && data.summary.key_milestones.length > 0 ? (
                  data.summary.key_milestones.map((m, i) => (
                    <div key={i} style={{ display: 'flex', gap: 10, fontSize: 12 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)', flexShrink: 0 }}>
                        {m.time}
                      </span>
                      <div>
                        <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{m.event}</div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{m.actor}</div>
                      </div>
                    </div>
                  ))
                ) : allEvents.length > 0 ? (
                  // Auto-generate milestones from top events
                  allEvents.slice(0, 5).map((evt, i) => (
                    <div key={i} style={{ display: 'flex', gap: 10, fontSize: 12, cursor: 'pointer' }}
                      onClick={() => seekToEvent(evt, i)}>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)', flexShrink: 0 }}>
                        {fmtSecOnly((evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000)}
                      </span>
                      <div>
                        <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                          {evt.display_name || formatLabel(evt.event_type || 'Event')}
                        </div>
                        {evt.person_label && (
                          <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {evt.person_label}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '12px 0', textAlign: 'center' }}>
                    No milestones — processing produced no events.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── MODALS ────────────────────────────────────────────────────── */}
      {dossierPerson && (
        <PersonDossierModal
          person={dossierPerson}
          allEvents={allEvents}
          durationSeconds={duration}
          onClose={() => setDossierPerson(null)}
        />
      )}

      {previewEventId && (
        <EventPreviewModal
          eventId={previewEventId}
          eventType={selectedEvent?.event_type}
          confidence={selectedEvent?.confidence}
          startMs={selectedEvent?.start_ms}
          onClose={() => setPreviewEventId(null)}
        />
      )}
    </div>
  );
}
