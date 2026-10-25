'use client';

import { useState } from 'react';
import {
  X, User, Clock, Eye, MapPin, Activity,
  ChevronRight, Target, ArrowRight,
  Shield, Film, BarChart2
} from 'lucide-react';
import { BACKEND_URL } from '@/lib/api/client';

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
  const msRem = Math.floor(ms % 1000);
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}.${String(msRem).padStart(3, '0')}`;
}

export default function PersonDossierModal({
  person, allEvents, durationSeconds, onClose,
}: PersonDossierModalProps) {
  const [view, setView] = useState<'portrait' | 'scene'>('portrait');
  const [imgError, setImgError] = useState(false);

  if (!person) return null;

  const personEvents = allEvents
    .filter((e) => e.person_label === person.person_label)
    .sort((a, b) => (a.start_ms ?? a.timestamp_ms ?? 0) - (b.start_ms ?? b.timestamp_ms ?? 0));

  const durationSec = (person.last_seen_ms - person.first_seen_ms) / 1000;
  const coverage = durationSeconds > 0 ? Math.min((durationSec / durationSeconds) * 100, 100) : 0;

  const cropSrc = person.crop_url
    ? person.crop_url.startsWith('http') ? person.crop_url : `${BACKEND_URL}${person.crop_url}`
    : null;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 16
    }}>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'absolute', inset: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(4px)'
        }}
      />

      {/* Modal Card */}
      <div
        className="card-raised"
        style={{
          position: 'relative', width: '100%', maxWidth: 780,
          borderRadius: 8, overflow: 'hidden', zIndex: 10,
          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          display: 'flex', flexDirection: 'column',
          maxHeight: '88vh'
        }}
      >
        {/* Header */}
        <div style={{
          padding: '14px 18px', backgroundColor: 'var(--bg-inset)',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 30, height: 30, borderRadius: 6,
              backgroundColor: 'var(--accent-bg)', border: '1px solid var(--accent-dim)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--accent)'
            }}>
              <Shield size={15} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
                  {person.person_label}
                </span>
                <span className="badge badge-accent" style={{ fontSize: 10 }}>
                  Active Subject
                </span>
              </div>
              <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                Visual Dossier & Continuity Log
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="btn btn-ghost"
            style={{ width: 28, height: 28, padding: 0 }}
          >
            <X size={15} />
          </button>
        </div>

        {/* Content Body */}
        <div style={{
          display: 'grid', gridTemplateColumns: '280px 1fr',
          overflowY: 'auto', flex: 1
        }}>
          {/* Left: Portrait Frame & Identity */}
          <div style={{
            padding: 16, borderRight: '1px solid var(--border)',
            backgroundColor: 'var(--bg-panel)',
            display: 'flex', flexDirection: 'column', gap: 14
          }}>
            <div style={{
              width: '100%', height: 260, borderRadius: 6, overflow: 'hidden',
              backgroundColor: '#0D1013', border: '1px solid var(--border)',
              position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              {cropSrc && !imgError ? (
                <img
                  src={cropSrc}
                  alt={person.person_label}
                  onError={() => setImgError(true)}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, color: 'var(--text-muted)' }}>
                  <User size={36} />
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>No biometric crop</span>
                </div>
              )}

              {/* Corner reticles */}
              <div style={{ position: 'absolute', top: 6, left: 6, width: 8, height: 8, borderTop: '2px solid var(--accent)', borderLeft: '2px solid var(--accent)' }} />
              <div style={{ position: 'absolute', top: 6, right: 6, width: 8, height: 8, borderTop: '2px solid var(--accent)', borderRight: '2px solid var(--accent)' }} />
              <div style={{ position: 'absolute', bottom: 6, left: 6, width: 8, height: 8, borderBottom: '2px solid var(--accent)', borderLeft: '2px solid var(--accent)' }} />
              <div style={{ position: 'absolute', bottom: 6, right: 6, width: 8, height: 8, borderBottom: '2px solid var(--accent)', borderRight: '2px solid var(--accent)' }} />
            </div>

            {/* Quick Metrics */}
            <div className="card-inset" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>First Observed:</span>
                <span style={{ color: 'var(--text-primary)' }}>{fmtTimecode(person.first_seen_ms)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Last Observed:</span>
                <span style={{ color: 'var(--text-primary)' }}>{fmtTimecode(person.last_seen_ms)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Dwell Duration:</span>
                <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{durationSec.toFixed(1)}s</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Frame Detections:</span>
                <span style={{ color: 'var(--text-primary)' }}>{person.observation_count} frames</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Entry Vector:</span>
                <span style={{ color: 'var(--text-secondary)' }}>{person.entry_direction || 'Left / Corridor'}</span>
              </div>
            </div>
          </div>

          {/* Right: Actions & Events Timeline */}
          <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                Temporal Event Participation
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                {personEvents.length} events logged involving this subject
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 380, overflowY: 'auto' }}>
              {personEvents.length === 0 ? (
                <div className="card-inset" style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                  No discrete events linked directly to this actor.
                </div>
              ) : (
                personEvents.map((evt, idx) => {
                  const ms = evt.start_ms ?? evt.timestamp_ms ?? 0;
                  return (
                    <div
                      key={idx}
                      className="card-inset"
                      style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                    >
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                          {evt.display_name || evt.event_type?.replace(/_/g, ' ')}
                        </div>
                        <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
                          At {fmtTimecode(ms)} • {evt.confidence ? `${Math.round(evt.confidence * 100)}% verified` : 'Observed'}
                        </div>
                      </div>
                      <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                        {fmtTimecode(ms).slice(0, 5)}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
