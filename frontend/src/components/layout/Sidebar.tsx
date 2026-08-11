'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Upload, Zap, BarChart3, Settings, FlaskConical } from 'lucide-react';
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

  // BUG-30 FIX: Timeline and processing pages highlight Dashboard
  const getIsActive = (href: string) => {
    if (href === '/') {
      return pathname === '/'
        || pathname.startsWith('/timeline')
        || pathname.startsWith('/processing');
    }
    return pathname === href || (href !== '/' && pathname.startsWith(href));
  };

  return (
    <div className="w-[240px] flex-shrink-0 bg-[#09090b] border-r border-white/[0.07] flex flex-col h-full">
      <div className="p-6">
        <div className="flex items-center gap-3 mb-2">
          {/* BUG-32 FIX: bg-accent → bg-indigo-600 */}
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <span className="font-bold text-white text-sm">TCE</span>
          </div>
          <span className="font-bold text-white tracking-tight">Time Compression</span>
        </div>
        {/* BUG-32 FIX: text-muted → text-white/40 */}
        <p className="text-xs text-white/40">Hours of Video. Seconds of Truth.</p>
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
          const isActive = getIsActive(item.href);
          return (
            <Link key={item.name} href={item.href}>
              <motion.div
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-indigo-600/10 text-indigo-400 border border-indigo-500/20'
                    : 'text-white/40 hover:text-white hover:bg-white/5'
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
              : 'bg-white/[0.03] border-white/[0.07] text-white/40 hover:text-white hover:bg-white/5'
          }`}
        >
          <span className="flex items-center gap-1.5">
            <FlaskConical className="w-3.5 h-3.5" />
            Demo Mode
          </span>
          <div className={`w-8 h-4 rounded-full border transition-colors relative ${
            demoMode ? 'bg-amber-400 border-amber-500' : 'bg-white/5 border-white/10'
          }`}>
            <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
              demoMode ? 'left-4' : 'left-0.5'
            }`} />
          </div>
        </button>

        {/* BUG-29 FIX: bg-success → bg-emerald-400, animate-pulse-slow → animate-pulse */}
        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.07]">
          <span className="text-xs text-white/40 font-mono">v1.0.1</span>
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
        </div>
      </div>
    </div>
  );
}
