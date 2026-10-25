'use client';

import { useEffect, useState } from 'react';
import {
  X, Loader2, AlertCircle, Play, Clock, User,
  Shield, Info, Eye, MapPin, TrendingUp, Zap, CheckCircle2
} from 'lucide-react';
import { API_BASE } from '@/lib/api/client';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

interface EventPreview {
  event_id: string;
  event_type: string;
  event_time_ms: number;
  confidence: number;
  track_id?: number | string;
  person_label?: string;
  frames: {
    before: { path: string | null; url: string | null; available: boolean };
    event:  { path: string | null; url: string | null; available: boolean };
    after:  { path: string | null; url: string | null; available: boolean };
  };
  thumbnail_url: string | null;
  clip_url: string | null;
  evidence: {
    lighting_condition?: string;
    preprocessing_mode?: string;
    zone_id?: string;
    direction?: string;
    description?: string;
  };
}

interface Props {
  eventId: string;
  eventType?: string;
  confidence?: number;
  startMs?: number;
  onClose: () => void;
}

function formatMs(ms: number): string {
  const total = ms / 1000;
  const m = Math.floor(total / 60);
  const s = (total % 60).toFixed(1);
  return m > 0 ? `${m}:${s.padStart(4, '0')}` : `${s}s`;
}

function formatEventType(et: string): string {
  return et.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function FrameImage({
  url, label, active = false,
}: { url: string | null; label: string; active?: boolean }) {
  const [errored, setErrored] = useState(false);
  const [loaded, setLoaded] = useState(false);

  if (!url) {
    return (
      <div
        className="card-inset"
        style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          minHeight: 120, padding: 12, textAlign: 'center'
        }}
      >
        <AlertCircle size={16} style={{ color: 'var(--text-muted)', marginBottom: 6 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
          Frame artifact pending
        </span>
      </div>
    );
  }

  const src = url.startsWith('/') ? `${BACKEND}${url}` : url;

  if (errored) {
    return (
      <div
        className="card-inset"
        style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          minHeight: 120, padding: 12, textAlign: 'center'
        }}
      >
        <AlertCircle size={16} style={{ color: 'var(--warning)', marginBottom: 6 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>
          Artifact missing
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'relative', borderRadius: 6, overflow: 'hidden',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
        minHeight: 120, backgroundColor: '#0D1013'
      }}
    >
      <img
        src={src}
        alt={label}
        style={{ width: '100%', height: '100%', objectFit: 'cover', maxHeight: 150 }}
        onLoad={() => setLoaded(true)}
        onError={() => setErrored(true)}
      />
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        padding: '3px 6px', backgroundColor: 'rgba(19, 22, 24, 0.85)',
        fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
        textAlign: 'center', borderTop: '1px solid var(--border-dim)'
      }}>
        {label}
      </div>
      {active && (
        <div style={{
          position: 'absolute', top: 4, right: 4,
          padding: '1px 5px', borderRadius: 3,
          backgroundColor: 'var(--accent)', color: '#1a1f1b',
          fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700
        }}>
          EVENT PEAK
        </div>
      )}
    </div>
  );
}

export default function EventPreviewModal({ eventId, eventType, confidence, startMs, onClose }: Props) {
  const [preview, setPreview] = useState<EventPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clipPlaying, setClipPlaying] = useState(false);

  useEffect(() => {
    if (!eventId) return;
    setLoading(true);
    setError(null);

    fetch(`${API_BASE}/events/${eventId}/preview`)
      .then((r) => {
        if (!r.ok) throw new Error(`Preview unavailable (${r.status})`);
        return r.json();
      })
      .then((data) => {
        setPreview(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Could not load preview');
        setLoading(false);
      });
  }, [eventId]);

  const clipApiUrl = `${API_BASE}/events/${eventId}/clip`;
  const displayEventType = preview?.event_type ?? eventType ?? 'Event';
  const displayConf = preview?.confidence ?? confidence;
  const displayMs = preview?.event_time_ms ?? startMs ?? 0;
  const trackLabel = preview?.person_label ?? (preview?.track_id ? `Track ${preview.track_id}` : null);

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

      {/* Modal Window */}
      <div
        className="card-raised"
        style={{
          position: 'relative', width: '100%', maxWidth: 640,
          borderRadius: 8, overflow: 'hidden', zIndex: 10,
          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          display: 'flex', flexDirection: 'column'
        }}
      >
        {/* Header */}
        <div style={{
          padding: '14px 18px', backgroundColor: 'var(--bg-inset)',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
              <span className="badge badge-accent" style={{ fontSize: 10 }}>
                Verification Frame Context
              </span>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                {eventId}
              </span>
            </div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              {formatEventType(displayEventType)}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>TC: {formatMs(displayMs)}</span>
              {displayConf !== undefined && (
                <span style={{ color: 'var(--accent)' }}>
                  {Math.round(displayConf * 100)}% verified
                </span>
              )}
              {trackLabel && (
                <span style={{ color: 'var(--text-muted)' }}>
                  {trackLabel}
                </span>
              )}
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

        {/* Modal Body */}
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 16, maxHeight: '75vh', overflowY: 'auto' }}>
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 0', gap: 8, color: 'var(--text-muted)' }}>
              <div style={{ width: 22, height: 22, borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: 'var(--accent)', animation: 'spin 0.8s linear infinite' }} />
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>Loading frame sequence...</span>
            </div>
          ) : error ? (
            <div style={{ textAlign: 'center', padding: '30px 0' }}>
              <AlertCircle size={24} style={{ color: 'var(--warning)', margin: '0 auto 8px' }} />
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>{error}</p>
            </div>
          ) : preview ? (
            <>
              {/* Before / Peak / After Frames */}
              <div>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: 8 }}>
                  TEMPORAL EVIDENCE SEQUENCE
                </span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                  <FrameImage url={preview.frames.before.url} label="T-Before" />
                  <FrameImage url={preview.frames.event.url} label="T-Event Peak" active={true} />
                  <FrameImage url={preview.frames.after.url} label="T-After" />
                </div>
              </div>

              {/* Clip Video Player or Play Trigger */}
              {clipPlaying ? (
                <div style={{ borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)', backgroundColor: '#000' }}>
                  <video controls autoPlay style={{ width: '100%', maxHeight: 220 }} onError={() => setClipPlaying(false)}>
                    <source src={clipApiUrl} type="video/mp4" />
                  </video>
                </div>
              ) : (
                <button
                  onClick={() => setClipPlaying(true)}
                  className="btn btn-secondary"
                  style={{ width: '100%', padding: '10px', fontSize: 12 }}
                >
                  <Play size={13} style={{ color: 'var(--accent)' }} />
                  <span>Stream Event Video Snippet</span>
                </button>
              )}

              {/* Evidence Metadata */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                {preview.evidence.description && (
                  <div className="card-inset" style={{ gridColumn: 'span 2', padding: 10 }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: 10, marginBottom: 2 }}>EVIDENCE LOG</div>
                    <div style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', fontSize: 12, lineHeight: 1.5 }}>
                      {preview.evidence.description}
                    </div>
                  </div>
                )}
                <div className="card-inset" style={{ padding: 10 }}>
                  <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>VECTOR DIRECTION</div>
                  <div style={{ color: 'var(--text-secondary)', marginTop: 2 }}>{preview.evidence.direction || 'In-frame'}</div>
                </div>
                <div className="card-inset" style={{ padding: 10 }}>
                  <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>SCENE ILLUMINATION</div>
                  <div style={{ color: 'var(--success)', marginTop: 2 }}>{preview.evidence.lighting_condition || 'Normal'}</div>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
