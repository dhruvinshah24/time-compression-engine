'use client';

/**
 * Settings page — /settings
 *
 * Displays the TCE pipeline configuration fetched from GET /api/v1/settings.
 * All settings are read-only in v1.1. Each setting shows its key, current
 * value, description, category, and unit.
 */

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Loader2, AlertCircle, Lock, Cpu, Zap, Activity,
  BookOpen, Shield, Settings2, TrendingUp, CheckCircle2,
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

const CATEGORY_COLORS: Record<string, string> = {
  Detection:   'text-blue-400   bg-blue-400/10   border-blue-400/20',
  Tracking:    'text-violet-400 bg-violet-400/10 border-violet-400/20',
  Performance: 'text-amber-400  bg-amber-400/10  border-amber-400/20',
  Compression: 'text-cyan-400   bg-cyan-400/10   border-cyan-400/20',
  Events:      'text-indigo-400 bg-indigo-400/10 border-indigo-400/20',
  Story:       'text-pink-400   bg-pink-400/10   border-pink-400/20',
  Quality:     'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  System:      'text-white/40   bg-white/5       border-white/10',
};

function ValueBadge({ value }: { value: string }) {
  const isTrue  = value === 'True';
  const isFalse = value === 'False';
  const isNumber = !isNaN(parseFloat(value)) && !['True', 'False', 'adaptive'].includes(value);

  if (isTrue)  return <span className="px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-400 text-xs font-mono border border-emerald-500/20">True</span>;
  if (isFalse) return <span className="px-2 py-0.5 rounded-md bg-red-500/10 text-red-400/70 text-xs font-mono border border-red-500/15">False</span>;
  if (isNumber) return <span className="px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-300 text-xs font-mono border border-indigo-500/15">{value}</span>;
  return <span className="px-2 py-0.5 rounded-md bg-white/5 text-white/60 text-xs font-mono border border-white/10">{value}</span>;
}

function SettingCard({ setting, idx }: { setting: SettingRecord; idx: number }) {
  const Icon = CATEGORY_ICONS[setting.category] ?? Settings2;
  const colorClass = CATEGORY_COLORS[setting.category] ?? CATEGORY_COLORS.System;
  const [color] = colorClass.split(' ');

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.025 }}
      className="p-4 rounded-2xl bg-white/[0.025] border border-white/[0.07] hover:bg-white/[0.04] transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${colorClass.split(' ').slice(1).join(' ')}`}>
          <Icon size={14} className={color} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <p className="text-sm font-medium text-white">{setting.display_name}</p>
              <p className="text-[10px] text-white/25 font-mono mt-0.5">{setting.key}</p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <ValueBadge value={setting.value} />
              {setting.unit && (
                <span className="text-[9px] text-white/20 font-mono">{setting.unit}</span>
              )}
              {setting.readonly && (
                <Lock size={10} className="text-white/15" />
              )}
            </div>
          </div>
          <p className="text-xs text-white/40 mt-2 leading-relaxed">{setting.description}</p>
        </div>
      </div>
    </motion.div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    (api.settings.list() as Promise<SettingRecord[]>)
      .then(d => { setSettings(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  // Group by category
  const grouped: Record<string, SettingRecord[]> = {};
  for (const s of settings) {
    if (!grouped[s.category]) grouped[s.category] = [];
    grouped[s.category].push(s);
  }

  const categoryOrder = ['Detection', 'Tracking', 'Performance', 'Compression', 'Events', 'Story', 'Quality', 'System'];
  const sortedCategories = Object.keys(grouped).sort(
    (a, b) => (categoryOrder.indexOf(a) ?? 99) - (categoryOrder.indexOf(b) ?? 99)
  );

  let cardIdx = 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-white/30 text-sm mt-1">
            TCE v1.1-dev · Pipeline configuration reference
          </p>
        </div>
        {settings.length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/[0.07] text-xs text-white/30">
            <CheckCircle2 size={12} className="text-emerald-400" />
            {settings.length} settings · read-only
          </div>
        )}
      </div>

      {/* Info banner */}
      {!loading && settings.length > 0 && (
        <div className="flex items-start gap-3 p-4 rounded-2xl bg-indigo-500/5 border border-indigo-500/15 text-sm text-indigo-300/70">
          <Lock size={14} className="text-indigo-400 flex-shrink-0 mt-0.5" />
          <p>
            Settings are read-only in v1.1. These reflect the frozen TCE_V1_REFERENCE configuration
            validated in Phase 6E.14. Modify production parameters directly in the codebase.
          </p>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center justify-center py-24 gap-3 text-center">
          <AlertCircle className="w-10 h-10 text-red-400" />
          <p className="text-white font-medium">Failed to load settings</p>
          <p className="text-white/40 text-sm">{error}</p>
        </div>
      )}

      {/* Settings grouped by category */}
      {!loading && !error && sortedCategories.map(cat => {
        const Icon = CATEGORY_ICONS[cat] ?? Settings2;
        const colorClass = CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.System;
        const [color, bg, border] = colorClass.split(' ');

        return (
          <div key={cat} className="space-y-3">
            <div className="flex items-center gap-2">
              <div className={`w-6 h-6 rounded-lg flex items-center justify-center ${bg} ${border} border`}>
                <Icon size={12} className={color} />
              </div>
              <h2 className="text-sm font-semibold text-white/60 uppercase tracking-wider">{cat}</h2>
              <div className="flex-1 h-px bg-white/[0.05]" />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {grouped[cat].map(s => (
                <SettingCard key={s.key} setting={s} idx={cardIdx++} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
