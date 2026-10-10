'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Upload, Zap, BarChart3, Settings, BookOpen } from 'lucide-react';
import { motion } from 'framer-motion';

const navItems = [
  { name: 'Dashboard',  href: '/',           icon: LayoutDashboard },
  { name: 'Upload',     href: '/upload',      icon: Upload },
  { name: 'Events',     href: '/events',      icon: Zap },
  { name: 'Analytics',  href: '/analytics',   icon: BarChart3 },
  { name: 'Settings',   href: '/settings',    icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  // Extract videoId from pathname for context-aware Stories link
  const timelineMatch = pathname.match(/\/timeline\/([^/]+)/);
  const storiesMatch  = pathname.match(/\/stories\/([^/]+)/);
  const summaryMatch  = pathname.match(/\/summary\/([^/]+)/);
  const contextVideoId = timelineMatch?.[1] ?? storiesMatch?.[1] ?? summaryMatch?.[1] ?? 'VID-PHASE6-06CE78E1';

  const getIsActive = (href: string) => {
    if (href === '/') {
      return pathname === '/'
        || pathname.startsWith('/timeline')
        || pathname.startsWith('/processing');
    }
    return pathname === href || (href !== '/' && pathname.startsWith(href));
  };

  const isStoriesActive = pathname.startsWith('/stories');

  return (
    <aside className="w-[260px] flex-shrink-0 bg-[#090b10]/95 backdrop-blur-2xl border-r border-white/[0.08] flex flex-col h-full relative z-20 select-none">
      {/* Brand Header */}
      <div className="p-6 border-b border-white/[0.06]">
        <Link href="/" className="flex items-center gap-3.5 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/25 ring-1 ring-white/20 group-hover:scale-105 transition-transform duration-200">
            <span className="font-extrabold text-white text-sm tracking-wider">TCE</span>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-slate-100 text-[15px] tracking-tight group-hover:text-white transition-colors">Time Compression</span>
            </div>
            <p className="text-[11px] font-medium text-slate-400">Intelligence Engine</p>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3.5 py-5 space-y-1.5 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
          Platform
        </div>

        {navItems.map((item) => {
          const isActive = getIsActive(item.href);
          return (
            <Link key={item.name} href={item.href}>
              <div
                className={`relative flex items-center gap-3.5 px-3.5 py-2.5 rounded-xl transition-all duration-200 group ${
                  isActive
                    ? 'nav-pill-active font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="activeNavIndicator"
                    className="absolute left-0 w-1 h-5 rounded-r-full bg-indigo-400 shadow-[0_0_12px_#818cf8]"
                    transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                  />
                )}
                <item.icon className={`w-4 h-4 transition-colors ${isActive ? 'text-indigo-400' : 'text-slate-400 group-hover:text-slate-200'}`} />
                <span className="text-[13px]">{item.name}</span>
                {item.name === 'Events' && (
                  <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    Live
                  </span>
                )}
              </div>
            </Link>
          );
        })}

        <div className="pt-4 px-3 pb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
          Analysis
        </div>

        {/* Stories Link */}
        <Link href={`/stories/${contextVideoId}`}>
          <div
            className={`relative flex items-center gap-3.5 px-3.5 py-2.5 rounded-xl transition-all duration-200 group ${
              isStoriesActive
                ? 'nav-pill-active font-semibold'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
            }`}
          >
            {isStoriesActive && (
              <motion.div
                layoutId="activeNavIndicator"
                className="absolute left-0 w-1 h-5 rounded-r-full bg-indigo-400 shadow-[0_0_12px_#818cf8]"
                transition={{ type: 'spring', stiffness: 350, damping: 30 }}
              />
            )}
            <BookOpen className={`w-4 h-4 transition-colors ${isStoriesActive ? 'text-indigo-400' : 'text-slate-400 group-hover:text-slate-200'}`} />
            <span className="text-[13px]">Story Arcs</span>
            <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-400 border border-purple-500/20">
              Arcs
            </span>
          </div>
        </Link>
      </nav>

      {/* System Status Card in Footer */}
      <div className="p-3.5 mt-auto border-t border-white/[0.06]">
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:bg-white/[0.04] transition-colors">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-medium text-slate-300">Engine Core</span>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-[10px] font-mono text-emerald-400">READY</span>
            </div>
          </div>
          <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
            <span>v1.1 Intelligence</span>
            <span>RTX 5050</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
