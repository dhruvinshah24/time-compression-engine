'use client';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';
import { api } from '@/lib/api/client';

const ROUTE_LABELS: Record<string, string> = {
  '/':          'Dashboard',
  '/upload':    'Upload',
  '/events':    'Events',
  '/analytics': 'Analytics',
  '/settings':  'Settings',
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

  useEffect(() => {
    let mounted = true;
    api.health()
      .then((res) => { if (mounted) setHealth(res); })
      .catch(() => {});
    return () => { mounted = false; };
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
      <Sidebar />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', minWidth: 0 }}>
        {/* Top bar — only on standard dashboard pages */}
        {!isTimeline && (
          <header style={{
            height: 50,
            flexShrink: 0,
            borderBottom: '1px solid var(--border)',
            backgroundColor: 'var(--bg-sidebar)',
            display: 'flex',
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

        <main style={{
          flex: 1,
          padding: isTimeline ? '16px 20px' : '24px 28px',
          maxWidth: isTimeline ? '100%' : 1400,
          width: '100%',
          margin: isTimeline ? '0' : '0 auto',
          boxSizing: 'border-box'
        }}>
          {children}
        </main>
      </div>
    </div>
  );
}
