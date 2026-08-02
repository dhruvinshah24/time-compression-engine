'use client';

import { useState } from 'react';
import { LayoutGrid, Network, Filter, Download } from 'lucide-react';
import { motion } from 'framer-motion';

export default function EventsPage() {
  const [activeTab, setActiveTab] = useState<'list' | 'graph'>('list');

  return (
    <div className="h-full flex flex-col animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white tracking-tight">Event Intelligence</h1>
          <span className="px-2.5 py-0.5 rounded-full bg-accent/10 text-accent text-sm font-medium border border-accent/20">
            1,847 Total Events
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

        <div className="flex-1 glass rounded-xl border border-border overflow-hidden relative">
          {activeTab === 'list' ? (
            <div className="p-6 grid grid-cols-3 gap-4 overflow-y-auto h-full">
              {Array.from({length: 12}).map((_, i) => (
                <div key={i} className="bg-surface border border-border rounded-lg p-4 hover:border-accent/50 transition-colors cursor-pointer">
                  <div className="w-full h-32 bg-[#09090b] rounded mb-3 border border-border flex items-center justify-center relative overflow-hidden group">
                    <span className="text-muted text-xs">Preview</span>
                    <div className="absolute inset-0 bg-accent/10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                  </div>
                  <h3 className="font-medium text-white mb-1">Person Entered</h3>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted">Today, 08:17</span>
                    <span className="text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">94%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="absolute inset-0 flex items-center justify-center flex-col p-8">
              <Network className="w-16 h-16 text-muted mb-4 opacity-50" />
              <h2 className="text-xl font-medium text-white mb-2">Event Graph Visualization</h2>
              <p className="text-muted text-center max-w-md mb-6">Interactive causal event graphs will be available in Phase 4. This feature maps semantic relationships between localized events.</p>
              <div className="px-4 py-2 bg-accent/10 text-accent rounded-lg text-sm border border-accent/20">Coming Soon</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
