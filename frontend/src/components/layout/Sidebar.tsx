'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Upload, Cpu, Zap, Sparkles, BarChart3, Settings, Timer, FlaskConical } from 'lucide-react';
import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';

const navItems = [
  { name: 'Dashboard',  href: '/',           icon: LayoutDashboard },
  { name: 'Upload',     href: '/upload',      icon: Upload },
  { name: 'Events',     href: '/events',      icon: Zap },
  { name: 'Analytics',  href: '/analytics',   icon: BarChart3 },
  { name: 'Settings',   href: '/settings',    icon: Settings },
];

const DEMO_KEY = 'tce_demo_mode';

export function Sidebar() {
  const pathname = usePathname();
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    setDemoMode(localStorage.getItem(DEMO_KEY) === 'true');
  }, []);

  const toggleDemo = () => {
    const next = !demoMode;
    setDemoMode(next);
    localStorage.setItem(DEMO_KEY, String(next));
  };

  return (
    <div className="w-[240px] flex-shrink-0 bg-background border-r border-border flex flex-col h-full glass">
      <div className="p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center glow-blue">
            <span className="font-bold text-white text-sm">TCE</span>
          </div>
          <span className="font-bold text-white tracking-tight">Time Compression</span>
        </div>
        <p className="text-xs text-muted">Hours of Video. Seconds of Truth.</p>
      </div>

      {/* Demo mode banner */}
      {demoMode && (
        <div className="mx-4 mb-2 px-3 py-2 bg-amber-400/10 border border-amber-400/20 rounded-lg">
          <p className="text-xs text-amber-400 font-medium flex items-center gap-1.5">
            <FlaskConical className="w-3.5 h-3.5" /> Demo Mode Active
          </p>
          <p className="text-xs text-amber-400/60 mt-0.5">Showing sample data</p>
        </div>
      )}

      <nav className="flex-1 px-4 py-4 space-y-1">
        {navItems.map((item) => {
          // Determine active: exact match or prefix (e.g. /processing/JOB-xxx)
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href));
          return (
            <Link key={item.name} href={item.href}>
              <motion.div
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-accent/10 text-accent glow-blue border border-accent/20'
                    : 'text-muted hover:text-white hover:bg-white/5'
                }`}
              >
                <item.icon className="w-5 h-5" />
                <span className="text-sm font-medium">{item.name}</span>
              </motion.div>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 mt-auto space-y-2">
        {/* Demo mode toggle */}
        <button
          onClick={toggleDemo}
          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border transition-colors text-xs ${
            demoMode
              ? 'bg-amber-400/10 border-amber-400/20 text-amber-400'
              : 'bg-surface border-border text-muted hover:text-white hover:bg-white/5'
          }`}
        >
          <span className="flex items-center gap-1.5">
            <FlaskConical className="w-3.5 h-3.5" />
            Demo Mode
          </span>
          <div className={`w-8 h-4 rounded-full border transition-colors relative ${
            demoMode ? 'bg-amber-400 border-amber-500' : 'bg-surface border-border'
          }`}>
            <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
              demoMode ? 'left-4' : 'left-0.5'
            }`} />
          </div>
        </button>

        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-surface border border-border">
          <span className="text-xs text-muted font-mono">v1.0.1</span>
          <div className="w-2 h-2 rounded-full bg-success animate-pulse-slow"></div>
        </div>
      </div>
    </div>
  );
}
