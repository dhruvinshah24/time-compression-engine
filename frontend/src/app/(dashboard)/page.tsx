'use client';

import { motion } from 'framer-motion';
import { Video, Zap, TrendingDown, HardDrive, Plus, Clock, CheckCircle2, Play } from 'lucide-react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import Link from 'next/link';

const stats = [
  { label: 'Total Videos', value: '24', icon: Video, color: 'text-blue-400', bg: 'bg-blue-400/10' },
  { label: 'Events Detected', value: '1,847', icon: Zap, color: 'text-purple-400', bg: 'bg-purple-400/10' },
  { label: 'Avg Compression', value: '32:1', icon: TrendingDown, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  { label: 'Storage Saved', value: '847 GB', icon: HardDrive, color: 'text-amber-400', bg: 'bg-amber-400/10' },
];

const mockEvents = [
  { time: '08:17', event: 'Person Entered', conf: 94 },
  { time: '09:43', event: 'Parcel Delivered', conf: 87 },
  { time: '11:20', event: 'Vehicle Arrived', conf: 91 },
  { time: '14:05', event: 'Lights Turned Off', conf: 88 },
  { time: '15:33', event: 'Chair Moved', conf: 76 },
  { time: '16:48', event: 'Person Exited', conf: 93 },
];

const sparklineData = [ { v: 28 }, { v: 35 }, { v: 31 }, { v: 42 }, { v: 29 }, { v: 45 }, { v: 32 } ];

export default function DashboardPage() {
  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Welcome back</h1>
          <p className="text-muted mt-1">Today is {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>
        <Link href="/upload">
          <motion.button 
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white px-5 py-2.5 rounded-lg font-medium transition-colors glow-blue"
          >
            <Plus className="w-5 h-5" />
            New Upload
          </motion.button>
        </Link>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {stats.map((stat, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="glass-strong rounded-xl p-6 hover:-translate-y-1 transition-transform duration-300"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted font-medium mb-1">{stat.label}</p>
                <h3 className="text-3xl font-bold text-white">{stat.value}</h3>
              </div>
              <div className={`w-12 h-12 rounded-full ${stat.bg} ${stat.color} flex items-center justify-center`}>
                <stat.icon className="w-6 h-6" />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-8">
        <div className="col-span-2 space-y-6">
          <div className="glass rounded-xl border border-border p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-white">Recent Events Feed</h2>
              <Link href="/events" className="text-sm text-accent hover:text-accent-hover">View all</Link>
            </div>
            <div className="space-y-4">
              {mockEvents.map((evt, i) => (
                <div key={i} className="flex items-center gap-4 p-4 rounded-lg bg-surface border border-border/50 hover:border-border transition-colors">
                  <div className="text-sm font-mono text-muted">{evt.time}</div>
                  <div className="w-2 h-2 rounded-full bg-accent"></div>
                  <div className="flex-1 font-medium text-white">{evt.event}</div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted">Confidence</span>
                    <span className="text-sm font-mono text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded">{evt.conf}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass rounded-xl border border-border p-6">
            <h2 className="text-xl font-semibold text-white mb-6">Compression Ratio Trends</h2>
            <div className="h-[120px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sparklineData}>
                  <Line type="monotone" dataKey="v" stroke="#6366f1" strokeWidth={3} dot={{ fill: '#6366f1', strokeWidth: 2, r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="col-span-1">
          <div className="glass rounded-xl border border-border p-6 h-full">
            <h2 className="text-xl font-semibold text-white mb-6">Processing Queue</h2>
            
            <div className="space-y-6">
              {[
                { name: 'cam_front_door_04.mp4', progress: 78, status: 'Processing', icon: Clock, color: 'text-blue-400' },
                { name: 'warehouse_aisle_b.mkv', progress: 34, status: 'Processing', icon: Clock, color: 'text-blue-400' },
                { name: 'lab_experiment_22.mp4', progress: 100, status: 'Completed', icon: CheckCircle2, color: 'text-success' },
              ].map((job, i) => (
                <div key={i} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <Play className="w-4 h-4 text-muted flex-shrink-0" />
                      <span className="text-sm font-medium text-white truncate">{job.name}</span>
                    </div>
                    <span className="text-xs font-mono text-muted">{job.progress}%</span>
                  </div>
                  <div className="h-2 w-full bg-surface rounded-full overflow-hidden">
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${job.progress}%` }}
                      transition={{ duration: 1, delay: i * 0.2 }}
                      className={`h-full rounded-full ${job.progress === 100 ? 'bg-success' : 'bg-accent relative overflow-hidden'}`}
                    >
                      {job.progress < 100 && (
                        <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
                      )}
                    </motion.div>
                  </div>
                </div>
              ))}
            </div>
            
            <Link href="/processing/demo">
              <button className="w-full mt-8 py-2.5 rounded-lg border border-border text-sm text-white hover:bg-white/5 transition-colors">
                View All Jobs
              </button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
