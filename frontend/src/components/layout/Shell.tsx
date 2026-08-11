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
    // BUG-32 FIX: bg-background → explicit bg-[#09090b]
    <div className="flex h-screen w-full bg-[#09090b] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col h-full overflow-y-auto">
        {/* BUG-27 FIX: Breadcrumb now reflects current route */}
        {/* BUG-28 FIX: Documentation button removed (was dead) */}
        <header className="h-16 flex-shrink-0 border-b border-white/[0.07] bg-[#09090b]/80 backdrop-blur-md flex items-center px-8 z-10 sticky top-0">
          <div className="text-sm text-white/40 font-medium">
            Time Compression Engine / <span className="text-white/70">{page}</span>
          </div>
          <div className="ml-auto flex items-center gap-4">
            {/* BUG-32 FIX: bg-accent → bg-gradient explicit */}
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 border border-white/20"></div>
          </div>
        </header>
        <main className="flex-1 p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
