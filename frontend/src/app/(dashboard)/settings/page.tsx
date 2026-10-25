'use client';

import { useEffect, useState, useMemo } from 'react';
import {
  Loader2, AlertCircle, Lock, Cpu, Zap, Activity,
  BookOpen, Shield, Settings2, TrendingUp, CheckCircle2,
  Search, Sliders, Filter, X
} from 'lucide-react';
import { api } from '@/lib/api/client';
import { SettingsSkeleton } from '@/components/skeletons/SettingsSkeleton';
import Link from 'next/link';
import React from 'react';

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

function ValueBadge({ value, unit }: { value: string; unit: string | null }) {
  const isTrue  = value === 'True';
  const isFalse = value === 'False';
  const isNumber = !isNaN(parseFloat(value)) && !['True', 'False', 'adaptive'].includes(value);

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      {isTrue && <span className="badge badge-success">{value}</span>}
      {isFalse && <span className="badge badge-danger">{value}</span>}
      {isNumber && <span className="badge badge-accent">{value}</span>}
      {!isTrue && !isFalse && !isNumber && <span className="badge badge-neutral">{value}</span>}
      {unit && (
        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {unit}
        </span>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingRecord[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [search, setSearch]     = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  useEffect(() => {
    (api.settings.list() as Promise<SettingRecord[]>)
      .then(d => { setSettings(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  const categories = useMemo(() => {
    const list = Array.from(new Set(settings.map(s => s.category)));
    const order = ['Detection', 'Tracking', 'Performance', 'Compression', 'Events', 'Story', 'Quality', 'System'];
    return list.sort((a, b) => {
      const idxA = order.indexOf(a);
      const idxB = order.indexOf(b);
      return (idxA !== -1 ? idxA : 99) - (idxB !== -1 ? idxB : 99);
    });
  }, [settings]);

  const filteredSettings = useMemo(() => {
    return settings.filter(s => {
      const q = search.toLowerCase();
      const matchSearch = s.display_name.toLowerCase().includes(q) || s.key.toLowerCase().includes(q) || s.description.toLowerCase().includes(q);
      const matchCat = !activeCategory || s.category === activeCategory;
      return matchSearch && matchCat;
    });
  }, [settings, search, activeCategory]);

  if (loading) return <SettingsSkeleton />;

  if (error) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <div className="card" style={{ padding: 32, textAlign: 'center', maxWidth: 420 }}>
        <AlertCircle size={28} style={{ color: 'var(--danger)', margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 6px' }}>Configuration Unavailable</h3>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0, fontFamily: 'var(--font-mono)' }}>{error}</p>
      </div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* ── Breadcrumb & Header ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6
          }}>
            <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Dashboard</Link>
            <span>/</span>
            <span style={{ color: 'var(--text-secondary)' }}>System Parameters</span>
          </div>

          <h1 style={{
            fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
            letterSpacing: '-0.02em', margin: 0
          }}>
            Pipeline Engine Configuration
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2, marginBottom: 0 }}>
            TCE v1.1 • {settings.length} frozen runtime parameters calibrated for surveillance intelligence.
          </p>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
          backgroundColor: 'var(--bg-raised)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '6px 12px'
        }}>
          <Lock size={12} style={{ color: 'var(--accent)' }} />
          <span>Phase 6E Immutable Compliance</span>
        </div>
      </div>

      {/* ── Info Compliance Banner ──────────────────────────────────────── */}
      <div className="card-inset" style={{ padding: '12px 16px', display: 'flex', alignItems: 'flex-start', gap: 12, border: '1px solid var(--border)' }}>
        <CheckCircle2 size={16} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 1 }} />
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          These parameters govern all 12 pipeline stages including YOLO11x detection thresholds, ByteTrack tracker persistence, cosine similarity re-identification margins, and causal story fusion policies. All values are read-only to ensure forensic chain of custody.
        </div>
      </div>

      {/* ── Filter & Search Toolbar ─────────────────────────────────────── */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ position: 'relative', width: 280, maxWidth: '100%' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
          <input
            type="text"
            placeholder="Search parameter key or description..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input"
            style={{ paddingLeft: 32, paddingRight: search ? 30 : 12, fontFamily: 'var(--font-mono)', fontSize: 12 }}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{
                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 2
              }}
            >
              <X size={13} />
            </button>
          )}
        </div>

        {/* Category Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <button
            onClick={() => setActiveCategory(null)}
            style={{
              fontSize: 11, padding: '5px 12px', borderRadius: 4, border: '1px solid', cursor: 'pointer',
              backgroundColor: !activeCategory ? 'var(--accent-bg)' : 'var(--bg-panel)',
              borderColor: !activeCategory ? 'var(--accent-dim)' : 'var(--border)',
              color: !activeCategory ? 'var(--accent)' : 'var(--text-secondary)',
              fontFamily: 'var(--font-mono)', transition: 'all 0.15s'
            }}
          >
            All Parameters ({settings.length})
          </button>
          {categories.map(cat => {
            const count = settings.filter(s => s.category === cat).length;
            const active = activeCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(active ? null : cat)}
                style={{
                  fontSize: 11, padding: '5px 12px', borderRadius: 4, border: '1px solid', cursor: 'pointer',
                  backgroundColor: active ? 'var(--accent-bg)' : 'var(--bg-panel)',
                  borderColor: active ? 'var(--accent-dim)' : 'var(--border)',
                  color: active ? 'var(--accent)' : 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono)', transition: 'all 0.15s',
                  display: 'flex', alignItems: 'center', gap: 6
                }}
              >
                <span>{cat}</span>
                <span style={{ fontSize: 10, opacity: 0.7 }}>({count})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Structured Parameter Table / List ────────────────────────────── */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', border: '1px solid var(--border)' }}>
        {/* Table Header */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '140px 240px 180px 1fr 90px',
          padding: '10px 16px',
          backgroundColor: 'var(--bg-raised)',
          borderBottom: '1px solid var(--border)',
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          fontWeight: 700,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          <div>Category</div>
          <div>Parameter Name & Key</div>
          <div>Configured Value</div>
          <div>Functional Description</div>
          <div style={{ textAlign: 'right' }}>Status</div>
        </div>

        {/* Rows */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {filteredSettings.map((setting, idx) => {
            const Icon = CATEGORY_ICONS[setting.category] ?? Settings2;
            const isLast = idx === filteredSettings.length - 1;

            return (
              <div
                key={setting.key}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '140px 240px 180px 1fr 90px',
                  alignItems: 'center',
                  padding: '12px 16px',
                  borderBottom: isLast ? 'none' : '1px solid var(--border-dim)',
                  backgroundColor: idx % 2 === 1 ? 'rgba(255, 255, 255, 0.015)' : 'transparent',
                  transition: 'background-color 0.15s ease'
                }}
              >
                {/* Category */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: 4,
                    backgroundColor: 'var(--accent-bg)', border: '1px solid var(--accent-dim)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--accent)', flexShrink: 0
                  }}>
                    <Icon size={12} />
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
                    {setting.category}
                  </span>
                </div>

                {/* Name & Key */}
                <div style={{ paddingRight: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {setting.display_name}
                  </div>
                  <div style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                    marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                  }}>
                    {setting.key}
                  </div>
                </div>

                {/* Value & Unit */}
                <div>
                  <ValueBadge value={setting.value} unit={setting.unit} />
                </div>

                {/* Description */}
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', paddingRight: 16, lineHeight: 1.4 }}>
                  {setting.description}
                </div>

                {/* Status / Lock */}
                <div style={{ textAlign: 'right' }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                    backgroundColor: 'var(--bg-inset)', padding: '3px 6px', borderRadius: 4,
                    border: '1px solid var(--border-dim)'
                  }}>
                    <Lock size={9} />
                    <span>Frozen</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {filteredSettings.length === 0 && (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
            <Search size={24} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
            <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>No parameters match &ldquo;{search}&rdquo;</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Try clearing the search query or selecting another category.</div>
          </div>
        )}
      </div>
    </div>
  );
}
