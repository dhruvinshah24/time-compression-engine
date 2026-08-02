'use client';

import { motion } from 'framer-motion';
import { Download, PlayCircle, Share2, Sparkles, Clock, Calendar, FileText } from 'lucide-react';
import { ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

export default function SummaryPage({ params }: { params: { videoId: string } }) {
  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-purple-400" />
            AI Summary & Highlight
          </h1>
          <p className="text-muted mt-2">cam_front_door_04.mp4 • Processed on Aug 14, 2024</p>
        </div>
        <div className="flex gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-surface border border-border rounded-lg text-sm text-white hover:bg-white/5 transition-colors">
            <Share2 className="w-4 h-4 text-muted" /> Share
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover rounded-lg text-sm font-medium text-white transition-colors glow-blue">
            <Download className="w-4 h-4" /> Download Report
          </button>
        </div>
      </div>

      <div className="glass-strong rounded-2xl border border-border p-8 text-center relative overflow-hidden">
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-accent/20 rounded-full blur-3xl"></div>
        <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-purple-500/20 rounded-full blur-3xl"></div>
        
        <h2 className="text-xl font-medium text-white mb-8 relative z-10">Time Compression Result</h2>
        
        <div className="flex items-center justify-center gap-8 mb-8 relative z-10">
          <div className="text-right">
            <div className="text-4xl font-bold text-white mb-1">24 hours</div>
            <div className="text-sm text-muted">Original Duration</div>
          </div>
          
          <div className="flex flex-col items-center gap-2">
            <div className="w-32 h-1 bg-surface rounded-full overflow-hidden">
              <div className="w-full h-full bg-gradient-to-r from-muted to-accent"></div>
            </div>
            <div className="text-xs font-mono text-accent bg-accent/10 px-2 py-1 rounded">1,920:1 Ratio</div>
          </div>
          
          <div className="text-left">
            <div className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-accent to-purple-400 mb-1">45 seconds</div>
            <div className="text-sm text-muted">Highlight Duration</div>
          </div>
        </div>

        <button className="relative z-10 flex items-center gap-2 mx-auto px-8 py-3 bg-white text-black hover:bg-gray-100 rounded-full font-semibold transition-transform hover:scale-105">
          <PlayCircle className="w-5 h-5" /> Play Highlight Video
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 glass rounded-xl border border-border p-8">
          <div className="flex items-center gap-2 mb-6">
            <FileText className="w-5 h-5 text-accent" />
            <h2 className="text-xl font-semibold text-white">Narrative Summary</h2>
          </div>
          <div className="space-y-4 text-gray-300 leading-relaxed text-lg">
            <p>
              Between 08:17 and 16:48, the monitoring system identified <strong>8 meaningful events</strong> out of 86,400 seconds of footage.
            </p>
            <p>
              The session began with an individual entering through the main entrance and accessing a storage locker at 08:25, retrieving a parcel shortly after. A significant secondary event occurred at 11:41 when a courier delivered a new package.
            </p>
            <p>
              Activity concluded with a vehicle arriving in the loading zone at 16:48. In total, <strong>86,355 seconds of inactivity were successfully removed</strong> while maintaining the core narrative context.
            </p>
          </div>
        </div>

        <div className="col-span-1 space-y-6">
          <div className="glass rounded-xl border border-border p-6 text-center">
            <h3 className="text-sm font-medium text-muted mb-4">Narrative Coherence</h3>
            <div className="relative w-32 h-32 mx-auto">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={[{ value: 94 }, { value: 6 }]} cx="50%" cy="50%" innerRadius={40} outerRadius={55} dataKey="value" startAngle={90} endAngle={-270} stroke="none">
                    <Cell fill="#6366f1" />
                    <Cell fill="#27272a" />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex items-center justify-center flex-col">
                <span className="text-2xl font-bold text-white">94%</span>
              </div>
            </div>
            <p className="text-xs text-emerald-400 mt-2">High confidence score</p>
          </div>

          <div className="glass rounded-xl border border-border p-6">
            <h3 className="text-sm font-medium text-muted mb-4">Event Breakdown</h3>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Events Included</span>
                <span className="text-white font-medium">8</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Events Excluded</span>
                <span className="text-white font-medium">0</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Segments Preserved</span>
                <span className="text-white font-medium">8</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
