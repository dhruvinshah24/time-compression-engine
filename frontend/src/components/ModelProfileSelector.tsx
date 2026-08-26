'use client';

/**
 * ModelProfileSelector
 *
 * 3-card selector for FAST / BALANCED / ACCURACY model profiles.
 * All values are measured, not estimated.
 * Measured 2026-08-25 on NVIDIA RTX 5050, CUDA 13.2, 1080p input.
 */

import { motion } from 'framer-motion';
import { Zap, Scale, Target } from 'lucide-react';

export type ModelProfile = 'fast' | 'balanced' | 'accuracy';

export interface ModelProfileSelectorProps {
  value: ModelProfile;
  onChange: (profile: ModelProfile) => void;
  disabled?: boolean;
}

interface ProfileDef {
  id: ModelProfile;
  label: string;
  model: string;
  fps: number;
  vramMb: number;
  intendedUse: string;
  tradeoff: string;
  icon: React.ComponentType<{ className?: string }>;
  accentClass: string;
  selectedBorderClass: string;
  selectedBgClass: string;
  badgeClass: string;
}

const PROFILES: ProfileDef[] = [
  {
    id: 'fast',
    label: 'Fast',
    model: 'YOLO11n',
    fps: 80,
    vramMb: 44,
    intendedUse: 'Exploratory analysis, high-throughput screening',
    tradeoff: 'Lower detection accuracy. Best for exploratory analysis or high-throughput screening.',
    icon: Zap,
    accentClass: 'text-emerald-400',
    selectedBorderClass: 'border-emerald-500/60',
    selectedBgClass: 'bg-emerald-500/[0.06]',
    badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  },
  {
    id: 'balanced',
    label: 'Balanced',
    model: 'YOLO11l',
    fps: 32,
    vramMb: 183,
    intendedUse: 'General CCTV / surveillance processing',
    tradeoff: 'Good accuracy/throughput balance. Recommended for general CCTV processing.',
    icon: Scale,
    accentClass: 'text-indigo-400',
    selectedBorderClass: 'border-indigo-500/60',
    selectedBgClass: 'bg-indigo-500/[0.06]',
    badgeClass: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  },
  {
    id: 'accuracy',
    label: 'Accuracy',
    model: 'YOLO11x',
    fps: 32,
    vramMb: 392,
    intendedUse: 'Maximum detection quality, small-object detection',
    tradeoff:
      'Maximum detection quality. Higher compute requirement. Same throughput as Balanced on RTX 5050.',
    icon: Target,
    accentClass: 'text-violet-400',
    selectedBorderClass: 'border-violet-500/60',
    selectedBgClass: 'bg-violet-500/[0.06]',
    badgeClass: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
  },
];

export default function ModelProfileSelector({
  value,
  onChange,
  disabled = false,
}: ModelProfileSelectorProps) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {PROFILES.map((profile) => {
          const isSelected = value === profile.id;
          const Icon = profile.icon;

          return (
            <motion.button
              key={profile.id}
              onClick={() => !disabled && onChange(profile.id)}
              whileHover={disabled ? {} : { scale: 1.015 }}
              whileTap={disabled ? {} : { scale: 0.985 }}
              disabled={disabled}
              aria-pressed={isSelected}
              className={[
                'relative text-left rounded-xl border p-4 transition-all duration-200',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/50',
                disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
                isSelected
                  ? `${profile.selectedBorderClass} ${profile.selectedBgClass}`
                  : 'border-white/[0.07] bg-white/[0.03] hover:border-white/[0.14] hover:bg-white/[0.05]',
              ].join(' ')}
            >
              {/* Selected ring glow */}
              {isSelected && (
                <motion.div
                  layoutId="profile-glow"
                  className={`absolute inset-0 rounded-xl opacity-20 blur-sm pointer-events-none ${profile.selectedBgClass}`}
                />
              )}

              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Icon
                    className={`w-4 h-4 ${isSelected ? profile.accentClass : 'text-white/40'}`}
                  />
                  <span
                    className={`text-sm font-semibold ${
                      isSelected ? 'text-white' : 'text-white/70'
                    }`}
                  >
                    {profile.label}
                  </span>
                </div>
                {isSelected && (
                  <motion.span
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${profile.badgeClass}`}
                  >
                    selected
                  </motion.span>
                )}
              </div>

              {/* Model name */}
              <p className="text-xs font-mono text-white/50 mb-3">{profile.model}</p>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mb-3">
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">FPS</p>
                  <p className={`text-base font-bold font-mono ${isSelected ? profile.accentClass : 'text-white/80'}`}>
                    {profile.fps}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">VRAM</p>
                  <p className={`text-base font-bold font-mono ${isSelected ? profile.accentClass : 'text-white/80'}`}>
                    {profile.vramMb} MB
                  </p>
                </div>
              </div>

              {/* Intended use */}
              <p className="text-[11px] text-white/40 mb-2 leading-snug">{profile.intendedUse}</p>

              {/* Tradeoff — shown always, not hidden */}
              <p className="text-[10px] text-white/25 leading-snug border-t border-white/[0.05] pt-2">
                {profile.tradeoff}
              </p>
            </motion.button>
          );
        })}
      </div>

      {/* Measurement footnote */}
      <p className="text-[10px] text-white/20 font-mono">
        FPS measured on NVIDIA RTX 5050 @ 1080p, CUDA 13.2, 2026-08-25. Performance varies by
        hardware.
      </p>
    </div>
  );
}
