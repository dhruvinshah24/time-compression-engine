'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Play, Pause, RotateCcw, RotateCw, Volume2, VolumeX,
  Maximize2, Eye, Shield, Film, User, Crosshair, Sparkles
} from 'lucide-react';
import { API_BASE } from '@/lib/api/client';

interface Person {
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
  display_name?: string;
}

interface CinemaVideoPlayerProps {
  videoId: string;
  durationSeconds: number;
  persons: Person[];
  events: EventRecord[];
  seekTimestamp?: number | null;
  onPersonSelect?: (person: Person) => void;
}

function fmtTime(sec: number) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.floor((sec % 1) * 1000);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

export default function CinemaVideoPlayer({
  videoId,
  durationSeconds,
  persons,
  events,
  seekTimestamp,
  onPersonSelect,
}: CinemaVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(durationSeconds || 59.39);
  const [isMuted, setIsMuted] = useState(true);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [hoverTime, setHoverTime] = useState<number | null>(null);

  const videoUrl = `${API_BASE}/videos/${videoId}/stream`;

  // Seek when seekTimestamp prop changes
  useEffect(() => {
    if (seekTimestamp !== null && seekTimestamp !== undefined && videoRef.current) {
      videoRef.current.currentTime = seekTimestamp;
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  }, [seekTimestamp]);

  const togglePlay = useCallback(() => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  }, []);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      if (videoRef.current.duration && !isNaN(videoRef.current.duration)) {
        setDuration(videoRef.current.duration);
      }
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    const target = pos * duration;
    if (videoRef.current) {
      videoRef.current.currentTime = target;
      setCurrentTime(target);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    setHoverTime(pos * duration);
  };

  const skipTime = (delta: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, Math.min(duration, videoRef.current.currentTime + delta));
    }
  };

  const changeRate = (rate: number) => {
    setPlaybackRate(rate);
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
  };

  // Determine which person is active at currentTime
  const currentMs = currentTime * 1000;
  const activeActors = persons.filter(
    p => currentMs >= p.first_seen_ms && currentMs <= p.last_seen_ms
  );

  return (
    <div className="hud-card rounded-2xl overflow-hidden border border-cyan-400/20 shadow-[0_4px_30px_rgba(0,0,0,0.6)]">
      {/* Player Header Bar */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-[#090c12]/90">
        <div className="flex items-center gap-3">
          <div className="relative w-5 h-5 flex items-center justify-center">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#00d4ff]" />
            <span className="absolute inset-0 rounded-full border border-cyan-400/40 animate-ping opacity-60" />
          </div>
          <div>
            <span className="text-xs font-mono font-bold text-white tracking-wider uppercase">
              FORENSIC STREAM · SYNCHRONIZED SURVEILLANCE
            </span>
            <span className="ml-2 text-[10px] font-mono text-cyan-400/70 border border-cyan-400/30 px-1.5 py-0.2 rounded">
              2340×1080 @ 27.5 FPS
            </span>
          </div>
        </div>

        {/* Live Active Actor Tags */}
        <div className="flex items-center gap-2">
          {activeActors.map(a => (
            <span
              key={a.person_label}
              className={`text-[10px] font-mono px-2 py-0.5 rounded-full border flex items-center gap-1.5 ${
                a.person_label === 'Person 1'
                  ? 'border-amber-400/50 bg-amber-400/10 text-amber-300'
                  : 'border-cyan-400/50 bg-cyan-400/10 text-cyan-300'
              }`}
            >
              <User size={10} />
              {a.person_label} In-Frame
            </span>
          ))}
          {activeActors.length === 0 && (
            <span className="text-[10px] font-mono text-white/30">Scanning room…</span>
          )}
        </div>
      </div>

      {/* Main Video Screen with HUD Reticle */}
      <div className="relative aspect-[16/9] max-h-[460px] bg-black flex items-center justify-center overflow-hidden group">
        <video
          ref={videoRef}
          src={videoUrl}
          playsInline
          muted={isMuted}
          onTimeUpdate={handleTimeUpdate}
          onEnded={() => setIsPlaying(false)}
          className="w-full h-full object-contain cursor-pointer"
          onClick={togglePlay}
        />

        {/* HUD Frame Overlays */}
        <div className="absolute top-3 left-3 w-6 h-6 border-t-2 border-l-2 border-cyan-400/60 pointer-events-none" />
        <div className="absolute top-3 right-3 w-6 h-6 border-t-2 border-r-2 border-cyan-400/60 pointer-events-none" />
        <div className="absolute bottom-3 left-3 w-6 h-6 border-b-2 border-l-2 border-cyan-400/60 pointer-events-none" />
        <div className="absolute bottom-3 right-3 w-6 h-6 border-b-2 border-r-2 border-cyan-400/60 pointer-events-none" />

        {/* On-Screen Watermark */}
        <div className="absolute top-4 left-5 flex items-center gap-2 pointer-events-none bg-black/60 backdrop-blur-md px-2.5 py-1 rounded border border-white/10">
          <Film size={12} className="text-cyan-400" />
          <span className="text-[11px] font-mono text-cyan-300 tracking-widest">
            TC {fmtTime(currentTime)}
          </span>
        </div>

        {/* Big Center Play Button when paused */}
        {!isPlaying && (
          <motion.button
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            onClick={togglePlay}
            className="absolute inset-0 m-auto w-16 h-16 rounded-full bg-cyan-500/20 border border-cyan-400/50 backdrop-blur-md flex items-center justify-center text-cyan-300 shadow-[0_0_30px_rgba(0,212,255,0.3)] hover:scale-110 hover:bg-cyan-500/30 transition-all z-20"
          >
            <Play size={24} className="ml-1" />
          </motion.button>
        )}
      </div>

      {/* Multi-Track Forensic DAW Scrubber Rail */}
      <div className="px-5 pt-3 pb-4 bg-[#080b10] border-t border-white/5 space-y-2.5">
        {/* Seek Bar with Event Markers */}
        <div
          className="relative h-6 flex items-center cursor-pointer select-none group"
          onClick={handleSeek}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverTime(null)}
        >
          {/* Base track */}
          <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden relative">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-cyan-300 relative transition-all"
              style={{ width: `${(currentTime / duration) * 100}%` }}
            />
          </div>

          {/* Event markers on scrub track */}
          {events.map((evt, i) => {
            const pos = ((evt.start_ms ?? evt.timestamp_ms ?? 0) / 1000) / duration;
            const isP2 = evt.person_label === 'Person 2';
            return (
              <div
                key={evt.event_id ?? evt.id ?? i}
                title={`${evt.display_name || evt.event_type} (${fmtTime((evt.start_ms ?? 0) / 1000)})`}
                className={`absolute w-1.5 h-3 -translate-x-1/2 rounded-full pointer-events-none transition-transform group-hover:scale-125 ${
                  isP2 ? 'bg-cyan-400' : 'bg-amber-400'
                }`}
                style={{ left: `${pos * 100}%` }}
              />
            );
          })}

          {/* Scrubber thumb */}
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-white border-2 border-cyan-400 shadow-[0_0_10px_#00d4ff] pointer-events-none"
            style={{ left: `${(currentTime / duration) * 100}%` }}
          />

          {/* Hover tooltip */}
          {hoverTime !== null && (
            <div
              className="absolute -top-7 -translate-x-1/2 px-2 py-0.5 rounded bg-black/90 border border-cyan-400/40 text-[10px] font-mono text-cyan-300 pointer-events-none whitespace-nowrap shadow-lg"
              style={{ left: `${(hoverTime / duration) * 100}%` }}
            >
              {fmtTime(hoverTime)}
            </div>
          )}
        </div>

        {/* Actor Presence Swimlanes */}
        <div className="space-y-1 pt-1 border-t border-white/5">
          {persons.map(p => {
            const startPct = ((p.first_seen_ms / 1000) / duration) * 100;
            const endPct   = ((p.last_seen_ms / 1000) / duration) * 100;
            const widthPct = Math.max(1, endPct - startPct);
            const isP1 = p.person_label === 'Person 1';

            return (
              <div key={p.person_label} className="flex items-center gap-3 text-[10px] font-mono">
                <span className="w-16 truncate text-white/40 flex-shrink-0">
                  {p.person_label}
                </span>
                <div
                  className="flex-1 h-2 rounded bg-black/40 border border-white/5 relative cursor-pointer"
                  onClick={e => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    const target = ((e.clientX - rect.left) / rect.width) * duration;
                    if (videoRef.current) {
                      videoRef.current.currentTime = target;
                      setCurrentTime(target);
                    }
                  }}
                >
                  <div
                    className={`absolute top-0 bottom-0 rounded opacity-80 hover:opacity-100 transition-opacity ${
                      isP1 ? 'bg-amber-400/70 border border-amber-300' : 'bg-cyan-400/70 border border-cyan-300'
                    }`}
                    style={{ left: `${startPct}%`, width: `${widthPct}%` }}
                    title={`${p.person_label} active: ${((p.last_seen_ms - p.first_seen_ms)/1000).toFixed(1)}s`}
                  />
                </div>
                <span className="w-12 text-right text-white/30 text-[9px]">
                  {((p.last_seen_ms - p.first_seen_ms) / 1000).toFixed(0)}s
                </span>
              </div>
            );
          })}
        </div>

        {/* Transport Controls Bar */}
        <div className="flex items-center justify-between pt-2">
          {/* Play/Pause + Skips */}
          <div className="flex items-center gap-2">
            <button
              onClick={togglePlay}
              className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-400/40 text-cyan-300 hover:bg-cyan-500/20 flex items-center justify-center transition-colors"
            >
              {isPlaying ? <Pause size={14} /> : <Play size={14} className="ml-0.5" />}
            </button>
            <button
              onClick={() => skipTime(-5)}
              title="Back 5s"
              className="w-7 h-7 rounded bg-white/5 border border-white/10 text-white/60 hover:text-white flex items-center justify-center transition-colors"
            >
              <RotateCcw size={12} />
            </button>
            <button
              onClick={() => skipTime(5)}
              title="Forward 5s"
              className="w-7 h-7 rounded bg-white/5 border border-white/10 text-white/60 hover:text-white flex items-center justify-center transition-colors"
            >
              <RotateCw size={12} />
            </button>

            <span className="text-xs font-mono text-white/60 ml-2">
              <span className="text-cyan-400 font-bold">{fmtTime(currentTime)}</span> / {fmtTime(duration)}
            </span>
          </div>

          {/* Right controls: Speed, Mute, Fullscreen */}
          <div className="flex items-center gap-2">
            {/* Speed Pills */}
            <div className="flex items-center rounded bg-black/40 border border-white/5 p-0.5">
              {[0.5, 1, 2].map(rate => (
                <button
                  key={rate}
                  onClick={() => changeRate(rate)}
                  className={`text-[10px] font-mono px-2 py-0.5 rounded transition-all ${
                    playbackRate === rate
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/40'
                      : 'text-white/30 hover:text-white/60'
                  }`}
                >
                  {rate}x
                </button>
              ))}
            </div>

            <button
              onClick={() => setIsMuted(m => !m)}
              className="w-7 h-7 rounded bg-white/5 border border-white/10 text-white/60 hover:text-white flex items-center justify-center transition-colors"
            >
              {isMuted ? <VolumeX size={13} /> : <Volume2 size={13} />}
            </button>

            <button
              onClick={() => {
                if (videoRef.current) {
                  if (videoRef.current.requestFullscreen) {
                    videoRef.current.requestFullscreen();
                  }
                }
              }}
              className="w-7 h-7 rounded bg-white/5 border border-white/10 text-white/60 hover:text-white flex items-center justify-center transition-colors"
            >
              <Maximize2 size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
