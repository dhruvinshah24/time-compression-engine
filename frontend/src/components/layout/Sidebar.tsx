'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Upload, Cpu, Zap, Sparkles, BarChart3, Settings, Timer } from 'lucide-react';
import { motion } from 'framer-motion';

const navItems = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Uploads', href: '/upload', icon: Upload },
  { name: 'Processing', href: '/processing/demo', icon: Cpu },
  { name: 'Timeline', href: '/timeline/demo', icon: Timer },
  { name: 'Events', href: '/events', icon: Zap },
  { name: 'AI Summary', href: '/summary/demo', icon: Sparkles },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-[240px] flex-shrink-0 bg-[#0d0d10] border-r border-[#1f1f23] flex flex-col h-full glass">
      <div className="p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center glow-blue">
            <span className="font-bold text-white text-sm">TCE</span>
          </div>
          <span className="font-bold text-white tracking-tight">Time Compression</span>
        </div>
        <p className="text-xs text-muted">Hours of Video. Seconds of Truth.</p>
      </div>

      <nav className="flex-1 px-4 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
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

      <div className="p-4 mt-auto">
        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-surface border border-border">
          <span className="text-xs text-muted font-mono">System v2.4.1</span>
          <div className="w-2 h-2 rounded-full bg-success animate-pulse-slow"></div>
        </div>
      </div>
    </div>
  );
}
