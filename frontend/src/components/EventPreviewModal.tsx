'use client';

/**
 * EventPreviewModal
 *
 * Displays real event media: before frame / event frame / after frame,
 * event thumbnail, clip player, evidence chain.
 *
 * Fetches from GET /api/v1/events/{event_id}/preview
 * Images served from GET /outputs/{path} (static files)
 * Clip served from GET /api/v1/events/{event_id}/clip
 */

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Loader2, AlertCircle, Play, Clock, User,
  Shield, Info, Eye, MapPin, TrendingUp, Zap, Sparkles
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
  return et.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/** Show an image from the backend outputs static path */
function FrameImage({
  url, label, active = false,
}: { url: string | null; label: string; active?: boolean }) {
  const [errored, setErrored] = useState(false);
  const [loaded, setLoaded] = useState(false);

  if (!url) {
    return (
      <div className={`flex flex-col items-center justify-center rounded-2xl border text-center p-4 transition-all
        ${active ? 'border-indigo-500/40 surface-card shadow-[0_0_15px_rgba(99,102,241,0.15)]' : 'border-white/5 surface-inset'}`}
        style={{ minHeight: 140 }}
      >
        <AlertCircle size={18} className="text-white/20 mb-2" />
        <p className="text-xs font-semibold text-white/50">{label}</p>
        <p className="text-[10px] font-mono text-white/25 mt-0.5">Telemetry frame pending</p>
      </div>
    );
  }

  const src = url.startsWith('/') ? `${BACKEND}${url}` : url;

  if (errored) {
    return (
      <div className={`flex flex-col items-center justify-center rounded-2xl border text-center p-4 transition-all
        ${active ? 'border-rose-500/30 bg-rose-500/5' : 'border-white/5 surface-inset'}`}
        style={{ minHeight: 140 }}
      >
        <AlertCircle size={18} className="text-rose-400/50 mb-2" />
        <p className="text-xs font-semibold text-white/50">{label}</p>
        <p className="text-[10px] font-mono text-rose-400/40 mt-0.5">Frame not on storage disk</p>
      </div>
    );
  }

  return (
    <div className={`relative rounded-2xl overflow-hidden border transition-all
      ${active ? 'border-indigo-500/50 ring-2 ring-indigo-500/30 shadow-[0_0_20px_rgba(99,102,241,0.2)]' : 'border-white/10'}`}
      style={{ minHeight: 140 }}
    >
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center surface-inset">
          <Loader2 size={16} className="animate-spin text-indigo-400" />
        </div>
      )}
      <img
        src={src}
        alt={label}
        className={`w-full h-full object-cover transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
        style={{ maxHeight: 200 }}
        onLoad={() => setLoaded(true)}
        onError={() => setErrored(true)}
      />
      <div className="absolute bottom-0 left-0 right-0 py-1.5 px-2.5 bg-black/75 backdrop-blur-md text-[10px] font-mono text-white/70 text-center border-t border-white/5">
        {label}
      </div>
      {active && (
        <div className="absolute top-2 right-2 px-2.5 py-0.5 rounded-full bg-indigo-600 text-[9px] text-white font-mono font-bold shadow-[0_0_10px_rgba(99,102,241,0.5)]">
          PEAK EVENT
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
      .then(r => {
        if (!r.ok) throw new Error(`Preview not available (${r.status})`);
        return r.json();
      })
      .then(data => {
        setPreview(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message || 'Could not load preview');
        setLoading(false);
      });
  }, [eventId]);

  const clipApiUrl = `${API_BASE}/events/${eventId}/clip`;

  const displayEventType = preview?.event_type ?? eventType ?? 'Event';
  const displayConf = preview?.confidence ?? confidence;
  const displayMs   = preview?.event_time_ms ?? startMs ?? 0;
  const trackLabel  = preview?.person_label ?? (preview?.track_id ? `Track ${preview.track_id}` : null);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        {/* Backdrop */}
        <motion.div
          className="absolute inset-0 bg-black/80 backdrop-blur-md"
          onClick={onClose}
        />

        {/* Modal Window */}
        <motion.div
          className="relative w-full max-w-2xl surface-card border rounded-3xl shadow-[0_0_50px_rgba(0,0,0,0.8)] overflow-hidden z-10"
          initial={{ scale: 0.96, opacity: 0, y: 15 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.96, opacity: 0, y: 15 }}
          transition={{ type: 'spring', stiffness: 350, damping: 32 }}
        >
          {/* Header */}
          <div className="flex items-start justify-between p-5 border-b border-white/5 surface-inset">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono uppercase tracking-widest text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                  Event Verification
                </span>
                <span className="text-[10px] font-mono text-white/30">{eventId}</span>
              </div>
              <h2 className="text-lg font-bold text-white tracking-tight">
                {formatEventType(displayEventType)}
              </h2>
              <div className="flex items-center gap-3 mt-1.5 font-mono text-xs">
                <span className="flex items-center gap-1.5 text-white/50">
                  <Clock size={12} className="text-indigo-400" /> {formatMs(displayMs)}
                </span>
                {displayConf !== undefined && (
                  <span className="flex items-center gap-1.5 text-emerald-400">
                    <Zap size={12} /> {Math.round(displayConf * 100)}% confidence
                  </span>
                )}
                {trackLabel && (
                  <span className="flex items-center gap-1.5 text-violet-300">
                    <User size={12} /> {trackLabel}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl surface-card border text-white/40 hover:text-white transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Modal Content */}
          <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto scrollbar-thin">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3 text-white/40">
                <Loader2 size={24} className="animate-spin text-indigo-400" />
                <span className="text-xs font-mono uppercase tracking-wider">Retrieving multi-frame buffer…</span>
              </div>
            ) : error ? (
              <div className="space-y-4">
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <AlertCircle size={32} className="text-white/20 mb-3" />
                  <p className="text-sm font-semibold text-white/70">{error}</p>
                  <p className="text-xs text-white/30 mt-1 max-w-sm">
                    Frame capture artifacts are generated during full video pipeline analysis.
                  </p>
                </div>
              </div>
            ) : preview ? (
              <>
                {/* Before / Peak / After Frames */}
                <div>
                  <p className="text-[10px] font-mono text-white/40 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                    <Eye size={12} className="text-indigo-400" /> Multi-Frame Verification Context
                  </p>
                  <div className="grid grid-cols-3 gap-3">
                    <FrameImage url={preview.frames.before.url} label="T-Before" />
                    <FrameImage url={preview.frames.event.url}  label="T-Event Peak" active={true} />
                    <FrameImage url={preview.frames.after.url}  label="T-After" />
                  </div>
                </div>

                {/* Clip player */}
                {clipPlaying ? (
                  <div className="rounded-2xl overflow-hidden border border-white/10 bg-black shadow-2xl">
                    <video
                      controls
                      autoPlay
                      className="w-full"
                      style={{ maxHeight: 240 }}
                      onError={() => setClipPlaying(false)}
                    >
                      <source src={clipApiUrl} type="video/mp4" />
                    </video>
                  </div>
                ) : (
                  <button
                    onClick={() => setClipPlaying(true)}
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-indigo-600/20 via-violet-600/20 to-indigo-600/20 border border-indigo-500/30 hover:border-indigo-500/60 text-indigo-300 hover:text-white transition-all text-xs font-mono font-medium shadow-[0_0_15px_rgba(99,102,241,0.15)]"
                  >
                    <Play size={14} className="text-indigo-400" />
                    Stream Event Video Snippet
                  </button>
                )}

                {/* Evidence / Telemetry */}
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  {preview.evidence.description && (
                    <div className="col-span-2 p-3.5 rounded-xl surface-inset border border-white/5">
                      <p className="text-white/40 uppercase tracking-wider text-[10px] mb-1 flex items-center gap-1">
                        <Info size={10} className="text-indigo-400" /> Synthetic Narrative
                      </p>
                      <p className="text-white/80 font-sans text-xs">{preview.evidence.description}</p>
                    </div>
                  )}
                  {preview.evidence.zone_id && (
                    <div className="p-3.5 rounded-xl surface-inset border border-white/5">
                      <p className="text-white/40 uppercase tracking-wider text-[10px] mb-1 flex items-center gap-1">
                        <MapPin size={10} className="text-indigo-400" /> ROI Coordinate Zone
                      </p>
                      <p className="text-indigo-300 font-semibold">{preview.evidence.zone_id}</p>
                    </div>
                  )}
                  {preview.evidence.direction && (
                    <div className="p-3.5 rounded-xl surface-inset border border-white/5">
                      <p className="text-white/40 uppercase tracking-wider text-[10px] mb-1 flex items-center gap-1">
                        <TrendingUp size={10} className="text-indigo-400" /> Vector Direction
                      </p>
                      <p className="text-white/80">{preview.evidence.direction}</p>
                    </div>
                  )}
                  {preview.evidence.lighting_condition && (
                    <div className="p-3.5 rounded-xl surface-inset border border-white/5">
                      <p className="text-white/40 uppercase tracking-wider text-[10px] mb-1 flex items-center gap-1">
                        <Shield size={10} className="text-indigo-400" /> Scene Illumination
                      </p>
                      <p className="text-emerald-400 font-semibold">{preview.evidence.lighting_condition}</p>
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
