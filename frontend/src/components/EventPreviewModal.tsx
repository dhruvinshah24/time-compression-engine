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
 *
 * Shows empty state with explanation if media is not generated.
 * Never shows placeholder images.
 */

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Loader2, AlertCircle, Play, Clock, User,
  Shield, ChevronLeft, ChevronRight, Info,
  Eye, MapPin, TrendingUp, Zap,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';
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
      <div className={`flex flex-col items-center justify-center rounded-xl border text-center p-4
        ${active ? 'border-indigo-500/40 bg-indigo-500/5' : 'border-white/10 bg-white/[0.02]'}`}
        style={{ minHeight: 140 }}
      >
        <AlertCircle size={20} className="text-white/20 mb-2" />
        <p className="text-xs text-white/25">{label}</p>
        <p className="text-[10px] text-white/15 mt-1">Not generated</p>
      </div>
    );
  }

  const src = url.startsWith('/') ? `${BACKEND}${url}` : url;

  if (errored) {
    return (
      <div className={`flex flex-col items-center justify-center rounded-xl border text-center p-4
        ${active ? 'border-red-500/30 bg-red-500/5' : 'border-white/10 bg-white/[0.02]'}`}
        style={{ minHeight: 140 }}
      >
        <AlertCircle size={20} className="text-red-400/50 mb-2" />
        <p className="text-xs text-white/25">{label}</p>
        <p className="text-[10px] text-red-400/40 mt-1">Image missing from server</p>
      </div>
    );
  }

  return (
    <div className={`relative rounded-xl overflow-hidden border
      ${active ? 'border-indigo-500/40 ring-1 ring-indigo-500/20' : 'border-white/10'}`}
      style={{ minHeight: 140 }}
    >
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/[0.02]">
          <Loader2 size={16} className="animate-spin text-white/20" />
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
      <div className="absolute bottom-0 left-0 right-0 py-1 px-2 bg-black/60 text-[10px] text-white/50 text-center">
        {label}
      </div>
      {active && (
        <div className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-indigo-500/80 text-[9px] text-white font-semibold">
          EVENT
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

    fetch(`${API}/events/${eventId}/preview`)
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

  const clipApiUrl = `${API}/events/${eventId}/clip`;
  const thumbApiUrl = `${API}/events/${eventId}/thumbnail`;

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
          className="absolute inset-0 bg-black/70 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Modal */}
        <motion.div
          className="relative w-full max-w-2xl bg-[#0f1117] border border-white/10 rounded-2xl shadow-2xl overflow-hidden z-10"
          initial={{ scale: 0.95, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.95, opacity: 0, y: 20 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        >
          {/* Header */}
          <div className="flex items-start justify-between p-5 border-b border-white/[0.07]">
            <div>
              <h2 className="text-lg font-bold text-white">
                {formatEventType(displayEventType)}
              </h2>
              <div className="flex items-center gap-3 mt-1">
                <span className="flex items-center gap-1 text-xs text-white/40">
                  <Clock size={11} /> {formatMs(displayMs)}
                </span>
                {displayConf !== undefined && (
                  <span className="flex items-center gap-1 text-xs text-indigo-400">
                    <Zap size={11} /> {Math.round(displayConf * 100)}% confidence
                  </span>
                )}
                {trackLabel && (
                  <span className="flex items-center gap-1 text-xs text-violet-400">
                    <User size={11} /> {trackLabel}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl hover:bg-white/10 text-white/40 hover:text-white/80 transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="p-5 space-y-5">
            {loading ? (
              <div className="flex items-center justify-center py-16 gap-3 text-white/30">
                <Loader2 size={20} className="animate-spin" />
                <span className="text-sm">Loading preview...</span>
              </div>
            ) : error ? (
              <div className="space-y-4">
                {/* Show thumbnail even if preview endpoint has partial error */}
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <AlertCircle size={32} className="text-white/20 mb-3" />
                  <p className="text-sm text-white/40">{error}</p>
                  <p className="text-xs text-white/25 mt-1">
                    Preview frames are generated during pipeline processing.
                    Run a full pipeline job to generate thumbnails.
                  </p>
                </div>
              </div>
            ) : preview ? (
              <>
                {/* Before / Event / After frames */}
                <div>
                  <p className="text-xs text-white/30 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Eye size={11} /> Event Context
                  </p>
                  <div className="grid grid-cols-3 gap-3">
                    <FrameImage url={preview.frames.before.url} label="Before" />
                    <FrameImage url={preview.frames.event.url}  label="Event"  active={true} />
                    <FrameImage url={preview.frames.after.url}  label="After" />
                  </div>
                  {!preview.frames.event.available && (
                    <p className="text-xs text-white/20 mt-2 text-center">
                      Thumbnails are generated when the pipeline runs with frame_annotator enabled.
                    </p>
                  )}
                </div>

                {/* Clip player */}
                {clipPlaying ? (
                  <div className="rounded-xl overflow-hidden border border-white/10 bg-black">
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
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-white/10 hover:border-indigo-500/40 hover:bg-indigo-500/5 text-white/40 hover:text-indigo-300 transition-all group text-sm"
                  >
                    <Play size={15} className="group-hover:text-indigo-400" />
                    Play Event Clip
                    {!preview.clip_url && (
                      <span className="text-[10px] text-white/20 ml-1">(unavailable if not generated)</span>
                    )}
                  </button>
                )}

                {/* Evidence / metadata */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  {preview.evidence.description && (
                    <div className="col-span-2 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      <p className="text-white/30 uppercase tracking-wider mb-1 flex items-center gap-1">
                        <Info size={10} /> Description
                      </p>
                      <p className="text-white/60">{preview.evidence.description}</p>
                    </div>
                  )}
                  {preview.evidence.zone_id && (
                    <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      <p className="text-white/30 uppercase tracking-wider mb-1 flex items-center gap-1">
                        <MapPin size={10} /> Zone
                      </p>
                      <p className="text-white/60 font-mono">{preview.evidence.zone_id}</p>
                    </div>
                  )}
                  {preview.evidence.direction && (
                    <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      <p className="text-white/30 uppercase tracking-wider mb-1 flex items-center gap-1">
                        <TrendingUp size={10} /> Direction
                      </p>
                      <p className="text-white/60">{preview.evidence.direction}</p>
                    </div>
                  )}
                  {preview.evidence.lighting_condition && preview.evidence.lighting_condition !== 'unknown' && (
                    <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      <p className="text-white/30 uppercase tracking-wider mb-1 flex items-center gap-1">
                        <Shield size={10} /> Scene Quality
                      </p>
                      <p className={`font-mono ${
                        preview.evidence.lighting_condition === 'normal' ? 'text-green-400' :
                        preview.evidence.lighting_condition === 'low_light' ? 'text-amber-400' :
                        'text-red-400'
                      }`}>{preview.evidence.lighting_condition}</p>
                      {preview.evidence.preprocessing_mode && preview.evidence.preprocessing_mode !== 'off' && (
                        <p className="text-white/20 mt-0.5">Enhanced: {preview.evidence.preprocessing_mode}</p>
                      )}
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
