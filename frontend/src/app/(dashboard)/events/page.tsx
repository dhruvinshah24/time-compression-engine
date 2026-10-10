'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Film, Zap, AlertTriangle, User, Play, ChevronRight, Clock,
  SlidersHorizontal, ArrowUpRight, FileVideo, Sparkles, Filter, CheckCircle2
} from 'lucide-react';
import { api, API_BASE } from '@/lib/api/client';
import Link from 'next/link';

interface EventRecord {
  id?: string;
  event_id?: string;
  type?: string;
  event_type?: string;
  timestamp_ms?: number;
  start_ms?: number;
  end_ms?: number;
  confidence?: number;
  video_id?: string;
  person_label?: string;
  rule_name?: string;
  display_name?: string;
  evidence?: {
    description?: string;
    direction?: string;
  };
}

interface VideoRecord {
  id: string;
  filename?: string;
  metadata?: {
    duration_hms?: string;
    resolution?: string;
    fps?: number;
  };
}

const getEventType = (e: EventRecord) => e.event_type ?? e.type ?? '';
const getEventId = (e: EventRecord) => e.event_id ?? e.id ?? '';
const getTimeSec = (e: EventRecord) => ((e.start_ms ?? e.timestamp_ms ?? 0) / 1000);

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(1);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

function formatEventLabel(et: string) {
  return et.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function EventsPage() {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [videos, setVideos] = useState<VideoRecord[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [minConf, setMinConf] = useState(0);
  const [selectedPerson, setSelectedPerson] = useState<string>('all');

  useEffect(() => {
    let mounted = true;
    Promise.all([
      api.events.list({ limit: '300' }) as Promise<EventRecord[]>,
      api.videos.list() as Promise<VideoRecord[]>
    ])
      .then(([evts, vids]) => {
        if (mounted) {
          setEvents(Array.isArray(evts) ? evts : []);
          setVideos(Array.isArray(vids) ? vids : []);
          setLoading(false);
        }
      })
      .catch(err => {
        if (mounted) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => { mounted = false; };
  }, []);

  // Unique video IDs & persons
  const videoIds = useMemo(() => Array.from(new Set(events.map(e => e.video_id).filter(Boolean) as string[])), [events]);
  const personLabels = useMemo(() => Array.from(new Set(events.map(e => e.person_label).filter(Boolean) as string[])), [events]);

  // Group events by video
  const eventsByVideo = useMemo(() => {
    const map: Record<string, EventRecord[]> = {};
    for (const evt of events) {
      const vid = evt.video_id || 'unknown';
      if (!map[vid]) map[vid] = [];
      map[vid].push(evt);
    }
    return map;
  }, [events]);

  // Filtered video groups
  const filteredVideos = useMemo(() => {
    return Object.keys(eventsByVideo).filter(vid => {
      if (selectedVideoId !== 'all' && vid !== selectedVideoId) return false;
      return true;
    });
  }, [eventsByVideo, selectedVideoId]);

  return (
    <div className="flex flex-col gap-6 animate-slide-up pb-10">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-white/5 font-mono">
        <div>
          <div className="flex items-center gap-2 mb-1 text-xs text-white/40">
            <Link href="/" className="hover:text-white transition-colors">Dashboard</Link>
            <ChevronRight size={12} className="text-white/20" />
            <span className="text-cyan-400">Section-Wise Event Intelligence</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <FileVideo className="w-6 h-6 text-cyan-400" />
            Video-Wise Event Hub
          </h1>
          <p className="text-white/40 text-xs mt-1">
            Classified events neatly structured per CCTV video stream with direct instant playback.
          </p>
        </div>

        {/* Global Filter Bar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Video Selector */}
          <select
            value={selectedVideoId}
            onChange={e => setSelectedVideoId(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-[#0d1218] border border-white/10 text-xs text-cyan-300 focus:outline-none focus:border-cyan-400/50"
          >
            <option value="all">ALL VIDEOS ({videoIds.length})</option>
            {videoIds.map(vid => (
              <option key={vid} value={vid}>
                {vid} ({eventsByVideo[vid]?.length || 0} evts)
              </option>
            ))}
          </select>

          {/* Actor Selector */}
          <select
            value={selectedPerson}
            onChange={e => setSelectedPerson(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-[#0d1218] border border-white/10 text-xs text-white/80 focus:outline-none focus:border-cyan-400/50"
          >
            <option value="all">ALL ACTORS</option>
            {personLabels.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Videos & Events Stream */}
      {loading ? (
        <div className="min-h-[50vh] flex flex-col items-center justify-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-cyan-400/20 border-t-cyan-400 animate-spin" />
          <span className="text-xs font-mono text-white/40">Loading section-wise video telemetry...</span>
        </div>
      ) : error ? (
        <div className="surface-card p-6 rounded-2xl border border-rose-500/30 text-center max-w-md mx-auto">
          <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto mb-2" />
          <p className="text-sm text-white font-bold">{error}</p>
        </div>
      ) : filteredVideos.length === 0 ? (
        <div className="surface-card p-12 rounded-2xl border text-center text-white/40 font-mono text-xs">
          No events found matching active filter criteria.
        </div>
      ) : (
        <div className="space-y-6">
          {filteredVideos.map(vid => {
            const videoEvents = (eventsByVideo[vid] || []).filter(e => {
              if (selectedPerson !== 'all' && e.person_label !== selectedPerson) return false;
              if (minConf > 0 && (e.confidence ?? 0) < minConf / 100) return false;
              return true;
            });

            if (videoEvents.length === 0) return null;

            const videoMeta = videos.find(v => v.id === vid);
            const filename = videoMeta?.filename || vid;

            return (
              <div
                key={vid}
                className="surface-card rounded-2xl border border-white/[0.08] overflow-hidden shadow-2xl transition-all"
              >
                {/* Section Video Header */}
                <div className="p-4 bg-[#0a0e14] border-b border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-400/30 flex items-center justify-center text-cyan-400">
                      <Film size={18} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-sm font-bold text-white tracking-tight">{filename}</h2>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-400/10 border border-cyan-400/30 text-cyan-300">
                          {vid}
                        </span>
                      </div>
                      <p className="text-[11px] font-mono text-white/40 mt-0.5">
                        {videoEvents.length} events detected · {videoMeta?.metadata?.duration_hms || 'Processed Feed'}
                      </p>
                    </div>
                  </div>

                  <Link href={`/timeline/${vid}`}>
                    <button className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold text-xs shadow-lg transition-all">
                      <span>Open Video & Timeline</span>
                      <ArrowUpRight size={14} />
                    </button>
                  </Link>
                </div>

                {/* Section Events List */}
                <div className="divide-y divide-white/[0.03]">
                  {videoEvents.map((evt, idx) => {
                    const t = getTimeSec(evt);
                    const desc = evt.display_name || evt.evidence?.description || formatEventLabel(getEventType(evt));

                    return (
                      <div
                        key={getEventId(evt) || idx}
                        className="p-3.5 hover:bg-white/[0.02] transition-colors flex items-center gap-4 group"
                      >
                        {/* Time badge */}
                        <div className="w-16 shrink-0 flex items-center gap-1.5 text-xs font-mono font-bold text-cyan-300">
                          <Clock size={12} className="text-white/40" />
                          <span>{fmtTime(t)}</span>
                        </div>

                        {/* Actor pill */}
                        <div className="w-24 shrink-0">
                          {evt.person_label ? (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-400/10 border border-amber-400/30 text-amber-300 font-bold flex items-center gap-1 w-fit">
                              <User size={10} />
                              {evt.person_label}
                            </span>
                          ) : (
                            <span className="text-[10px] font-mono text-white/30">—</span>
                          )}
                        </div>

                        {/* Event narrative description */}
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-white/90 truncate group-hover:text-cyan-200 transition-colors">
                            {desc}
                          </p>
                          <span className="text-[10px] font-mono text-white/30 capitalize">
                            {formatEventLabel(getEventType(evt))}
                          </span>
                        </div>

                        {/* Confidence bar */}
                        <div className="shrink-0 hidden md:flex items-center gap-2 font-mono text-[10px] text-white/40">
                          <span>{Math.round((evt.confidence ?? 0.85) * 100)}% conf</span>
                        </div>

                        {/* Quick Jump Action */}
                        <Link
                          href={`/timeline/${vid}?time=${evt.start_ms ?? evt.timestamp_ms ?? 0}`}
                          className="shrink-0"
                        >
                          <button
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-cyan-500/20 text-white/70 hover:text-cyan-300 border border-white/10 text-xs font-mono transition-colors"
                            title="Jump to moment in video player"
                          >
                            <Play size={10} />
                            <span>Jump</span>
                          </button>
                        </Link>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
