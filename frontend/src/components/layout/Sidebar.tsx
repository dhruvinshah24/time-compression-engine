'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, Clock, Zap, GitFork, Upload, BarChart3, Settings
} from 'lucide-react';
import { api } from '@/lib/api/client';

export function Sidebar() {
  const pathname = usePathname();
  const [firstVideoId, setFirstVideoId] = useState<string>('VID-PHASE6-06CE78E1');

  useEffect(() => {
    let mounted = true;
    api.videos.list()
      .then((vids) => {
        if (mounted && Array.isArray(vids) && vids.length > 0 && vids[0]?.id) {
          setFirstVideoId(vids[0].id);
        }
      })
      .catch(() => {});
    return () => { mounted = false; };
  }, []);

  const timelineMatch = pathname.match(/\/timeline\/([^/]+)/);
  const storiesMatch  = pathname.match(/\/stories\/([^/]+)/);
  const summaryMatch  = pathname.match(/\/summary\/([^/]+)/);
  const contextVideoId = timelineMatch?.[1] ?? storiesMatch?.[1] ?? summaryMatch?.[1] ?? firstVideoId;

  const navItems = [
    { name: 'Dashboard',   href: '/',                           icon: LayoutDashboard },
    { name: 'Timeline',    href: `/timeline/${contextVideoId}`, icon: Clock },
    { name: 'Events',      href: '/events',                     icon: Zap },
    { name: 'Story Arcs',  href: `/stories/${contextVideoId}`,  icon: GitFork },
    { name: 'Upload',      href: '/upload',                     icon: Upload },
    { name: 'Analytics',   href: '/analytics',                  icon: BarChart3 },
    { name: 'Settings',    href: '/settings',                   icon: Settings },
  ];

  const prewarmData = (href: string) => {
    try {
      if (href === '/') {
        api.jobs.list().catch(() => {});
        api.analytics().catch(() => {});
        api.events.list().catch(() => {});
      } else if (href.startsWith('/timeline')) {
        api.timeline(contextVideoId).catch(() => {});
      } else if (href === '/events') {
        api.events.list({ limit: '300' }).catch(() => {});
        api.videos.list().catch(() => {});
      } else if (href.startsWith('/stories')) {
        api.stories(contextVideoId).catch(() => {});
      } else if (href === '/analytics') {
        api.analytics().catch(() => {});
        api.jobs.list().catch(() => {});
      } else if (href === '/settings') {
        api.settings.list().catch(() => {});
      }
    } catch {
      // Ignore pre-warm errors
    }
  };

  const getIsActive = (href: string) => {
    if (href === '/') return pathname === '/';
    if (href.startsWith('/timeline')) return pathname.startsWith('/timeline');
    if (href.startsWith('/stories')) return pathname.startsWith('/stories');
    return pathname === href || pathname.startsWith(href);
  };

  return (
    <aside
      style={{
        width: 220,
        flexShrink: 0,
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border)',
        zIndex: 20,
        userSelect: 'none',
      }}
    >
      {/* Brand */}
      <div style={{ padding: '18px 18px 14px', borderBottom: '1px solid var(--border-dim)' }}>
        <Link href="/" prefetch={true} style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{
            width: 28, height: 28, borderRadius: 6,
            backgroundColor: 'var(--accent-bg)',
            border: '1px solid var(--accent-dim)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.05em' }}>TCE</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>TCE</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>•</span>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>Engine</span>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '16px 10px', overflowY: 'auto' }}>
        {navItems.map((item) => {
          const isActive = getIsActive(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              prefetch={true}
              onMouseEnter={() => prewarmData(item.href)}
              style={{ textDecoration: 'none' }}
            >
              <div
                style={{
                  display: 'flex', alignItems: 'center', gap: 11,
                  padding: '9px 12px',
                  borderRadius: 6, marginBottom: 3,
                  backgroundColor: isActive ? 'var(--accent-bg)' : 'transparent',
                  color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                  fontWeight: isActive ? 600 : 500,
                  fontSize: 13,
                  transition: 'background 0.12s, color 0.12s',
                  cursor: 'pointer',
                  border: isActive ? '1px solid rgba(98, 221, 176, 0.35)' : '1px solid transparent',
                }}
              >
                <item.icon size={16} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.7 }} />
                <span>{item.name}</span>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* Footer matching reference */}
      <div style={{
        padding: '14px 16px',
        borderTop: '1px solid var(--border-dim)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: 11,
        fontFamily: 'var(--font-mono)',
        color: 'var(--text-muted)'
      }}>
        <span>v2.4.1-rc</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
          <span style={{ color: 'var(--accent)' }}>Online</span>
        </div>
      </div>
    </aside>
  );
}
