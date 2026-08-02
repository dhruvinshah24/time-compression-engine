'use client';

import { useState, useEffect } from 'react';
import { LayoutGrid, Network, Filter, Zap, Loader2 } from 'lucide-react';
import { api } from '@/lib/api/client';

interface EventRecord {
  id?: string;
  type?: string;
  event_type?: string;
  timestamp_ms?: number;
  confidence?: number;
}

export default function EventsPage() {
  const [activeTab, setActiveTab] = useState<'list' | 'graph'>('list');
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (api.events.list() as Promise<EventRecord[]>)
      .then(res => {
        if (mounted) {
          setEvents(Array.isArray(res) ? res : []);
          setLoading(false);
        }
      })
      .catch(err => {
        if (mounted) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => { mounted = false; };
  }, []);

  return (
    <div className="h-full flex flex-col animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white tracking-tight">Event Intelligence</h1>
          <span className="px-2.5 py-0.5 rounded-full bg-accent/10 text-accent text-sm font-medium border border-accent/20">
            {events.length} Total Events
          </span>
        </div>
        <div className="flex bg-surface p-1 rounded-lg border border-border">
          <button
            onClick={() => setActiveTab('list')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm transition-colors ${activeTab === 'list' ? 'bg-background text-white shadow-sm' : 'text-muted hover:text-white'}`}
          >
            <LayoutGrid className="w-4 h-4" /> List
          </button>
          <button
            onClick={() => setActiveTab('graph')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm transition-colors ${activeTab === 'graph' ? 'bg-background text-white shadow-sm' : 'text-muted hover:text-white'}`}
          >
            <Network className="w-4 h-4" /> Graph
          </button>
        </div>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Filter panel */}
        <div className="w-64 flex-shrink-0 space-y-6 overflow-y-auto pr-2">
          <div className="glass rounded-xl border border-border p-5">
            <div className="flex items-center gap-2 mb-4 text-white font-medium">
              <Filter className="w-4 h-4" /> Filters
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-muted font-medium mb-2 block">Event Type</label>
                <div className="space-y-2">
                  {['Person Entered', 'Object Moved', 'Vehicle Arrived', 'Anomaly'].map(t => (
                    <label key={t} className="flex items-center gap-2 text-sm text-gray-300">
                      <input type="checkbox" className="rounded border-border bg-surface accent-accent" defaultChecked />
                      {t}
                    </label>
                  ))}
                </div>
              </div>
              <div className="pt-4 border-t border-border">
                <label className="text-xs text-muted font-medium mb-2 block">Min Confidence</label>
                <input type="range" min="0" max="100" defaultValue="80" className="w-full accent-accent" />
                <div className="flex justify-between text-xs text-muted mt-1">
                  <span>0%</span><span>80%</span><span>100%</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 glass rounded-xl border border-border overflow-hidden relative">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-accent animate-spin" />
            </div>
          ) : error ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <div className="text-red-400 mb-2">Error loading events</div>
              <div className="text-sm text-muted">{error}</div>
            </div>
          ) : activeTab === 'list' ? (
            <div className="p-6 overflow-y-auto h-full">
              {events.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center py-16">
                  <Zap className="w-12 h-12 text-muted opacity-30 mb-4" />
                  <h3 className="text-lg font-medium text-white mb-2">No events detected yet</h3>
                  <p className="text-sm text-muted max-w-xs">
                    Process a video to see events here. Events appear after the pipeline runs s01–s12.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {events.map((evt, i) => (
                    <div key={evt.id ?? i} className="bg-surface border border-border rounded-lg p-4 hover:border-accent/50 transition-colors cursor-pointer">
                      <div className="w-full h-32 bg-background rounded mb-3 border border-border flex items-center justify-center relative overflow-hidden group">
                        <span className="text-muted text-xs">Preview</span>
                        <div className="absolute inset-0 bg-accent/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      <h3 className="font-medium text-white mb-1">{evt.type ?? evt.event_type ?? 'Event'}</h3>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-muted">{evt.timestamp_ms != null ? `${(evt.timestamp_ms / 1000).toFixed(1)}s` : '—'}</span>
                        <span className="text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">
                          {Math.round((evt.confidence ?? 0) * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="absolute inset-0 flex items-center justify-center flex-col p-8">
              <Network className="w-16 h-16 text-muted mb-4 opacity-50" />
              <h2 className="text-xl font-medium text-white mb-2">Event graph is generated after pipeline completes.</h2>
              <p className="text-muted text-center max-w-md mb-6">
                Interactive causal event graphs will be available in Phase 4. This feature maps semantic relationships between localized events.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
