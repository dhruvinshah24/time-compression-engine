'use client';
import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';

const ROUTE_LABELS: Record<string, string> = {
  '/':           'Dashboard',
  '/upload':     'Upload Video',
  '/events':     'Events',
  '/analytics':  'Analytics',
  '/settings':   'Settings',
};

function getBreadcrumb(pathname: string): string {
  if (pathname.startsWith('/timeline/'))   return 'Timeline';
  if (pathname.startsWith('/processing/')) return 'Processing';
  return ROUTE_LABELS[pathname] ?? 'Dashboard';
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const page = getBreadcrumb(pathname);

  return (
    <div className="flex h-screen w-full bg-[#08090d] text-slate-100 overflow-hidden font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col h-full overflow-y-auto min-w-0">
        <header className="h-16 flex-shrink-0 border-b border-white/[0.08] bg-[#090b10]/80 backdrop-blur-xl flex items-center justify-between px-8 z-10 sticky top-0">
          {/* Breadcrumb path */}
          <div className="flex items-center gap-2 text-[13px]">
            <span className="text-slate-400 font-medium">TCE</span>
            <span className="text-white/20">/</span>
            <span className="text-slate-200 font-semibold">{page}</span>
          </div>

          {/* Right Status / Telemetry bar */}
          <div className="flex items-center gap-5">
            <div className="hidden md:flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.07] text-[11px] font-mono text-slate-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></span>
              <span>GPU Accelerated</span>
              <span className="text-white/20">|</span>
              <span className="text-indigo-400 font-semibold">5.03× Real-time</span>
            </div>

          </div>
        </header>

        <main className="flex-1 p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
