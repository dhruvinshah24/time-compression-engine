'use client';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, PieChart, Pie, Cell } from 'recharts';

const ratioData = [
  { date: 'Aug 08', ratio: 24 }, { date: 'Aug 09', ratio: 35 }, { date: 'Aug 10', ratio: 28 }, 
  { date: 'Aug 11', ratio: 42 }, { date: 'Aug 12', ratio: 39 }, { date: 'Aug 13', ratio: 45 }, { date: 'Aug 14', ratio: 32 }
];

const eventTypes = [
  { name: 'Person Entered', value: 400 },
  { name: 'Vehicle', value: 300 },
  { name: 'Object Moved', value: 300 },
  { name: 'Anomaly', value: 200 },
];
const COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#f59e0b'];

const speedData = [
  { stage: 's01', ms: 2340 }, { stage: 's02', ms: 31204 }, { stage: 's03', ms: 18392 }, 
  { stage: 's04', ms: 45100 }, { stage: 's05', ms: 22400 }, { stage: 's06', ms: 19800 }
];

export default function AnalyticsPage() {
  return (
    <div className="space-y-6 animate-slide-up">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">System Analytics</h1>
        <p className="text-muted mt-1">Performance and compression metrics across all processed jobs.</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="glass rounded-xl border border-border p-6 h-[350px] flex flex-col">
          <h2 className="text-lg font-medium text-white mb-6">Average Compression Ratio</h2>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ratioData}>
                <defs>
                  <linearGradient id="colorRatio" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis dataKey="date" stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}:1`} />
                <Tooltip contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', color: '#fff' }} itemStyle={{ color: '#6366f1' }} />
                <Area type="monotone" dataKey="ratio" stroke="#6366f1" strokeWidth={3} fillOpacity={1} fill="url(#colorRatio)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass rounded-xl border border-border p-6 h-[350px] flex flex-col">
          <h2 className="text-lg font-medium text-white mb-6">Event Type Distribution</h2>
          <div className="flex-1 min-h-0 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={eventTypes} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="value">
                  {eventTypes.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', color: '#fff' }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-3 justify-center ml-4">
              {eventTypes.map((entry, index) => (
                <div key={entry.name} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index] }}></div>
                  <span className="text-sm text-gray-300">{entry.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="glass rounded-xl border border-border p-6 h-[350px] flex flex-col col-span-2">
          <h2 className="text-lg font-medium text-white mb-6">Processing Speed per Stage (ms)</h2>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={speedData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis dataKey="stage" stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: '#27272a', opacity: 0.4 }} contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', color: '#fff' }} />
                <Bar dataKey="ms" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
