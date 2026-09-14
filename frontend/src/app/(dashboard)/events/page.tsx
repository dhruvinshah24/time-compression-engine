'use client';

import { useState, useEffect, useMemo } from 'react';
import { Filter, Zap, Loader2, AlertCircle, User, ChevronRight, Share2, Radio } from 'lucide-react';
import { api, API_BASE } from '@/lib/api/client';
import Link from 'next/link';
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ZAxis,
} from 'recharts';

// ── Types ─────────────────────────────────────────────────────────────────────
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

interface GraphNode {
  id: string;
  label: string;
  node_type: string;
  event_count: number;
  first_seen_ms: number;
  last_seen_ms: number;
  duration_s: number;
  event_types: string[];
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  label: string;
  weight: number;
}

interface EventGraph {
  video_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    node_count: number;
    edge_count: number;
    event_count: number;
    co_occurrence_edges: number;
    arc_edges: number;
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const getEventType = (e: EventRecord) => e.event_type ?? e.type ?? '';
const getEventId   = (e: EventRecord) => e.event_id ?? e.id ?? '';
const getTime      = (e: EventRecord) => ((e.start_ms ?? e.timestamp_ms ?? 0) / 1000);

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${(s % 60).toFixed(0)}s` : `${s.toFixed(1)}s`;
}

function fmtMs(ms: number) {
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}:${String(Math.floor(s % 60)).padStart(2,'0')}` : `${s.toFixed(0)}s`;
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

// ── Graph Visualization ───────────────────────────────────────────────────────
const NODE_COLORS = [
  '#818cf8', '#34d399', '#f59e0b', '#f472b6', '#38bdf8',
  '#a78bfa', '#4ade80', '#fb923c', '#e879f9', '#22d3ee',
];

interface GraphTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: { label: string; event_count: number; duration_s: number; first_seen_ms: number; last_seen_ms: number; event_types: string[] } }>;
}

function GraphTooltip({ active, payload }: GraphTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-[#0f1117] border border-white/10 rounded-xl p-3 text-xs shadow-xl min-w-[180px]">
      <p className="text-white font-semibold mb-1">{d.label}</p>
      <p className="text-white/40">{d.event_count} events</p>
      <p className="text-white/40">{fmtMs(d.first_seen_ms)} → {fmtMs(d.last_seen_ms)}</p>
      {d.event_types.slice(0, 3).map((et: string) => (
        <p key={et} className="text-white/25 text-[10px] truncate">{formatEventLabel(et)}</p>
      ))}
    </div>
  );
}

function EventGraphView({ videoIds }: { videoIds: string[] }) {
  const [graphData, setGraphData] = useState<EventGraph | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [selectedVideoId, setSelectedVideoId] = useState<string>(videoIds[0] ?? '');

  useEffect(() => {
    if (!selectedVideoId) return;
    setGraphLoading(true);
    setGraphError(null);
    fetch(`${API_BASE}/event-graph/${selectedVideoId}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setGraphData(d); setGraphLoading(false); })
      .catch(e => { setGraphError(e.message); setGraphLoading(false); });
  }, [selectedVideoId]);

  // Transform nodes to scatter chart data points
  const scatterData = useMemo(() => {
    if (!graphData?.nodes.length) return [];
    return graphData.nodes.map((node, i) => ({
      x: node.first_seen_ms / 1000,          // timeline position (seconds)
      y: i,                                   // vertical slot per actor
      z: Math.max(20, node.event_count * 15), // dot size = event count
      label: node.label,
      event_count: node.event_count,
      duration_s: node.duration_s,
      first_seen_ms: node.first_seen_ms,
      last_seen_ms: node.last_seen_ms,
      event_types: node.event_types,
      color: NODE_COLORS[i % NODE_COLORS.length],
      nodeType: node.node_type,
    }));
  }, [graphData]);

  if (videoIds.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-8">
        <Share2 className="w-10 h-10 text-white/10" />
        <p className="text-white/40 text-sm">No videos processed yet.</p>
        <Link href="/upload" className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
          Upload a video →
        </Link>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col gap-4 p-5 overflow-y-auto">
      {/* Video selector */}
      {videoIds.length > 1 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/30">Video:</span>
          <select
            value={selectedVideoId}
            onChange={e => setSelectedVideoId(e.target.value)}
            className="text-xs bg-white/5 border border-white/10 text-white/60 rounded-lg px-2 py-1"
          >
            {videoIds.map(id => <option key={id} value={id}>{id.slice(0, 8)}…</option>)}
          </select>
        </div>
      )}

      {graphLoading && (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
        </div>
      )}

      {graphError && (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
          <AlertCircle className="w-8 h-8 text-red-400" />
          <p className="text-white/40 text-sm">{graphError}</p>
        </div>
      )}

      {graphData && !graphLoading && (
        <>
          {/* Stats row */}
          <div className="flex items-center gap-4 text-xs text-white/30">
            <span><span className="text-white/60 font-mono">{graphData.stats.node_count}</span> actors</span>
            <span><span className="text-white/60 font-mono">{graphData.stats.event_count}</span> events</span>
            <span><span className="text-white/60 font-mono">{graphData.stats.co_occurrence_edges}</span> co-occurrences</span>
          </div>

          {graphData.nodes.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
              <Radio className="w-10 h-10 text-white/10" />
              <p className="text-white/40 text-sm">No actors identified in this video.</p>
              <p className="text-white/20 text-xs max-w-xs">Events need person or track attribution to appear in the graph.</p>
            </div>
          ) : (
            <>
              {/* Timeline scatter plot */}
              <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] p-4">
                <p className="text-[10px] text-white/25 uppercase tracking-wider mb-3">Actor Timeline (dot size = event count)</p>
                <ResponsiveContainer width="100%" height={Math.max(120, graphData.nodes.length * 40)}>
                  <ScatterChart margin={{ top: 8, right: 20, bottom: 8, left: 80 }}>
                    <XAxis
                      dataKey="x"
                      type="number"
                      domain={['dataMin', 'dataMax']}
                      tickFormatter={v => `${Math.round(v)}s`}
                      tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 10 }}
                      axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                      tickLine={false}
                    />
                    <YAxis
                      dataKey="y"
                      type="number"
                      domain={[-0.5, graphData.nodes.length - 0.5]}
                      ticks={graphData.nodes.map((_, i) => i)}
                      tickFormatter={i => graphData.nodes[i as number]?.label ?? ''}
                      tick={{ fill: 'rgba(255,255,255,0.35)', fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      width={75}
                    />
                    <ZAxis dataKey="z" range={[20, 200]} />
                    <Tooltip content={<GraphTooltip />} cursor={false} />
                    <Scatter data={scatterData} fillOpacity={0.85}>
                      {scatterData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>

              {/* Co-occurrence edges list */}
              {graphData.edges.filter(e => e.relation === 'CO_OCCURRENCE').length > 0 && (
                <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] p-4">
                  <p className="text-[10px] text-white/25 uppercase tracking-wider mb-3">Co-occurrence Relationships</p>
                  <div className="space-y-1">
                    {graphData.edges
                      .filter(e => e.relation === 'CO_OCCURRENCE')
                      .sort((a, b) => b.weight - a.weight)
                      .slice(0, 10)
                      .map(edge => (
                        <div key={edge.id} className="flex items-center gap-2 text-xs">
                          <span className="text-white/50 truncate max-w-[100px]">
                            {graphData.nodes.find(n => n.id === edge.source)?.label ?? edge.source}
                          </span>
                          <span className="text-white/20">↔</span>
                          <span className="text-white/50 truncate max-w-[100px]">
                            {graphData.nodes.find(n => n.id === edge.target)?.label ?? edge.target}
                          </span>
                          <span className="text-[10px] text-indigo-400/60 font-mono ml-auto">{edge.weight}×</span>
                          <span className="text-[9px] text-white/15">{edge.label}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
type Tab = 'list' | 'graph';

export default function EventsPage() {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [minConf, setMinConf] = useState(0);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [tab, setTab] = useState<Tab>('list');

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

  // Unique video IDs for graph selector
  const videoIds = useMemo(() =>
    Array.from(new Set(events.map(e => e.video_id).filter(Boolean) as string[])),
    [events]
  );

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
          <p className="text-white/30 text-sm mt-0.5">
            {filtered.length} events{selectedTypes.size > 0 || minConf > 0 ? ' (filtered)' : ''} · {events.length} total
          </p>
        </div>
        {/* Tab switcher */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-white/[0.04] border border-white/[0.07]">
          {([['list', 'Event List'], ['graph', 'Actor Graph']] as const).map(([t, label]) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                tab === t
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-white/40 hover:text-white hover:bg-white/5'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'graph' ? (
        <div className="flex-1 rounded-2xl bg-white/[0.02] border border-white/[0.06] overflow-hidden flex flex-col">
          <EventGraphView videoIds={videoIds} />
        </div>
      ) : (
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
      )}
    </div>
  );
}
