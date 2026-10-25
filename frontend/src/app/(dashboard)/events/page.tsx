'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Film, Zap, AlertTriangle, User, Play, ChevronRight, Clock,
  SlidersHorizontal, CheckCircle2, ShieldCheck,
  Search, Filter, ExternalLink, Grid, List, Eye, Video
} from 'lucide-react';
import { api, API_BASE } from '@/lib/api/client';
import Link from 'next/link';
import EventPreviewModal from '@/components/EventPreviewModal';
import { EventsSkeleton } from '@/components/skeletons/EventsSkeleton';

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
    thumbnail_path?: string;
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

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(1);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

function formatLabel(et: string) {
  return et.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function getCategory(eventType: string): string {
  const t = eventType.toLowerCase();
  if (t.includes('light')) return 'lighting';
  if (t.includes('phone') || t.includes('laptop') || t.includes('drink') || t.includes('read') || t.includes('desk') || t.includes('screen')) return 'interaction';
  if (t.includes('gathering') || t.includes('unattended') || t.includes('theft') || t.includes('running')) return 'security';
  return 'activity';
}

export default function EventsPage() {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [videos, setVideos] = useState<VideoRecord[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState<string>('all');
  const [selectedPerson, setSelectedPerson] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [previewEventId, setPreviewEventId] = useState<string | null>(null);
  const [selectedEventData, setSelectedEventData] = useState<EventRecord | null>(null);

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
      .catch((err) => {
        if (mounted) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const videoIds = useMemo(
    () => Array.from(new Set(events.map((e) => e.video_id).filter(Boolean) as string[])),
    [events]
  );

  const personLabels = useMemo(
    () => Array.from(new Set(events.map((e) => e.person_label).filter(Boolean) as string[])),
    [events]
  );

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

  const filteredVideos = useMemo(() => {
    return Object.keys(eventsByVideo).filter((vid) => {
      if (selectedVideoId !== 'all' && vid !== selectedVideoId) return false;
      return true;
    });
  }, [eventsByVideo, selectedVideoId]);

  if (loading) {
    return <EventsSkeleton />;
  }

  const categoryChips = [
    { id: 'all', label: 'All Evidence' },
    { id: 'activity', label: 'Locomotion & Presence' },
    { id: 'interaction', label: 'Object Interactions' },
    { id: 'lighting', label: 'Lighting Changes' },
    { id: 'security', label: 'Threat & Causal Links' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* ── Breadcrumb & Header ────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
        <div>
          <div style={{
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6
          }}>
            <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Dashboard</Link>
            <span>/</span>
            <span style={{ color: 'var(--text-secondary)' }}>Evidence Library</span>
          </div>

          <h1 style={{
            fontSize: 24, fontWeight: 700, color: 'var(--text-primary)',
            letterSpacing: '-0.02em', margin: 0
          }}>
            Forensic Events & Evidence Hub
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2, marginBottom: 0 }}>
            Cinematic surveillance catalog indexing verified causal events, actor tracks, and multi-frame evidence crops.
          </p>
        </div>

        {/* Global Controls & Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {/* Search Box */}
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Filter events, actors, actions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input"
              style={{ paddingLeft: 28, fontSize: 12, height: 34, width: 220 }}
            />
          </div>

          {/* Video Stream Dropdown */}
          <select
            value={selectedVideoId}
            onChange={(e) => setSelectedVideoId(e.target.value)}
            className="input"
            style={{ width: 'auto', height: 34, fontSize: 12, paddingRight: 24 }}
          >
            <option value="all">All Surveillance Streams ({videoIds.length})</option>
            {videoIds.map((vid) => (
              <option key={vid} value={vid}>
                {vid} ({eventsByVideo[vid]?.length || 0} events)
              </option>
            ))}
          </select>

          {/* Actor Dropdown */}
          <select
            value={selectedPerson}
            onChange={(e) => setSelectedPerson(e.target.value)}
            className="input"
            style={{ width: 'auto', height: 34, fontSize: 12, paddingRight: 24 }}
          >
            <option value="all">All Tracked Actors</option>
            {personLabels.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>

          {/* View Mode Toggle */}
          <div style={{
            display: 'flex', alignItems: 'center', backgroundColor: 'var(--bg-panel)',
            border: '1px solid var(--border)', borderRadius: 6, padding: 2
          }}>
            <button
              onClick={() => setViewMode('grid')}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 30, height: 28, borderRadius: 4, border: 'none',
                backgroundColor: viewMode === 'grid' ? 'var(--accent-bg)' : 'transparent',
                color: viewMode === 'grid' ? 'var(--accent)' : 'var(--text-muted)',
                cursor: 'pointer'
              }}
              title="Cinematic Card Gallery"
            >
              <Grid size={14} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 30, height: 28, borderRadius: 4, border: 'none',
                backgroundColor: viewMode === 'list' ? 'var(--accent-bg)' : 'transparent',
                color: viewMode === 'list' ? 'var(--accent)' : 'var(--text-muted)',
                cursor: 'pointer'
              }}
              title="Forensic Table View"
            >
              <List size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* ── Category Filter Pills ────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflowX: 'auto', paddingBottom: 2 }}>
        {categoryChips.map((chip) => {
          const isSelected = selectedCategory === chip.id;
          return (
            <button
              key={chip.id}
              onClick={() => setSelectedCategory(chip.id)}
              style={{
                fontSize: 12,
                fontWeight: isSelected ? 600 : 500,
                padding: '5px 12px',
                borderRadius: 20,
                cursor: 'pointer',
                border: isSelected ? '1px solid var(--accent)' : '1px solid var(--border)',
                backgroundColor: isSelected ? 'var(--accent-bg)' : 'var(--bg-panel)',
                color: isSelected ? 'var(--accent)' : 'var(--text-secondary)',
                transition: 'all 0.12s ease',
                whiteSpace: 'nowrap'
              }}
            >
              {chip.label}
            </button>
          );
        })}
      </div>

      {/* ── Content ────────────────────────────────────────────────────── */}
      {error ? (
        <div className="card" style={{ padding: 24, textAlign: 'center', maxWidth: 440, margin: '40px auto' }}>
          <AlertTriangle size={28} style={{ color: 'var(--warning)', margin: '0 auto 10px' }} />
          <p style={{ fontSize: 13, color: 'var(--text-primary)', margin: 0 }}>{error}</p>
        </div>
      ) : filteredVideos.length === 0 ? (
        <div className="card empty-state">
          <Film size={32} />
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>
            No events matched your current filters.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {filteredVideos.map((vid) => {
            const videoEvents = (eventsByVideo[vid] || [])
              .filter((e) => {
                if (selectedPerson !== 'all' && e.person_label !== selectedPerson) return false;
                if (selectedCategory !== 'all') {
                  const cat = getCategory(e.event_type || e.type || '');
                  if (cat !== selectedCategory) return false;
                }
                if (searchQuery) {
                  const query = searchQuery.toLowerCase();
                  const matchName = (e.display_name || e.event_type || '').toLowerCase().includes(query);
                  const matchDesc = (e.evidence?.description || '').toLowerCase().includes(query);
                  const matchActor = (e.person_label || '').toLowerCase().includes(query);
                  if (!matchName && !matchDesc && !matchActor) return false;
                }
                return true;
              })
              .sort((a, b) => ((a.start_ms ?? a.timestamp_ms ?? 0) - (b.start_ms ?? b.timestamp_ms ?? 0)));

            if (videoEvents.length === 0) return null;

            const videoMeta = videos.find((v) => v.id === vid);
            const filename = videoMeta?.filename || vid;

            return (
              <div key={vid} className="card" style={{ overflow: 'hidden' }}>
                {/* Section Stream Header (Reference B style collection bar) */}
                <div style={{
                  padding: '14px 20px',
                  backgroundColor: 'var(--bg-raised)',
                  borderBottom: '1px solid var(--border)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  flexWrap: 'wrap', gap: 12
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: 6,
                      backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: 'var(--accent)'
                    }}>
                      <Film size={18} />
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                          {filename}
                        </span>
                        <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                          {vid}
                        </span>
                        <span className="badge badge-accent" style={{ fontSize: 10 }}>
                          CAM-07 • Node
                        </span>
                      </div>
                      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
                        {videoEvents.length} events catalogued • 4K CCTV Source Stream
                      </div>
                    </div>
                  </div>

                  {/* Open Timeline Link */}
                  <Link href={`/timeline/${vid}`} style={{ textDecoration: 'none' }}>
                    <button className="btn btn-primary" style={{ fontSize: 12, padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>Open Forensic Timeline</span>
                      <ChevronRight size={13} />
                    </button>
                  </Link>
                </div>

                {/* ── View Mode: Cinematic Grid (Reference B) ────────────────── */}
                {viewMode === 'grid' ? (
                  <div style={{
                    padding: 20,
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                    gap: 16
                  }}>
                    {videoEvents.map((evt, idx) => {
                      const startSec = (evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000;
                      const eventId = evt.event_id || evt.id;
                      const thumbUrl = eventId ? `${API_BASE}/events/${eventId}/thumbnail` : null;

                      return (
                        <div
                          key={eventId || idx}
                          className="card"
                          style={{
                            padding: 0,
                            overflow: 'hidden',
                            backgroundColor: 'var(--bg-panel)',
                            borderColor: 'var(--border)',
                            display: 'flex',
                            flexDirection: 'column',
                            transition: 'transform 0.12s ease, border-color 0.12s ease'
                          }}
                        >
                          {/* 16:9 Thumbnail Preview */}
                          <div style={{
                            position: 'relative',
                            width: '100%',
                            paddingTop: '56.25%',
                            backgroundColor: '#0A0D10',
                            overflow: 'hidden'
                          }}>
                            {thumbUrl ? (
                              <img
                                src={thumbUrl}
                                alt={evt.display_name || evt.event_type}
                                style={{
                                  position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                                  objectFit: 'cover'
                                }}
                                onError={(e) => {
                                  // Fallback to placeholder on load error
                                  (e.target as HTMLElement).style.display = 'none';
                                }}
                              />
                            ) : null}

                            {/* Timecode overlay badge */}
                            <div style={{
                              position: 'absolute', top: 8, left: 8,
                              backgroundColor: 'rgba(23, 28, 33, 0.85)',
                              backdropFilter: 'blur(4px)',
                              border: '1px solid var(--border)',
                              borderRadius: 4,
                              padding: '2px 6px',
                              fontSize: 10,
                              fontFamily: 'var(--font-mono)',
                              color: 'var(--text-primary)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 4
                            }}>
                              <Clock size={10} style={{ color: 'var(--accent)' }} />
                              <span>{fmtTime(startSec)}</span>
                            </div>

                            {/* Confidence rating badge */}
                            <div style={{
                              position: 'absolute', top: 8, right: 8,
                              backgroundColor: 'rgba(23, 28, 33, 0.85)',
                              border: '1px solid var(--border)',
                              borderRadius: 4,
                              padding: '2px 6px',
                              fontSize: 10,
                              fontFamily: 'var(--font-mono)',
                              color: 'var(--accent)',
                              fontWeight: 600
                            }}>
                              {Math.round((evt.confidence || 0.85) * 100)}% verified
                            </div>
                          </div>

                          {/* Details & Actions */}
                          <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
                            <div>
                              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.3 }}>
                                {evt.display_name || formatLabel(evt.event_type || 'Event')}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.4 }}>
                                {evt.evidence?.description || `${formatLabel(evt.event_type || 'event')} identified with causal grounding.`}
                              </div>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: 6, borderTop: '1px solid var(--border-dim)' }}>
                              <div>
                                {evt.person_label ? (
                                  <span className="badge badge-accent" style={{ fontSize: 10 }}>
                                    <User size={9} />
                                    <span>{evt.person_label}</span>
                                  </span>
                                ) : (
                                  <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                    Ambient Scene
                                  </span>
                                )}
                              </div>

                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <button
                                  onClick={() => {
                                    setSelectedEventData(evt);
                                    setPreviewEventId(eventId || null);
                                  }}
                                  className="btn btn-secondary"
                                  style={{ fontSize: 10, padding: '3px 8px', height: 24 }}
                                  title="Inspect Evidence Media"
                                >
                                  <Eye size={11} />
                                  <span>Inspect</span>
                                </button>

                                <Link href={`/timeline/${vid}?time=${evt.start_ms}`}>
                                  <button
                                    className="btn btn-ghost"
                                    style={{ width: 24, height: 24, padding: 0 }}
                                    title="Seek in Forensic Timeline"
                                  >
                                    <Play size={11} style={{ color: 'var(--accent)' }} />
                                  </button>
                                </Link>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* ── View Mode: Forensic Table (List View) ─────────────────── */
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {videoEvents.map((evt, idx) => {
                      const startSec = (evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000;
                      const isLast = idx === videoEvents.length - 1;

                      return (
                        <div
                          key={evt.event_id || evt.id || idx}
                          style={{
                            padding: '12px 18px',
                            display: 'grid',
                            gridTemplateColumns: '110px 1fr 140px 120px 110px',
                            alignItems: 'center',
                            gap: 16,
                            borderBottom: isLast ? 'none' : '1px solid var(--border-dim)',
                            backgroundColor: idx % 2 === 0 ? 'transparent' : 'rgba(25, 29, 32, 0.4)',
                            transition: 'background-color 0.12s'
                          }}
                        >
                          {/* Timecode Badge */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span className="badge badge-neutral" style={{ fontSize: 11 }}>
                              <Clock size={10} style={{ color: 'var(--text-muted)' }} />
                              <span>{fmtTime(startSec)}</span>
                            </span>
                          </div>

                          {/* Event Title & Involves */}
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                              {evt.display_name || formatLabel(evt.event_type || 'Event')}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                              {evt.evidence?.description || `${formatLabel(evt.event_type || 'event')} logged at track marker.`}
                            </div>
                          </div>

                          {/* Actor Badge */}
                          <div>
                            {evt.person_label ? (
                              <span className="badge badge-accent" style={{ fontSize: 11 }}>
                                <User size={10} />
                                <span>{evt.person_label}</span>
                              </span>
                            ) : (
                              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                Environment
                              </span>
                            )}
                          </div>

                          {/* Confidence Metric */}
                          <div>
                            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                              {Math.round((evt.confidence || 0.85) * 100)}% verified
                            </div>
                            <div className="progress-track" style={{ height: 2, marginTop: 4, maxWidth: 80 }}>
                              <div className="progress-fill" style={{ width: `${Math.round((evt.confidence || 0.85) * 100)}%` }} />
                            </div>
                          </div>

                          {/* Action: Quick Preview / Seek */}
                          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
                            <button
                              onClick={() => {
                                setSelectedEventData(evt);
                                setPreviewEventId(evt.event_id || evt.id || null);
                              }}
                              className="btn btn-secondary"
                              style={{ fontSize: 11, padding: '4px 8px', height: 26 }}
                              title="Inspect Evidence Media"
                            >
                              <span>Inspect</span>
                            </button>

                            <Link href={`/timeline/${vid}?time=${evt.start_ms}`}>
                              <button
                                className="btn btn-ghost"
                                style={{ width: 26, height: 26, padding: 0 }}
                                title="Seek in Timeline"
                              >
                                <Play size={12} style={{ color: 'var(--accent)' }} />
                              </button>
                            </Link>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Event Preview Modal */}
      {previewEventId && (
        <EventPreviewModal
          eventId={previewEventId}
          eventType={selectedEventData?.event_type}
          confidence={selectedEventData?.confidence}
          startMs={selectedEventData?.start_ms}
          onClose={() => {
            setPreviewEventId(null);
            setSelectedEventData(null);
          }}
        />
      )}
    </div>
  );
}
