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
  const contextVideoId = timelineMatch?.[1] ?? storiesMatch?.[1] ?? summaryMatch?.[1] ?? null;

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
    <div className="w-[240px] flex-shrink-0 bg-[#09090b] border-r border-white/[0.07] flex flex-col h-full">
      <div className="p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <span className="font-bold text-white text-sm">TCE</span>
          </div>
          <span className="font-bold text-white tracking-tight">Time Compression</span>
        </div>
        <p className="text-xs text-white/40">Hours of Video. Seconds of Truth.</p>
      </div>

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

        {/* Stories — context-aware: links to current video if known, else disabled */}
        {contextVideoId ? (
          <Link href={`/stories/${contextVideoId}`}>
            <motion.div
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                isStoriesActive
                  ? 'bg-indigo-600/10 text-indigo-400 border border-indigo-500/20'
                  : 'text-white/40 hover:text-white hover:bg-white/5'
              }`}
            >
              <BookOpen className="w-5 h-5" />
              <span className="text-sm font-medium">Stories</span>
            </motion.div>
          </Link>
        ) : (
          <div className={`flex items-center gap-3 px-3 py-2.5 rounded-lg ${
            isStoriesActive
              ? 'bg-indigo-600/10 text-indigo-400 border border-indigo-500/20'
              : 'text-white/20 cursor-not-allowed'
          }`}>
            <BookOpen className="w-5 h-5" />
            <span className="text-sm font-medium">Stories</span>
            <span className="ml-auto text-[9px] text-white/15 font-mono">video ctx</span>
          </div>
        )}
      </nav>

      <div className="p-4 mt-auto space-y-2">
        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.07]">
          <span className="text-xs text-white/40 font-mono">v1.1-dev</span>
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
        </div>
      </div>
    </div>
  );
}
