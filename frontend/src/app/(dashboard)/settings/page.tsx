'use client';

/**
 * Settings page — /settings
 *
 * Displays the frozen TCE pipeline configuration fetched from GET /api/v1/settings.
 * Precision-styled as an enterprise AI runtime inspector.
 */

import { useEffect, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Loader2, AlertCircle, Lock, Cpu, Zap, Activity,
  BookOpen, Shield, Settings2, TrendingUp, CheckCircle2,
  Search, SlidersHorizontal, Terminal
} from 'lucide-react';
import { api } from '@/lib/api/client';

interface SettingRecord {
  key: string;
  value: string;
  display_name: string;
  description: string;
  category: string;
  readonly: boolean;
  unit: string | null;
}

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  Detection:   Cpu,
  Tracking:    Activity,
  Performance: Zap,
  Compression: TrendingUp,
  Events:      Zap,
  Story:       BookOpen,
  Quality:     Shield,
  System:      Settings2,
};

const CATEGORY_STYLES: Record<string, { color: string; bg: string; border: string; glow: string }> = {
  Detection:   { color: 'text-blue-400',   bg: 'bg-blue-500/10',   border: 'border-blue-500/30',   glow: 'shadow-[0_0_12px_rgba(59,130,246,0.15)]' },
  Tracking:    { color: 'text-violet-400', bg: 'bg-violet-500/10', border: 'border-violet-500/30', glow: 'shadow-[0_0_12px_rgba(168,85,247,0.15)]' },
  Performance: { color: 'text-amber-400',  bg: 'bg-amber-500/10',  border: 'border-amber-500/30',  glow: 'shadow-[0_0_12px_rgba(245,158,11,0.15)]' },
  Compression: { color: 'text-cyan-400',   bg: 'bg-cyan-500/10',   border: 'border-cyan-500/30',   glow: 'shadow-[0_0_12px_rgba(6,182,212,0.15)]' },
  Events:      { color: 'text-indigo-400', bg: 'bg-indigo-500/10', border: 'border-indigo-500/30', glow: 'shadow-[0_0_12px_rgba(99,102,241,0.15)]' },
  Story:       { color: 'text-pink-400',   bg: 'bg-pink-500/10',   border: 'border-pink-500/30',   glow: 'shadow-[0_0_12px_rgba(236,72,153,0.15)]' },
  Quality:     { color: 'text-emerald-400',bg: 'bg-emerald-500/10',border: 'border-emerald-500/30',glow: 'shadow-[0_0_12px_rgba(16,185,129,0.15)]' },
  System:      { color: 'text-slate-400',  bg: 'bg-slate-500/10',  border: 'border-slate-500/30',  glow: 'shadow-[0_0_12px_rgba(148,163,184,0.15)]' },
};

function ValueBadge({ value }: { value: string }) {
  const isTrue  = value === 'True';
  const isFalse = value === 'False';
  const isNumber = !isNaN(parseFloat(value)) && !['True', 'False', 'adaptive'].includes(value);

  if (isTrue)
    return <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-xs font-mono font-medium border border-emerald-500/30 shadow-[0_0_8px_rgba(16,185,129,0.2)]">True</span>;
  if (isFalse)
    return <span className="px-2.5 py-0.5 rounded-full bg-rose-500/15 text-rose-400 text-xs font-mono font-medium border border-rose-500/30">False</span>;
  if (isNumber)
    return <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 text-xs font-mono font-medium border border-cyan-500/30">{value}</span>;
  return (
    <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 text-xs font-mono font-medium border border-indigo-500/30">
      {value}
    </span>
  );
}

function SettingCard({ setting, idx }: { setting: SettingRecord; idx: number }) {
  const style = CATEGORY_STYLES[setting.category] ?? CATEGORY_STYLES.System;
  const Icon = CATEGORY_ICONS[setting.category] ?? Settings2;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(0.3, idx * 0.02) }}
      className="p-4 rounded-xl surface-card border hover:border-white/20 transition-all group flex flex-col justify-between"
    >
      <div>
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2.5">
            <div className={`w-8 h-8 rounded-lg ${style.bg} ${style.border} border flex items-center justify-center ${style.color} ${style.glow} flex-shrink-0`}>
              <Icon size={14} />
            </div>
            <div>
              <p className="text-sm font-semibold text-white tracking-tight">{setting.display_name}</p>
              <p className="text-[10px] font-mono text-white/30 truncate mt-0.5">{setting.key}</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            <ValueBadge value={setting.value} />
            {setting.unit && (
              <span className="text-[10px] font-mono text-white/40">{setting.unit}</span>
            )}
            {setting.readonly && (
              <div className="p-1 rounded bg-white/5 text-white/30" title="Locked runtime parameter">
                <Lock size={10} />
              </div>
            )}
          </div>
        </div>

        <p className="text-xs text-white/50 leading-relaxed mt-2.5">
          {setting.description}
        </p>
      </div>

      <div className="mt-3 pt-2.5 border-t border-white/[0.04] flex items-center justify-between text-[10px] font-mono text-white/30">
        <span className="uppercase tracking-wider">{setting.category}</span>
        <span className="text-white/20">Read-only runtime</span>
      </div>
    </motion.div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [search, setSearch]   = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  useEffect(() => {
    (api.settings.list() as Promise<SettingRecord[]>)
      .then(d => { setSettings(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  const categories = useMemo(() => {
    const list = Array.from(new Set(settings.map(s => s.category)));
    const order = ['Detection', 'Tracking', 'Performance', 'Compression', 'Events', 'Story', 'Quality', 'System'];
    return list.sort((a, b) => (order.indexOf(a) ?? 99) - (order.indexOf(b) ?? 99));
  }, [settings]);

  const filteredSettings = useMemo(() => {
    return settings.filter(s => {
      const matchesSearch = s.display_name.toLowerCase().includes(search.toLowerCase()) ||
        s.key.toLowerCase().includes(search.toLowerCase()) ||
        s.description.toLowerCase().includes(search.toLowerCase());
      const matchesCategory = !activeCategory || s.category === activeCategory;
      return matchesSearch && matchesCategory;
    });
  }, [settings, search, activeCategory]);

  if (loading) return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
        <p className="text-white/40 text-xs font-mono uppercase tracking-widest animate-pulse">Inspecting frozen config…</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center p-8 max-w-md surface-card rounded-3xl border border-red-500/20">
        <AlertCircle className="w-12 h-12 text-red-400" />
        <h2 className="text-lg font-bold text-white">Config Stream Failed</h2>
        <p className="text-white/50 text-xs">{error}</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-7 animate-slide-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/5">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Pipeline Reference Configuration</h1>
          <p className="text-white/40 text-xs mt-1 font-mono">
            TCE v1.1-dev · Frozen reference hyperparameters validated in Phase 6E
          </p>
        </div>
        <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full surface-card border text-xs text-white/50 font-mono">
          <Lock size={12} className="text-indigo-400" />
          <span>{settings.length} parameters immutable</span>
        </div>
      </div>

      {/* Info notice banner */}
      <div className="p-4 rounded-2xl surface-card border border-indigo-500/20 flex items-start gap-3.5 text-xs text-indigo-300/80">
        <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 flex-shrink-0 mt-0.5">
          <Terminal size={15} />
        </div>
        <div className="leading-relaxed">
          <span className="font-semibold text-white block mb-0.5">Immutable Reference Standard</span>
          These settings govern all 12 pipeline stages including YOLO11x detection thresholds, ByteTrack tracker persistence, cosine similarity re-identification margins, and synthesis compression curves.
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <input
            type="text"
            placeholder="Search parameters or keys…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full px-4 py-2 pl-9 rounded-xl surface-inset border border-white/10 text-xs text-white placeholder-white/30 focus:outline-none focus:border-indigo-500 font-mono"
          />
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
        </div>

        {/* Category switcher */}
        <div className="flex flex-wrap gap-1.5 w-full sm:w-auto">
          <button
            onClick={() => setActiveCategory(null)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
              !activeCategory
                ? 'bg-indigo-600/30 border-indigo-500/50 text-indigo-200'
                : 'bg-white/[0.02] border-white/5 text-white/40 hover:text-white'
            }`}
          >
            All ({settings.length})
          </button>
          {categories.map(cat => {
            const style = CATEGORY_STYLES[cat] ?? CATEGORY_STYLES.System;
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
                  activeCategory === cat
                    ? `${style.bg} ${style.border} ${style.color} font-medium`
                    : 'bg-white/[0.02] border-white/5 text-white/40 hover:text-white'
                }`}
              >
                {cat}
              </button>
            );
          })}
        </div>
      </div>

      {/* Setting Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredSettings.map((s, idx) => (
          <SettingCard key={s.key} setting={s} idx={idx} />
        ))}
      </div>

      {filteredSettings.length === 0 && (
        <div className="p-12 text-center surface-card rounded-2xl border">
          <p className="text-white/40 text-xs font-mono">No configuration parameters match query &ldquo;{search}&rdquo;</p>
        </div>
      )}
    </div>
  );
}
