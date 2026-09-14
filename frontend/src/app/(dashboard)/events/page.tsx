'use client';

import { useState, useEffect, useMemo } from 'react';
import { Filter, Zap, Loader2, AlertCircle, User, Clock, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api/client';
import Link from 'next/link';

interface EventRecord {
  id?: string;
  event_id?: string;
  type?: string;
  event_type?: string;
  timestamp_ms?: number;
  start_ms?: number;
  confidence?: number;
  video_id?: string;
  person_label?: string;
  rule_name?: string;
  evidence?: Record<string, unknown>;
}

const getEventType = (e: EventRecord) => e.event_type ?? e.type ?? '';
const getEventId = (e: EventRecord) => e.event_id ?? e.id ?? '';
const getTime = (e: EventRecord) => ((e.start_ms ?? e.timestamp_ms ?? 0) / 1000);

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${(s % 60).toFixed(0)}s` : `${s.toFixed(1)}s`;
}

function formatEventLabel(et: string) {
  return et.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function ConfBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 90 ? 'bg-emerald-500' : pct >= 70 ? 'bg-indigo-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-mono text-white/40">{pct}%</span>
    </div>
  );
}

export default function EventsPage() {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [minConf, setMinConf] = useState(0);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());

  useEffect(() => {
    let mounted = true;
    (api.events.list({ limit: '200' }) as Promise<EventRecord[]>)
      .then(res => { if (mounted) { setEvents(Array.isArray(res) ? res : []); setLoading(false); } })
      .catch(err => { if (mounted) { setError(err.message); setLoading(false); } });
    return () => { mounted = false; };
  }, []);

  const allTypes = useMemo(() => Array.from(new Set(events.map(getEventType))).sort(), [events]);

  const filtered = useMemo(() => events.filter(e => {
    const conf = e.confidence ?? 0;
    if (conf < minConf / 100) return false;
    if (selectedTypes.size > 0 && !selectedTypes.has(getEventType(e))) return false;
    return true;
  }), [events, minConf, selectedTypes]);

  const toggleType = (t: string) => setSelectedTypes(prev => {
    const next = new Set(prev);
    next.has(t) ? next.delete(t) : next.add(t);
    return next;
  });

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Event Explorer</h1>
          <p className="text-white/30 text-sm mt-0.5">{filtered.length} events{selectedTypes.size > 0 || minConf > 0 ? ' (filtered)' : ''} · {events.length} total</p>
        </div>
      </div>

      <div className="flex gap-5 flex-1 min-h-0">
        {/* Filters sidebar */}
        <div className="w-56 flex-shrink-0 space-y-4">
          <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06]">
            <div className="flex items-center gap-2 mb-4 text-white/60 text-sm font-medium">
              <Filter size={14} /> Filters
            </div>

            <div className="mb-4">
              <label className="text-[11px] text-white/40 uppercase tracking-wider mb-2 block">Min Confidence</label>
              <input type="range" min="0" max="100" value={minConf}
                onChange={e => setMinConf(Number(e.target.value))}
                className="w-full accent-indigo-500" />
              <div className="flex justify-between text-[10px] text-white/30 mt-1">
                <span>0%</span><span className="text-indigo-400 font-mono">{minConf}%</span><span>100%</span>
              </div>
            </div>

            {allTypes.length > 0 && (
              <div>
                <label className="text-[11px] text-white/40 uppercase tracking-wider mb-2 block">Event Type</label>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {allTypes.map(t => (
                    <label key={t} className="flex items-center gap-2 cursor-pointer group">
                      <input type="checkbox" checked={selectedTypes.has(t)} onChange={() => toggleType(t)}
                        className="rounded border-white/20 bg-transparent accent-indigo-500" />
                      <span className="text-[11px] text-white/50 group-hover:text-white/80 transition-colors truncate">
                        {formatEventLabel(t)}
                      </span>
                    </label>
                  ))}
                </div>
                {selectedTypes.size > 0 && (
                  <button onClick={() => setSelectedTypes(new Set())}
                    className="mt-2 text-[11px] text-indigo-400 hover:text-indigo-300 transition-colors">
                    Clear filter
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Event list */}
        <div className="flex-1 rounded-2xl bg-white/[0.02] border border-white/[0.06] overflow-hidden flex flex-col">
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-8">
              <AlertCircle className="w-10 h-10 text-red-400" />
              <p className="text-white font-medium">Error loading events</p>
              <p className="text-white/40 text-sm">{error}</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-8">
              <Zap className="w-10 h-10 text-white/10" />
              <p className="text-white/40 text-sm">{events.length === 0 ? 'No events yet — process a video first.' : 'No events match your filters.'}</p>
              {events.length === 0 && <Link href="/upload" className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">Upload a video →</Link>}
            </div>
          ) : (
            <div className="overflow-y-auto flex-1">
              {/* Header row */}
              <div className="sticky top-0 grid grid-cols-[1fr_120px_80px_80px_40px] gap-3 px-4 py-2.5 bg-[#09090b] border-b border-white/[0.06] text-[10px] text-white/30 uppercase tracking-wider">
                <span>Event</span>
                <span>Time</span>
                <span>Confidence</span>
                <span>Person</span>
                <span></span>
              </div>
              {filtered.map((evt, i) => {
                const et = getEventType(evt);
                const id = getEventId(evt);
                return (
                  <div key={id || i}
                    className="grid grid-cols-[1fr_120px_80px_80px_40px] gap-3 px-4 py-3 border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors items-center group">
                    <div className="min-w-0">
                      <p className="text-sm text-white/80 font-medium truncate">{formatEventLabel(et)}</p>
                      {evt.rule_name && <p className="text-[10px] text-white/25 truncate">{evt.rule_name.replace(/_/g,' ')}</p>}
                    </div>
                    <span className="text-xs text-white/40 font-mono">{fmtTime(getTime(evt))}</span>
                    <ConfBar value={evt.confidence ?? 0} />
                    <div>
                      {evt.person_label && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/15 border border-violet-500/25 text-violet-300 flex items-center gap-1 w-fit">
                          <User size={8} /> {evt.person_label}
                        </span>
                      )}
                    </div>
                    <div className="flex justify-end">
                      {evt.video_id && (
                        <Link href={`/timeline/${evt.video_id}`}
                          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-lg hover:bg-white/5">
                          <ChevronRight size={14} className="text-white/40" />
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
