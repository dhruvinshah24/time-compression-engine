'use client';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { Menu } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { api } from '@/lib/api/client';

const ROUTE_LABELS: Record<string, string> = {
  '/':           'Dashboard',
  '/timeline':   'Timelines',
  '/stories':    'Story Arcs',
  '/processing': 'Processing Jobs',
  '/summary':    'Executive Summaries',
  '/upload':     'Upload',
  '/events':     'Events',
  '/analytics':  'Analytics',
  '/settings':   'Settings',
};

function getBreadcrumb(pathname: string): string {
  if (pathname.startsWith('/timeline/'))   return 'Forensic Timeline';
  if (pathname.startsWith('/processing/')) return 'Processing';
  if (pathname.startsWith('/stories/'))    return 'Story Arcs';
  if (pathname.startsWith('/summary/'))    return 'Summary';
  return ROUTE_LABELS[pathname] ?? 'Dashboard';
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const page = getBreadcrumb(pathname);
  const isTimeline = pathname.startsWith('/timeline/');
  const [health, setHealth] = useState<any>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    api.health()
      .then((res) => { if (mounted) setHealth(res); })
      .catch(() => {});
    return () => { mounted = false; };
  }, []);

  // Close drawer on route change
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  // Close drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileNavOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const isOnline = health?.status === 'ok';
  const isCuda = health?.device_info?.cuda_available;
  const deviceLabel = isCuda
    ? `CUDA · ${health?.device_info?.gpu_name ?? 'Accelerated'}`
    : health?.device_info?.device === 'cpu'
    ? `CPU Mode · Pipeline v${health?.pipeline_version || '1.0.1'}`
    : 'TCE Engine Online';

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100%', overflow: 'hidden', backgroundColor: 'var(--bg-main)' }}>
      {/* Desktop Persistent Sidebar */}
      <Sidebar />

      {/* Mobile Slide-Over Drawer + Backdrop */}
      {mobileNavOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 lg:hidden"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          <div
            className="fixed inset-y-0 left-0 z-50 lg:hidden shadow-2xl flex"
            role="dialog"
            aria-modal="true"
            aria-label="Main Navigation Menu"
          >
            <Sidebar
              isMobileDrawer
              onNavigate={() => setMobileNavOpen(false)}
              onClose={() => setMobileNavOpen(false)}
            />
          </div>
        </>
      )}

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', minWidth: 0 }}>
        {/* Mobile Top Header (always available on <lg screens) */}
        <div className="flex lg:hidden h-12 shrink-0 items-center justify-between px-3 sm:px-4 bg-[var(--bg-sidebar)] border-b border-[var(--border)] sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileNavOpen(true)}
              aria-label="Open navigation menu"
              className="p-1.5 rounded bg-[var(--bg-panel)] hover:bg-[var(--bg-raised)] border border-[var(--border)] text-[var(--text-primary)] cursor-pointer"
            >
              <Menu size={18} />
            </button>
            <div className="flex items-center gap-2 text-xs">
              <span className="font-mono text-[10px] text-[var(--accent)] font-bold px-1.5 py-0.5 rounded bg-[var(--accent-bg)] border border-[var(--accent-dim)]">TCE</span>
              <span className="text-[var(--text-muted)] font-mono text-[11px]">/</span>
              <span className="text-[var(--text-primary)] font-semibold truncate max-w-[180px] sm:max-w-xs">{page}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-[var(--accent)]' : 'bg-[var(--warning)]'} animate-pulse`} />
            <span className="text-[10px] font-mono text-[var(--text-muted)] hidden sm:inline">Active</span>
          </div>
        </div>

        {/* Desktop Top bar — standard dashboard pages */}
        {!isTimeline && (
          <header className="hidden lg:flex" style={{
            height: 50,
            flexShrink: 0,
            borderBottom: '1px solid var(--border)',
            backgroundColor: 'var(--bg-sidebar)',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}>
            {/* Breadcrumb */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>TCE</span>
              <span style={{ color: 'var(--border)', fontSize: 11 }}>/</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{page}</span>
            </div>

            {/* Status bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '4px 10px',
                borderRadius: 4,
                backgroundColor: 'var(--bg-inset)',
                border: '1px solid var(--border-dim)',
                fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
              }}>
                <span className={`status-dot ${isOnline ? 'status-dot-success' : 'status-dot-warning'} animate-pulse-subtle`} />
                <span>{deviceLabel}</span>
                <span style={{ color: 'var(--border)' }}>·</span>
                <span style={{ color: 'var(--accent)', fontWeight: 500 }}>System Active</span>
              </div>
            </div>
          </header>
        )}

        <main className={isTimeline ? "p-3 sm:p-4 lg:p-5 w-full flex-1 box-border" : "p-4 sm:p-6 lg:p-7 max-w-[1400px] w-full mx-auto flex-1 box-border"}>
          {children}
        </main>
      </div>
    </div>
  );
}
