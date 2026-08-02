'use client';

import { motion } from 'framer-motion';
import { Search, Filter, Clock, Zap, Download, PlayCircle, Eye, Settings2 } from 'lucide-react';
import { useState } from 'react';

const MOCK_EVENTS = [
  { id: '1', time: '08:17:22', type: 'Person Entered', conf: 94, duration: '3.2s', desc: 'Individual entered through main entrance', objects: ['person'] },
  { id: '2', time: '08:25:05', type: 'Locker Opened', conf: 82, duration: '12.5s', desc: 'Locker #4 accessed in hallway', objects: ['person', 'locker'] },
  { id: '3', time: '08:27:14', type: 'Parcel Retrieved', conf: 88, duration: '4.1s', desc: 'Package removed from locker', objects: ['person', 'parcel'] },
  { id: '4', time: '08:29:50', type: 'Person Exited', conf: 91, duration: '2.8s', desc: 'Individual left via side exit', objects: ['person'] },
  { id: '5', time: '11:41:03', type: 'Parcel Delivered', conf: 87, duration: '8.4s', desc: 'Courier dropped off medium package', objects: ['person', 'parcel'] },
  { id: '6', time: '14:05:33', type: 'Lights Turned Off', conf: 85, duration: '1.0s', desc: 'Area illumination dropped below threshold', objects: ['environment'] },
  { id: '7', time: '15:33:12', type: 'Chair Moved', conf: 76, duration: '5.5s', desc: 'Office chair relocated 2 meters', objects: ['chair'] },
  { id: '8', time: '16:48:05', type: 'Vehicle Arrived', conf: 93, duration: '15.2s', desc: 'White van parked in loading zone', objects: ['vehicle'] },
];

export default function TimelinePage({ params }: { params: { videoId: string } }) {
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null);

  return (
    <div className="h-full flex flex-col animate-slide-up space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-white tracking-tight">cam_front_door_04.mp4</h1>
          <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-emerald-400 text-xs font-medium">
            <TrendingDownIcon className="w-3.5 h-3.5" /> 1,920:1 Ratio
          </div>
          <span className="text-sm text-muted">Aug 14, 2024</span>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-surface border border-border rounded-lg text-sm text-white hover:bg-white/5 transition-colors">
            <Download className="w-4 h-4 text-muted" /> Export JSON
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium text-white transition-colors glow-blue">
            <PlayCircle className="w-4 h-4" /> Play Highlight
          </button>
        </div>
      </div>

      <div className="flex items-center gap-4 p-4 bg-surface border border-border rounded-xl">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input 
            type="text" 
            placeholder="Search events, objects, descriptions..." 
            className="w-full bg-background border border-border rounded-lg pl-9 pr-4 py-2 text-sm text-white focus:border-accent outline-none transition-colors"
          />
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 px-3 py-2 bg-background border border-border rounded-lg text-sm text-white hover:bg-white/5">
            <Filter className="w-4 h-4 text-muted" /> Type
          </button>
          <button className="flex items-center gap-2 px-3 py-2 bg-background border border-border rounded-lg text-sm text-white hover:bg-white/5">
            <Settings2 className="w-4 h-4 text-muted" /> Confidence &gt; 80%
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 space-y-4 relative">
        <div className="absolute left-8 top-0 bottom-0 w-px bg-border z-0"></div>
        
        {MOCK_EVENTS.map((event, idx) => (
          <motion.div 
            key={event.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.1 }}
            className={`relative z-10 flex gap-6 ${selectedEvent === event.id ? 'scale-[1.01] transition-transform' : ''}`}
            onClick={() => setSelectedEvent(event.id)}
          >
            <div className="w-16 flex flex-col items-center pt-4">
              <div className="w-3 h-3 rounded-full bg-accent ring-4 ring-background mb-2"></div>
              <div className="text-xs font-mono text-muted">{event.time}</div>
            </div>
            
            <div className={`flex-1 glass rounded-xl border p-5 cursor-pointer transition-colors ${
              selectedEvent === event.id ? 'border-accent bg-accent/5' : 'border-border hover:border-border/80'
            }`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-surface border border-border flex items-center justify-center">
                    <Zap className="w-5 h-5 text-accent" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white">{event.type}</h3>
                    <p className="text-sm text-muted">{event.desc}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded">
                    {event.conf}% conf
                  </span>
                  <span className="text-xs text-muted flex items-center gap-1">
                    <Clock className="w-3 h-3" /> {event.duration}
                  </span>
                </div>
              </div>
              
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-border/50">
                <div className="flex gap-2">
                  {event.objects.map(obj => (
                    <span key={obj} className="text-xs bg-surface border border-border px-2 py-1 rounded text-muted">
                      {obj}
                    </span>
                  ))}
                </div>
                <button className="text-xs text-accent hover:text-accent-hover flex items-center gap-1">
                  <Eye className="w-3 h-3" /> Preview Segment
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function TrendingDownIcon(props: React.SVGProps<SVGSVGElement>) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/></svg>;
}
